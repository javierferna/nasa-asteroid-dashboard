import streamlit as st
import pandas as pd
import plotly.express as px
from pyathena import connect
import os
from datetime import datetime

# Set up AWS credentials from Streamlit secrets
os.environ['AWS_ACCESS_KEY_ID'] = st.secrets['AWS_ACCESS_KEY_ID']
os.environ['AWS_SECRET_ACCESS_KEY'] = st.secrets['AWS_SECRET_ACCESS_KEY']
os.environ['AWS_REGION'] = st.secrets['AWS_REGION']

# Page configuration
st.set_page_config(
    page_title="NASA Asteroid Dashboard",
    page_icon="🚀",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
<style>
    .main-header {
        font-size: 3rem;
        color: #1f77b4;
        text-align: center;
        margin-bottom: 2rem;
    }
    .metric-card {
        background-color: #f0f2f6;
        padding: 1rem;
        border-radius: 10px;
        margin: 0.5rem 0;
    }
</style>
""", unsafe_allow_html=True)

st.markdown('<h1 class="main-header">🚀 NASA Asteroid Dashboard</h1>', unsafe_allow_html=True)
st.markdown("---")

@st.cache_data(ttl=3600)
def load_asteroid_data():
    conn = connect(
        s3_staging_dir="s3://nasa-asteroid-data-1/athena-results/",
        region_name="us-east-1"
    )
    query = """
        SELECT
            id,
            name,
            close_approach_date,
            miss_distance_km,
            velocity_km_s,
            is_potentially_hazardous,
            min_diameter_km,
            max_diameter_km
        FROM nasa_neo_database.asteroids
        WHERE close_approach_date >= date_format(current_date - interval '7' day, '%Y-%m-%d')
    """
    return pd.read_sql(query, conn)

df = load_asteroid_data()

# Sidebar filters
st.sidebar.header("🔧 Filters")
hazardous_filter = st.sidebar.selectbox(
    "Asteroid Type",
    ["All", "Potentially Hazardous", "Non-Hazardous"]
)

max_distance = st.sidebar.slider(
    "Maximum Miss Distance (million km)",
    min_value=0.0,
    max_value=100.0,
    value=10.0,
    step=0.5
)

# User input: Select top N largest asteroids for bar chart
top_n = st.sidebar.number_input(
    "Show Top N Largest Asteroids",
    min_value=1, max_value=50, value=10, step=1
)

# Apply filters
filtered_df = df.copy()
if hazardous_filter == "Potentially Hazardous":
    filtered_df = filtered_df[filtered_df['is_potentially_hazardous'] == True]
elif hazardous_filter == "Non-Hazardous":
    filtered_df = filtered_df[filtered_df['is_potentially_hazardous'] == False]

filtered_df = filtered_df[filtered_df['miss_distance_km'] <= max_distance * 1_000_000]

# Metrics
col1, col2, col3, col4 = st.columns(4)
with col1:
    st.metric("🌍 Total Asteroids", len(filtered_df))
with col2:
    hazardous_count = len(filtered_df[filtered_df['is_potentially_hazardous'] == True])
    st.metric("⚠️ Potentially Hazardous", hazardous_count)
with col3:
    closest = filtered_df['miss_distance_km'].min() if len(filtered_df) > 0 else 0
    st.metric("🎯 Closest Approach", f"{closest/1_000_000:.2f}M km" if closest > 0 else "N/A")
with col4:
    avg_velocity = filtered_df['velocity_km_s'].mean() if len(filtered_df) > 0 else 0
    st.metric("💨 Avg Velocity", f"{avg_velocity:.1f} km/s")

st.markdown("---")

# Visualizations
col1, col2 = st.columns([2, 1])

with col1:
    st.subheader("📊 Daily Asteroid Approaches")
    if len(filtered_df) > 0:
        daily_counts = (
            filtered_df.groupby('close_approach_date')
            .size()
            .reset_index(name='count')
        )
        fig = px.line(
            daily_counts,
            x='close_approach_date',
            y='count',
            title="Asteroid Approaches by Date"
        )
        st.plotly_chart(fig, use_container_width=True)

with col2:
    st.subheader("🎯 Risk Assessment")
    if len(filtered_df) > 0:
        hazard_labels = {True: "Potentially Hazardous", False: "Safe"}
        hazard_vals = filtered_df['is_potentially_hazardous'].map(hazard_labels).value_counts()
        fig = px.pie(
            values=hazard_vals.values,
            names=hazard_vals.index,
            color=hazard_vals.index,
            color_discrete_map={
                'Safe': '#2ecc71',
                'Potentially Hazardous': '#e74c3c'
            }
        )
        st.plotly_chart(fig, use_container_width=True)

st.markdown("---")

# Top N largest asteroids bar chart
st.subheader(f"🪨 Top {top_n} Largest Asteroids (max diameter)")
if len(filtered_df) > 0:
    topn_df = (
        filtered_df.sort_values("max_diameter_km", ascending=False)
        .head(top_n)
        .copy()
    )
    fig = px.bar(
        topn_df[::-1],  # reverse for largest on top
        x="max_diameter_km",
        y="name",
        orientation="h",
        color="is_potentially_hazardous",
        color_discrete_map={False: '#2ecc71', True: '#e74c3c'},
        labels={
            "max_diameter_km": "Max Diameter (km)",
            "name": "Asteroid Name",
            "is_potentially_hazardous": "Hazardous"
        },
        title=f"Top {top_n} Largest Asteroids"
    )
    fig.update_layout(yaxis=dict(tickfont=dict(size=11)))
    st.plotly_chart(fig, use_container_width=True)

# Data table
st.subheader("📋 Detailed Asteroid Data")
if len(filtered_df) > 0:
    display_df = filtered_df.sort_values('miss_distance_km').copy()
    display_df['Miss Distance (M km)'] = (display_df['miss_distance_km'] / 1_000_000).round(2)
    display_df['Potentially Hazardous'] = display_df['is_potentially_hazardous'].map({True: '⚠️ Yes', False: '✅ No'})
    st.dataframe(
        display_df[['name', 'close_approach_date', 'Miss Distance (M km)',
                    'velocity_km_s', 'Potentially Hazardous', 'min_diameter_km', 'max_diameter_km']].rename(columns={
            'name': 'Asteroid Name',
            'close_approach_date': 'Approach Date',
            'velocity_km_s': 'Velocity (km/s)',
            'min_diameter_km': 'Min Diameter (km)',
            'max_diameter_km': 'Max Diameter (km)'
        }),
        use_container_width=True
    )

st.markdown("---")
st.markdown("**Data Source:** NASA Near Earth Object Web Service | **Built with:** Streamlit + AWS")
st.markdown("**Last Updated:** " + datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
st.markdown("---")
st.markdown("© 2025 Javier Fernández. All rights reserved.")
