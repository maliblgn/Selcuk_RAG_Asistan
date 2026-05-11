FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PIP_NO_CACHE_DIR=1
ENV STREAMLIT_SERVER_HEADLESS=true
ENV STREAMLIT_SERVER_PORT=7860
ENV STREAMLIT_SERVER_ADDRESS=0.0.0.0
ENV FLASHRANK_ENABLED=false
ENV METADATA_RERANK_ENABLED=true
ENV MULTI_QUERY_ENABLED=true
ENV MULTI_QUERY_LEGAL_SAFE_MODE=true
ENV METADATA_RERANK_CANDIDATE_K=25
ENV FINAL_CONTEXT_DOCS=4
ENV MAX_CONTEXT_CHARS=4000

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 7860

CMD ["streamlit", "run", "app.py", "--server.port=7860", "--server.address=0.0.0.0"]
