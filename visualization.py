"""Visualization utilities for the generic BESS Digital Twin."""

from __future__ import annotations

import os
from typing import Optional

import pandas as pd
import matplotlib.pyplot as plt

import config


def generate_plots(results_csv_path: Optional[str] = None) -> None:
    path = results_csv_path or config.OUTPUT_CSV_PATH
    if not os.path.exists(path):
        raise FileNotFoundError(f"Results CSV not found at {path}")

    df = pd.read_csv(path)
    os.makedirs(config.PLOT_OUTPUT_DIR, exist_ok=True)

    # Plot 1: Site Power Profile
    fig, ax = plt.subplots(figsize=(10, 5))
    ax.plot(df['time_h'], df['site_target_power_mw'], label='Target Power (MW)')
    if 'avg_group_applied_power_mw' in df.columns:
        ax.plot(df['time_h'], df['avg_group_applied_power_mw'], label='Applied Power (MW)', alpha=0.7)
    ax.set_xlabel('Time (hours)')
    ax.set_ylabel('Power (MW)')
    ax.set_title('Site Power Profile')
    ax.grid(True, alpha=0.3)
    ax.legend()
    fig.tight_layout()
    fig.savefig(os.path.join(config.PLOT_OUTPUT_DIR, 'plot_site_power_profile.png'), dpi=200)
    plt.close(fig)

    # Plot 2: Average SOC (proxy for system behavior)
    fig, ax = plt.subplots(figsize=(10, 5))
    ax.plot(df['time_h'], df['avg_group_soc_percent'], label='Average Inverter Group SOC (%)')
    ax.set_xlabel('Time (hours)')
    ax.set_ylabel('SOC (%)')
    ax.set_title('System SOC Profile')
    ax.grid(True, alpha=0.3)
    ax.legend()
    fig.tight_layout()
    fig.savefig(os.path.join(config.PLOT_OUTPUT_DIR, 'plot_system_soc_profile.png'), dpi=200)
    plt.close(fig)

    # Plot 3: Cell voltage extrema to visualize weakest-link behavior
    if 'min_cell_voltage_v' in df.columns and 'max_cell_voltage_v' in df.columns:
        fig, ax = plt.subplots(figsize=(10, 5))
        ax.plot(df['time_h'], df['min_cell_voltage_v'], label='Min Cell Voltage (V)')
        ax.plot(df['time_h'], df['max_cell_voltage_v'], label='Max Cell Voltage (V)')
        ax.axhline(y=config.L2_CUTOFF_LOW_VOLTAGE, color='r', linestyle='--', alpha=0.5, label='L2 Low Cutoff')
        ax.axhline(y=config.L2_CUTOFF_HIGH_VOLTAGE, color='g', linestyle='--', alpha=0.5, label='L2 High Cutoff')
        ax.set_xlabel('Time (hours)')
        ax.set_ylabel('Voltage (V)')
        ax.set_title('Cell Voltage Extremes')
        ax.grid(True, alpha=0.3)
        ax.legend()
        fig.tight_layout()
        fig.savefig(os.path.join(config.PLOT_OUTPUT_DIR, 'plot_cell_voltage_extrema.png'), dpi=200)
        plt.close(fig)


