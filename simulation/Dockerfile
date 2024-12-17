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
    tar \
    supervisor && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

# Wineのリポジトリを追加してインストール
RUN dpkg --add-architecture i386 && apt-get update && apt-get install -y \
    wine64 \
    wine32 && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

# ユーザー 'spice' を追加し、ホームディレクトリを作成
RUN useradd -m -s /bin/bash spice

# Python依存ライブラリのインストール
COPY requirements.txt /app/requirements.txt
RUN pip3 install -r /app/requirements.txt

# wine_and_ltspice_backup.tar.gzをコンテナにコピー
COPY wine_and_ltspice_backup.tar.gz /app/wine_and_ltspice_backup.tar.gz

# wine_and_ltspice_backup.tar.gzを解凍して 'spice' ユーザーのホームディレクトリに展開
RUN tar -xzvf /app/wine_and_ltspice_backup.tar.gz -C /home/spice && \
    chown -R spice:spice /home/spice/.wine && \
    chown -R spice:spice /home/spice/LTspiceXVII && \
    rm /app/wine_and_ltspice_backup.tar.gz

# supervisordの設定ファイルをコピー
COPY supervisord.conf /etc/supervisor/conf.d/supervisord.conf

# 作業ディレクトリを設定
WORKDIR /app

# 必要なPythonスクリプトをコンテナにコピー
COPY redis_worker.py /app/redis_worker.py
COPY app.py /app/app.py

# REDISHOST環境変数を指定可能にする
ENV REDISHOST=localhost

# ユーザーを 'spice' に切り替え
USER spice

# supervisordをエントリポイントとして使用
ENTRYPOINT ["supervisord", "-c", "/etc/supervisor/conf.d/supervisord.conf"]
