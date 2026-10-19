# Resultados experimentais

Gerado por `python scripts/relatorio_experimental.py` em 17/10/2026 22:02. Não edite à mão: rode o script de novo.

## 1. Matriz de confusão de níveis: benchmark escrito à mão

Saídas boas de cada nível e as saídas ruins que trocam o nível (Iniciante com jargão sem explicação; texto Iniciante entregue como Avançado).

| Pedido \ Classificado | Iniciante | Intermediário | Avançado | Indistinto | Recall |
|---|---|---|---|---|---|
| **Iniciante** | 1 | 0 | 0 | 1 | 0.50 |
| **Intermediário** | 0 | 1 | 0 | 0 | 1.00 |
| **Avançado** | 0 | 0 | 1 | 1 | 0.50 |

n = 5 · acerto = 60% · indistinto = 2 · precisão por nível: Iniciante 1.00, Intermediário 1.00, Avançado 1.00

| Caso | Esperado | Classificado | Flesch PT-BR | Densidade /100 |
|---|---|---|---|---|
| g1_iniciante | Iniciante | Iniciante | 73.6 | 2.71 |
| g2_intermediario | Intermediário | Intermediário | 44.6 | 5.85 |
| g3_avancado | Avançado | Avançado | 32.3 | 8.51 |
| b08_iniciante_jargao_sem_explicacao | Iniciante | Indistinto | 65.8 | 5.16 |
| b09_avancado_sem_jargao | Avançado | Indistinto | 73.9 | 3.21 |

## 2. Matriz de confusão de níveis: saídas reais do modelo

1 execução(ões) gravada(s), 27 tentativas (3.0 por material).

### Todas as tentativas, nível gravado na execução

| Pedido \ Classificado | Iniciante | Intermediário | Avançado | Indistinto | Recall |
|---|---|---|---|---|---|
| **Iniciante** | 3 | 0 | 0 | 6 | 0.33 |
| **Intermediário** | 1 | 0 | 0 | 8 | 0.00 |
| **Avançado** | 3 | 0 | 0 | 6 | 0.00 |

n = 27 · acerto = 11% · indistinto = 20 · precisão por nível: Iniciante 0.43, Intermediário —, Avançado —

### Todas as tentativas, reclassificadas com o código atual

| Pedido \ Classificado | Iniciante | Intermediário | Avançado | Indistinto | Recall |
|---|---|---|---|---|---|
| **Iniciante** | 3 | 0 | 0 | 6 | 0.33 |
| **Intermediário** | 1 | 0 | 0 | 8 | 0.00 |
| **Avançado** | 3 | 0 | 0 | 6 | 0.00 |

n = 27 · acerto = 11% · indistinto = 20 · precisão por nível: Iniciante 0.43, Intermediário —, Avançado —

### Versão final de cada material (a que vai para revisão)

| Pedido \ Classificado | Iniciante | Intermediário | Avançado | Indistinto | Recall |
|---|---|---|---|---|---|
| **Iniciante** | 1 | 0 | 0 | 2 | 0.33 |
| **Intermediário** | 0 | 0 | 0 | 3 | 0.00 |
| **Avançado** | 0 | 0 | 0 | 3 | 0.00 |

n = 9 · acerto = 11% · indistinto = 8 · precisão por nível: Iniciante 1.00, Intermediário —, Avançado —

Status final dos materiais: reprovado_nas_metricas: 9

### Por que as tentativas reprovaram (falhas das métricas determinísticas)

| Falha | Tentativas |
|---|---|
| densidade_fora_da_faixa | 17 |
| legibilidade_fora_da_faixa | 15 |
| numero_ou_data_sem_origem | 13 |
| trigramas_repetidos | 7 |
| variacao_nao_declarada_pela_fonte | 7 |
| frase_longa_no_roteiro | 5 |
| frases_sem_respaldo_na_fonte | 5 |
| tamanho_fora_do_intervalo | 5 |
| slides_de_corpo_sem_um_ponto_cada | 5 |
| emoji_encontrado | 3 |
| saida_invalida_do_modelo | 2 |
| titulo_longo | 1 |

## 3. Custo e latência medidos

| Etapa | Chamadas | Tokens | Tokens por chamada | Latência média (s) |
|---|---|---|---|---|
| texto_analitico | 9 | 32009 | 3557 | 1.39 |
| carrossel | 9 | 30350 | 3372 | 1.47 |
| roteiro_video | 9 | 34109 | 3790 | 1.99 |
| nivel:iniciante | 9 | 31348 | 3483 | 1.41 |
| nivel:intermediario | 9 | 32750 | 3639 | 1.8 |
| nivel:avancado | 9 | 32370 | 3597 | 1.65 |
| geracao | 27 | 96468 | 3573 | 1.62 |
| juiz | 0 | 0 | — | — |

| Execução | Documento | Tokens totais | Extração (estimada) | Latência somada (s) | Modelos |
|---|---|---|---|---|---|
| 2026-10-17T14:47 | ‘Prospera MEI’ tem saldo positivo, mas acende aler | 107371 | 10903 | 49.6 | openai/gpt-oss-20b|openai/gpt-oss-120b |
