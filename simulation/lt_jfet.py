import matplotlib.pyplot as plt
import os
from PyLTSpice import SimRunner, SpiceEditor, LTspice, RawRead

class JFET_IV_Characteristic:
    def __init__(self, device_name, spice_string, template_filename="jfet_iv.net"):
        # 初期設定
        self.device_name = device_name
        self.spice_string = spice_string
        
        
        # スクリプトのディレクトリを基準にテンプレートファイルのパスを設定
        script_dir = os.path.dirname(os.path.abspath(__file__))  # スクリプトの絶対パスを取得
        self.template_path = os.path.join(script_dir, 'net', template_filename)  # 'net' フォルダ内にテンプレートを配置
        self.output_folder = os.path.join(script_dir, 'data')
        
        self.runner = SimRunner(output_folder=self.output_folder, simulator=LTspice)
        self.net = None
        self.raw_data = None

    def modify_netlist(self):
        """ネットリストを修正してファイル名を変更して保存"""
        # Netlistの読み込み
        self.net = SpiceEditor(self.template_path)  # 絶対パスを使用してネットリストを読み込む

        self.net.set_component_value('J1', self.device_name)
        self.net.add_instructions(self.spice_string)

    def run_simulation(self):
        """シミュレーションを実行してRAWデータを取得"""
        run_filename = f"{os.path.splitext(os.path.basename(self.template_path))[0]}_{self.device_name}.net"

        # シミュレーションの実行
        raw_path, log = self.runner.run_now(self.net, run_filename=run_filename)
        
        # RAWファイルの読み込み
        self.raw_data = RawRead(raw_path)

    def extract_data(self):
        """シミュレーション結果から必要なデータを抽出"""
        # 必要なトレースを取得
        Vds = self.raw_data['V(n002)'].data  # Vds（ドレイン-ソース電圧）
        Vgs = self.raw_data['V(n001)'].data  # Vgs（ゲート-ソース電圧）
        Id = self.raw_data['Id(J1)'].data    # Id（ドレイン電流）

        # ドレイン電流をmA単位に変換
        Id_mA = Id * 1e3
        return Vds, Vgs, Id_mA

    def plot_iv_characteristics(self, Vds, Vgs, Id_mA):
        """I-V特性をプロットする"""
        plt.figure(figsize=(8, 6))

        for vgs_value in [-0.4, -0.3, -0.2, -0.1, 0]:
            # Vgsが変化する部分のデータを抽出
            mask = (Vgs >= vgs_value - 0.05) & (Vgs <= vgs_value + 0.05)  # 小さい範囲でVgsにフィルタを適用
            plt.plot(Vds[mask], Id_mA[mask], label=f'Vgs = {vgs_value}V')

        # プロットの装飾
        plt.title("I-V Characteristic of JFET for Different Vgs")
        plt.xlabel("Vds (Volts)")
        plt.ylabel("Id (mA)")
        plt.xlim(0)
        plt.ylim(0)
        plt.grid(True)
        plt.legend()

        # 画像を保存するディレクトリがない場合は作成
        image_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'images')  # 現在のスクリプトのディレクトリを基準
        if not os.path.exists(image_dir):
            os.makedirs(image_dir)

        # 画像のファイル名をテンプレートのファイル名から生成
        image_filename = f"{os.path.splitext(os.path.basename(self.template_path))[0]}_{self.device_name}.png"
        image_path = os.path.join(image_dir, image_filename)

        # 画像を指定したパスに保存
        plt.savefig(image_path)

    def run_and_plot(self):
        """シミュレーション実行、データ取得、プロットを行う一連の流れ"""
        self.modify_netlist()
        self.run_simulation()
        Vds, Vgs, Id_mA = self.extract_data()
        self.plot_iv_characteristics(Vds, Vgs, Id_mA)


if __name__ == "__main__":

    import requests

    # モデルデータを取得するエンドポイント
    API_URL = "https://spice-model-manager.onrender.com/api/models"  # APIのURL（適宜変更してください）

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


    def main():
        # データベースからNJFおよびPJFのモデルデータを取得
        jfet_models = fetch_model_data()
        
        # 各モデルデータに対してI-V特性を生成
        for model in jfet_models:
            device_name = model["device_name"]
            spice_string = model["spice_string"]

            # JFETのI-V特性をプロット
            print(f"Generating I-V characteristics for {device_name} ({model['device_type']})")
            jfet_iv = JFET_IV_Characteristic(device_name, spice_string)
            jfet_iv.run_and_plot()


    # 使用例
    # device_name = "2sk208"
    # spice_string = ".model 2SK208 NJF Vto=-2.638 Beta=1.059m Lambda=2.8m Rs=56.63 Rd=56.63 Betatce=-.5 Vtotc=-2.5m Cgd=10.38p M=.4373 Pb=.3905 Fc=.5 Cgs=6.043p Isr=112.8p Nr=2 Is=11.28p N=1 Xti=3 Alpha=10u Vk=100 Kf=1E-18"
    # jfet_iv = JFET_IV_Characteristic(device_name, spice_string)
    # jfet_iv.run_and_plot()

    main()