import streamlit as st
import pandas as pd
import plotly.express as px
import requests
from datetime import datetime, timedelta
import math
import mysql.connector
import pydeck as pdk
import plotly.figure_factory as ff
import plotly.graph_objects as go
import numpy as np


API_KEY = '53c365c5-8e53-4583-acf8-e9c37e6f00bd'
MAC_ADDRESS = 'D2:7E:14:56:24:41'
PAGE_SIZE = 20
DEV_UI = '0080e1150510a98f'


def get_met(start_datetime, end_datetime):
    config = {
        'user': 'root',
        'password': 'sQzWfQ56eSgYr4pVtZoew7tKq45GD1yM',
        'host': '7gpqlg.stackhero-network.com',
        'database': 'twinERGY',
        'raise_on_warnings': True
    }

    start_timestamp = int(start_datetime.timestamp())
    end_timestamp = int(end_datetime.timestamp())

    conn = mysql.connector.connect(**config)
    cursor = conn.cursor()

    query = """
    SELECT tc_met, tc_timestamp 
    FROM user_thermal_comfort 
    WHERE tc_timestamp >= %s 
    AND tc_timestamp <= %s 
    AND wearable_id = %s
    LIMIT 100
    """
    cursor.execute(query, (start_timestamp, end_timestamp, DEV_UI))

    # Fetch all results
    rows = cursor.fetchall()

    data = []
    for row in rows:
        met_value = row[0]
        timestamp = row[1]

        dt_object = datetime.utcfromtimestamp(timestamp)
        formatted_date = dt_object.strftime('%Y-%m-%dT%H:%M:%S.000Z')
        data.append((met_value, formatted_date))

    # Close the cursor and connection
    cursor.close()
    conn.close()

    df = pd.DataFrame(data, columns=['met', 'timestamp'])

    df['timestamp'] = pd.to_datetime(df['timestamp'])
    df.set_index('timestamp', inplace=True)
    result = df.resample('1T').mean()

    return result


def calculate_pmv(temperature, relative_humidity, met):
    # Constants
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
    hide_streamlit_style = """
                <style>
                footer {visibility: hidden;}
                </style>
                """
    st.markdown(hide_streamlit_style, unsafe_allow_html=True)

def plot_line_chart1(df, x, y, title, width=None):
    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=df[x],
            y=df[y],
            mode='lines',
            line=dict(width=2, color='#1f78b4'),
            marker=dict(size=6, color='#1f78b4'),
            hoverinfo='x+y',
            hovertemplate='<b>Thermal Comfort:</b> %{y}<br><b>Timestamp:</b> %{x}<extra></extra>'

        )
    )
    fig.update_layout(
        title=title,
        margin=dict(l=0, r=0, t=30, b=0),
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        # hovermode='x unified',
        hoverlabel=dict(
            bgcolor='white',
            font_size=16,
            font_family='Arial'
        ),
        xaxis_title=x,
        yaxis_title=y
    )
    if width:
        fig.update_layout(width=width)
    st.plotly_chart(fig, use_container_width=True)

def plot_line_chart(data, x_column, y_column, title, width=None):
    fig = px.line(data, x=x_column, y=y_column, title=title)

    if width:
        fig.update_layout(autosize=False, width=width)
    else:
        fig.update_layout(autosize=True)  # This will make Plotly attempt to size the plot to the container.

    st.plotly_chart(fig, use_container_width=True)  # This will make Streamlit size the container to the plot.


def plot_line_chart_pmv(data, x_column, y_column, title, width=None):
    fig = go.Figure()

    # Define the categories, boundaries, and their muted colors
    categories = {
        'Cold': (-3, -2.5, '#333399'),  # Darker Muted Blue
        'Cool': (-2.5, -1.5, '#6666CC'),  # Darker Medium Muted Blue
        'Slightly Cool': (-1.5, -0.5, '#9999CC'),  # Darker Light Muted Blue
        'Neutral': (-0.5, 0.5, '#80B380'),  # Darker Muted Green
        'Slightly Warm': (0.5, 1.5, '#FF9999'),  # Darker Light Muted Red
        'Warm': (1.5, 2.5, '#FF6666'),  # Darker Medium Muted Red
        'Hot': (2.5, 3, '#FF3333')  # Darker Dark Muted Red
    }

    # Add shaded regions for each category
    for category, (y0, y1, color) in categories.items():
        fig.add_shape(
            type='rect',
            x0=data[x_column].min(),
            x1=data[x_column].max(),
            y0=y0,
            y1=y1,
            fillcolor=color,
            line=dict(width=0),
            layer='below',
            opacity=0.6
        )


    # Add the line plot
    fig.add_trace(
        go.Scatter(
            x=data[x_column],
            y=data[y_column],
            mode='lines',
            line=dict(color='black', width=2),
            name="PMV"
        )
    )

    # Update the layout
    fig.update_layout(
        title=title,
        xaxis_title=x_column,
        yaxis_title=y_column,
        hovermode='closest',
        yaxis=dict(
            tickmode='array',
            tickvals=[-3, -2.5, -2, -1.5, -1, -0.5, 0, 0.5, 1, 1.5, 2, 2.5, 3],
            ticktext=[
                '-3 (Cold)', '-2.5', '-2 (Cool)', '-1.5', '-1 (Slightly Cool)', '-0.5',
                '0 (Neutral)', '0.5', '1 (Slightly Warm)', '1.5', '2 (Warm)', '2.5', '3 (Hot)'
           ]
        ),
        font = dict(color='black')
    )
    if width:
        fig.update_layout(autosize=False, width=width)
    else:
        fig.update_layout(autosize=True)  # This will make Plotly attempt to size the plot to the container.

    st.plotly_chart(fig, use_container_width=True)  # This will make Streamlit size the container to the plot.


def fetch_data(start_date, end_date):
    url = 'https://api.atmotube.com/api/v1/data'
    params = {
        'api_key': API_KEY,
        'mac': MAC_ADDRESS,
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

    default_end_date = datetime.today().date()
    default_start_date = datetime.today().date()- timedelta(days=1)

    col1, col2 = st.columns(2)
    start_date_input = col1.date_input('Start Date', day_before)
    end_date_input = col2.date_input('End Date', today)

    # Calculate the difference in days between the start and end dates
    date_diff = (end_date_input - start_date_input).days

    col3, col4 = st.columns(2)
    press = col3.button("Fetch Data")
    real_time = col4.checkbox("Real Time")

    # Check if the difference is greater than 7 days
    if date_diff > 7:
        st.error('The selected date range is more than 7 days. Please select a shorter range.')
    else:

        if 'data' not in st.session_state:
            st.session_state.data = None
        if real_time:
            st.session_state.data = fetch_data(default_start_date.strftime('%Y-%m-%d'), default_end_date.strftime('%Y-%m-%d'))
            start_date_input=default_start_date
            end_date_input=default_end_date
        elif press:
                st.session_state.data = fetch_data(start_date_input.strftime('%Y-%m-%d'), end_date_input.strftime('%Y-%m-%d'))



        if st.session_state.data and "data" in st.session_state.data and "items" in st.session_state.data["data"]:
            start_datetime = datetime.combine(start_date_input, datetime.min.time())  # Convert to datetime with 00:00:00 time
            end_datetime = datetime.combine(end_date_input, datetime.max.time())
            df_met = get_met(start_datetime, end_datetime)

            df = pd.DataFrame(st.session_state.data["data"]["items"])
            df['time'] = pd.to_datetime(df['time'])

            df.set_index('time', inplace=True)

            joined_df = df.join(df_met, how='outer')
            joined_df.reset_index(inplace=True)

            joined_df.rename(columns={'index': 'time'}, inplace=True)

            if 'pm25' in joined_df.columns:
                joined_df['Air Quality Description'] = joined_df['pm25'].apply(get_pm25_description)
            if 't' in joined_df.columns and 'h' in joined_df.columns:
                joined_df['pmv'] = joined_df.apply(
                    lambda row: round(calculate_pmv(row['t'], row['h'], row['met'] if not pd.isna(row['met']) else 1),2), axis=1)

            if not joined_df.empty:
                if 'time' in joined_df.columns and 't' in joined_df.columns:
                    plot_line_chart(joined_df, 'time', 't', 'Indoor Temperature')
                if 'time' in joined_df.columns and 'h' in joined_df.columns:
                    plot_line_chart(joined_df, 'time', 'h', 'Indoor Humidity', width=1150)
                if 'time' in joined_df.columns and 'voc' in joined_df.columns:
                    st.markdown("""
                        # TVOC Analysis
                        Total Volatile Organic Compounds (TVOC) refers to the collective amount of 
                        organic chemicals present in the air. These chemicals, known as VOCs, are 
                        emitted as gases from certain solids or liquids, including a variety of 
                        household and industrial products.

                        Monitoring TVOC is crucial for several reasons:

                        - **Health Implications:** Exposure to high levels of VOCs can cause 
                          immediate health effects including eye, nose and throat irritation, 
                          headaches, loss of coordination, and nausea. Long-term exposure may 
                          also lead to chronic respiratory problems, liver and kidney damage, 
                          and even cancer.
                        - **Indoor Air Quality:** TVOC is a key indicator of indoor air quality. 
                          Effective management and reduction of TVOC levels contribute to better 
                          air quality and a healthier indoor environment.
                        - **Regulatory Compliance:** In many regions, there are guidelines or 
                          regulations governing the permissible levels of VOC emissions in indoor 
                          environments, necessitating regular monitoring and management.

                        The sources of VOCs include building materials, furnishings, cleaning 
                        compounds, office equipment, personal care products, air fresheners, 
                        pesticides, and more. Thus, analyzing TVOC levels is essential for 
                        maintaining a safe and comfortable indoor environment.
                    """)
                    plot_line_chart(joined_df, 'time', 'voc', 'TVOCs', width=1150)
                if 'time' in joined_df.columns and 'pm1' in joined_df.columns:
                    st.markdown("""
                        # Particulate Matter (PM) Analysis
                        Particulate matter (PM) refers to tiny particles or droplets in the air 
                        that can be inhaled into the lungs. PM is usually categorized by size, 
                        with common categories including PM1, PM2.5, and PM10, which refer to 
                        particles with diameters of 1 micrometer, 2.5 micrometers, and 10 micrometers, 
                        respectively.

                        Monitoring PM is essential due to several reasons:

                        - **Health Implications:** Exposure to PM can cause a range of health issues, 
                          including respiratory and cardiovascular problems, as well as adverse 
                          effects on the liver, spleen, and blood. Long-term exposure may also lead 
                          to chronic respiratory diseases, heart disease, lung cancer, and can affect 
                          development in children and the unborn.
                        - **Environmental Impact:** PM can affect visibility, cause damage to vegetation, 
                          and contribute to acid rain.
                        - **Regulatory Compliance:** Many regions have established standards or guidelines 
                          for PM concentrations to ensure air quality and public health.

                        Various sources contribute to PM levels, including combustion from vehicles, 
                        industrial processes, residential heating, and natural sources such as wildfires 
                        and volcanic eruptions. Thus, analyzing PM levels is crucial for understanding 
                        and improving air quality, ensuring a healthier and safer environment.
                    """)

                    plot_line_chart(joined_df, 'time', 'pm1', 'PM1', width=1150)
                if 'time' in joined_df.columns and 'pm25' in joined_df.columns:
                    plot_line_chart(joined_df, 'time', 'pm25', 'PM2.5', width=1150)
                if 'time' in joined_df.columns and 'pm10' in joined_df.columns:
                    plot_line_chart(joined_df, 'time', 'pm10', 'PM10', width=1150)
                if 'time' in joined_df.columns and 'pmv' in joined_df.columns:
                    st.markdown("""
                        # Thermal Comfort Analysis
                        Thermal comfort refers to the condition of mind that expresses satisfaction 
                        with the thermal environment. It is crucial for an individual's well-being 
                        and can impact one's health and productivity. Thermal comfort is achieved 
                        when the body can dissipate an equal amount of heat to the environment, 
                        maintaining a core body temperature within a narrow range around 37°C (98.6°F).

                        Several factors influence thermal comfort, including:

                        - **Air Temperature:** The temperature of the air surrounding the body.
                        - **Radiant Temperature:** The temperature radiated from surrounding surfaces.
                        - **Humidity:** The moisture content in the air.
                        - **Air Velocity:** The speed of air moving across the body.
                        - **Clothing Insulation:** The level of insulation provided by clothing.
                        - **Metabolic Heat:** The heat generated by the body's metabolism.

                        Monitoring and analyzing thermal comfort is essential for creating comfortable 
                        and healthy indoor environments, improving occupants' satisfaction, and 
                        enhancing the efficiency of heating, ventilation, and air conditioning (HVAC) systems.
                    """)
                    plot_line_chart_pmv(joined_df, 'time', 'pmv', 'PMV (Thermal Comfort)', width=1150)

                # Count the frequency of each description
                description_counts = joined_df['Air Quality Description'].value_counts()

                # Plot the frequencies using a bar chart
                fig = px.bar(description_counts, x=description_counts.index, y=description_counts.values, title="Frequency of Air Quality Index", labels={
                    'y': 'Frequency', 'index': 'Description'})

                st.plotly_chart(fig,
                                use_container_width=True)  # This will make Streamlit size the container to the plot

                st.markdown("""
                    # Atmotube Real time Location
                """)

                # Define the latitude and longitude of the location you want to highlight
                first_non_nan_coords = next(((coords['lat'], coords['lon']) for coords in df['coords'][::-1] if
                                             pd.notna(coords) and 'lat' in coords and 'lon' in coords), (None, None))
                lat, lon = first_non_nan_coords
                if first_non_nan_coords:
                    # Create a DataFrame with the location data

                    df_l = pd.DataFrame({'lat': [lat], 'lon': [lon]})

                    # Define the Pydeck map layer
                    layer = pdk.Layer(
                        "ScatterplotLayer",
                        df_l,
                        get_position='[lon, lat]',
                        get_radius=100,  # Radius of the circle in meters
                        get_fill_color=[255, 0, 0],  # Circle color
                    )

                    # Define the map view state
                    view_state = pdk.ViewState(latitude=lat, longitude=lon, zoom=12)

                    # Create the Pydeck chart
                    st.pydeck_chart(pdk.Deck(layers=[layer], initial_view_state=view_state))


                num_pages = max(1, len(joined_df) // PAGE_SIZE + (1 if len(joined_df) % PAGE_SIZE else 0))

                st.title("TwinBAS Data Collection")

                page = st.selectbox("Select page", list(range(1, num_pages + 1)))
                print(joined_df['coords'])
                # Splitting the 'coords' column into 'lat' and 'lon'
                joined_df['lat'] = joined_df['coords'].apply(lambda x: x['lat'] if pd.notna(x) else None)
                joined_df['lon'] = joined_df['coords'].apply(lambda x: x['lon'] if pd.notna(x) else None)

                numerical_cols = joined_df.select_dtypes(include=[np.number]).columns
                joined_df[numerical_cols] = joined_df[numerical_cols].round(2)

                joined_df = joined_df.drop(columns=['coords'])

                start_idx = (page - 1) * PAGE_SIZE
                end_idx = start_idx + PAGE_SIZE
                st.table(joined_df.iloc[start_idx:end_idx])

            else:
                st.warning("No data available for the selected date range.")


if __name__ == '__main__':
    main()
