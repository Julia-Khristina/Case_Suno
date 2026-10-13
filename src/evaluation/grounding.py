"""Grounding and factual fidelity checks."""
import re

NUMBER_PATTERN = re.compile(r"\d[\d.,]*%?")


def extract_numbers(text: str) -> list[str]:
    return NUMBER_PATTERN.findall(text)


def normalize_number(value: str) -> str:
    return value.replace(" ", "").strip()


def all_generated_numbers_exist(generated_text: str, source_text: str) -> bool:
    source_normalized = normalize_number(source_text)
    for number in extract_numbers(generated_text):
        if normalize_number(number) not in source_normalized:
            return False
    return True


def check_general_impact_markers(text: str, approved_explanations: list[str]) -> bool:
    approved = {explanation.strip().lower() for explanation in approved_explanations}
    for sentence in text.split("."):
        if "em geral" in sentence.lower():
            explanation = sentence.strip().lower()
            if explanation and explanation not in approved and not any(approved_item in explanation for approved_item in approved):
                return False
    return True