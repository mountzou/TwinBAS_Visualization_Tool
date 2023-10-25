import streamlit as st
import pandas as pd
import plotly.express as px
import requests
from datetime import datetime, timedelta

import requests

API_KEY = '53c365c5-8e53-4583-acf8-e9c37e6f00bd'
MAC_ADDRESS = 'D2:7E:14:56:24:41'


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
    st.title("ATMOTube Data Fetcher")

    today = datetime.today().date()
    day_before = today - timedelta(days=1)

    default_end_date = today.strftime('%Y-%m-%d')
    default_start_date = day_before.strftime('%Y-%m-%d')

    col1, col2 = st.columns(2)
    start_date_input = col1.date_input('Start Date', day_before)
    end_date_input = col2.date_input('End Date', today)

    if st.button("Fetch Data"):
        data = fetch_data(start_date_input.strftime('%Y-%m-%d'), end_date_input.strftime('%Y-%m-%d'))
        if data and "data" in data and "items" in data["data"]:
            st.table(data["data"]["items"])


if __name__ == '__main__':
    main()
