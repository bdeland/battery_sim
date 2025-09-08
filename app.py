from __future__ import annotations

import time
from typing import List
import json

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

    # SIMULATION_CONFIG defaults
    sim_cfg = getattr(config, 'SIMULATION_CONFIG', {}) or {}
    sim_ctrl = sim_cfg.get('simulation_control') or {}
    env_cfg = sim_cfg.get('environmental_conditions') or {}
    init_state = sim_cfg.get('bess_initial_state') or {}
    test_seq = sim_cfg.get('test_sequence') or []
    inv_groups_cfg = sim_cfg.get('inverter_groups_config') or []

    st.session_state.SIM_START_DATETIME_UTC = sim_ctrl.get('start_datetime_utc') or ''
    st.session_state.SIM_TIME_STEP_SECONDS = int(sim_ctrl.get('time_step_seconds', config.TIME_STEP_SECONDS))
    st.session_state.SIM_DURATION_HOURS = float(sim_ctrl.get('duration_hours', config.SIMULATION_DURATION_HOURS))

    st.session_state.ENV_MODE = (env_cfg.get('mode') or 'constant')
    st.session_state.ENV_AMBIENT_T_C = float(env_cfg.get('ambient_temperature_c', getattr(config, 'AMBIENT_TEMPERATURE_C', 25.0)))
    st.session_state.ENV_SOLAR_W_M2 = float(env_cfg.get('solar_irradiance_w_per_m2', 800.0))
    st.session_state.ENV_LOCATION_ADDRESS = (env_cfg.get('location') or {}).get('address') if isinstance(env_cfg.get('location'), dict) else ''
    provider = env_cfg.get('historical_data_provider') or {}
    st.session_state.ENV_PROVIDER_API_NAME = provider.get('api_name') or ''
    st.session_state.ENV_PROVIDER_BASE_URL = provider.get('api_base_url') or ''

    st.session_state.INIT_SOC_DIST_TYPE = (init_state.get('soc_distribution_type') or 'normal')
    st.session_state.INIT_SOC_MEAN = float(init_state.get('soc_mean_percent', 8.0))
    st.session_state.INIT_SOC_STD = float(init_state.get('soc_std_dev_percent', 1.5))
    st.session_state.INIT_CELL_TEMP_C = float(init_state.get('cell_temperatures_c', getattr(config, 'AMBIENT_TEMPERATURE_C', 25.0)))

    st.session_state.USE_TEST_SEQUENCE = bool(test_seq)
    st.session_state.TEST_SEQUENCE_JSON = json.dumps(test_seq, indent=2)

    st.session_state.USE_STRUCTURED_WIRING = bool(inv_groups_cfg)
    st.session_state.INVERTER_GROUPS_CONFIG_JSON = json.dumps(inv_groups_cfg, indent=2)


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
        st.session_state.SIM_START_DATETIME_UTC = st.text_input("Start DateTime UTC (ISO)", value=str(st.session_state.SIM_START_DATETIME_UTC))

    with st.sidebar.expander("Environmental Conditions", expanded=False):
        st.session_state.ENV_MODE = st.selectbox("Mode", options=["constant", "historical"], index=0 if st.session_state.ENV_MODE == 'constant' else 1)
        if st.session_state.ENV_MODE == 'constant':
            st.session_state.ENV_AMBIENT_T_C = st.number_input("Ambient Temperature (°C)", value=float(st.session_state.ENV_AMBIENT_T_C))
            st.session_state.ENV_SOLAR_W_M2 = st.number_input("Solar Irradiance (W/m²)", value=float(st.session_state.ENV_SOLAR_W_M2))
        else:
            st.session_state.ENV_LOCATION_ADDRESS = st.text_input("Location (address)", value=str(st.session_state.ENV_LOCATION_ADDRESS))
            st.session_state.ENV_PROVIDER_API_NAME = st.text_input("Provider API Name", value=str(st.session_state.ENV_PROVIDER_API_NAME))
            st.session_state.ENV_PROVIDER_BASE_URL = st.text_input("Provider Base URL", value=str(st.session_state.ENV_PROVIDER_BASE_URL))

    with st.sidebar.expander("Site Layout", expanded=True):
        st.session_state.USE_STRUCTURED_WIRING = st.checkbox("Use structured wiring diagram (Step 2)", value=bool(st.session_state.USE_STRUCTURED_WIRING))
        if st.session_state.USE_STRUCTURED_WIRING:
            st.caption("Edit JSON for inverter_groups_config (list of {group_id, containers_in_group}).")
            st.session_state.INVERTER_GROUPS_CONFIG_JSON = st.text_area("inverter_groups_config JSON", value=st.session_state.INVERTER_GROUPS_CONFIG_JSON, height=200)
        else:
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

    with st.sidebar.expander("Initial State (SIMULATION_CONFIG)", expanded=False):
        st.session_state.INIT_SOC_DIST_TYPE = st.selectbox("SOC Distribution Type", options=["uniform", "normal"], index=1 if st.session_state.INIT_SOC_DIST_TYPE == 'normal' else 0)
        st.session_state.INIT_SOC_MEAN = st.number_input("SOC Mean (%)", value=float(st.session_state.INIT_SOC_MEAN))
        st.session_state.INIT_SOC_STD = st.number_input("SOC StdDev (%)", min_value=0.0, value=float(st.session_state.INIT_SOC_STD))
        st.session_state.INIT_CELL_TEMP_C = st.number_input("Cell Temperature (°C)", value=float(st.session_state.INIT_CELL_TEMP_C))

    with st.sidebar.expander("Test Sequence (Step 4)", expanded=False):
        st.session_state.USE_TEST_SEQUENCE = st.checkbox("Use test_sequence (overrides built-in test state machine)", value=bool(st.session_state.USE_TEST_SEQUENCE))
        st.caption("Edit JSON array of steps. Only 'real_power_mw' affects power currently; negative=charge, positive=discharge.")
        st.session_state.TEST_SEQUENCE_JSON = st.text_area("test_sequence JSON", value=st.session_state.TEST_SEQUENCE_JSON, height=200)

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

        # SIMULATION_CONFIG assembly
        sim_cfg = getattr(config, 'SIMULATION_CONFIG', {}) or {}
        sim_cfg['simulation_control'] = {
            'start_datetime_utc': st.session_state.SIM_START_DATETIME_UTC or None,
            'duration_hours': float(st.session_state.SIM_DURATION_HOURS),
            'time_step_seconds': int(st.session_state.SIM_TIME_STEP_SECONDS),
        }
        if st.session_state.ENV_MODE == 'constant':
            sim_cfg['environmental_conditions'] = {
                'mode': 'constant',
                'ambient_temperature_c': float(st.session_state.ENV_AMBIENT_T_C),
                'solar_irradiance_w_per_m2': float(st.session_state.ENV_SOLAR_W_M2),
            }
        else:
            sim_cfg['environmental_conditions'] = {
                'mode': 'historical',
                'location': {'address': st.session_state.ENV_LOCATION_ADDRESS} if st.session_state.ENV_LOCATION_ADDRESS else None,
                'historical_data_provider': {
                    'api_name': st.session_state.ENV_PROVIDER_API_NAME or None,
                    'api_base_url': st.session_state.ENV_PROVIDER_BASE_URL or None,
                }
            }
        sim_cfg['bess_initial_state'] = {
            'soc_distribution_type': st.session_state.INIT_SOC_DIST_TYPE,
            'soc_mean_percent': float(st.session_state.INIT_SOC_MEAN),
            'soc_std_dev_percent': float(st.session_state.INIT_SOC_STD),
            'cell_temperatures_c': float(st.session_state.INIT_CELL_TEMP_C),
        }
        # Test sequence parsing
        if bool(st.session_state.USE_TEST_SEQUENCE):
            try:
                sim_cfg['test_sequence'] = json.loads(st.session_state.TEST_SEQUENCE_JSON) if st.session_state.TEST_SEQUENCE_JSON.strip() else []
            except Exception as exc:
                st.warning(f"Invalid test_sequence JSON, ignoring. Details: {exc}")
                sim_cfg['test_sequence'] = []
        else:
            sim_cfg['test_sequence'] = []

        # Wiring diagram parsing
        if bool(st.session_state.USE_STRUCTURED_WIRING):
            try:
                sim_cfg['inverter_groups_config'] = json.loads(st.session_state.INVERTER_GROUPS_CONFIG_JSON) if st.session_state.INVERTER_GROUPS_CONFIG_JSON.strip() else []
            except Exception as exc:
                st.warning(f"Invalid inverter_groups_config JSON, ignoring. Details: {exc}")
                sim_cfg['inverter_groups_config'] = []
            # Ensure legacy layout disabled
            config.INVERTER_GROUP_CONTAINER_COUNTS = []
        else:
            sim_cfg['inverter_groups_config'] = []
            use_custom_counts = bool(st.session_state.INVERTER_GROUP_CONTAINER_COUNTS)
            if use_custom_counts:
                config.INVERTER_GROUP_CONTAINER_COUNTS = list(st.session_state.INVERTER_GROUP_CONTAINER_COUNTS)
            else:
                config.INVERTER_GROUP_CONTAINER_COUNTS = []
                config.NUM_INVERTER_GROUPS = int(st.session_state.NUM_INVERTER_GROUPS)
                config.CONTAINERS_PER_GROUP = int(st.session_state.CONTAINERS_PER_GROUP)

        # Apply SIMULATION_CONFIG and sync legacy globals
        config.SIMULATION_CONFIG = sim_cfg
        if hasattr(config, '_apply_simulation_config'):
            config._apply_simulation_config()

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


