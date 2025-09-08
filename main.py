"""Main entry point for the generic BESS Digital Twin simulation.

Usage examples:
    python main.py                 # run full simulation
    python main.py --steps 5000    # override number of steps
    python main.py --profile       # run with pyinstrument and write outputs/profile.html
"""

from __future__ import annotations

import os
import argparse
import random
from typing import Dict, Any, List

import pandas as pd
from tqdm import tqdm

import config
from simulation_objects import (
    BESS_Site,
    InverterGroup,
    BatteryContainer,
)

def initialize_simulation() -> BESS_Site:
    """Build the full site object graph using generic, config-driven layout."""
    groups: List[InverterGroup] = []
    per_group_counts = getattr(config, 'INVERTER_GROUP_CONTAINER_COUNTS', []) or []
    if per_group_counts:
        for g, count in enumerate(per_group_counts):
            containers = [BatteryContainer(id=f"G{g+1}C{c+1}") for c in range(int(count))]
            groups.append(InverterGroup(id=f"G{g+1}", containers=containers))
    else:
        num_groups = int(getattr(config, 'NUM_INVERTER_GROUPS', 2))
        containers_per_group = int(getattr(config, 'CONTAINERS_PER_GROUP', 2))
        for g in range(num_groups):
            containers = [BatteryContainer(id=f"G{g+1}C{c+1}") for c in range(containers_per_group)]
            groups.append(InverterGroup(id=f"G{g+1}", containers=containers))
    return BESS_Site(inverter_groups=groups)


def run_simulation(total_steps: int | None = None) -> None:
    site = initialize_simulation()
    results_log: List[Dict[str, Any]] = []

    total_steps = total_steps or config.TOTAL_STEPS
    for _ in tqdm(range(total_steps), desc='Simulating'):
        site.run_time_step(config.TIME_STEP_SECONDS)
        # Example logging: extend as needed
        avg_group_socs = []
        group_cmd_power = []
        group_applied_power = []
        container_min_v = []
        container_max_v = []
        for group in site.inverter_groups:
            if group.containers:
                avg_group_socs.append(sum(c.get_soc() for c in group.containers) / len(group.containers))
                group_cmd_power.append(group.last_commanded_power_mw)
                group_applied_power.append(group.last_applied_power_mw)
                for c in group.containers:
                    vmin, vmax = c.get_cell_voltage_extrema()
                    container_min_v.append(vmin)
                    container_max_v.append(vmax)
        results_log.append({
            'time_s': site.current_time_s,
            'time_h': site.current_time_s / 3600.0,
            'site_target_power_mw': site.get_site_target_power(),
            'test_state': site.test_state,
            'avg_group_soc_percent': sum(avg_group_socs) / len(avg_group_socs) if avg_group_socs else 0.0,
            'avg_group_commanded_power_mw': sum(group_cmd_power) / len(group_cmd_power) if group_cmd_power else 0.0,
            'avg_group_applied_power_mw': sum(group_applied_power) / len(group_applied_power) if group_applied_power else 0.0,
            'min_cell_voltage_v': min(container_min_v) if container_min_v else 0.0,
            'max_cell_voltage_v': max(container_max_v) if container_max_v else 0.0,
        })

    # Export
    os.makedirs(os.path.dirname(config.OUTPUT_CSV_PATH), exist_ok=True)
    df = pd.DataFrame(results_log)
    df.to_csv(config.OUTPUT_CSV_PATH, index=False)


def main() -> None:
    parser = argparse.ArgumentParser(description='Generic BESS Digital Twin Simulation')
    parser.add_argument('--steps', type=int, default=None, help='Override number of time steps')
    parser.add_argument('--profile', action='store_true', help='Enable pyinstrument profiler and save HTML flame chart')
    parser.add_argument('--profile-output', default=os.path.join('outputs', 'profile.html'), help='Path to write profile HTML')
    args = parser.parse_args()

    if args.profile:
        try:
            from pyinstrument import Profiler
        except Exception as exc:
            raise SystemExit(f'pyinstrument not installed. Install and retry. Details: {exc}')
        os.makedirs('outputs', exist_ok=True)
        profiler = Profiler()
        profiler.start()
        try:
            run_simulation(args.steps)
        finally:
            profiler.stop()
            with open(args.profile_output, 'w', encoding='utf-8') as f:
                f.write(profiler.output_html())
            print(f'Profile written to {args.profile_output}')
    else:
        run_simulation(args.steps)


if __name__ == '__main__':
    main()


