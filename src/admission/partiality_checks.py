"""Partial-content checks."""
from .models import PartialityResult

MIN_TEXT_CHARACTERS = 500
SENTENCE_ENDINGS = (".", "!", "?", '"', "”")

PAYWALL_MARKERS = [
    "assine para continuar",
    "conteudo exclusivo para assinantes",
    "continue lendo",
    "faça login para continuar",
]


def check_partiality(text: str, min_characters: int = MIN_TEXT_CHARACTERS) -> PartialityResult:
    reasons: list[str] = []
    normalized = text.strip()

    if len(normalized) < min_characters:
        reasons.append("tamanho_minimo_nao_atingido")

    if not normalized.endswith(SENTENCE_ENDINGS):
        reasons.append("texto_nao_termina_em_frase_completa")

    lowered = normalized.lower()
    if any(marker in lowered for marker in PAYWALL_MARKERS):
        reasons.append("marcador_de_paywall_encontrado")

    return PartialityResult(is_partial=bool(reasons), reasons=reasons)