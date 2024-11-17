import requests
from PyQt5.QtGui import QGuiApplication, QFont
from PyQt5.QtWidgets import (QApplication, QCheckBox, QLabel, QLineEdit, 
                             QMainWindow, QPushButton, QTableWidget, 
                             QTableWidgetItem, QVBoxLayout, QHBoxLayout, 
                             QWidget, QMessageBox, QComboBox)
from PyQt5.QtCore import Qt
from spice_model_parser import SpiceModelParser

class ModelManager:
    def __init__(self, main_window):
        self.main_window = main_window
        self.devices_cache = []  # ローカルキャッシュ
        self.table_window = None

    def load_from_api(self):
        """APIからデータをロードしてキャッシュに保存"""
        try:
            response = requests.get('https://spice-model-manager.onrender.com/api/models')
            response.raise_for_status()  # エラーがあれば例外を発生
            self.devices_cache = response.json()  # キャッシュに保存
            return self.devices_cache
        except requests.RequestException as e:
            QMessageBox.warning(self.main_window, "エラー", f"データの取得に失敗しました: {e}")
            self.devices_cache = []  # エラーの場合は空リスト
            return self.devices_cache

    def save_to_api(self, params):
        try:
            response = requests.post('https://spice-model-manager.onrender.com/api/models', json=params)
            response.raise_for_status()
            self.load_from_api()  # データの再ロード
        except requests.RequestException as e:
            QMessageBox.warning(self.main_window, "エラー", f"データの保存に失敗しました: {e}")

    def update_to_api(self, model_id, params):
        try:
            url = f'https://spice-model-manager.onrender.com/api/models/{model_id}'
            response = requests.put(url, json=params)
            response.raise_for_status()
            QMessageBox.information(self.main_window, "更新成功", "モデルが更新されました。")
            self.load_from_api()  # データの再ロード
        except requests.RequestException as e:
            QMessageBox.warning(self.main_window, "エラー", f"データの更新に失敗しました: {e}")

    def delete_model_from_api(self, model_id):
        try:
            url = f'https://spice-model-manager.onrender.com/api/models/{model_id}'
            response = requests.delete(url)
            response.raise_for_status()
            QMessageBox.information(self.main_window, "削除成功", "モデルが削除されました。")
            self.load_from_api()  # データの再ロード
        except requests.RequestException as e:
            QMessageBox.warning(self.main_window, "エラー", f"データの削除に失敗しました: {e}")

    def add_model(self, model_line):
        try:
            # SpiceModelParserを使ってモデル行をパース
            parser = SpiceModelParser()
            params = parser.parse(model_line, convert_units=False)

            # パラメータからspice_stringを作成
            spice_string = f".MODEL {params['device_name']} {params['device_type']} " + \
                           " ".join(f"{k}={v}" for k, v in params.items() if k not in ['device_name', 'device_type'])

            # APIから既存デバイスの情報を取得
            existing_devices = {d['device_name']: d['id'] for d in self.load_from_api()}
            device_name = params['device_name']

            if device_name in existing_devices:
                reply = QMessageBox.question(
                    self.main_window, '上書き確認', f"{device_name} は既に登録されています。上書きしますか？",
                    QMessageBox.Yes | QMessageBox.No, QMessageBox.No
                )
                if reply == QMessageBox.No:
                    return False

                # 上書きの場合、IDを使ってPUTリクエストを送信
                model_id = existing_devices[device_name]
                self.update_to_api(model_id, {
                    "device_name": device_name,
                    "device_type": params['device_type'],
                    "spice_string": spice_string
                })
            else:
                # 新規の場合はPOSTリクエストを送信
                self.save_to_api({
                    "device_name": device_name,
                    "device_type": params['device_type'],
                    "spice_string": spice_string
                })
            return True
        except Exception as e:
            QMessageBox.warning(self.main_window, "エラー", f"モデルの追加中にエラーが発生しました: {e}")
            return False

    def remove_device(self, device_name):
        """選択されたデバイスを削除する"""
        device = next((d for d in self.devices_cache if d['device_name'] == device_name), None)
        if device:
            reply = QMessageBox.question(
                self.main_window, '削除確認', f"{device_name} を削除しますか？",
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No
            )
            if reply == QMessageBox.Yes:
                model_id = device['id']
                self.delete_model_from_api(model_id)
        
    def get_device_list(self):
        """キャッシュからデバイスリストを取得"""
        return [device['device_name'] for device in self.devices_cache]

    def get_spice_string(self, device_name, multiline=False):
        """キャッシュから指定デバイスのSPICE文字列を取得"""
        device = next((d for d in self.devices_cache if d['device_name'] == device_name), None)
        
        if device:
            parser = SpiceModelParser()
            parsed_string = parser.parse(device['spice_string'])
            spice_string = f".MODEL {parsed_string['device_name']} {parsed_string['device_type']} "
            param_str = " ".join(f"{k}={v}" for k, v in parsed_string.items() if k not in ['device_name', 'device_type'])

            if multiline:
                lines = param_str.split(" ")
                spice_string += "\n" + "\n".join(f"+ {line}" for line in lines)
            else:
                spice_string += param_str

            return spice_string
        return ""

    def display_table_window(self):
        devices = self.devices_cache
        if not devices:
            QMessageBox.warning(self.main_window, "警告", "データがありません。")
            return

        if self.table_window is not None:
            self.table_window.close()
            self.table_window = None

        self.table_window = QMainWindow()
        self.table_window.setWindowTitle("モデルデータ")
        table_widget = QTableWidget()
        table_widget.setRowCount(len(devices))
        table_widget.setColumnCount(len(devices[0]))
        table_widget.setHorizontalHeaderLabels(devices[0].keys())

        for row, device in enumerate(devices):
            for col, (key, value) in enumerate(device.items()):
                item = QTableWidgetItem(str(value))
                table_widget.setItem(row, col, item)

        layout = QVBoxLayout()
        layout.addWidget(table_widget)
        container = QWidget()
        container.setLayout(layout)
        self.table_window.setCentralWidget(container)

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

def on_delete_click():
    selected_device = device_combo.currentText()
    if selected_device:
        model_manager.remove_device(selected_device)
    else:
        QMessageBox.warning(window, "警告", "削除するデバイスを選択してください。")


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
    model_manager.load_from_api()
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
register_button.setFixedWidth(100)
register_button.clicked.connect(on_register_click)

# 削除ボタンの作成
delete_button = QPushButton("削除")
delete_button.setFixedHeight(40)
delete_button.setFixedWidth(70)
delete_button.clicked.connect(on_delete_click)

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
# h_layout.addWidget(delete_button)
h_layout.addWidget(text_input)
h_layout.addWidget(register_button)


device_layout = QHBoxLayout()
device_layout.addWidget(device_combo)
device_layout.addWidget(delete_button)

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

for widget in [text_input, register_button, delete_button, device_combo, spice_display_label, 
               multiline_checkbox, uppercase_checkbox, copy_button, show_table_button]:
    widget.setFont(font)


window.show()
app.exec_()
