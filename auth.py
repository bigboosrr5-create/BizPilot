import streamlit as st


def is_logged_in():
    return st.session_state.get("logged_in", False)


def get_business_id():
    return st.session_state.get("business_id")


def get_business_name():
    return st.session_state.get("business_name")


def get_owner_name():
    return st.session_state.get("owner_name")


def logout():
    st.session_state.clear()