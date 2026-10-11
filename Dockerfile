FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt || true

# Instalar dependencias do projeto quando houver.
COPY . .

CMD ["streamlit", "run", "src/app/main.py", "--server.address=0.0.0.0", "--server.port=8501"]