FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8000

WORKDIR /app

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        build-essential \
        gcc \
        g++ \
        make \
        curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
RUN pip install --no-cache-dir cryptography==42.0.8 pyOpenSSL==24.0.0 urllib3==1.26.18 && \
    pip install --no-cache-dir boto3 botocore && \
    pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

CMD python -m uvicorn main:app --host 0.0.0.0 --port ${PORT}
