"""HTML and text cleaning helpers."""
import re


def clean_html(html: str) -> str:
    html = re.sub(r"(?is)<script.*?>.*?</script>", " ", html)
    html = re.sub(r"(?is)<style.*?>.*?</style>", " ", html)
    text = re.sub(r"(?s)<[^>]+>", " ", html)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


PAYWALL_MARKERS = [
    "assine para continuar",
    "conteudo exclusivo para assinantes",
    "continue lendo",
    "faça login para continuar",
    "subscriber only",
    "sign in to continue",
]


def has_paywall_marker(text: str) -> bool:
    lowered = text.lower()
    return any(marker in lowered for marker in PAYWALL_MARKERS)