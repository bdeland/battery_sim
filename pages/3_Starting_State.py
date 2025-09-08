from __future__ import annotations

import streamlit as st

from ui_shared import ensure_session_state_defaults


def main() -> None:
    st.set_page_config(page_title="Step 3 – Parameters & Initial Conditions", layout="wide")
    ensure_session_state_defaults()

    st.title("Step 3 – Parameters & Initial Conditions")

    with st.expander("Simulation Control", expanded=True):
        st.session_state.SIM_START_DATETIME_UTC = st.text_input("Start DateTime UTC (ISO)", value=str(st.session_state.SIM_START_DATETIME_UTC))
        st.session_state.SIM_TIME_STEP_SECONDS = st.number_input("Time Step (seconds)", min_value=1, value=int(st.session_state.SIM_TIME_STEP_SECONDS))
        st.session_state.SIM_DURATION_HOURS = st.number_input("Duration (hours)", min_value=0.1, value=float(st.session_state.SIM_DURATION_HOURS))

    with st.expander("Environmental Conditions", expanded=False):
        st.session_state.ENV_MODE = st.selectbox("Mode", options=["constant", "historical"], index=0 if st.session_state.ENV_MODE == 'constant' else 1)
        if st.session_state.ENV_MODE == 'constant':
            st.session_state.ENV_AMBIENT_T_C = st.number_input("Ambient Temperature (°C)", value=float(st.session_state.ENV_AMBIENT_T_C))
            st.session_state.ENV_SOLAR_W_M2 = st.number_input("Solar Irradiance (W/m²)", value=float(st.session_state.ENV_SOLAR_W_M2))
        else:
            st.session_state.ENV_LOCATION_ADDRESS = st.text_input("Location (address)", value=str(st.session_state.ENV_LOCATION_ADDRESS))
            st.session_state.ENV_PROVIDER_API_NAME = st.text_input("Provider API Name", value=str(st.session_state.ENV_PROVIDER_API_NAME))
            st.session_state.ENV_PROVIDER_BASE_URL = st.text_input("Provider Base URL", value=str(st.session_state.ENV_PROVIDER_BASE_URL))

    with st.expander("Initial State", expanded=False):
        st.session_state.INIT_SOC_DIST_TYPE = st.selectbox("SOC Distribution Type", options=["uniform", "normal"], index=1 if st.session_state.INIT_SOC_DIST_TYPE == 'normal' else 0)
        st.session_state.INIT_SOC_MEAN = st.number_input("SOC Mean (%)", value=float(st.session_state.INIT_SOC_MEAN))
        st.session_state.INIT_SOC_STD = st.number_input("SOC StdDev (%)", min_value=0.0, value=float(st.session_state.INIT_SOC_STD))
        st.session_state.INIT_CELL_TEMP_C = st.number_input("Cell Temperature (°C)", value=float(st.session_state.INIT_CELL_TEMP_C))


if __name__ == "__main__":
    main()


