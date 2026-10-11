# Plano de Implementação 

Objetivo deste documento: ser a única referência operacional para implementação, sem necessidade de inferir dados, nomes de arquivos, estruturas, regras ou ordem de execução.

## 1. Regras operacionais inegociáveis

1. **Um bloco por vez.** Ao final de cada bloco, entregar resumo detalhado e aguardar aprovação explícita antes de iniciar o próximo.
2. **Escopo completo preservado.** Nenhuma funcionalidade será removida, adiada por conveniência ou transformada em MVP.
3. **Modo simulado obrigatório.** Toda chamada a LLM passa por `LLMClient`, que pode operar em `live` ou `simulated`. Testes automatizados usam somente `simulated`.
4. **Congelamento experimental.** Toda execução registra versões/hashes de glossário, prompts, modelos, limiares, rubrica e guia de estilo. Relatórios usam versão congelada.
5. **Provedor travado.** Groq é o provedor padrão, com dois modelos distintos: `generation_model_id` e `judge_model_id`, ambos fixados em configuração.
6. **Persistência única.** PostgreSQL é a única fonte de verdade. Grafo é modelado como nós/arestas no mesmo banco.
7. **Admissão com árbitro determinístico.** A regra de texto financeiro (≥5 termos distintos do glossário e ≥200 palavras) decide. Extração estruturada é metadado/sinal auxiliar.
8. **Documentos longos.** Chunking por sentença/pragações com offsets de origem preservados + segunda passagem de agregação.
9. **Limiares híbridos.** Faixas absolutas decidem; complexidade da fonte é registrada; `indistinto` é outcome válido quando justificado.
10. **Retroalimentação limitada.** Decisões humanas alimentam apenas métricas de concordância, histórico versionado e auditoria. Nenhuma alteração automática de limiares, prompts ou ranking.
11. **Entrega 100% local.** Link público, se exigido, é incremento posterior. Vídeo demonstrativo do ambiente funcionando é a entrega visual.
12. **Conteúdo é dado, nunca instrução.** Toda saída LLM validada por Pydantic. Saída inválida conta como falha da tentativa.

## 2. Stack e versões

- Linguagem: Python 3.11 ou superior.
- Orquestração: LangGraph com estado Pydantic.
- Validação: Pydantic v2.
- Interface: Streamlit.
- Banco: PostgreSQL 16 em Docker com volume persistente.
- Drivers: `psycopg[binary]` e checkpointer LangGraph compatível com psycopg.
- Coleta/renderização: Playwright.
- Provedor LLM: Groq (IDs fixados em config).
- Avaliação: pytest, DeepEval ou Ragas para asserts.
- Formato de configuração: YAML validado por Pydantic na leitura.
- Controle de versão: Git com commits regulares.

## 3. Estrutura de pastas e arquivos

```text
Case_Suno/
├── README.md
├── docker-compose.yml
├── pyproject.toml
├── .env.example
├── config/
│   ├── glossario.yaml
│   ├── apelidos.yaml
│   ├── verbos_acao.yaml
│   ├── termos_proibidos.yaml
│   ├── guia_estilo.yaml
│   ├── limiares.yaml
│   ├── estrutura_texto.yaml
│   ├── enquadramentos.yaml
│   └── tokens_visuais.yaml
├── src/
│   ├── app/
│   │   ├── main.py
│   │   ├── cards_screen.py
│   │   ├── level_selection.py
│   │   ├── validation_screen.py
│   │   ├── dashboard.py
│   │   ├── glossary_panel.py
│   │   └── status_stream.py
│   ├── api/
│   │   └── internal.py
│   ├── shared/
│   │   ├── models.py
│   │   ├── llm_client.py
│   │   ├── cache.py
│   │   ├── token_limiter.py
│   │   ├── logging.py
│   │   └── schemas.py
│   ├── admission/
│   │   ├── fetcher.py
│   │   ├── cleaner.py
│   │   ├── partiality_checks.py
│   │   ├── classification.py
│   │   ├── origin.py
│   │   ├── pdf_text.py
│   │   └── language.py
│   ├── extraction/
│   │   ├── extractor.py
│   │   ├── chunker.py
│   │   ├── numeric_data.py
│   │   ├── entity_event.py
│   │   └── typology.py
│   ├── glossary/
│   │   ├── reader.py
│   │   ├── aliases.py
│   │   ├── pending_terms.py
│   │   └── versioning.py
│   ├── generation/
│   │   ├── text_analytical.py
│   │   ├── carousel.py
│   │   ├── script.py
│   │   ├── caption.py
│   │   └── prompts/
│   │       ├── text/
│   │       ├── carousel/
│   │       └── script/
│   ├── evaluation/
│   │   ├── flesch_ptbr.py
│   │   ├── term_density.py
│   │   ├── grounding.py
│   │   ├── coverage.py
│   │   ├── format_checks.py
│   │   ├── level_classifier.py
│   │   ├── judge.py
│   │   ├── rubric.yaml
│   │   └── concordance.py
│   ├── pipeline/
│   │   ├── state.py
│   │   ├── graph.py
│   │   ├── checkpointer.py
│   │   └── nodes/
│   │       ├── admit.py
│   │       ├── extract.py
│   │       ├── generate.py
│   │       ├── evaluate_deterministic.py
│   │       ├── judge.py
│   │       ├── route.py
│   │       ├── human_validation.py
│   │       └── export.py
│   ├── persistence/
│   │   ├── database.py
│   │   ├── schema.sql
│   │   ├── migrations/
│   │   ├── repositories/
│   │   └── graph_queries.py
│   ├── collection/
│   │   ├── fetchers.py
│   │   ├── scheduler.py
│   │   ├── cleaner.py
│   │   ├── dedup.py
│   │   ├── ranker.py
│   │   └── card_builder.py
│   ├── rendering/
│   │   ├── playwright_renderer.py
│   │   └── templates/
│   └── export/
│       ├── text_export.py
│       ├── carousel_export.py
│       ├── script_export.py
│       └── zip_export.py
├── tests/
│   ├── unit/
│   ├── integration/
│   ├── e2e/
│   └── offline/
├── tests/fixtures/
│   ├── documents/
│   ├── llm_responses/
│   └── glossary/
├── data/
│   ├── reference_days/
│   ├── sample_documents/
│   └── exports/
├── scripts/
│   ├── migrate.py
│   ├── seed_data.py
│   └── run_offline_suite.py
├── docs/
│   ├── Arquitetura_Sistema.md
│   ├── Plano_Implementacao.md
│   └── decisoes/
└── documents/
    ├── Arquitetura_Sistema.md
    ├── Tapi_Suno.pdf
    └── Plano_Implementacao.md (cópia operacional solicitada)
```

Observação: manter `docs/` como referência arquitetural e `documents/` como pasta pedida pelo usuário para o plano. O arquivo operacional aprovado é `documents/Plano_Implementacao.md`.

## 4. Contratos de configuração (YAML)

### 4.1 `config/glossario.yaml`

Campos obrigatórios:
- `termo` (string)
- `variacoes` (lista de string)
- `nivel` (`iniciante`, `intermediario`, `avancado`)
- `explicacao_iniciante` (string ou null)
- `explicacao_impacto` (string ou null)
- `pronuncia` (string opcional)
- `fonte_definicao` (string ou null)
- `data_consulta` (date ou null)
- `trecho_original` (string ou null)
- `status` (`aprovado`, `pendente`, `sem_definicao`, `autoria_manual`)
- `versao` (string/hash)

Regra: a mesma variação não pode apontar para dois termos.

### 4.2 `config/apelidos.yaml`

Campos:
- `id` (string, vira nó no grafo)
- `tipo` (`instituicao`, `empresa`, `evento_recorrente`)
- `nome_canonico` (string)
- `apelidos` (lista de string)

### 4.3 `config/limiares.yaml`

Campos:
- `flesch_iniciante_min`: 55
- `flesch_intermediario_min`: 40
- `flesch_intermediario_max`: 55
- `flesch_avancado_max`: 40
- `densidade_iniciante_max`: 3
- `densidade_intermediaria_min`: 3
- `densidade_intermediaria_max`: 8
- `densidade_avancado_min`: 8
- `tentativas_maximas`: 2
- `limite_cards_diario_padrao`: 8
- `profundidade_recursao_max`: inteiro configurável
- `janela_contexto_termo_palavras`: 20
- `limite_palavras_frase_roteiro`: configurável
- `palavras_por_segundo_roteiro`: entre 2 e 3, a calibrar lendo em voz alta
- `limite_caracteres_legenda_instagram`: 2000
- `slides_maximos`: 5
- `cenas_maximas`: 5
- `duracao_video_max_segundos`: 60
- `tamanho_texto_min_palavras`: 350
- `tamanho_texto_max_palavras`: 500
- `proporcao_introducao`: 0.15
- `proporcao_desenvolvimento`: 0.35
- `proporcao_analise`: 0.30
- `proporcao_conclusao`: 0.20

### 4.4 `config/estrutura_texto.yaml`

Instruções por seção:
- Introdução: apresentar tema, relevância, questão central.
- Desenvolvimento: dados, indicadores e acontecimentos; todo número/data deve existir na fonte.
- Análise: causas, impactos e riscos somente declarados pela fonte.
- Conclusão: retomar questão central, resumir conclusão da fonte, indicar o que acompanhar.

### 4.5 `config/enquadramentos.yaml`

Vocabulário controlado:
- `close`
- `plano_medio`
- `plano_aberto`

### 4.6 `config/tokens_visuais.yaml`

Campos mínimos:
- paleta: vermelha e branca.
- formato slides: 1080x1350 px (4:5).
- formato Reels: 9:16.
- margens de segurança.
- posição da linha por nível:
  - Iniciante: em cima.
  - Intermediário: duas linhas verticais, uma em cada lado.
  - Avançado: embaixo.
- fundo vermelho: linha branca.

### 4.7 `config/verbos_acao.yaml`

Lista:
- compartilhar
- curtir
- comentar
- salvar

Com formas do imperativo.

### 4.8 `config/termos_proibidos.yaml`

Expressões sensacionalistas, promessas e linguagem de recomendação de compra/venda.

### 4.9 `config/guia_estilo.yaml`

- voz sóbria e factual em português do Brasil;
- uma linha por nível;
- sem emojis;
- sem recomendação de compra ou venda;
- analogia apenas como sinônimo/explicação de termo técnico;
- informações futuras relatadas como projeção/evento futuro, nunca previsão do sistema.

## 5. Contratos Pydantic obrigatórios

### 5.1 Admissão

`AdmissionResult`:
- `is_partial: bool`
- `partial_reasons: list[str]`
- `is_financial: bool`
- `financial_rule_passed: bool`
- `structured_type: str | None`
- `language: str`
- `word_count: int`
- `distinct_glossary_terms: int`
- `origin: OriginMetadata`
- `status: Literal["admitido", "bloqueado", "aviso"]`

### 5.2 Extração

`ExtractionResult`:
- `main_points: list[MainPoint]` com exatamente até 3
- `assertions: list[Assertion]`
- `numeric_data: list[NumericData]`
- `entities: list[Entity]`
- `events: list[Event]`
- `detected_terms: list[str]`
- `pending_terms: list[PendingTerm]`
- `source_complexity: SourceComplexity`

`MainPoint`: `id`, `order`, `title`, `assertion_ids`.
`Assertion`: `id`, `text`, `type`, `role`, `source_span` (texto exato), `variation_declared`.
`NumericData`: `id`, `indicator`, `value`, `unit`, `reference_period`, `source_span`.
`SourceComplexity`: `flesch`, `term_density`, ` word_count`.

### 5.3 Geração texto

`AnalyticalText`:
- `title`
- `subtitle`
- `sections`: introdução, desenvolvimento, análise, conclusão
- `covered_main_points: list[str]`
- `general_impact_markers: list[str]`
- `word_count_total`
- `word_count_by_section`

### 5.4 Carrossel e legenda

`Carousel`:
- `slides`: exatamente 5
- cada slide: `order`, `role`, `title`, `body`, `highlight_data` opcional
`Caption`:
- `opening`
- `short_context`
- `source_block`
- `cta_verb`
- `cta_sentence`
- `institutional_notice` opcional
- `hashtags`

### 5.5 Roteiro

`Script`:
- `scenes`: exatamente 5
- cada cena: `order`, `role`, `start_sec`, `end_sec`, `spoken`, `screen_text`, `visual`, `framing`, `direction_note`
- `total_duration_sec`

### 5.6 Avaliação

`DeterministicEvaluation`:
- `flesch`
- `term_density`
- `grounding_score`
- `numbers_verified`
- `main_points_coverage`
- `beginner_term_window_ok`
- `format_checks`
- `classified_level`
- `source_complexity`
- `passed: bool`
- `failures: list[str]`

`JudgeEvaluation`:
- `rubric_version`
- `judge_model_id`
- `scores` (critério -> nota)
- `justification`
- `text_length`
- `evidence`

## 6. Esquema do banco de dados

### 6.1 Tabelas operacionais

Tabelas obrigatórias:
- `cards`
- `documentos`
- `execucoes`
- `materiais`
- `tentativas`
- `avaliacoes_juiz`
- `decisoes_humanas`
- `termos_pendentes`
- `coletas`
- `eval_execucoes`
- `eval_resultados`

Campos mínimos obrigatórios:
- `cards`: `card_id`, `title`, `description`, `source_type`, `source_name`, `source_url`, `category`, `entry_reason`, `card_date`, `state`, `created_at`.
- `documentos`: `hash`, `card_id`, `origin_type`, `origin_institution`, `origin_title`, `origin_date`, `origin_url`, `language`, `integrity_status`, `partial`, `is_financial`, `technical_term_count`, `word_count`, `raw_text_path`, `created_at`.
- `execucoes`: `execution_id`, `document_hash`, `levels_requested`, `config_hash`, `glossary_version`, `prompt_version`, `model_version`, `threshold_version`, `rubric_version`, `style_version`, `total_tokens`, `total_latency`, `status`, `created_at`.
- `materiais`: `material_id`, `execution_id`, `level`, `format`, `state`, `content_generated`, `content_edited`, `created_at`, `updated_at`.
- `tentativas`: `attempt_id`, `material_id`, `attempt_number`, `content`, `metrics`, `failures`, `rejection_reason`, `tokens`, `latency`, `model_id`, `created_at`.
- `avaliacoes_juiz`: `judge_id`, `attempt_id`, `rubric_version`, `judge_model_id`, `scores`, `justification`, `text_length`, `evidence`, `created_at`.
- `decisoes_humanas`: `decision_id`, `material_id`, `decision`, `note`, `created_at`.
- `termos_pendentes`: `pending_id`, `term`, `proposed_definition`, `source_span`, `source_url`, `status`, `created_at`, `resolved_at`.
- `coletas`: `collection_id`, `source_name`, `started_at`, `finished_at`, `items_count`, `errors`.
- `eval_execucoes`: `eval_id`, `context_hash`, `started_at`, `finished_at`.
- `eval_resultados`: `result_id`, `eval_id`, `test_case`, `metric`, `result`, `metadata`.

### 6.2 Grafo lógico

Tabelas:
- `graph_nodes`
- `graph_edges`

Campos `graph_nodes`:
- `node_id`
- `node_type` (`documento`, `trecho`, `ponto_central`, `afirmacao`, `dado`, `entidade`, `evento`, `card`, `material`, `frase_gerada`, `termo`)
- `properties` (jsonb)
- `created_at`

Campos `graph_edges`:
- `edge_id`
- `from_node_id`
- `to_node_id`
- `relation_type` (`TEM_TRECHO`, `EXTRAIDA_DE`, `SUSTENTA`, `EXTRAIDO_DE`, `SOBRE`, `TRATA_DE`, `ATUALIZA`, `APONTA_PARA`, `MENCIONA`, `TEM_FRASE`, `BASEADA_EM`)
- `properties` (jsonb)
- `created_at`

Profundidade máxima de recursão deve ser configurável antes do commit.

Índices obrigatórios:
- PK em todas as tabelas.
- FK lógicas por UUID.
- Índices em `cards.card_date`, `documentos.created_at`, `execucoes.document_hash`, `graph_edges.from_node_id`, `graph_edges.to_node_id`, `graph_edges.relation_type`.

## 7. Pipeline LangGraph

### 7.1 Estado

`PipelineState` contém:
- `execution_id`
- `document`
- `selected_levels`
- `config_versions`
- `extraction`
- `generated_outputs` por nível e formato
- `attempt_history`
- `deterministic_evaluation`
- `judge_evaluation`
- `human_decision`
- `token_count`
- `errors`

### 7.2 Nós

- `admit`
- `extract`
- `generate`
- `evaluate_deterministic`
- `judge`
- `route`
- `human_validation`
- `export`

### 7.3 Arestas condicionais

- Reprovou nas métricas e tem reescrita sobrando: `generate`.
- Passou nas métricas: `judge`.
- Juiz reprova e tem reescrita sobrando: `generate`.
- Esgotou duas reescritas: `human_validation` com aviso.
- Aprovado: `human_validation`.

### 7.4 Execução

- Níveis rodam em sequência controlada por limitador global de tokens compartilhado.
- Uma saída que não passa em Pydantic é falha da tentativa.
- Estado persistido no PostgreSQL via checkpointer compatível.

## 8. Admissão: comportamento exato

1. **Link:** ler com Playwright, limpar HTML, extrair texto principal.
2. **PDF digital:** extrair texto; se pouco texto, pedir cola de texto.
3. **Texto colado:** coletar origem obrigatória.
4. **Checagens de parcialidade:**
   - tamanho mínimo;
   - texto termina em frase completa;
   - ausência de marcadores de paywall.
   - se falhar: marcar parcial e bloquear geração.
5. **Financeiro (regra determinística):** ≥5 termos distintos do glossário e ≥200 palavras; caso contrário aviso com opção de seguir.
6. **Extração estruturada:** metadado/sinal auxiliar, não veto autônomo.
7. **Origem:**
   - link: instituição, título, data extraídos quando possível;
   - texto: instituição/veículo, título, data, link opcional.
   - sem origem: mostrar “texto enviado pelo usuário”.
8. **Idioma:** detecção; recusar ou avisar se não for português.
9. **Prompt injection:** conteúdo é dado; nunca instrução; saídas estruturadas.

## 9. Extração: comportamento exato

1. Dividir documentos longos por sentença/pragações preservando offsets.
2. Produzir até 3 pontos centrais.
3. Produzir afirmações com tipo e papel.
4. Produzir dados numéricos estruturados.
5. Marcar var variation declarada quando a fonte declarar.
6. Não comparar documentos nem calcular “o que mudou”.
7. Agregar pontos centrais em segunda passagem.
8. Normalizar entidades/eventos pelos apelidos.
9. Ligar cards por evento/responsáveis; se houver dúvida, não ligar.
10. Fato novo em história em andamento cria card novo ligado por `ATUALIZA`.
11. Validar extrator nos documentos de referência.

## 10. Glossário e apelidos: comportamento exato

1. Dois arquivos separados.
2. Formato YAML versionado e validado por Pydantic.
3. Autoria humana.
4. Termo pendente:
   - busca apenas no glossário do BCB e no glossário da B3;
   - se não encontrar, status `sem_definicao`;
   - aprovação exige definição do usuário;
   - resultado da busca é cacheado.
5. Versão do glossário entra em `execucoes`.
6. Edições valem apenas para materiais novos.
7. Cobertura medida pela fração de termos técnicos dos documentos de teste presentes no glossário.

## 11. Geração: comportamento exato

### 11.1 Entrada

O gerador recebe:
- 3 pontos centrais, cada um com afirmações e trecho original;
- dados numéricos;
- entradas do glossário dos termos presentes;
- regras do nível e do formato;
- guia de estilo;
- termos proibidos.
Não recebe documento inteiro nem documentos anteriores.

### 11.2 Regras de fidelidade

Permitido:
- reformular;
- trocar jargão por explicação;
- omitir detalhe secundário;
- reorganizar ordem.

Proibido:
- alterar números, datas ou direção de variação;
- mudar grau de certeza;
- acrescentar afirmações factuais não presentes na fonte;
- omitir algo que muda o sentido;
- comparar documentos.

Analogia:
- apenas sinônimo/explicação de termo técnico, nunca história/narrativa.
- usa explicações aprovadas do glossário.

Impacto prático no Iniciante:
- usar campo `explicacao_impacto`;
- marcador obrigatório `Em geral,`;
- toda frase com marcador deve existir no glossário.

Sem emojis, sem recomendação de compra/venda, sem termos proibidos.

### 11.3 Texto analítico

- Estrutura: título, subtítulo, 4 seções na ordem.
- Pontos centrais cobertos registrados.
- Intertítulos curtos gerados pelo modelo.
- Tamanho: 350-500 palavras para os três níveis.
- Proporção: 15/35/30/20.
- Caixa “Entenda os termos” somente no Iniciante, após conclusão e antes da fonte, por regra.

Checks:
- quatro seções na ordem;
- 3 pontos centrais presentes;
- contagem de palavras total e por seção;
- limites de título/subtítulo/parágrafo;
- todo número/data existe na fonte;
- toda causa/impacto/risco corresponde a afirmação da fonte;
- legibilidade e densidade na faixa do nível;
- termo técnico no Iniciante com explicação em janela curta;
- bloco de fonte igual ao montado por regra;
- sem emojis/termos proibidos/recomendação.

### 11.4 Carrossel e legenda

- 5 slides: gancho, 3 pontos, conclusão.
- Sem slide de CTA.
- Gancho apoia-se em fato/número da fonte, sem exagero.
- Legenda:
  - abertura com ponto central;
  - contexto curto na linguagem do nível;
  - fonte por regra;
  - CTA com verbo da lista;
  - aviso institucional apenas se configurado;
  - hashtags de entidades, se desejado.
- Tamanho máximo 2.000 caracteres.
- Renderização HTML/CSS + Playwright sem LLM.
- PNG por slide + ZIP após aprovação.
- Aviso institucional não é bloqueante; nenhum texto obrigatório confirmado pela Suno.

### 11.5 Roteiro de vídeo

- Instagram Reels, vertical, até 60s.
- 5 cenas.
- Campos recomendados: ordem, papel, tempos, fala escrita/falada, texto na tela, visual, enquadramento, observação.
- Tempos contínuos, sem sobreposição.
- Exportação para pessoa e para IA.
- Prompt por modelo de texto, sem LLM.
- Ferramenta IA gera narração; pronúncia de siglas vem do glossário.
- Texto na tela adicionado na edição.

### 11.6 Níveis

- Iniciante: zero jargão sem analogia cotidiana, foco no impacto prático.
- Intermediário: vocabulário padrão, alocação e tendências.
- Avançado: jargão pleno, foco analítico e metodológico.
- Usuário escolhe níveis; suíte offline gera os três para matriz de confusão.

## 12. Avaliação híbrida

Métricas determinísticas:
- Flesch com coeficientes adaptados ao português.
- Domain Term Density Score.
- Grounding Checker.
- Número e data existem na fonte.
- Cobertura dos 3 pontos centrais.
- Termo técnico no Iniciante com explicação em janela curta.
- Checks de formato.

RAG:
- Sem recuperação de documentos anteriores na geração.
- Recuperação por percurso no grafo e matching exato por números, entidades e termos; sem embedding vetorial.

Eval:
- runtime + offline.
- Registrar contexto completo: versões, modelo, limiares, rubrica, guia.
- Cache de resultados.

Juiz:
- complemento, nunca árbitro único.
- roda apenas após métricas determinísticas;
- modelo diferente do gerador;
- registrar rubrica, modelo, notas, justificativa, tamanho do texto, evidência.
- decisões humanas calibram concordância, mas não alteram configuração automaticamente.

Limiares:
- Flesch: Iniciante ≥55, Intermediário 40-55, Avançado ≤40.
- Densidade: Iniciante ≤3, Intermediário 3-8, Avançado ≥8.
- Fonte pouco técnica: registrar complexidade; aceitar `indistinto` quando justificado.

Reflexão:
- 2 reescritas.
- se esgotar, seguir para validação humana com aviso.

## 13. Validação humana

- Mesma pessoa que escolheu o card valida.
- Tela mostra texto, scores, trechos, tipo de fonte, complexidade, versão do glossário, termos pendentes.
- Ações: aprovar, editar, rejeitar.
- Edição reavalia deterministicamente e preserva original.
- Exportações apenas após aprovação.
- Termos pendentes bloqueiam aprovação.

## 14. Dashboard, relatório e consultas

Obrigatórios:
- matriz de 9 saídas com células vazias e botão de gerar;
- rastreabilidade de fonte até trecho exato;
- pontuações por nível;
- cota de tokens do dia.
- relatório experimental: metodologia, matriz de confusão, trade-offs, reprodutibilidade.

Consultas D1-D12 e R1-R15 devem ser implementadas conforme arquitetura:
- 6 percurso puro;
- 4 mistas;
- 17 agregação/filtro.

Nenhum cálculo de “o que mudou” entre documentos pode ser implementado.

## 15. Estado, interface e exportação

- Interface Streamlit.
- Cards: título, descrição, fonte, tipo de fonte, motivo de entrada.
- Entrada manual: link, texto colado, PDF digital.
- Níveis escolhidos no clique; todos marcados por padrão; estimativa de tempo antes de confirmar.
- Estado visível: na fila, extraindo, gerando, avaliando, aguardando revisão.
- Uma tarefa ativa por card.
- Reaproveitamento de resultados do mesmo conteúdo.
- Cota de tokens restante visível.
- Erros com toast e causa real.
- Glossário editável com validação e versionamento.
- Exportação: artigo Markdown/HTML, PNGs, ZIP, roteiro para pessoa e prompt para IA.

## 16. Coleta e ranking

- Fontes primárias priorizadas: BCB, CVM, B3, IBGE.
- Forbes somente manchetes, link, sem extração.
- Sem coleta automática de releases de RI.
- Varredura diária às 8h em fuso de Brasília + botão manual.
- Ranking determinístico com pontuação transparente.
- Categorias: acabou de acontecer; em andamento.
- Sem categoria “vem aí”.
- Cards de mesma história unificados apontando para primário.
- Motivo de entrada mostrado.
- Título/fonte do metadado, sem reescrita.
- Descrição por extração ou LLM apenas nos cards escolhidos.
- Histórico de até 7 dias.
- Limite diário padrão 8, configurável, piso por medição.

Fallback de coleta:
- fonte não coletável fica inativa;
- usar acervo local de documentos reais;
- usar botão manual;
- não buscar fontes/APIs alternativas não verificadas.

## 17. Infraestrutura

- Docker local, sem hospedagem no escopo.
- Compose com:
  - app (interface/API)
  - PostgreSQL com volume persistente
  - coletor/agendador
  - renderizador Playwright
  - `.env` e `.env.example`
- Fuso de Brasília para agendamento.
- Cache, fila de tokens, retry com espera crescente.
- Demonstração com resultados pré-gerados e uma geração ao vivo curta.

## 18. Plano de validação

- 12-15 dias de referência, espalhados por semanas e tipos.
- ~10 dias para ajustar pesos, 5 para medir.
- Eventos agendados do Copom e IBGE como checagem objetiva.
- Calibração do limite de cards por recall e cotovelo.
- Pares de notícias para acurácia da ligação.
- Extrator validado manualmente.
- Fatia fina ponta a ponta com um documento real.
- Teste de qualidade de um nível completo em português.
- Concordância juiz x decisões humanas.
- Limitação: único avaliador.
- Reprodutibilidade com versão congelada.

## 19. Critérios de aceitação (seção 14)

Implementar testes/checklist para:
- card abre seleção de níveis;
- texto colado e PDF digital entram;
- link inacessível mostra mensagem definida;
- conteúdo parcial bloqueado com toast;
- extração grava 3 pontos, afirmações, números e trechos;
- geração produz 3 formatos em JSON válido;
- fidelidade: nenhum número/data fora da fonte, nenhum “Em geral,” fora do glossário, sem emojis;
- métricas determinísticas gravadas;
- juiz com modelo diferente do gerador;
- nível classificado registrado;
- loop de reflexão demonstrado;
- validação humana: aprovar/editar/rejeitar, termos pendentes bloqueiam, exportações após aprovação;
- dashboard: matriz 9 saídas, proveniência, scores, cota;
- exportação: Markdown/HTML, PNGs 1080x1350 com linha correta, roteiro pessoa e prompt IA;
- coleta: manual e agendamento gravam cards conforme regras;
- reprodutibilidade: subida comum comando, testes simulados, versão do glossário;
- suíte offline: matriz de confusão, custo e latência.

## 20. Detalhamento dos blocos

### Bloco 0 — Fundações
Arquivos: seção 3.  
Dados: respostas LLM gravadas, glossário mínimo, `.env.example`.  
Implementar estrutura, Compose, LLM client com modos, cache, limitador, migração vazia.  
Testes: modo simulado, subida limpa.  
Gate: aprovação.

### Bloco 1 — Persistência
Arquivos: `src/persistence/*`, migrações, `src/pipeline/checkpointer.py`.  
Dados: schema e nós/arestas.  
Implementar tabelas, índices, repositories, consultas D2/D3/D9/D10/D11/R12, checkpointer.  
Testes: CRUD grafo, roundtrip, benchmark.  
Gate: aprovação.

### Bloco 2 — Admissão
Arquivos: `src/admission/*`.  
Dados: links, textos, PDFs, glossários.  
Implementar fetch, clean, partial checks, classificação, origem, idioma.  
Testes: link inacessível, parcial, não financeiro, PDF pobre.  
Gate: aprovação.

### Bloco 3 — Extração
Arquivos: `src/extraction/*`, `src/glossary/*`.  
Dados: documentos reais, glossário, apelidos.  
Implementar chunking, extração, numéricos, entidades/eventos, apelidos, termos pendentes.  
Testes: 3 pontos, números, offsets, termo pendente.  
Gate: aprovação.

### Bloco 4 — Texto analítico
Arquivos: `src/generation/text_analytical.py`, métricas, pipeline.  
Dados: glossário, estilo, termos proibidos, estrutura.  
Implementar geração, métricas, loop até 2.  
Testes: schema, métricas, reflexão.  
Gate: aprovação.

### Bloco 5 — Carrossel, legenda, roteiro
Arquivos: `src/generation/carousel.py`, `script.py`, `caption.py`, render.  
Dados: tokens visuais, enquadramentos.  
Implementar formatos, checks, render PNG.  
Testes: slides/cenas, tempos, posição linha, dimensões.  
Gate: aprovação.

### Bloco 6 — Juiz e custo
Arquivos: `src/evaluation/judge.py`, `concordance.py`, repositories.  
Dados: rubrica, versões.  
Implementar juiz em textos aprovados, concordância, custo/latência.  
Testes: schema, modelo diferente, cache.  
Gate: aprovação.

### Bloco 7 — Validação humana e exportação
Arquivos: `src/app/validation_screen.py`, `src/export/*`.  
Dados: materiais avaliados, termos pendentes.  
Implementar pausa, edição, rejeição, exportações.  
Testes: aprovação, edição, bloqueio termos.  
Gate: aprovação.

### Bloco 8 — Interface e dashboard
Arquivos: `src/app/*`.  
Dados: cards, matriz, cota, grafo.  
Implementar cards, seleção, status, dashboard, glossário.  
Testes: subida, fluxo, consultas.  
Gate: aprovação.

### Bloco 9 — Coleta
Arquivos: `src/collection/*`.  
Dados: fontes, dias referência.  
Implementar agendador, fetchers, ranker, dedup, card builder.  
Testes: agendamento, manual, ranking.  
Gate: aprovação.

### Bloco 10 — Suíte offline e aceitação final
Arquivos: `tests/offline/*`, scripts, relatório.  
Dados: 12-15 dias, docs referência.  
Implementar suíte, relatório, subida limpa, demonstração.  
Gate final: aprovação e vídeo.

## 21. Regra de parada

Se o usuário não aprovar, ajustar o bloco atual. Nenhum bloco inicia sem aprovação explícita do anterior. Nenhum dado ou interface deve ser inferido durante a implementação; ausência de especificação deve ser apontada antes da execução.