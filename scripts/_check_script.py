"""Gera um roteiro pelo pipeline real e imprime fala escrita e fala falada (usa LLM_MODE do ambiente).

Uso: LLM_MODE=live python scripts/_check_script.py caminho/do/documento.txt [nivel]
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.pipeline.graph import run_pipeline  # noqa: E402

if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    if len(sys.argv) < 2:
        raise SystemExit("Uso: python scripts/_check_script.py documento.txt [nivel]")
    text = Path(sys.argv[1]).read_text(encoding="utf-8")
    level = sys.argv[2] if len(sys.argv) > 2 else "iniciante"
    final = run_pipeline(text, [level])
    output = (final.get("generated_outputs") or {}).get(f"{level}:roteiro_video") or {}
    print("status:", output.get("status"), "| aviso:", output.get("aviso"))
    for scene in (output.get("conteudo") or {}).get("scenes", []):
        print(f"[{scene['start_sec']}-{scene['end_sec']}s] {scene['fala_escrita']}\n    falada: {scene['fala_falada']}")
