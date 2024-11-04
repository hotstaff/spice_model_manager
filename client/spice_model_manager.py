import os
import re

import pandas as pd
from PyQt5.QtGui import QGuiApplication, QFont
from PyQt5.QtWidgets import (QApplication, QCheckBox, QLabel, QLineEdit, 
                             QMainWindow, QPushButton, QTableWidget, 
                             QTableWidgetItem, QVBoxLayout, QHBoxLayout, 
                             QWidget, QMessageBox, QComboBox)

from PyQt5.QtCore import Qt
import requests
import pandas as pd
import re

class ModelManager:
    def __init__(self, main_window):
        self.df = pd.DataFrame()
        self.main_window = main_window
        self.table_window = None
        self.load_from_api()  # APIからデータを読み込む

    def load_from_api(self):
        try:
            response = requests.get('https://spice-model-manager.onrender.com/api/models')
            response.raise_for_status()  # HTTPエラーがあれば例外を発生させる
            self.df = pd.DataFrame(response.json())
        except requests.RequestException as e:
            QMessageBox.warning(self.main_window, "エラー", f"データの取得に失敗しました: {e}")

    def save_to_api(self):
        for _, row in self.df.iterrows():
            response = requests.post('https://spice-model-manager.onrender.com/api/models', json=row.to_dict())
            response.raise_for_status()  # エラーをチェック

    def parse_ltspice_model(self, model_line):
        model_line = model_line.replace('+', '').replace('\n', ' ').strip()
        pattern = r'\.MODEL\s+(\S+)\s+(\S+)\s*(\(.*)?(.*)'
        match = re.match(pattern, model_line, re.IGNORECASE)

        if not match:
            raise SyntaxError("モデル行の形式が正しくありません。")

        device_name = match.group(1).upper()
        device_type = match.group(2).upper().split('(')[0]
        params_str = match.group(3) + ' ' + match.group(4) if match.group(3) else match.group(4)

        params = {}
        param_pattern = re.compile(r'([A-Z]+)\s*=\s*([+-]?\d*\.?\d+(?:[eEpP][+-]?\d+)?)', re.IGNORECASE)
        for param in param_pattern.finditer(params_str):
            key = param.group(1).upper()
            value = float(param.group(2).replace('p', 'e-12').replace('n', 'e-9').replace('u', 'e-6').replace('m', 'e-3').replace('k', 'e3'))
            params[key] = value

        params['DEVICE_NAME'] = device_name
        params['DEVICE_TYPE'] = device_type

        return params

    def add_model(self, model_line):
        params = self.parse_ltspice_model(model_line)

        device_name = params['DEVICE_NAME']
        if 'DEVICE_NAME' in self.df.columns and device_name in self.df['DEVICE_NAME'].values:
            reply = QMessageBox.question(
                self.main_window, '上書き確認', f"{device_name} は既に登録されています。上書きしますか？",
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No
            )
            if reply == QMessageBox.No:
                return False

        for key in params.keys():
            if key not in self.df.columns:
                self.df[key] = None

        self.df = self.df[self.df['DEVICE_NAME'] != device_name]
        self.df = pd.concat([self.df, pd.DataFrame([params])], ignore_index=True)

        self.save_to_api()  # APIに保存
        return True

    def get_device_list(self):
        return self.df['DEVICE_NAME'].tolist() if not self.df.empty else []

    def get_spice_string(self, device_name, multiline=False):
        device_row = self.df[self.df['DEVICE_NAME'] == device_name]
        if not device_row.empty:
            params = device_row.iloc[0]
            spice_string = f".MODEL {params['DEVICE_NAME']} {params['DEVICE_TYPE']} "
            
            # パラメータ部分を生成
            param_str = self.generate_param_string(params)
            
            if multiline:
                spice_string += self.format_multiline(param_str)
            else:
                spice_string += param_str

            return spice_string
        return ""

    def generate_param_string(self, params):
        return " ".join(f"{k}={v}" for k, v in params.items() 
                        if k not in ['DEVICE_NAME', 'DEVICE_TYPE'] and pd.notna(v))

    def format_multiline(self, param_str):
        lines = param_str.split(" ")
        return "\n" + "\n".join(f"+ {line}" for line in lines)

    def display_table_window(self):
        if self.df.empty:
            QMessageBox.warning(self.main_window, "警告", "データがありません。")
            return

        if self.table_window is not None:
            self.table_window.close()
            self.table_window = None

        # 新しいウィンドウを作成してテーブルを表示
        self.table_window = QMainWindow()
        self.table_window.setWindowTitle("モデルデータ")
        table_widget = QTableWidget()

        # データフレームの行数と列数をテーブルに設定
        table_widget.setRowCount(len(self.df))
        table_widget.setColumnCount(len(self.df.columns))
        table_widget.setHorizontalHeaderLabels(self.df.columns.tolist())

        # データフレームのデータをテーブルウィジェットに挿入
        for row in range(len(self.df)):
            for col in range(len(self.df.columns)):
                item = QTableWidgetItem(str(self.df.iat[row, col]))
                table_widget.setItem(row, col, item)

        # テーブルウィジェットを新しいウィンドウに配置
        layout = QVBoxLayout()
        layout.addWidget(table_widget)

        # ウィジェットにレイアウトを設定
        container = QWidget()
        container.setLayout(layout)
        self.table_window.setCentralWidget(container)

        # ウィンドウを表示
        self.table_window.setGeometry(100, 100, 800, 400)
        self.table_window.show()


def on_register_click():
    input_text = text_input.text()
    try:
        if model_manager.add_model(input_text):
            QMessageBox.information(window, "登録成功", "モデルが登録されました。")
            text_input.clear()  # テキストボックスをリセット
            update_device_combo()
    except SyntaxError as e:
        QMessageBox.warning(window, "エラー", str(e))

def on_device_selected(device_name):
    spice_string = model_manager.get_spice_string(
        device_name, multiline=multiline_checkbox.isChecked()
    )
    if not uppercase_checkbox.isChecked():
        spice_string = spice_string.lower()
    spice_display_label.setText(spice_string)

def copy_to_clipboard():
    spice_string = spice_display_label.text()
    if spice_string:
        clipboard = QGuiApplication.clipboard()
        clipboard.setText(spice_string)
        QMessageBox.information(window, "コピー成功", "Spice文字列がクリップボードにコピーされました。")

def update_device_combo():
    device_list = model_manager.get_device_list()
    device_combo.clear()
    device_combo.addItems(device_list)


app = QApplication([])

font = QFont()
font.setPointSize(11)

window = QWidget()
window.setWindowTitle("SpiceModelManager")
window.setGeometry(100, 100, 640, 900)

# ModelManagerインスタンスの作成
model_manager = ModelManager(window)

text_input = QLineEdit()
text_input.setPlaceholderText("ここにモデルデータを入力してください（例： .model 2SK208 NJF ...）")
text_input.setFixedHeight(40)

register_button = QPushButton("登録")
register_button.setFixedHeight(40)
register_button.clicked.connect(on_register_click)

device_combo = QComboBox()
device_combo.currentTextChanged.connect(on_device_selected)
device_combo.setFixedHeight(40)

spice_display_label = QLabel("選択したデバイスのSPICEモデル文字列がここに表示されます。")
spice_display_label.setWordWrap(True)

multiline_checkbox = QCheckBox("マルチライン表示")
multiline_checkbox.setChecked(True)

uppercase_checkbox = QCheckBox("大文字")
uppercase_checkbox.setChecked(True)  # Default to uppercase

multiline_checkbox.toggled.connect(lambda: on_device_selected(device_combo.currentText()))
uppercase_checkbox.toggled.connect(lambda: on_device_selected(device_combo.currentText()))

copy_button = QPushButton("クリップボードへコピー")
copy_button.setFixedHeight(40)
copy_button.clicked.connect(copy_to_clipboard)

show_table_button = QPushButton("モデルデータ表示")
show_table_button.clicked.connect(model_manager.display_table_window)

h_layout = QHBoxLayout()
h_layout.addWidget(text_input)
h_layout.addWidget(register_button)

device_layout = QHBoxLayout()
device_layout.addWidget(device_combo)

checkbox_layout = QHBoxLayout()
checkbox_layout.addWidget(multiline_checkbox)
checkbox_layout.addWidget(uppercase_checkbox)
checkbox_layout.setAlignment(Qt.AlignLeft)  # Align checkboxes to the left
checkbox_layout.setSpacing(0)  # Remove spacing between checkboxes

layout = QVBoxLayout()
layout.addLayout(h_layout)
layout.addLayout(device_layout)
layout.addWidget(spice_display_label)
layout.addLayout(checkbox_layout)
layout.addWidget(copy_button)
layout.addWidget(show_table_button)

window.setLayout(layout)

update_device_combo()

text_input.setFont(font)
register_button.setFont(font)
device_combo.setFont(font)
spice_display_label.setFont(font)
multiline_checkbox.setFont(font)
uppercase_checkbox.setFont(font)
copy_button.setFont(font)
show_table_button.setFont(font)


window.show()
app.exec_()
