"""Coleta (seção 4.1 + decisão de 17/10/2026): cards de cunho financeiro e geráveis, Atom/RSS com texto completo."""
from __future__ import annotations

from collections import Counter

from src.collection.fetchers import CollectedItem, _parse_atom, _parse_rss, html_to_text
from src.collection.ranker import rank_items
from src.collection.relevance import evaluate_item, select_items
from src.collection.scheduler import run_collection
from tests.fakes import content

ARTICLE = content.SOURCE  # ata sintética: financeira, > 200 palavras, muitos termos do glossário

RSS = f"""<?xml version="1.0"?><rss version="2.0" xmlns:content="http://purl.org/rss/1.0/modules/content/">
<channel><item><title>Copom mantém a Selic em 10,50%</title><link>https://exemplo.com/selic</link>
<pubDate>Fri, 16 Oct 2026 10:00:00 -0300</pubDate><description>&lt;p&gt;Decisão do Copom&lt;/p&gt;</description>
<content:encoded><![CDATA[<p>{ARTICLE}</p><figure>legenda</figure><p>O post Copom mantém apareceu primeiro em Fonte.</p>]]></content:encoded>
</item></channel></rss>"""

ATOM = """<?xml version="1.0" encoding="utf-8"?><feed xmlns="http://www.w3.org/2005/Atom">
<entry><title type="text">BC divulga o IBC-Br</title><updated>2026-10-16T09:00:49-03:00</updated>
<link rel="alternate" href="https://www.bcb.gov.br/detalhenoticia/1/nota" />
<content type="html">&lt;div&gt;&lt;p&gt;O índice cresceu.&lt;/p&gt;&lt;/div&gt;</content></entry></feed>"""


def _item(title, text=ARTICLE, source="Fonte A", description="", priority=4):
    return CollectedItem(titulo=title, nome_fonte=source, tipo_fonte="secundaria", url=f"https://x/{title}",
                         data_publicacao="2026-10-16", descricao=description, prioridade=priority, conteudo=text)


def test_rss_keeps_full_text_without_figures_and_feed_trailer():
    item = _parse_rss(RSS, "Fonte", "secundaria", 4)[0]
    assert item.conteudo.startswith("O Comitê de Política Monetária")
    assert "legenda" not in item.conteudo and "apareceu primeiro" not in item.conteudo
    assert item.data_publicacao == "2026-10-16" and item.descricao == "Decisão do Copom"


def test_atom_feed_from_central_bank_is_parsed():
    item = _parse_atom(ATOM, "Banco Central", "primaria", 1)[0]
    assert item.titulo == "BC divulga o IBC-Br" and item.url.endswith("/nota")
    assert item.conteudo == "O índice cresceu." and item.data_publicacao == "2026-10-16"


def test_html_to_text_preserves_paragraphs():
    assert html_to_text("<p>Um &amp; dois</p><p>Três</p>") == "Um & dois\n\nTrês"


def test_financial_and_generable_item_is_accepted_with_reason():
    selection = evaluate_item(_item("Copom mantém a Selic em 10,50%"))
    assert selection.aceito and selection.financeiro and selection.geravel
    assert "selic" in [t.lower() for t in selection.termos_tema]


def test_non_financial_title_is_discarded():
    assert evaluate_item(_item("Flamengo vence o Palmeiras no Brasileirão")).motivo_exclusao.startswith("tema fora do escopo")
    assert evaluate_item(_item("Pesquisa mostra novo líder na corrida presidencial")).motivo_exclusao == \
        "sem termo financeiro no título ou na descrição"


def test_item_that_would_not_pass_admission_is_discarded():
    short = evaluate_item(_item("Selic fica em 10,50%", text="O Copom manteve a Selic."))
    assert not short.aceito and short.motivo_exclusao.startswith("texto não passa na admissão")
    no_text = evaluate_item(_item("Selic fica em 10,50%", text=None))
    assert no_text.motivo_exclusao.startswith("feed sem texto completo")


def test_ranking_limits_cards_per_source():
    items = [_item(f"Selic e juros {i}", source="Fonte A") for i in range(6)] + \
            [_item(f"Ibovespa e dólar {i}", source="Fonte B") for i in range(6)]
    ranked = rank_items(items, limit=8, max_per_source=3)
    assert Counter(i.nome_fonte for i in ranked) == {"Fonte A": 3, "Fonte B": 3}


def test_collection_returns_only_financial_generable_cards():
    items = [
        _item("Copom mantém a Selic em 10,50%", source="Banco Central", priority=1),
        _item("Ibovespa sobe com dólar em queda", source="Fonte B"),
        _item("Flamengo vence o clássico", source="Fonte B"),
        _item("Inflação: IPCA fica acima da meta", text="Texto curto demais.", source="Fonte C"),
    ]
    result = run_collection(conn=None, fetcher=lambda: (items, []), limit=8)
    titles = [c["titulo"] for c in result["cards"]]
    assert titles[0] == "Copom mantém a Selic em 10,50%"  # fonte primária com prioridade maior
    assert set(titles) == {"Copom mantém a Selic em 10,50%", "Ibovespa sobe com dólar em queda"}
    assert all("texto completo admitido" in c["motivo_entrada"] for c in result["cards"])
    assert len(result["discarded"]) == 2


def test_select_items_reports_reason_for_every_discard():
    accepted, discarded = select_items([_item("Novela das nove estreia")])
    assert not accepted and discarded[0]["motivo"]
