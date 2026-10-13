"""Numeric data extraction and validation."""
import re
from typing import Iterable


def extract_numbers(text: str) -> list[str]:
    return re.findall(r"\d[\d\.,]*%?", text)


def all_numbers_exist(source_text: str, generated_number: str) -> bool:
    return generated_number in source_text or generated_number.replace(".", "," ) in source_text


def normalize_number(value: str) -> str:
    return value.strip()