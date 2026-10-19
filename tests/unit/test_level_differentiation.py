from src.evaluation.differentiation import trigram_overlap_ratio, assert_differentiation


def test_high_overlap_detected():
    text = "palavra um dois palavra tres quatro cinco seis sete oito nove dez"
    assert trigram_overlap_ratio(text, text) == 1.0


def test_different_texts_pass():
    left = "Copom manteve a Selic em dez pontos cinco zero porcento e focou no curto prazo."
    right = "A autoridade monetaria preservou a taxa e destacou fatores estruturais de prazo maior."
    assert_differentiation({"iniciante": left, "avancado": right})
