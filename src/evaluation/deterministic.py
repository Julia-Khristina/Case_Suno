"""Avaliador determinístico por formato (seções 4.6 e 4.7 da especificação).

Cada verificação produz uma `Failure` estruturada (código, métrica, valor, limiar, detalhe). O relatório
vira o feedback numérico injetado na reescrita. Nenhum limiar é escrito aqui: todos vêm de
config/limiares.yaml (via `Thresholds.req`).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from pydantic import BaseModel, Field

from src.evaluation.coverage import uncovered_points, unexplained_terms
from src.evaluation.flesch_ptbr import evaluate_level, flesch_reading_ease_pt
from src.evaluation.format_checks import (
    cta_problems,
    forbidden_terms_found,
    has_emoji,
    recommendation_language,
    script_timing_problems,
)
from src.evaluation.grounding import (
    dates_without_origin,
    general_marker_violations,
    numbers_without_origin,
    undeclared_variations,
    unsupported_sentences,
)
from src.evaluation.level_classifier import classify_scores, density_in_band
from src.evaluation.redundancy import repeated_sentences, sentence_repetition_ratio, trigram_repetition_ratio
from src.evaluation.term_density import technical_density
from src.evaluation.text_utils import jaccard_trigrams, sentences, word_count
from src.evaluation.thresholds import Thresholds, as_thresholds
from src.generation import rules

SECTIONS = ("introduction", "development", "analysis", "conclusion")
SECTION_KEYS = {"introduction": "proporcao_introducao", "development": "proporcao_desenvolvimento",
                "analysis": "proporcao_analise", "conclusion": "proporcao_conclusao"}


class Failure(BaseModel):
    code: str
    metrica: str
    valor: Any = None
    limiar: Any = None
    detalhe: Any = None

    def line(self) -> str:
        parts = [f"- {self.code}: {self.metrica}={_fmt(self.valor)}"]
        if self.limiar is not None:
            parts.append(f"limiar={_fmt(self.limiar)}")
        if self.detalhe:
            parts.append(f"detalhe={_fmt(self.detalhe)}")
        return " | ".join(parts)


def _fmt(value: Any) -> str:
    if isinstance(value, float):
        return f"{value:.2f}"
    if isinstance(value, (list, tuple)):
        shown = [str(v) for v in list(value)[:6]]
        return "[" + "; ".join(shown) + (" …" if len(value) > 6 else "") + "]"
    return str(value)


class DeterministicReport(BaseModel):
    nivel: str
    formato: str
    passed: bool
    failures: list[Failure] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    metrics: dict[str, Any] = Field(default_factory=dict)
    classified_level: str = "indistinto"
    source_complexity: dict[str, Any] = Field(default_factory=dict)

    @property
    def failure_codes(self) -> list[str]:
        return [f.code for f in self.failures]

    def feedback(self) -> str:
        """Relatório numérico de falhas para a próxima tentativa."""
        if not self.failures:
            return ""
        header = (f"Relatório das métricas determinísticas (nível {self.nivel}, formato {self.formato}). "
                  f"Corrija cada item sem acrescentar texto de preenchimento:")
        context = (f"Medidas atuais: palavras={self.metrics.get('palavras')}, flesch={self.metrics.get('flesch', 0):.1f}, "
                   f"densidade_termos={self.metrics.get('densidade_termos', 0):.2f}/100 palavras, "
                   f"nivel_classificado={self.classified_level}.")
        return "\n".join([header, *[f.line() for f in self.failures], context])


@dataclass
class EvaluationContext:
    level: str
    fmt: str
    source_text: str
    glossary: Any
    thresholds: Thresholds
    main_points: list[dict] = field(default_factory=list)       # [{"id", "title", "assertions": [str]}]
    assertions: list[str] = field(default_factory=list)          # textos de todas as afirmações
    declared_variations: list[str] = field(default_factory=list)  # afirmações com variação declarada
    forbidden_terms: list[str] = field(default_factory=list)
    recommendation_patterns: list[str] | None = None
    origin: dict = field(default_factory=dict)
    triangulacao: dict | None = None  # {"matriz", "fontes", "pontos_centrais"} no texto triangulado

    @property
    def triangulated(self) -> bool:
        return bool(self.triangulacao) and self.fmt == "texto_analitico"

    @property
    def approved_impact(self) -> list[str]:
        return self.glossary.approved_impact_explanations()


# ----------------------------------------------------------------------------------- extração de texto


def section_content(value: Any) -> str:
    if isinstance(value, dict):
        return value.get("content", "") or ""
    return getattr(value, "content", value if isinstance(value, str) else "") or ""


def text_for_metrics(content: dict, fmt: str) -> str:
    """Texto usado nas métricas de leitura e fidelidade (sem bloco de fonte nem caixa de termos)."""
    content = content or {}
    if fmt == "texto_analitico":
        return "\n".join([content.get("title", ""), content.get("subtitle", ""),
                          *[section_content(content.get(s)) for s in SECTIONS]])
    if fmt == "carrossel":
        slides = content.get("slides", [])
        caption = content.get("legenda") or {}
        parts = [f"{s.get('title', '')}. {s.get('body', '')}" for s in slides]
        parts += [caption.get("opening", ""), caption.get("short_context", "")]
        return "\n".join(p for p in parts if p)
    if fmt == "roteiro_video":
        return "\n".join(s.get("fala_escrita", "") for s in content.get("scenes", []))
    raise ValueError(f"Formato desconhecido: {fmt}")


def text_for_format_checks(content: dict, fmt: str) -> str:
    """Todo o texto visível (inclui tela, visual, legenda e chamada) para emoji, termos proibidos e números."""
    content = content or {}
    base = text_for_metrics(content, fmt)
    if fmt == "carrossel":
        caption = content.get("legenda") or {}
        extra = [caption.get("cta_sentence", ""), " ".join(s.get("highlight_data") or "" for s in content.get("slides", []))]
        return "\n".join([base, *extra])
    if fmt == "roteiro_video":
        extra = [f"{s.get('texto_na_tela', '')}\n{s.get('visual', '')}" for s in content.get("scenes", [])]
        return "\n".join([base, *extra])
    return base


# ------------------------------------------------------------------------------------------- avaliação


def evaluate(content: dict, ctx: EvaluationContext) -> DeterministicReport:
    t = as_thresholds(ctx.thresholds)
    fails: list[Failure] = []
    warnings: list[str] = []
    text = text_for_metrics(content, ctx.fmt)
    visible = text_for_format_checks(content, ctx.fmt)
    words = word_count(text)
    source_words = word_count(ctx.source_text)

    # --- legibilidade e densidade (faixa do nível)
    flesch = flesch_reading_ease_pt(text)
    density = technical_density(text, ctx.glossary)
    classified = classify_scores(flesch, density, t)
    if not evaluate_level(flesch, ctx.level, t):
        fails.append(Failure(code="legibilidade_fora_da_faixa", metrica="flesch_ptbr", valor=round(flesch, 1),
                             limiar=_flesch_band(ctx.level, t)))
    if not density_in_band(density, ctx.level, t):
        fails.append(Failure(code="densidade_fora_da_faixa", metrica="termos_tecnicos_por_100_palavras",
                             valor=round(density, 2), limiar=_density_band(ctx.level, t)))

    # --- tamanho (mesmo intervalo para os três níveis; ajustado à fonte curta)
    lo, hi = rules.word_range("texto_triangulado" if ctx.triangulated else ctx.fmt, source_words, t)
    if not lo <= words <= hi:
        fails.append(Failure(code="tamanho_fora_do_intervalo", metrica="palavras", valor=words, limiar=f"{lo}..{hi}"))

    # --- fidelidade
    missing_numbers = numbers_without_origin(visible, ctx.source_text)
    missing_dates = dates_without_origin(visible, ctx.source_text)
    if missing_numbers or missing_dates:
        fails.append(Failure(code="numero_ou_data_sem_origem", metrica="numeros_e_datas_fora_da_fonte",
                             valor=len(missing_numbers) + len(missing_dates), limiar=0,
                             detalhe=missing_numbers + missing_dates))
    unsupported, explanations = unsupported_sentences(text, ctx.source_text, ctx.assertions,
                                                      t.req("respaldo_sobreposicao_min"),
                                                      glossary_forms=ctx.glossary.all_forms(),
                                                      matrix_units=_matrix_units(ctx) if ctx.triangulated else (),
                                                      source_names=_source_names(ctx) if ctx.triangulated else ())
    total_sentences = max(1, len(sentences(text)))
    unsupported_share = len(unsupported) / total_sentences
    if unsupported_share > t.req("frases_sem_respaldo_max"):
        fails.append(Failure(code="frases_sem_respaldo_na_fonte", metrica="fracao_frases_sem_respaldo",
                             valor=round(unsupported_share, 2), limiar=t.req("frases_sem_respaldo_max"),
                             detalhe=unsupported))
    if explanations:
        warnings.append(f"{len(explanations)} frase(s) de explicação sem correspondência na fonte: conferir contra o glossário")
    variations = undeclared_variations(text, ctx.source_text, ctx.declared_variations, t.req("respaldo_sobreposicao_min"))
    if variations:
        fails.append(Failure(code="variacao_nao_declarada_pela_fonte", metrica="frases_com_variacao_sem_origem",
                             valor=len(variations), limiar=0, detalhe=variations))
    markers = general_marker_violations(text, ctx.approved_impact)
    if markers:
        fails.append(Failure(code="marcador_em_geral_fora_do_glossario", metrica="frases_em_geral_invalidas",
                             valor=len(markers), limiar=0,
                             detalhe=markers if ctx.approved_impact else ["nenhuma explicação de impacto aprovada no glossário: não use 'Em geral,'"]))

    # --- cobertura dos pontos centrais
    missing_points = uncovered_points(text, ctx.main_points, t.req("cobertura_sobreposicao_min"))
    if missing_points:
        fails.append(Failure(code="cobertura_de_pontos_centrais_insuficiente", metrica="pontos_centrais_cobertos",
                             valor=f"{len(ctx.main_points) - len(missing_points)}/{len(ctx.main_points)}",
                             limiar=f"{len(ctx.main_points)}/{len(ctx.main_points)}", detalhe=missing_points))

    # --- repetição (padding). No carrossel, a abertura da legenda reafirma o gancho por desenho:
    #     a repetição é medida nos slides.
    rep_text = "\n".join(f"{s.get('title', '')}. {s.get('body', '')}" for s in content.get("slides", [])) \
        if ctx.fmt == "carrossel" else text
    if ctx.triangulated:  # a atribuição obrigatória ("segundo a Fonte X") não é repetição de conteúdo
        rep_text = _without_attribution(rep_text, _source_names(ctx))
    rep_s = sentence_repetition_ratio(rep_text)
    rep_t = trigram_repetition_ratio(rep_text)
    if rep_s > t.req("repeticao_frases_max"):
        fails.append(Failure(code="frases_repetidas", metrica="fracao_frases_repetidas", valor=round(rep_s, 3),
                             limiar=t.req("repeticao_frases_max"), detalhe=repeated_sentences(rep_text)))
    if rep_t > t.req("repeticao_trigramas_max"):
        fails.append(Failure(code="trigramas_repetidos", metrica="fracao_trigramas_repetidos", valor=round(rep_t, 3),
                             limiar=t.req("repeticao_trigramas_max")))

    # --- estilo e regras gerais
    if has_emoji(visible):
        fails.append(Failure(code="emoji_encontrado", metrica="emojis", valor="sim", limiar=0))
    forbidden = forbidden_terms_found(visible, ctx.forbidden_terms)
    if forbidden:
        fails.append(Failure(code="termo_proibido_encontrado", metrica="termos_proibidos", valor=len(forbidden),
                             limiar=0, detalhe=forbidden))
    reco = recommendation_language(visible, ctx.recommendation_patterns)
    if reco:
        fails.append(Failure(code="linguagem_de_recomendacao", metrica="expressoes_de_recomendacao", valor=len(reco),
                             limiar=0, detalhe=reco))

    # --- Iniciante: todo termo técnico explicado na janela
    if ctx.level == "iniciante":
        # no texto analítico, título e subtítulo não têm como explicar termos: a janela vale para o corpo
        body = "\n".join(section_content(content.get(s)) for s in SECTIONS) if ctx.fmt == "texto_analitico" else text
        unexplained = unexplained_terms(body, ctx.glossary, t.req("janela_contexto_termo_palavras"))
        if unexplained:
            fails.append(Failure(code="termo_tecnico_sem_explicacao", metrica="termos_sem_explicacao_na_janela",
                                 valor=len(unexplained), limiar=0,
                                 detalhe=[f"{u} (explique em até {t.req('janela_contexto_termo_palavras')} palavras)"
                                          for u in unexplained]))

    # --- verificações do formato
    if ctx.fmt == "texto_analitico":
        fails += _text_checks(content, ctx, t)
        if ctx.triangulated:
            fails += triangulation_checks(content, ctx)
    elif ctx.fmt == "carrossel":
        fails += _carousel_checks(content, ctx, t)
    elif ctx.fmt == "roteiro_video":
        fails += _script_checks(content, ctx, t)

    metrics = {
        "palavras": words, "intervalo_palavras": [lo, hi], "flesch": round(flesch, 2),
        "densidade_termos": round(density, 3), "frases": total_sentences,
        "fracao_frases_sem_respaldo": round(unsupported_share, 3), "repeticao_frases": round(rep_s, 3),
        "repeticao_trigramas": round(rep_t, 3), "numeros_sem_origem": missing_numbers, "datas_sem_origem": missing_dates,
        "pontos_nao_cobertos": missing_points, "razao_saida_fonte": round(words / source_words, 3) if source_words else None,
    }
    complexity = {"palavras": source_words, "flesch": round(flesch_reading_ease_pt(ctx.source_text), 2),
                  "densidade_termos": round(technical_density(ctx.source_text, ctx.glossary), 3)}
    return DeterministicReport(nivel=ctx.level, formato=ctx.fmt, passed=not fails, failures=fails, warnings=warnings,
                               metrics=metrics, classified_level=classified, source_complexity=complexity)


def _flesch_band(level: str, t: Thresholds) -> str:
    return {"iniciante": f">= {t.req('flesch_iniciante_min')}",
            "intermediario": f"{t.req('flesch_intermediario_min')}..{t.req('flesch_intermediario_max')}",
            "avancado": f"<= {t.req('flesch_avancado_max')}"}[level]


def _density_band(level: str, t: Thresholds) -> str:
    return {"iniciante": f"<= {t.req('densidade_iniciante_max')}",
            "intermediario": f"{t.req('densidade_intermediaria_min')}..{t.req('densidade_intermediaria_max')}",
            "avancado": f">= {t.req('densidade_avancado_min')}"}[level]


def _point_ids(ctx: EvaluationContext) -> set[str]:
    return {p["id"] for p in ctx.main_points}


def _text_checks(content: dict, ctx: EvaluationContext, t: Thresholds) -> list[Failure]:
    fails = []
    title, subtitle = content.get("title", ""), content.get("subtitle", "")
    if len(title) > t.req("titulo_max_caracteres"):
        fails.append(Failure(code="titulo_longo", metrica="caracteres_titulo", valor=len(title), limiar=t.req("titulo_max_caracteres")))
    if len(subtitle) > t.req("subtitulo_max_caracteres"):
        fails.append(Failure(code="subtitulo_longo", metrica="caracteres_subtitulo", valor=len(subtitle),
                             limiar=t.req("subtitulo_max_caracteres")))
    # ponto_ids por seção e os três pontos em algum lugar
    declared = set()
    for name in SECTIONS:
        ids = (content.get(name) or {}).get("ponto_ids") or []
        declared.update(ids)
    missing_ids = sorted(_point_ids(ctx) - declared)
    if missing_ids:
        fails.append(Failure(code="ponto_ids_nao_declarados", metrica="pontos_sem_paragrafo", valor=missing_ids, limiar=[]))
    # proporção medida pelo avaliador (não pela contagem declarada pelo gerador)
    counts = {name: word_count(section_content(content.get(name))) for name in SECTIONS}
    total = sum(counts.values()) or 1
    tol = t.req("proporcao_tolerancia")
    off = {name: round(counts[name] / total, 2) for name in SECTIONS
           if abs(counts[name] / total - t.req(SECTION_KEYS[name])) > tol}
    if off:
        fails.append(Failure(code="proporcao_de_secoes_fora_do_padrao", metrica="proporcao_medida", valor=off,
                             limiar=f"15/35/30/20 ± {tol}"))
    max_par = t.req("paragrafo_max_palavras")
    long_pars = [f"{name}: {word_count(p)} palavras" for name in SECTIONS
                 for p in section_content(content.get(name)).split("\n\n") if word_count(p) > max_par]
    if long_pars:
        fails.append(Failure(code="paragrafo_longo", metrica="palavras_por_paragrafo", valor=long_pars, limiar=max_par))
    expected_source = rules.source_block(ctx.origin)
    if content.get("fonte_bloco") != expected_source:
        fails.append(Failure(code="bloco_de_fonte_diferente_da_regra", metrica="fonte_bloco", valor=content.get("fonte_bloco"),
                             limiar=expected_source))
    box = content.get("caixa_entenda_os_termos")
    if ctx.level == "iniciante":
        expected_box = rules.understand_terms_box(text_for_metrics(content, ctx.fmt), ctx.glossary)
        if (box or None) != expected_box:
            fails.append(Failure(code="caixa_entenda_os_termos_diferente_da_regra", metrica="caixa_entenda_os_termos",
                                 valor=bool(box), limiar="montada por regra a partir do glossário aprovado"))
    elif box:
        fails.append(Failure(code="caixa_entenda_os_termos_fora_do_iniciante", metrica="caixa_entenda_os_termos",
                             valor="presente", limiar="só no Iniciante"))
    return fails


def _carousel_checks(content: dict, ctx: EvaluationContext, t: Thresholds) -> list[Failure]:
    fails = []
    slides = content.get("slides", [])
    if len(slides) != t.req("slides_maximos"):
        fails.append(Failure(code="numero_de_slides", metrica="slides", valor=len(slides), limiar=t.req("slides_maximos")))
    long_titles = [s.get("order") for s in slides if len(s.get("title", "")) > t.req("slide_titulo_max_caracteres")]
    long_bodies = [s.get("order") for s in slides if len(s.get("body", "")) > t.req("slide_corpo_max_caracteres")]
    if long_titles:
        fails.append(Failure(code="titulo_de_slide_longo", metrica="slides", valor=long_titles, limiar=t.req("slide_titulo_max_caracteres")))
    if long_bodies:
        fails.append(Failure(code="corpo_de_slide_longo", metrica="slides", valor=long_bodies, limiar=t.req("slide_corpo_max_caracteres")))
    overlaps = []
    for i in range(len(slides)):
        for j in range(i + 1, len(slides)):
            a = f"{slides[i].get('title', '')} {slides[i].get('body', '')}"
            b = f"{slides[j].get('title', '')} {slides[j].get('body', '')}"
            sim = jaccard_trigrams(a, b)
            if sim > t.req("slides_sobreposicao_max"):
                overlaps.append(f"{slides[i].get('order')}-{slides[j].get('order')}: {sim:.2f}")
    if overlaps:
        fails.append(Failure(code="slides_repetidos", metrica="sobreposicao_trigramas_entre_slides", valor=overlaps,
                             limiar=t.req("slides_sobreposicao_max")))
    body_ids = [s.get("ponto_id") for s in slides if s.get("role") == "corpo"]
    expected = _point_ids(ctx)
    if expected and (len(set(body_ids)) != len(body_ids) or not expected.issubset(set(body_ids))):
        fails.append(Failure(code="slides_de_corpo_sem_um_ponto_cada", metrica="ponto_id_por_slide", valor=body_ids,
                             limiar=sorted(expected)))
    expected_line = rules.level_line(ctx.level)
    if content.get("linha_vermelha_nivel") != expected_line:
        fails.append(Failure(code="linha_de_nivel_errada", metrica="linha_vermelha_nivel",
                             valor=content.get("linha_vermelha_nivel"), limiar=expected_line))
    caption = content.get("legenda")
    if not caption:
        fails.append(Failure(code="legenda_ausente", metrica="legenda", valor="ausente", limiar="obrigatória"))
        return fails
    final = caption.get("texto_final") or ""
    if len(final) > t.req("limite_caracteres_legenda_instagram"):
        fails.append(Failure(code="legenda_longa", metrica="caracteres_legenda", valor=len(final),
                             limiar=t.req("limite_caracteres_legenda_instagram")))
    problems = cta_problems(caption.get("cta_verb", ""), caption.get("cta_sentence", ""), t.req("cta_max_caracteres"))
    if problems:
        fails.append(Failure(code="chamada_para_acao_invalida", metrica="regras_da_chamada", valor=len(problems), limiar=0,
                             detalhe=problems))
    if caption.get("source_block") != rules.source_block(ctx.origin):
        fails.append(Failure(code="bloco_de_fonte_diferente_da_regra", metrica="legenda.source_block",
                             valor=caption.get("source_block"), limiar=rules.source_block(ctx.origin)))
    return fails


def _script_checks(content: dict, ctx: EvaluationContext, t: Thresholds) -> list[Failure]:
    from types import SimpleNamespace

    fails = []
    scenes_raw = content.get("scenes", [])
    scenes = [SimpleNamespace(**{k: s.get(k) for k in ("order", "start_sec", "end_sec")}) for s in scenes_raw]
    if len(scenes_raw) != t.req("cenas_maximas"):
        fails.append(Failure(code="numero_de_cenas", metrica="cenas", valor=len(scenes_raw), limiar=t.req("cenas_maximas")))
    timing = script_timing_problems(scenes, t.req("duracao_video_max_segundos")) if scenes else ["sem cenas"]
    if timing:
        fails.append(Failure(code="tempos_do_roteiro_invalidos", metrica="tempos", valor=len(timing), limiar=0, detalhe=timing))
    total = scenes_raw[-1].get("end_sec", 0) if scenes_raw else 0
    if scenes_raw and abs(float(content.get("total_duration_sec", 0)) - float(total)) > 0.5:
        fails.append(Failure(code="duracao_total_inconsistente", metrica="total_duration_sec",
                             valor=content.get("total_duration_sec"), limiar=total))
    rate_max = t.req("palavras_por_segundo_roteiro_max") * (1 + t.req("roteiro_tolerancia_ritmo"))
    fast = []
    for s in scenes_raw:
        dur = max(0.1, float(s.get("end_sec", 0)) - float(s.get("start_sec", 0)))
        rate = word_count(s.get("fala_escrita", "")) / dur
        if rate > rate_max:
            fast.append(f"cena {s.get('order')}: {rate:.1f} palavras/s")
    if fast:
        fails.append(Failure(code="fala_rapida_demais_para_a_duracao", metrica="palavras_por_segundo", valor=fast,
                             limiar=round(rate_max, 2)))
    max_words = t.req("frase_max_palavras_roteiro")
    long_sentences = [s for sc in scenes_raw for s in sentences(sc.get("fala_escrita", "")) if word_count(s) > max_words]
    if long_sentences:
        fails.append(Failure(code="frase_longa_no_roteiro", metrica="palavras_por_frase", valor=len(long_sentences),
                             limiar=max_words, detalhe=long_sentences))
    long_screen = [s.get("order") for s in scenes_raw if len(s.get("texto_na_tela", "")) > t.req("texto_tela_max_caracteres")]
    if long_screen:
        fails.append(Failure(code="texto_na_tela_longo", metrica="cenas", valor=long_screen, limiar=t.req("texto_tela_max_caracteres")))
    body_ids = [s.get("ponto_id") for s in scenes_raw if s.get("role") == "corpo"]
    expected = _point_ids(ctx)
    if expected and (len(set(body_ids)) != len(body_ids) or not expected.issubset(set(body_ids))):
        fails.append(Failure(code="cenas_de_corpo_sem_um_ponto_cada", metrica="ponto_id_por_cena", valor=body_ids,
                             limiar=sorted(expected)))
    wrong_spoken = [s.get("order") for s in scenes_raw
                    if s.get("fala_falada") != rules.spoken_text(s.get("fala_escrita", ""), ctx.glossary)]
    if wrong_spoken:
        fails.append(Failure(code="fala_falada_diferente_da_regra", metrica="cenas", valor=wrong_spoken, limiar="derivada por regra"))
    return fails


# ------------------------------------------------------------------------------------- triangulação




def _strip(text: str) -> str:
    import unicodedata

    return "".join(c for c in unicodedata.normalize("NFKD", text or "") if not unicodedata.combining(c)).lower()


def _verdict_patterns() -> list[str]:
    from pathlib import Path

    import yaml

    path = Path("config/triangulacao.yaml")
    config = yaml.safe_load(path.read_text(encoding="utf-8")) or {} if path.exists() else {}
    return [_strip(p) for p in config.get("padroes_veredito_proibido") or []]


def triangulation_checks(content: dict, ctx: EvaluationContext) -> list[Failure]:
    """Regras do texto triangulado: lado a lado, atribuído, sem veredito (decisão de 17/10/2026)."""
    import re

    tri = ctx.triangulacao or {}
    rows = {r["linha_id"]: r for r in tri.get("matriz", [])}
    names = {f["id"]: f["nome"] for f in tri.get("fontes", [])}
    fails: list[Failure] = []
    sections = {name: content.get(name) or {} for name in SECTIONS}

    cited = {lid for sec in sections.values() for lid in (sec.get("linha_ids") or [])}
    unknown = sorted(cited - set(rows))
    if unknown:
        fails.append(Failure(code="linha_da_matriz_inexistente", metrica="linha_ids", valor=unknown, limiar=sorted(rows)))

    one_sided = []
    for row_id, row in rows.items():
        if row.get("status") not in {"divergencia_numerica", "divergencia_qualitativa"}:
            continue
        if row_id not in cited and row_id not in tri.get("pontos_centrais", []):
            continue
        sides = [names.get(f, f) for f in row.get("fontes_divergentes") or []]
        texts = [section_content(sec) for sec in sections.values() if row_id in (sec.get("linha_ids") or [])]
        joined = _strip(" ".join(texts))
        if len(sides) >= 2 and sum(_strip(s) in joined for s in sides) < 2:
            one_sided.append(f"{row_id} ({row.get('topico')}): nomeie {' e '.join(sides)}")
    if one_sided:
        fails.append(Failure(code="divergencia_sem_os_dois_lados", metrica="divergencias_com_uma_fonte_so",
                             valor=len(one_sided), limiar=0, detalhe=one_sided))

    full = _strip(text_for_metrics(content, ctx.fmt))
    verdicts = [p for p in _verdict_patterns() if p and p in full]
    verdicts += re.findall(r"confirmad[oa]s? por (?:\d+|duas|tres|varias|todas as) fontes", full)
    if verdicts:
        fails.append(Failure(code="veredito_entre_fontes", metrica="expressoes_de_veredito", valor=len(verdicts), limiar=0,
                             detalhe=sorted(set(verdicts))))

    unattributed = []
    for name, sec in sections.items():
        for paragraph in section_content(sec).split("\n\n"):
            if re.search(r"\d", paragraph) and not any(_strip(n) in _strip(paragraph) for n in names.values()):
                unattributed.append(f"{name}: {paragraph[:80]}…")
    if unattributed:
        fails.append(Failure(code="numero_sem_atribuicao_de_fonte", metrica="paragrafos_com_numero_sem_fonte",
                             valor=len(unattributed), limiar=0, detalhe=unattributed))
    return fails


def _source_names(ctx: EvaluationContext) -> list[str]:
    return [f["nome"] for f in (ctx.triangulacao or {}).get("fontes", [])]


_STATUS_PHRASE = {
    "convergencia": "as fontes concordam e confirmam o mesmo dado",
    "divergencia_numerica": "as fontes divergem nas estimativas e informam valores diferentes",
    "divergencia_qualitativa": "as fontes divergem e apresentam posições opostas",
    "sem_contraponto": "só uma fonte trata do ponto",
    "nao_comparavel": "os valores não são comparáveis",
}


def _matrix_units(ctx: EvaluationContext) -> list[str]:
    """Frases-base da matriz: o que cada fonte diz em cada linha e o status calculado pelo sistema."""
    units = []
    for row in (ctx.triangulacao or {}).get("matriz", []):
        cells = row.get("celulas", [])
        names = " e ".join(c.get("fonte_nome", "") for c in cells)
        units.append(f"{row.get('topico', '')}: {names} — {_STATUS_PHRASE.get(row.get('status'), '')}.")
        for cell in cells:
            units.append(f"{cell.get('fonte_nome', '')}: {row.get('topico', '')} — {cell.get('valor_texto', '')}. "
                         f"{cell.get('trecho') or ''}")
    for fonte in (ctx.triangulacao or {}).get("fontes", []):
        units.append(f"{fonte.get('nome')}: {fonte.get('titulo', '')} ({fonte.get('tipo_fonte', '')}).")
    return units


def _without_attribution(text: str, names: list[str]) -> str:
    import re

    for name in sorted(names, key=len, reverse=True):
        text = re.sub(rf"\b(segundo|de acordo com|para|conforme)?\s*(a|o|as|os)?\s*{re.escape(name)}\b", " ", text,
                      flags=re.IGNORECASE)
    return text
