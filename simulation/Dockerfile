# ベースイメージ
FROM python:3.9-slim

# 作業ディレクトリを作成
WORKDIR /app

# 必要なパッケージのインストール
RUN apt-get update && apt-get install -y --no-install-recommends \
    wine64 \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Python依存関係のインストール
COPY requirements.txt .
RUN pip install --upgrade pip && pip install --no-cache-dir -r requirements.txt

# アプリケーションのコピー
COPY . .

# サービスを開始するためのコマンド
CMD ["sh", "-c", "gunicorn api:app --bind 0.0.0.0:$PORT"]

