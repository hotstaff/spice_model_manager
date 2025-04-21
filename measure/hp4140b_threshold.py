#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
HP4140B Threshold Voltage Measurement Program

This program controls the HP4140B via GPIB (PyVISA) to measure the
threshold voltage (Vth) by bisection between user-defined limits.
"""

import argparse
import sys

try:
    import pyvisa
except ImportError:
    sys.exit("Error: PyVISA is required. Install with 'pip install pyvisa'.")

def parse_args():
    parser = argparse.ArgumentParser(
        description='HP4140B Threshold Voltage Measurement')
    parser.add_argument(
        '-r', '--resource', default='GPIB0::22::INSTR',
        help='GPIB resource string (default: GPIB0::22::INSTR)')
    parser.add_argument(
        '--step-delay', type=float, default=0.01,
        help='Step delay after voltage change in seconds (default: 0.01)')
    parser.add_argument(
        '--hold-time', type=float, default=0.0,
        help='Hold time at each voltage in seconds (default: 0.0)')
    return parser.parse_args()

def parse_response(resp):
    resp = resp.strip()
    if ',' in resp:
        curr_str, volt_str = resp.split(',', 1)
    else:
        parts = resp.split()
        if len(parts) >= 2:
            curr_str, volt_str = parts[0], parts[1]
        else:
            raise ValueError(f"Cannot parse response: {resp}")
    return float(curr_str), float(volt_str)

def get_settings():
    sample = input("Sample name (max 18 chars): ").strip()
    channel = input("Channel? (P or N): ").strip().upper()
    while channel not in ('P', 'N'):
        print("Invalid channel. Enter 'P' or 'N'.")
        channel = input("Channel? (P or N): ").strip().upper()
    try:
        Vd = float(input("Vd (V)? ").strip())
        Ith_uA = float(input("Ith (uA)? ").strip())
        Ith = Ith_uA * 1e-6
        vth_upper = float(input("Vth upper limit (V)? ").strip())
        vth_lower = float(input("Vth lower limit (V)? ").strip())
    except ValueError:
        sys.exit("Invalid numeric input.")
    return sample, channel, Vd, Ith, vth_upper, vth_lower

def setup_instrument(inst):
    # Reset and configure for voltage sourcing, current measurement
    inst.write('RS;')
    inst.write('F2;RA1;I1;J1;T2;A3;B1;L3;M3;')

def measure_current(inst, Vgs, Vd, step_delay, hold_time):
    # Set drain/source voltage and gate voltage for one-point measurement
    cmd = (
        f"PB{Vd};"
        f"PS{Vgs};PT{Vgs};PE0;"
        f"PH{hold_time};PD{step_delay};"
    )
    inst.write(cmd)
    inst.write('W1;')
    resp = inst.read()
    curr, volt = parse_response(resp)
    return curr, volt

def bisection_threshold(inst, channel, Vd, Ith, vth_upper, vth_lower,
                        step_delay, hold_time):
    low_v = min(vth_lower, vth_upper)
    high_v = max(vth_lower, vth_upper)
    # Initial bracket measurements
    I_low, _ = measure_current(inst, low_v, Vd, step_delay, hold_time)
    I_high, _ = measure_current(inst, high_v, Vd, step_delay, hold_time)
    # Check that Ith is between the bracketed currents
    if channel == 'N':
        if not (I_low <= Ith <= I_high):
            print("Warning: Ith not bracketed by initial limits.")
    else:
        if not (I_high <= Ith <= I_low):
            print("Warning: Ith not bracketed by initial limits.")
    # Bisection loop
    resolution = 0.01
    max_iter = 50
    for _ in range(max_iter):
        if abs(high_v - low_v) <= resolution:
            break
        mid_v = (low_v + high_v) / 2.0
        I_mid, _ = measure_current(inst, mid_v, Vd, step_delay, hold_time)
        if channel == 'N':
            if I_mid < Ith:
                low_v, I_low = mid_v, I_mid
            else:
                high_v, I_high = mid_v, I_mid
        else:
            if I_mid > Ith:
                low_v, I_low = mid_v, I_mid
            else:
                high_v, I_high = mid_v, I_mid
    return (low_v + high_v) / 2.0

def main():
    args = parse_args()
    sample, channel, Vd, Ith, vth_upper, vth_lower = get_settings()
    rm = pyvisa.ResourceManager()
    inst = rm.open_resource(
        args.resource, write_termination='\n', read_termination='\n')
    # Timeout: allow for step delays and hold times
    inst.timeout = int((args.step_delay + args.hold_time + 1) * 1000)
    print("\nInstrument ID:", inst.query('*IDN?').strip())
    setup_instrument(inst)
    print("\nMeasuring threshold voltage...")
    vth = bisection_threshold(
        inst, channel, Vd, Ith, vth_upper, vth_lower,
        args.step_delay, args.hold_time)
    # Output result
    print(f"\nSample: {sample}")
    print(f"Channel: {channel}")
    print(f"Threshold voltage (Vth): {vth:.3f} V")
    # Beep on completion
    print('\a')
    inst.close()

if __name__ == '__main__':
    main()