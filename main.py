import streamlit as st
import pandas as pd
import plotly.express as px

# Sample data
data = {
    'Date': ['2023-01-01', '2023-01-02', '2023-01-03', '2023-01-04'],
    'Value': [10, 20, 30, 40]
}
df = pd.DataFrame(data)

# Streamlit app
st.title('Data Visualization with Streamlit')

# Display data in a table
st.write(df)

# Display data in a line chart
fig = px.line(df, x='Date', y='Value', title='Line Chart Visualization')
st.plotly_chart(fig)

# Display data in a bar chart
fig2 = px.bar(df, x='Date', y='Value', title='Bar Chart Visualization')
st.plotly_chart(fig2)

if __name__ == '__main__':
    st.write("This is a basic Streamlit app for data visualization.")
