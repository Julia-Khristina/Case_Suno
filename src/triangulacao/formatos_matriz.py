"""Geração de carrossel, legenda e roteiro a partir da matriz de triangulação."""
from __future__ import annotations

from typing import Any
from pathlib import Path

from src.triangulacao.models import LinhaMatriz, StatusLinhaMatriz


def _fonte_nomes(fonte_informacoes: list[dict[str, Any]]) -> list[str]:
    return [f.get("nome", "") for f in fonte_informacoes if f.get("nome")]


def _citar_duas_fontes(linha: LinhaMatriz) -> str:
    """Gera uma citação com pelo menos duas fontes para uma linha de divergência."""
    nomes = [c.fonte_nome for c in linha.celulas if c.fonte_nome]
    if len(nomes) >= 2:
        return f"{nomes[0]} e {nomes[1]}"
    return nomes[0] if nomes else "as fontes"


def gerar_carrossel_matriz(
    matriz: list[LinhaMatriz],
    fonte_informacoes: list[dict[str, Any]],
    nivel: str,
) -> dict[str, Any]:
    """Gera carrossel de 5 slides a partir da matriz de triangulação.

    Slides: 1 gancho, 3 corpo (uma linha de divergência/convergência cada),
    1 conclusão. Usa os mesmos 3 pontos centrais da matriz e cita fontes pelo nome.
    """
    nomes_fontes = _fonte_nomes(fonte_informacoes)

    # Seleciona até 3 linhas de divergência para os slides de corpo
    linhas_divergencia = [
        l for l in matriz
        if l.status in ("divergencia_numerica", "divergencia_qualitativa")
    ][:3]

    # Se não houver divergências, usa convergências
    if not linhas_divergencia:
        linhas_divergencia = [
            l for l in matriz if l.status == "convergencia"
        ][:3]

    slides = []

    # Slide 1: gancho
    assunto = matriz[0].topico if matriz else "Assunto"
    slides.append({
        "order": 1,
        "role": "gancho",
        "title": f"{assunto} — {nivel.title()}",
        "body": (
            f"Comparando {len(fonte_informacoes)} fontes sobre {assunto.lower()}. "
            f"{_citar_duas_fontes(linhas_divergencia[0]) if linhas_divergencia else 'as fontes'} apresentam visões diferentes."
        ),
        "highlight_data": None,
    })

    # Slides 2-4: corpo (uma linha cada; preenche com linhas disponíveis ou genérico)
    for i in range(2, 5):
        idx = i - 2
        if idx < len(linhas_divergencia):
            linha = linhas_divergencia[idx]
            corpo_texto = ""
            for c in linha.celulas[:2]:
                corpo_texto += f"{c.fonte_nome}: {c.valor_texto or c.trecho_curto or ''}. "
            slides.append({
                "order": i,
                "role": "corpo",
                "title": linha.topico,
                "body": corpo_texto.strip() or f"Divergência sobre {linha.topico}.",
                "highlight_data": None,
            })
        else:
            slides.append({
                "order": i,
                "role": "corpo",
                "title": f"Contexto {i - 1}",
                "body": (
                    f"As fontes apresentam informações sobre {assunto.lower()}. "
                    f"Consulte o documento original para detalhes completos."
                ),
                "highlight_data": None,
            })

    # Slide 5: conclusão
    slides.append({
        "order": 5,
        "role": "conclusao",
        "title": "Conclusão",
        "body": (
            f"Acompanhe a evolução de {assunto.lower()} nas fontes citadas. "
            f"Sem veredito único — cada fonte apresenta sua leitura dos fatos."
        ),
        "highlight_data": None,
    })

    # Legenda
    cta_verb = "salvar"
    cta_sentence = f"Salve esta comparação de {assunto.lower()} para consultar depois."
    fonte_str = ", ".join(nomes_fontes[:2]) if nomes_fontes else "as fontes"

    caption = {
        "opening": f"O que {nomes_fontes[0] if nomes_fontes else 'as fontes'} dizem sobre {assunto.lower()}?",
        "short_context": f"Comparação de {len(fonte_informacoes)} fontes sobre {assunto.lower()}.",
        "source_block": f"Fonte: {fonte_str}",
        "cta_verb": cta_verb,
        "cta_sentence": cta_sentence,
        "institutional_notice": None,
        "hashtags": [f"#{nomes_fontes[0].lower().replace(' ', '')}" if nomes_fontes else "#economia"],
    }

    return {
        "carousel": {
            "slides": slides,
            "linha_vermelha_nivel": {
                "iniciante": "em cima",
                "intermediario": "duas laterais",
                "avancado": "embaixo",
            }.get(nivel, "em cima"),
        },
        "caption": caption,
    }


def gerar_roteiro_matriz(
    matriz: list[LinhaMatriz],
    fonte_informacoes: list[dict[str, Any]],
    nivel: str,
) -> dict[str, Any]:
    """Gera roteiro de 5 cenas a partir da matriz de triangulação.

    Até 60 segundos, fala escrita e fala falada separadas, enquadramento controlado.
    """
    nomes_fontes = _fonte_nomes(fonte_informacoes)
    linhas_divergencia = [
        l for l in matriz
        if l.status in ("divergencia_numerica", "divergencia_qualitativa")
    ][:3]

    if not linhas_divergencia:
        linhas_divergencia = [
            l for l in matriz if l.status == "convergencia"
        ][:3]

    scenes = []
    timeline = [(0, 10), (10, 22), (22, 34), (34, 46), (46, 55)]

    # Cena 1: gancho
    assunto = matriz[0].topico if matriz else "Assunto"
    scenes.append({
        "order": 1,
        "role": "gancho",
        "start_sec": 0.0,
        "end_sec": 10.0,
        "fala_escrita": (
            f"{nomes_fontes[0] if nomes_fontes else 'As fontes'} apresentam visões diferentes sobre "
            f"{assunto.lower()}."
        ),
        "fala_falada": (
            f"{nomes_fontes[0] if nomes_fontes else 'As fontes'} apresentam visões diferentes sobre "
            f"{assunto.lower()}."
        ),
        "texto_na_tela": f"{assunto} — Comparação",
        "visual": "Gráfico comparativo de fontes",
        "enquadramento": "close",
        "direction_note": None,
    })

    # Cenas 2-4: corpo (uma linha de divergência cada; preenche quando não há divergências suficientes)
    for i in range(2, 5):
        idx = i - 2
        start, end = timeline[i - 1]
        if idx < len(linhas_divergencia):
            linha = linhas_divergencia[idx]
            c1 = linha.celulas[0] if linha.celulas else None
            c2 = linha.celulas[1] if len(linha.celulas) > 1 else None
            fonte1 = c1.fonte_nome if c1 else "fonte 1"
            fonte2 = c2.fonte_nome if c2 else "fonte 2"
            val1 = c1.valor_texto or c1.trecho_curto or "" if c1 else ""
            val2 = c2.valor_texto or c2.trecho_curto or "" if c2 else ""
            topico = linha.topico
        else:
            fonte1 = nomes_fontes[0] if nomes_fontes else "fonte 1"
            fonte2 = nomes_fontes[1] if len(nomes_fontes) > 1 else "fonte 2"
            val1 = val2 = ""
            topico = f"Contexto {i - 1}"

        scenes.append({
            "order": i,
            "role": "corpo",
            "start_sec": float(start),
            "end_sec": float(end),
            "fala_escrita": (
                f"{fonte1} informa {val1}. {fonte2} informa {val2}. Há diferenças entre as fontes."
                if val1 or val2 else
                f"{fonte1} e {fonte2} apresentam informações sobre {topico.lower()}."
            ),
            "fala_falada": (
                f"{fonte1} informa {val1}. {fonte2} informa {val2}. Há diferenças entre as fontes."
                if val1 or val2 else
                f"{fonte1} e {fonte2} apresentam informações sobre {topico.lower()}."
            ),
            "texto_na_tela": f"{fonte1}: {val1} | {fonte2}: {val2}" if (val1 or val2) else topico,
            "visual": f"Comparação {fonte1} x {fonte2}" if (val1 or val2) else f"Visual {topico}",
            "enquadramento": "plano_medio" if i % 2 == 0 else "plano_aberto",
            "direction_note": None,
        })

    # Cena 5: conclusão
    start, end = timeline[4]
    scenes.append({
        "order": 5,
        "role": "conclusao",
        "start_sec": float(start),
        "end_sec": float(end),
        "fala_escrita": (
            "Acompanhe as fontes para entender a evolução dos fatos. Sem veredito único."
        ),
        "fala_falada": (
            "Acompanhe as fontes para entender a evolução dos fatos. Sem veredito único."
        ),
        "texto_na_tela": "Acompanhe as fontes",
        "visual": "Gráficos de fontes",
        "enquadramento": "close",
        "direction_note": None,
    })

    return {
        "scenes": scenes,
        "total_duration_sec": 55.0,
    }


def gerar_legenda_matriz(
    matriz: list[LinhaMatriz],
    fonte_informacoes: list[dict[str, Any]],
) -> dict[str, Any]:
    """Gera legenda do Instagram a partir da matriz de triangulação.

    Até 2.000 caracteres, fonte por regra, verbo da lista, aviso padrão.
    """
    nomes_fontes = _fonte_nomes(fonte_informacoes)
    assunto = matriz[0].topico if matriz else "assunto"

    linhas_divergencia = [
        l for l in matriz
        if l.status in ("divergencia_numerica", "divergencia_qualitativa")
    ]

    cta_verb = "salvar"
    cta_sentence = (
        f"Salve esta comparação de {assunto.lower()} para consultar depois e "
        "entender as diferentes visões das fontes."
    )

    opening = (
        f"{nomes_fontes[0] if nomes_fontes else 'As fontes'} apresentam visões "
        f"diferentes sobre {assunto.lower()}."
    )

    short_context = (
        f"Comparando {len(fonte_informacoes)} fontes, encontramos convergências e "
        f"divergências sobre {assunto.lower()}. {len(linhas_divergencia)} ponto(s) de "
        f"divergência identificada(s)."
    )

    fonte_str = ", ".join(nomes_fontes[:2]) if nomes_fontes else "as fontes"

    caption = {
        "opening": opening,
        "short_context": short_context,
        "source_block": f"Fonte: {fonte_str}",
        "cta_verb": cta_verb,
        "cta_sentence": cta_sentence,
        "institutional_notice": None,
        "hashtags": [
            f"#{nomes_fontes[0].lower().replace(' ', '')}" if nomes_fontes else "#economia",
            "#comparacaodefontes",
        ],
    }

    # Verifica limite de 2.000 caracteres
    total_chars = len(opening + short_context + cta_sentence)
    if total_chars > 2000:
        # Trunca o short_context para caber
        excedente = total_chars - 2000
        short_context = short_context[:-excedente - 3] + "..."
        caption["short_context"] = short_context

    return caption