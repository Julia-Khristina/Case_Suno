# Baseline Fase 0 - Resultados dos Experimentos

## A5 - Diferenciação entre níveis (Flesch, densidade de termos, tamanho de frase, trigramas, edição)

**Documentos de teste** (atas do Copom, criadas a partir do acervo de referência):
| Documento | Palavras | Flesch | Densidade term/100 | Termos encontrados | Frases | Média palavras/frase |
|-----------|----------|--------|---------------------|-------------------|--------|----------------------|
| Curto | 143 | -19.55 | 4.20 | 6 (selic, copom, ipca, juros, banco central, meta) | 8 | 17.6 |
| Médio | 376 | -21.71 | 1.86 | 7 (+ pib) | 17 | 21.9 |
| Longo | 972 | -16.36 | 0.72 | 7 (+ pib) | 49 | 19.4 |

**Comparações par a par:**
| Par | Sobreposição de trigramas | Distância de edição |
|-----|---------------------------|---------------------|
| Curto × Médio | 0.10 | 296 |
| Curto × Longo | 0.05 | 877 |
| Médio × Longo | 0.08 | 823 |

**Achados:**
- Flesch adaptado ao português retorna valores negativos para textos curtos → `evaluate_level("iniciante")` falharia sempre para textos < ~200 palavras. O coeficiente de sílabas do português precisa de calibração.
- Densidade de termos cai conforme o texto cresce (4.20 → 1.86 → 0.70) → comportamento esperado para o mesmo glossário.
- Sobreposição de trigramas entre documentos diferentes é baixa (≤ 0.10) → boa separação entre fontes distintas.

## A6 - Repetição, padding, números sem origem, tamanho saída vs fonte

**Saídas ruins detectadas:**
| Caso | Palavras | Repetição frases | Repetição trigramas | Números sem origem | Razão saída/fonte |
|------|----------|------------------|---------------------|---------------------|-------------------|
| bad_padding (curto) | 440 | 0.00 | 0.998 | Não | 17.6× |
| bad_repetition (curto) | 88 | 0.875 | 0.872 | Não | 3.52× |
| bad_number_no_origin (curto) | 33 | 0.00 | 0.00 | **Sim** (99,99%, 25,00%, 15,00%) | 1.32× |
| bad_output_too_large | 2200 | 0.995 | 0.995 | Não | até 88× |

**Saídas boas:** repetição zero, todos os números na fonte, razão saída/fonte entre 0.19 e 1.88.

**Achado:** O detector de números sem origem funciona (99,99% não está na fonte). O ratio saída/fonte pode chegar a 88× com padding.

## B6 - 12 saídas ruins + 3 boas vs métricas determinísticas

**Total: 15 casos | Todos corretos: false**

| Caso | Esperado | Obtido | Correto? | Falhas detectadas |
|------|----------|--------|----------|-------------------|
| b1_padding | falhar | falhar | ❌ | legibilidade, cobertura (não "tamanho") |
| b2_repetição | falhar | falhar | ✅ | redundância, tamanho, cobertura |
| b3_número_sem_origem | falhar | falhar | ✅ | número fora da fonte, tamanho, cobertura |
| b4_emoji | falhar | falhar | ✅ | emoji, tamanho, cobertura |
| b5_termo_proibido | falhar | falhar | ✅ | termo proibido, tamanho, cobertura |
| b6_sem_cobertura | falhar | falhar | ✅ | cobertura, tamanho |
| b7_flesch_baixo_iniciante | falhar | falhar | ✅ | legibilidade, tamanho, cobertura |
| b8_flesch_alto_avancado | falhar | falhar | ✅ | legibilidade, densidade, tamanho |
| b9_saída_muito_curta | falhar | falhar | ✅ | tamanho, cobertura |
| b10_em_geral_fora_glossário | falhar | falhar | ❌ | não detectou marcador em geral |
| b11_densidade_alta_iniciante | falhar | falhar | ❌ | densidade 2.0 ≤ 3 (dentro do limite) |
| b12_nível_classificado_diferente | falhar | falhar | � nível classificado como "indistinto" |
| g1_iniciante (boa) | passar | falhar | ❌ | 28 palavras < 350 mínimo |
| g2_intermediario (boa) | passar | falhar | ❌ | 47 palavras < 350 mínimo |
| g3_avancado (boa) | passar | falhar | ❌ | 60 palavras < 350 mínimo |

**Achados críticos:**
1. O mínimo de 350 palavras bloqueia todas as "saídas boas" de teste — o limiar de admissão precisa ser revisado para textos curtos ou os exemplos precisam ter ≥350 palavras.
2. O marcador "Em geral," fora do glossário não é detectado (b10) — a função `check_general_impact_markers` só verifica se a frase inteira está nas explicações aprovadas, não se o marcador aparece com explicação ausente.
3. Densidade 2.0 para iniciante está dentro do limite (≤3) — b11 não dispara "densidade_fora_da_faixa".
4. Nível classificado como "indistinto" evita a falha "nivel_classificado_diferente_do_alvo" (b12) — "indistinto" é outcome válido por especificação.

## G4 - Auditoria contra a especificação

| Item | Resultado | Problemas |
|------|-----------|-----------|
| Legenda boa (verbo da lista) | ❌ | cta_sentence não começa com verbo da lista |
| Legenda ruim (verbo fora da lista) | ❌ | Detectado corretamente |
| Carrossel (5 slides, gancho/conclusão) | ✅ | Sem problemas |
| Roteiro (5 cenas, ≤60s, enquadramento) | ✅ | Sem problemas |
| Emoji ausente | ✅ | Detecção funciona |
| Emoji presente | ❌ | Detectado corretamente |
| Termos proibidos ausentes | ✅ | Detecção funciona |
| Termos proibidos presentes | ❌ | Detectado corretamente |
| Marcador "Em geral," com explicação do glossário | ❌ | Não detecta quando explicação está ausente |
| Guia de estilo (sem emoji, sem proibidos) | ✅ | Detecção funciona |
| Caixa "Entenda os termos" (só Iniciante) | ✅ (manual) | Não há verificação automática implementada |

## Conclusão da Fase 0

O baseline revela que:
1. **Flesch adaptado ao português** retorna valores negativos para textos curtos — precisa de calibração ou limiares relativos.
2. **Mínimo de 350 palavras** é muito restritivo para testes — bloqueia saídas válidas curtas.
3. **Marcador "Em geral,"** não é validado contra o glossário de forma automática.
4. **Todas as 12 saídas ruins** são detectadas como falhas (100% de detecção), mas nem sempre com a falha específica esperada.
5. **As 3 saídas boas** falham por estarem abaixo do mínimo de palavras.

Arquivos de resultado: `tests/audit/baseline/results/a5_result.json`, `a6_result.json`, `b6_result.json`, `g4_result.json`.

---

**Fase 0 concluída.** Aguardo sua confirmação para iniciar a Fase 1 (Fundação).