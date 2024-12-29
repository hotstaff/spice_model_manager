

# LTspice Model Manager and Simulation Server

LTspiceデバイスモデルの管理とシミュレーションを行うツールです。
ウェブインターフェースを通じてモデルを管理し、シミュレーションサーバーを利用して回路解析を行えます。

## 特徴

モデル管理: LTspiceモデルの追加、編集、削除をウェブインターフェースで操作可能。
シミュレーションツール: JFETシミュレーションやタスク管理をサポート。
クラウドデプロイ: Google Cloud Runでのデプロイを想定。
多言語対応: インターフェースは英語と日本語に対応。

## ディレクトリ構成

app.py: Google Cloud Run用のメインアプリケーション。
client/: モデル管理ロジックを含む。
    spice_model_manager.py: モデル管理スクリプト(GUI)。
    spice_model_parser.py: LTspiceモデルの解析モジュール。
models/: データベースモデル関連。
    db_model.py: データベースのモデル定義。
simulation/: シミュレーションサーバー関連コード。
    jfet.py: JFETシミュレーションロジック。
    lt_jfet.py: LTspice用JFETロジック。(テスト用)
    redis_worker.py: タスク管理用スクリプト。(シミュレーションサーバーのワーカー)
    net/jfet_dc.net: サンプルネットリストファイル。(JFETテスト用の回路テンプレート)
templates/: ウェブインターフェース用HTMLテンプレート。
Dockerfile: メインアプリ用のDockerfile。
simulation/Dockerfile: シミュレーションサーバー用のDockerfile。
requirements.txt: 依存ライブラリリスト。

## 動作環境

Python 3.8以上
必要ライブラリ:
    メインアプリ用: requirements.txtを参照。
    シミュレーションサーバー用: simulation/requirements.txtを参照。

## インストール手順:

リポジトリをクローン: 


    git clone https://github.com/your-repo-name/ltspice-model-manager.git
    cd ltspice-model-manager


## 使用方法

### デプロイ方法:

Google Cloud Run: 提供されているDockerfileを使用してコンテナ化し、デプロイ可能。
Dockerでローカル実行:

    docker build -t ltspice-app .
    docker run -p 8080:8080 ltspice-app

## 今後の予定:

モデル検索機能の追加。
シミュレーション結果の可視化機能の強化。
エクスポートオプションの拡張 (JSON, XMLなど)。