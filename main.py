import streamlit as st
import pandas as pd
import plotly.express as px
import requests
from datetime import datetime, timedelta

API_KEY = '53c365c5-8e53-4583-acf8-e9c37e6f00bd'
MAC_ADDRESS = 'D2:7E:14:56:24:41'
PAGE_SIZE = 20


def set_container_width(width):
    st.markdown(
        f"""
    <style>
        .reportview-container .main .block-container{{
            max-width: {width}px;
        }}
    </style>
    """,
        unsafe_allow_html=True,
    )


def plot_line_chart(data, x_column, y_column, title, width=None):
    fig = px.line(data, x=x_column, y=y_column, title=title)

    if width:
        fig.update_layout(autosize=False, width=width)

    st.plotly_chart(fig)


def fetch_data(start_date, end_date):
    url = 'https://api.atmotube.com/api/v1/data'
    params = {
        'api_key': API_KEY,
        'mac': MAC_ADDRESS,
        'limit': 100,
        'offset': 0,
        'order': 'desc',
        'start_date': start_date,
        'end_date': end_date,
        'format': 'json'
    }

    response = requests.get(url, params=params)
    if response.status_code == 200:
        return response.json()
    else:
        st.error(f"Error fetching data: {response.text}")
        return None


def main():
    st.set_page_config(layout="wide")
    set_container_width(1200)

    st.title("TwinBAS - Data Visualization Tool")

    today = datetime.today().date()
    day_before = today - timedelta(days=1)

    default_end_date = today.strftime('%Y-%m-%d')
    default_start_date = day_before.strftime('%Y-%m-%d')

    col1, col2 = st.columns(2)
    start_date_input = col1.date_input('Start Date', day_before)
    end_date_input = col2.date_input('End Date', today)

    if 'data' not in st.session_state:
        st.session_state.data = None

    if st.button("Fetch Data"):
        st.session_state.data = fetch_data(start_date_input.strftime('%Y-%m-%d'), end_date_input.strftime('%Y-%m-%d'))

    if st.session_state.data and "data" in st.session_state.data and "items" in st.session_state.data["data"]:

        df = pd.DataFrame(st.session_state.data["data"]["items"])

        if not df.empty:
            if 'time' in df.columns and 't' in df.columns:
                plot_line_chart(df, 'time', 't', 'Indoor Temperature', width=1150)
            if 'time' in df.columns and 'h' in df.columns:
                plot_line_chart(df, 'time', 'h', 'Indoor Humidity', width=1150)
            if 'time' in df.columns and 'voc' in df.columns:
                plot_line_chart(df, 'time', 'voc', 'TVOCs', width=1150)
            if 'time' in df.columns and 'pm25' in df.columns:
                plot_line_chart(df, 'time', 'pm25', 'PM2.5', width=1150)

            num_pages = max(1, len(df) // PAGE_SIZE + (1 if len(df) % PAGE_SIZE else 0))

            page = st.selectbox("Select page", list(range(1, num_pages + 1)))

            start_idx = (page - 1) * PAGE_SIZE
            end_idx = start_idx + PAGE_SIZE
            st.table(df.iloc[start_idx:end_idx])
        else:
            st.warning("No data available for the selected date range.")


if __name__ == '__main__':
    main()
