import streamlit as st
import pandas as pd
import json
import os
import glob
import numpy as np
from datetime import datetime
import plotly.graph_objects as go
import plotly.express as px

# ==================== PAGE CONFIG ====================
st.set_page_config(
    page_title="Executive UX Command Center",
    page_icon="🛡️",
    layout="wide"
)

# ==================== DATA ENGINE ====================
def load_all_clarity_data():
    data_path = os.path.join("data", "clarity_*.json")
    all_files = glob.glob(data_path)
    if not all_files:
        all_files = glob.glob("clarity_*.json")
        
    global_state = {}
    for file in sorted(all_files):
        try:
            with open(file, 'r', encoding='utf-8') as f:
                day_data = json.load(f)
            for country, data in day_data.items():
                # Handling Z-suffix in timestamps for ISO compatibility
                ts_str = data['timestamp'].replace('Z', '')
                new_ts = datetime.fromisoformat(ts_str)
                if country not in global_state:
                    global_state[country] = data
                else:
                    curr_ts = datetime.fromisoformat(global_state[country]['timestamp'].replace('Z', ''))
                    if new_ts > curr_ts:
                        global_state[country] = data
        except Exception:
            continue
    return global_state

def get_metric(country_data, name):
    if not country_data.get('webshop'): return {}
    for m in country_data['webshop']:
        if m['metricName'] == name:
            return m['information'][0] if m['information'] else {}
    return {}

# ==================== CALCULATIONS ====================
def get_advanced_stats(data):
    rows = []
    for country, c_data in data.items():
        # Core Metrics
        dead = get_metric(c_data, 'DeadClickCount')
        rage = get_metric(c_data, 'RageClickCount')
        error = get_metric(c_data, 'ErrorClickCount')
        scroll = get_metric(c_data, 'ScrollDepth')
        js_err = get_metric(c_data, 'ScriptErrorCount')
        
        sessions = int(dead.get('sessionsCount', 0))
        if sessions == 0: continue
        
        # 1. Friction Score (Normalized intensity)
        dead_p = float(dead.get('sessionsWithMetricPercentage', 0))
        rage_p = float(rage.get('sessionsWithMetricPercentage', 0))
        friction = (dead_p * 0.6) + (rage_p * 0.4)
        
        # 2. Tech Debt (Errors vs Views)
        js_p = float(js_err.get('sessionsWithMetricPercentage', 0))
        err_p = float(error.get('sessionsWithMetricPercentage', 0))
        tech_debt = (js_p * 0.7) + (err_p * 0.3)
        
        # 3. Ghost Reading (Scroll vs Clicks)
        avg_scroll = float(scroll.get('averageScrollDepth', 0))
        # Logic: High scroll + Low Dead Clicks = Good content/Low interaction
        ghost_index = (avg_scroll * (100 - dead_p)) / 100 
        
        # 4. Conversion Risk (Transactional weighting)
        pages = next((m['information'] for m in c_data['webshop'] if m['metricName'] == 'PopularPages'), [])
        tx_v = sum(int(p.get('visitsCount', 0)) for p in pages if any(kw in p['url'].lower() for kw in ['cart', 'pay', 'check', 'login']))
        total_v = sum(int(p.get('visitsCount', 0)) for p in pages)
        tx_density = tx_v / total_v if total_v > 0 else 0
        conv_risk = friction * (1 + tx_density * 3)

        rows.append({
            'Country': country,
            'Sessions': sessions,
            'Friction': round(friction, 2),
            'Tech Debt': round(tech_debt, 2),
            'Ghost Index': round(ghost_index, 2),
            'Conversion Risk': round(min(conv_risk, 100), 2),
            'Avg Scroll': avg_scroll,
            'Dead Clicks %': dead_p,
            'Date': c_data['timestamp'][:10]
        })
    return pd.DataFrame(rows)

# ==================== APP LAYOUT ====================
st.title("🛡️ Senior Executive UX Dashboard")
st.caption("Global Quality Monitoring | Data-Driven Prioritization for AI Agents")

all_data = load_all_clarity_data()
if not all_data:
    st.error("Data directory empty or invalid.")
    st.stop()

df = get_advanced_stats(all_data)

tabs = st.tabs([
    "🎯 Friction Matrix", 
    "🚨 Stability & Tech Debt", 
    "👻 Engagement (Ghost Reading)", 
    "📊 Statistical Anomalies"
])

# --- TAB 1: FRICTION MATRIX ---
with tabs[0]:
    st.header("Conversion Friction Matrix")
    st.info("""
    **WHAT:** This matrix plots Market Size (Sessions) against User Friction (Rage + Dead Clicks).
    **HOW:** We calculate a weighted index of frustration and cross-reference it with volume.
    **WHY:** It identifies 'Money Burners' (High volume + High friction) where every minute of delay costs the most revenue.
    """)
    
    fig = px.scatter(
        df, x="Sessions", y="Friction", size="Conversion Risk", color="Friction",
        hover_name="Country", text="Country", color_continuous_scale="RdYlGn_r",
        title="Impact vs. Friction (Bubble Size = Conversion Risk)"
    )
    st.plotly_chart(fig, use_container_width=True)
    
    st.subheader("🤖 AI Agent Mission")
    top_f = df.sort_values('Friction', ascending=False).iloc[0]
    st.warning(f"**Primary Objective:** Analyze {top_f['Country']}. Friction is {top_f['Friction']} pts. Focus on resolving Dead Clicks on high-traffic pages.")

# --- TAB 2: STABILITY & TECH DEBT ---
with tabs[1]:
    st.header("Technical Debt & Stability")
    st.info("""
    **WHAT:** Measures the density of code-level failures (JS Errors and Error Clicks).
    **HOW:** Score = (Script Errors % * 0.7) + (Error Clicks % * 0.3).
    **WHY:** High friction might be a design choice, but High Tech Debt is always a bug.
    """)
    
    col1, col2 = st.columns([2, 1])
    with col1:
        fig_bar = px.bar(df.sort_values('Tech Debt'), x='Tech Debt', y='Country', orientation='h', 
                         color='Tech Debt', color_continuous_scale='OrRd')
        st.plotly_chart(fig_bar, use_container_width=True)
    with col2:
        st.write("**Top Tech Failures**")
        st.table(df[['Country', 'Tech Debt']].sort_values('Tech Debt', ascending=False).head(5))

# --- TAB 3: ENGAGEMENT (GHOST READING) ---
with tabs[2]:
    st.header("Ghost Reading Analysis")
    st.info("""
    **WHAT:** Distinguishes between 'Passive Reading' and 'Active Interaction'.
    **HOW:** Ghost Index = (Scroll Depth * (100 - Friction)) / 100.
    **WHY:** High scroll but zero clicks suggests users are consuming content but failing to find/trigger the Call to Action (CTA).
    """)
    
    fig_ghost = px.scatter(df, x="Avg Scroll", y="Dead Clicks %", size="Sessions", color="Country",
                           title="Scroll Depth vs. Dead Clicks (Identify 'Dead-End' Content)")
    st.plotly_chart(fig_ghost, use_container_width=True)

# --- TAB 4: STATISTICAL ANOMALIES ---
with tabs[3]:
    st.header("Statistical Outlier Detection")
    st.info("""
    **WHAT:** Uses Z-Score calculation to find countries that are 'Statistically Broken' compared to the global average.
    **HOW:** Any score above +1.5 standard deviations from the mean is flagged.
    **WHY:** It removes 'normal' background noise and highlights catastrophic failures.
    """)
    
    mean_f = df['Friction'].mean()
    std_f = df['Friction'].std()
    df['Z-Score'] = (df['Friction'] - mean_f) / std_f
    
    outliers = df[df['Z-Score'] > 1.5]
    if not outliers.empty:
        st.error("🚨 STATISTICAL ANOMALIES DETECTED")
        st.dataframe(outliers[['Country', 'Friction', 'Z-Score', 'Date']])
    else:
        st.success("✅ No critical statistical outliers detected today.")
        
    st.subheader("Global Distribution")
    fig_dist = px.histogram(df, x="Friction", nbins=10, marginal="box", title="Global Friction Distribution")
    st.plotly_chart(fig_dist, use_container_width=True)
