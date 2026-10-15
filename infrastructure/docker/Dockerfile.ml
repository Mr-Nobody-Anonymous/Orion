FROM python:3.10-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt pyproject.toml ./
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

COPY src/ ./src/
COPY configs/ ./configs/
COPY start.py ./

ENV PYTHONPATH=/app/src:/app
ENV ORION_ENV=production

CMD ["python", "start.py", "--check"]
