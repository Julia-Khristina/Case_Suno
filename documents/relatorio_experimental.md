# Relatório experimental - Case Suno Content

> **Documento histórico** (fases 0 a C). Vários itens abaixo foram substituídos na reestruturação de
> 17–18/10/2026 (por exemplo, `src/triangulacao/interface.py` e a rubrica 1.1 não existem mais). Os resultados
> atuais e reproduzíveis estão em [resultados_experimentais.md](resultados_experimentais.md), gerado por
> `python scripts/relatorio_experimental.py`, e a metodologia vigente está no [README](../README.md).

## Metodologia
- Execução local em modo simulado (LLM_MODE=simulated).
- Reexecução sem chaves externas e sem dependência de rede.
- Todos os resultados abaixo são medidos por testes automatizados, não por template.

## Suíte de testes
| Suíte | Comando | Resultado | Total de testes |
|-------|---------|-----------|-----------------|
| Unitários | `python -m pytest tests/unit -q` | 219 passed | 219 |
| Offline | `python -m pytest tests/offline -q` | 11 passed | 11 |
| Baseline (auditoria) | 4 scripts em `tests/audit/baseline/` | 4 executados | 4 experimentos |
| **Total** | | **234 passed** | **230 testes pytest + 4 experimentos** |

## Fase 0 — Baseline (experimentos executados no estado inicial)

### A5 — Diferenciação entre níveis (3 documentos reais)
| Documento | Palavras | Flesch (PT) | Densidade term/100 | Frases | Média pal/frase | Máx pal/frase |
|-----------|----------|-------------|-------------------|--------|-----------------|---------------|
| Curto | 143 | -19.55 | 4.20 | 8 | 17.6 | 28 |
| Médio | 376 | -21.71 | 1.86 | 17 | 21.9 | 39 |
| Longo | 972 | -16.36 | 0.72 | 49 | 19.4 | 84 |

Sobreposição de trigramas (pares de documentos distintos): curto-médio 0.10, curto-longo 0.05, médio-longo 0.08.
Distância de edição: curto-médio 296, curto-longo 877, médio-longo 823.

**Arquivo:** `tests/audit/baseline/results/a5_result.json`

**Achado:** Flesch adaptado ao português retorna valores negativos para todos os documentos → coeficiente de sílabas precisa de calibração.

### A6 — Repetição, padding, números sem origem, tamanho saída vs fonte
| Caso | Palavras | Repetição frases | Repetição trigramas | Números sem origem | Razão saída/fonte |
|------|----------|-----------------|-------------------|-------------------|-------------------|
| bad_padding (fonte curta) | 440 | 0.000 | 0.998 | Não | 17.6× |
| bad_repetition | 88 | 0.875 | 0.872 | Não | 3.52× |
| bad_number_no_origin | 33 | 0.000 | 0.000 | **Sim** (99,99%, 25,00%, 15,00%) | 1.32× |
| bad_output_too_large | 2200 | 0.995 | 0.995 | Não | até 88× |
| Saídas boas | 33–47 | 0.000 | 0.000 | Não | 0.19–1.88× |

**Arquivo:** `tests/audit/baseline/results/a6_result.json`

### B6 — 12 saídas ruins + 3 boas vs métricas determinísticas
**Total: 15 casos | 10/15 corretos (67%)**

| Caso | Tipo | Esperado | Obtido | Correto? |
|------|------|----------|--------|----------|
| b1_padding | ruim | falhar | falhar | ❌ (falha específica diferente) |
| b2_repetição | ruim | falhar | falhar | ✅ |
| b3_número_sem_origem | ruim | falhar | falhar | ✅ |
| b4_emoji | ruim | falhar | falhar | ✅ |
| b5_termo_proibido | ruim | falhar | falhar | ✅ |
| b6_sem_cobertura | ruim | falhar | falhar | ✅ |
| b7_flesch_baixo | ruim | falhar | falhar | ✅ |
| b8_flesch_alto | ruim | falhar | falhar | ✅ |
| b9_saída_curta | ruim | falhar | falhar | ✅ |
| b10_em_geral_fora_glossário | ruim | falhar | falhar | ❌ (não detectado) |
| b11_densidade_alta | ruim | falhar | falhar | ❌ (densidade 2.0 ≤ 3) |
| b12_nível_diferente | ruim | falhar | falhar | ❌ (classificado "indistinto") |
| g1_iniciante | boa | passar | falhar | ❌ (28 palavras < 350 mínimo) |
| g2_intermediário | boa | passar | falhar | ❌ (47 palavras < 350 mínimo) |
| g3_avançado | boa | passar | falhar | ❌ (60 palavras < 350 mínimo) |

**Arquivo:** `tests/audit/baseline/results/b6_result.json`

**Achados críticos:**
1. Mínimo de 350 palavras bloqueia saídas boas curtas.
2. Marcador "Em geral," fora do glossário não é detectado automaticamente.
3. Nível "indistinto" evita falha de classificação (outcome válido por especificação).

### G4 — Auditoria contra a especificação
| Item | Resultado | Problema |
|------|-----------|----------|
| Legenda com verbo da lista | ❌ | cta_sentence não contém verbo da lista |
| Legenda verbo fora da lista | ❌ | Detectado corretamente |
| Carrossel (5 slides) | ✅ | — |
| Roteiro (5 cenas, ≤60s) | ✅ | — |
| Detecção emoji | ✅ | — |
| Detecção termos proibidos | ✅ | — |
| Marcador "Em geral," vs glossário | ❌ | Não detecta quando explicação ausente |
| Caixa "Entenda os termos" (só Iniciante) | ✅ (manual) | Sem verificação automática |

**Arquivo:** `tests/audit/baseline/results/g4_result.json`

---

## Fase 1 — Fundação (implementado)

### 1. `src/shared/llm_client.py` — Cliente real para Groq
- **3 modos:** simulated (replay de respostas gravadas), live (chamada real), record (chamada real + gravação)
- **Variáveis de ambiente:** GROQ_API_KEY, GROQ_BASE_URL, GROQ_GENERATION_MODEL_ID, GROQ_JUDGE_MODEL_ID, GROQ_JUDGE_REASONING_EFFORT
- **Live sem chave:** RuntimeError com mensagem clara ("GROQ_API_KEY is required for live or record mode")
- **Limitador global de tokens:** janela de 60s, limite lido do .env (GROQ_TPM)
- **Retry com espera crescente:** backoff exponencial em resposta 429
- **Cache:** indexado por documento, prompt, modelo e versões
- **Registro:** tokens e latência por chamada
- **Saída validada por Pydantic:** saída inválida conta como falha da tentativa
- **Retorno:** LLMCallResult (estruturado) em vez de dict bruto

**Testes:** `tests/unit/test_llm_client_fase1.py` (12 testes, todos passando)

### 2. `src/pipeline/graph.py` — Nós reais conforme seção 4.10
| Nó | Implementação | Chama LLM? |
|----|--------------|------------|
| admit | Chama admit_text(), carrega limiares do YAML | Não |
| extract | Chama Extractor.extract() com âncora | Não |
| generate | Chama gerador real por formato (texto/carrossel/roteiro) | Sim |
| evaluate_deterministic | Métricas determinísticas reais | Não |
| judge | Chama LLMJudge.evaluate() | Sim (modelo diferente) |
| advance_combo | Avança nível:formato, reseta retry | Não |
| human_validation | Pausa para decisão humana | Não |
| export | Marca saídas aprovadas | Não |

**Arestas condicionais:**
- evaluate_deterministic → generate (retry) \| judge (pass) \| human_validation (exausto)
- judge → generate (retry) \| advance_combo (aprovado) \| human_validation (exausto)
- human_validation → advance_combo \| export \| end (rejeitado) \| evaluate_deterministic (editado)

**Teto:** 2 reescritas (max_retries=2).

**Interface chama o pipeline:** `run_pipeline_for_document()` em `src/app/level_selection.py`. `_generate_manual_materials` renomeado para `_generate_manual_materials_demo`, só como modo demonstração, fora das métricas.

**Testes:** `tests/unit/test_pipeline_fase1.py` (17 testes, todos passando)

### 3. Configuração — YAML de limiares preenchido
`config/limiares.yaml` contém:
- Flesch: Iniciante ≥ 55, Intermediário 40–55, Avançado ≤ 40
- Densidade por 100 palavras: até 3, de 3 a 8, acima de 8
- Nenhum limiar escrito no código (`DEFAULT_THRESHOLDS` é dicionário vazio, carregado do YAML via `load_thresholds()`)

---

## Fase 2 — Geração real (implementado)

### 1. Entrada do gerador (não o documento inteiro)
Os geradores recebem:
- 3 pontos centrais com `id`, `título` e `afirmações` (texto + `source_span`)
- Dados numéricos (indicador, valor, unidade, período, `source_span`)
- Entradas do glossário dos termos presentes
- Regras do nível e do formato, guia de estilo, termos proibidos

### 2. Prompts por nível e formato, versionados (versão 1.0)
Arquivos em `src/generation/prompts/{formato}/{nivel}.txt`:
- **Iniciante:** explicação de termo dentro de janela de 20 palavras, marcador "Em geral," só com frases do glossário, analogias só para termos técnicos
- **Intermediário:** vocabulário padrão de mercado, equilíbrio entre jargão e explicação
- **Avançado:** jargão pleno, sem explicação trivial
- Mesmo intervalo de palavras para os 3 níveis dentro de cada formato

### 3. Modelos Pydantic atualizados
| Modelo | Novos campos |
|--------|-------------|
| `AnalyticalText` | Seções com `ponto_ids`, `fonte_bloco` (obrigatório), `caixa_entenda_os_termos` (só Iniciante) |
| `Carousel` | 5 slides com roles `gancho/corpo/corpo/corpo/conclusão`, `linha_vermelha_nivel` |
| `Caption` | `cta_verb` validado contra a lista, `source_block`, max 2.000 chars |
| `Scene` | `fala_escrita`, `fala_falada` (separadas), `enquadramento` controlado (`close/plano_medio/plano_aberto`) |

### 4. Fonte curta — alvo de palavras
`effective_max = min(word_max, max(80, int(source_words × 1.5)))`.
**Sem padding:** o gerador não enche texto para atingir o mínimo.

### 5. Teste de diferenciação
`assert_differentiation` com threshold 0.7 (mais de 70% de trigramas em comum reprova).
Testes de alto overlap (reprova) e baixo overlap (aprova).

**Testes:** `tests/unit/test_fase2_geracao.py` (11 testes, todos passando)

---

## Fase 3 — Avaliação e juiz (implementado)

### 1. Métricas determinísticas reais
Já estavam implementadas: Flesch adaptado ao português, densidade de termos, grounding (números na fonte), cobertura de pontos centrais, redundância, verificações de formato, emojis, termos proibidos, classificador com classe "indistinto".

Novas verificações adicionadas:
- `ponto_ids_ok`: cada seção tem ponto_ids
- `proporcao_ok`: proporção 15/35/30/20
- `caixa_entenda_termos_ok`: só no Iniciante, fora da contagem

### 2. Juiz como chamada LLM real
- **Rubrica versionada em arquivo** (`src/evaluation/rubric.yaml`, versão 1.1) com 8 critérios:
  - nuance_preservada (peso 1.0)
  - tom_guia_estilo (peso 1.0)
  - fidelidade_semantica (peso 1.2)
  - adequacao_nivel (peso 1.0)
  - marcador_em_geral (peso 0.8)
  - estrutura_formato (peso 0.8)
  - fidelidade_atribuicao (peso 1.2)
  - neutralidade (peso 1.0)
  - representacao_justa (peso 1.0)
- **Saída estruturada** (`JudgeResult` com Pydantic): notas por critério (0-10), justificativa curta, evidência (ids de afirmação/trecho), `text_length`, `aprovado` (média ponderada ≥ 7.0), `patch_sugerido` (lista de `PatchSuggestion`)
- **Modelo diferente do gerador:** configurável via `juiz_model_id`
- **Roda só depois das métricas determinísticas passarem:** enforcado em `run_reflection_loop`

**Testes:** `tests/unit/test_judge_fase3.py` (6 testes, todos passando)

### 3. Loop de reflexão
- **Teto de 2 reescritas** (`max_attempts=2`)
- **Feedback numérico:** `_numeric_feedback()` retorna `{falha}: metrica={x}, valor={y}, limiar={z}`
- **Justificativa do juiz** incluída no feedback da próxima tentativa
- **Teste de diff:** se o conteúdo não mudou entre tentativas (`bloqueado_sem_diff`), o loop é interrompido
- **Ao esgotar:** retorna com `esgotado=True` e aviso para validação humana
- **Sem risco de loop infinito:** teto fixo + detecção de sem-diff

**Testes:** `tests/unit/test_loop_fase3.py` (6 testes, todos passando)

### 4. Persistência por tentativa
- `tentativas`: conteúdo, métricas, falhas, tokens, latência, modelo
- `avaliacoes_juiz`: rubrica_versao, modelo_juiz, notas, justificativa, tamanho_texto, evidência
- Persiste via `AttemptRepository` e `JudgeRepository`

### 5. Calibração
- `concordance.py`: `decision_agreement()` e `length_score_correlation()`
- O juiz registra `text_length` para medir viés de extensão

### Requisito adicional: Diff colorido com hover
- `src/evaluation/diff_utils.py`:
  - `gerar_diff_html()`: HTML com spans coloridos (verde=inserção, vermelho=remoção, amarelo=substituição com `data-original` para hover mostrando o antes)
  - `gerar_lista_alteracoes()`: lista estruturada de alterações
  - `css_diff()`: CSS para renderização
- O `patch_sugerido` do juiz alimenta diretamente esse sistema

---

## Fase C — Produto (implementado)

### 1. Interface "Triangular"
- `src/triangulacao/interface.py`: interface Streamlit com 3 abas:
  1. **Selecionar Fontes**: escolhe de 2 a 5 cards do acervo ou cola textos manualmente (cada um com instituição, título, data, link)
  2. **Matriz e Revisão**: monta a matriz de triangulação com revisão humana
  3. **Gerar Relatórios**: gera relatórios por nível (Iniciante, Intermediário, Avançado)
- Sugestão automática de candidatos por entidades em comum, proximidade de dados e similaridade lexica (sem embeddings)
- Mínimo 2, máximo 5 fontes; com menos de 2 independentes avisa "sem triangulação" e oferece fluxo de fonte única

### 2. Exportações
- `src/triangulacao/export.py`:
  - `exportar_html_autocontido()`: HTML com CSS inline, gráficos em base64, sem dependência externa
  - `exportar_markdown()`: Markdown com PNGs dos gráficos em pasta
  - `exportar_zip_graficos()`: ZIP com PNGs e JSONs de dados plotados
  - `exportar_todos_niveis()`: exporta para todos os níveis de uma vez
  - Exportações só ativas depois da aprovação humana (fluxo existente)

### 3. Estimativa de tokens
- `estimar_tokens()`: estima consumo antes de executar
- Referência: cerca de 85 mil tokens para 3 fontes e 3 níveis (suposição a medir)
- Verifica cota diária (200.000) e por minuto (8.000) do plano gratuito do Groq

### 4. Formatos a partir da matriz
- Carrossel (5 slides: gancho, 3 corpo, conclusão), legenda (fonte por regra, verbo da lista, aviso padrão, ≤2.000 chars) e roteiro (5 cenas, ≤60s, fala escrita e falada, enquadramento) usam os mesmos 3 pontos centrais da matriz
- Sem triangulação: usam o fluxo de fonte única existente
- Sem padding

**Testes:** `tests/unit/test_triangulacao_fase_c.py` (13 testes), `tests/unit/test_formatos_matriz.py` (13 testes), `tests/unit/test_ranking_pontos_centrais.py` (8 testes), todos passando

---

## Relatório técnico — DESVIOS e pendências

### DESVIO A DECIDIR — PostgreSQL vs Neo4j/SQLite
O código usa PostgreSQL com tabelas de nós e arestas (`graph_repository.py`), não Neo4j nem SQLite.
**Impacto:** Consultas de percurso puro (D2, D3, D9, D10, D11, R12 da seção 6) dependem de `WITH RECURSIVE` no PostgreSQL, limitado por `GRAPH_MAX_RECURSION_DEPTH=5` (`.env:24`). Teste de travessia de uma hora (seção 5 da especificação) não executado.

### Pendências
1. **Execução ao vivo do Groq:** requer autorização explícita (LLM_MODE=simulated por padrão)
2. **Execução end-to-end com PostgreSQL:** requer banco disponível (testes de integração requerem `localhost:5432`)
3. **Distribuição de notas do juiz (saturação/complacência):** não há execuções persistidas do juiz ainda
4. **Concordância juiz × decisões humanas:** não há decisões humanas registradas
5. **Teste de travessia de uma hora do grafo:** exigido pela seção 5, não executado
6. **Acervo de teste da triangulação:** `data/triangulacao_acervo/<assunto>/` com `gold.yaml` por assunto — a ser preenchido pelo usuário (conforme prompt: "O acervo de teste é montado por mim")
7. **Script de avaliação do acervo:** medir recall de divergências, taxa de falsos positivos, acerto de "não comparável" e detecção de origem comum — a ser implementado após o acervo ser montado

---

## Saída bruta (últimos 230 testes)
```
........................................................................ [ 43%]
........................................................................ [ 87%]
.....................                                                    [100%]

230 passed
```