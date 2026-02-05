import streamlit as st
import pandas as pd
import json
import glob
import plotly.express as px

# ==================== PAGE CONFIG ====================
st.set_page_config(
    page_title="Executive UX Command Center v3.0",
    page_icon="🛡️",
    layout="wide"
)

# ==================== SESSION STATE ====================
if 'analysis_active' not in st.session_state:
    st.session_state['analysis_active'] = False

# ==================== HELPER: PLATFORM DETECTOR ====================
def detect_platform(country_data):
    """Próbuje zgadnąć platformę na podstawie URLi w PopularPages."""
    urls = []
    # Szukamy w PopularPages
    if 'webshop' in country_data:
        for m in country_data['webshop']:
            if m['metricName'] == 'PopularPages' and m.get('information'):
                urls = [p['url'] for p in m['information']]
                break
    
    if not urls:
        return "Unknown"

    # Logika detekcji
    str_urls = " ".join(urls).lower()
    if "shop.lyreco" in str_urls:
        return "Next_Gen"
    elif "webshop" in str_urls or "lyreco.com" in str_urls:
        return "Webshop"
    elif "support.lyreco" in str_urls:
        return "Support"
    
    return "Other"

# ==================== DATA ENGINE ====================
@st.cache_data(ttl=3600)
def load_consolidated_data():
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
                
                # DETEKCJA PLATFORMY
                platform = detect_platform(c_data)
                
                # Tworzymy unikalną nazwę rynku: "France (Next_Gen)"
                market_name = f"{country} ({platform})"
                
                m_dict = {m['metricName']: m['information'][0] for m in c_data.get('webshop', []) if m.get('information')}
                
                # Pomijamy wpisy bez sesji lub "Support" jeśli nie chcemy ich analizować
                if platform == "Support":
                    continue

                historical_rows.append({
                    'Date': date_only,
                    'Country': country,
                    'Platform': platform,
                    'Market': market_name, # <-- KLUCZ DO SUKCESU
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
                            page_details.append({
                                'Date': date_only, 
                                'Market': market_name,
                                'Platform': platform,
                                'URL': p['url'], 
                                'Visits': int(p['visitsCount'])
                            })
                    if m['metricName'] in ['Browser', 'Device', 'OS']:
                        for t in m['information']:
                            tech_details.append({
                                'Date': date_only, 
                                'Market': market_name,
                                'Category': m['metricName'], 
                                'Name': t['name'], 
                                'Sessions': int(t['sessionsCount'])
                            })
                            
        except Exception:
            continue

    return pd.DataFrame(historical_rows), pd.DataFrame(page_details), pd.DataFrame(tech_details)

# ==================== UI & LOGIC ====================

st.sidebar.title("🎛️ Panel Sterowania")
st.sidebar.markdown("---")

if st.sidebar.button("🚀 URUCHOM ANALIZĘ", type="primary"):
    st.session_state['analysis_active'] = True
    st.cache_data.clear()
    st.rerun()

if st.sidebar.button("🔄 Odśwież"):
    st.cache_data.clear()
    st.rerun()

if not st.session_state['analysis_active']:
    st.title("🛡️ Executive UX Command Center v3.0")
    st.markdown("### Next Gen vs Legacy Edition")
    st.info("Kliknij URUCHOM, aby zobaczyć porównanie platform.")
else:
    df_main, df_pages, df_tech = load_consolidated_data()

    if df_main.empty:
        st.error("Brak danych.")
    else:
        # KPI Calculation
        df_main['Friction_Score'] = (df_main['DeadClicks_Pct'] * 0.7) + (df_main['RageClicks_Pct'] * 0.3)

        # FILTRY
        st.sidebar.header("Filtry")
        
        # 1. Wybór Platformy
        avail_platforms = sorted(df_main['Platform'].unique())
        sel_platform = st.sidebar.multiselect("Platforma", avail_platforms, default=avail_platforms)
        
        # 2. Wybór Rynku (Country)
        avail_countries = sorted(df_main['Country'].unique())
        sel_countries = st.sidebar.multiselect("Kraj", avail_countries, default=avail_countries)

        # Filtrowanie
        mask = (df_main['Platform'].isin(sel_platform)) & (df_main['Country'].isin(sel_countries))
        filtered_df = df_main[mask]
        
        # DASHBOARD HEADER
        st.title("🛡️ UX Battle: NextGen vs Webshop")
        st.caption(f"Analiza dla {len(filtered_df['Market'].unique())} segmentów (Kraj + Platforma).")

        # KPI ROW
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Średnia Frustracja", f"{filtered_df['Friction_Score'].mean():.1f}")
        c2.metric("Dead Clicks", f"{filtered_df['DeadClicks_Pct'].mean():.1f}%")
        
        # Dynamiczne porównanie (jeśli mamy obie platformy)
        if "Next_Gen" in avail_platforms and "Webshop" in avail_platforms:
            ng_score = df_main[df_main['Platform']=="Next_Gen"]['Friction_Score'].mean()
            ws_score = df_main[df_main['Platform']=="Webshop"]['Friction_Score'].mean()
            delta = ws_score - ng_score
            c3.metric("Przewaga NextGen", f"{ng_score:.1f}", delta=f"{delta:.1f} lepszy" if delta > 0 else f"{delta:.1f} gorszy", delta_color="inverse")
        else:
            c3.metric("JS Errors", f"{filtered_df['JS_Errors_Pct'].mean():.1f}%")
            
        c4.metric("Total Sessions", f"{filtered_df['Sessions'].sum()}")

        st.markdown("---")
        
        tabs = st.tabs(["⚔️ Porównanie Platform", "📈 Trendy Rynkowe", "🛠️ Tech & Bugs", "📄 Strony"])

        # --- TAB 1: BATTLE ---
        with tabs[0]:
            st.header("Globalne Starcie: NextGen vs Legacy")
            
            col_a, col_b = st.columns(2)
            with col_a:
                st.subheader("Średnia Frustracja wg Platformy")
                fig_bar = px.box(df_main[df_main['Country'].isin(sel_countries)], x="Platform", y="Friction_Score", color="Platform", points="all")
                st.plotly_chart(fig_bar, use_container_width=True)
            
            with col_b:
                st.subheader("Błędy Skryptów (Tech Debt)")
                fig_tech = px.box(df_main[df_main['Country'].isin(sel_countries)], x="Platform", y="JS_Errors_Pct", color="Platform")
                st.plotly_chart(fig_tech, use_container_width=True)
            
            st.subheader("Detale per Rynek (Kto radzi sobie lepiej?)")
            # Pivot table dla porównania
            pivot = df_main[df_main['Country'].isin(sel_countries)].groupby(['Country', 'Platform'])['Friction_Score'].mean().reset_index()
            fig_comp = px.bar(pivot, x="Country", y="Friction_Score", color="Platform", barmode="group", title="Bezpośrednie Porównanie Frustracji")
            st.plotly_chart(fig_comp, use_container_width=True)

        # --- TAB 2: TRENDY ---
        with tabs[1]:
            st.subheader("Trendy w Czasie (Rozbite na Platformy)")
            # Tutaj używamy 'Market' jako koloru, żeby widzieć np. France (NG) vs France (WS)
            fig_line = px.line(filtered_df, x="Date", y="Friction_Score", color="Market", markers=True)
            st.plotly_chart(fig_line, use_container_width=True)

        # --- TAB 3: TECH ---
        with tabs[2]:
            st.header("Gdzie są bugi?")
            
            # Filtrujemy szczegóły techniczne
            tech_sub = df_tech[df_tech['Market'].isin(filtered_df['Market'])]
            
            if not tech_sub.empty:
                col_t1, col_t2 = st.columns(2)
                with col_t1:
                    st.subheader("Rozkład błędów na Urządzeniach")
                    fig_dev = px.sunburst(tech_sub[tech_sub['Category']=='Device'], path=['Platform', 'Name'], values='Sessions')
                    st.plotly_chart(fig_dev, use_container_width=True)
                with col_t2:
                    st.subheader("Systemy Operacyjne")
                    fig_os = px.bar(tech_sub[tech_sub['Category']=='OS'], x="Sessions", y="Name", color="Platform", barmode="group", orientation='h')
                    st.plotly_chart(fig_os, use_container_width=True)
            else:
                st.info("Brak danych technicznych dla wyboru.")

        # --- TAB 4: PAGES ---
        with tabs[3]:
            st.header("Problematyczne Strony")
            st.caption("Top strony posortowane wg liczby wizyt.")
            pages_sub = df_pages[df_pages['Market'].isin(filtered_df['Market'])]
            if not pages_sub.empty:
                top_p = pages_sub.groupby(['Platform', 'URL'])['Visits'].sum().sort_values(ascending=False).head(20).reset_index()
                st.dataframe(top_p, use_container_width=True)
