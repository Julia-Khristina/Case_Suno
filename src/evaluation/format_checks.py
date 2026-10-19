"""Format and fidelity checks for generated content."""
from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path

import yaml

from src.evaluation.text_utils import word_count

# Cobre emoticons, pictogramas, transporte, bandeiras, símbolos suplementares (U+1F900–1FAFF),
# símbolos diversos e dingbats (U+2600–27BF: ✅ ❤ ⚠), setas/estrelas usadas como emoji e seletores de variação.
EMOJI_PATTERN = re.compile(
    "["
    "\U0001F000-\U0001FAFF"
    "\U00002600-\U000027BF"
    "\U00002B00-\U00002BFF"
    "\U00002190-\U000021FF"
    "\U0000FE0F\U0000200D"
    "]",
    flags=re.UNICODE,
)


def has_emoji(text: str) -> bool:
    return bool(EMOJI_PATTERN.search(text or ""))


@lru_cache(maxsize=4)
def _load_forbidden(path: str = "config/termos_proibidos.yaml") -> tuple[tuple[str, ...], tuple[str, ...]]:
    file_path = Path(path)
    if not file_path.exists():
        return (), ()
    data = yaml.safe_load(file_path.read_text(encoding="utf-8")) or {}
    return tuple(data.get("termos") or []), tuple(data.get("padroes_recomendacao") or [])


def load_forbidden_terms(path: str = "config/termos_proibidos.yaml") -> list[str]:
    return list(_load_forbidden(path)[0])


def load_recommendation_patterns(path: str = "config/termos_proibidos.yaml") -> list[str]:
    return list(_load_forbidden(path)[1])


def forbidden_terms_found(text: str, forbidden_terms: list[str]) -> list[str]:
    lowered = (text or "").lower()
    return [t for t in forbidden_terms if re.search(rf"(?<!\w){re.escape(t.lower())}(?!\w)", lowered)]


def has_forbidden_terms(text: str, forbidden_terms: list[str]) -> bool:
    return bool(forbidden_terms_found(text, forbidden_terms))


def recommendation_language(text: str, patterns: list[str] | None = None) -> list[str]:
    patterns = load_recommendation_patterns() if patterns is None else patterns
    found = []
    for pattern in patterns:
        for m in re.finditer(pattern, text or "", flags=re.IGNORECASE):
            found.append(m.group(0))
    return found


@lru_cache(maxsize=2)
def load_action_verbs(path: str = "config/verbos_acao.yaml") -> dict[str, tuple[str, ...]]:
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    imperatives = data.get("imperativos") or {}
    return {verb: tuple(imperatives.get(verb, [])) for verb in data.get("verbos", [])}


def cta_problems(cta_verb: str, cta_sentence: str, max_chars: int) -> list[str]:
    """Regras da chamada para ação (seção 4.6): verbo da lista no imperativo, sem números, curta, sem recomendação."""
    verbs = load_action_verbs()
    problems = []
    verb = (cta_verb or "").lower()
    if verb not in verbs:
        problems.append(f"verbo fora da lista: {cta_verb}")
    first_word = (re.findall(r"[^\W\d_]+", cta_sentence or "") or [""])[0].lower()
    if verb in verbs and first_word not in verbs[verb] and first_word != verb:
        problems.append(f"chamada não começa com o imperativo de '{verb}' ({', '.join(verbs[verb])})")
    if re.search(r"\d", cta_sentence or ""):
        problems.append("chamada contém número")
    if len(cta_sentence or "") > max_chars:
        problems.append(f"chamada com {len(cta_sentence)} caracteres (máx. {max_chars})")
    if recommendation_language(cta_sentence or ""):
        problems.append("chamada com linguagem de recomendação")
    return problems


def count_words(text: str) -> int:
    return word_count(text)


def check_section_order(text: str, section_markers: list[str]) -> bool:
    positions = [text.find(marker) for marker in section_markers]
    if any(position < 0 for position in positions):
        return False
    return positions == sorted(positions)


def validate_analytical_text(text: str, word_min: int, word_max: int, forbidden_terms: list[str]) -> dict[str, bool]:
    words = count_words(text)
    return {
        "word_count_in_range": word_min <= words <= word_max,
        "no_emoji": not has_emoji(text),
        "no_forbidden_terms": not has_forbidden_terms(text, forbidden_terms),
    }


def validate_carousel(carousel_slides: list, max_slides: int = 5) -> dict[str, bool]:
    roles = [getattr(s, "role", None) for s in carousel_slides]
    return {
        "slide_count": len(carousel_slides) == max_slides,
        "has_hook": bool(roles) and roles[0] == "gancho",
        "has_conclusion": bool(roles) and roles[-1] == "conclusao",
    }


def script_timing_problems(scenes: list, max_seconds: float) -> list[str]:
    problems = []
    if not scenes:
        return ["roteiro sem cenas"]
    if abs(scenes[0].start_sec) > 1e-6:
        problems.append(f"primeira cena começa em {scenes[0].start_sec}s (esperado 0s)")
    for a, b in zip(scenes, scenes[1:]):
        if b.start_sec < a.end_sec - 1e-6:
            problems.append(f"cenas {a.order} e {b.order} se sobrepõem")
        elif b.start_sec > a.end_sec + 1e-6:
            problems.append(f"intervalo entre as cenas {a.order} e {b.order}")
    if [s.order for s in scenes] != sorted(s.order for s in scenes):
        problems.append("ordem das cenas fora de sequência")
    if scenes[-1].end_sec > max_seconds:
        problems.append(f"duração {scenes[-1].end_sec}s acima de {max_seconds}s")
    return problems


def validate_script_timing(scenes: list, max_seconds: float = 60.0) -> dict[str, bool]:
    problems = script_timing_problems(scenes, max_seconds)
    return {
        "scene_count": len(scenes) == 5,
        "total_duration_ok": bool(scenes) and scenes[-1].end_sec <= max_seconds,
        "contiguous_timing": not any("sobrepõem" in p or "intervalo" in p for p in problems),
        "ordered_timing": not any("ordem" in p for p in problems),
    }
