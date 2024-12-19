import os
import tempfile
import shutil
import zipfile
from io import BytesIO
import requests
import time

from PyLTSpice import SimRunner, LTspice

from jfet import JFET_IV_Characteristic, JFET_Vgs_Id_Characteristic, JFET_Gm_Vgs_Characteristic, JFET_Gm_Id_Characteristic

class SimulationClient:
    def __init__(self, api_url):
        self.api_url = api_url
        self.job_id = None  # ジョブIDを格納する変数
        self.temp_files = {}  # job_idごとの一時ファイルを格納する辞書

    def simulation_run(self, netlist_file, max_retries=3, retry_delay=5):
        """ネットリストを一時ファイルに保存し、APIに送信してジョブを開始する関数"""
        if not os.path.exists(netlist_file):
            print(f"Error: The netlist file '{netlist_file}' does not exist.")
            return None

        # 最大リトライ回数分ループして再試行
        for attempt in range(1, max_retries + 1):
            with open(netlist_file, 'rb') as f:
                files = {'file': (os.path.basename(netlist_file), f, 'application/octet-stream')}
                response = requests.post(f"{self.api_url}/api/simulate", files=files)

            if response.status_code == 202:
                job_data = response.json()
                self.job_id = job_data.get("job_id")
                print(f"Job started with ID: {self.job_id}")
                return self.job_id
            else:
                print(f"Error starting simulation (attempt {attempt}/{max_retries}): {response.status_code}, {response.text}")
                if attempt < max_retries:
                    print(f"Retrying in {retry_delay} seconds...")
                    time.sleep(retry_delay)
                else:
                    print("Max retries reached. Job registration failed.")
                    return None

    def get_result(self, job_id=None, wait=False):
        """ジョブIDを指定して結果を取得し、ZIPファイルを解凍して.raw と .log ファイルを返す関数"""
        if job_id is None:
            job_id = self.job_id

        if not job_id:
            print("Error: No job ID provided.")
            return None, None

        if wait:
            while True:
                status = self.get_job_status(job_id)
                if status == "completed":
                    print(f"Job {job_id} completed.")
                    break
                elif status == "failed":
                    print(f"Job {job_id} failed.")
                    return None, None
                else:
                    print(f"Job {job_id} is still running. Waiting...")
                    time.sleep(0.5)

        result_response = requests.get(f"{self.api_url}/api/simulations/{job_id}/result")
        
        if result_response.status_code == 200:
            raw_file, log_file = self.extract_zip_contents(result_response.content, job_id)
            return raw_file, log_file
        else:
            print(f"Error retrieving result for job {job_id}: {result_response.status_code}")
            return None, None

    def get_job_status(self, job_id=None):
        """ジョブの状態を取得する関数"""
        if job_id is None:
            job_id = self.job_id

        if not job_id:
            print("Error: No job ID provided.")
            return None

        # ジョブのステータスを取得
        status_response = requests.get(f"{self.api_url}/api/simulations/{job_id}")
        
        if status_response.status_code == 200:
            # 成功した場合、ステータスを返す
            job_data = status_response.json()
            return job_data["status"]
        
        elif status_response.status_code == 404:
            # 404エラーの場合、ジョブ登録が失敗したとみなす
            print(f"Error: Job with ID {job_id} not found. Job registration may have failed.")
            return None

        else:
            # 他のエラーの場合
            print(f"Error retrieving status for job {job_id}: {status_response.status_code}")
            return None

    def extract_zip_contents(self, zip_data, job_id):
        """ZIPデータを解凍して、.raw と .log ファイルのパスを返す関数"""
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

            if raw_file and log_file:
                print(f"Job results extracted: {raw_file}, {log_file}")
                # job_idをキーに一時ファイルを保存
                self.temp_files[job_id] = {'raw': raw_file, 'log': log_file, 'dir': extraction_dir}
                return raw_file, log_file
            else:
                raise ValueError("エラー: .raw または .log ファイルが見つかりません")

    def cleanup_temp_files(self, job_id=None):
        """job_idを指定して一時ファイルを削除する関数"""
        if job_id is None:
            job_id = self.job_id

        if job_id not in self.temp_files:
            print(f"Error: No temporary files found for job ID {job_id}.")
            return

        try:
            # 一時ファイルを削除
            temp_files = self.temp_files.pop(job_id)
            raw_file = temp_files.get('raw')
            log_file = temp_files.get('log')
            extraction_dir = temp_files.get('dir')

            if raw_file and os.path.exists(raw_file):
                os.remove(raw_file)
                # print(f"Deleted temporary file: {raw_file}")
            if log_file and os.path.exists(log_file):
                os.remove(log_file)
                # print(f"Deleted temporary file: {log_file}")

            # 一時ディレクトリも削除
            if os.path.exists(extraction_dir):
                shutil.rmtree(extraction_dir)
                print(f"Deleted temporary directory: {extraction_dir}")
        except Exception as e:
            print(f"Error during cleanup: {e}")


# メイン処理
if __name__ == "__main__":

    API_URL = "https://spice-model-manager-72390409021.asia-northeast2.run.app/api/models"  # APIのURL

    def fetch_model_data():
        """APIから全モデルデータを取得し、NJF/PJFのものを抽出"""
        try:
            response = requests.get(API_URL)
            response.raise_for_status()  # ステータスコードが200以外なら例外を発生
            
            # レスポンスをJSONとしてデコード
            models = response.json()
            
            # NJFまたはPJFタイプのデータを抽出
            jfet_models = [model for model in models if model["device_type"] in ["NJF", "PJF"]]
            return jfet_models
        except requests.exceptions.RequestException as e:
            print(f"Error fetching model data: {e}")
            return []
        except ValueError:
            print("Error: API response is not in JSON format.")
            return []

    def upload_image(model_id, image_path, image_type):
        """画像をアップロードする関数"""
        url = 'https://spice-model-manager-72390409021.asia-northeast2.run.app/api/upload_image'
        data = {
            'image_type': image_type,
            'data_id': model_id
        }

        try:
            with open(image_path, 'rb') as image_file:
                files = {'image': ('image.png', image_file, 'image/png')}
                response = requests.post(url, data=data, files=files)

            if response.status_code == 200:
                print(f"Upload successful: {model_id}")
            else:
                print(f"Upload failed (status: {response.status_code}): {model_id}")

        except Exception as e:
            print(f"Error during upload: {e}")

    def simulate(obj, local=True):
        netlist_path = obj.build()

        if local:
            runner = SimRunner(output_folder=obj.output_folder, simulator=LTspice)
            raw_file, log_file = runner.run_now(obj.net, run_filename=os.path.basename(netlist_path))
            return raw_file, log_file
        else:
            simulation_client = SimulationClient(api_url="https://spice-model-manager-72390409021.asia-northeast2.run.app")
            job_id = simulation_client.simulation_run(netlist_path)
            raw_file, log_file = simulation_client.get_result(job_id=job_id, wait=True)
            return raw_file, log_file


    def main():
        """メイン処理"""
        # データベースからNJFおよびPJFのモデルデータを取得
        jfet_models = fetch_model_data()
        
        # 各モデルデータに対してI-V特性またはVgs-Id特性を生成
        for model in jfet_models:

            model_id = model["id"]
            device_name = model["device_name"]
            device_type = model["device_type"]
            spice_string = model["spice_string"]

            if model["simulation_done"]:
                print(f"{device_name} is already simulated. skip...")
                pass

            # JFETのI-V特性をプロット
            print(f"Generating I-V characteristics for {device_name} ({model['device_type']})")
            jfet_iv = JFET_IV_Characteristic(device_name, device_type, spice_string)

            raw_file, log_file = simulate(jfet_iv, local=False)

            jfet_iv.load_results(raw_file, log_file)
            image_path_iv = jfet_iv.plot()


            # JFETのVgs-Id特性をプロット
            print(f"Generating Vgs-Id characteristics for {device_name} ({model['device_type']})")
            jfet_vgs_id = JFET_Vgs_Id_Characteristic(device_name, device_type, spice_string)

            raw_file, log_file = simulate(jfet_vgs_id, local=False)

            jfet_vgs_id.load_results(raw_file, log_file)
            image_path_vgs_id = jfet_vgs_id.plot()


            # JFETのgm-Vgs特性をプロット
            print(f"Generating gm-Vgs characteristics for {device_name} ({model['device_type']})")
            jfet_gm_vgs = JFET_Gm_Vgs_Characteristic(device_name, device_type, spice_string)

            raw_file, log_file = simulate(jfet_gm_vgs, local=False)

            jfet_gm_vgs.load_results(raw_file, log_file)
            image_path_gm_vgs = jfet_gm_vgs.plot()


            # JFETのgm-Id特性をプロット
            print(f"Generating gm-Id characteristics for {device_name} ({model['device_type']})")
            jfet_gm_id = JFET_Gm_Id_Characteristic(device_name, device_type, spice_string)

            raw_file, log_file = simulate(jfet_gm_id, local=False)

            jfet_gm_id.load_results(raw_file, log_file)
            image_path_gm_id = jfet_gm_id.plot()

            upload_image(model_id, image_path_iv, 'iv')
            upload_image(model_id, image_path_vgs_id, 'vgs_id')
            upload_image(model_id, image_path_gm_vgs, 'gm_vgs')
            upload_image(model_id, image_path_gm_id, 'gm_id')


    main()
