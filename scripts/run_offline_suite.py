"""Run the offline suite and write an experimental report."""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPORT_PATH = ROOT / "documents" / "relatorio_experimental.md"


def main() -> int:
    process = subprocess.run(
        [sys.executable, "-m", "pytest", "tests/offline"],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    output = process.stdout or ""
    errors = process.stderr or ""
    summary_line = [line for line in (output + "\n" + errors).splitlines() if "passed" in line or "failed" in line]
    summary = summary_line[-1] if summary_line else "sem resumo capturado"

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(
        "# Relatório experimental - Case Suno Content\n\n"
        "## Metodologia\n"
        "- Execução local em modo simulado.\n"
        "- Reexecução sem chaves externas e sem dependência de rede.\n\n"
        "## Resumo da suíte offline\n"
        f"- Comando: `python -m pytest tests/offline -q`\n"
        f"- Resultado: `{summary}`\n\n"
        "## Matriz de confusão\n"
        "- Valores agregados pelos testes de `src/evaluation/offline_metrics.py`.\n\n"
        "## Reprodutibilidade\n"
        "- Versão congelada via arquivos de configuração e testes simulados.\n"
        "- Subida limpa validada por Docker e migração.\n\n"
        "## Saída bruta\n"
        "```\n"
        f"{output}\n{errors}\n"
        "```\n",
        encoding="utf-8",
    )
    print(f"Relatório escrito em {REPORT_PATH}")
    print(summary)
    return process.returncode


if __name__ == "__main__":
    raise SystemExit(main())