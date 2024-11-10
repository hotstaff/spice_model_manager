import matplotlib.pyplot as plt
import os
from PyLTSpice import SimRunner, SpiceEditor, LTspice, RawRead

class JFET_IV_Characteristic:
    def __init__(self, device_name, spice_string, output_folder='./data', template_filename="jfet_iv.net"):
        # 初期設定
        self.device_name = device_name
        self.spice_string = spice_string
        
        # output_folderを絶対パスに変換
        self.output_folder = os.path.abspath(output_folder)
        
        # スクリプトのディレクトリを基準にテンプレートファイルのパスを設定
        script_dir = os.path.dirname(os.path.abspath(__file__))  # スクリプトの絶対パスを取得
        self.template_path = os.path.join(script_dir, 'net', template_filename)  # 'net' フォルダ内にテンプレートを配置
        
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
    # 使用例
    device_name = "2sk209"
    spice_string = ".model 2SK209 njf vto = -0.7869 beta = 0.021 lambda = 6.15e-3 rd = 12.194 rs = 16.746 is = 2.613e-15 cgd = 1.458e-11 cgs = 1.478e-11 pb = 0.3754 fc = 0.5 N = 1"
    
    jfet_iv = JFET_IV_Characteristic(device_name, spice_string)
    jfet_iv.run_and_plot()
