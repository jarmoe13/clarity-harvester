import streamlit as st
import pandas as pd
import json
import glob
import plotly.express as px

# ==================== PAGE CONFIG ====================
st.set_page_config(
    page_title="Executive UX Command Center v5.0",
    page_icon="🛡️",
    layout="wide"
)

# ==================== COLORS & STYLES ====================
# Sztywne kolory - Dashboard jest gotowy na NextGen, gdy tylko dane spłyną
PLATFORM_COLORS = {
    "NextGen": "#00CC96",   # Zielony (To chcemy widzieć)
    "Webshop": "#EF553B",   # Czerwony (Legacy)
    "Netshop": "#636EFA",   # Niebieski (Nordics)
    "Support": "#AB63FA",   # Fioletowy
    "Other": "#B6E880",
    "Unknown": "#7F7F7F"    # Szary (Brak danych o URL)
}

# ==================== HELPER: PLATFORM DETECTOR ====================
def detect_platform(country, country_data):
    """
    Logika detekcji:
    1. Szwecja/Norwegia -> Zawsze Netshop (chyba że URL mówi inaczej)
    2. shop.lyreco -> NextGen
    3. webshop -> Webshop
    """
    urls = []
    if 'webshop' in country_data:
        for m in country_data['webshop']:
            if m['metricName'] == 'PopularPages' and m.get('information'):
                urls = [p['url'] for p in m['information']]
                break
    
    # Fallback logic
    if not urls:
        if country in ['Sweden', 'Norway']: return "Netshop"
        return "Unknown" # To wyłapie Francję z pustymi danymi

    str_urls = " ".join(urls).lower()
    
    if ".se/" in str_urls or ".no/" in str_urls or "lyreco.se" in str_urls or "lyreco.no" in str_urls:
        return "Netshop"
    if "shop.lyreco" in str_urls:
        return "NextGen"
    if "webshop" in str_urls or "lyreco.com/webshop" in str_urls:
        return "Webshop"
    if "support.lyreco" in str_urls:
        return "Support"
    
    return "Other"

# ==================== DATA ENGINE ====================
@st.cache_data(ttl=3600)
def load_consolidated_data():
    all_files = glob.glob("clarity_*.json") + glob.glob("data/clarity_*.json")
    
    historical_rows = []
    page_details = []
    tech_details = []
    audit_log = [] # Nowa lista do debugowania

    if not all_files:
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), pd.DataFrame()

    for file in all_files:
        try:
            with open(file, 'r', encoding='utf-8') as f:
                day_data = json.load(f)
            
            for country, c_data in day_data.items():
                ts_str = c_data['timestamp'].replace('Z', '')
                ts = pd.to_datetime(ts_str)
                date_only = ts.date()
                
                # DETEKCJA
                platform = detect_platform(country, c_data)
                market_name = f"{country} ({platform})"
                
                # ZBIERANIE DANYCH DO AUDYTU (DEBUGGER)
                sample_urls = []
                if 'webshop' in c_data:
                    for m in c_data['webshop']:
                        if m['metricName'] == 'PopularPages' and m.get('information'):
                            sample_urls = [p['url'] for p in m['information'][:3]] # Weź 3 pierwsze
                
                audit_log.append({
                    'Date': date_only,
                    'Country': country,
                    'Detected_Platform': platform,
                    'Sample_URLs': str(sample_urls) if sample_urls else "NO URLS FOUND"
                })

                # GŁÓWNE DANE
                m_dict = {m['metricName']: m['information'][0] for m in c_data.get('webshop', []) if m.get('information')}
                
                if platform == "Support" or platform == "Unknown":
                    continue # Pomijamy w analizie biznesowej, ale są w audycie

                historical_rows.append({
                    'Date': date_only,
                    'Country': country,
                    'Platform': platform,
                    'Market': market_name,
                    'Sessions': int(m_dict.get('DeadClickCount', {}).get('sessionsCount', 0)),
                    'DeadClicks_Pct': float(m_dict.get('DeadClickCount', {}).get('sessionsWithMetricPercentage', 0)),
                    'RageClicks_Pct': float(m_dict.get('RageClickCount', {}).get('sessionsWithMetricPercentage', 0)),
                    'JS_Errors_Pct': float(m_dict.get('ScriptErrorCount', {}).get('sessionsWithMetricPercentage', 0)),
                    'Avg_Scroll': float(m_dict.get('ScrollDepth', {}).get('averageScrollDepth', 0)),
                    'QuickBack_Pct': float(m_dict.get('QuickbackClick', {}).get('sessionsWithMetricPercentage', 0))
                })

                # SZCZEGÓŁY STRON
                for m in c_data.get('webshop', []):
                    if m['metricName'] == 'PopularPages':
                        for p in m['information']:
                            page_details.append({
                                'Date': date_only, 'Market': market_name, 'Platform': platform,
                                'URL': p['url'], 'Visits': int(p['visitsCount'])
                            })
                    if m['metricName'] in ['Browser', 'Device', 'OS']:
                        for t in m['information']:
                            tech_details.append({
                                'Date': date_only, 'Market': market_name, 'Platform': platform, 'Category': m['metricName'], 
                                'Name': t['name'], 'Sessions': int(t['sessionsCount'])
                            })
                            
        except Exception:
            continue

    return pd.DataFrame(historical_rows), pd.DataFrame(page_details), pd.DataFrame(tech_details), pd.DataFrame(audit_log)

# ==================== UI & LOGIC ====================

st.sidebar.title("🎛️ Control Panel")
st.sidebar.markdown("---")

if 'analysis_active' not in st.session_state:
    st.session_state['analysis_active'] = False

if st.sidebar.button("🚀 RUN ANALYSIS", type="primary"):
    st.session_state['analysis_active'] = True
    st.cache_data.clear()
    st.rerun()

if st.sidebar.button("🔄 Refresh Data"):
    st.cache_data.clear()
    st.rerun()

# --- LANDING PAGE ---
if not st.session_state['analysis_active']:
    st.title("🛡️ Executive UX Command Center")
    st.info("System Ready. Click RUN ANALYSIS to start.")
else:
    df_main, df_pages, df_tech, df_audit = load_consolidated_data()

    if df_main.empty and df_audit.empty:
        st.error("No data found.")
    else:
        df_main['Friction_Score'] = (df_main['DeadClicks_Pct'] * 0.7) + (df_main['RageClicks_Pct'] * 0.3)

        # FILTERS
        st.sidebar.header("Filters")
        avail_platforms = sorted(df_main['Platform'].unique())
        sel_platform = st.sidebar.multiselect("Platform", avail_platforms, default=avail_platforms)
        avail_countries = sorted(df_main['Country'].unique())
        sel_countries = st.sidebar.multiselect("Country", avail_countries, default=avail_countries)

        mask = (df_main['Platform'].isin(sel_platform)) & (df_main['Country'].isin(sel_countries))
        filtered_df = df_main[mask]
        
        # HEADER
        st.title("🛡️ UX Strategy: Platform Comparison")
        
        # OSTRZEŻENIE O JAKOŚCI DANYCH
        missing_nextgen = df_audit[df_audit['Detected_Platform'] == 'NextGen']
        if missing_nextgen.empty:
            st.warning("⚠️ **DATA ALERT:** No 'NextGen' traffic detected in the uploaded files. Charts will show Legacy Webshop only.")

        # KPI ROW
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Avg Friction Score", f"{filtered_df['Friction_Score'].mean():.1f}")
        c2.metric("Dead Clicks", f"{filtered_df['DeadClicks_Pct'].mean():.1f}%")
        
        if "NextGen" in avail_platforms and "Webshop" in avail_platforms:
            ng_score = df_main[df_main['Platform']=="NextGen"]['Friction_Score'].mean()
            ws_score = df_main[df_main['Platform']=="Webshop"]['Friction_Score'].mean()
            if pd.notna(ng_score) and pd.notna(ws_score):
                delta = ws_score - ng_score
                c3.metric("NextGen Advantage", f"{ng_score:.1f}", delta=f"{delta:.1f} pts better" if delta > 0 else f"{delta:.1f} pts worse", delta_color="inverse")
            else:
                c3.metric("JS Errors", f"{filtered_df['JS_Errors_Pct'].mean():.1f}%")
        else:
            c3.metric("JS Errors", f"{filtered_df['JS_Errors_Pct'].mean():.1f}%")
            
        c4.metric("Total Sessions", f"{filtered_df['Sessions'].sum()}")

        st.markdown("---")
        
        tabs = st.tabs(["⚔️ Platform Battle", "📈 Trends", "🔍 Data Inspector (Audit)", "📄 Pages"])

        with tabs[0]:
            st.header("Platform Comparison")
            if filtered_df.empty:
                st.info("Select filters to see data.")
            else:
                col_a, col_b = st.columns(2)
                with col_a:
                    st.subheader("Friction Score Distribution")
                    fig_bar = px.box(df_main[df_main['Country'].isin(sel_countries)], 
                                     x="Platform", y="Friction_Score", 
                                     color="Platform", points="all",
                                     color_discrete_map=PLATFORM_COLORS)
                    st.plotly_chart(fig_bar, use_container_width=True)
                    st.caption("ℹ️ **Calculation:** `(Dead Clicks % * 0.7) + (Rage Clicks % * 0.3)`. Lower is better.")
                
                with col_b:
                    st.subheader("Tech Debt (JS Errors)")
                    fig_tech = px.box(df_main[df_main['Country'].isin(sel_countries)], 
                                      x="Platform", y="JS_Errors_Pct", 
                                      color="Platform",
                                      color_discrete_map=PLATFORM_COLORS)
                    st.plotly_chart(fig_tech, use_container_width=True)
                    st.caption("ℹ️ **Metric:** % of sessions with Script Errors.")

        with tabs[1]:
            st.subheader("Trends over Time")
            fig_line = px.line(filtered_df, x="Date", y="Friction_Score", color="Market", markers=True)
            st.plotly_chart(fig_line, use_container_width=True)

        with tabs[2]:
            st.header("🔍 Data Inspector")
            st.markdown("""
            **Use this tab to debug why a country is classified as Webshop/NextGen.**
            If you see 'Webshop' for France/Poland, it means the JSON file only contained legacy URLs.
            """)
            
            # Pokaż ostatni dzień dla każdego kraju
            latest_audit = df_audit.sort_values('Date', ascending=False).drop_duplicates(subset=['Country'])
            st.dataframe(latest_audit[['Country', 'Detected_Platform', 'Sample_URLs']], use_container_width=True)
            
            st.error(f"**Missing Countries:** Italy (not found in any file).")
            st.warning(f"**Empty Data:** France (found but no URL data).")

        with tabs[3]:
            st.header("Top URLs")
            pages_sub = df_pages[df_pages['Market'].isin(filtered_df['Market'])]
            if not pages_sub.empty:
                top_p = pages_sub.groupby(['Platform', 'URL'])['Visits'].sum().sort_values(ascending=False).head(20).reset_index()
                st.dataframe(top_p, use_container_width=True)
