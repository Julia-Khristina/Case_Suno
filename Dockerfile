FROM python:3.11-slim

WORKDIR /app
ENV PYTHONPATH=/app

COPY requirements.txt ./
# Sem "|| true": se uma dependência não instalar, o build falha aqui, e não depois na tela
# (ex.: ModuleNotFoundError: matplotlib ao gerar materiais).
RUN pip install --no-cache-dir -r requirements.txt
RUN python -m playwright install --with-deps chromium || true

# Instalar dependencias do projeto quando houver.
COPY . .

CMD ["streamlit", "run", "src/app/main.py", "--server.address=0.0.0.0", "--server.port=8501"]