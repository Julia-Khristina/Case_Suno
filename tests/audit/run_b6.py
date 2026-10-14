# -*- coding: utf-8 -*-
import os
os.environ.setdefault("PYTHONPATH", ".")
from src.evaluation.thresholds import load_thresholds
from src.generation.models import AnalyticalText
from src.pipeline.nodes.evaluate_deterministic import evaluate_analytical_text
THRESHOLDS = load_thresholds()

GOOD = AnalyticalText(
    title="Titulo do material",
    subtitle="Subtitulo do material",
    introduction="sim. " * 90 + "Ponto central.",
    development="sim. " * 120 + " 10,50%.",
    analysis="sim. " * 110,
    conclusion="sim. " * 80,
    covered_main_points=["Ponto central"],
    word_count_total=405,
    word_count_by_section={"introduction":91,"development":122,"analysis":110,"conclusion":80},
)

def eval_text(name, text, forbidden, main_points):
    if name.startswith("good"):
        at = GOOD
    else:
        at = AnalyticalText(
            title="Titulo do material",
            subtitle="Subtitulo do material",
            introduction=text,
            development=text[:50],
            analysis=text[:50],
            conclusion=text[:120],
            covered_main_points=["Ponto central"],
            word_count_total=len(text.split()),
            word_count_by_section={"introduction": len(text.split()), "development": min(50,len(text.split()))},
        )
    ev = evaluate_analytical_text(
        analytical_text=at,
        level="iniciante",
        source_text="Copom manteve a Selic em 10,50%. Ponto central.",
        main_points=main_points or ["Ponto central"],
        glossary_terms=[],
        forbidden_terms=forbidden,
        thresholds=THRESHOLDS,
    )
    return ev.passed, ev.failures

cases = [
 ("bad_padding", "sim " * 420, []),
 ("bad_number", "A Selic esta em 99,99%.", []),
]
for name, txt, fb in cases:
    p, f = eval_text(name, txt, fb, ["Ponto central"])
    print(name, "pass=", p, "failures=", f)

# expected good
p, f = eval_text("good_x", "x", [], [])
print("GOOD pass=", p, "failures=", f)
