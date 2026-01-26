import streamlit as st
import pandas as pd
import json
import requests
from datetime import datetime, timedelta
import plotly.graph_objects as go
import plotly.express as px
from pathlib import Path

# ==================== PAGE CONFIG ====================
st.set_page_config(
    page_title="🚀 Clarity Analytics Dashboard",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ==================== CUSTOM STYLING ====================
st.markdown("""
    <style>
        .main-header {
            text-align: center;
            color: #1f77b4;
            margin-bottom: 30px;
        }
        .metric-card {
            background-color: #f0f2f6;
            padding: 20px;
            border-radius: 10px;
            text-align: center;
        }
        .metric-value {
            font-size: 32px;
            font-weight: bold;
            color: #1f77b4;
        }
        .metric-label {
            font-size: 14px;
            color: #666;
            margin-top: 10px;
        }
    </style>
""", unsafe_allow_html=True)

# ==================== DATA LOADING ====================
@st.cache_data(ttl=3600)  # Cache for 1 hour
def load_clarity_data():
    """Load latest clarity data from GitHub"""
    try:
        # Get list of files from GitHub
        repo_raw = "https://raw.githubusercontent.com/jarmoe13/clarity-harvester/main"
        
        # Try to load the latest JSON file
        today = datetime.now().strftime("%Y-%m-%d")
        url = f"{repo_raw}/data/clarity_{today}.json"
        
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            data = response.json()
            st.session_state['data_date'] = today
            return data
        else:
            # Try yesterday if today doesn't exist
            yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
            url = f"{repo_raw}/data/clarity_{yesterday}.json"
            response = requests.get(url, timeout=5)
            if response.status_code == 200:
                data = response.json()
                st.session_state['data_date'] = yesterday
                return data
            else:
                st.error("❌ Could not load data from GitHub")
                return None
    except Exception as e:
        st.error(f"❌ Error loading data: {str(e)}")
        return None

@st.cache_data(ttl=3600)
def load_history_data():
    """Load history CSV from GitHub"""
    try:
        repo_raw = "https://raw.githubusercontent.com/jarmoe13/clarity-harvester/main"
        url = f"{repo_raw}/data/history.csv"
        
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            df = pd.read_csv(StringIO(response.text))
            return df
        else:
            return None
    except:
        return None

# ==================== HELPER FUNCTIONS ====================
def get_metric_value(country_data, metric_name, info_key):
    """Extract metric value from country data"""
    if not country_data.get('webshop'):
        return None
    
    for metric in country_data['webshop']:
        if metric.get('metricName') == metric_name:
            info = metric.get('information', [])
            if info and len(info) > 0:
                return info[0].get(info_key)
    return None

def get_top_items(country_data, metric_name, limit=5):
    """Get top items from a metric"""
    if not country_data.get('webshop'):
        return []
    
    for metric in country_data['webshop']:
        if metric.get('metricName') == metric_name:
            info = metric.get('information', [])
            return sorted(info, key=lambda x: int(x.get('sessionsCount', 0)), reverse=True)[:limit]
    return []

# ==================== MAIN APP ====================
st.markdown("<h1 class='main-header'>🚀 Clarity Analytics Dashboard</h1>", unsafe_allow_html=True)

# Load data
with st.spinner("📊 Loading data..."):
    clarity_data = load_clarity_data()

if clarity_data:
    # ==================== HEADER INFO ====================
    col1, col2, col3 = st.columns(3)
    
    with col1:
        countries_count = len([c for c in clarity_data.keys() if clarity_data[c].get('webshop')])
        st.metric("📍 Countries", countries_count)
    
    with col2:
        data_date = st.session_state.get('data_date', 'Unknown')
        st.metric("📅 Data Date", data_date)
    
    with col3:
        last_update = datetime.now().strftime("%H:%M UTC")
        st.metric("🔄 Last Update", last_update)
    
    st.divider()
    
    # ==================== COUNTRY SELECTOR ====================
    countries = [c for c in clarity_data.keys() if clarity_data[c].get('webshop')]
    selected_country = st.selectbox("🌍 Select Country:", countries)
    
    if selected_country:
        country_data = clarity_data[selected_country]
        
        # ==================== KEY METRICS ====================
        st.subheader(f"📊 Key Metrics - {selected_country}")
        
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            traffic = get_metric_value(country_data, 'Traffic', 'totalSessionCount')
            st.metric("👥 Total Sessions", traffic if traffic else "N/A")
        
        with col2:
            scroll_depth = get_metric_value(country_data, 'ScrollDepth', 'averageScrollDepth')
            st.metric("📜 Avg Scroll Depth", f"{scroll_depth}%" if scroll_depth else "N/A")
        
        with col3:
            dead_clicks = get_metric_value(country_data, 'DeadClickCount', 'sessionsWithMetricPercentage')
            st.metric("🔴 Dead Clicks %", f"{dead_clicks}%" if dead_clicks else "N/A")
        
        with col4:
            rage_clicks = get_metric_value(country_data, 'RageClickCount', 'sessionsWithMetricPercentage')
            st.metric("😡 Rage Clicks %", f"{rage_clicks}%" if rage_clicks else "N/A")
        
        st.divider()
        
        # ==================== BROWSER DISTRIBUTION ====================
        st.subheader("🌐 Browser Distribution")
        
        browsers = get_top_items(country_data, 'Browser', limit=10)
        if browsers:
            browser_df = pd.DataFrame([
                {
                    'Browser': b.get('name', 'Unknown'),
                    'Sessions': int(b.get('sessionsCount', 0))
                }
                for b in browsers
            ])
            
            col1, col2 = st.columns(2)
            
            with col1:
                fig_pie = px.pie(
                    browser_df,
                    values='Sessions',
                    names='Browser',
                    title="Browser Share"
                )
                st.plotly_chart(fig_pie, use_container_width=True)
            
            with col2:
                fig_bar = px.bar(
                    browser_df,
                    x='Sessions',
                    y='Browser',
                    orientation='h',
                    title="Browser Sessions"
                )
                st.plotly_chart(fig_bar, use_container_width=True)
        
        st.divider()
        
        # ==================== DEVICE & OS ====================
        st.subheader("📱 Device & OS Distribution")
        
        col1, col2 = st.columns(2)
        
        with col1:
            devices = get_top_items(country_data, 'Device', limit=5)
            if devices:
                device_df = pd.DataFrame([
                    {
                        'Device': d.get('name', 'Unknown'),
                        'Sessions': int(d.get('sessionsCount', 0))
                    }
                    for d in devices
                ])
                
                fig = px.pie(device_df, values='Sessions', names='Device', title="Device Distribution")
                st.plotly_chart(fig, use_container_width=True)
        
        with col2:
            os_data = get_top_items(country_data, 'OS', limit=5)
            if os_data:
                os_df = pd.DataFrame([
                    {
                        'OS': o.get('name', 'Unknown'),
                        'Sessions': int(o.get('sessionsCount', 0))
                    }
                    for o in os_data
                ])
                
                fig = px.pie(os_df, values='Sessions', names='OS', title="OS Distribution")
                st.plotly_chart(fig, use_container_width=True)
        
        st.divider()
        
        # ==================== TOP PAGES ====================
        st.subheader("🏆 Top Pages")
        
        pages = get_top_items(country_data, 'PopularPages', limit=10)
        if pages:
            page_df = pd.DataFrame([
                {
                    'Page': p.get('url', 'Unknown')[:60] + '...',
                    'Full URL': p.get('url', 'Unknown'),
                    'Visits': int(p.get('visitsCount', 0))
                }
                for p in pages
            ])
            
            fig = px.bar(
                page_df,
                x='Visits',
                y='Page',
                orientation='h',
                title="Top 10 Pages",
                hover_data=['Full URL']
            )
            st.plotly_chart(fig, use_container_width=True)
        
        st.divider()
        
        # ==================== USER BEHAVIOR ====================
        st.subheader("🖱️ User Behavior Metrics")
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            quickback = get_metric_value(country_data, 'QuickbackClick', 'sessionsWithMetricPercentage')
            st.metric("⚡ Quickback %", f"{quickback}%" if quickback else "N/A")
        
        with col2:
            script_errors = get_metric_value(country_data, 'ScriptErrorCount', 'sessionsWithMetricPercentage')
            st.metric("⚠️ Script Errors %", f"{script_errors}%" if script_errors else "N/A")
        
        with col3:
            error_clicks = get_metric_value(country_data, 'ErrorClickCount', 'sessionsWithMetricPercentage')
            st.metric("❌ Error Clicks %", f"{error_clicks}%" if error_clicks else "N/A")
        
        st.divider()
        
        # ==================== RAW DATA ====================
        with st.expander("📋 View Raw Data"):
            st.json(country_data)

else:
    st.error("❌ Failed to load data. Please check back later.")

# ==================== FOOTER ====================
st.divider()
col1, col2, col3 = st.columns(3)

with col1:
    st.caption("🚀 Powered by Clarity API")

with col2:
    st.caption("📊 Dashboard by Streamlit")

with col3:
    st.caption("🔄 Auto-updates daily at 05:00 UTC")
