"""Pending term flow."""
from typing import Iterable


def find_pending_terms(text_terms: Iterable[str], approved_terms: Iterable[str]) -> list[str]:
    approved = {term.lower() for term in approved_terms}
    return [term for term in text_terms if term.lower() not in approved]