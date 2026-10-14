# Relatório experimental - Case Suno Content

## Metodologia
- Execução local em modo simulado.
- Reexecução sem chaves externas e sem dependência de rede.

## Resumo da suíte offline
- Comando: `python -m pytest tests/offline -q`
- Resultado: `7 passed in 0.11s`

## Matriz de confusão
- Valores agregados pelos testes de `src/evaluation/offline_metrics.py`.

## Reprodutibilidade
- Versão congelada via arquivos de configuração e testes simulados.
- Subida limpa validada por Docker e migração.

## Saída bruta
```
.......                                                                  [100%]
7 passed in 0.11s


```
