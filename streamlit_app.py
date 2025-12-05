import streamlit as st
import pandas as pd
import plotly.express as px
from pyathena import connect
import os
from datetime import datetime
from datetime import timedelta
import math

# Set up AWS credentials from Streamlit secrets
os.environ['AWS_ACCESS_KEY_ID'] = st.secrets['AWS_ACCESS_KEY_ID']
os.environ['AWS_SECRET_ACCESS_KEY'] = st.secrets['AWS_SECRET_ACCESS_KEY']
os.environ['AWS_REGION'] = st.secrets['AWS_REGION']

# Page configuration
st.set_page_config(
    page_title="NASA Asteroid Dashboard",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Dark space theme
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Space+Mono:wght@400;700&display=swap');
    
    .main-header {
        font-size: 3rem;
        color: #7b68ee;
        text-align: center;
        margin-bottom: 2rem;
    }
    .stApp {
        background: linear-gradient(180deg, #0d1117 0%, #161b22 50%, #0d1117 100%);
    }
    .stMetric {
        background: linear-gradient(135deg, #1a1f35 0%, #2d2b55 100%);
        padding: 1rem;
        border-radius: 10px;
        border: 1px solid #7b68ee33;
    }
    [data-testid="stMetricLabel"] {
        color: #8b949e !important;
        font-family: 'Space Mono', monospace !important;
        text-transform: uppercase;
        font-size: 0.75em !important;
        letter-spacing: 1px;
    }
    [data-testid="stMetricValue"] {
        color: #c9d1d9 !important;
        font-family: 'Space Mono', monospace !important;
    }
    h1, h2, h3, .stSubheader {
        color: #c9d1d9 !important;
    }
    [data-testid="stSidebar"] {
        background: linear-gradient(180deg, #161b22 0%, #0d1117 100%);
    }
    [data-testid="stSidebar"] .stMarkdown {
        color: #8b949e;
    }
</style>
""", unsafe_allow_html=True)

st.markdown('<h1 class="main-header">NASA Asteroid Dashboard</h1>', unsafe_allow_html=True)
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

# Remove duplicate entries (based on unique ID + date)
df = df.drop_duplicates(subset=["id", "close_approach_date"])

# Sidebar filters
st.sidebar.header("Filters")
hazardous_filter = st.sidebar.selectbox(
    "Asteroid Type",
    ["All", "Potentially Hazardous", "Non-Hazardous"]
)

max_distance = st.sidebar.slider(
    "Maximum Miss Distance (million km)",
    min_value=0.0,
    max_value=100.0,
    value=80.0,
    step=0.5
)

if len(df) > 0:
    # Find true min/max velocities
    velocity_min = float(df['velocity_km_s'].min())
    velocity_max = float(df['velocity_km_s'].max())
    # Clean boundaries to two decimals, fix if they're too close
    slider_min = math.floor(velocity_min * 100) / 100
    slider_max = math.ceil(velocity_max * 100) / 100
    # Guarantee a minimum visible range
    if slider_max - slider_min < 0.01:
        slider_max = round(slider_min + 0.01, 2)
else:
    slider_min, slider_max = 0.0, 100.0

velocity_range = st.sidebar.slider(
    "Velocity Range (km/s)",
    min_value=slider_min,
    max_value=slider_max,
    value=(slider_min, slider_max),
    step=0.01
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
filtered_df = filtered_df[
    (filtered_df['velocity_km_s'] >= velocity_range[0]) &
    (filtered_df['velocity_km_s'] <= velocity_range[1])
]

# Metrics row
col1, col2, col3, col4 = st.columns(4)
with col1:
    st.metric("Total Asteroids", len(filtered_df))
with col2:
    hazardous_count = len(filtered_df[filtered_df['is_potentially_hazardous'] == True])
    st.metric("Potentially Hazardous", hazardous_count)
with col3:
    closest = filtered_df['miss_distance_km'].min() if len(filtered_df) > 0 else 0
    st.metric("Closest Approach", f"{closest/1_000_000:.2f}M km" if closest > 0 else "N/A")
with col4:
    avg_velocity = filtered_df['velocity_km_s'].mean() if len(filtered_df) > 0 else 0
    st.metric("Avg Velocity", f"{avg_velocity:.1f} km/s")

st.markdown("---")

# Visualizations
col1, col2 = st.columns([2, 1])

with col1:
    st.subheader("Daily Asteroid Approaches")
    if len(filtered_df) > 0:
        # Aggregate by date
        daily_counts = (
            filtered_df.groupby('close_approach_date')
            .agg(
                count=('id', 'size'),
                hazardous=('is_potentially_hazardous', 'sum'),
                avg_distance=('miss_distance_km', 'mean')
            )
            .reset_index()
        )
        daily_counts['avg_distance_mkm'] = daily_counts['avg_distance'] / 1_000_000
        
        fig = px.bar(
            daily_counts,
            x='close_approach_date',
            y='count',
            color='hazardous',
            color_continuous_scale=['#4a5568', '#9f7aea', '#e53e3e'],
            hover_data={'avg_distance_mkm': ':.2f'},
            labels={
                'close_approach_date': 'Date',
                'count': 'Number of Asteroids',
                'hazardous': 'Hazardous Count',
                'avg_distance_mkm': 'Avg Distance (M km)'
            }
        )
        fig.update_layout(
            plot_bgcolor='rgba(13, 17, 23, 0.8)',
            paper_bgcolor='rgba(0,0,0,0)',
            font_color='#c9d1d9',
            xaxis=dict(gridcolor='#30363d'),
            yaxis=dict(gridcolor='#30363d')
        )
        st.plotly_chart(fig, use_container_width=True)
        st.caption("Number of near-Earth objects passing by each day, colored by hazard level.")

with col2:
    st.subheader("Risk Assessment")
    if len(filtered_df) > 0:
        hazard_labels = {True: "Potentially Hazardous", False: "Safe"}
        hazard_vals = filtered_df['is_potentially_hazardous'].map(hazard_labels).value_counts()
        fig = px.pie(
            values=hazard_vals.values,
            names=hazard_vals.index,
            color=hazard_vals.index,
            color_discrete_map={
                'Safe': '#48bb78',
                'Potentially Hazardous': '#fc8181'
            },
            hole=0.4
        )
        fig.update_layout(
            plot_bgcolor='rgba(0,0,0,0)',
            paper_bgcolor='rgba(0,0,0,0)',
            font_color='#c9d1d9',
            legend=dict(font=dict(color='#c9d1d9'))
        )
        fig.update_traces(textfont_color='#c9d1d9')
        st.plotly_chart(fig, use_container_width=True)
        st.caption("Proportion of potentially hazardous asteroids in the current selection.")

st.markdown("---")

# Scatter plot: Velocity vs Distance (size = diameter)
st.subheader("Asteroid Threat Profile")
if len(filtered_df) > 0:
    scatter_df = filtered_df.copy()
    scatter_df['miss_distance_mkm'] = scatter_df['miss_distance_km'] / 1_000_000
    
    fig = px.scatter(
        scatter_df,
        x='miss_distance_mkm',
        y='velocity_km_s',
        size='max_diameter_km',
        color='is_potentially_hazardous',
        color_discrete_map={False: '#48bb78', True: '#fc8181'},
        hover_name='name',
        hover_data={
            'miss_distance_mkm': ':.2f',
            'velocity_km_s': ':.2f',
            'max_diameter_km': ':.3f',
            'is_potentially_hazardous': False
        },
        labels={
            'miss_distance_mkm': 'Miss Distance (Million km)',
            'velocity_km_s': 'Velocity (km/s)',
            'max_diameter_km': 'Diameter (km)',
            'is_potentially_hazardous': 'Hazardous'
        }
    )
    # Space-like purple-blue background
    fig.update_layout(
        plot_bgcolor='#1a1033',
        paper_bgcolor='rgba(0,0,0,0)',
        font_color='#c9d1d9',
        xaxis=dict(
            gridcolor='#2d2455',
            title_font=dict(color='#c9d1d9'),
            zerolinecolor='#2d2455'
        ),
        yaxis=dict(
            gridcolor='#2d2455',
            title_font=dict(color='#c9d1d9'),
            zerolinecolor='#2d2455'
        ),
        legend=dict(font=dict(color='#c9d1d9'))
    )
    fig.update_traces(marker=dict(line=dict(width=1, color='#2d2455')))
    st.plotly_chart(fig, use_container_width=True)
    st.caption("Each point is an asteroid. Size represents diameter, position shows velocity and proximity. Top-left = higher threat.")

st.markdown("---")

# Top N largest asteroids bar chart
st.subheader(f"Top {top_n} Largest Asteroids")
if len(filtered_df) > 0:
    topn_df = (
        filtered_df.sort_values("max_diameter_km", ascending=False)
        .head(top_n)
        .copy()
    )
    # Add velocity for extra context
    topn_df['velocity_display'] = topn_df['velocity_km_s'].round(2)
    
    fig = px.bar(
        topn_df[::-1],  # reverse for largest on top
        x="max_diameter_km",
        y="name",
        orientation="h",
        color="is_potentially_hazardous",
        color_discrete_map={False: '#48bb78', True: '#fc8181'},
        hover_data=['velocity_display', 'miss_distance_km'],
        labels={
            "max_diameter_km": "Max Diameter (km)",
            "name": "Asteroid Name",
            "is_potentially_hazardous": "Hazardous",
            "velocity_display": "Velocity (km/s)",
            "miss_distance_km": "Miss Distance (km)"
        }
    )
    fig.update_layout(
        yaxis=dict(tickfont=dict(size=11, color='#c9d1d9')),
        plot_bgcolor='rgba(13, 17, 23, 0.8)',
        paper_bgcolor='rgba(0,0,0,0)',
        font_color='#c9d1d9',
        xaxis=dict(gridcolor='#30363d'),
        legend=dict(font=dict(color='#c9d1d9'))
    )
    st.plotly_chart(fig, use_container_width=True)
    st.caption("Ranked by maximum estimated diameter. Larger asteroids pose greater potential impact risk.")

# Data table
st.subheader("Detailed Asteroid Data")
if len(filtered_df) > 0:
    display_df = filtered_df.sort_values('miss_distance_km').copy()
    display_df['Miss Distance (M km)'] = (display_df['miss_distance_km'] / 1_000_000).round(2)
    display_df['Potentially Hazardous'] = display_df['is_potentially_hazardous'].map({True: 'Yes', False: 'No'})
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
    st.caption("Full dataset sorted by closest approach distance. Click column headers to sort.")

# Footer with data refresh time
@st.cache_data(ttl=3600)
def get_data_refresh_time():
    return datetime.now()

st.markdown("---")
st.markdown("**Data Source:** NASA Near Earth Object Web Service | **Built with:** Streamlit + AWS")
st.markdown("**Last Data Refresh:** " + get_data_refresh_time().strftime("%Y-%m-%d %H:%M:%S"))
st.markdown("---")
st.markdown("© 2025 Javier Fernández. All rights reserved.")
