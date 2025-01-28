import os  # ファイルパスやディレクトリ操作
import re
import json
import itertools

import numpy as np  # 数値計算
import matplotlib.pyplot as plt  # プロットの作成

from PyLTSpice import SpiceEditor, RawRead  # PyLTSpiceライブラリの必要な機能
from bokeh.plotting import figure
from bokeh.embed import json_item


color_map = [
    '#1f77b4',  # 青
    '#ff7f0e',  # 橙
    '#2ca02c',  # 緑
    '#d62728',  # 赤
    '#9467bd',  # 紫
    '#8c564b',  # 茶
    '#e377c2',  # ピンク
    '#7f7f7f',  # 灰
    '#bcbd22',  # 黄緑
    '#17becf'   # シアン
]

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

        self.config = self._CONFIG.copy()  # インスタンスごとに設定を分離

    @classmethod
    def get_simulation_name(cls):
        return cls._SIMULATION_NAME

    @classmethod
    def show_default_config(cls):
        """クラスのデフォルト設定を表示する"""
        return cls._CONFIG

    def update_config(self, key, value):
        """設定値を動的に更新する"""
        if key in self.config:
            self.config[key] = value
        else:
            raise KeyError(f"Invalid config key: {key}")

    def get_config(self, key):
        """設定値を取得する"""
        return self.config.get(key)

    def show_config(self):
        """現在の設定を表示する"""
        return self.config

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
        plt.clf()
        plt.close()
        return image_path

    def dump_json(self, p):
        return json.dumps(json_item(p)) 

    def plot_data(self, *args):
        """データをプロットするメソッド（サブクラスで実装）"""
        raise NotImplementedError("このメソッドはサブクラスで実装してください")

    def plot(self, json=False, measurement_data=None):
        """抽出したデータをプロットし、画像ファイルのパスを返却する"""
        
        # シミュレーション結果が読み込まれていない場合、エラーを投げる
        if not self.raw_data:
            raise ValueError("シミュレーション結果が読み込まれていません")

        # データの抽出
        data = self.extract_data()

        # JSON形式でプロットを返す場合
        if json:
            p = self.plot_bokeh(*data)  # Bokehプロット作成
            if measurement_data:
                # 測定データをBokehプロットに追加
                p = self.add_measurement_data(p, measurement_data["x"], measurement_data["y"], plot_type="bokeh")
            return self.dump_json(p) # プロットをJSON形式で返す

        # 画像ファイルを保存する場合（Matplotlib）
        plt_obj = self.plot_data(*data)  # Matplotlibプロット作成
        if measurement_data:
            # 測定データをMatplotlibプロットに追加
            plt_obj = self.add_measurement_data(plt_obj, measurement_data["x"], measurement_data["y"], plot_type="matplotlib")
        
        # 画像ファイルとして保存して返す
        return self.save_image(plt_obj)


    def add_measurement_data(self, p, x, y, color="black", legend_label="Measured Data", plot_type="bokeh"):
        """測定データをプロットに追加 (Bokeh または Matplotlib で対応)"""
        if plot_type == "bokeh":
            p.scatter(x, y, size=8, color=color, legend_label=legend_label)
        elif plot_type == "matplotlib":
            if isinstance(p, plt.Axes):  # Matplotlib のプロットオブジェクトを確認
                p.scatter(x, y, s=8**2, c=color, label=legend_label)  # s は面積で指定
                p.legend(title="Legend")
            else:
                raise ValueError("Matplotlib のプロットオブジェクトを渡してください。")
        else:
            raise ValueError("サポートされていない plot_type が指定されました。'bokeh' または 'matplotlib' を選択してください。")
        
        return p

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

    _CONFIG = {
        "VGS_ABSMAX": 0.4,
        "VGS_STEP": 0.1,
        "VDS_ABSMAX": 20,
        "VDS_STEP": 0.1
    }

    def modify_netlist(self):
        super().modify_netlist()

        # DC sweep
        vgs_absmax = self.get_config("VGS_ABSMAX")
        vgs_step = self.get_config("VGS_STEP")
        vds_absmax = self.get_config("VDS_ABSMAX")
        vds_step = self.get_config("VDS_STEP")

        if self.device_type == 'NJF':
            self.net.add_instructions(
                f'.dc V1 -{vgs_absmax} 0 {vgs_step} V2 0 {vds_absmax} {vds_step}'
            )
        elif self.device_type == 'PJF':
            self.net.add_instructions(
                f'.dc V1 0 {vgs_absmax} {vgs_step} V2 0 -{vds_absmax} -{vds_step}'
            )

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

        vgs_absmax = self.get_config("VGS_ABSMAX")
        vgs_step = self.get_config("VGS_STEP")

        if self.device_type == 'NJF':
            vgs_list = np.linspace(-vgs_absmax, 0, int(vgs_absmax / vgs_step) + 1)  # -vgs_absmaxから0までの範囲
        elif self.device_type == 'PJF':
            vgs_list = np.linspace(vgs_absmax, 0, int(vgs_absmax / vgs_step) + 1)  # vgs_absmaxから0までの範囲

        color_cycle = itertools.cycle(color_map)

        for vgs_value in vgs_list:
            color = next(color_cycle)
            mask = (Vgs >= vgs_value - vgs_step / 2) & (Vgs <= vgs_value + vgs_step / 2)
            plt.plot(Vds[mask], Id_mA[mask], color=color, label=f'Vgs = {vgs_value:.2f}V')

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

        return plt

    def plot_bokeh(self, Vds, Vgs, Id_mA):
        """I-V特性をBokehでプロットし、JSONデータとして返す"""
        p = figure(
            title="I-V Characteristic of JFET for Different Vgs",
            x_axis_label='Vds (Volts)',
            y_axis_label='Id (mA)',
            width=800, height=600
        )

        # Vgsのリスト
        vgs_absmax = self.get_config("VGS_ABSMAX")
        vgs_step = self.get_config("VGS_STEP")

        if self.device_type == 'NJF':
            vgs_list = np.linspace(-vgs_absmax, 0, int(vgs_absmax / vgs_step) + 1)  # -vgs_absmaxから0までの範囲
        elif self.device_type == 'PJF':
            vgs_list = np.linspace(vgs_absmax, 0, int(vgs_absmax / vgs_step) + 1)  # vgs_absmaxから0までの範囲

        color_cycle = itertools.cycle(color_map)

        # Vgsごとにプロット
        for vgs_value in vgs_list:
            color = next(color_cycle)
            mask = (Vgs >= vgs_value - vgs_step / 2) & (Vgs <= vgs_value + vgs_step / 2)
            p.line(Vds[mask], Id_mA[mask], legend_label=f'Vgs = {vgs_value:.2f}V', line_width=2, color=color)

        if self.device_type == 'PJF':
            p.x_range.flipped = True
            p.y_range.flipped = True

        p.legend.title = "Vgs"
        p.legend.location = "bottom_right"

        return p

class JFET_Vgs_Id_Characteristic(JFET_SimulationBase):

    _SIMULATION_NAME = 'vgs_id'

    _CONFIG = {
        "VGS_ABSMAX": 3,
        "VGS_STEP": 0.01,
        "VDS_ABS": 10,
    }

    def modify_netlist(self):
        super().modify_netlist()

        vds_abs = self.get_config("VDS_ABS")
        vgs_absmax = self.get_config("VGS_ABSMAX")
        vgs_step = self.get_config("VGS_STEP")

        # DC sweep
        if self.device_type == 'NJF':
            self.net.set_element_model('V2',f'DC {vds_abs}')
            self.net.add_instructions(f'.dc V1 -{vgs_absmax} 0 {vgs_step}')
        elif self.device_type == 'PJF':
            self.net.set_element_model(f'V2',f'DC -{vds_abs}')
            self.net.add_instructions(f'.dc V1 0 {vgs_absmax} {vgs_step}')

    def extract_data(self):
        """VgsとIdの関係を抽出"""
        Vgs = self.raw_data['V(n001)'].data  # Vgs（ゲート-ソース電圧）
        Id = self.raw_data['Id(J1)'].data    # Id（ドレイン電流）
        Id_mA = Id * 1e3  # ドレイン電流をmA単位に変換
        return Vgs, Id_mA

    def plot_data(self, Vgs, Id_mA):
        """VgsとIdの特性をプロットする"""
        vgs_absmax = self.get_config("VGS_ABSMAX")

        plt.figure(figsize=(8, 6))
        plt.plot(Vgs, Id_mA, label=f'Id vs Vgs')

        plt.title("Vgs-Id Characteristic of JFET")
        plt.xlabel("Vgs (Volts)")
        plt.ylabel("Id (mA)")

        if self.device_type == 'PJF':
            plt.gca().invert_xaxis()
            plt.gca().invert_yaxis()
            plt.xlim(vgs_absmax, 0)
        elif self.device_type == 'NJF':
            plt.xlim(-vgs_absmax, 0)

        plt.ylim(0)
        plt.grid(True)
        plt.legend()

        return plt

    def plot_bokeh(self, Vgs, Id_mA):
        """VgsとIdの特性をBokehでプロットし、JSONデータとして返す"""
        p = figure(
            title="Vgs-Id Characteristic of JFET",
            x_axis_label='Vgs (Volts)',
            y_axis_label='Id (mA)',
            width=800, height=600
        )

        # VgsとIdをプロット
        p.line(Vgs, Id_mA, legend_label="Id vs Vgs", line_width=2, color="blue")

        # VGS_ABSMAXを取得
        vgs_absmax = self.get_config("VGS_ABSMAX")

        # デバイスタイプに応じて範囲を設定
        if self.device_type == 'PJF':
            p.y_range.flipped = True
            p.x_range.start = vgs_absmax
            p.x_range.end = 0
        elif self.device_type == 'NJF':
            p.x_range.start = -vgs_absmax
            p.x_range.end = 0

        p.legend.title = "Vgs"
        p.legend.location = "top_left"

        return p



class JFET_Gm_Vgs_Characteristic(JFET_SimulationBase):

    _SIMULATION_NAME = 'gm_vgs'

    _CONFIG = {
        "VGS_ABSMAX": 3,
        "VGS_STEP": 0.001,
        "VDS_ABS": 10,
    }

    def modify_netlist(self):
        super().modify_netlist()

        vds_abs = self.get_config("VDS_ABS")
        vgs_absmax = self.get_config("VGS_ABSMAX")
        vgs_step = self.get_config("VGS_STEP")

        # DC sweep
        if self.device_type == 'NJF':
            self.net.set_element_model('V2',f"DC {vds_abs}")
            self.net.add_instructions(f'.dc V1 -{vgs_absmax} 0 {vgs_step}')
        elif self.device_type == 'PJF':
            self.net.set_element_model('V2',f"DC -{vds_abs}")
            self.net.add_instructions(f'.dc V1 0 {vgs_absmax} {vgs_step}')

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

        vgs_absmax = self.get_config("VGS_ABSMAX")

        if self.device_type == 'PJF':
            plt.gca().invert_xaxis()
            plt.xlim(vgs_absmax, 0)
        elif self.device_type == 'NJF':
            plt.xlim(-vgs_absmax, 0)

        plt.ylim(0)
        plt.grid(True)
        plt.legend()

        return plt

    def plot_bokeh(self, Vgs, gm):
        """gm-Vgs特性をBokehでプロットし、JSONデータとして返す"""
        p = figure(
            title="gm-Vgs Characteristic of JFET",
            x_axis_label='Vgs (Volts)',
            y_axis_label='gm (mS)',
            width=800, height=600
        )

        # gm-Vgsをプロット
        p.line(Vgs, gm, legend_label="gm vs Vgs", line_width=2, color="blue")

        vgs_absmax = self.get_config("VGS_ABSMAX")

        if self.device_type == 'PJF':
            p.x_range.start = vgs_absmax
            p.x_range.end = 0
        elif self.device_type == 'NJF':
            p.x_range.start = -vgs_absmax
            p.x_range.end = 0

        p.legend.title = "Vgs"
        p.legend.location = "top_left"

        return p


class JFET_Gm_Id_Characteristic(JFET_SimulationBase):

    _SIMULATION_NAME = 'gm_id'

    _CONFIG = {
        "VGS_ABSMAX": 3,
        "VGS_STEP": 0.001,
        "VDS_ABS": 10,
    }

    def modify_netlist(self):
        super().modify_netlist()

        vds_abs = self.get_config("VDS_ABS")
        vgs_absmax = self.get_config("VGS_ABSMAX")
        vgs_step = self.get_config("VGS_STEP")

        # DC sweep
        if self.device_type == 'NJF':
            self.net.set_element_model('V2',f"DC {vds_abs}")
            self.net.add_instructions(f'.dc V1 -{vgs_absmax} 0 {vgs_step}')
        elif self.device_type == 'PJF':
            self.net.set_element_model('V2',f"DC -{vds_abs}")
            self.net.add_instructions(f'.dc V1 0 {vgs_absmax} {vgs_step}')

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

        return plt


    def plot_bokeh(self, Id_mA, gm):
        """gm-Id特性をBokehでプロットし、JSONデータとして返す"""
        p = figure(
            title="gm-Id Characteristic of JFET",
            x_axis_label='Id (mA)',
            y_axis_label='gm (mS)',
            width=800, height=600
        )

        # gm-Idをプロット（絶対値gmを使用）
        p.line(Id_mA, np.abs(gm), legend_label="gm vs Id", line_width=2, color="green")

        if self.device_type == 'PJF':
            p.x_range.flipped = True
            p.x_range.start = max(Id_mA)
            p.x_range.end = min(Id_mA)
        elif self.device_type == 'NJF':
            p.x_range.start = min(Id_mA)
            p.x_range.end = max(Id_mA)

        p.y_range.start = min(np.abs(gm))
        p.y_range.end = max(np.abs(gm))

        p.legend.title = "Id"
        p.legend.location = "top_left"

        return p
