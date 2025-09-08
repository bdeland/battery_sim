from __future__ import annotations

import json
import streamlit as st

from ui_shared import ensure_session_state_defaults


def main() -> None:
    st.set_page_config(page_title="Step 4 – Test Sequence", layout="wide")
    ensure_session_state_defaults()

    st.title("Step 4 – Test Sequence")

    st.session_state.USE_TEST_SEQUENCE = st.checkbox(
        "Use test_sequence (overrides built-in test state machine)", value=bool(st.session_state.USE_TEST_SEQUENCE)
    )
    st.caption("Edit JSON array of steps. Only 'real_power_mw' affects power currently; negative=charge, positive=discharge.")
    st.session_state.TEST_SEQUENCE_JSON = st.text_area(
        "test_sequence JSON",
        value=st.session_state.TEST_SEQUENCE_JSON,
        height=400,
    )

    if st.button("Validate JSON", key="btn_validate_sequence_json"):
        try:
            _ = json.loads(st.session_state.TEST_SEQUENCE_JSON) if st.session_state.TEST_SEQUENCE_JSON.strip() else []
            st.success("JSON is valid.")
        except Exception as exc:
            st.error(f"Invalid JSON: {exc}")


if __name__ == "__main__":
    main()


