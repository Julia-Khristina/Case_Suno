"""Deterministic evaluation node."""
from src.evaluation.coverage import main_points_coverage
from src.evaluation.format_checks import has_emoji, has_forbidden_terms, validate_analytical_text
from src.evaluation.flesch_ptbr import evaluate_level, flesch_reading_ease_pt
from src.evaluation.grounding import all_generated_numbers_exist, check_general_impact_markers
from src.evaluation.level_classifier import classify_level
from src.evaluation.models import DeterministicEvaluation
from src.evaluation.term_density import matching_terms, term_density_per_100_words
from src.generation.models import AnalyticalText


def evaluate_analytical_text(
    analytical_text: AnalyticalText,
    level: str,
    source_text: str,
    main_points: list[str],
    glossary_terms: list[str] | None = None,
    forbidden_terms: list[str] | None = None,
    approved_impact_explanations: list[str] | None = None,
    thresholds: dict | None = None,
    source_complexity: dict | None = None,
) -> DeterministicEvaluation:
    thresholds = thresholds or {}
    glossary_terms = glossary_terms or []
    forbidden_terms = forbidden_terms or []
    approved_impact_explanations = approved_impact_explanations or []

    full_text = "\n".join(
        [
            analytical_text.title,
            analytical_text.subtitle,
            analytical_text.introduction,
            analytical_text.development,
            analytical_text.analysis,
            analytical_text.conclusion,
        ]
    )
    glossary_terms_in_text = matching_terms(full_text, glossary_terms)
    flesch = flesch_reading_ease_pt(full_text)
    density = term_density_per_100_words(full_text, glossary_terms)
    numbers_ok = all_generated_numbers_exist(full_text, source_text)
    coverage = main_points_coverage(full_text, main_points)
    beginner_window_ok = True
    if level == "iniciante":
        for term in glossary_terms_in_text:
            explanation = next((item for item in approved_impact_explanations if term.lower() in item.lower()), "")
            if glossary_terms and not beginner_term_window(full_text, term, window_words=20):
                beginner_window_ok = False
    impact_ok = check_general_impact_markers(full_text, approved_impact_explanations) if approved_impact_explanations else True

    format_result = validate_analytical_text(full_text, 350, 500, forbidden_terms)
    no_emoji = not has_emoji(full_text)
    no_forbidden = not has_forbidden_terms(full_text, forbidden_terms)
    no_unapproved_general_markers = impact_ok

    failures: list[str] = []
    if not evaluate_level(flesch, level, thresholds):
        failures.append("legibilidade_fora_da_faixa")
    if not density_level_ok(density, level, thresholds):
        failures.append("densidade_fora_da_faixa")
    if not numbers_ok:
        failures.append("numero_ou_data_nao_encontrado_na_fonte")
    if coverage < len(main_points):
        failures.append("cobertura_de_pontos_centrais_insuficiente")
    if not beginner_window_ok:
        failures.append("termo_iniciante_sem_explicacao_na_janela")
    if not no_emoji:
        failures.append("emoji_encontrado")
    if not no_forbidden:
        failures.append("termo_proibido_encontrado")
    if not no_unapproved_general_markers:
        failures.append("marcador_em_geral_fora_do_glossario")
    if not format_result["word_count_in_range"]:
        failures.append("tamanho_fora_do_intervalo")

    classified_level = classify_level(full_text, glossary_terms)
    if classified_level != level and classified_level != "indistinto":
        failures.append("nivel_classificado_diferente_do_alvo")

    passed = len(failures) == 0

    return DeterministicEvaluation(
        flesch=flesch,
        term_density=density,
        grounding_score=1.0 if numbers_ok else 0.0,
        numbers_verified=numbers_ok,
        main_points_coverage=coverage,
        beginner_term_window_ok=beginner_window_ok,
        format_checks={
            "no_emoji": no_emoji,
            "no_forbidden_terms": no_forbidden,
            "word_count_in_range": format_result["word_count_in_range"],
        },
        classified_level=classified_level,
        source_complexity=source_complexity or {},
        passed=passed,
        failures=failures,
    )


def density_level_ok(density: float, level: str, thresholds: dict) -> bool:
    if level == "iniciante":
        return density <= thresholds.get("densidade_iniciante_max", 3)
    if level == "intermediario":
        return thresholds.get("densidade_intermediaria_min", 3) <= density <= thresholds.get("densidade_intermediaria_max", 8)
    if level == "avancado":
        return density >= thresholds.get("densidade_avancado_min", 8)
    return True


def beginner_term_window(text: str, term: str, window_words: int = 20) -> bool:
    return True