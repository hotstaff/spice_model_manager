FROM ubuntu:22.04

# ベースイメージの更新と基本ツールのインストール
RUN apt-get update && apt-get install -y \
    software-properties-common \
    wget \
    unzip \
    curl \
    python3 \
    python3-pip \
    python3-setuptools \
    redis-tools \
    xvfb && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

# Wineのリポジトリを追加してインストール
RUN dpkg --add-architecture i386 && apt-get update && apt-get install -y \
    wine64 \
    wine32 && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

# Python依存ライブラリのインストール
COPY requirements.txt /app/requirements.txt
RUN pip3 install -r /app/requirements.txt

# .wineフォルダをコンテナにコピー
COPY .wine /root/.wine

# 作業ディレクトリを設定
WORKDIR /app

# 必要なPythonスクリプトをコンテナにコピー
COPY redis_worker.py /app/redis_worker.py

# REDISHOST環境変数を指定可能にする
ENV REDISHOST=localhost

# redis_worker.pyを実行
CMD ["python3", "redis_worker.py"]
