import streamlit as st
import os

class SessionManager:
    def __init__(self):
        self._initialize_session()
    
    def _initialize_session(self):
        if "ev_upload_csv_filepath" not in st.session_state:
            st.session_state.ev_upload_csv_file = None
            
        if "ev_output_csv_filepath" not in st.session_state:
            st.session_state.ev_output_csv_filepath = os.getcwd()
            
        if "results_df" not in st.session_state:
            st.session_state.results_df = None
            
        if "summary" not in st.session_state:
            st.session_state.results_df = None
            
        st.session_state["_initialized"] = True
            
    def get(self, key, default=None):
        """Get a session variable safely."""
        return st.session_state.get(key, default)
    
    def set(self, key, value):
        """Set a session variable."""
        st.session_state[key] = value