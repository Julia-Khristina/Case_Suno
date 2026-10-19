# -*- coding: utf-8 -*-
"""RETRATO DO ESTADO ANTERIOR À CORREÇÃO (17/10/2026): reproduz os defeitos encontrados na auditoria.
Auditoria: coleta as saídas reais dos geradores que rodam sem LLM.

Executa, para uma árvore de código (--root), a função que a interface usa hoje:
- HEAD (commit ff8cf41): src.app.level_selection._generate_manual_materials
- árvore de trabalho:    src.app.level_selection._generate_manual_materials_demo

Não grava em banco: connect() e os repositórios são substituídos por falsos em memória.
Uso: python tests/audit/audit_collect_outputs.py --root <dir> --label head|wt --out <json>
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

HERE = Path(__file__).resolve().parent


def _load_docs() -> dict[str, str]:
    spec = importlib.util.spec_from_file_location("audit_docs", HERE / "baseline" / "documents.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    curto = mod.DOC_CURTO.strip()
    card = ". ".join(curto.split(". ")[:2]) + "."  # ~descrição de card (o que o clique no card envia)
    return {"card": card, "curto": curto, "medio": mod.DOC_MEDIO.strip(), "longo": mod.DOC_LONGO.strip()}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", required=True)
    ap.add_argument("--label", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    os.environ["LLM_MODE"] = "simulated"
    os.chdir(args.root)
    sys.path.insert(0, args.root)
    docs = _load_docs()

    captured: list[dict] = []

    class FakeMaterialRepo:
        def __init__(self, *_a, **_k):
            pass

        def create(self, execution_id=None, level=None, output_format=None, state=None, generated_content=None):
            captured.append({"nivel": level, "formato": output_format, "conteudo": generated_content})
            return f"m{len(captured)}"

    import src.app.level_selection as ls  # noqa: E402  (importa da árvore --root)

    results = {}
    for doc_name, text in docs.items():
        captured.clear()
        with patch.object(ls, "connect", lambda: MagicMock()), \
             patch("src.persistence.repositories.material_repository.MaterialRepository", FakeMaterialRepo), \
             patch("src.persistence.repositories.document_repository.DocumentRepository", MagicMock()):
            levels = ["iniciante", "intermediario", "avancado"]
            if hasattr(ls, "_generate_manual_materials"):
                fn = "_generate_manual_materials"
                ls._generate_manual_materials(text, levels, "Ata do Copom")
                outs = list(captured)
            else:
                fn = "_generate_manual_materials_demo"
                ret = ls._generate_manual_materials_demo(text, levels, "Ata do Copom")
                outs = [{"nivel": m["nivel"], "formato": m["formato"], "conteudo": m["conteudo_gerado"]}
                        for m in ret[0]["materiais"]]
        results[doc_name] = {"source": text, "function": fn, "outputs": outs}

    Path(args.out).write_text(json.dumps({"label": args.label, "docs": results}, ensure_ascii=False, indent=1),
                              encoding="utf-8")
    print(f"{args.label}: {sum(len(v['outputs']) for v in results.values())} saídas -> {args.out}")


if __name__ == "__main__":
    main()
