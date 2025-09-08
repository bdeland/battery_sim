from __future__ import annotations

import json
import streamlit as st

import config
from ui_shared import ensure_session_state_defaults


def main() -> None:
    st.set_page_config(page_title="Step 1 – Equipment Specifications", layout="wide")
    ensure_session_state_defaults()

    st.title("Step 1 – Equipment Specifications")
    st.caption("Define component-level specs. Stored in SIMULATION_CONFIG['equipment_specs'] as JSON.")

    st.session_state.EQUIPMENT_SPECS_JSON = st.text_area(
        "Equipment Specs JSON",
        value=st.session_state.EQUIPMENT_SPECS_JSON,
        height=400,
    )

    if st.button("Validate JSON"):
        try:
            _ = json.loads(st.session_state.EQUIPMENT_SPECS_JSON) if st.session_state.EQUIPMENT_SPECS_JSON.strip() else {}
            st.success("JSON is valid.")
        except Exception as exc:
            st.error(f"Invalid JSON: {exc}")


if __name__ == "__main__":
    main()


