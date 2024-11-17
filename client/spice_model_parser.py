import re

class SpiceModelParser:
    def __init__(self):
        self.conversion_dict = {
            'f': 'e-15',   # フェムト (femto) = 10^-15
            'p': 'e-12',   # ピコ (pico) = 10^-12
            'n': 'e-9',    # ナノ (nano) = 10^-9
            'u': 'e-6',    # マイクロ (micro) = 10^-6
            'm': 'e-3',    # ミリ (milli) = 10^-3
            'k': 'e3',     # キロ (kilo) = 10^3
            'meg': 'e6',   # メガ (mega) = 10^6
            'g': 'e9',     # ギガ (giga) = 10^9
            'T': 'e12',    # テラ (tera) = 10^12
            'da': 'e1',    # ダカ (deca) = 10^1
            'h': 'e2',     # ヘクト (hecto) = 10^2
        }

    def parse(self, model_line, convert_units=False):
        model_line = self._normalize_line(model_line)
        match = self._parse_model_line(model_line)
        if not match:
            raise SyntaxError("モデル行の形式が正しくありません。")

        device_name = match.group(1).upper()
        device_type = match.group(2).upper()
        params_str = (match.group(3) or '') + ' ' + (match.group(4) or '')

        params = self._parse_parameters(params_str, convert_units)
        params['device_name'] = device_name
        params['device_type'] = device_type

        return params

    def _normalize_line(self, model_line):
        model_line = model_line.replace('+', '').replace('\n', ' ').strip()
        model_line = model_line.replace('(', '( ').replace(')', ') ')
        return model_line

    def _parse_model_line(self, model_line):
        pattern = r'\.MODEL\s+(\S+)\s+(\S+)\s*(\(.*\))?\s*(.*)'
        return re.match(pattern, model_line, re.IGNORECASE)

    def _parse_parameters(self, params_str, convert_units):
        params = {}
        param_pattern = re.compile(r'([A-Z]+)\s*=\s*([+-]?\d*\.?\d+(?:[eEpP][+-]?\d+)?[a-zA-Z]*)', re.IGNORECASE)

        for param in param_pattern.finditer(params_str):
            key = param.group(1).upper()
            value = param.group(2).lower()

            if convert_units:
                value = self._convert_units(value)

            params[key] = value

        return params

    def _convert_units(self, value):
        for unit, factor in self.conversion_dict.items():
            if value.endswith(unit):
                value = value.replace(unit, factor)
                return float(value)
        return float(value)

    def format(self, params, format_with_parens=False, capitalize='none'):
        """パースしたパラメータを整形して出力

        Args:
            params (dict): パース結果のパラメータ辞書
            format_with_parens (bool): Trueなら括弧を含めて整形する
            capitalize (str): 'none'で変更なし、'upper'で全て大文字、'lower'で全て小文字、'first'で最初の文字だけ大文字

        Returns:
            str: 整形されたモデル行
        """
        device_name = params.get('device_name')
        device_type = params.get('device_type')

        # capitalizeオプションをデバイス名、デイバイスタイプ、.modelに適用
        if capitalize == 'upper':
            model_keyword = '.MODEL'.upper()
            device_name = device_name.upper()
            device_type = device_type.upper()
        elif capitalize == 'lower':
            model_keyword = '.model'.lower()
            device_name = device_name.lower()
            device_type = device_type.lower()
        elif capitalize == 'first':
            model_keyword = '.model'.lower()
            device_name = device_name.capitalize()
            device_type = device_type.capitalize()
        else:
            model_keyword = '.MODEL'  # デフォルトは大文字

        param_strs = []
        for key, value in params.items():
            if key not in ['device_name', 'device_type']:
                # capitalizeオプションをパラメータ名と値に適用
                if capitalize == 'first':
                    key = key.capitalize()
                    # valueが文字列の場合のみcapitalize
                    if isinstance(value, str):
                        value = value.capitalize()
                elif capitalize == 'upper':
                    key = key.upper()
                    value = value.upper() if isinstance(value, str) else value
                elif capitalize == 'lower':
                    key = key.lower()
                    value = value.lower() if isinstance(value, str) else value

                # '='の両サイドにスペースを入れない
                param_strs.append(f"{key}={value}")

        if format_with_parens:
            formatted_params = ' '.join([f"{param}" for param in param_strs])
            return f"{model_keyword} {device_name} {device_type} ({formatted_params})"
        else:
            return f"{model_keyword} {device_name} {device_type} " + ' '.join(param_strs)


if __name__ == "__main__":


    # 使用例
    parser = SpiceModelParser()

    # テストする .model 行
    model_lines = [
        ".model 2SC2240 NPN(Is=99.13f Xti=3 Eg=1.11 Vaf=422.2 Bf=352.8 Ise=1.179p Ne=1.782 Ikf=.4704 Nk=.9631 Xtb=1.5 Var=100 Br=1.663 Isc=555.1p Nc=1.796 Ikr=5.85 Rc=.2032 Cjc=7.561p Mjc=.2472 Vjc=.3905 Fc=.5 Cje=5p Mje=.3333 Vje=.75 Tr=10n Tf=1.295n Itf=1 Xtf=0 Vtf=10)",
        ".model BF862 NJF(beta= 0.049998 VTO= -0.5967 lambda= 0.036629 Rs= 7.234 Is= 9.36E-14 N= 1.245 Betatce=-.5 Vtotc=-2.0E-3 Isr=2.995p Nr=2 Xti=3 Alpha=-1.0E-3 Vk=59.97E1 Cgd=7.4002E-12 Pb=.5 Fc=.5 Cgs=8.2890E-12 Kf=87.5E-18 Af=1)",
        ".model 2SK208 NJF Vto=-2.638 Beta=1.059m Lambda=2.8m Rs=56.63 Rd=56.63 Betatce=-.5  Vtotc=-2.5m Cgd=10.38p M=.4373 Pb=.3905 Fc=.5 Cgs=6.043p Isr=112.8p Nr=2 Is=11.28p N=1 Xti=3 Alpha=10u Vk=100 Kf=1E-18"
    ]

    # 各モデル行を解析し、整形して出力
    for model_line in model_lines:
        try:
            params = parser.parse(model_line, convert_units=True)

            # 括弧なしで整形して出力（最初の文字を大文字にする）
            output_first_capitalized = parser.format(params, format_with_parens=False, capitalize='first')
            print("最初の文字を大文字:")
            print(output_first_capitalized)

            # 括弧ありで整形して出力（全て大文字）
            output_upper_case = parser.format(params, format_with_parens=True, capitalize='upper')
            print("\n全て大文字:")
            print(output_upper_case)

            # 括弧ありで整形して出力（全て小文字）
            output_lower_case = parser.format(params, format_with_parens=True, capitalize='lower')
            print("\n全て小文字:")
            print(output_lower_case)

            parseprint("\n" + "="*50 + "\n")
        
        except SyntaxError as e:
            print(f"エラー: {e}")

