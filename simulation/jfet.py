import os  # ファイルパスやディレクトリ操作
import re
import numpy as np  # 数値計算
import matplotlib.pyplot as plt  # プロットの作成
from PyLTSpice import SpiceEditor, RawRead  # PyLTSpiceライブラリの必要な機能

from bokeh.plotting import figure
from bokeh.embed import json_item
import json

class JFET_SimulationBase:

    VALID_TYPES = ["NJF", "PJF"]
    _SIMULATION_NAME = 'jfet_dc'  # default

    def __init__(self, device_name, device_type, spice_string):
        self.device_name = device_name
        self.device_type = device_type
        self.spice_string = spice_string
        self.simulation_name = self._SIMULATION_NAME

        script_dir = os.path.dirname(os.path.abspath(__file__))  # スクリプトの絶対パスを取得
        self.template_path = os.path.join(script_dir, 'net', 'jfet_dc.net')  # テンプレートファイルのパス
        self.output_folder = os.path.join(script_dir, 'data')

        self.net = None
        self.raw_data = None
        self.log_data = None

    def modify_netlist(self):
        """JFETのモデルを交換する(共通の動作)"""
        self.net = SpiceEditor(self.template_path)
        self.net.set_component_value('J1', self.device_name)
        self.net.add_instructions(self.spice_string)

    def build(self):
        self.modify_netlist()
        run_filename = f"{self.simulation_name}_{self.device_name}.net"
        netlist_path = os.path.join(self.output_folder, run_filename)
        self.net.save_netlist(netlist_path)

        return netlist_path

    def load_results(self, raw_file, log_file):
        """外部で実行されたシミュレーション結果を読み込む"""
        self.raw_data = RawRead(raw_file)
        with open(log_file, 'r') as log:
            self.log_data = log.read()

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

    def plot(self, json=False):
        """抽出したデータをプロットし、画像ファイルのパスを返却する"""
        if not self.raw_data:
            raise ValueError("シミュレーション結果が読み込まれていません")

        data = self.extract_data()
        try:
            if json:
                return self.get_json(*data)
            else:
                return self.plot_data(*data)
        finally:
            plt.close('all')  # メモリを解放

    def plot_data(self, *args):
        """データをプロットするメソッド（サブクラスで実装）"""
        raise NotImplementedError("このメソッドはサブクラスで実装してください")


class JFET_Basic_Performance(JFET_SimulationBase):

    _SIMULATION_NAME = 'basic_performance'

    def modify_netlist(self):
        super().modify_netlist()

        if self.device_type == 'NJF':
            self.net.set_element_model('V2', "DC 10")
        elif self.device_type == 'PJF':
            self.net.set_element_model('V2', "DC -10")

        # .op解析（定常状態解析）
        self.net.add_instructions('.op')

    def extract_data(self, include_units=True):
        """.logファイルから基本性能指標に必要なデータを抽出"""
        performance_data = {}

        # .logファイルの内容を読み込む
        log_content = self.log_data

        # 正規表現を使って必要な性能指標を抽出
        patterns = {
            'id': r"Id:\s+([\d\.\-e\+]+)",  # "Id: 1.34e-02" の形式
            'vgs': r"Vgs:\s+([\d\.\-e\+]+)",  # "Vgs: 0.00e+00" の形式
            'vds': r"Vds:\s+([\d\.\-e\+]+)",  # "Vds: 1.00e+01" の形式
            'gm': r"Gm:\s+([\d\.\-e\+]+)",  # "Gm: 3.83e-02" の形式
            'gds': r"Gds:\s+([\d\.\-e\+]+)",  # "Gds: 3.22e-05" の形式
            'cgs': r"Cgs:\s+([\d\.\-e\+]+)",  # "Cgs: 1.34e-11" の形式
            'cgd': r"Cgd:\s+([\d\.\-e\+]+)"  # "Cgd: 3.27e-12" の形式
        }

        for key, pattern in patterns.items():
            match = re.search(pattern, log_content)
            if match:
                value = float(match.group(1))
                if key == 'id':
                    performance_data[key] = value * 1e3  # ミリアンペアに変換
                elif key == 'vgs' or key == 'vds':
                    performance_data[key] = value  # ボルトに変換
                elif key == 'gm':
                    performance_data[key] = value * 1e3  # ミリジーメンスに変換
                elif key == 'gds':
                    performance_data[key] = value * 1e3  # ミリジーメンスに変換
                elif key == 'cgs' or key == 'cgd':
                    performance_data[key] = value * 1e12  # ピコファラッドに変換

        # 単位を含める場合
        if include_units:
            for key in performance_data:
                if key == 'id':
                    performance_data[key] = f"{performance_data[key]:.2f} mA"
                elif key == 'vgs' or key == 'vds':
                    performance_data[key] = f"{performance_data[key]:.2f} V"
                elif key == 'gm':
                    performance_data[key] = f"{performance_data[key]:.2f} mS"
                elif key == 'gds':
                    performance_data[key] = f"{performance_data[key]:.2f} mS"
                elif key == 'cgs' or key == 'cgd':
                    performance_data[key] = f"{performance_data[key]:.2f} pF"

        return performance_data

    def get_basic_performance(self, include_units=False):
        """基本性能指標を返す"""
        if not self.log_data:
            raise ValueError("シミュレーション結果が読み込まれていません")

        data = self.extract_data(include_units=include_units)
        return data


class JFET_IV_Characteristic(JFET_SimulationBase):

    _SIMULATION_NAME = 'iv'

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

    def plot_data(self, Vds, Vgs, Id_mA):
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

    def get_json(self, Vds, Vgs, Id_mA):
        """I-V特性をBokehでプロットし、JSONデータとして返す"""
        p = figure(
            title="I-V Characteristic of JFET for Different Vgs",
            x_axis_label='Vds (Volts)',
            y_axis_label='Id (mA)',
            width=800, height=600
        )

        # Vgsのリストと色のリスト
        if self.device_type == 'NJF':
            vgs_list = [-0.4, -0.3, -0.2, -0.1, 0]
            colors = ["blue", "green", "cyan", "orange", "red"]  # 色のリスト（黄色をcyanに変更）
        elif self.device_type == 'PJF':
            vgs_list = [0.4, 0.3, 0.2, 0.1, 0]
            colors = ["red", "orange", "cyan", "green", "blue"]  # 色のリスト（黄色をcyanに変更）

        # Vgsごとにプロット
        for vgs_value, color in zip(vgs_list, colors):
            mask = (Vgs >= vgs_value - 0.05) & (Vgs <= vgs_value + 0.05)
            p.line(Vds[mask], Id_mA[mask], legend_label=f'Vgs = {vgs_value}V', line_width=2, color=color)

        p.legend.title = "Vgs"
        p.legend.location = "top_left"

        # プロットデータをJSON形式でエクスポート
        plot_json = json.dumps(json_item(p))

        # JSONデータを返す
        return plot_json

class JFET_Vgs_Id_Characteristic(JFET_SimulationBase):

    _SIMULATION_NAME = 'vgs_id'

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

    def plot_data(self, Vgs, Id_mA):
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

    _SIMULATION_NAME = 'gm_vgs'

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

    def plot_data(self, Vgs, gm):
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

    _SIMULATION_NAME = 'gm_id'

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

    def plot_data(self, Id_mA, gm):
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
