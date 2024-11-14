import matplotlib.pyplot as plt
import os
import numpy as np
from PyLTSpice import SimRunner, SpiceEditor, LTspice, RawRead

class JFET_SimulationBase:
    def __init__(self, device_name, spice_string, template_filename):
        self.device_name = device_name
        self.spice_string = spice_string

        script_dir = os.path.dirname(os.path.abspath(__file__))  # スクリプトの絶対パスを取得
        self.template_path = os.path.join(script_dir, 'net', template_filename)  # テンプレートファイルのパス
        self.output_folder = os.path.join(script_dir, 'data')

        self.runner = SimRunner(output_folder=self.output_folder, simulator=LTspice)
        self.net = None
        self.raw_data = None

    def modify_netlist(self):
        """ネットリストを修正してファイル名を変更して保存"""
        self.net = SpiceEditor(self.template_path)
        self.net.set_component_value('J1', self.device_name)
        self.net.add_instructions(self.spice_string)

    def run_simulation(self):
        """シミュレーションを実行してRAWデータを取得"""
        run_filename = f"{os.path.splitext(os.path.basename(self.template_path))[0]}_{self.device_name}.net"
        raw_path, log = self.runner.run_now(self.net, run_filename=run_filename)
        self.raw_data = RawRead(raw_path)

    def extract_data(self):
        """シミュレーション結果から必要なデータを抽出"""
        raise NotImplementedError("このメソッドはサブクラスで実装してください")


class JFET_IV_Characteristic(JFET_SimulationBase):
    def extract_data(self):
        """I-V特性に必要なデータを抽出"""
        Vds = self.raw_data['V(n002)'].data  # Vds（ドレイン-ソース電圧）
        Vgs = self.raw_data['V(n001)'].data  # Vgs（ゲート-ソース電圧）
        Id = self.raw_data['Id(J1)'].data    # Id（ドレイン電流）
        Id_mA = Id * 1e3  # ドレイン電流をmA単位に変換
        return Vds, Vgs, Id_mA

    def plot_iv_characteristics(self, Vds, Vgs, Id_mA):
        """I-V特性をプロットする"""
        plt.figure(figsize=(8, 6))
        for vgs_value in [-0.4, -0.3, -0.2, -0.1, 0]:
            mask = (Vgs >= vgs_value - 0.05) & (Vgs <= vgs_value + 0.05)
            plt.plot(Vds[mask], Id_mA[mask], label=f'Vgs = {vgs_value}V')

        plt.title("I-V Characteristic of JFET for Different Vgs")
        plt.xlabel("Vds (Volts)")
        plt.ylabel("Id (mA)")
        plt.xlim(0)
        plt.ylim(0)
        plt.grid(True)
        plt.legend()

        # 画像保存のディレクトリ設定
        image_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'images')
        if not os.path.exists(image_dir):
            os.makedirs(image_dir)
        
        image_filename = f"{os.path.splitext(os.path.basename(self.template_path))[0]}_{self.device_name}.png"
        image_path = os.path.join(image_dir, image_filename)
        plt.savefig(image_path)
        return image_path


class JFET_Vgs_Id_Characteristic(JFET_SimulationBase):
    def extract_data(self):
        """VgsとIdの関係を抽出"""
        Vgs = self.raw_data['V(n001)'].data  # Vgs（ゲート-ソース電圧）
        Id = self.raw_data['Id(J1)'].data    # Id（ドレイン電流）
        Id_mA = Id * 1e3  # ドレイン電流をmA単位に変換
        return Vgs, Id_mA

    def plot_vgs_id_characteristics(self, Vgs, Id_mA):
        """VgsとIdの特性をプロットする"""
        plt.figure(figsize=(8, 6))
        plt.plot(Vgs, Id_mA, label=f'Id vs Vgs')

        plt.title("Vgs-Id Characteristic of JFET")
        plt.xlabel("Vgs (Volts)")
        plt.ylabel("Id (mA)")
        plt.xlim(-3, 0)
        plt.ylim(0)
        plt.grid(True)
        plt.legend()

        # 画像保存のディレクトリ設定
        image_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'images')
        if not os.path.exists(image_dir):
            os.makedirs(image_dir)

        image_filename = f"{os.path.splitext(os.path.basename(self.template_path))[0]}_{self.device_name}.png"
        image_path = os.path.join(image_dir, image_filename)
        plt.savefig(image_path)
        return image_path

class JFET_Gm_Vgs_Characteristic(JFET_SimulationBase):
    def extract_data(self):
        """VgsとIdからgmを計算"""
        Vgs = self.raw_data['V(n001)'].data  # Vgs（ゲート-ソース電圧）
        Id = self.raw_data['Id(J1)'].data    # Id（ドレイン電流）
        Id_mA = Id * 1e3  # ドレイン電流をmA単位に変換
        
        # gmを数値微分で計算
        gm = np.gradient(Id_mA, Vgs)  # Vgsに対するIdの数値微分
        return Vgs, gm

    def plot_gm_vgs_characteristics(self, Vgs, gm):
        """gm-Vgs特性をプロットする"""
        plt.figure(figsize=(8, 6))
        plt.plot(Vgs, gm, label=f'gm vs Vgs')

        plt.title("gm-Vgs Characteristic of JFET")
        plt.xlabel("Vgs (Volts)")
        plt.ylabel("gm (mS)")
        plt.xlim(-3, 0)
        plt.ylim(0)
        plt.grid(True)
        plt.legend()

        # 画像保存のディレクトリ設定
        image_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'images')
        if not os.path.exists(image_dir):
            os.makedirs(image_dir)

        image_filename = f"{os.path.splitext(os.path.basename(self.template_path))[0]}_{self.device_name}.png"
        image_path = os.path.join(image_dir, image_filename)
        plt.savefig(image_path)
        return image_path

class JFET_Gm_Id_Characteristic(JFET_SimulationBase):
    def extract_data(self):
        """VgsとIdからgmを計算（mS単位に変換）"""
        Vgs = self.raw_data['V(n001)'].data  # Vgs（ゲート-ソース電圧）
        Id = self.raw_data['Id(J1)'].data    # Id（ドレイン電流）
        Id_mA = Id * 1e3  # ドレイン電流をmA単位に変換（元々はA単位）

        # gmを数値微分で計算（mS単位）
        gm = np.gradient(Id_mA, Vgs)  # Vgsに対するIdの数値微分
        return Id_mA, gm

    def plot_gm_id_characteristics(self, Id_mA, gm):
        """gm-Vgs特性をプロットする"""
        plt.figure(figsize=(8, 6))
        plt.plot(Id_mA, np.abs(gm), label=f'gm vs Id')  # |gm|（mS単位）でプロット

        plt.title("gm-Id Characteristic of JFET")
        plt.xlabel("Id (mA)")  # ドレイン電流をmA単位
        plt.ylabel("gm (mS)")  # フィールド・トランスコンダクタンス（ミリジーメンス）
        plt.xlim([min(Id_mA), max(Id_mA)])  # Idの最小値と最大値で範囲を設定
        plt.ylim([min(np.abs(gm)), max(np.abs(gm))])  # gmの絶対値で範囲を設定
        plt.grid(True)
        plt.legend()

        # 画像保存のディレクトリ設定
        image_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'images')
        os.makedirs(image_dir, exist_ok=True)

        image_filename = f"{os.path.splitext(os.path.basename(self.template_path))[0]}_{self.device_name}.png"
        image_path = os.path.join(image_dir, image_filename)
        plt.savefig(image_path)
        return image_path



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
            spice_string = model["spice_string"]

            # JFETのI-V特性をプロット
            print(f"Generating I-V characteristics for {device_name} ({model['device_type']})")
            jfet_iv = JFET_IV_Characteristic(device_name, spice_string, 'jfet_iv.net')
            jfet_iv.modify_netlist()
            jfet_iv.run_simulation()
            Vds, Vgs, Id_mA = jfet_iv.extract_data()
            image_path_iv = jfet_iv.plot_iv_characteristics(Vds, Vgs, Id_mA)

            upload_image(model_id, image_path_iv, 'iv')

            # JFETのVgs-Id特性をプロット
            print(f"Generating Vgs-Id characteristics for {device_name} ({model['device_type']})")
            jfet_vgs_id = JFET_Vgs_Id_Characteristic(device_name, spice_string, 'jfet_vgs_id.net')
            jfet_vgs_id.modify_netlist()
            jfet_vgs_id.run_simulation()
            Vgs, Id_mA = jfet_vgs_id.extract_data()
            image_path_vgs_id = jfet_vgs_id.plot_vgs_id_characteristics(Vgs, Id_mA)

            upload_image(model_id, image_path_vgs_id, 'vgs_id')

            # JFETのgm-Vgs特性をプロット
            print(f"Generating gm-Vgs characteristics for {device_name} ({model['device_type']})")
            jfet_gm_vgs = JFET_Gm_Vgs_Characteristic(device_name, spice_string, 'jfet_gm_vgs.net')
            jfet_gm_vgs.modify_netlist()
            jfet_gm_vgs.run_simulation()
            Vgs, gm = jfet_gm_vgs.extract_data()
            image_path_gm_vgs = jfet_gm_vgs.plot_gm_vgs_characteristics(Vgs, gm)

            upload_image(model_id, image_path_gm_vgs, 'gm_vgs')

            # JFETのgm-Id特性をプロット
            print(f"Generating gm-Id characteristics for {device_name} ({model['device_type']})")
            jfet_gm_id = JFET_Gm_Id_Characteristic(device_name, spice_string, 'jfet_gm_id.net')
            jfet_gm_id.modify_netlist()
            jfet_gm_id.run_simulation()
            Id_mA, gm = jfet_gm_id.extract_data()
            image_path_gm_id = jfet_gm_id.plot_gm_id_characteristics(Id_mA, gm)
            
            upload_image(model_id, image_path_gm_id, 'gm_id')

    main()
