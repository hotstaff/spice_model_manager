import os
import json
from datetime import datetime
import zipfile
import tempfile
from io import BytesIO
import shutil

from redis import Redis

class JobModel:
    def __init__(self, redis_host="localhost", redis_port=6379, redis_db=0):
        self.redis = Redis(host=redis_host, port=redis_port, db=redis_db, decode_responses=False)
        self.REDIS_JOB_PREFIX = "job:"
        self.REDIS_RESULT_PREFIX = "result:"
        self.MAX_JOBS = 25
        self.SIMULATION_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
        os.makedirs(self.SIMULATION_DIR, exist_ok=True)

        self.temp_files = {}


    def extract_zip_contents(self, zip_data, job_id):
        """ZIPデータを解凍して、.raw と .log ファイルのパスを返す関数"""
        extraction_dir = None
        try:
            with zipfile.ZipFile(BytesIO(zip_data)) as zip_ref:
                extraction_dir = tempfile.mkdtemp()

                raw_file = None
                log_file = None
                for file_name in zip_ref.namelist():
                    zip_ref.extract(file_name, extraction_dir)
                    if file_name.endswith('.raw'):
                        raw_file = os.path.join(extraction_dir, file_name)
                    elif file_name.endswith('.log'):
                        log_file = os.path.join(extraction_dir, file_name)

                if not raw_file or not log_file:
                    print(f"Error: .raw or .log is not found in the ZIP file for job {job_id}.")
                    return None, None

                print(f"Job results extracted: {raw_file}, {log_file}")
                self.temp_files[job_id] = {'raw': raw_file, 'log': log_file, 'dir': extraction_dir}
                return raw_file, log_file

        except zipfile.BadZipFile:
            print(f"Error: The file for job {job_id} is not a valid ZIP file.")
        except Exception as e:
            print(f"Error extracting files for job {job_id}: {str(e)}")
        
        finally:
            # エラーが発生した場合にのみ一時ディレクトリを削除
            if extraction_dir and not (raw_file and log_file):
                print(f"Cleaning up temporary directory: {extraction_dir}")
                shutil.rmtree(extraction_dir)

        return None, None


    def cleanup(self, job_id):
        """ジョブ結果に関連する一時ファイルを削除する関数"""
        if job_id in self.temp_files:
            temp_files = self.temp_files.pop(job_id)
            extraction_dir = temp_files.get('dir')

            if extraction_dir and os.path.exists(extraction_dir):
                # 解凍したディレクトリとファイルを再帰的に削除
                shutil.rmtree(extraction_dir)
                print(f"Temporary files for job ID {job_id} have been deleted.")
            else:
                print(f"Extraction directory for job ID {job_id} not found.")
        else:
            print(f"No temporary files found for job ID {job_id}.")


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

    def get_job_result(self, job_id, extract=False):
        """ジョブの結果を取得し、必要なら解凍する"""
        result_key = f"{self.REDIS_RESULT_PREFIX}{job_id}"
        result_data = self.redis.get(result_key)
        
        if result_data:
            if extract:
                # ZIPファイルの解凍処理
                return self.extract_zip_contents(result_data, job_id)
            return result_data
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


    def get_job_result_with_notification(self, job_id, timeout=30, extract=False):
        """
        Pub/Subを使用してジョブの結果を取得。
        タイムアウト期間内に通知がない場合は、直接Redisキーを確認。

        Args:
            job_id (str): ジョブID。
            timeout (int): タイムアウト秒数。
            extract (bool): 解凍を行うかどうか。

        Returns:
            bytes or tuple: ジョブ結果のバイナリデータ、または解凍されたファイルパスのタプル。
            None: 結果が存在しない場合。
        """
        pubsub = self.redis.pubsub()
        pubsub.subscribe("job_notifications")
        result_key = f"{self.REDIS_RESULT_PREFIX}{job_id}"

        try:
            start_time = datetime.now()
            for message in pubsub.listen():
                # タイムアウトチェック
                if (datetime.now() - start_time).seconds > timeout:
                    break

                # 通知を受信した場合
                if message["type"] == "message" and message["data"].decode() == job_id:
                    # Redisから結果を取得して返す
                    result = self.redis.get(result_key)
                    if result:
                        if extract:
                            return self.extract_zip_contents(result, job_id)  # 解凍を行う
                        return result  # 解凍しない場合、そのまま結果を返す

        except Exception as e:
            print(f"Error getting job result for job_id {job_id}: {str(e)}")
            return None  # エラーが発生した場合、Noneを返す

        finally:
            # Pub/Subリソースをクリーンアップ
            pubsub.unsubscribe()
            pubsub.close()

        # タイムアウト後にRedisキーを直接確認
        result = self.redis.get(result_key)
        if result and extract:
            return self.extract_zip_contents(result, job_id)  # 解凍を行う
        return result  # 解凍しない場合、そのまま結果を返す


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
