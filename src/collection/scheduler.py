"""Coleta: leitura dos feeds em intervalos, acervo da janela de horas, pautas e cards do dia.

Fluxo (decisão de 18/10/2026):
1. Lê os feeds ativos; nas fontes com `texto_completo: pagina`, lê a página da matéria quando o feed não traz o
   texto (só para notícias de tema financeiro e se o robots.txt permitir).
2. Avalia cada notícia nova uma vez (tema financeiro + admissão do texto completo) e guarda tudo no acervo.
3. Agrupa as notícias aceitas da janela (72 h) em pautas: mesma notícia em fontes diferentes.
4. Pautas que já têm cards ganham cards para as novas fontes. Pautas novas disputam as vagas do dia
   (`limite_cards_diario_padrao` = pautas por dia): primeiro as comparáveis (2+ fontes independentes).
"""

import sys
import time
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Callable

from zoneinfo import ZoneInfo

from src.collection.acervo import item_row, open_acervo, row_selection, window_start
from src.collection.card_builder import build_card, insert_cards
from src.collection.fetchers import fetch_all_sources, fetch_article_text, load_sources, SourceDefinition
from src.collection.pautas import PautaItem, agency_of, cluster, default_config
from src.collection.ranker import score_card
from src.collection.relevance import entry_reason, evaluate_item, load_selection_config, topic_check
from src.glossary.reader import load_glossary
from src.persistence.repositories.collection_repository import CollectionRepository


BRAZIL_TZ = ZoneInfo("America/Sao_Paulo")


def _load_config() -> dict[str, Any]:
    try:
        import yaml

        with open("config/coleta_fontes.yaml", encoding="utf-8-sig") as file:
            data = yaml.safe_load(file) or {}
        return data
    except Exception:
        return {}


def pauta_config(config: dict | None = None) -> dict:
    config = _load_config() if config is None else config
    return {**default_config(), **(config.get("pautas") or {})}


def _field(item: Any, name: str):
    return item.get(name) if isinstance(item, dict) else getattr(item, name, None)


def _dedupe_by_url(items: list[Any]) -> list[Any]:
    seen, unique = set(), []
    for item in items:
        key = _field(item, "url") or f"{_field(item, 'nome_fonte')}|{_field(item, 'titulo')}"
        if key not in seen:
            seen.add(key)
            unique.append(item)
    return unique


def _set(item: Any, name: str, value) -> None:
    if isinstance(item, dict):
        item[name] = value
    else:
        setattr(item, name, value)


def _fill_page_texts(items: list[Any], sources, page_fetcher, selection_config) -> int:
    """Lê a página das notícias financeiras de fontes `texto_completo: pagina` cujo feed veio sem o texto."""
    page_sources = {s.nome for s in sources or [] if getattr(s, "texto_completo", "feed") == "pagina"}
    read = 0
    for item in items:
        if _field(item, "conteudo") or _field(item, "nome_fonte") not in page_sources:
            continue
        financial, _terms, _excluded = topic_check(item, config=selection_config)
        if not financial:
            continue
        text = page_fetcher(str(_field(item, "url") or ""))
        if text:
            _set(item, "conteudo", text)
            read += 1
    return read


def run_collection(conn=None, fetcher: Callable[[], Any] | None = None, sources=None, limit: int | None = None,
                   now=None, page_fetcher: Callable[[str], str | None] | None = None, acervo=None) -> dict[str, Any]:
    config = _load_config()
    pautas_cfg = pauta_config(config)
    if limit is None:
        limit = int(config.get("limite_cards_diario_padrao", 8))
    if sources is None:
        sources = load_sources()
    now = now or datetime.now(timezone.utc)
    page_fetcher = page_fetcher or fetch_article_text

    if fetcher is not None:
        fetched = fetcher()
        items, errors = fetched if isinstance(fetched, tuple) else (fetched, [])
    else:
        items, errors = fetch_all_sources(sources=sources)
    items = _dedupe_by_url(list(items))

    acervo = acervo if acervo is not None else open_acervo(conn)
    since = window_start(now, int(pautas_cfg["janela_horas"]))
    known = acervo.known_urls(since)
    new_items = [item for item in items if not _field(item, "url") or _field(item, "url") not in known]

    selection_config = load_selection_config()
    pages_read = _fill_page_texts(new_items, sources, page_fetcher, selection_config)
    glossary = load_glossary()
    rows, discarded = [], []
    for item in new_items:
        selection = evaluate_item(item, glossary, selection_config)
        if not selection.aceito:
            discarded.append({"titulo": _field(item, "titulo"), "fonte": _field(item, "nome_fonte"),
                              "motivo": selection.motivo_exclusao})
        content = _field(item, "conteudo") or ""
        credit = "\n".join([str(_field(item, "descricao") or ""), content[:600], content[-600:]])
        rows.append(item_row(item, selection, agency_of(credit), now))
    acervo.add(rows)

    # pautas sobre o acervo da janela (inclui o que acabou de entrar)
    pool = acervo.window(since)
    texts = {row["url"]: acervo.text(row) for row in pool}
    members = [PautaItem.from_item({**row, "conteudo": texts[row["url"]]}, key=row["url"] or str(uuid.uuid4()),
                                   id_pauta=row["id_pauta"], id_card=row["id_card"]) for row in pool]
    pautas = cluster(members, pautas_cfg)

    growing = [p for p in pautas if any(m.id_card for m in p.membros) and any(not m.id_card for m in p.membros)]
    fresh = [p for p in pautas if not any(m.id_card for m in p.membros)]
    day_start = now.astimezone(BRAZIL_TZ).replace(hour=0, minute=0, second=0, microsecond=0)
    remaining = max(0, limit - acervo.pautas_with_cards_since(day_start))
    selected = _choose_pautas(fresh, remaining, selection_config["max_por_fonte"])

    cards, card_ids, pauta_summaries = [], [], []
    for pauta in growing + selected:
        pauta.id_pauta = acervo.save_pauta(pauta.id_pauta, pauta.assunto, pauta.independentes)
        new_cards = []
        for member in sorted(pauta.membros, key=lambda m: m is not pauta.lider):
            if member.id_card:
                continue
            row = member.payload
            existing = acervo.existing_card(row["url"])
            if existing:  # card de coleta anterior para o mesmo link: só entra na pauta, sem duplicar
                acervo.attach_card(existing, pauta.id_pauta)
                acervo.link(row["url"], pauta.id_pauta, existing)
                member.id_card = existing
                continue
            card = build_card({**row, "url": row["url"]})
            card["id_pauta"] = pauta.id_pauta
            reason = entry_reason(row, row_selection(row))
            if len(pauta.membros) > 1:
                reason += (f"; pauta com {len(pauta.membros)} fontes ({pauta.independentes} independentes): "
                           + ", ".join(pauta.fontes))
            card["motivo_entrada"] = reason
            new_cards.append((card, member, row))
        if conn is not None and new_cards:
            ids = insert_cards(conn, [c for c, _m, _r in new_cards])
            for (card, member, row), card_id in zip(new_cards, ids):
                card["id_card"] = card_id
                text = texts.get(row["url"])
                if text:
                    _store_card_document(conn, card, text, row_selection(row))
        for card, member, row in new_cards:
            member.id_card = card["id_card"]
            acervo.link(row["url"], pauta.id_pauta, card["id_card"])
            cards.append(card)
            card_ids.append(card["id_card"])
        pauta_summaries.append({"id_pauta": pauta.id_pauta, "assunto": pauta.assunto, "fontes": pauta.fontes,
                                "independentes": pauta.independentes, "novos_cards": len(new_cards)})

    if conn is not None:
        try:
            CollectionRepository(conn).create(source_name="coleta_diaria", items_count=len(items), errors=errors)
        except Exception:  # noqa: BLE001
            conn.rollback()

    return {
        "started_at": now,
        "items": items,
        "deduped": items,
        "new_items": new_items,
        "pages_read": pages_read,
        "cards": cards,
        "discarded": discarded,
        "errors": errors,
        "card_ids": card_ids if conn is not None else [],  # sem banco os ids não existem fora desta coleta
        "pautas": pauta_summaries,
        "comparable_in_window": sum(1 for p in pautas if p.comparavel),
    }


def _choose_pautas(pautas, slots: int, max_per_source: int | None):
    """Comparáveis primeiro (mais fontes independentes antes), depois pela pontuação do melhor membro.
    O limite por fonte vale para pautas de uma fonte só (diversidade dos cards do dia)."""
    def best_score(pauta):
        return max(score_card(m.payload, len(row_selection(m.payload).termos_tema)) for m in pauta.membros)

    ordered = sorted(pautas, key=lambda p: (not p.comparavel, -p.independentes, -best_score(p), p.lider.prioridade,
                                            p.assunto))
    chosen, per_source = [], {}
    for pauta in ordered:
        if len(chosen) >= slots:
            break
        source = pauta.lider.nome_fonte
        if not pauta.comparavel and max_per_source and per_source.get(source, 0) >= max_per_source:
            continue
        chosen.append(pauta)
        per_source[source] = per_source.get(source, 0) + 1
    return chosen


def _store_card_document(conn, card: dict, text: str, selection) -> None:
    """Guarda o texto completo do feed como documento do card (arquivo por hash + linha em documentos)."""
    import hashlib

    from src.persistence.repositories.document_repository import DocumentRepository
    from src.pipeline.persistence import store_document_text

    admission = selection.admissao or {}
    document_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()
    path = store_document_text(document_hash, text)
    try:
        DocumentRepository(conn).create(
            document_hash=document_hash, origin_type="card", id_card=card["id_card"],
            instituicao_origem=card.get("nome_fonte"), titulo_origem=card.get("titulo"), url_origem=card.get("url_fonte"),
            data_origem=card.get("data_card"), idioma=admission.get("language"),
            status_integridade=admission.get("status", "admitido"), eh_financeiro=admission.get("is_financial"),
            quantidade_palavras=selection.palavras, quantidade_termos_tecnicos=selection.termos_glossario,
            caminho_texto_bruto=str(path),
        )
    except Exception:  # noqa: BLE001  o card continua válido: o clique cai para a leitura do link
        conn.rollback()


def should_run_scheduled(last_run_date, config_time: str = "08:00", now=None) -> bool:
    now = now or datetime.now(BRAZIL_TZ)
    if last_run_date == now.date():
        return False
    return now.strftime("%H:%M") == config_time


def collection_due(last_run_at: datetime | None, now: datetime | None = None, interval_hours: float = 3,
                   start: str = "07:00", end: str = "22:00") -> bool:
    """Coleta em intervalos dentro do horário de funcionamento (ex.: das 07:00 às 22:00, a cada 3 horas)."""
    now = (now or datetime.now(BRAZIL_TZ)).astimezone(BRAZIL_TZ)
    if not start <= now.strftime("%H:%M") <= end:
        return False
    return last_run_at is None or now - last_run_at >= timedelta(hours=interval_hours)


def _print_result(result: dict, saved: bool) -> None:
    print(f"Coleta finalizada: {len(result['new_items'])} notícias novas no acervo, {len(result['cards'])} cards "
          f"criados, {len(result['discarded'])} itens descartados, {result['pages_read']} páginas lidas, "
          f"{len(result['errors'])} erros de fonte. {'Gravados no banco.' if saved else 'Nada gravado.'}")
    print(f"Pautas comparáveis na janela: {result['comparable_in_window']}")
    for pauta in result["pautas"]:
        mark = f"{len(pauta['fontes'])} fontes, {pauta['independentes']} independentes" if len(pauta["fontes"]) > 1 \
            else pauta["fontes"][0]
        print(f"  + {pauta['assunto'][:90]} [{mark}]")
    for error in result["errors"]:
        print(f"  ! {error}")


def _connect():
    try:
        from src.persistence.database import connect

        return connect()
    except Exception as exc:  # noqa: BLE001
        print(f"AVISO: banco indisponível ({type(exc).__name__}); os cards NÃO serão gravados.")
        return None


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    if len(sys.argv) > 1 and sys.argv[1] == "run":
        conn = _connect()
        result = run_collection(conn=conn)
        _print_result(result, conn is not None)
        if conn is not None:
            conn.close()
        return

    config = _load_config()
    interval = float(config.get("intervalo_coleta_horas", 3))
    window = config.get("horario_coleta") or {}
    start, end = str(window.get("inicio", "07:00")), str(window.get("fim", "22:00"))
    print(f"Agendador ativo: a cada {interval:g} h, das {start} às {end} (horário de Brasília). Ctrl+C para parar.")
    last_run_at = None
    while True:
        now = datetime.now(BRAZIL_TZ)
        if collection_due(last_run_at, now, interval, start, end):
            conn = _connect()
            try:
                _print_result(run_collection(conn=conn), conn is not None)
            except Exception as exc:  # noqa: BLE001  uma coleta com erro não derruba o agendador
                print(f"Coleta falhou: {type(exc).__name__}: {exc}")
            finally:
                if conn is not None:
                    conn.close()
            last_run_at = now
        time.sleep(30)


if __name__ == "__main__":
    main()
