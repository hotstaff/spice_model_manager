import os
import tempfile
import shutil
import zipfile
from io import BytesIO
import requests
import time
import numpy as np
import matplotlib.pyplot as plt

from PyLTSpice import SimRunner, SpiceEditor, LTspice, RawRead


class SimulationClient:
    def __init__(self, api_url):
        self.api_url = api_url
        self.job_id = None  # ジョブIDを格納する変数
        self.temp_files = {}  # job_idごとの一時ファイルを格納する辞書

    def simulation_run(self, netlist_file):
        """ネットリストを一時ファイルに保存し、APIに送信してジョブを開始する関数"""
        if not os.path.exists(netlist_file):
            print(f"Error: The netlist file '{netlist_file}' does not exist.")
            return None

        with open(netlist_file, 'rb') as f:
            files = {'file': (os.path.basename(netlist_file), f, 'application/octet-stream')}
            response = requests.post(f"{self.api_url}/api/simulate", files=files)

        if response.status_code == 202:
            job_data = response.json()
            self.job_id = job_data.get("job_id")
            print(f"Job started with ID: {self.job_id}")
            return self.job_id
        else:
            print(f"Error starting simulation: {response.status_code}, {response.text}")
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
                    time.sleep(1)

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

        status_response = requests.get(f"{self.api_url}/api/simulations/{job_id}")
        
        if status_response.status_code == 200:
            job_data = status_response.json()
            return job_data["status"]
        else:
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


class JFET_SimulationBase:

    _simulation_name = 'jfet_dc' # default

    def __init__(self, device_name, device_type, spice_string, remote=True):
        self.device_name = device_name
        self.device_type = device_type
        self.spice_string = spice_string
        self.simulation_name = self._simulation_name

        script_dir = os.path.dirname(os.path.abspath(__file__))  # スクリプトの絶対パスを取得
        self.template_path = os.path.join(script_dir, 'net', 'jfet_dc.net')  # テンプレートファイルのパス
        self.output_folder = os.path.join(script_dir, 'data')

        self.net = None
        self.raw_data = None

        self.remote = remote

        if remote:
            self.simulation_client = SimulationClient(api_url="http://34.30.181.119:5000")
            self.runner = None
        else:
            self.simulation_client = None
            self.runner = SimRunner(output_folder=self.output_folder, simulator=LTspice)

    def modify_netlist(self):
        """ネットリストを修正してファイル名を変更して保存"""
        self.net = SpiceEditor(self.template_path)
        self.net.set_component_value('J1', self.device_name)
        self.net.add_instructions(self.spice_string)

    def run_simulation(self):
        """シミュレーションを実行してRAWデータを取得"""
        run_filename = f"{self.simulation_name}_{self.device_name}.net"
        raw_file, log = self.runner.run_now(self.net, run_filename=run_filename)
        self.raw_data = RawRead(raw_file)

    def run_simulation_api(self):
        """ネットリストを指定したフォルダに保存し、APIに送信する関数"""
        run_filename = f"{self.simulation_name}_{self.device_name}.net"

        # フォルダ内にネットリストファイルを保存
        netlist_path = os.path.join(self.output_folder, run_filename)
        
        # ネットリストをファイルに保存
        self.net.save_netlist(netlist_path)
        job_id = self.simulation_client.simulation_run(netlist_path)

        # 待つ
        raw_file, log_file = self.simulation_client.get_result(job_id=job_id, wait=True)

        self.raw_data = RawRead(raw_file)

        # 必要に応じてファイルを手動で削除
        os.remove(netlist_path)


    def extract_data(self):
        """シミュレーション結果から必要なデータを抽出"""
        raise NotImplementedError("このメソッドはサブクラスで実装してください")

    def save_image(self, plt, filename=None):
        if not filename:
            filename = f"jfet_{self.simulation_name}_{self.device_name}.png"
        image_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'images')
        os.makedirs(image_dir, exist_ok=True)
        image_path = os.path.join(image_dir, filename)
        plt.savefig(image_path)
        return image_path

    def process_and_plot(self):
        self.modify_netlist()
        self.run_simulation_api()
        data = self.extract_data()
        try:
            return self.plot(*data)
        finally:
            plt.close('all')  # メモリを解放
            if self.remote:
                self.simulation_client.cleanup_temp_files()


class JFET_IV_Characteristic(JFET_SimulationBase):

    _simulation_name = 'iv'

    def modify_netlist(self):
        super().modify_netlist()

        # DC sweep
        if self.device_type == 'NJF':
            self.net.add_instructions('.dc V1 -0.4 0 0.1 V2 0 20 0.1')
        elif self.device_type == 'PJF':
            self.net.add_instructions('.dc V1 0 0.4 0.1 V2 0 -20 -0.1')

    def extract_data(self):
        """I-V特性に必要なデータを抽出"""
        Vds = self.raw_data['V(n002)'].data  # Vds（ドレイン-ソース電圧）
        Vgs = self.raw_data['V(n001)'].data  # Vgs（ゲート-ソース電圧）
        Id = self.raw_data['Id(J1)'].data    # Id（ドレイン電流）
        Id_mA = Id * 1e3  # ドレイン電流をmA単位に変換
        return Vds, Vgs, Id_mA

    def plot(self, Vds, Vgs, Id_mA):
        """I-V特性をプロットする"""
        plt.figure(figsize=(8, 6))

        if self.device_type == 'NJF':
            vgs_list = [-0.4, -0.3, -0.2, -0.1, 0]
        elif self.device_type == 'PJF':
            vgs_list = [0.4, 0.3, 0.2, 0.1, 0]

        for vgs_value in vgs_list:
            mask = (Vgs >= vgs_value - 0.05) & (Vgs <= vgs_value + 0.05)
            plt.plot(Vds[mask], Id_mA[mask], label=f'Vgs = {vgs_value}V')

        plt.title("I-V Characteristic of JFET for Different Vgs")
        plt.xlabel("Vds (Volts)")
        plt.ylabel("Id (mA)")

        if self.device_type == 'PJF':
            plt.gca().invert_xaxis()
            plt.gca().invert_yaxis()

        plt.xlim(0)
        plt.ylim(0)

        plt.grid(True)
        plt.legend()

        return self.save_image(plt)

class JFET_Vgs_Id_Characteristic(JFET_SimulationBase):

    _simulation_name = 'vgs_id'

    def modify_netlist(self):
        super().modify_netlist()

        # DC sweep
        if self.device_type == 'NJF':
            self.net.set_element_model('V2',"DC 10")
            self.net.add_instructions('.dc V1 -3 0 0.01')
        elif self.device_type == 'PJF':
            self.net.set_element_model('V2',"DC -10")
            self.net.add_instructions('.dc V1 0 3 0.01')

    def extract_data(self):
        """VgsとIdの関係を抽出"""
        Vgs = self.raw_data['V(n001)'].data  # Vgs（ゲート-ソース電圧）
        Id = self.raw_data['Id(J1)'].data    # Id（ドレイン電流）
        Id_mA = Id * 1e3  # ドレイン電流をmA単位に変換
        return Vgs, Id_mA

    def plot(self, Vgs, Id_mA):
        """VgsとIdの特性をプロットする"""
        plt.figure(figsize=(8, 6))
        plt.plot(Vgs, Id_mA, label=f'Id vs Vgs')

        plt.title("Vgs-Id Characteristic of JFET")
        plt.xlabel("Vgs (Volts)")
        plt.ylabel("Id (mA)")

        if self.device_type == 'PJF':
            plt.gca().invert_xaxis()
            plt.gca().invert_yaxis()
            plt.xlim(3, 0)
        elif self.device_type == 'NJF':
            plt.xlim(-3, 0)

        plt.ylim(0)
        plt.grid(True)
        plt.legend()

        return self.save_image(plt)

class JFET_Gm_Vgs_Characteristic(JFET_SimulationBase):

    _simulation_name = 'gm_vgs'

    def modify_netlist(self):
        super().modify_netlist()

        # DC sweep
        if self.device_type == 'NJF':
            self.net.set_element_model('V2',"DC 10")
            self.net.add_instructions('.dc V1 -3 0 0.001')
        elif self.device_type == 'PJF':
            self.net.set_element_model('V2',"DC -10")
            self.net.add_instructions('.dc V1 0 3 0.001')

    def extract_data(self):
        """VgsとIdからgmを計算"""
        Vgs = self.raw_data['V(n001)'].data  # Vgs（ゲート-ソース電圧）
        Id = self.raw_data['Id(J1)'].data    # Id（ドレイン電流）
        Id_mA = Id * 1e3  # ドレイン電流をmA単位に変換
        
        # gmを数値微分で計算
        gm = np.gradient(Id_mA, Vgs)  # Vgsに対するIdの数値微分
        return Vgs, gm

    def plot(self, Vgs, gm):
        """gm-Vgs特性をプロットする"""
        plt.figure(figsize=(8, 6))
        plt.plot(Vgs, gm, label=f'gm vs Vgs')

        plt.title("gm-Vgs Characteristic of JFET")
        plt.xlabel("Vgs (Volts)")
        plt.ylabel("gm (mS)")

        if self.device_type == 'PJF':
            plt.gca().invert_xaxis()
            plt.xlim(3, 0)
        elif self.device_type == 'NJF':
            plt.xlim(-3, 0)

        plt.ylim(0)
        plt.grid(True)
        plt.legend()

        return self.save_image(plt)

class JFET_Gm_Id_Characteristic(JFET_SimulationBase):

    _simulation_name = 'gm_id'

    def modify_netlist(self):
        super().modify_netlist()

        # DC sweep
        if self.device_type == 'NJF':
            self.net.set_element_model('V2',"DC 10")
            self.net.add_instructions('.dc V1 -3 0 0.001')
        elif self.device_type == 'PJF':
            self.net.set_element_model('V2',"DC -10")
            self.net.add_instructions('.dc V1 0 3 0.001')


    def extract_data(self):
        """VgsとIdからgmを計算（mS単位に変換）"""
        Vgs = self.raw_data['V(n001)'].data  # Vgs（ゲート-ソース電圧）
        Id = self.raw_data['Id(J1)'].data    # Id（ドレイン電流）
        Id_mA = Id * 1e3  # ドレイン電流をmA単位に変換（元々はA単位）

        # gmを数値微分で計算（mS単位）
        gm = np.gradient(Id_mA, Vgs)  # Vgsに対するIdの数値微分
        return Id_mA, gm

    def plot(self, Id_mA, gm):
        """gm-Vgs特性をプロットする"""
        plt.figure(figsize=(8, 6))
        plt.plot(Id_mA, np.abs(gm), label=f'gm vs Id')  # |gm|（mS単位）でプロット

        plt.title("gm-Id Characteristic of JFET")
        plt.xlabel("Id (mA)")  # ドレイン電流をmA単位
        plt.ylabel("gm (mS)")  # フィールド・トランスコンダクタンス（ミリジーメンス）

        if self.device_type == 'PJF':
            plt.gca().invert_xaxis()
            plt.xlim([max(Id_mA), min(Id_mA)]) 
        elif self.device_type == 'NJF':
            plt.xlim([min(Id_mA), max(Id_mA)])  # Idの最小値と最大値で範囲を設定

        plt.ylim([min(np.abs(gm)), max(np.abs(gm))])  # gmの絶対値で範囲を設定
        plt.grid(True)
        plt.legend()

        return self.save_image(plt)



# メイン処理
if __name__ == "__main__":
    import requests

    API_URL = "https://spice-model-manager.onrender.com/api/models"  # APIのURL

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
        url = 'https://spice-model-manager.onrender.com/api/upload_image'
        data = {
            'image_type': image_type,  # 任意の値
            'data_id': model_id  # 任意のデータID
        }

        with open(image_path, 'rb') as image_file:
            files = {'image': ('image.png', image_file, 'image/png')}
            response = requests.post(url, data=data, files=files)

        print(response.json(), model_id)

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

            # # JFETのI-V特性をプロット
            print(f"Generating I-V characteristics for {device_name} ({model['device_type']})")
            jfet_iv = JFET_IV_Characteristic(device_name, device_type, spice_string)
            image_path_iv = jfet_iv.process_and_plot()

            upload_image(model_id, image_path_iv, 'iv')

            # # JFETのVgs-Id特性をプロット
            print(f"Generating Vgs-Id characteristics for {device_name} ({model['device_type']})")
            jfet_vgs_id = JFET_Vgs_Id_Characteristic(device_name, device_type, spice_string)
            image_path_vgs_id = jfet_vgs_id.process_and_plot()

            upload_image(model_id, image_path_vgs_id, 'vgs_id')

            # JFETのgm-Vgs特性をプロット
            print(f"Generating gm-Vgs characteristics for {device_name} ({model['device_type']})")
            jfet_gm_vgs = JFET_Gm_Vgs_Characteristic(device_name, device_type, spice_string)
            image_path_gm_vgs = jfet_gm_vgs.process_and_plot()

            upload_image(model_id, image_path_gm_vgs, 'gm_vgs')

            # # JFETのgm-Id特性をプロット
            print(f"Generating gm-Id characteristics for {device_name} ({model['device_type']})")
            jfet_gm_id = JFET_Gm_Id_Characteristic(device_name, device_type, spice_string)
            image_path_gm_id = jfet_gm_id.process_and_plot()
            
            upload_image(model_id, image_path_gm_id, 'gm_id')

    main()
