# ビルドステージ
FROM python:3.9-slim AS build

WORKDIR /app

# 依存関係ファイルをコピーしてインストール
COPY requirements.txt .
RUN pip install --upgrade pip && pip install --no-cache-dir -r requirements.txt

# 実行ステージ
FROM gcr.io/distroless/python3

WORKDIR /app

# ビルドステージから必要なファイルをコピー
COPY --from=build /app /app

# アプリケーションのソースコードをコピー
COPY . .

# 起動
CMD ["gunicorn", "app:app", "--bind", "0.0.0.0:$PORT", "&", "celery", "-A", "tasks.celery", "worker", "--loglevel=info", "--concurrency=1", "&", "wait"]
