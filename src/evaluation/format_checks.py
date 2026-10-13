"""Format and fidelity checks for generated content."""
import re

EMOJI_PATTERN = re.compile(
    "["
    "\U0001F600-\U0001F64F"
    "\U0001F300-\U0001F5FF"
    "\U0001F680-\U0001F6FF"
    "\U0001F1E0-\U0001F1FF"
    "]+",
    flags=re.UNICODE,
)


def has_emoji(text: str) -> bool:
    return bool(EMOJI_PATTERN.search(text))


def has_forbidden_terms(text: str, forbidden_terms: list[str]) -> bool:
    lowered = text.lower()
    return any(term.lower() in lowered for term in forbidden_terms)


def count_words(text: str) -> int:
    return len(re.findall(r"\w+", text, flags=re.UNICODE))


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
    return {
        "slide_count": len(carousel_slides) == max_slides,
        "has_hook": len(carousel_slides) > 0,
        "has_conclusion": len(carousel_slides) > 0,
    }


def validate_script_timing(scenes: list, max_seconds: float = 60.0) -> dict[str, bool]:
    ordered = sorted(scenes, key=lambda scene: scene.start_sec)
    total = scenes[-1].end_sec if scenes else 0
    contiguous = all(
        abs(scenes[index].end_sec - scenes[index + 1].start_sec) < 0.0001
        for index in range(len(scenes) - 1)
    ) if len(scenes) > 1 else True
    return {
        "scene_count": len(scenes) == 5,
        "total_duration_ok": total <= max_seconds,
        "contiguous_timing": contiguous,
        "ordered_timing": ordered == scenes,
    }