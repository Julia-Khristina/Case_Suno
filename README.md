# Case_Suno

Pipeline de adaptação de documentos financeiros para 3 níveis (Iniciante, Intermediário, Avançado) em 3 formatos (Texto Analítico, Carrossel, Roteiro de Vídeo), com avaliador híbrido.

## Subida rápida

```bash
cp .env.example .env
docker compose up --build
```

A interface ficará disponível em `http://localhost:8501`.

## Testes

```bash
python -m pytest -q
```

Metodologia, arquitetura e plano de implementação estão em `documents/`.