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
    xvfb \
    tar && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

# Wineのリポジトリを追加してインストール
RUN dpkg --add-architecture i386 && apt-get update && apt-get install -y \
    wine64 \
    wine32 && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

# Python依存ライブラリのインストール
COPY requirements.txt /app/requirements.txt
RUN pip3 install -r /app/requirements.txt

# wine_and_ltspice_backup.tar.gzをコンテナにコピー
COPY wine_and_ltspice_backup.tar.gz /app/wine_and_ltspice_backup.tar.gz

# wine_and_ltspice_backup.tar.gzを解凍して.wineディレクトリに展開
RUN tar -xzvf /app/wine_and_ltspice_backup.tar.gz -C /root && \
    chown -R root:root /root/.wine && \
    rm /app/wine_and_ltspice_backup.tar.gz

# 作業ディレクトリを設定
WORKDIR /app

# 必要なPythonスクリプトをコンテナにコピー
COPY redis_worker.py /app/redis_worker.py

# REDISHOST環境変数を指定可能にする
ENV REDISHOST=localhost

# Xvfbを起動してDISPLAY環境変数を設定する
ENTRYPOINT ["/bin/bash", "-c", "Xvfb :0 -screen 0 1024x768x16 & export DISPLAY=:0 && python3 redis_worker.py"]
