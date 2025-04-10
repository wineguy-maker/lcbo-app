import streamlit as st

def verify_pin(input_pin, correct_pin):
    return input_pin == correct_pin

def is_authorized(session_state):
    return session_state.get("is_authorized", False)

def authorize_user(session_state, input_pin):
    correct_pin = st.secrets["correct_pin"]
    if verify_pin(input_pin, correct_pin):
        session_state["is_authorized"] = True
        return True
    return False

def logout_user(session_state):
    session_state["is_authorized"] = False