# 基盤となるPythonイメージを指定
FROM python:3.9-alpine

RUN apk add --no-cache gcc libc-dev

# 作業ディレクトリを作成
WORKDIR /app

# 依存関係ファイルをコピーしてインストール
COPY requirements.txt .
RUN pip install --upgrade pip && pip install --no-cache-dir -r requirements.txt

# アプリケーションのソースコードをコピー
COPY . .

# 起動
CMD ["sh", "-c", "gunicorn app:app --bind 0.0.0.0:$PORT & celery -A tasks.celery worker --loglevel=info --concurrency=1 & wait"]
