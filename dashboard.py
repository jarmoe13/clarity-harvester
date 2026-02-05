import streamlit as st
import pandas as pd
import json
import os
import glob
from datetime import datetime
import plotly.express as px

# ==================== PAGE CONFIG ====================
st.set_page_config(
    page_title="Executive UX Command Center v2.2",
    page_icon="🛡️",
    layout="wide"
)

# ==================== SESSION STATE INIT ====================
# To zapobiega znikaniu danych po kliknięciu w filtry
if 'analysis_active' not in st.session_state:
    st.session_state['analysis_active'] = False

# ==================== DATA ENGINE ====================
@st.cache_data(ttl=3600) # Cache ważny przez godzinę lub do ręcznego resetu
def load_consolidated_data():
    """Konsoliduje dane z obsługą błędów."""
    all_files = glob.glob("clarity_*.json") + glob.glob("data/clarity_*.json")
    
    historical_rows = []
    page_details = []
    tech_details = []

    if not all_files:
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame()

    for file in all_files:
        try:
            with open(file, 'r', encoding='utf-8') as f:
                day_data = json.load(f)
            
            for country, c_data in day_data.items():
                ts_str = c_data['timestamp'].replace('Z', '')
                ts = pd.to_datetime(ts_str)
                date_only = ts.date()
                
                m_dict = {m['metricName']: m['information'][0] for m in c_data.get('webshop', []) if m.get('information')}
                
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

                for m in c_data.get('webshop', []):
                    if m['metricName'] == 'PopularPages':
                        for p in m['information']:
                            page_details.append({'Date': date_only, 'Country': country, 'URL': p['url'], 'Visits': int(p['visitsCount'])})
                    if m['metricName'] in ['Browser', 'Device', 'OS']:
                        for t in m['information']:
                            tech_details.append({'Date': date_only, 'Country': country, 'Category': m['metricName'], 'Name': t['name'], 'Sessions': int(t['sessionsCount'])})
                            
        except Exception:
            continue

    return pd.DataFrame(historical_rows), pd.DataFrame(page_details), pd.DataFrame(tech_details)

# ==================== SIDEBAR CONTROL PANEL ====================
st.sidebar.title("🎛️ Panel Sterowania")

st.sidebar.markdown("---")
# BIG RED BUTTON
if st.sidebar.button("🚀 URUCHOM ANALIZĘ", type="primary"):
    st.session_state['analysis_active'] = True
    st.cache_data.clear() # Wymuś odświeżenie danych przy kliknięciu start
    st.rerun()

if st.sidebar.button("🔄 Odśwież pliki (Clear Cache)"):
    st.cache_data.clear()
    st.rerun()

st.sidebar.markdown("---")

# ==================== MAIN LOGIC ====================

if not st.session_state['analysis_active']:
    # --- EKRAN STARTOWY (LANDING PAGE) ---
    st.title("🛡️ Executive UX Command Center")
    st.markdown("""
    ### Witaj w centrum analizy Clarity.
    
    Ten dashboard skonsoliduje Twoje pliki JSON i wykryje:
    * 🚨 **Rage Clicks & Dead Clicks** (Frustracja użytkowników)
    * 🐛 **Dług Techniczny** (Błędy JS na konkretnych rynkach)
    * 📉 **Trendy** (Czy po wdrożeniu jest lepiej czy gorzej?)
    
    **Status:** Oczekiwanie na uruchomienie silnika danych.
    
    👈 **Kliknij "URUCHOM ANALIZĘ" w menu po lewej, aby rozpocząć.**
    """)
    st.image("https://clarity.microsoft.com/favicon.ico", width=100) # Opcjonalne logo
    
else:
    # --- DASHBOARD WŁAŚCIWY ---
    df_main, df_pages, df_tech = load_consolidated_data()

    if df_main.empty:
        st.error("🚨 Brak danych! Wrzuć pliki `clarity_*.json` do folderu.")
    else:
        # Obliczenia
        df_main['Friction_Score'] = (df_main['DeadClicks_Pct'] * 0.7) + (df_main['RageClicks_Pct'] * 0.3)
        
        # Filtry w Sidebarze (pojawiają się dopiero po uruchomieniu)
        st.sidebar.header("Filtry Danych")
        all_countries = sorted(df_main['Country'].unique())
        selected_countries = st.sidebar.multiselect("Rynki", all_countries, default=all_countries[:3])
        
        if not selected_countries:
            st.warning("Wybierz przynajmniej jeden kraj z menu po lewej.")
            st.stop()

        # Filtrowanie DF
        filtered_df = df_main[df_main['Country'].isin(selected_countries)]
        
        # HEADER
        st.title("🛡️ Executive UX Dashboard")
        st.caption(f"Analiza dla: {', '.join(selected_countries)} | Zakres danych: {filtered_df['Date'].min()} - {filtered_df['Date'].max()}")

        # KPI ROW
        kpi1, kpi2, kpi3, kpi4 = st.columns(4)
        kpi1.metric("Średnia Frustracja (Friction)", f"{filtered_df['Friction_Score'].mean():.1f}", delta_color="inverse")
        kpi2.metric("Dead Clicks (Śr.)", f"{filtered_df['DeadClicks_Pct'].mean():.1f}%")
        kpi3.metric("JS Errors (Max)", f"{filtered_df['JS_Errors_Pct'].max():.1f}%", "Krytyczne!" if filtered_df['JS_Errors_Pct'].max() > 20 else "Normal")
        kpi4.metric("Liczba Sesji", f"{filtered_df['Sessions'].sum()}")

        st.markdown("---")

        # TABS
        tabs = st.tabs(["📈 Trendy Biznesowe", "🛠️ Analiza Techniczna", "📄 Top Strony", "🤖 Rekomendacje"])

        with tabs[0]:
            st.subheader("Trendy Frustracji (Dead + Rage Clicks)")
            fig_trend = px.line(filtered_df, x='Date', y='Friction_Score', color='Country', markers=True, height=400)
            st.plotly_chart(fig_trend, use_container_width=True)
            
            st.subheader("Głębokość Scrollowania")
            fig_scroll = px.bar(filtered_df, x='Date', y='Avg_Scroll', color='Country', barmode='group')
            st.plotly_chart(fig_scroll, use_container_width=True)

        with tabs[1]:
            st.header("Segmentacja Błędów")
            c1, c2 = st.columns(2)
            tech_filtered = df_tech[df_tech['Country'].isin(selected_countries)]
            
            with c1:
                st.subheader("Błędy a Przeglądarka (Browser)")
                browser_data = tech_filtered[tech_filtered['Category'] == 'Browser'].groupby('Name')['Sessions'].sum().reset_index()
                fig_pie = px.pie(browser_data, values='Sessions', names='Name', hole=0.4)
                st.plotly_chart(fig_pie)
                
            with c2:
                st.subheader("Błędy a Urządzenie (Device)")
                device_data = tech_filtered[tech_filtered['Category'] == 'Device'].groupby('Name')['Sessions'].sum().reset_index()
                fig_bar = px.bar(device_data, x='Sessions', y='Name', orientation='h', color='Sessions')
                st.plotly_chart(fig_bar)

        with tabs[2]:
            st.header("Strony generujące ruch")
            pages_filtered = df_pages[df_pages['Country'].isin(selected_countries)]
            top_pages = pages_filtered.groupby('URL')['Visits'].sum().sort_values(ascending=False).head(20).reset_index()
            st.dataframe(top_pages, use_container_width=True)

        with tabs[3]:
            st.header("🤖 Product Owner Action Plan")
            
            # Algorytm rekomendacji
            high_friction = filtered_df[filtered_df['Friction_Score'] > 15]
            if not high_friction.empty:
                st.error(f"⚠️ **PRIORYTET:** Znaleziono {len(high_friction)} dni z bardzo wysoką frustracją (>15 pkt).")
                st.write("Sugerowane działanie: Sprawdź wdrożenia z tych dni.")
                st.dataframe(high_friction[['Date', 'Country', 'Friction_Score', 'JS_Errors_Pct']].sort_values('Friction_Score', ascending=False))
            else:
                st.success("✅ Brak krytycznych anomalii w wybranym okresie.")
