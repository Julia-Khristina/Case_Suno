from pydantic import BaseModel


class DeterministicEvaluation(BaseModel):
    flesch: float
    term_density: float
    grounding_score: float
    numbers_verified: bool
    main_points_coverage: int
    beginner_term_window_ok: bool
    format_checks: dict[str, bool]
    classified_level: str
    source_complexity: dict[str, float | int | None]
    passed: bool
    failures: list[str]