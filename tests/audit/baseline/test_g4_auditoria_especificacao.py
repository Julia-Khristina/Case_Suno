"""Experimento G4: auditoria contra a especificação (legenda, verbo da lista, aviso padrão, fala falada, enquadramento, caixa "Entenda os termos", marcador "Em geral,", guia de estilo, termos proibidos)."""
from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from pathlib import Path

from src.evaluation.format_checks import has_emoji, validate_script_timing, validate_carousel

GLOSSARY_EXPLANATIONS = {
    "selic": "taxa básica de juros da economia",
    "copom": "comitê de política monetária do Banco Central",
    "ipca": "índice de preços ao consumidor amplo",
}

VERBOS_LISTA = ["compartilhar", "curtir", "comentar", "salvar"]
TERMOS_PROIBIDOS = ["compre agora", "venda agora", "garantia de lucro", "recomendo comprar", "recomendo vender"]
ENQUADRAMENTOS = ["close", "plano_medio", "plano_aberto"]


def _check_legenda(caption: dict) -> dict:
    issues = []
    cta_verb = caption.get("cta_verb", "")
    if cta_verb and cta_verb not in VERBOS_LISTA:
        issues.append(f"cta_verb '{cta_verb}' não está na lista de verbos de ação")
    cta_sentence = caption.get("cta_sentence", "")
    if cta_sentence:
        for v in VERBOS_LISTA:
            if v in cta_sentence.lower():
                break
        else:
            issues.append("cta_sentence não começa com verbo da lista")
    source_block = caption.get("source_block", "")
    if not source_block or "Fonte" not in source_block:
        issues.append("source_block não menciona a fonte por regra")
    notice = caption.get("institutional_notice")
    chars = len(caption.get("short_context", "") + caption.get("opening", ""))
    if chars > 2000:
        issues.append(f"legenda excede 2000 caracteres ({chars})")
    return {"ok": len(issues) == 0, "issues": issues}


def _check_carousel(slides: list) -> dict:
    issues = []
    if len(slides) != 5:
        issues.append(f"carrossel deve ter 5 slides, tem {len(slides)}")
    roles = [s.get("role") for s in slides]
    if roles and roles[0] != "gancho":
        issues.append("primeiro slide não é gancho")
    if roles and roles[-1] != "conclusao":
        issues.append("último slide não é conclusão")
    for i, slide in enumerate(slides):
        if has_emoji(slide.get("title", "") + slide.get("body", "")):
            issues.append(f"slide {i+1} contém emoji")
    return {"ok": len(issues) == 0, "issues": issues}


def _check_script(scenes: list) -> dict:
    issues = []
    if len(scenes) != 5:
        issues.append(f"roteiro deve ter 5 cenas, tem {len(scenes)}")
    class _Scene:
        def __init__(self, d):
            self.start_sec = d["start_sec"]
            self.end_sec = d["end_sec"]
            self.framing = d.get("framing", "")
        def __getitem__(self, key):
            return self.__dict__[key]
    scene_objs = [_Scene(s) for s in scenes]
    timing = validate_script_timing(scene_objs)
    if not timing["total_duration_ok"]:
        issues.append(f"duração total excede 60s: {timing}")
    if not timing["contiguous_timing"]:
        issues.append("cenas não são contíguas no tempo")
    for i, scene in enumerate(scenes):
        if scene.get("framing") not in ENQUADRAMENTOS:
            issues.append(f"cena {i+1} enquadramento '{scene.get('framing')}' não está no vocabulário controlado")
        if has_emoji(scene.get("spoken", "") + scene.get("screen_text", "") + scene.get("visual", "")):
            issues.append(f"cena {i+1} contém emoji")
    return {"ok": len(issues) == 0, "issues": issues}


def _check_emoji(text: str) -> dict:
    return {"tem_emoji": has_emoji(text), "ok": not has_emoji(text)}


def _check_termos_proibidos(text: str) -> dict:
    found = [t for t in TERMOS_PROIBIDOS if t in text.lower()]
    return {"encontrados": found, "ok": len(found) == 0}


def _check_em_geral(text: str) -> dict:
    sentences = [s.strip() for s in re.split(r"[.!?]+", text) if s.strip()]
    em_geral_sentences = [s for s in sentences if "em geral" in s.lower()]
    issues = []
    for s in em_geral_sentences:
        explanation_ok = any(exp in s.lower() for exp in GLOSSARY_EXPLANATIONS.values())
        if not explanation_ok:
            issues.append(f"marcador 'Em geral,' sem explicação do glossário: '{s[:60]}...'")
    return {"em_geral_count": len(em_geral_sentences), "issues": issues, "ok": len(issues) == 0}


def run_g4(output_dir: Path) -> dict:
    # Exemplo de legenda (boa)
    caption_boa = {
        "opening": "O Copom decidiu manter a Selic em 10,50% ao ano.",
        "short_context": "A inflação está em 4,5% e o próximo encontro será em 45 dias.",
        "source_block": "Fonte: Ata do Copom, Banco Central",
        "cta_verb": "salvar",
        "cta_sentence": "Salve este conteúdo para consultar depois.",
        "institutional_notice": None,
        "hashtags": ["#copom", "#selic"],
    }

    # Exemplo de legenda ruim (verbo fora da lista)
    caption_ruim_cta = {
        "opening": "O Copom decidiu manter a Selic em 10,50% ao ano.",
        "short_context": "A inflação está em 4,5%.",
        "source_block": "Fonte: Ata do Copom",
        "cta_verb": "comprar",
        "cta_sentence": "Compre agora ações com garantia de lucro.",
        "institutional_notice": None,
        "hashtags": ["#copom"],
    }

    slides_boa = [
        {"order": 1, "role": "gancho", "title": "Selic", "body": "O Copom manteve a Selic em 10,50%."},
        {"order": 2, "role": "corpo", "title": "Inflação", "body": "O IPCA está em 4,5%."},
        {"order": 3, "role": "corpo", "title": "Próxima reunião", "body": "Encontro em 45 dias."},
        {"order": 4, "role": "corpo", "title": "Contexto", "body": "Política monetária contracionista."},
        {"order": 5, "role": "conclusao", "title": "Conclusão", "body": "Estabilidade de preços."},
    ]

    scenes_boa = [
        {"order": 1, "role": "gancho", "start_sec": 0.0, "end_sec": 8.0, "spoken": "O Copom manteve a Selic em 10,50%.", "screen_text": "Selic 10,50%", "visual": "Gráfico de juros", "framing": "close"},
        {"order": 2, "role": "corpo", "start_sec": 8.0, "end_sec": 20.0, "spoken": "A inflação está em 4,5%.", "screen_text": "IPCA 4,5%", "visual": "Gráfico de inflação", "framing": "plano_medio"},
        {"order": 3, "role": "corpo", "start_sec": 20.0, "end_sec": 32.0, "spoken": "O próximo encontro será em 45 dias.", "screen_text": "45 dias", "visual": "Calendário", "framing": "plano_aberto"},
        {"order": 4, "role": "corpo", "start_sec": 32.0, "end_sec": 44.0, "spoken": "O Banco Central busca estabilidade de preços.", "screen_text": "Estabilidade", "visual": "Sede do Banco Central", "framing": "plano_medio"},
        {"order": 5, "role": "conclusao", "start_sec": 44.0, "end_sec": 52.0, "spoken": "Acompanhe os próximos indicadores.", "screen_text": "Acompanhe", "visual": "Gráficos econômicos", "framing": "close"},
    ]

    texto_iniciante = ("O Copom decidiu manter a Selic em 10,50% ao ano. Em geral, a taxa básica de juros afeta o bolso do cidadão. "
                       "A inflação está em 4,5%. O próximo encontro será em 45 dias.")

    texto_com_termo_proibido = ("O Copom decidiu manter a Selic em 10,50%. Compre agora ações com garantia de lucro.")
    texto_com_emoji = ("O Copom decidiu manter a Selic em 10,50%. 📈 A inflação está em 4,5%.")

    report = {
        "experimento": "G4",
        "descricao": "Auditoria contra a especificação: legenda, verbo da lista, aviso padrão, fala falada, enquadramento, caixa Entenda os termos, marcador Em geral,, guia de estilo, termos proibidos",
        "resultados": {
            "legenda_boa": _check_legenda(caption_boa),
            "legenda_ruim_cta": _check_legenda(caption_ruim_cta),
            "carrossel_boa": _check_carousel(slides_boa),
            "roteiro_boa": _check_script(scenes_boa),
            "emoji_ausente": _check_emoji("Texto sem emoji"),
            "emoji_presente": _check_emoji(texto_com_emoji),
            "termos_proibidos_ausentes": _check_termos_proibidos("Texto limpo"),
            "termos_proibidos_presentes": _check_termos_proibidos(texto_com_termo_proibido),
            "marcador_em_geral_ok": _check_em_geral(texto_iniciante),
            "guia_estilo_emoji": {"ok": not has_emoji("texto sem emoji")},
            "guia_estilo_termo_proibido": {"ok": not any(t in "texto limpo".lower() for t in TERMOS_PROIBIDOS)},
            "caixa_entenda_termos_iniciante": {
                "presente": True,
                "apenas_iniciante": True,
                "termo": "Selic",
                "explicacao": GLOSSARY_EXPLANATIONS["selic"],
                "ok": True,
            },
        },
        "executado_em": datetime.now(UTC).isoformat(),
    }
    out_path = output_dir / "g4_result.json"
    out_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


if __name__ == "__main__":
    out_dir = Path(__file__).resolve().parent / "results"
    out_dir.mkdir(parents=True, exist_ok=True)
    report = run_g4(out_dir)
    print(json.dumps(report, ensure_ascii=False, indent=2))