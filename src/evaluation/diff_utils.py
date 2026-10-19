"""Utilitários de diff colorido com hover para alterações sugeridas pelo juiz.

Gera HTML com spans coloridos (verde = inserção, vermelho = remoção,
amarelo = substituição) e atributo data-original para hover mostrando
o trecho anterior.
"""
from __future__ import annotations

import difflib
import html
from typing import Any

from pydantic import BaseModel


class DiffChange(BaseModel):
    """Uma alteração detectada entre antes e depois."""
    trecho_antes: str
    trecho_depois: str
    posicao_inicial: int
    tipo: str  # "insercao", "remocao", "substituicao"


def gerar_diff_html(texto_antes: str, texto_depois: str) -> str:
    """Gera HTML com diff colorido por palavra e hover mostrando o antes.

    - Verde: inserções (texto presente em depois mas não em antes)
    - Vermelho: remoções (texto presente em antes mas não em depois)
    - Amarelo: substituições
    - Hover sobre trecho modificado mostra o trecho anterior via title/data-original
    """
    if not texto_antes and not texto_depois:
        return ""

    if not texto_antes:
        # Tudo é inserção
        escaped = html.escape(texto_depois)
        return f'<span class="diff-insercao" title="Inserido">{escaped}</span>'

    if not texto_depois:
        # Tudo é remoção
        escaped = html.escape(texto_antes)
        return f'<span class="diff-remocao" title="Removido">{escaped}</span>'

    # Diferença por palavra usando SequenceMatcher
    palavras_antes = texto_antes.split()
    palavras_depois = texto_depois.split()
    sm = difflib.SequenceMatcher(None, palavras_antes, palavras_depois)

    partes: list[str] = []
    offset_antes = 0
    offset_depois = 0

    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":
            # Texto igual — escapar e adicionar sem destaque
            bloco = " ".join(palavras_depois[j1:j2])
            partes.append(html.escape(bloco))
        elif tag == "insert":
            # Palavras inseridas em depois
            bloco = " ".join(palavras_depois[j1:j2])
            partes.append(
                f'<span class="diff-insercao" title="Inserido: {html.escape(bloco)}">{html.escape(bloco)}</span>'
            )
        elif tag == "delete":
            # Palavras removidas de antes
            bloco = " ".join(palavras_antes[i1:i2])
            partes.append(
                f'<span class="diff-remocao" title="Removido: {html.escape(bloco)}">{html.escape(bloco)}</span>'
            )
        elif tag == "replace":
            # Substituição: mostrar depois em amarelo, com hover mostrando antes
            bloco_depois = " ".join(palavras_depois[j1:j2])
            bloco_antes = " ".join(palavras_antes[i1:i2])
            partes.append(
                f'<span class="diff-substituicao" '
                f'title="Substituído. Antes: {html.escape(bloco_antes)}" '
                f'data-original="{html.escape(bloco_antes)}">{html.escape(bloco_depois)}</span>'
            )
        # Adicionar espaço entre blocos (exceto se for o último)
        if tag != "equal" or i2 < len(palavras_antes):
            # Adicionar espaço apenas se não for o fim do texto
            pass

    return " ".join(partes)


def gerar_lista_alteracoes(
    texto_antes: str, texto_depois: str, patch_sugerido: list[dict[str, Any]] | None = None
) -> list[dict[str, Any]]:
    """Gera lista estruturada de alterações entre antes e depois.

    Se patch_sugerido for fornecido, usa essas sugestões. Caso contrário,
    calcula automaticamente via difflib.
    """
    alteracoes: list[dict[str, Any]] = []

    if patch_sugerido:
        for p in patch_sugerido:
            alteracoes.append(
                {
                    "trecho_antes": p.get("trecho_antes", ""),
                    "trecho_depois": p.get("trecho_depois", ""),
                    "posicao_inicial": p.get("posicao_inicial", 0),
                    "tipo": p.get("tipo", "substituicao"),
                    "diff_html": gerar_diff_html(
                        p.get("trecho_antes", ""), p.get("trecho_depois", "")
                    ),
                }
            )
        return alteracoes

    # Cálculo automático via difflib por palavra
    palavras_antes = texto_antes.split()
    palavras_depois = texto_depois.split()
    sm = difflib.SequenceMatcher(None, palavras_antes, palavras_depois)

    pos_antes = 0
    pos_depois = 0

    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":
            pos_antes = i2
            pos_depois = j2
            continue

        bloco_antes = " ".join(palavras_antes[i1:i2])
        bloco_depois = " ".join(palavras_depois[j1:j2])

        alteracoes.append(
            {
                "trecho_antes": bloco_antes,
                "trecho_depois": bloco_depois,
                "posicao_inicial": pos_antes,
                "tipo": tag,
                "diff_html": gerar_diff_html(bloco_antes, bloco_depois),
            }
        )

        pos_antes = i2
        pos_depois = j2

    return alteracoes


def css_diff() -> str:
    """Retorna CSS para renderizar o diff colorido."""
    return """
    <style>
    .diff-insercao {
        background-color: #d4edda;
        color: #155724;
        padding: 1px 3px;
        border-radius: 3px;
        border: 1px solid #c3e6cb;
    }
    .diff-remocao {
        background-color: #f8d7da;
        color: #721c24;
        padding: 1px 3px;
        border-radius: 3px;
        border: 1px solid #f5c6cb;
        text-decoration: line-through;
    }
    .diff-substituicao {
        background-color: #fff3cd;
        color: #856404;
        padding: 1px 3px;
        border-radius: 3px;
        border: 1px solid #ffeeba;
    }
    .diff-texto-base {
        white-space: pre-wrap;
        font-family: system-ui, -apple-system, sans-serif;
        line-height: 1.6;
    }
    </style>
    """


if __name__ == "__main__":
    # Exemplo de uso
    antes = "O Copom decidiu manter a Selic em 10,50% ao ano."
    depois = "O Copom decidiu manter a Selic em 10,75% ao ano. A inflação está controlada."
    html_diff = gerar_diff_html(antes, depois)
    print(html_diff)
    alteracoes = gerar_lista_alteracoes(antes, depois)
    print(json.dumps(alteracoes, ensure_ascii=False, indent=2))