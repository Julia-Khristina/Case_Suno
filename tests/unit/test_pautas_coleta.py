"""Pautas na coleta (decisão de 18/10/2026): mesma notícia em fontes diferentes, acervo de 72 h, leitura de página,
coleta em intervalos e gráficos por indicador."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from src.collection.acervo import MemoryAcervo
from src.collection.fetchers import CollectedItem, SourceDefinition, article_text
from src.collection.pautas import PautaItem, agency_of, cluster, extract_entities, similarity
from src.collection.scheduler import collection_due, run_collection, BRAZIL_TZ
from src.triangulacao.graficos_matriz import charts_for_single_source, indicator_families
from src.triangulacao.origem_comum import mesmo_identificador
from tests.fakes.content import SOURCE as COPOM
from tests.fakes.triangulacao import F1, F2

NOW = datetime(2026, 10, 18, 15, 0, tzinfo=timezone.utc)


def _item(title, source, text, url=None, description="", date="2026-10-17", kind="secundaria"):
    return CollectedItem(titulo=title, nome_fonte=source, tipo_fonte=kind, url=url or f"https://{source}.test/{title}",
                         data_publicacao=date, descricao=description, prioridade=4, conteudo=text)


MEI_A = _item("Governo lança Prospera MEI com perdão de dívidas", "Money Times", F1,
              description="Programa Prospera MEI prevê perdão de dívidas e teto maior para o MEI")
MEI_B = _item("Prospera MEI piora risco fiscal, dizem economistas", "Seu Dinheiro", F2,
              description="Economistas veem custo maior do Prospera MEI em ano eleitoral")
COPOM_C = _item("Copom mantém a Selic em 10,50% ao ano", "InfoMoney", COPOM,
                description="Comitê de Política Monetária manteve os juros básicos")


def _pi(item, key):
    return PautaItem.from_item(item, key)


# ------------------------------------------------------------------ entidades e semelhança
def test_entities_keep_tickers_acronyms_and_names_but_not_generic_words():
    found = extract_entities("Veja Braskem (BRKM5): FIP Shine consolida controle após OPA", "Ações da Braskem sobem")
    assert {"brkm5", "brkm", "braskem", "fip shine", "opa"} <= set(found)
    assert "veja" not in found and "acoes" not in found


def test_agency_credit_is_detected_only_when_credited():
    assert agency_of("Texto. (Reuters) - O petróleo subiu.") == "reuters"
    assert agency_of("Com informações da Reuters") == "reuters"
    assert agency_of("Estadão Conteúdo") is None or agency_of("Por Estadão Conteúdo") == "estadao conteudo"
    assert agency_of("O analista comentou a alta do dólar.") is None


def test_same_story_from_two_sources_links_and_unrelated_story_does_not():
    a, b, c = _pi(MEI_A, "a"), _pi(MEI_B, "b"), _pi(COPOM_C, "c")
    from src.collection.pautas import Corpus, default_config

    corpus = Corpus.build([a, b, c])
    assert similarity(a, b, corpus) >= default_config()["limiar_similaridade"]
    assert similarity(a, c, corpus) == 0.0


def test_same_source_and_outside_the_window_never_link():
    same_source = _item("Prospera MEI piora risco fiscal", "Money Times", F2)
    late = _item("Prospera MEI piora risco fiscal", "Seu Dinheiro", F2, date="2026-10-25")
    a = _pi(MEI_A, "a")
    assert similarity(a, _pi(same_source, "s")) == 0.0
    assert similarity(a, _pi(late, "l")) == 0.0


def test_cluster_groups_one_item_per_source_and_keeps_others_alone():
    duplicate_source = _item("Prospera MEI: o que muda para o microempreendedor", "Seu Dinheiro", F1, url="https://x/dup")
    pautas = cluster([_pi(MEI_A, "a"), _pi(MEI_B, "b"), _pi(COPOM_C, "c"), _pi(duplicate_source, "d")])
    groups = sorted(sorted(m.key for m in p.membros) for p in pautas)
    assert ["a", "b"] in groups or ["a", "d"] in groups  # uma notícia por fonte na pauta
    assert ["c"] in groups
    assert all(len({m.nome_fonte for m in p.membros}) == len(p.membros) for p in pautas)


def test_wire_copy_in_two_sites_counts_as_one_origin():
    wire_a = _item("Petróleo sobe com tensão no Oriente Médio", "Site A", "(Reuters) - " + F1)
    wire_b = _item("Petróleo sobe com tensão no Oriente Médio", "Site B", "(Reuters) - " + F1)
    pauta = cluster([_pi(wire_a, "a"), _pi(wire_b, "b")])[0]
    assert len(pauta.membros) == 2 and pauta.independentes == 1 and not pauta.comparavel


def test_year_alone_is_not_a_shared_identifier():
    assert not mesmo_identificador("Petróleo a US$ 80 em 2026", "Brasil será 8ª economia em 2026")
    assert mesmo_identificador("Ata da 263ª reunião do Copom", "Copom divulga ata da 263ª reunião")


# ------------------------------------------------------------------ coleta
def test_collection_puts_comparable_pauta_first_and_it_takes_one_daily_slot():
    result = run_collection(conn=None, fetcher=lambda: ([COPOM_C, MEI_A, MEI_B], []), limit=1, now=NOW)
    assert len(result["pautas"]) == 1
    pauta = result["pautas"][0]
    assert sorted(pauta["fontes"]) == ["Money Times", "Seu Dinheiro"] and pauta["independentes"] == 2
    assert len(result["cards"]) == 2 and len({c["id_pauta"] for c in result["cards"]}) == 1
    assert all("pauta com 2 fontes (2 independentes)" in c["motivo_entrada"] for c in result["cards"])


def test_pauta_grows_in_a_later_collection_without_using_a_new_slot():
    acervo = MemoryAcervo()
    first = run_collection(conn=None, fetcher=lambda: ([MEI_A], []), limit=1, now=NOW, acervo=acervo)
    assert len(first["cards"]) == 1
    later = NOW + timedelta(hours=3)
    second = run_collection(conn=None, fetcher=lambda: ([MEI_A, MEI_B], []), limit=1, now=later, acervo=acervo)
    assert [c["nome_fonte"] for c in second["cards"]] == ["Seu Dinheiro"]  # só a fonte nova vira card
    assert second["cards"][0]["id_pauta"] == first["cards"][0]["id_pauta"]
    assert len(second["new_items"]) == 1  # o que já estava no acervo não é reavaliado


def test_card_from_an_earlier_collection_joins_the_pauta_instead_of_being_duplicated():
    class Acervo(MemoryAcervo):
        attached = []

        def existing_card(self, url):
            return "card-antigo" if url == MEI_A.url else None

        def attach_card(self, id_card, id_pauta):
            self.attached.append((id_card, id_pauta))

    acervo = Acervo()
    result = run_collection(conn=None, fetcher=lambda: ([MEI_A, MEI_B], []), limit=1, now=NOW, acervo=acervo)
    assert [c["nome_fonte"] for c in result["cards"]] == ["Seu Dinheiro"]
    assert acervo.attached == [("card-antigo", result["cards"][0]["id_pauta"])]


def test_page_is_read_only_for_financial_items_of_page_sources():
    calls = []
    source = SourceDefinition("Agência", "secundaria", 5, url="https://feed", texto_completo="pagina")
    financial = _item("Copom mantém a Selic em 10,50%", "Agência", None, url="https://ag/selic")
    other = _item("Festival de cinema começa hoje", "Agência", None, url="https://ag/cinema")

    def page(url):
        calls.append(url)
        return COPOM

    result = run_collection(conn=None, fetcher=lambda: ([financial, other], []), sources=[source], now=NOW,
                            page_fetcher=page)
    assert calls == ["https://ag/selic"] and result["pages_read"] == 1
    assert [c["titulo"] for c in result["cards"]] == ["Copom mantém a Selic em 10,50%"]


def test_article_text_prefers_json_ld_body_and_drops_short_paragraphs():
    body = " ".join(["palavra"] * 90)
    page = f'<script type="application/ld+json">{{"@type":"NewsArticle","articleBody":"{body}"}}</script><p>menu</p>'
    assert article_text(page) == body
    page = "<p>Menu</p><p>" + "texto da matéria " * 5 + "</p><p>Compartilhe</p>"
    assert article_text(page) == ("texto da matéria " * 5).strip()


def test_collection_runs_in_intervals_inside_working_hours():
    at = lambda h: datetime(2026, 10, 18, h, 0, tzinfo=BRAZIL_TZ)  # noqa: E731
    assert collection_due(None, at(7))
    assert not collection_due(None, at(23))
    assert not collection_due(at(9), at(11), interval_hours=3)
    assert collection_due(at(9), at(12), interval_hours=3)


# ------------------------------------------------------------------ interface
def test_cards_of_the_same_pauta_are_grouped_with_primary_source_first():
    from src.app.components.news_cards import group_cards

    cards = [{"id_card": "1", "id_pauta": "p", "tipo_fonte": "secundaria"}, {"id_card": "2"},
             {"id_card": "3", "id_pauta": "p", "tipo_fonte": "primaria"}]
    groups = group_cards(cards)
    assert [[c["id_card"] for c in g] for g in groups] == [["3", "1"], ["2"]]


def test_read_transaction_is_closed_at_the_end_of_each_run():
    from psycopg.pq import TransactionStatus

    from src.app.db import end_read_transaction

    class Conn:
        closed, broken, rolled = False, False, 0

        class info:
            transaction_status = TransactionStatus.INTRANS

        def rollback(self):
            self.rolled += 1

    conn = Conn()
    end_read_transaction(conn)
    assert conn.rolled == 1
    Conn.info.transaction_status = TransactionStatus.IDLE
    end_read_transaction(conn)
    assert conn.rolled == 1


# ------------------------------------------------------------------ gráficos de fonte única
def _numbers(*rows):
    return {"numeric_data": [{"id": f"n{i}", "indicator": ind, "value": val, "unit": unit, "reference_period": per,
                              "source_span": {"text": val}} for i, (ind, val, unit, per) in enumerate(rows)]}


def test_different_indicators_in_the_same_unit_are_not_plotted_together(tmp_path):
    data = _numbers(("Perdão de dívidas com a União", "R$ 12 bilhões", "", ""),
                    ("Reajuste do Bolsa Família", "R$ 22,7 bilhões", "", ""))
    assert indicator_families(data) == []
    assert charts_for_single_source(data, tmp_path) == []


def test_same_indicator_in_several_periods_becomes_a_timeline(tmp_path):
    data = _numbers(("Renúncia com o teto do MEI", "R$ 2,5 bilhões", "", "2027"),
                    ("Renúncia com o teto do MEI", "R$ 2,7 bilhões", "", "2028"),
                    ("Renúncia de receita do teto do MEI", "R$ 2,9 bilhões", "", "2029"),
                    ("Reajuste do Bolsa Família", "R$ 22,7 bilhões", "", "2027"))
    charts = charts_for_single_source(data, tmp_path)
    assert len(charts) == 1 and charts[0]["tipo"] == "serie_temporal"
    assert [d["periodo"] for d in charts[0]["dados"]] == ["2027", "2028", "2029"]
    assert "Bolsa Família" not in charts[0]["texto_alternativo"]
