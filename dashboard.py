import streamlit as st
import pandas as pd
import json
import os
import glob
from datetime import datetime
import plotly.graph_objects as go
import plotly.express as px

# ==================== PAGE CONFIG ====================
st.set_page_config(
    page_title="🚀 AI-Ready Clarity Dashboard",
    page_icon="🤖",
    layout="wide"
)

# ==================== DATA ENGINE (LAST KNOWN STATE) ====================
def load_all_clarity_data():
    """
    Skanuje pliki JSON i buduje stan 'Last Known State' dla każdego kraju.
    """
    all_files = glob.glob("clarity_*.json")
    global_state = {}
    
    for file in sorted(all_files): # Sortowanie zapewnia, że nowsze nadpiszą starsze
        try:
            with open(file, 'r') as f:
                day_data = json.load(f)
            for country, data in day_data.items():
                if country not in global_state:
                    global_state[country] = data
                else:
                    curr_ts = datetime.fromisoformat(global_state[country]['timestamp'])
                    new_ts = datetime.fromisoformat(data['timestamp'])
                    if new_ts > curr_ts:
                        global_state[country] = data
        except Exception as e:
            st.error(f"Błąd ładowania {file}: {e}")
            
    return global_state

def get_metric_info(country_data, metric_name):
    if not country_data.get('webshop'): return None
    for m in country_data['webshop']:
        if m['metricName'] == metric_name:
            return m['information'][0] if m['information'] else None
    return None

# ==================== ADVANCED METRICS (INTENSITY & RISK) ====================
def calculate_frustration_velocity(country_data):
    """Mierzy zagęszczenie kliknięć w sesjach z błędami (Gęstość frustracji)"""
    dead = get_metric_info(country_data, 'DeadClickCount')
    rage = get_metric_info(country_data, 'RageClickCount')
    
    def calc_v(info):
        if not info: return 0
        total_clicks = float(info.get('subTotal', 0))
        sessions = float(info.get('sessionsCount', 1))
        perc = float(info.get('sessionsWithMetricPercentage', 0)) / 100
        affected = sessions * perc
        return total_clicks / affected if affected > 0 else 0

    return round((calc_v(dead) + calc_v(rage)) / 2, 2)

def calculate_silent_killer_score(country_data):
    """Ryzyko porzucenia koszyka: Błędy * Gęstość stron transakcyjnych"""
    pages = next((m['information'] for m in country_data['webshop'] if m['metricName'] == 'PopularPages'), [])
    tx_keywords = ['cart', 'checkout', 'pay', 'basket', 'login', 'wslogin', 'validate']
    
    total_v = sum(int(p.get('visitsCount', 0)) for p in pages)
    if total_v == 0: return 0
    
    tx_v = sum(int(p.get('visitsCount', 0)) for p in pages if any(kw in p['url'].lower() for kw in tx_keywords))
    tx_density = tx_v / total_v
    
    dead_p = float(get_metric_info(country_data, 'DeadClickCount').get('sessionsWithMetricPercentage', 0))
    err_p = float(get_metric_info(country_data, 'ErrorClickCount').get('sessionsWithMetricPercentage', 0) if get_metric_info(country_data, 'ErrorClickCount') else 0)
    
    # Formuła: Błędy bazowe podbite przez wagę stron transakcyjnych
    score = (dead_p * 0.7 + err_p * 0.3) * (1 + tx_density * 3)
    return round(min(score, 100), 2)

# ==================== MAIN DASHBOARD ====================
st.title("🤖 Clarity AI-Agent Command Center")
st.markdown("---")

data = load_all_clarity_data()

if data:
    stats = []
    for country, c_data in data.items():
        v = calculate_frustration_velocity(c_data)
        sk = calculate_silent_killer_score(c_data)
        sessions = int(get_metric_info(c_data, 'DeadClickCount').get('sessionsCount', 0))
        
        stats.append({
            'Country': country,
            'Frustration Velocity': v,
            'Silent Killer Score': sk,
            'Sessions': sessions,
            'Last Update': c_data['timestamp'][:10]
        })
    
    df = pd.DataFrame(stats)

    # --- KPI ROW ---
    c1, c2, c3 = st.columns(3)
    c1.metric("🌍 Countries Monitored", len(df))
    c2.metric("🔥 Avg. Silent Killer", f"{df['Silent Killer Score'].mean():.1f}")
    c3.metric("📅 Oldest Record", df['Last Update'].min())

    # --- VISUALIZATION: IMPACT VS SCALE (BUBBLE CHART) ---
    st.subheader("🎯 Critical Impact Matrix (Scale vs Intensity)")
    fig_bubble = px.scatter(
        df, x="Sessions", y="Silent Killer Score",
        size="Frustration Velocity", color="Silent Killer Score",
        hover_name="Country", text="Country",
        color_continuous_scale="RdYlGn_r",
        title="Oś Y: Ryzyko przychodów | Wielkość: Gęstość frustracji"
    )
    st.plotly_chart(fig_bubble, use_container_width=True)

    # --- THE AGENT'S TARGET LIST ---
    st.subheader("📋 Top 5 Sessions for AI Agent Analysis")
    priority_df = df.sort_values('Silent Killer Score', ascending=False).head(5)
    
    cols = st.columns(5)
    for i, (idx, row) in enumerate(priority_df.iterrows()):
        with cols[i]:
            st.error(f"**{row['Country']}**")
            st.write(f"Risk: {row['Silent Killer Score']}")
            st.write(f"Velocity: {row['Frustration Velocity']}")
            if st.button(f"Analyze {row['Country']}", key=row['Country']):
                st.session_state['target'] = row['Country']

    # --- RADAR CHART (NORMALIZED) ---
    st.subheader("📊 Comparative Health Radar")
    # Normalizacja do skali 100 dla radaru
    radar_df = df.copy()
    for col in ['Frustration Velocity', 'Silent Killer Score', 'Sessions']:
        radar_df[col] = (radar_df[col] / radar_df[col].max()) * 100
        
    fig_radar = go.Figure()
    for country in df['Country'].unique()[:5]: # Top 5 dla czytelności
        c_row = radar_df[radar_df['Country'] == country].iloc[0]
        fig_radar.add_trace(go.Scatterpolar(
            r=[c_row['Frustration Velocity'], c_row['Silent Killer Score'], c_row['Sessions']],
            theta=['Frustration Velocity', 'Silent Killer Score', 'Scale (Sessions)'],
            fill='toself', name=country
        ))
    st.plotly_chart(fig_radar, use_container_width=True)

else:
    st.warning("No clarity_*.json files found in the directory.")
