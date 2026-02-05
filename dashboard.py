import streamlit as st
import pandas as pd
import json
import os
import glob
import numpy as np
from datetime import datetime
import plotly.express as px

# ==================== PAGE CONFIG ====================
st.set_page_config(
    page_title="Executive UX Command Center v2.0",
    page_icon="🛡️",
    layout="wide"
)

# ==================== DATA ENGINE (REMASTERED) ====================
@st.cache_data
def load_consolidated_data():
    """Konsoliduje wszystkie pliki JSON w jedną strukturę DataFrame bez nadpisywania."""
    data_path = "clarity_*.json"
    all_files = glob.glob(data_path)
    
    historical_rows = []
    page_details = []
    tech_details = []

    for file in all_files:
        try:
            with open(file, 'r', encoding='utf-8') as f:
                day_data = json.load(f)
            
            for country, c_data in day_data.items():
                ts = pd.to_datetime(c_data['timestamp'])
                date_only = ts.date()
                
                # Słownik metryk głównych
                m_dict = {m['metricName']: m['information'][0] for m in c_data.get('webshop', []) if m.get('information')}
                
                # 1. Główny wiersz danych (Time Series)
                historical_rows.append({
                    'Date': date_only,
                    'Country': country,
                    'Sessions': int(m_dict.get('DeadClickCount', {}).get('sessionsCount', 0)),
                    'DeadClicks_Pct': float(m_dict.get('DeadClickCount', {}).get('sessionsWithMetricPercentage', 0)),
                    'RageClicks_Pct': float(m_dict.get('RageClickCount', {}).get('sessionsWithMetricPercentage', 0)),
                    'JS_Errors_Pct': float(m_dict.get('ScriptErrorCount', {}).get('sessionsWithMetricPercentage', 0)),
                    'Avg_Scroll': float(m_dict.get('ScrollDepth', {}).get('averageScrollDepth', 0)),
                    'QuickBack_Pct': float(m_dict.get('QuickbackClick', {}).get('sessionsWithMetricPercentage', 0))
                })

                # 2. Dane o stronach (PopularPages)
                for m in c_data.get('webshop', []):
                    if m['metricName'] == 'PopularPages':
                        for p in m['information']:
                            page_details.append({
                                'Date': date_only,
                                'Country': country,
                                'URL': p['url'],
                                'Visits': int(p['visitsCount'])
                            })
                    
                    # 3. Dane techniczne (Browser/OS/Device)
                    if m['metricName'] in ['Browser', 'Device', 'OS']:
                        for t in m['information']:
                            tech_details.append({
                                'Date': date_only,
                                'Country': country,
                                'Category': m['metricName'],
                                'Name': t['name'],
                                'Sessions': int(t['sessionsCount'])
                            })
                            
        except Exception as e:
            st.warning(f"Błąd ładowania pliku {file}: {e}")
            continue

    return pd.DataFrame(historical_rows), pd.DataFrame(page_details), pd.DataFrame(tech_details)

# Załaduj dane
df_main, df_pages, df_tech = load_consolidated_data()

# ==================== CALCULATIONS ====================
# Wyliczanie wskaźnika Friction Score
df_main['Friction_Score'] = (df_main['DeadClicks_Pct'] * 0.7) + (df_main['RageClicks_Pct'] * 0.3)

# ==================== APP LAYOUT ====================
st.title("🛡️ Executive UX Command Center")
st.markdown("### Monitorowanie Jakości i Priorytetyzacja Napraw")

# Sidebar - Globalne Filtry
st.sidebar.header("Filtry Globalne")
selected_countries = st.sidebar.multiselect("Rynki", df_main['Country'].unique(), default=df_main['Country'].unique()[:3])
date_range = st.sidebar.date_input("Zakres dat", [df_main['Date'].min(), df_main['Date'].max()])

# Filtrowanie danych
mask = (df_main['Country'].isin(selected_countries)) & (df_main['Date'] >= date_range[0]) & (df_main['Date'] <= date_range[1])
filtered_df = df_main[mask]

# TABS
tabs = st.tabs(["📈 Trendy i Biznes", "🛠️ Techniczny Deep-Dive", "📄 Analiza Stron", "🤖 Rekomendacje PO"])

# --- TAB 1: TRENDY I BIZNES ---
with tabs[0]:
    col1, col2 = st.columns([3, 1])
    with col1:
        st.subheader("Ewolucja Frustracji Użytkowników")
        fig_trend = px.line(filtered_df, x='Date', y='Friction_Score', color='Country', markers=True,
                            title="Friction Score (Dead + Rage Clicks) w czasie")
        st.plotly_chart(fig_trend, use_container_width=True)
    
    with col2:
        st.metric("Avg Friction", f"{filtered_df['Friction_Score'].mean():.2f}")
        st.metric("Max JS Errors", f"{filtered_df['JS_Errors_Pct'].max():.1f}%")
        st.info("Friction Score powyżej 15.0 wymaga natychmiastowej interwencji UX.")

# --- TAB 2: TECHNICZNY DEEP-DIVE ---
with tabs[1]:
    st.header("Gdzie psuje się technologia?")
    c1, c2 = st.columns(2)
    
    # Segmentacja urządzeń
    t_mask = (df_tech['Country'].isin(selected_countries))
    tech_sum = df_tech[t_mask].groupby(['Category', 'Name'])['Sessions'].sum().reset_index()
    
    with c1:
        fig_dev = px.pie(tech_sum[tech_sum['Category']=='Device'], values='Sessions', names='Name', title="Ruch wg Urządzeń")
        st.plotly_chart(fig_dev)
    
    with c2:
        fig_os = px.bar(tech_sum[tech_sum['Category']=='OS'].sort_values('Sessions'), x='Sessions', y='Name', orientation='h', title="Systemy Operacyjne")
        st.plotly_chart(fig_os)

# --- TAB 3: ANALIZA STRON ---
with tabs[2]:
    st.header("Najpopularniejsze strony vs Ryzyko")
    p_mask = (df_pages['Country'].isin(selected_countries))
    top_pages = df_pages[p_mask].groupby('URL')['Visits'].sum().sort_values(ascending=False).head(15).reset_index()
    
    st.table(top_pages)
    st.caption("PO Tip: Skoreluj te strony z Dead Clicks w Clarity, aby znaleźć wąskie gardła w koszyku.")

# --- TAB 4: REKOMENDACJE PO ---
with tabs[3]:
    st.header("🤖 Backlog AI dla Product Ownera")
    
    # Prosta logika alertów
    critical = filtered_df[filtered_df['JS_Errors_Pct'] > 25]
    if not critical.empty:
        for _, row in critical.iterrows():
            st.error(f"🚨 **KRYTYCZNY BŁĄD:** Rynek {row['Country']} miał {row['Date']} aż {row['JS_Errors_Pct']}% błędów skryptów!")
            st.write("--> Zadanie dla IT: Sprawdzić konsolę błędów dla najnowszych wdrożeń na tym rynku.")
    
    dead_alert = filtered_df[filtered_df['DeadClicks_Pct'] > 20]
    if not dead_alert.empty:
        st.warning(f"⚠️ **UX ISSUE:** Wykryto wysoki poziom Dead Clicks (>20%) na {len(dead_alert)} rynkach.")
        st.write("--> Zadanie dla UX: Przeprowadzić sesje obserwacyjne (Recordingi) dla kliknięć w elementy nieinteraktywne.")
