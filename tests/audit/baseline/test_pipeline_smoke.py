"""Verifica que o pipeline compila e o estado inicial funciona."""
from src.pipeline.graph import build_graph
from src.pipeline.state import PipelineState

app = build_graph()

initial_state = PipelineState(
    execution_id="test-1",
    document={
        "content": "O Copom decidiu manter a Selic em 10,50% ao ano. A inflacao esta em 4,5%.",
        "origin": {"instituicao": "Banco Central", "titulo": "Copom"},
    },
    selected_levels=["iniciante"],
    config_versions={},
    thresholds={
        "flesch_iniciante_min": 55,
        "flesch_intermediario_min": 40,
        "flesch_intermediario_max": 55,
        "flesch_avancado_max": 40,
        "densidade_iniciante_max": 3,
        "densidade_intermediaria_min": 3,
        "densidade_intermediaria_max": 8,
        "densidade_avancado_min": 8,
        "tentativas_maximas": 2,
        "tamanho_texto_min_palavras": 350,
        "tamanho_texto_max_palavras": 500,
    },
    glossary_terms=["selic", "copom", "ipca"],
    forbidden_terms=["compre agora", "venda agora"],
)

print("Grafo compilado e estado inicial criado com sucesso")
print(f"Nós: {list(app.nodes.keys())}")
print(f"Níveis: {initial_state.selected_levels}")
