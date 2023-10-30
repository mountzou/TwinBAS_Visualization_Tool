import streamlit as st
import pandas as pd
import plotly.express as px
import requests
from datetime import datetime, timedelta
import math

API_KEY = '53c365c5-8e53-4583-acf8-e9c37e6f00bd'
MAC_ADDRESS = 'D2:7E:14:56:24:41'
PAGE_SIZE = 20


def calculate_pmv(temperature, relative_humidity):
    # Constants
    met = 1.0  # metabolic rate
    va = 0  # air velocity
    tr = temperature  # mean radiant temperature
    clo = 0.5  # clothing insulation

    pa = relative_humidity * 10  # water vapor pressure

    # Fanger's PMV equation parameters
    icl = 0.155 * clo  # clothing insulation in M2K/W
    m = met * 58.15  # metabolic rate in W/M2
    w = 0  # external work in W/M2, usually it's 0
    mw = m - w  # internal heat production in the human body
    if icl <= 0.078:
        fcl = 1 + (1.29 * icl)
    else:
        fcl = 1.05 + (0.645 * icl)

    # thermal insulation of the clothing in M2K/W
    hcf = 12.1 * (va ** 0.5)
    taa = temperature + 273
    tra = tr + 273
    tcla = taa + (35.5 - temperature) / (3.5 * (6.45 * icl + 0.1))

    p1 = icl * fcl
    p2 = p1 * 3.96
    p3 = p1 * 100
    p4 = p1 * taa
    p5 = (308.7 - 0.028 * mw) + (p2 * ((tra / 100) ** 4))
    xn = tcla / 100
    xf = tcla / 50
    eps = 0.00015

    hc = hcf  # Initialize hc before the loop

    n = 0
    while abs(xn - xf) > eps:
        xf = (xf + xn) / 2
        hcn = 2.38 * abs(100.0 * xf - taa) ** 0.25
        if hcf > hcn:
            hc = hcf
        else:
            hc = hcn
        xn = (p5 + p4 * hc - p2 * (xf ** 4)) / (100 + p3 * hc)
        n += 1
        if n > 150:
            break

    tcl = 100 * xn - 273

    # final PMV calculation
    hl1 = 3.05 * 0.001 * (5733 - 6.99 * mw - pa)
    hl2 = 0.42 * (mw - 58.15)
    hl3 = 1.7 * 0.00001 * m * (5867 - pa)
    hl4 = 0.0014 * m * (34 - temperature)
    hl5 = 3.96 * fcl * (xn ** 4 - (tra / 100) ** 4)
    hl6 = fcl * hc * (tcl - temperature)

    ts = 0.303 * (math.exp(-0.036 * m) + 0.028)
    pmv = ts * (mw - hl1 - hl2 - hl3 - hl4 - hl5 - hl6)

    return pmv


def calculate_combined_aqi(pm25_concentration, pm10_concentration):
    pm25_aqi = calculate_aqi(pm25_concentration, 'pm25')
    pm10_aqi = calculate_aqi(pm10_concentration, 'pm10')

    if pm25_aqi is None or pm10_aqi is None:
        return None

    combined_aqi = (pm25_aqi + pm10_aqi) * 0.5
    return round(combined_aqi)


def calculate_aqi(concentration, pollutant):
    if pollutant not in ['pm25', 'pm10']:
        return None

    breakpoints = {
        'pm25': [(0, 10), (11, 20), (21, 25), (26, 50), (51, 75), (76, 800)],
        'pm10': [(0, 20), (21, 35), (36, 50), (51, 100), (101, 150), (151, 1200)]
    }

    i_values = [(0, 25), (26, 50), (51, 75), (76, 100), (101, 125), (126, 200)]

    for bp_low, bp_high in breakpoints[pollutant]:
        if bp_low <= concentration <= bp_high:
            i_low, i_high = i_values[breakpoints[pollutant].index((bp_low, bp_high))]
            aqi = ((i_high - i_low) / (bp_high - bp_low)) * (concentration - bp_low) + i_low
            return round(aqi)


def get_pm25_description(pm25_value):
    aqi = calculate_aqi(pm25_value, 'pm25')
    if aqi is None:
        return "Unknown AQI"

    if 0 <= aqi <= 25:
        return "Air quality is considered satisfactory."
    elif 26 <= aqi <= 50:
        return "Air quality is acceptable."
    elif 51 <= aqi <= 75:
        return "Moderate air quality."
    elif 76 <= aqi <= 100:
        return "High air pollution. Health warnings."
    elif 101 <= aqi <= 125:
        return "Very high air pollution. Health alert."
    elif 126 <= aqi <= 200:
        return "Extremely high air pollution. Health warnings of emergency conditions."
    else:
        return "Unable to determine the air quality."


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

        df['Air Quality Description'] = df['pm25'].apply(get_pm25_description)
        df['pmv'] = df.apply(lambda row: calculate_pmv(row['t'], row['h']), axis=1)

        if not df.empty:
            if 'time' in df.columns and 't' in df.columns:
                plot_line_chart(df, 'time', 't', 'Indoor Temperature', width=1150)
            if 'time' in df.columns and 'h' in df.columns:
                plot_line_chart(df, 'time', 'h', 'Indoor Humidity', width=1150)
            if 'time' in df.columns and 'voc' in df.columns:
                plot_line_chart(df, 'time', 'voc', 'TVOCs', width=1150)
            if 'time' in df.columns and 'pm25' in df.columns:
                plot_line_chart(df, 'time', 'pm25', 'PM2.5', width=1150)
            if 'time' in df.columns and 'pmv' in df.columns:
                plot_line_chart(df, 'time', 'pmv', 'PMV (Thermal Comfort)', width=1150)

            # Count the frequency of each description
            description_counts = df['Air Quality Description'].value_counts()

            # Plot the frequencies using a bar chart
            fig = px.bar(description_counts, x=description_counts.index, y=description_counts.values, title="Frequency of Air Quality Index", labels={
                'y': 'Frequency', 'index': 'Description'})
            st.plotly_chart(fig, width=1150)

            num_pages = max(1, len(df) // PAGE_SIZE + (1 if len(df) % PAGE_SIZE else 0))

            page = st.selectbox("Select page", list(range(1, num_pages + 1)))

            start_idx = (page - 1) * PAGE_SIZE
            end_idx = start_idx + PAGE_SIZE
            st.table(df.iloc[start_idx:end_idx])
        else:
            st.warning("No data available for the selected date range.")


if __name__ == '__main__':
    main()
