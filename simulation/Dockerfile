# ベースイメージ
FROM python:3.9-slim

# 作業ディレクトリを作成
WORKDIR /app

# 32ビットアーキテクチャを追加
RUN dpkg --add-architecture i386

# 必要なパッケージのインストール
RUN apt-get update && apt-get install -y --no-install-recommends \
    wine64 \
    wine32 \
    x11-utils \
    xvfb \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Python依存関係のインストール
COPY requirements.txt .
RUN pip install --upgrade pip && pip install --no-cache-dir -r requirements.txt

# アプリケーションのコピー
COPY . .

# Xvfb仮想ディスプレイを起動し、WineでLTspiceを実行
CMD ["sh", "-c", "Xvfb :0 -screen 0 1024x768x16 & export DISPLAY=:0 && gunicorn api:app --bind 0.0.0.0:$PORT"]
