"""Persistência do pipeline (seções 4.10 e 5): execução, extração no grafo, materiais, tentativas,
avaliações do juiz e rastreabilidade frase → afirmação.

Duas implementações com a mesma interface:
- InMemoryPersistence: testes e execução sem banco (registros em listas, inspecionáveis).
- PostgresPersistence: produção (repositórios + grafo de nós e arestas no PostgreSQL).
"""
from __future__ import annotations

import hashlib
import json
import os
import uuid
from pathlib import Path
from typing import Any

from src.evaluation.deterministic import SECTIONS, section_content
from src.evaluation.text_utils import content_stems, sentences


DOCUMENTS_DIR = Path(os.getenv("DOCUMENTS_DIR", "data/documentos"))


def store_document_text(document_hash: str, content: str) -> Path:
    """Seção 5: o texto original fica em arquivo no volume, identificado pelo hash."""
    DOCUMENTS_DIR.mkdir(parents=True, exist_ok=True)
    path = DOCUMENTS_DIR / f"{document_hash}.txt"
    if not path.exists():
        path.write_text(content, encoding="utf-8")
    return path


def load_document_text(document_hash: str) -> str | None:
    path = DOCUMENTS_DIR / f"{document_hash}.txt"
    return path.read_text(encoding="utf-8") if path.exists() else None


# --------------------------------------------------------------------------------- rastreabilidade


def link_sentences(content: dict, fmt: str, extraction: dict, min_overlap: float = 0.4) -> list[dict]:
    """Liga cada frase gerada à afirmação com maior sobreposição de conteúdo.

    Prioriza as afirmações que o próprio gerador declarou no campo (afirmacao_ids); cai para todas.
    Frase sem afirmação acima do limiar fica sem ligação (conta contra a rastreabilidade, R12).
    """
    assertions = {a["id"]: a for a in (extraction or {}).get("assertions", [])}

    def best(sentence: str, preferred: list[str]) -> tuple[str | None, float]:
        stems = content_stems(sentence)
        if not stems:
            return None, 0.0
        scored = []
        for aid, a in assertions.items():
            overlap = len(stems & content_stems(a.get("text", "") + " " + (a.get("source_span") or {}).get("text", ""))) / len(stems)
            scored.append((overlap + (0.05 if aid in preferred else 0), aid, overlap))
        if not scored:
            return None, 0.0
        _bonus, aid, overlap = max(scored)
        return (aid, overlap) if overlap >= min_overlap else (None, overlap)

    fields: list[tuple[str, str, list[str]]] = []
    if fmt == "texto_analitico":
        fields = [(name, section_content(content.get(name)), (content.get(name) or {}).get("afirmacao_ids", []))
                  for name in SECTIONS]
    elif fmt == "carrossel":
        fields = [(f"slide_{s.get('order')}", f"{s.get('title', '')}. {s.get('body', '')}", s.get("afirmacao_ids", []))
                  for s in content.get("slides", [])]
    elif fmt == "roteiro_video":
        fields = [(f"cena_{s.get('order')}", s.get("fala_escrita", ""), s.get("afirmacao_ids", []))
                  for s in content.get("scenes", [])]
    links = []
    for field, text, preferred in fields:
        for sentence in sentences(text):
            aid, overlap = best(sentence, preferred or [])
            links.append({"campo": field, "texto": sentence, "afirmacao_id": aid, "sobreposicao": round(overlap, 3)})
    return links


def traceability_ratio(links: list[dict]) -> float:
    return sum(1 for link in links if link["afirmacao_id"]) / len(links) if links else 0.0


# ------------------------------------------------------------------------------------- interface


class InMemoryPersistence:
    """Persistência em memória com a mesma interface da PostgresPersistence."""

    def __init__(self) -> None:
        self.executions: dict[str, dict] = {}
        self.materials: dict[str, dict] = {}
        self.attempts: list[dict] = []
        self.judge_evaluations: list[dict] = []
        self.sentence_links: dict[str, list[dict]] = {}
        self.extractions: dict[str, dict] = {}

    def start_execution(self, document_hash: str, content: str, origin: dict, admission: dict | None,
                        levels: list[str], config_versions: dict) -> str:
        execution_id = str(uuid.uuid4())
        self.executions[execution_id] = {"hash_documento": document_hash, "origem": origin, "niveis": levels,
                                         "config": config_versions, "estado": "em_andamento"}
        return execution_id

    def persist_extraction(self, document_hash: str, content: str, extraction: dict, mapping_key: str | None = None,
                           id_prefix: str = "") -> None:
        self.extractions[document_hash] = extraction

    def create_material(self, execution_id: str, level: str, fmt: str) -> str:
        material_id = str(uuid.uuid4())
        self.materials[material_id] = {"id_execucao": execution_id, "nivel": level, "formato": fmt, "estado": "gerando"}
        return material_id

    def record_attempt(self, material_id: str, attempt: dict) -> str:
        attempt_id = str(uuid.uuid4())
        self.attempts.append({"id_tentativa": attempt_id, "id_material": material_id, **attempt})
        return attempt_id

    def record_judge(self, attempt_id: str, judge: dict) -> str:
        judge_id = str(uuid.uuid4())
        self.judge_evaluations.append({"id_avaliacao_juiz": judge_id, "id_tentativa": attempt_id, **judge})
        return judge_id

    def finalize_material(self, material_id: str, content: Any, status: str, warning: str | None,
                          classified_level: str | None, source_complexity: dict | None, glossary_version: str,
                          links: list[dict], document_hash: str | None = None) -> None:
        self.materials[material_id].update({"conteudo_gerado": content, "estado": "aguardando_revisao",
                                            "status_avaliacao": status, "aviso": warning,
                                            "nivel_classificado": classified_level,
                                            "complexidade_fonte": source_complexity, "versao_glossario": glossary_version})
        self.sentence_links[material_id] = links

    def finish_execution(self, execution_id: str, total_tokens: int, total_latency: float, status: str,
                         accumulate: bool = False) -> None:
        execution = self.executions.setdefault(execution_id, {})
        if accumulate:
            total_tokens += int(execution.get("total_tokens") or 0)
            total_latency += float(execution.get("latencia_total") or 0.0)
        execution.update({"total_tokens": total_tokens, "latencia_total": total_latency, "estado": status})


class PostgresPersistence(InMemoryPersistence):
    """Persistência no PostgreSQL (relacional + grafo de nós e arestas)."""

    def __init__(self, conn) -> None:
        super().__init__()
        self.conn = conn
        self._assertion_nodes: dict[str, dict[str, str]] = {}

    def _exec(self, query: str, params: tuple) -> Any:
        try:
            with self.conn.cursor() as cur:
                cur.execute(query, params)
                row = cur.fetchone() if cur.description else None
            self.conn.commit()
            return row
        except Exception:
            # transação abortada deixaria a conexão inutilizável para as próximas gravações
            if not getattr(self.conn, "closed", True):
                self.conn.rollback()
            raise

    def start_execution(self, document_hash, content, origin, admission, levels, config_versions) -> str:
        from src.persistence.repositories.document_repository import DocumentRepository

        admission = admission or {}
        raw_path = store_document_text(document_hash, content)
        DocumentRepository(self.conn).create(
            caminho_texto_bruto=str(raw_path),
            document_hash=document_hash, origin_type=origin.get("tipo_origem") or "texto",
            instituicao_origem=origin.get("instituicao"), titulo_origem=origin.get("titulo"),
            url_origem=origin.get("url"), idioma=admission.get("language"),
            status_integridade=admission.get("status", "admitido"), eh_financeiro=admission.get("is_financial"),
            quantidade_palavras=len(content.split()), quantidade_termos_tecnicos=admission.get("distinct_glossary_terms", 0),
        )
        config_hash = hashlib.sha256(json.dumps(config_versions, sort_keys=True).encode()).hexdigest()[:16]
        row = self._exec(
            """INSERT INTO execucoes (hash_documento, niveis_solicitados, hash_configuracao, versao_glossario, versao_prompt,
                   versao_modelo, versao_limiares, versao_rubrica, versao_estilo)
               VALUES (%s, %s::jsonb, %s, %s, %s, %s, %s, %s, %s) RETURNING id_execucao""",
            (document_hash, json.dumps(levels), config_hash, config_versions.get("glossario", ""),
             config_versions.get("prompts", ""),
             f"{config_versions.get('modelo_geracao', '')}|{config_versions.get('modelo_juiz', '')}",
             config_versions.get("limiares", ""), config_versions.get("rubrica", ""), config_versions.get("estilo", "")),
        )
        return str(row[0])

    def persist_extraction(self, document_hash, content, extraction, mapping_key=None, id_prefix="") -> None:
        """Grava a extração de um documento no grafo. No modo triangulado, cada fonte é gravada com o próprio hash
        e as afirmações entram no mapa do dossiê (mapping_key) com o prefixo da fonte ('f1:a3')."""
        from src.extraction.chunker import split_into_chunks
        from src.extraction.extractor import persist_extraction
        from src.extraction.models import ExtractionResult

        result = ExtractionResult.model_validate(extraction)
        store_document_text(document_hash, content)
        nodes = persist_extraction(self.conn, document_hash, content, result, split_into_chunks(content), {})
        bucket = self._assertion_nodes.setdefault(mapping_key or document_hash, {})
        bucket.update({f"{id_prefix}{aid}": node for aid, node in nodes.items()})

    def create_material(self, execution_id, level, fmt) -> str:
        from src.persistence.repositories.material_repository import MaterialRepository

        return MaterialRepository(self.conn).create(execution_id=execution_id, level=level, output_format=fmt, state="gerando")

    def record_attempt(self, material_id, attempt) -> str:
        row = self._exec(
            """INSERT INTO tentativas (id_material, numero_tentativa, conteudo, metricas, falhas, motivo_reprovacao, tokens,
                   latencia, id_modelo, nivel_classificado, feedback_usado, tamanho_texto, versao_prompt, mudanca_vs_anterior)
               VALUES (%s, %s, %s::jsonb, %s::jsonb, %s::jsonb, %s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING id_tentativa""",
            (material_id, attempt["tentativa"], json.dumps(attempt.get("conteudo"), default=str),
             json.dumps(attempt.get("metricas") or {}, default=str), json.dumps(attempt.get("falhas") or [], default=str),
             attempt.get("motivo_reprovacao"), attempt.get("tokens", 0), attempt.get("latencia", 0.0),
             attempt.get("modelo"), attempt.get("nivel_classificado"), attempt.get("feedback_usado"),
             attempt.get("tamanho_texto"), attempt.get("versao_prompt"), attempt.get("mudanca_vs_anterior")),
        )
        return str(row[0])

    def record_judge(self, attempt_id, judge) -> str:
        row = self._exec(
            """INSERT INTO avaliacoes_juiz (id_tentativa, versao_rubrica, id_modelo_juiz, notas, justificativa, tamanho_texto,
                   evidencias, media_ponderada, aprovado, justificativas, tokens, latencia)
               VALUES (%s, %s, %s, %s::jsonb, %s, %s, %s::jsonb, %s, %s, %s::jsonb, %s, %s) RETURNING id_avaliacao_juiz""",
            (attempt_id, judge.get("rubric_version", ""), judge.get("judge_model_id", ""), json.dumps(judge.get("scores") or {}),
             judge.get("justification"), judge.get("text_length"), json.dumps(judge.get("evidence") or []),
             judge.get("media_ponderada"), judge.get("aprovado"), json.dumps(judge.get("criterios") or [], default=str),
             (judge.get("usage") or {}).get("total_tokens", 0), judge.get("latency_seconds", 0.0)),
        )
        return str(row[0])

    def finalize_material(self, material_id, content, status, warning, classified_level, source_complexity,
                          glossary_version, links, document_hash=None) -> None:
        from src.persistence.repositories.graph_repository import GraphRepository

        self._exec(
            """UPDATE materiais SET conteudo_gerado = %s::jsonb, estado = 'aguardando_revisao', status_avaliacao = %s,
                   aviso = %s, nivel_classificado = %s, complexidade_fonte = %s::jsonb, versao_glossario = %s,
                   atualizado_em = NOW() WHERE id_material = %s""",
            (json.dumps(content, default=str), status, warning, classified_level, json.dumps(source_complexity or {}),
             glossary_version, material_id),
        )
        graph = GraphRepository(self.conn)
        material_node = graph.add_node("material", {"id_material": material_id})
        assertion_nodes = self._assertion_nodes.get(document_hash or "", {})
        for link in links:
            sentence_node = graph.add_node("frase_gerada", {"campo": link["campo"], "texto": link["texto"],
                                                            "sobreposicao": link["sobreposicao"]})
            graph.add_edge(material_node, sentence_node, "TEM_FRASE")
            target = assertion_nodes.get(link.get("afirmacao_id") or "")
            if target:
                graph.add_edge(sentence_node, target, "BASEADA_EM")

    def finish_execution(self, execution_id, total_tokens, total_latency, status, accumulate: bool = False) -> None:
        if accumulate:
            self._exec("UPDATE execucoes SET total_tokens = COALESCE(total_tokens, 0) + %s, "
                       "latencia_total = COALESCE(latencia_total, 0) + %s, estado = %s WHERE id_execucao = %s",
                       (total_tokens, total_latency, status, execution_id))
            return
        self._exec("UPDATE execucoes SET total_tokens = %s, latencia_total = %s, estado = %s WHERE id_execucao = %s",
                   (total_tokens, total_latency, status, execution_id))
