"""Typology helpers for assertions."""
VALID_ASSERTION_TYPES = {"fato", "projecao", "evento_futuro"}
VALID_ASSERTION_ROLES = {"nenhum", "causa", "impacto", "risco", "acompanhar"}


def normalize_assertion_type(value: str) -> str:
    if value in VALID_ASSERTION_TYPES:
        return value
    if "futuro" in value or "future" in value:
        return "evento_futuro"
    if "projec" in value:
        return "projecao"
    return "fato"


def normalize_assertion_role(value: str) -> str:
    if value in VALID_ASSERTION_ROLES:
        return value
    lowered = value.lower()
    for role in VALID_ASSERTION_ROLES:
        if role in lowered:
            return role
    return "nenhum"