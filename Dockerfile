# 基盤となるPythonイメージを指定
FROM python:3.9-slim

# 作業ディレクトリを作成
WORKDIR /app

# 必要なパッケージのインストール
RUN apt-get update && apt-get install -y ngspice

# Python依存関係をインストール
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# アプリケーションのコピー
COPY . .

# Gunicornを使ってアプリケーションを起動
CMD ["gunicorn", "app:app", "--bind", "0.0.0.0:$PORT"]

