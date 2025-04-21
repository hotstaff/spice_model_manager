#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Gm-Vgs Measurement (Python Version)
------------------------------------

BASIC版の内容を Python で再現した例です。
実際の計測器との通信部分はシミュレーションに置き換えてあります。

(参考) 測定器 HP 4140B のアドレスコード、計測設定、グラフ描画などの処理を再現しています。

作成例: 2025-02-11
"""

import math
import numpy as np
import matplotlib.pyplot as plt

def get_measurement_settings():
    """
    測定設定の入力を受け付ける
    ・4140Bアドレスコード（デフォルト717）
    ・DUT識別文字列、測定日
    ・START V, STOP V, STEP V, STEP DELAY(sec), HOLD TIME(sec), Vds
    ・測定点数 N2 を BASIC のアルゴリズムに従い算出
    """
    addr_in = input("4140B Address Code ? (717): ").strip()
    if addr_in == "":
        M = 717
    else:
        try:
            M = int(addr_in)
        except Exception:
            M = 717

    S = input("OUT=? (UP to 10 characters): ").strip()
    D = input("DATE=? ").strip()
    params = input("Input ; START V?, STOP V?, STEP V?, STEP DELAY(sec)?, HOLD TIME(sec)?, Vds (separated by spaces): ").strip()
    try:
        V1, V2, V3, T1, T2, V0 = [float(x) for x in params.split()]
    except Exception as e:
        print("入力が正しくありません。既定値を使用します。")
        V1, V2, V3, T1, T2, V0 = 0.0, 5.0, 0.5, 1.0, 1.0, 5.0

    # BASIC版では N1 = ABS((V2-V1)/V3)
    # もし小数部が 0 でなければ N2 = int(N1)+2, そうでなければ int(N1)+1
    N1 = abs((V2 - V1) / V3)
    frac = N1 - int(N1)
    if abs(frac) > 1e-9:
        N2 = int(N1) + 2
    else:
        N2 = int(N1) + 1

    return M, S, D, V1, V2, V3, T1, T2, V0, N2

def simulate_measurement(V1, V2, V3, N2):
    """
    設定値に基づき、各 Vgs での Id をシミュレーションする。
    ここでは例として、Vgs が 1V 以下では Id = 1e-15 A、
    それ以降は以下の指数関数的カーブを用いる：
      Id = 10^((Vgs-1)*3.25 - 15)
    （Vgs=1V で 1e-15 A、Vgs=5V で約 1e-2 A となる）
    """
    V_points = []
    v = V1
    for i in range(N2):
        if v > V2:
            break
        V_points.append(v)
        v += V3
    # 必要なら最後の点として V2 を含める
    if V_points[-1] < V2:
        V_points.append(V2)
        N2 = len(V_points)
    else:
        N2 = len(V_points)
    
    I1 = []
    for v in V_points:
        if v < 1:
            id_val = 1e-15
        else:
            id_val = 10 ** ((v - 1) * 3.25 - 15)
        I1.append(id_val)
    
    return np.array(V_points), np.array(I1), N2

def plot_id_vgs(V_points, I1, S, D, V0, V1, V2, V3):
    """
    Id-Vgs カーブのグラフを描画する。
    BASIC版では x 軸は Vgs、y 軸は log10(Id) の線形プロットでしたが、
    ここでは semilogy プロットで再現しています。
    """
    plt.figure(figsize=(8, 6))
    plt.semilogy(V_points, I1, marker='o', linestyle='-', label="Measured Id")
    plt.xlabel("Vgs (V)")
    plt.ylabel("Id (A)")
    plt.title("Id-Vgs Characteristics")
    
    # BASIC版では M1=1e-15, M2=0.01 を用いて軸のスケールを決定していました
    M1 = 1e-15
    M2 = 0.01
    X = V2 - V1
    Y = math.log10(M2) - math.log10(M1)  # 全体の対数レンジ
    Y1 = math.log10(M1)
    # 下記はラベルの配置例です（位置は適宜調整してください）
    plt.text(V1 + 0.55 * X, 10 ** (Y1 + 1.15 * Y), "Id-Vgs Characteristics", fontsize=12, weight='bold')
    plt.text(V1 + 0.25 * X, 10 ** (Y1 + 1.07 * Y), f"DUT = {S}", fontsize=10)
    plt.text(V1 + 0.9 * X, 10 ** (Y1 + 1.05 * Y), f"Vds = {V0:.2f} V", fontsize=10)
    plt.text(V1 + 0.3 * X, 10 ** (Y1 + 0.55 * Y), "Id (A)", rotation=90, fontsize=10)
    plt.text(V1 + 0.31 * X, 10 ** (Y1 - 0.2 * Y), "HP 4140B", fontsize=10)
    plt.text(V1 + 0.99 * X, 10 ** (Y1 - 0.2 * Y), "Vgs (V)", fontsize=10)
    plt.text(V1 + 0.99 * X, 10 ** (Y1 - 0.3 * Y), D, fontsize=10)
    
    plt.grid(True, which="both", ls="--")
    plt.xlim(V1, V2)
    plt.ylim(M1, M2)
    plt.legend()
    plt.tight_layout()
    plt.show()
    
    input("PRESS 'CONT' to continue...")

def calculate_gm(V_points, I1, V3):
    """
    gm（transconductance）を、各測定点での差分近似
      gm[i] = |(I[i+1]-I[i]) / Vstep|
    により求め、さらに最大 gm（G2）と、
    プロット用スケール因子 G3 を BASIC版と同様の計算式で求める。
    """
    G1 = []
    for i in range(len(I1) - 1):
        gm_val = abs((I1[i+1] - I1[i]) / V3)
        G1.append(gm_val)
    G1 = np.array(G1)
    if len(G1) == 0:
        G2 = 0.0
    else:
        G2 = np.max(G1)
    
    # BASIC版の式：
    #   G3 = 10^( INT(log10(G2)) - ( (fractional part of log10(G2)) != 0 and log10(G2)>=0 ? 1 : 0 ) )
    if G2 > 0:
        logG2 = math.log10(G2)
        int_part = int(math.floor(logG2))
        frac = logG2 - int_part
        if abs(frac) > 1e-9 and logG2 >= 0:
            exponent = int_part - 1
        else:
            exponent = int_part
        G3 = 10 ** exponent
    else:
        G3 = 0.0
    
    return G1, G2, G3

def plot_gm_vgs(V_points, G1, S, D, V0, V1, V2, V3, G2, G3):
    """
    Gm-Vgs カーブのグラフを描画する。
    x 軸は Vgs、y 軸は gm（A/V）とし、BASIC版のラベル配置に近い配置例を示しています。
    """
    plt.figure(figsize=(8, 6))
    # G1 の要素数は (測定点数 - 1) なので、x 軸は V_points[:-1] とする
    x_gm = V_points[:-1]
    plt.plot(x_gm, G1, marker='o', linestyle='-', label="gm")
    plt.xlabel("Vgs (V)")
    plt.ylabel("gm (A/V)")
    plt.title("Gm-Vgs Characteristics")
    
    # y 軸の上限 Y を BASIC版と同様に計算： Y = G3 * (1 + int(G2/G3))
    if G3 != 0:
        Y = G3 * (1 + int(G2 / G3))
    else:
        Y = G2
    plt.ylim(0, Y)
    plt.xlim(V1, V2)
    
    X = V2 - V1
    # ラベルの配置例（位置はお好みで調整してください）
    plt.text(V1 + 0.55 * X, Y * 1.15, "Gm-Vgs Characteristics", fontsize=12, weight='bold')
    plt.text(V1 + 0.25 * X, Y * 1.07, f"DUT = {S}", fontsize=10)
    plt.text(V1 + X, Y * 1.05, f"Gm-(S)* {V0:.2f}", fontsize=10)
    plt.text(V1 - 0.15 * X, Y * 0.5, f"{G3:.2e}", rotation=90, fontsize=10)
    plt.text(V1 + 0.31 * X, -Y * 0.2, "HP 4140B", fontsize=10)
    plt.text(V1 + 0.99 * X, -Y * 0.2, "Vgs (V)", fontsize=10)
    plt.text(V1 + 0.99 * X, -Y * 0.3, D, fontsize=10)
    
    plt.grid(True, ls="--")
    plt.legend()
    plt.tight_layout()
    plt.show()

def main():
    # 測定設定の入力
    M, S, D, V1, V2, V3, T1, T2, V0, N2 = get_measurement_settings()
    
    print("\n【測定設定】")
    print(f"Address Code: {M}")
    print(f"DUT: {S}")
    print(f"Date: {D}")
    print(f"Vstart: {V1} V, Vstop: {V2} V, Vstep: {V3} V, Step Delay: {T1} sec, Hold Time: {T2} sec, Vds: {V0} V")
    print(f"Number of measurement points (N2): {N2}")
    
    input("\nConnect DUT for Id-Vgs Measurement as D:HI, G:Va, S:GND, LO:Vb 'CONT' (Enterキーで続行)")
    
    # 測定（シミュレーション）
    V_points, I1, N2 = simulate_measurement(V1, V2, V3, N2)
    print("\n【測定結果 (Vgs, Id)】")
    for v, i_val in zip(V_points, I1):
        print(f"{v:.3f} V, {i_val:.3e} A")
    
    # Id-Vgs グラフの描画
    plot_id_vgs(V_points, I1, S, D, V0, V1, V2, V3)
    
    # gm の計算（有限差分法）
    G1, G2, G3 = calculate_gm(V_points, I1, V3)
    print(f"\nMaximum gm (G2): {G2:.3e} A/V")
    print(f"gm scaling factor (G3): {G3:.3e} A/V")
    
    # Gm-Vgs グラフの描画
    plot_gm_vgs(V_points, G1, S, D, V0, V1, V2, V3, G2, G3)

if __name__ == "__main__":
    main()
