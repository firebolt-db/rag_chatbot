FROM python:3.12-slim-bookworm

RUN apt-get update && apt-get install -y \
    curl \
    git \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

RUN adduser \
    --system \
    --no-create-home \
    --group \
    rag_user

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

RUN curl -fsSL https://ollama.com/install.sh | sh

COPY . .

RUN chown -R rag_user:rag_user /app

USER rag_user

EXPOSE 5000

ENV PYTHONPATH=/app
ENV OLLAMA_HOST=0.0.0.0:11434

CMD ["sh", "-c", "ollama serve & sleep 10 && ollama pull llama3.1 && ollama pull nomic-embed-text && python web_server.py"]
