from __future__ import annotations

import json
from typing import List

import streamlit as st

import config


def ensure_session_state_defaults() -> None:
    if 'initialized' in st.session_state:
        return
    st.session_state.initialized = True

    # Legacy controls (still used by Run action as defaults)
    st.session_state.TIME_STEP_SECONDS = int(getattr(config, 'TIME_STEP_SECONDS', 1))
    st.session_state.SIMULATION_DURATION_HOURS = float(getattr(config, 'SIMULATION_DURATION_HOURS', 10))
    st.session_state.SITE_TARGET_POWER_MW = float(getattr(config, 'SITE_TARGET_POWER_MW', 40.0))
    st.session_state.RAMP_DURATION_SECONDS = int(getattr(config, 'RAMP_DURATION_SECONDS', 30))
    st.session_state.CHARGE_TAPER_DURATION_SECONDS = int(getattr(config, 'CHARGE_TAPER_DURATION_SECONDS', 60))
    st.session_state.DISCHARGE_TAPER_DURATION_SECONDS = int(getattr(config, 'DISCHARGE_TAPER_DURATION_SECONDS', 60))
    st.session_state.HEAT_SOAK_DURATION_HOURS = float(getattr(config, 'HEAT_SOAK_DURATION_HOURS', 2.0))

    st.session_state.INVERTER_GROUP_CONTAINER_COUNTS = list(getattr(config, 'INVERTER_GROUP_CONTAINER_COUNTS', []))
    st.session_state.NUM_INVERTER_GROUPS = int(getattr(config, 'NUM_INVERTER_GROUPS', 2))
    st.session_state.CONTAINERS_PER_GROUP = int(getattr(config, 'CONTAINERS_PER_GROUP', 2))

    # BMS & balancing (exposed optionally in future pages)
    st.session_state.L2_CALIBRATE_LOW_VOLTAGE = float(getattr(config, 'L2_CALIBRATE_LOW_VOLTAGE', 3.0))
    st.session_state.L2_CUTOFF_LOW_VOLTAGE = float(getattr(config, 'L2_CUTOFF_LOW_VOLTAGE', 2.8))
    st.session_state.L2_CALIBRATE_HIGH_VOLTAGE = float(getattr(config, 'L2_CALIBRATE_HIGH_VOLTAGE', 3.45))
    st.session_state.L2_CUTOFF_HIGH_VOLTAGE = float(getattr(config, 'L2_CUTOFF_HIGH_VOLTAGE', 3.6))
    st.session_state.BALANCING_TOP_SOC_START = float(getattr(config, 'BALANCING_TOP_SOC_START', 94.0))
    st.session_state.BALANCING_BOTTOM_SOC_END = float(getattr(config, 'BALANCING_BOTTOM_SOC_END', 6.0))
    st.session_state.BALANCING_BLEED_CURRENT_A = float(getattr(config, 'BALANCING_BLEED_CURRENT_A', 0.6))

    # Initial SOC distribution (legacy UI)
    st.session_state.INITIAL_SOC_MEDIAN_PERCENT = float(getattr(config, 'INITIAL_SOC_MEDIAN_PERCENT', 6.6))
    st.session_state.INITIAL_SOC_STD_PERCENT = float(getattr(config, 'INITIAL_SOC_STD_PERCENT', 1.2))
    st.session_state.INITIAL_SOC_MIN_PERCENT = float(getattr(config, 'INITIAL_SOC_MIN_PERCENT', getattr(config, 'MIN_SAFE_SOC', 5.2)))
    st.session_state.INITIAL_SOC_MAX_PERCENT = float(getattr(config, 'INITIAL_SOC_MAX_PERCENT', 12.0))
    st.session_state.INITIAL_SOC_FRACTION_AT_FLOOR = float(getattr(config, 'INITIAL_SOC_FRACTION_AT_FLOOR', 0.4))

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
    equip_specs = sim_cfg.get('equipment_specs') or {}

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

    st.session_state.EQUIPMENT_SPECS_JSON = json.dumps(equip_specs, indent=2)


def render_equipment_tree_editor() -> None:
    """Interactive editor for inverter -> batteries (containers) tree.

    Uses st.session_state.INVERTER_GROUP_CONTAINER_COUNTS as the backing model.
    """
    if not isinstance(st.session_state.INVERTER_GROUP_CONTAINER_COUNTS, list):
        st.session_state.INVERTER_GROUP_CONTAINER_COUNTS = []

    counts: List[int] = [int(c) for c in st.session_state.INVERTER_GROUP_CONTAINER_COUNTS]

    total_inverters = len(counts)
    total_batteries = sum(counts) if counts else 0
    m1, m2 = st.columns(2)
    m1.metric("Total Inverters", total_inverters)
    m2.metric("Total Batteries", total_batteries)

    if st.button("+ Add Inverter", key="btn_add_inverter_shared"):
        counts.append(0)

    remove_index = None
    for idx, value in enumerate(counts):
        with st.expander(f"Inverter {idx + 1}", expanded=False):
            row = st.columns([1.5, 1, 1, 1])
            row[0].write(f"Batteries: {int(value)}")
            if row[1].button("+ Add Battery", key=f"btn_add_battery_shared_{idx}"):
                counts[idx] = int(counts[idx]) + 1
            if row[2].button("- Remove Battery", key=f"btn_rem_battery_shared_{idx}"):
                counts[idx] = max(0, int(counts[idx]) - 1)
            if row[3].button("Remove Inverter", key=f"btn_remove_inverter_shared_{idx}"):
                remove_index = idx

    if remove_index is not None and 0 <= remove_index < len(counts):
        counts.pop(remove_index)

    st.session_state.INVERTER_GROUP_CONTAINER_COUNTS = counts


