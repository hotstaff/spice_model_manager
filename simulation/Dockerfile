# ベースイメージを指定 (軽量なDebianを使用)
FROM debian:bullseye-slim

# 作業ディレクトリを設定
WORKDIR /app

# 必要なパッケージをインストール
RUN apt-get update && apt-get install -y --no-install-recommends \
    wine \
    python3 \
    python3-pip \
    && rm -rf /var/lib/apt/lists/*

# LTspice環境をホストからコピー (事前にインストール済みのフォルダ構成を使用)
COPY ~/.wine /root/.wine

# Python依存関係をインストール
COPY requirements.txt .
RUN pip3 install --no-cache-dir -r requirements.txt

# アプリケーションのコピー
COPY . .

# Flask APIサーバーを起動
CMD ["gunicorn", "-w", "2", "-b", "0.0.0.0:8000", "api:app"]