import os
import numpy as np
import matplotlib.pyplot as plt
import subprocess
from jinja2 import Environment, FileSystemLoader

class JFETSimulator:
    def __init__(self, device_name, spice_string, image_save_path='./images'):
        self.device_name = device_name
        self.spice_string = spice_string
        self.image_save_path = image_save_path
        self.root_dir = os.path.dirname(os.path.abspath(__file__))
        self.template_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'templates')

    def create_cir_file(self, template_name, output_filename):
        """
        Jinja2テンプレートを使って.cirファイルを動的に生成する。
        """
        # Jinja2環境設定
        env = Environment(loader=FileSystemLoader(self.template_dir))  # テンプレートを格納するディレクトリ
        try:
            template = env.get_template(template_name)  # テンプレートファイル名
        except Exception as e:
            print(f"Error loading template: {e}")
            exit(1)

        # テンプレートをレンダリングして.cirファイルを作成
        rendered_text = template.render(device_name=self.device_name, spice_string=self.spice_string)
        print(rendered_text)

        # ファイルに保存
        with open(output_filename, 'w') as f:
            f.write(rendered_text)
        print(f"{output_filename} file created.")

    def run_ngspice_simulation(self, cir_file, output_file):
        """
        指定された回路ファイルを使用してngspiceシミュレーションを実行し、結果を出力ファイルに保存する。
        """
        try:
            # ngspiceをバッチモードで実行
            subprocess.run(['ngspice', '-b', cir_file], check=True)
            
            if os.path.exists(output_file):
                print(f"Simulation completed successfully. Data saved to {output_file}.")
                return
            else:
                print(f"Warning: Expected output file {output_file} was not created.")

        except subprocess.CalledProcessError:
            print("Error: ngspice simulation failed.")
            exit(1)

    def extract_idss(self, file_path):
        """
        シミュレーション結果ファイルからIDSSを抽出
        """
        with open(file_path, 'r') as file:
            for line in file:
                if line.startswith('V(1)') or not line.strip():
                    continue
                
                data = line.split()
                try:
                    vds = float(data[0])
                    if abs(vds - 10.0) < 1e-1:
                        return float(data[3]) * 1000  # IDSSをmA単位で返す
                except ValueError:
                    continue

        raise ValueError("IDSS not found in the data.")

    def plot_iv_curve(self, data_file, output_image_file):
        """
        シミュレーション結果を読み込み、JFET IVカーブをプロットして画像ファイルとして保存する。
        """
        column_VDS = 1
        column_ID = 3
        column_VGS = 5

        # データファイルの読み込み（1行目をスキップ）
        data = np.loadtxt(data_file, skiprows=1)

        # VGSが非常に小さい場合、0Vとみなす閾値を設定
        threshold = 1e-10
        data[:, column_VGS] = np.where(np.abs(data[:, column_VGS]) < threshold, 0, data[:, column_VGS])

        # VGSごとのユニークな値を抽出
        VGS_values = np.unique(data[:, column_VGS])  # VGSは3列目に格納されていると仮定

        # 色の設定（識別しやすい色）
        colors = plt.cm.tab20(np.linspace(0, 1, len(VGS_values)))  # tab20カラーマップを使用

        # プロットの準備
        plt.figure(figsize=(8, 6))

        # 各VGSごとにプロット
        for i, VGS in enumerate(VGS_values):
            # VGSが一致するデータを抽出
            VDS = data[data[:, column_VGS] == VGS, column_VDS]
            ID = -data[data[:, column_VGS] == VGS, column_ID]  
            
            # IDをmAに変換 (1A = 1000mA)
            ID_mA = ID * 1000  # AからmAに変換

            # プロット（色を指定）
            plt.plot(VDS, ID_mA, label=f'VGS = {VGS}V', color=colors[i])

        # グラフのラベル設定
        plt.xlabel('VDS (V)', fontsize=12)
        plt.ylabel('Drain Current ID (mA)', fontsize=12)
        plt.title('JFET IV Curve for Different VGS', fontsize=14)
        plt.legend(title='VGS Values', loc='best')
        plt.grid(True)

        # 画像ファイルとして保存
        plt.savefig(output_image_file)
        print(f"Image saved as {output_image_file}")

        # グラフの描画を閉じる（次のプロットのため）
        plt.close()

    def main_idss(self):
        output_file = os.path.join(self.root_dir, './data/jfet_idss_data.dat')  # 結果を保存するデータファイル名
        cir_file = os.path.join(self.root_dir, 'cir/jfet_idss.cir')

        # .cirファイルを動的に生成
        self.create_cir_file('jfet_idss.cir.jinja', cir_file)

        # ngspiceシミュレーションの実行
        self.run_ngspice_simulation(cir_file, output_file)

        # IDSSの抽出
        try:
            idss_value = self.extract_idss(output_file)
            print(f"IDSS = {idss_value} mA")
            return idss_value
        except ValueError as e:
            print(e)

    def main_iv_curve(self):
        output_file = os.path.join(self.root_dir, 'data/jfet_iv_curve_data.dat')  # 結果を保存するデータファイル名
        cir_file = os.path.join(self.root_dir, 'cir/jfet_iv_curve.cir')

        # .cirファイルを動的に生成
        self.create_cir_file('jfet_iv_curve.cir.jinja', cir_file)

        # ngspiceシミュレーションの実行
        self.run_ngspice_simulation(cir_file, output_file)

        # シミュレーション結果のプロット
        self.plot_iv_curve(output_file, self.image_save_path)


if __name__ == '__main__':

    def test_jfet_simulation():
        # JFETデバイスの情報
        device_name = "2sk170"
        spice_string = ".model 2sk170 njf vto=-0.5211 beta=0.03683 lambda=0.004829 is=1e-09 rd=0.0 rs=0.0 cgs=5.647e-11 cgd=2.562e-11 pb=4.86 fc=0.5"
        image_save_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), f'images/jfet_iv_curve_{device_name}.png')

        # JFETシミュレータインスタンスを作成
        simulator = JFETSimulator(device_name, spice_string, image_save_path)

        # IVカーブをプロットして画像を保存
        simulator.main_iv_curve()


    test_jfet_simulation()  # テスト実行
