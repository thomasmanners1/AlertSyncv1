import streamlit as st
import pandas as pd
import re
from datetime import datetime
from fuzzywuzzy import fuzz
import io

# Function to load data
def load_data(csv_file, excel_file):
    new_alerts_df = pd.read_csv(csv_file)
    prev_data = {
        'Open Known Issues': pd.read_excel(excel_file, sheet_name='Open Known Issues'),
        'Closed Known Issues': pd.read_excel(excel_file, sheet_name='Closed Known Issues'),
        'SNS Daily Checks': pd.read_excel(excel_file, sheet_name='SNS Daily Checks')
    }
    return new_alerts_df, prev_data

# Refined regex match
def refined_regex_match(new_error, known_error):
    pattern = (
        r'L_ORDER_\d+|'                    # Order numbers
        r'EventId: [\w-]+|'                # Event IDs
        r'\b\d{4}-\d{2}-\d{2}\b|'          # Dates
        r'\b\d{2}:\d{2}:\d{2}\b|'          # Timestamps
        r'[_\d\w]+\.go|'                   # Filenames
        r'[_\d\w]+\.xml|'                  # XML filenames
        r'UUID_[0-9a-fA-F-]{36}|'          # UUIDs
        r'\b[A-Z]{3,4} \d{3} [A-Za-z ]+"|' # HTTP Status Codes
        r'https?:\/\/[^\s]+|'              # URLs
        r'\/[\w\.-]+(?:\/[\w\.-]+)*|'      # File paths
        r'\b\d+\b'                         # Standalone numbers
    )
    
    new_error_cleaned = re.sub(pattern, '', str(new_error)).strip()
    known_error_cleaned = re.sub(pattern, '', str(known_error)).strip()

    similarity = fuzz.partial_ratio(new_error_cleaned, known_error_cleaned)
    return similarity >= 75 

# Matching alerts
def improved_match_alerts(new_alerts_df, prev_data):
    new_alerts_df['Notes'] = ""
    new_alerts_df['Escalation Link'] = ""

    for sheet_name in ['Open Known Issues', 'Closed Known Issues']:
        known_issues_df = prev_data[sheet_name]

        for index, row in new_alerts_df.iterrows():
            asset = row['Asset']
            alert = row['Error']

            matches = known_issues_df[known_issues_df['Asset'] == asset]
            for _, match in matches.iterrows():
                if refined_regex_match(alert, match['Error']):
                    notes_value = match.get('Notes', '')
                    escalation_value = match.get('Escalation Link', '')

                    if pd.notna(notes_value):
                        new_alerts_df.at[index, 'Notes'] = f"{new_alerts_df.at[index, 'Notes']}; {notes_value}" if new_alerts_df.at[index, 'Notes'] else notes_value
                    if pd.notna(escalation_value):
                        new_alerts_df.at[index, 'Escalation Link'] = f"{new_alerts_df.at[index, 'Escalation Link']}; {escalation_value}" if new_alerts_df.at[index, 'Escalation Link'] else escalation_value

    return new_alerts_df

# Save to Excel
def save_to_excel(new_alerts_df, prev_data):
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        new_alerts_df.to_excel(writer, sheet_name='SNS Daily Checks', index=False)

        for sheet_name, df in prev_data.items():
            if sheet_name in ['Open Known Issues', 'Closed Known Issues']:
                df.to_excel(writer, sheet_name=sheet_name, index=False)

        for sheet_name in writer.sheets:
            worksheet = writer.sheets[sheet_name]
            df_to_adjust = new_alerts_df if sheet_name == 'SNS Daily Checks' else prev_data[sheet_name]
            for idx, col in enumerate(df_to_adjust.columns):
                max_len = df_to_adjust[col].astype(str).map(len).max() + 2
                worksheet.set_column(idx, idx, max_len)

    output.seek(0)
    return output

# Streamlit App
st.title("Alert Matching Tool")

st.sidebar.header("Upload Files")
csv_file = st.sidebar.file_uploader("Upload CSV File", type="csv")
excel_file = st.sidebar.file_uploader("Upload Excel File", type=["xls", "xlsx"])

if csv_file and excel_file:
    try:
        st.write("### Uploaded Files")
        new_alerts_df, prev_data = load_data(csv_file, excel_file)

        st.write("#### CSV Data (Alerts)")
        st.dataframe(new_alerts_df.head())

        if st.button("Run Matching Process"):
            matched_alerts_df = improved_match_alerts(new_alerts_df, prev_data)
            st.success("Alerts matched successfully!")

            st.write("#### Matched Alerts")
            st.dataframe(matched_alerts_df.head())

            excel_output = save_to_excel(matched_alerts_df, prev_data)
            date_str = datetime.now().strftime('%Y-%m-%d')
            st.download_button(
                label="Download Updated Excel File",
                data=excel_output,
                file_name=f"SNS-Sheet-{date_str}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
    except Exception as e:
        st.error(f"An error occurred: {str(e)}")
else:
    st.info("Please upload both CSV and Excel files to proceed.")
