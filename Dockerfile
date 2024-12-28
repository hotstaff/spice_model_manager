# ビルドステージ
FROM python:3.9-slim AS build

WORKDIR /app
COPY requirements.txt .
RUN pip install --upgrade pip && pip install --no-cache-dir -r requirements.txt

# 実行ステージ
FROM python:3.9-slim

WORKDIR /app
COPY --from=build /app /app

# 必要なファイルのみコピー
COPY . .

CMD ["sh", "-c", "gunicorn app:app --bind 0.0.0.0:$PORT & celery -A tasks.celery worker --loglevel=info --concurrency=1 & wait"]
