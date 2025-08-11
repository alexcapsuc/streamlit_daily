import streamlit as st

def multi_with_all(
    label: str,
    options,
    key: str,
    format_func=None,
    # selected_values: list = [],
    default_all: bool = True,
):
    """
    A multiselect with an adjacent 'All' checkbox that:
      - When checked: selects all options
      - When unchecked: clears selection
      - If user manually selects all: checkbox auto-ticks
      - If user deselects any: checkbox auto-unticks

    Args
    ----
    options: list of option IDs OR dict[id] -> display_name
    key: unique base key for widget state
    format_func: maps an ID -> display label (optional if options is dict)
    # selected_values: currently selected values
    default_all: if True and no prior state, start with 'All' selected

    Returns
    -------
    List of selected IDs
    """
    # Normalize options to (ids, label_func)
    if isinstance(options, dict):
        option_ids = list(options.keys())
        label_func = (lambda _id: options.get(_id, str(_id)))
    else:
        option_ids = list(options)
        label_func = (lambda _id: str(_id))

    if format_func:
        label_func = format_func

    ms_key = f"{key}__ms"
    all_key = f"{key}__all"

    # Initial defaults
    if ms_key not in st.session_state:
        st.session_state[ms_key] = option_ids if default_all else []
    if all_key not in st.session_state:
        st.session_state[all_key] = (len(st.session_state[ms_key]) == len(option_ids) and len(option_ids) > 0)

    # Callbacks
    def _on_all_change():
        if st.session_state[all_key]:
            st.session_state[ms_key] = option_ids[:]  # select all
        else:
            st.session_state[ms_key] = []            # select none

    def _on_ms_change():
        sel = st.session_state[ms_key]
        st.session_state[all_key] = (len(sel) == len(option_ids) and len(option_ids) > 0)

    # Render
    col1, col2 = st.columns([3, 1])
    with col1:
        st.sidebar.multiselect(
            label,
            options=option_ids,
            default=st.session_state[ms_key],
            key=ms_key,
            on_change=_on_ms_change,
            format_func=label_func,
        )
    with col2:
        st.sidebar.checkbox("All", key=all_key, on_change=_on_all_change)

    return st.session_state[ms_key], st.session_state[all_key]
