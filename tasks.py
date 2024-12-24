import os
from celery import Celery
from app import app  # Flaskアプリケーションのインスタンスをインポート

# 環境変数からREDISHOSTを取得
redis_host = os.getenv('REDISHOST', 'localhost')

# Celeryインスタンスを作成
celery = Celery(
    __name__,  # アプリケーション名（適宜変更）
    broker=f'redis://{redis_host}:6379/1'  # RedisのURL、DB番号は1に設定
)

# Flaskの設定をCeleryに渡す
celery.conf.update(app.config)

# 非同期タスクの例
@celery.task
def run_simulation(data_id):
    with app.app_context():  # Flaskアプリケーションのコンテキストを使用
        # シミュレーション処理をここに記述
        print(f"Running simulation for data_id: {data_id}")
        
        # シミュレーション結果をデータベースに保存する処理など
        # 例: db.session.add(simulation_result); db.session.commit()
        # 実際のシミュレーション処理はここで実装
        return f"Simulation for data_id {data_id} completed!"
