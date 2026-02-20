import streamlit as st
import threading
from src.services.session_manager import SessionManager

ev_session = SessionManager()
ev_session.initialize_session()

st.set_page_config(
    page_title="data explorer",
    page_icon="🌟",
    layout="wide",
    initial_sidebar_state="expanded",
)

def main():
    st.title("Data Explorer")
    st.error("This section is under construction...")
    
    
if __name__ == "__main__":
    main()