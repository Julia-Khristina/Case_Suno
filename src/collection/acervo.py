"""Acervo da coleta: tudo o que foi lido nos feeds na janela de horas, avaliado uma vez só (decisão de 18/10/2026).

Cada feed mostra só as notícias mais recentes; guardar tudo o que foi lido, não só os cards escolhidos, é o que
permite achar a mesma notícia em fontes diferentes publicadas com horas de diferença. O texto completo fica no
volume de documentos, pelo hash; a linha guarda o resultado da seleção para não reavaliar a cada coleta.
"""
from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import asdict
from datetime import date, datetime, timedelta, timezone
from typing import Any

from src.collection.relevance import Selection

COLUMNS = ("url", "titulo", "descricao", "nome_fonte", "tipo_fonte", "prioridade", "data_publicacao", "hash_texto",
           "agencia", "aceito", "motivo_exclusao", "selecao", "id_pauta", "id_card", "coletado_em")


def _field(item: Any, name: str):
    return item.get(name) if isinstance(item, dict) else getattr(item, name, None)


def _date(value) -> date | None:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value)[:10])
    except (TypeError, ValueError):
        return None


def item_row(item: Any, selection: Selection, agencia: str | None, now: datetime) -> dict:
    """Linha do acervo para um item lido no feed. O texto completo (só dos aceitos) segue em `_texto` até o
    acervo guardá-lo: no volume de documentos (banco) ou em memória (coleta sem banco)."""
    text = (_field(item, "conteudo") or "") if selection.aceito else ""
    text_hash = hashlib.sha256(text.encode("utf-8")).hexdigest() if text else None
    return {"_texto": text or None, "url": str(_field(item, "url") or ""), "titulo": str(_field(item, "titulo") or ""),
            "descricao": _field(item, "descricao"), "nome_fonte": str(_field(item, "nome_fonte") or "fonte"),
            "tipo_fonte": _field(item, "tipo_fonte") or "secundaria", "prioridade": int(_field(item, "prioridade") or 99),
            "data_publicacao": _date(_field(item, "data_publicacao")), "hash_texto": text_hash, "agencia": agencia,
            "aceito": selection.aceito, "motivo_exclusao": selection.motivo_exclusao, "selecao": asdict(selection),
            "id_pauta": None, "id_card": None, "coletado_em": now}


def row_selection(row: dict) -> Selection:
    data = row.get("selecao") or {}
    if isinstance(data, str):
        data = json.loads(data)
    return Selection(**{k: v for k, v in data.items() if k in Selection.__dataclass_fields__})


class MemoryAcervo:
    """Acervo sem banco (coleta sem conexão e testes): vale só para esta coleta."""

    def __init__(self):
        self.rows: dict[str, dict] = {}
        self.pautas: dict[str, dict] = {}
        self.texts: dict[str, str] = {}

    def known_urls(self, since: datetime) -> set[str]:
        return {url for url, row in self.rows.items() if row["coletado_em"] >= since}

    def add(self, rows: list[dict]) -> None:
        for row in rows:
            text = row.pop("_texto", None)
            if text and row["hash_texto"]:
                self.texts[row["hash_texto"]] = text
            self.rows.setdefault(row["url"] or str(uuid.uuid4()), row)

    def text(self, row: dict) -> str | None:
        return self.texts.get(row.get("hash_texto") or "")

    def window(self, since: datetime) -> list[dict]:
        return [row for row in self.rows.values() if row["aceito"] and row["coletado_em"] >= since]

    def save_pauta(self, id_pauta: str | None, assunto: str, independentes: int) -> str:
        id_pauta = id_pauta or str(uuid.uuid4())
        self.pautas[id_pauta] = {"assunto": assunto, "fontes_independentes": independentes,
                                 "criado_em": self.pautas.get(id_pauta, {}).get("criado_em", datetime.now(timezone.utc))}
        return id_pauta

    def link(self, url: str, id_pauta: str | None, id_card: str | None) -> None:
        row = self.rows.get(url)
        if row is not None:
            row["id_pauta"] = id_pauta or row["id_pauta"]
            row["id_card"] = id_card or row["id_card"]

    def existing_card(self, url: str) -> str | None:
        return None

    def pautas_with_cards_since(self, since: datetime) -> int:
        ids = {row["id_pauta"] for row in self.rows.values() if row["id_card"] and row["id_pauta"]}
        return sum(1 for i in ids if self.pautas.get(i, {}).get("criado_em", since) >= since)


class PostgresAcervo:
    def __init__(self, conn):
        self.conn = conn

    def _rows(self, sql: str, params: tuple) -> list[dict]:
        with self.conn.cursor() as cur:
            cur.execute(sql, params)
            columns = [d[0] for d in cur.description]
            return [dict(zip(columns, row)) for row in cur.fetchall()]

    def known_urls(self, since: datetime) -> set[str]:
        return {r["url"] for r in self._rows("SELECT url FROM itens_coletados WHERE coletado_em >= %s", (since,))}

    def add(self, rows: list[dict]) -> None:
        sql = (f"INSERT INTO itens_coletados ({', '.join(COLUMNS)}) VALUES ({', '.join(['%s'] * len(COLUMNS))}) "
               "ON CONFLICT (url) DO UPDATE SET coletado_em = EXCLUDED.coletado_em, aceito = EXCLUDED.aceito, "
               "motivo_exclusao = EXCLUDED.motivo_exclusao, selecao = EXCLUDED.selecao, "
               "hash_texto = COALESCE(EXCLUDED.hash_texto, itens_coletados.hash_texto), agencia = EXCLUDED.agencia")
        from src.pipeline.persistence import store_document_text

        with self.conn.cursor() as cur:
            for row in rows:
                text = row.pop("_texto", None)
                if text and row["hash_texto"]:
                    store_document_text(row["hash_texto"], text)
                if not row["url"]:
                    continue
                values = [json.dumps(row[c], ensure_ascii=False, default=str) if c == "selecao" else row[c]
                          for c in COLUMNS]
                cur.execute(sql, values)
        self.conn.commit()

    def window(self, since: datetime) -> list[dict]:
        rows = self._rows(f"SELECT {', '.join(COLUMNS)} FROM itens_coletados WHERE aceito AND coletado_em >= %s "
                          "ORDER BY coletado_em", (since,))
        for row in rows:
            row["id_pauta"] = str(row["id_pauta"]) if row["id_pauta"] else None
            row["id_card"] = str(row["id_card"]) if row["id_card"] else None
        return rows

    def text(self, row: dict) -> str | None:
        from src.pipeline.persistence import load_document_text

        return load_document_text(row["hash_texto"]) if row.get("hash_texto") else None

    def save_pauta(self, id_pauta: str | None, assunto: str, independentes: int) -> str:
        with self.conn.cursor() as cur:
            if id_pauta:
                cur.execute("UPDATE pautas SET fontes_independentes = %s, atualizado_em = NOW() WHERE id_pauta = %s",
                            (independentes, id_pauta))
            else:
                cur.execute("INSERT INTO pautas (assunto, fontes_independentes) VALUES (%s, %s) RETURNING id_pauta",
                            (assunto, independentes))
                id_pauta = str(cur.fetchone()[0])
        self.conn.commit()
        return id_pauta

    def link(self, url: str, id_pauta: str | None, id_card: str | None) -> None:
        with self.conn.cursor() as cur:
            cur.execute("UPDATE itens_coletados SET id_pauta = COALESCE(%s, id_pauta), id_card = COALESCE(%s, id_card) "
                        "WHERE url = %s", (id_pauta, id_card, url))
        self.conn.commit()

    def existing_card(self, url: str) -> str | None:
        """Card já criado para o mesmo link na última semana (ex.: por uma coleta anterior ao acervo)."""
        if not url:
            return None
        rows = self._rows("SELECT id_card FROM cards WHERE url_fonte = %s AND data_card >= CURRENT_DATE - 7 "
                          "ORDER BY criado_em LIMIT 1", (url,))
        return str(rows[0]["id_card"]) if rows else None

    def attach_card(self, id_card: str, id_pauta: str) -> None:
        with self.conn.cursor() as cur:
            cur.execute("UPDATE cards SET id_pauta = %s WHERE id_card = %s", (id_pauta, id_card))
        self.conn.commit()

    def pautas_with_cards_since(self, since: datetime) -> int:
        rows = self._rows("SELECT COUNT(DISTINCT c.id_pauta) AS n FROM cards c JOIN pautas p ON p.id_pauta = c.id_pauta "
                          "WHERE p.criado_em >= %s", (since,))
        return int(rows[0]["n"]) if rows else 0


def open_acervo(conn):
    return PostgresAcervo(conn) if conn is not None else MemoryAcervo()


def window_start(now: datetime, hours: int) -> datetime:
    return now - timedelta(hours=hours)
