"""Gera um texto analítico pelo pipeline real e imprime as seções (usa LLM_MODE do ambiente).

Antes este script chamava o template de demonstração; agora roda extração, geração, métricas e juiz.
Uso: LLM_MODE=live python scripts/_check_report.py caminho/do/documento.txt [nivel]
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.pipeline.graph import run_pipeline  # noqa: E402

if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    if len(sys.argv) < 2:
        raise SystemExit("Uso: python scripts/_check_report.py documento.txt [nivel]")
    text = Path(sys.argv[1]).read_text(encoding="utf-8")
    level = sys.argv[2] if len(sys.argv) > 2 else "iniciante"
    final = run_pipeline(text, [level])
    output = (final.get("generated_outputs") or {}).get(f"{level}:texto_analitico") or {}
    print("status:", output.get("status"), "| aviso:", output.get("aviso"))
    for section in ("introduction", "development", "analysis", "conclusion"):
        print(f"--- {section}\n{((output.get('conteudo') or {}).get(section) or {}).get('content', '')}")
    print("erros:", json.dumps(final.get("errors"), ensure_ascii=False))
