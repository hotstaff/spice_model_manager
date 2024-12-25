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

# supervisordの設定ファイルをコピー
COPY supervisord.conf /etc/supervisor/conf.d/supervisord.conf

# supervisordを起動
CMD ["supervisord", "-n"]
