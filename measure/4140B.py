#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
HP4140B Id-Vgs and Gm-Vgs Measurement Program

This program controls HP4140B via GPIB (PyVISA) to perform real Id-Vgs
and Gm-Vgs measurements. It prompts for measurement settings,
executes the voltage sweep, reads data, and plots the results.
"""

import argparse
import datetime
import math
import sys

import numpy as np
import matplotlib.pyplot as plt

try:
    import pyvisa
except ImportError:
    sys.exit("Error: PyVISA is required. Install with 'pip install pyvisa'.")

def parse_args():
    parser = argparse.ArgumentParser(description='HP4140B Id-Vgs and Gm-Vgs Measurement')
    parser.add_argument('-r', '--resource', default='GPIB0::22::INSTR',
                        help='GPIB resource string (default: GPIB0::22::INSTR)')
    return parser.parse_args()

def get_measurement_settings():
    device = input("OUT=? (Up to 10 chars): ").strip()
    date_str = input("DATE=? ").strip() or datetime.datetime.now().strftime("%Y-%m-%d")
    params = input("Input ; START V?, STOP V?, STEP V?, STEP DELAY(s)?, HOLD TIME(s)?, Vds (separated by spaces): ").strip()
    try:
        V1, V2, V3, T1, T2, V0 = map(float, params.split())
    except Exception:
        print("Invalid input; using defaults.")
        V1, V2, V3, T1, T2, V0 = 0.0, 5.0, 0.5, 1.0, 1.0, 5.0
    N1 = abs((V2 - V1) / V3)
    frac = N1 - int(N1)
    if abs(frac) > 1e-9:
        N2 = int(N1) + 2
    else:
        N2 = int(N1) + 1
    return device, date_str, V1, V2, V3, T1, T2, V0, N2

def setup_instrument(inst):
    inst.write("RS;")
    inst.write("F2;RA1;I1;J1;T2;A3;B1;L3;M3;")

def perform_id_vgs(inst, V1, V2, V3, T1, T2, V0, N2):
    inst.write(f"PS{V1};PT{V2};PE{V3};PD{T1};PH{T2};PB{V0};")
    inst.write("W1;")
    V_points = []
    I_points = []
    print("\nMeasuring Id-Vgs ...")
    for i in range(N2):
        resp = inst.read().strip()
        try:
            curr_str, volt_str = resp.split(',')
            curr = float(curr_str)
            volt = float(volt_str)
        except Exception:
            parts = resp.split()
            if len(parts) >= 2:
                curr = float(parts[0]); volt = float(parts[1])
            else:
                raise ValueError(f"Cannot parse response: {resp}")
        V_points.append(volt)
        I_points.append(curr)
        print(f"{volt:.3f} V, {curr:.3e} A")
    return np.array(V_points), np.array(I_points)

def plot_id_vgs(V, I, device, date_str, V0, V1, V2):
    plt.figure(figsize=(8,6))
    plt.semilogy(V, I, marker='o', linestyle='-')
    plt.xlabel("Vgs (V)")
    plt.ylabel("Id (A)")
    plt.title("Id-Vgs Characteristics")
    plt.grid(True, which="both", ls="--")
    plt.text(V1 + 0.55*(V2-V1), np.max(I)*0.5, f"DUT: {device}")
    plt.text(V1 + 0.55*(V2-V1), np.max(I)*0.3, f"Vds: {V0:.2f} V")
    plt.text(V1 + 0.55*(V2-V1), np.min(I)*2 if np.min(I)>0 else np.max(I)*0.1, f"Date: {date_str}")
    plt.tight_layout()
    plt.show()

def calculate_gm(V, I, V3):
    G1 = np.abs(np.diff(I) / V3)
    G2 = G1.max() if G1.size else 0.0
    if G2 > 0:
        logG2 = math.log10(G2)
        int_part = int(math.floor(logG2))
        frac = logG2 - int_part
        exponent = int_part - 1 if frac > 1e-9 and logG2 >= 0 else int_part
        G3 = 10**exponent
    else:
        G3 = 0.0
    return G1, G2, G3

def plot_gm_vgs(V, G1, device, date_str, V1, V2, G2, G3):
    plt.figure(figsize=(8,6))
    plt.plot(V[:-1], G1, marker='o', linestyle='-')
    plt.xlabel("Vgs (V)")
    plt.ylabel("gm (A/V)")
    plt.title("Gm-Vgs Characteristics")
    if G3 > 0:
        Ymax = G3 * (1 + int(G2 / G3))
    else:
        Ymax = G2
    plt.ylim(0, Ymax*1.1)
    plt.grid(True, ls="--")
    plt.text(V1 + 0.55*(V2-V1), Ymax*0.9, f"DUT: {device}")
    plt.text(V1 + 0.55*(V2-V1), Ymax*0.8, f"Date: {date_str}")
    plt.tight_layout()
    plt.show()

def main():
    args = parse_args()
    device, date_str, V1, V2, V3, T1, T2, V0, N2 = get_measurement_settings()
    print(f"\nSettings:\nResource: {args.resource}\n"
          f"DUT: {device}\nDate: {date_str}\n"
          f"Vstart: {V1} V, Vstop: {V2} V, Vstep: {V3} V, "
          f"Step Delay: {T1} s, Hold Time: {T2} s, Vds: {V0} V\n"
          f"Points: {N2}")
    input("\nConnect DUT for Id-Vgs measurement (D:HI, G:VA, S:GND, LO:Vb) and press Enter...")
    rm = pyvisa.ResourceManager()
    inst = rm.open_resource(args.resource, write_termination='\n', read_termination='\n')
    inst.timeout = int((T1 + T2 + 1) * 1000)
    print("\nInstrument ID:", inst.query("*IDN?").strip())
    setup_instrument(inst)
    V, I = perform_id_vgs(inst, V1, V2, V3, T1, T2, V0, N2)
    plot_id_vgs(V, I, device, date_str, V0, V1, V2)
    G1, G2, G3 = calculate_gm(V, I, V3)
    print(f"\nMaximum gm (G2): {G2:.3e} A/V\nScaling factor (G3): {G3:.3e} A/V")
    plot_gm_vgs(V, G1, device, date_str, V1, V2, G2, G3)
    inst.close()

if __name__ == "__main__":
    main()