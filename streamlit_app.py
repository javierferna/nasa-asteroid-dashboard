import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import numpy as np
from datetime import datetime, timedelta

# Page configuration
st.set_page_config(
    page_title="NASA Asteroid Dashboard",
    page_icon="🚀",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS
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

# Title
st.markdown('<h1 class="main-header">🚀 NASA Asteroid Dashboard</h1>', unsafe_allow_html=True)
st.markdown("---")

@st.cache_data
def load_demo_data():
    """Load demonstration asteroid data"""
    dates = pd.date_range(start='2025-07-15', end='2025-07-21', freq='D')
    
    asteroids = []
    for date in dates:
        num_asteroids = np.random.randint(3, 15)
        for i in range(num_asteroids):
            asteroids.append({
                'close_approach_date': date.strftime('%Y-%m-%d'),
                'name': f'Asteroid_{date.strftime("%Y%m%d")}_{i+1}',
                'miss_distance_km': np.random.uniform(50000, 50000000),
                'velocity_km_s': np.random.uniform(5, 25),
                'is_potentially_hazardous': np.random.choice([True, False], p=[0.15, 0.85]),
                'diameter_min_km': np.random.uniform(0.01, 2.0),
                'diameter_max_km': np.random.uniform(0.02, 4.0)
            })
    
    return pd.DataFrame(asteroids)

# Load data
df = load_demo_data()

# Sidebar filters
st.sidebar.header("🔧 Filters")
hazardous_filter = st.sidebar.selectbox(
    "Asteroid Type",
    ["All", "Potentially Hazardous", "Non-Hazardous"]
)

max_distance = st.sidebar.slider(
    "Maximum Miss Distance (million km)",
    min_value=0.05,
    max_value=50.0,
    value=10.0,
    step=0.5
)

# Apply filters
filtered_df = df.copy()
if hazardous_filter == "Potentially Hazardous":
    filtered_df = filtered_df[filtered_df['is_potentially_hazardous'] == True]
elif hazardous_filter == "Non-Hazardous":
    filtered_df = filtered_df[filtered_df['is_potentially_hazardous'] == False]

filtered_df = filtered_df[filtered_df['miss_distance_km'] <= max_distance * 1000000]

# Metrics
col1, col2, col3, col4 = st.columns(4)

with col1:
    st.metric("🌍 Total Asteroids", len(filtered_df))

with col2:
    hazardous_count = len(filtered_df[filtered_df['is_potentially_hazardous'] == True])
    st.metric("⚠️ Potentially Hazardous", hazardous_count)

with col3:
    closest = filtered_df['miss_distance_km'].min() if len(filtered_df) > 0 else 0
    st.metric("🎯 Closest Approach", f"{closest/1000000:.2f}M km" if closest > 0 else "N/A")

with col4:
    avg_velocity = filtered_df['velocity_km_s'].mean() if len(filtered_df) > 0 else 0
    st.metric("💨 Avg Velocity", f"{avg_velocity:.1f} km/s")

st.markdown("---")

# Visualizations
col1, col2 = st.columns([2, 1])

with col1:
    st.subheader("📊 Daily Asteroid Approaches")
    if len(filtered_df) > 0:
        daily_counts = filtered_df.groupby('close_approach_date').size().reset_index(name='count')
        fig = px.line(daily_counts, x='close_approach_date', y='count', 
                     title="Asteroid Approaches by Date")
        st.plotly_chart(fig, use_container_width=True)

with col2:
    st.subheader("🎯 Risk Assessment")
    if len(filtered_df) > 0:
        hazard_counts = filtered_df['is_potentially_hazardous'].value_counts()
        fig = px.pie(values=hazard_counts.values, 
                    names=['Safe', 'Potentially Hazardous'],
                    color_discrete_map={'Safe': '#2ecc71', 'Potentially Hazardous': '#e74c3c'})
        st.plotly_chart(fig, use_container_width=True)

# Data table
st.subheader("📋 Detailed Asteroid Data")
if len(filtered_df) > 0:
    display_df = filtered_df.sort_values('miss_distance_km').copy()
    display_df['Miss Distance (M km)'] = (display_df['miss_distance_km'] / 1000000).round(2)
    display_df['Potentially Hazardous'] = display_df['is_potentially_hazardous'].map({True: '⚠️ Yes', False: '✅ No'})
    
    st.dataframe(
        display_df[['name', 'close_approach_date', 'Miss Distance (M km)', 
                   'velocity_km_s', 'Potentially Hazardous']].rename(columns={
            'name': 'Asteroid Name',
            'close_approach_date': 'Approach Date',
            'velocity_km_s': 'Velocity (km/s)'
        }),
        use_container_width=True
    )

st.markdown("---")
st.markdown("**Data Source:** NASA Near Earth Object Web Service | **Built with:** Streamlit + AWS")
st.markdown("**Last Updated:** " + datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
