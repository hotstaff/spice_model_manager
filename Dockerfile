# 基盤となるPythonイメージを指定
FROM python:3.9-slim

# 作業ディレクトリを作成
WORKDIR /app

# 必要なパッケージのインストール
RUN apt-get update && apt-get install -y supervisor && rm -rf /var/lib/apt/lists/*

# Python依存関係をインストール
COPY requirements.txt .
RUN pip install --upgrade pip && pip install --no-cache-dir -r requirements.txt

# アプリケーションのコピー
COPY . .

# 起動
CMD ["sh", "-c", "gunicorn app:app --bind 0.0.0.0:$PORT & celery -A tasks.celery worker --loglevel=info"]


