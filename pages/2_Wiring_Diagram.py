from __future__ import annotations

import json
import streamlit as st

from ui_shared import ensure_session_state_defaults, render_equipment_tree_editor


def main() -> None:
    st.set_page_config(page_title="Step 2 – Wiring Diagram", layout="wide")
    ensure_session_state_defaults()

    st.title("Step 2 – Wiring Diagram")

    st.session_state.USE_STRUCTURED_WIRING = st.checkbox(
        "Use structured wiring diagram (inverter_groups_config)", value=bool(st.session_state.USE_STRUCTURED_WIRING)
    )
    if st.session_state.USE_STRUCTURED_WIRING:
        st.caption("Provide JSON for list of objects: {group_id, containers_in_group}")
        st.session_state.INVERTER_GROUPS_CONFIG_JSON = st.text_area(
            "inverter_groups_config JSON",
            value=st.session_state.INVERTER_GROUPS_CONFIG_JSON,
            height=300,
        )
        if st.button("Validate JSON", key="btn_validate_wiring_json"):
            try:
                _ = json.loads(st.session_state.INVERTER_GROUPS_CONFIG_JSON) if st.session_state.INVERTER_GROUPS_CONFIG_JSON.strip() else []
                st.success("JSON is valid.")
            except Exception as exc:
                st.error(f"Invalid JSON: {exc}")
    else:
        st.caption("Use simple per-inverter container counts editor.")
        render_equipment_tree_editor()


if __name__ == "__main__":
    main()


