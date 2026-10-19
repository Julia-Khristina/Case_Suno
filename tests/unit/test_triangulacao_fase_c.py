"""Testes da Fase C - Produto da triangulação de fontes."""
from __future__ import annotations

from unittest.mock import patch
from pathlib import Path
import json
import tempfile
import zipfile

import pytest

from src.triangulacao.models import (
    LinhaMatriz, CelulaMatriz, StatusLinhaMatriz,
    PosicaoClassificada, PosicaoQualitativa,
    DadoNumericoNormalizado, ComparacaoNumerica,
    Triangulacao,
)
from src.triangulacao.export import (
    exportar_html_autocontido,
    exportar_markdown,
    exportar_zip_graficos,
    exportar_todos_niveis,
    estimar_tokens,
    _imagem_para_base64,
    _hash_contexto,
)


# ============================================================================
# Hash de contexto
# ============================================================================

def test_hash_contexto_estavel():
    """Hash do contexto é estável para mesmos dados."""
    versoes = {"glossario": "1.0", "prompt": "2.0", "modelo": "llama-3.3"}
    h1 = _hash_contexto(versoes)
    h2 = _hash_contexto(versoes)
    assert h1 == h2
    assert len(h1) == 16


def test_hash_contexto_diferente_para_dados_diferentes():
    """Dados diferentes geram hashes diferentes."""
    h1 = _hash_contexto({"a": "1"})
    h2 = _hash_contexto({"a": "2"})
    assert h1 != h2


# ============================================================================
# Exportação HTML autocontido
# ============================================================================

def test_exportar_html_autocontido(tmp_path):
    """Gera HTML autocontido com CSS inline, dados e hash."""
    dados = {
        "fontes": [
            {"nome": "BCB", "tipo_fonte": "primaria", "data": "2026-10-01", "url": "https://bcb.gov.br", "origem_comum_id": None},
            {"nome": "Valor", "tipo_fonte": "secundaria", "data": "2026-10-01", "url": "https://valor.com.br", "origem_comum_id": None},
        ],
        "matriz": [
            {
                "linha_id": "div_1",
                "topico": "Selic",
                "status": "divergencia_numerica",
                "celulas": [
                    {"fonte_nome": "BCB"},
                    {"fonte_nome": "Valor"},
                ],
            },
        ],
        "texto": {
            "title": "Teste de Triangulação",
            "subtitle": "Subtítulo",
            "introduction": "Introdução sobre o assunto.",
            "development": "Desenvolvimento com dados.",
            "analysis": "Análise das divergências.",
            "conclusion": "Conclusão sem veredito.",
        },
        "graficos": [],
        "hash_contexto_execucao": "abc123",
    }

    resultado = exportar_html_autocontido("tri_001", "iniciante", dados, tmp_path)

    assert resultado["tipo"] == "html_autocontido"
    assert resultado["nivel"] == "iniciante"
    assert resultado["arquivo"].endswith(".html")

    conteudo = Path(resultado["arquivo"]).read_text(encoding="utf-8")
    assert "Teste de Triangulação" in conteudo
    assert "BCB" in conteudo
    assert "Valor" in conteudo
    assert "abc123" in conteudo
    assert "<style>" in conteudo  # CSS inline
    assert "base64" not in conteudo or "data:image" not in conteudo  # sem gráficos, sem base64


def test_exportar_html_com_graficos_base64(tmp_path):
    """HTML inclui gráficos em base64 quando há gráficos."""
    # Cria um PNG fake
    caminho_png = tmp_path / "grafico_teste.png"
    caminho_png.write_bytes(b"fake_png_data")

    dados = {
        "fontes": [
            {"nome": "BCB", "tipo_fonte": "primaria", "data": "2026-10-01"},
            {"nome": "Valor", "tipo_fonte": "secundaria", "data": "2026-10-01"},
        ],
        "matriz": [],
        "texto": {
            "title": "T", "subtitle": "S",
            "introduction": "I", "development": "D",
            "analysis": "A", "conclusion": "C",
        },
        "graficos": [
            {
                "arquivo": str(caminho_png),
                "texto_alternativo": "Gráfico de barras: Selic em atual.",
                "tipo": "barras_agrupadas",
                "indicador": "Selic",
                "periodo": "atual",
            },
        ],
        "hash_contexto_execucao": "xyz789",
    }

    resultado = exportar_html_autocontido("tri_002", "avancado", dados, tmp_path)

    conteudo = Path(resultado["arquivo"]).read_text(encoding="utf-8")
    assert "data:image/png;base64" in conteudo
    assert "Gráfico de barras: Selic em atual." in conteudo
    assert "xyz789" in conteudo


# ============================================================================
# Exportação Markdown
# ============================================================================

def test_exportar_markdown(tmp_path):
    """Gera Markdown com referências a PNGs."""
    # Cria um PNG fake
    caminho_png = tmp_path / "grafico.png"
    caminho_png.write_bytes(b"fake_png")

    dados = {
        "fontes": [
            {"nome": "BCB", "tipo_fonte": "primaria", "data": "2026-10-01"},
        ],
        "matriz": [
            {
                "linha_id": "l1",
                "topico": "Selic",
                "status": "convergencia",
                "celulas": [{"fonte_nome": "BCB"}],
            },
        ],
        "texto": {
            "title": "Relatório MD",
            "subtitle": "Sub",
            "introduction": "Intro",
            "development": "Dev",
            "analysis": "Analysis",
            "conclusion": "Conclusion",
        },
        "graficos": [
            {
                "arquivo": str(caminho_png),
                "texto_alternativo": "Gráfico de Selic",
                "tipo": "barras_agrupadas",
            },
        ],
        "hash_contexto_execucao": "md_hash",
    }

    resultado = exportar_markdown("tri_003", "intermediario", dados, tmp_path)

    assert resultado["tipo"] == "markdown"
    assert resultado["arquivo"].endswith(".md")

    conteudo = Path(resultado["arquivo"]).read_text(encoding="utf-8")
    assert "# Relatório MD — Intermediario" in conteudo
    assert "md_hash" in conteudo
    assert "Gráfico de Selic" in conteudo
    # O PNG deve ter sido copiado para a pasta de saída
    png_copiado = tmp_path / "grafico.png"
    assert png_copiado.exists()


# ============================================================================
# Exportação ZIP de gráficos
# ============================================================================

def test_exportar_zip_graficos(tmp_path):
    """Cria ZIP com PNGs e JSONs de dados."""
    # Cria PNG e JSON fake
    caminho_png = tmp_path / "grafico_1.png"
    caminho_png.write_bytes(b"png_data")
    caminho_json = tmp_path / "grafico_1.json"
    caminho_json.write_text(json.dumps({"valor": 10.5}), encoding="utf-8")

    graficos = [
        {"arquivo": str(caminho_png), "texto_alternativo": "Grafico 1"},
    ]

    resultado = exportar_zip_graficos("tri_004", graficos, tmp_path)

    assert resultado["tipo"] == "zip_graficos"
    assert resultado["n_graficos"] == 1
    assert resultado["arquivo"].endswith(".zip")

    # Verifica conteúdo do ZIP
    with zipfile.ZipFile(resultado["arquivo"]) as zf:
        nomes = zf.namelist()
        assert "grafico_1.png" in nomes
        assert "grafico_1.json" in nomes


# ============================================================================
# Exportação todos os níveis
# ============================================================================

def test_exportar_todos_niveis(tmp_path):
    """Exporta relatórios para múltiplos níveis."""
    pasta_base = tmp_path / "saida"

    dados_niveis = {
        "iniciante": {
            "fontes": [{"nome": "BCB", "tipo_fonte": "primaria"}],
            "matriz": [],
            "texto": {
                "title": "T", "subtitle": "S",
                "introduction": "I", "development": "D",
                "analysis": "A", "conclusion": "C",
            },
            "graficos": [],
            "hash_contexto_execucao": "h1",
        },
        "avancado": {
            "fontes": [{"nome": "BCB", "tipo_fonte": "primaria"}],
            "matriz": [],
            "texto": {
                "title": "T2", "subtitle": "S2",
                "introduction": "I2", "development": "D2",
                "analysis": "A2", "conclusion": "C2",
            },
            "graficos": [],
            "hash_contexto_execucao": "h2",
        },
    }

    resultado = exportar_todos_niveis("tri_multi", dados_niveis, pasta_base)

    assert resultado["triangulacao_id"] == "tri_multi"
    assert "iniciante" in resultado["niveis"]
    assert "avancado" in resultado["niveis"]
    assert len(resultado["arquivos"]) == 4  # 2 níveis × 2 exportações (HTML + MD)

    # Verifica que os arquivos existem
    for arq in resultado["arquivos"]:
        assert Path(arq["arquivo"]).exists()


# ============================================================================
# Estimativa de tokens
# ============================================================================

def test_estimar_tokens_referencia():
    """Estimativa para 3 fontes e 3 níveis deve estar próxima de 85 mil."""
    estimativa = estimar_tokens(n_fontes=3, n_niveis=3)
    assert estimativa["n_fontes"] == 3
    assert estimativa["n_niveis"] == 3
    assert estimativa["total_estimado"] > 0
    assert estimativa["referencia"] == "85 mil tokens para 3 fontes e 3 níveis (suposição a medir)"


def test_estimar_tokens_dentro_cota():
    """Verifica se a estimativa está dentro da cota diária gratuita."""
    estimativa = estimar_tokens(n_fontes=3, n_niveis=3)
    assert estimativa["dentro_cota_dia"] is True  # <= 200.000


def test_estimar_tokens_mais_fontes():
    """Mais fontes = mais tokens."""
    est_2 = estimar_tokens(n_fontes=2, n_niveis=2)
    est_5 = estimar_tokens(n_fontes=5, n_niveis=3)
    assert est_5["total_estimado"] > est_2["total_estimado"]


# ============================================================================
# Modelo Triangulacao completo
# ============================================================================

def test_modelo_triangulacao_completo():
    """Cria um objeto Triangulacao completo."""
    t = Triangulacao(
        triangulacao_id="t1",
        assunto="Teste de Triangulação",
        fontes=[
            {"id": "f1", "nome": "BCB", "tipo_fonte": "primaria"},
            {"id": "f2", "nome": "Valor", "tipo_fonte": "secundaria"},
        ],
        origem_comum_grupos=[],
        matriz=[],
        comparacoes_numericas=[],
        classificacoes_qualitativas=[],
        graficos=[],
        pontos_centrais=["pc1", "pc2", "pc3"],
        revisoes_humanas=[],
        hash_contexto_execucao="abc",
        total_fontes_independentes=2,
        permite_triangulacao=True,
    )
    assert t.triangulacao_id == "t1"
    assert t.permite_triangulacao is True
    assert t.total_fontes_independentes == 2
    assert len(t.fontes) == 2
    assert t.criado_em is not None