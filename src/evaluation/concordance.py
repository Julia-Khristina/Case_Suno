"""Concordance between judge and human decisions."""
from statistics import fmean


def decision_agreement(judge_decisions: list[str], human_decisions: list[str]) -> float:
    if not judge_decisions or len(judge_decisions) != len(human_decisions):
        return 0.0
    matches = sum(1 for judge, human in zip(judge_decisions, human_decisions) if judge == human)
    return matches / len(judge_decisions)


def length_score_correlation(text_lengths: list[int], scores: list[float]) -> float:
    if len(text_lengths) != len(scores) or len(text_lengths) < 2:
        return 0.0
    mean_length = fmean(text_lengths)
    mean_score = fmean(scores)
    numerator = sum((length - mean_length) * (score - mean_score) for length, score in zip(text_lengths, scores))
    length_variance = sum((length - mean_length) ** 2 for length in text_lengths)
    score_variance = sum((score - mean_score) ** 2 for score in scores)
    if length_variance == 0 or score_variance == 0:
        return 0.0
    return numerator / (length_variance ** 0.5 * score_variance ** 0.5)