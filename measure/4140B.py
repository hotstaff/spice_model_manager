# import pyvisa

class HP4140B:

    config_options = {
        "FUNCTION":{
            "I": "F1",
            "I-V": "F2",
            "C-V": "F3",
            "HSI": "F4"
        },
        "RANGE":{
            "HOLD": "RA0",
            "AUTO": "RA1",
            "10^-2": "R02",
            "10^-3": "R03",
            "10^-4": "R04",
            "10^-5": "R05",
            "10^-6": "R06",
            "10^-7": "R07",
            "10^-8": "R08",
            "10^-9": "R09",
            "10^-10": "R10",
            "10^-11": "R11",
            "10^-12": "R12"
        },
        "LIMIT_AUTO_RANGE":{
            "10^-2": "H02",
            "10^-3": "H03",
            "10^-4": "H04",
            "10^-5": "H05",
            "10^-6": "H06",
            "10^-7": "H07",
            "10^-8": "H08",
            "10^-9": "H09",
            "10^-10": "H10",
            "10^-11": "H11",
            "10^-12": "H12"
        },
        "INTEGRATION_TIME": {
            "SHORT": "I1",
            "MEDIUM": "I2",
            "LONG": "I3"
        },
        "FILTER": {
            "OFF": "J0",
            "ON": "J1"
        },
        "I_TRIG": {
            "INT": "T1",
            "EXT/MAN": "T2"
        },
        "C\% Enable":{
            "pF": "C0",
            "%": "C1"
        },
        "SWEEP_CONTROL":{
            "AUTO": "W1",
            "MANUAL": "W2",
            "PAUSE": "W3",
            "RESTART": "W4",
            "Down": "W5",
            "Up": "W6",
            "ABORT": "W7"
        },
        "VA_MODE":{
            "SINGLE_RAMP": "A1",
            "DOBLE_RAMP": "A2",
            "SINGLE_STAIRCASE": "A3",
            "DOBLE_STAIRCASE": "A4",
            "DC": "A5",
            "OFF": "A6"
        },
        "VB_MODE":{
            "DC": "B1",
            "OFF": "B2"
        },
        "VA_I_LIMIT":{
            "100uA": "L1",
            "1mA": "L2",
            "10mA": "L3"
        },
        "VB_I_LIMIT":{
            "100uA": "M1",
            "1mA": "M2",
            "10mA": "M3"
        },
        "SELF_TEST":{
            "OFF": "S0",
            "ON": "S1"
        },
        "SRQ_MASK":{
            "OFF": "D0",
            "ON (1)": "D1",
            "ON (2)": "D2",
            "ON (1, 2)": "D3",
            "ON (3)": "D4",
            "ON (1, 3)": "D5",
            "ON (2, 3)": "D6",
            "ON (ALL)": "D7"
        },
        "TRIGGER":"E",
        "ZERO_SET": "Z",
        "KEY_STATUS": "K",
        "RECORDER": {
            "LL": "XL",
            "ZERO": "XZ",
            "UR": "XR"
        }

    }


    def __init__(self, resource: str):
        """HP4140Bの制御クラス"""
        # self.rm = pyvisa.ResourceManager()
        # self.inst = self.rm.open_resource(resource)
        self.settings = {}

    def set_parameter(self, key: str, value: str):
        """2文字以上の設定を辞書で管理"""
        if not isinstance(value, str):
            raise ValueError("コマンドは文字列で指定してください")
        self.settings[key] = value

    def build_command(self) -> str:
        """設定内容からコマンドを構築"""
        return "".join(self.settings.values())

    def apply_settings(self):
        """構築したコマンドを送信"""
        command = self.build_command()
        # self.inst.write(command)
        print(f"Sent Command: {command}")  # デバッグ用

    def interactive_setup(self):
        """対話式に設定を行う"""
        print("HP4140Bの設定を対話的に入力します。")
        for category, options in self.config_options.items():
            if isinstance(options, dict):
                # 選択肢がある場合
                print(f"\n{category} の選択肢:")
                option_list = list(options.items())
                for i, (option_name, command) in enumerate(option_list, 1):
                    print(f"  {i}. {option_name} -> {command}")

                while True:
                    user_input = input(f"{category} の番号を選択してください: ").strip()
                    if user_input.isdigit():
                        index = int(user_input) - 1
                        if 0 <= index < len(option_list):
                            selected_option = option_list[index][1]
                            self.set_parameter(category, selected_option)
                            break
                    print("無効な選択です。もう一度入力してください。")
            else:
                # 単独の設定（例: "TRIGGER": "E"）
                print(f"\n{category} は {options} に設定されます。")
                self.set_parameter(category, options)


    def reset(self):
        """リセットコマンドを送信"""
        self.inst.write("RS;")

    def close(self):
        """通信を閉じる"""
        self.inst.close()



hp4140b = HP4140B("GPIB0::22::INSTR")

# 対話式で設定
hp4140b.interactive_setup()

# 一括送信
hp4140b.apply_settings()

# 終了
hp4140b.close()
