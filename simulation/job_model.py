import os
import json
from datetime import datetime
from redis import Redis

class JobModel:
    def __init__(self, redis_host="localhost", redis_port=6379, redis_db=0):
        self.redis = Redis(host=redis_host, port=redis_port, db=redis_db, decode_responses=False)
        self.REDIS_JOB_PREFIX = "job:"
        self.REDIS_RESULT_PREFIX = "result:"
        self.MAX_JOBS = 25
        self.SIMULATION_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
        os.makedirs(self.SIMULATION_DIR, exist_ok=True)

    def get_job_meta(self, job_id):
        """ジョブのメタデータを取得"""
        job_key = f"{self.REDIS_JOB_PREFIX}{job_id}:meta"
        job_data = self.redis.get(job_key)
        if job_data:
            return json.loads(job_data.decode('utf-8'))
        return None

    def get_job_file(self, job_id):
        """ジョブのファイルデータを取得"""
        file_key = f"{self.REDIS_JOB_PREFIX}{job_id}:file"
        return self.redis.get(file_key)

    def get_job_result(self, job_id):
        """ジョブの結果を取得"""
        result_key = f"{self.REDIS_RESULT_PREFIX}{job_id}"
        return self.redis.get(result_key)

    def fetch_stream_message(self, stream_name, job_id, timeout=30):
        """
        Redis Streamsから特定のジョブIDのメッセージを取得。

        Args:
            stream_name (str): ストリーム名。
            job_id (str): ジョブID。
            timeout (int): タイムアウト秒数。

        Returns:
            bool: メッセージが見つかった場合True、タイムアウトの場合False。
        """
        start_time = datetime.now()
        while (datetime.now() - start_time).seconds < timeout:
            print("hi", job_id)
            messages = self.redis.xread({stream_name: ">"}, block=1000, count=1)
            if messages:
                for stream, entries in messages:
                    for _, data in entries:
                        print(f"Received message: {data}")  # 受け取ったメッセージを表示
                        if data[b"job_id"].decode('utf-8') == job_id:
                            return True
        return False

    def get_job_result_with_notification(self, job_id, timeout=30):
        """
        Redis Streamsを使用してジョブの結果を取得。
        タイムアウト期間内に通知がない場合は、直接Redisキーを確認。

        Args:
            job_id (str): ジョブID。
            timeout (int): タイムアウト秒数。

        Returns:
            bytes: ジョブ結果のバイナリデータ。
            None: 結果が存在しない場合。
        """
        result_key = f"{self.REDIS_RESULT_PREFIX}{job_id}"
        stream_name = "job_notifications"

        # Redis Streamsからメッセージを取得
        if self.fetch_stream_message(stream_name, job_id, timeout):
            # メッセージが見つかった場合、結果を取得
            result = self.redis.get(result_key)
            if result:
                return result

        # タイムアウト後も結果がない場合Noneを返す
        return None

    def generate_job_id_from_timestamp(self, base_name):
        """ジョブIDを生成"""
        job_prefix = self.redis.incr("job_id_counter")
        job_prefix_padded = str(job_prefix).zfill(5)
        timestamp = datetime.now().strftime("%b_%d_%H%M")
        return f"{job_prefix_padded}_{base_name}_{timestamp}"

    def create_job(self, uploaded_file_path):
        """ジョブを作成（Redisパイプラインを使用）"""
        base_name = os.path.splitext(os.path.basename(uploaded_file_path))[0]
        job_id = self.generate_job_id_from_timestamp(base_name)

        # アップロードされたファイルを読み込む
        with open(uploaded_file_path, "rb") as file:
            binary_data = file.read()

        # ジョブのメタデータ
        job_data = {
            "status": "pending",
            "error": None,
            "file_path": os.path.basename(uploaded_file_path),
        }

        # Redisパイプラインで一括保存
        pipeline = self.redis.pipeline()
        pipeline.set(f"{self.REDIS_JOB_PREFIX}{job_id}:meta", json.dumps(job_data))
        pipeline.set(f"{self.REDIS_JOB_PREFIX}{job_id}:file", binary_data)
        pipeline.rpush("job_queue", job_id)
        pipeline.execute()

        # 古いジョブを削除
        all_jobs = self.redis.keys(f"{self.REDIS_JOB_PREFIX}*:meta")
        all_jobs_str = [key.decode('utf-8') for key in all_jobs]
        all_jobs_str.sort()

        if len(all_jobs_str) > self.MAX_JOBS:
            oldest_job_key = all_jobs_str[0]
            pipeline = self.redis.pipeline()
            pipeline.delete(oldest_job_key.replace(":meta", ":file"))
            pipeline.delete(oldest_job_key)
            pipeline.execute()

        return job_id

    def get_all_jobs(self):
        """すべてのジョブをRedisから取得（MGET使用）"""
        all_jobs = {}
        job_keys = self.redis.keys(f"{self.REDIS_JOB_PREFIX}*:meta")
        
        if not job_keys:
            return all_jobs
        
        # Redisから一度にデータを取得
        job_values = self.redis.mget(job_keys)
        
        for key, value in zip(job_keys, job_values):
            if value:
                job_key_str = key.decode('utf-8')
                job_id = job_key_str.replace(self.REDIS_JOB_PREFIX, "").replace(":meta", "")
                job_data = json.loads(value.decode('utf-8'))
                all_jobs[job_id] = job_data
        
        return all_jobs

    def clear_all_jobs(self):
        """Redisからすべてのジョブを削除"""
        all_jobs = self.redis.keys(f"{self.REDIS_JOB_PREFIX}*:meta")
        if all_jobs:
            for job_key in all_jobs:
                job_key_str = job_key.decode('utf-8')
                self.redis.delete(job_key_str)  # メタデータ削除
                self.redis.delete(job_key_str.replace(":meta", ":file"))  # ファイルデータ削除
        return "Redisのジョブをすべて削除しました。"
