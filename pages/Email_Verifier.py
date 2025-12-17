import streamlit as st
import pandas as pd
import os
import tempfile
from src.services.session_manager import SessionManager
from src.services.email_verifier import EmailVerifier

ev_session = SessionManager()
ev = EmailVerifier()

st.set_page_config(
    page_title="Email Verifier",
    page_icon="📧",
    layout="wide",
)



def email_verifier():
    input = ev_session.get("ev_upload_csv_filepath")
    output = ev_session.get("ev_output_csv_filepath")
    
    with tempfile.NamedTemporaryFile(delete=False) as tmp_file:
        tmp_file.write(input.getvalue())
        tmp_path = tmp_file.name
        
    try:
        df_results, summary = ev.process_emails_in_bulk(input_path=tmp_path, output_path=output)
        return df_results, summary
    except Exception as e:
        print(f"Error Verifying Emails in Bulk: {e}")
        return None, None
    
    
def main():
    st.title("Email Verifier")
    st.subheader("Upload your file")
    upload_csv_filepaths = st.file_uploader("Upload your CSV file...", type=["csv"], key="email-verifier-upload", )
    ev_session.set("ev_upload_csv_filepath", upload_csv_filepaths)
    
    if upload_csv_filepaths:
        df_input = pd.read_csv(upload_csv_filepaths)
        st.write(df_input)
    
    if st.button("Start Bulk Validation"):
        if not upload_csv_filepaths:
            st.error("No CSV file uploaded yet...")
        
        with tempfile.NamedTemporaryFile(delete=False, suffix=".csv") as tmp:
            tmp.write(upload_csv_filepaths.getvalue())
            tmp_path = tmp.name
        
        with st.spinner("Processing..."):
            df_results, summary = email_verifier()
            
            ev_session.set("df_results", df_results)
            ev_session.set("summary", summary)
            
    if ev_session.get("df_results") is not None:
        df_results = ev_session.get("df_results")
        summary = ev_session.get("summary")
        st.divider()
        st.subheader("Results Preview")
        st.dataframe(df_results.head())
        
        col1, col2 = st.columns([0.85, 0.115])
        
        with col1:
            st.subheader("Summary")
            st.write(summary)
            
        with col2:
            csv_data = df_results.to_csv(index=False).encode('utf-8')
            
            st.download_button(
                label="Download Full Results as CSV",
                data=csv_data,
                file_name="validated_emails.csv",
                mime="text/csv"
            )
    
if __name__ == "__main__":
    main()