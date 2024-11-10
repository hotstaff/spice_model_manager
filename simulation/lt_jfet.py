import matplotlib.pyplot as plt
import numpy as np
from PyLTSpice import SimRunner, SpiceEditor, LTspice, RawRead

runner = SimRunner(output_folder='./data', simulator=LTspice)  # Configures the simulator to use and output

# Netlistの読み込み
net = SpiceEditor("./net/TEST_JFET.net")  # 現在のネットリストファイルを読み込む

raw_path, log = runner.run_now(net, run_filename="./net/ss.net")

# RAWファイルの読み込み
raw = RawRead(raw_path)

# 必要なトレースを取得
Vds = raw['V(n002)'].data  # Vds（ドレイン-ソース電圧）
Vgs = raw['V(n001)'].data  # Vgs（ゲート-ソース電圧）
Id = raw['Id(J1)'].data    # Id（ドレイン電流）

Id_mA = Id * 1e3  # ドレイン電流をmA単位に変換

# 異なるVgsごとにプロットする
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

# 画像を保存
plt.savefig('images/jfet_iv_characteristic.png')

# 表示
plt.show()
