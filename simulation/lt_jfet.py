import tempfile
import matplotlib.pyplot as plt
import os
import zipfile
from io import BytesIO
import numpy as np
from PyLTSpice import SimRunner, SpiceEditor, LTspice, RawRead

class JFET_SimulationBase:

    _simulation_name = 'jfet_dc' # default

    def __init__(self, device_name, device_type, spice_string):
        self.device_name = device_name
        self.device_type = device_type
        self.spice_string = spice_string
        self.simulation_name = self._simulation_name

        script_dir = os.path.dirname(os.path.abspath(__file__))  # スクリプトの絶対パスを取得
        self.template_path = os.path.join(script_dir, 'net', 'jfet_dc.net')  # テンプレートファイルのパス
        self.output_folder = os.path.join(script_dir, 'data')

        self.runner = SimRunner(output_folder=self.output_folder, simulator=LTspice)
        self.net = None
        self.raw_data = None

        self.api_url = "http://127.0.0.1:5000/simulate"

    def modify_netlist(self):
        """ネットリストを修正してファイル名を変更して保存"""
        self.net = SpiceEditor(self.template_path)
        self.net.set_component_value('J1', self.device_name)
        self.net.add_instructions(self.spice_string)

    def run_simulation(self):
        """シミュレーションを実行してRAWデータを取得"""
        run_filename = f"{self.simulation_name}_{self.device_name}.net"
        raw_path, log = self.runner.run_now(self.net, run_filename=run_filename)
        self.raw_data = RawRead(raw_path)

    def extract_zip_contents(self, zip_data):
        """ZIPデータを解凍して、.raw と .log ファイルのパスを返す関数"""
        # ZIPファイルをメモリ上で解凍
        with zipfile.ZipFile(BytesIO(zip_data)) as zip_ref:
            # 解凍したファイルのディレクトリを作成
            extraction_dir = tempfile.mkdtemp()

            # .raw と .log のファイルを抽出
            raw_file = None
            log_file = None
            for file_name in zip_ref.namelist():
                zip_ref.extract(file_name, extraction_dir)
                if file_name.endswith('.raw'):
                    raw_file = os.path.join(extraction_dir, file_name)
                elif file_name.endswith('.log'):
                    log_file = os.path.join(extraction_dir, file_name)

            # .raw と .log ファイルが存在することを確認
            if raw_file and log_file:
                return raw_file, log_file
            else:
                raise ValueError("エラー: .raw または .log ファイルが見つかりません")


    def run_simulation_api(self):
        """ネットリストを一時ファイルに保存し、APIに送信する関数"""

        run_filename = f"{self.simulation_name}_{self.device_name}.net"

        # 一時的なネットリストファイルを作成
        with tempfile.NamedTemporaryFile(delete=True, suffix='.net') as temp_net_file:
            # ネットリストをファイルに保存
            self.net.save_netlist(temp_net_file.name)

            # APIにネットリストを送信
            with open(temp_net_file.name, 'rb') as f:
                files = {'file': (run_filename, f, 'application/octet-stream')}
                response = requests.post(self.api_url, files=files)

            # レスポンスの確認
            if response.status_code == 200:
                try:
                    # ZIPファイルを解凍し、.raw と .log ファイルを取得
                    raw_file, log_file = self.extract_zip_contents(response.content)

                    # RawReadで処理
                    self.raw_data = RawRead(raw_file)

                    # ファイル処理後に削除
                    os.remove(raw_file)
                    os.remove(log_file)

                except ValueError as e:
                    print(str(e))
            else:
                print(f"エラー: {response.status_code}, メッセージ: {response.text}")


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

            if model["simulation_done"]:
                pass
            model_id = model["id"]
            device_name = model["device_name"]
            device_type = model["device_type"]
            spice_string = model["spice_string"]

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
