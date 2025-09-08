from __future__ import annotations

import time
from typing import List

import streamlit as st

import config
from main import initialize_simulation
from simulation_runner import execute_simulation_step


st.set_page_config(page_title="BESS Digital Twin & Performance Simulator", layout="wide")


def init_session_state() -> None:
    if 'initialized' in st.session_state:
        return
    st.session_state.initialized = True
    # Copy key config values for interactive editing
    st.session_state.TIME_STEP_SECONDS = config.TIME_STEP_SECONDS
    st.session_state.SIMULATION_DURATION_HOURS = config.SIMULATION_DURATION_HOURS
    st.session_state.SITE_TARGET_POWER_MW = config.SITE_TARGET_POWER_MW
    st.session_state.RAMP_DURATION_SECONDS = config.RAMP_DURATION_SECONDS
    st.session_state.CHARGE_TAPER_DURATION_SECONDS = config.CHARGE_TAPER_DURATION_SECONDS
    st.session_state.DISCHARGE_TAPER_DURATION_SECONDS = config.DISCHARGE_TAPER_DURATION_SECONDS
    st.session_state.HEAT_SOAK_DURATION_HOURS = config.HEAT_SOAK_DURATION_HOURS

    st.session_state.INVERTER_GROUP_CONTAINER_COUNTS = list(getattr(config, 'INVERTER_GROUP_CONTAINER_COUNTS', []))
    st.session_state.NUM_INVERTER_GROUPS = getattr(config, 'NUM_INVERTER_GROUPS', 2)
    st.session_state.CONTAINERS_PER_GROUP = getattr(config, 'CONTAINERS_PER_GROUP', 2)

    # BMS & balancing
    st.session_state.L2_CALIBRATE_LOW_VOLTAGE = config.L2_CALIBRATE_LOW_VOLTAGE
    st.session_state.L2_CUTOFF_LOW_VOLTAGE = config.L2_CUTOFF_LOW_VOLTAGE
    st.session_state.L2_CALIBRATE_HIGH_VOLTAGE = config.L2_CALIBRATE_HIGH_VOLTAGE
    st.session_state.L2_CUTOFF_HIGH_VOLTAGE = config.L2_CUTOFF_HIGH_VOLTAGE
    st.session_state.BALANCING_TOP_SOC_START = config.BALANCING_TOP_SOC_START
    st.session_state.BALANCING_BOTTOM_SOC_END = config.BALANCING_BOTTOM_SOC_END
    st.session_state.BALANCING_BLEED_CURRENT_A = config.BALANCING_BLEED_CURRENT_A

    # Initial SOC distribution
    st.session_state.INITIAL_SOC_MEDIAN_PERCENT = config.INITIAL_SOC_MEDIAN_PERCENT
    st.session_state.INITIAL_SOC_STD_PERCENT = config.INITIAL_SOC_STD_PERCENT
    st.session_state.INITIAL_SOC_MIN_PERCENT = config.INITIAL_SOC_MIN_PERCENT
    st.session_state.INITIAL_SOC_MAX_PERCENT = config.INITIAL_SOC_MAX_PERCENT
    st.session_state.INITIAL_SOC_FRACTION_AT_FLOOR = config.INITIAL_SOC_FRACTION_AT_FLOOR

    # Runtime
    st.session_state.site = None
    st.session_state.running = False
    st.session_state.progress = 0.0


def render_equipment_tree_editor() -> None:
    """Interactive editor for inverter -> batteries (containers) tree.

    Uses st.session_state.INVERTER_GROUP_CONTAINER_COUNTS as the backing model.
    """
    if not isinstance(st.session_state.INVERTER_GROUP_CONTAINER_COUNTS, list):
        st.session_state.INVERTER_GROUP_CONTAINER_COUNTS = []

    counts = [int(c) for c in st.session_state.INVERTER_GROUP_CONTAINER_COUNTS]

    # Totals
    total_inverters = len(counts)
    total_batteries = sum(counts) if counts else 0
    m1, m2 = st.columns(2)
    m1.metric("Total Inverters", total_inverters)
    m2.metric("Total Batteries", total_batteries)

    # Add inverter button
    if st.button("+ Add Inverter", key="btn_add_inverter"):
        counts.append(0)

    # Per-inverter controls
    remove_index = None
    for idx, value in enumerate(counts):
        with st.expander(f"Inverter {idx + 1}", expanded=False):
            row = st.columns([1.5, 1, 1, 1])
            row[0].write(f"Batteries: {int(value)}")
            if row[1].button("+ Add Battery", key=f"btn_add_battery_{idx}"):
                counts[idx] = int(counts[idx]) + 1
            if row[2].button("- Remove Battery", key=f"btn_rem_battery_{idx}"):
                counts[idx] = max(0, int(counts[idx]) - 1)
            if row[3].button("Remove Inverter", key=f"btn_remove_inverter_{idx}"):
                remove_index = idx

    if remove_index is not None and 0 <= remove_index < len(counts):
        counts.pop(remove_index)

    # Persist back
    st.session_state.INVERTER_GROUP_CONTAINER_COUNTS = counts


def sidebar_controls() -> None:
    st.sidebar.title("Configuration")

    with st.sidebar.expander("Simulation Control", expanded=True):
        st.session_state.TIME_STEP_SECONDS = st.number_input(
            "Time Step (seconds)", min_value=1, value=int(st.session_state.TIME_STEP_SECONDS)
        )
        st.session_state.SIMULATION_DURATION_HOURS = st.number_input(
            "Simulation Duration (hours)", min_value=0.1, value=float(st.session_state.SIMULATION_DURATION_HOURS)
        )
        st.session_state.SITE_TARGET_POWER_MW = st.number_input(
            "Site Target Power (MW)", value=float(st.session_state.SITE_TARGET_POWER_MW)
        )
        st.session_state.RAMP_DURATION_SECONDS = st.number_input(
            "Ramp Duration (s)", min_value=1, value=int(st.session_state.RAMP_DURATION_SECONDS)
        )
        st.session_state.CHARGE_TAPER_DURATION_SECONDS = st.number_input(
            "Charge Taper Duration (s)", min_value=1, value=int(st.session_state.CHARGE_TAPER_DURATION_SECONDS)
        )
        st.session_state.DISCHARGE_TAPER_DURATION_SECONDS = st.number_input(
            "Discharge Taper Duration (s)", min_value=1, value=int(st.session_state.DISCHARGE_TAPER_DURATION_SECONDS)
        )
        st.session_state.HEAT_SOAK_DURATION_HOURS = st.number_input(
            "Heat Soak Duration (hours)", min_value=0.0, value=float(st.session_state.HEAT_SOAK_DURATION_HOURS)
        )

    with st.sidebar.expander("Site Layout", expanded=True):
        use_custom = st.checkbox("Use per-inverter container counts", value=bool(st.session_state.INVERTER_GROUP_CONTAINER_COUNTS))
        if use_custom:
            render_equipment_tree_editor()
        else:
            st.session_state.NUM_INVERTER_GROUPS = st.number_input("Number of inverter groups", min_value=1, value=int(st.session_state.NUM_INVERTER_GROUPS))
            st.session_state.CONTAINERS_PER_GROUP = st.number_input("Containers per group", min_value=1, value=int(st.session_state.CONTAINERS_PER_GROUP))

    with st.sidebar.expander("BMS & Balancing", expanded=False):
        st.session_state.L2_CALIBRATE_LOW_VOLTAGE = st.slider("L2 Calibrate Low Voltage (V)", 2.5, 3.2, float(st.session_state.L2_CALIBRATE_LOW_VOLTAGE))
        st.session_state.L2_CUTOFF_LOW_VOLTAGE = st.slider("L2 Cutoff Low Voltage (V)", 2.5, 3.2, float(st.session_state.L2_CUTOFF_LOW_VOLTAGE))
        st.session_state.L2_CALIBRATE_HIGH_VOLTAGE = st.slider("L2 Calibrate High Voltage (V)", 3.3, 3.6, float(st.session_state.L2_CALIBRATE_HIGH_VOLTAGE))
        st.session_state.L2_CUTOFF_HIGH_VOLTAGE = st.slider("L2 Cutoff High Voltage (V)", 3.4, 3.8, float(st.session_state.L2_CUTOFF_HIGH_VOLTAGE))
        st.session_state.BALANCING_TOP_SOC_START = st.slider("Top balancing starts at SOC (%)", 90.0, 100.0, float(st.session_state.BALANCING_TOP_SOC_START))
        st.session_state.BALANCING_BOTTOM_SOC_END = st.slider("Bottom balancing ends at SOC (%)", 0.0, 10.0, float(st.session_state.BALANCING_BOTTOM_SOC_END))
        st.session_state.BALANCING_BLEED_CURRENT_A = st.number_input("Balancing Bleed Current (A)", value=float(st.session_state.BALANCING_BLEED_CURRENT_A))

    with st.sidebar.expander("Initial SOC Distribution", expanded=False):
        st.session_state.INITIAL_SOC_MEDIAN_PERCENT = st.number_input("Initial Median SOC (%)", value=float(st.session_state.INITIAL_SOC_MEDIAN_PERCENT))
        st.session_state.INITIAL_SOC_MIN_PERCENT = st.number_input("Initial Minimum SOC (%)", value=float(st.session_state.INITIAL_SOC_MIN_PERCENT))
        st.session_state.INITIAL_SOC_STD_PERCENT = st.number_input("Initial SOC StdDev (%)", value=float(st.session_state.INITIAL_SOC_STD_PERCENT))
        st.session_state.INITIAL_SOC_FRACTION_AT_FLOOR = st.slider("% of Cells at Min SOC", 0, 100, int(st.session_state.INITIAL_SOC_FRACTION_AT_FLOOR * 100)) / 100.0

    st.sidebar.markdown("---")
    col1, col2 = st.sidebar.columns(2)
    run_clicked = col1.button("Run", type="primary")
    stop_clicked = col2.button("Stop")

    if run_clicked:
        # Apply overrides back to config for this session
        config.TIME_STEP_SECONDS = int(st.session_state.TIME_STEP_SECONDS)
        config.SIMULATION_DURATION_HOURS = float(st.session_state.SIMULATION_DURATION_HOURS)
        config.TOTAL_STEPS = int(config.SIMULATION_DURATION_HOURS * 3600 / config.TIME_STEP_SECONDS)
        config.SITE_TARGET_POWER_MW = float(st.session_state.SITE_TARGET_POWER_MW)
        config.RAMP_DURATION_SECONDS = int(st.session_state.RAMP_DURATION_SECONDS)
        config.CHARGE_TAPER_DURATION_SECONDS = int(st.session_state.CHARGE_TAPER_DURATION_SECONDS)
        config.DISCHARGE_TAPER_DURATION_SECONDS = int(st.session_state.DISCHARGE_TAPER_DURATION_SECONDS)
        config.HEAT_SOAK_DURATION_HOURS = float(st.session_state.HEAT_SOAK_DURATION_HOURS)

        use_custom_counts = bool(st.session_state.INVERTER_GROUP_CONTAINER_COUNTS)
        if use_custom_counts:
            config.INVERTER_GROUP_CONTAINER_COUNTS = list(st.session_state.INVERTER_GROUP_CONTAINER_COUNTS)
        else:
            config.INVERTER_GROUP_CONTAINER_COUNTS = []
            config.NUM_INVERTER_GROUPS = int(st.session_state.NUM_INVERTER_GROUPS)
            config.CONTAINERS_PER_GROUP = int(st.session_state.CONTAINERS_PER_GROUP)

        # BMS & balancing
        config.L2_CALIBRATE_LOW_VOLTAGE = float(st.session_state.L2_CALIBRATE_LOW_VOLTAGE)
        config.L2_CUTOFF_LOW_VOLTAGE = float(st.session_state.L2_CUTOFF_LOW_VOLTAGE)
        config.L2_CALIBRATE_HIGH_VOLTAGE = float(st.session_state.L2_CALIBRATE_HIGH_VOLTAGE)
        config.L2_CUTOFF_HIGH_VOLTAGE = float(st.session_state.L2_CUTOFF_HIGH_VOLTAGE)
        config.BALANCING_TOP_SOC_START = float(st.session_state.BALANCING_TOP_SOC_START)
        config.BALANCING_BOTTOM_SOC_END = float(st.session_state.BALANCING_BOTTOM_SOC_END)
        config.BALANCING_BLEED_CURRENT_A = float(st.session_state.BALANCING_BLEED_CURRENT_A)

        # Initial SOC distribution
        config.INITIAL_SOC_MEDIAN_PERCENT = float(st.session_state.INITIAL_SOC_MEDIAN_PERCENT)
        config.INITIAL_SOC_MIN_PERCENT = float(st.session_state.INITIAL_SOC_MIN_PERCENT)
        config.INITIAL_SOC_STD_PERCENT = float(st.session_state.INITIAL_SOC_STD_PERCENT)
        config.INITIAL_SOC_FRACTION_AT_FLOOR = float(st.session_state.INITIAL_SOC_FRACTION_AT_FLOOR)

        st.session_state.site = initialize_simulation()
        st.session_state.running = True

    if stop_clicked:
        st.session_state.running = False


def draw_main_view() -> None:
    st.title("BESS Digital Twin & Performance Simulator")
    placeholder = st.empty()
    progress = st.progress(int(st.session_state.progress * 100))

    if st.session_state.running and st.session_state.site is not None:
        total_steps = int(config.TOTAL_STEPS)
        step_count = 0
        for site in execute_simulation_step(st.session_state.site, time_step_s=int(config.TIME_STEP_SECONDS), max_steps=total_steps):
            step_count += 1
            st.session_state.progress = step_count / max(1, total_steps)
            progress.progress(int(st.session_state.progress * 100))
            with placeholder.container():
                st.subheader(f"Time: {site.current_time_s/3600:.2f} h | State: {site.test_state}")
                c1, c2, c3 = st.columns(3)
                c1.metric("Site Target Power (MW)", f"{site.get_site_target_power():.1f}")
                # Average container SOC
                socs = []
                for g in site.inverter_groups:
                    for cont in g.containers:
                        socs.append(cont.get_soc())
                avg_soc = sum(socs) / len(socs) if socs else 0.0
                c2.metric("Average Container SOC (%)", f"{avg_soc:.2f}")
                # Voltage extremes
                vmins, vmaxs = [], []
                for g in site.inverter_groups:
                    for cont in g.containers:
                        vmin, vmax = cont.get_cell_voltage_extrema()
                        vmins.append(vmin)
                        vmaxs.append(vmax)
                min_v = min(vmins) if vmins else 0.0
                max_v = max(vmaxs) if vmaxs else 0.0
                c3.metric("Cell Voltage Range (V)", f"{min_v:.2f} – {max_v:.2f}")

            if not st.session_state.running:
                break
            time.sleep(0.01)
        st.session_state.running = False


def main() -> None:
    init_session_state()
    sidebar_controls()
    draw_main_view()


if __name__ == "__main__":
    main()


