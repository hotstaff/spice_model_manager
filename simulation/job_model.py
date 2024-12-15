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
        """ジョブの結果のバイナリデータを取得"""
        result_key = f"{self.REDIS_RESULT_PREFIX}{job_id}"
        return self.redis.get(result_key)

    def generate_job_id_from_timestamp(self, base_name):
        """ジョブIDを生成"""
        job_prefix = self.redis.incr("job_id_counter")
        job_prefix_padded = str(job_prefix).zfill(5)
        timestamp = datetime.now().strftime("%b_%d_%H%M")
        return f"{job_prefix_padded}_{base_name}_{timestamp}"

    def create_job(self, uploaded_file_path):
        """ジョブを作成"""
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

        # メタデータを保存
        self.redis.set(f"{self.REDIS_JOB_PREFIX}{job_id}:meta", json.dumps(job_data))

        # アップロードファイルのバイナリデータを保存
        self.redis.set(f"{self.REDIS_JOB_PREFIX}{job_id}:file", binary_data)

        # ジョブIDをキューに追加
        self.redis.rpush("job_queue", job_id)

        # ジョブの過剰保存を防ぐ
        all_jobs = self.redis.keys(f"{self.REDIS_JOB_PREFIX}*:meta")
        all_jobs_str = [key.decode('utf-8') for key in all_jobs]
        all_jobs_str.sort()

        if len(all_jobs_str) > self.MAX_JOBS:
            oldest_job_key = all_jobs_str[0]
            self.redis.delete(oldest_job_key.replace(":meta", ":file"))
            self.redis.delete(oldest_job_key)

        return job_id

    def get_all_jobs(self):
        """すべてのジョブをRedisから取得"""
        all_jobs = {}
        for job_key in self.redis.keys(f"{self.REDIS_JOB_PREFIX}*:meta"):
            job_key_str = job_key.decode('utf-8')
            job_id = job_key_str.replace(self.REDIS_JOB_PREFIX, "").replace(":meta", "")
            job_data = self.redis.get(job_key_str)
            if isinstance(job_data, bytes):
                job_data = job_data.decode('utf-8')
            job_data = json.loads(job_data)
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