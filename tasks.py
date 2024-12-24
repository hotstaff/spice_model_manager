import os
from celery import Celery

# 環境変数からREDISHOSTを取得
redis_host = os.getenv('REDISHOST', 'localhost')

# Celeryインスタンスを作成
celery = Celery(
    __name__,  # アプリケーション名（適宜変更）
    broker=f'redis://{redis_host}:6379/1'  # RedisのURL、DB番号は1に設定
)

# 非同期タスクの例
@celery.task
def run_simulation(data_id):

    return f"Simulation for data_id {data_id} completed!"
