import re

class LTspiceModelParser:
    def __init__(self, spice_string):
        """LTspiceモデル文字列を受け取り、パース処理を行うクラス"""
        self.spice_string = spice_string
        self.params = self.parse_ltspice_model(spice_string)
    
    def parse_ltspice_model(self, model_line, convert_units=False):
        """LTspiceのモデル行をパースして辞書を返す

        Args:
            model_line (str): LTspiceモデル行の文字列
            convert_units (bool): Trueの場合、数値変換と単位変換を行う

        Returns:
            dict: パース結果を辞書形式で返す
        """
        model_line = model_line.replace('+', '').replace('\n', ' ').strip()
        model_line = model_line.replace('(', '(  ').replace(')', ')  ')  # 括弧を取り除く

        pattern = r'\.MODEL\s+(\S+)\s+(\S+)\s*(\(.*\))?\s*(.*)'  
        match = re.match(pattern, model_line, re.IGNORECASE)

        if not match:
            raise SyntaxError("モデル行の形式が正しくありません。")

        device_name = match.group(1).upper()
        device_type = match.group(2).upper().split('(')[0]
        params_str = (match.group(3) or '') + ' ' + (match.group(4) or '')

        params_str = params_str.replace('(', '').replace(')', '')  # 括弧を取り除く

        params = {}
        param_pattern = re.compile(r'([A-Z]+)\s*=\s*([+-]?\d*\.?\d+(?:[eEpP][+-]?\d+)?[a-zA-Z]*)', re.IGNORECASE)
        
        for param in param_pattern.finditer(params_str):
            key = param.group(1).upper()
            value = param.group(2).lower()  # そのまま文字列として保持

            if convert_units:
                # 単位変換が必要な場合、変換テーブルで置換
                conversion_dict = {
                    'p': 'e-12', 'n': 'e-9', 'u': 'e-6', 'm': 'e-3',
                    'k': 'e3', 'meg': 'e6', 'g': 'e9'
                }
                for unit, factor in conversion_dict.items():
                    if value.endswith(unit):
                        value = value.replace(unit, factor)
                        value = float(value)  # 数値に変換
                        break
            params[key] = value  # 単位の有無に関係なく保存

        params['device_name'] = device_name
        params['device_type'] = device_type

        return params

    def calculate_gm(self, Vgs):
        """トランスコンダクタンス g_m の計算
        
        Args:
            Vgs (float): ゲート-ソース電圧 (V)
        
        Returns:
            float: トランスコンダクタンス g_m
        """
        Vto = float(self.params.get('VTO', -2.638))  # Vto (しきい値電圧)
        beta = float(self.params.get('BETA', 1.059e-3))  # Beta
        if Vgs <= Vto:
            return 0
        return beta * (Vgs - Vto)

    def calculate_Id(self, Vgs, Vds):
        """ドレイン電流 I_D の計算
        
        Args:
            Vgs (float): ゲート-ソース電圧 (V)
            Vds (float): ドレイン-ソース電圧 (V)
        
        Returns:
            float: ドレイン電流 I_D
        """
        Vto = float(self.params.get('VTO', -2.638))  # Vto (しきい値電圧)
        beta = float(self.params.get('BETA', 1.059e-3))  # Beta
        lambda_ = float(self.params.get('LAMBDA', 2.8e-3))  # Lambda (チャネル長変調係数)
        if Vgs <= Vto:
            return 0
        Id = beta * (Vgs - Vto)**2 * (1 + lambda_ * Vds)
        return Id

    def calculate_ro(self, Id):
        """出力インピーダンス r_o の計算
        
        Args:
            Id (float): ドレイン電流 I_D (A)
        
        Returns:
            float: 出力インピーダンス r_o (Ω)
        """
        lambda_ = float(self.params.get('LAMBDA', 2.8e-3))  # Lambda
        if Id == 0:
            return float('inf')
        return 1 / (lambda_ * Id)

    def calculate_IDSS(self):
        """ドレイン飽和電流 I_DSS の計算
        
        Returns:
            float: ドレイン飽和電流 I_DSS (A)
        """
        Vgs = 0  # Vgsが0のときのI_DSS
        Vto = float(self.params.get('VTO', -2.638))  # Vto (しきい値電圧)
        beta = float(self.params.get('BETA', 1.059e-3))  # Beta
        return beta * (Vgs - Vto)**2

# 使用例:
spice_model_line = ".model 2SK209 njf vto = -0.7869 beta = 0.021 lambda = 6.15e-3 rd = 12.194 rs = 16.746 is = 2.613e-15 cgd = 1.458e-11 cgs = 1.478e-11 pb = 0.3754 fc = 0.5 N = 1"
parser = LTspiceModelParser(spice_model_line)

Vgs = 0.0  # ゲート-ソース電圧 (V)
Vds = 10.0  # ドレイン-ソース電圧 (V)

gm = parser.calculate_gm(Vgs)
Id = parser.calculate_Id(Vgs, Vds)
ro = parser.calculate_ro(Id)
IDSS = parser.calculate_IDSS()

print(f"Transconductance (g_m): {gm * 1E3} mS")
print(f"Drain current (I_D): {Id * 1E3} mA")
print(f"Output impedance (r_o): {ro} Ω")
print(f"Drain saturation current (I_DSS): {IDSS * 1E3} mA")
