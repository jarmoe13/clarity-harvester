import streamlit as st
import pandas as pd
import json
import glob
import plotly.express as px

# ==================== PAGE CONFIG ====================
st.set_page_config(
    page_title="Executive UX Command Center v5.5",
    page_icon="🛡️",
    layout="wide"
)

# ==================== COLORS & STYLES ====================
PLATFORM_COLORS = {
    "NextGen": "#00CC96",   # Zielony
    "Webshop": "#EF553B",   # Czerwony
    "Netshop": "#636EFA",   # Niebieski
    "Support": "#AB63FA",   # Fioletowy
    "Other": "#B6E880",
    "Unknown": "#7F7F7F"
}

# ==================== HELPER: PLATFORM DETECTOR (UPDATED) ====================
def detect_platform(country, country_data):
    """
    Ulepszona logika detekcji:
    1. Sprawdza PopularPages.
    2. Jeśli brak wyniku, sprawdza ReferrerUrl (często tam ukrywa się NextGen).
    3. Fallback do reguł geograficznych.
    """
    # 1. Zbieramy dowody z PopularPages
    page_urls = []
    if 'webshop' in country_data:
        for m in country_data['webshop']:
            if m['metricName'] == 'PopularPages' and m.get('information'):
                page_urls = [p['url'] for p in m['information']]
                break
    
    # 2. Zbieramy dowody z ReferrerUrl (NOWOŚĆ)
    ref_urls = []
    if 'webshop' in country_data:
        for m in country_data['webshop']:
            if m['metricName'] == 'ReferrerUrl' and m.get('information'):
                # Referrer 'name' może być None, więc filtrujemy
                ref_urls = [str(p['name']) for p in m['information'] if p.get('name')]
                break

    # Łączymy dowody w jeden ciąg tekstowy do analizy
    all_evidence = (" ".join(page_urls) + " " + " ".join(ref_urls)).lower()

    # PRIORYTET 1: Netshop (Szwecja/Norwegia są specyficzne)
    if country in ['Sweden', 'Norway'] or ".se/" in all_evidence or ".no/" in all_evidence:
        return "Netshop"

    # PRIORYTET 2: NextGen (Szukamy shop.lyreco gdziekolwiek)
    if "shop.lyreco" in all_evidence:
        return "NextGen"
        
    # PRIORYTET 3: Legacy Webshop
    if "webshop" in all_evidence or "lyreco.com/webshop" in all_evidence:
        return "Webshop"
        
    # PRIORYTET 4: Support
    if "support.lyreco" in all_evidence:
        return "Support"
    
    # Fallback jeśli brak URLi, ale znamy kraj (np. Francja bez URLi w pliku)
    # Możemy założyć Webshop, chyba że wiesz, że Francja to już NextGen?
    if not page_urls and not ref_urls:
        return "Unknown"

    return "Other"

# ==================== DATA ENGINE ====================
@st.cache_data(ttl=3600)
def load_consolidated_data():
    all_files = glob.glob("clarity_*.json") + glob.glob("data/clarity_*.json")
    
    historical_rows = []
    page_details = []
    tech_details = []
    audit_log = []

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
                
                # DETEKCJA PLATFORMY (Nowa logika)
                platform = detect_platform(country, c_data)
                market_name = f"{country} ({platform})"
                
                # DEBUGGER log
                audit_log.append({
                    'Date': date_only,
                    'Country': country,
                    'Detected_Platform': platform,
                    'Source_File': file
                })

                m_dict = {m['metricName']: m['information'][0] for m in c_data.get('webshop', []) if m.get('information')}
                
                if platform in ["Support", "Unknown"]:
                    continue

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

    if df_main.empty:
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
        st.caption("Now scanning `PopularPages` AND `ReferrerUrl` to detect NextGen traffic.")

        # KPI ROW
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Avg Friction Score", f"{filtered_df['Friction_Score'].mean():.1f}")
        c2.metric("Dead Clicks", f"{filtered_df['DeadClicks_Pct'].mean():.1f}%")
        
        if "NextGen" in avail_platforms:
             ng_score = df_main[df_main['Platform']=="NextGen"]['Friction_Score'].mean()
             if pd.notna(ng_score):
                 c3.metric("NextGen Friction", f"{ng_score:.1f}", "Target < 10.0")
             else:
                 c3.metric("NextGen Friction", "N/A")
        else:
             c3.metric("JS Errors", f"{filtered_df['JS_Errors_Pct'].mean():.1f}%")
            
        c4.metric("Total Sessions", f"{filtered_df['Sessions'].sum()}")

        st.markdown("---")
        
        tabs = st.tabs(["⚔️ Platform Battle", "📈 Trends", "🔍 Data Inspector", "📄 Pages"])

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
                
                with col_b:
                    st.subheader("Tech Debt (JS Errors)")
                    fig_tech = px.box(df_main[df_main['Country'].isin(sel_countries)], 
                                      x="Platform", y="JS_Errors_Pct", 
                                      color="Platform",
                                      color_discrete_map=PLATFORM_COLORS)
                    st.plotly_chart(fig_tech, use_container_width=True)

        with tabs[1]:
            st.subheader("Trends over Time")
            fig_line = px.line(filtered_df, x="Date", y="Friction_Score", color="Market", markers=True)
            st.plotly_chart(fig_line, use_container_width=True)

        with tabs[2]:
            st.header("🔍 Data Inspector")
            st.markdown("Check how countries are classified based on `PopularPages` + `ReferrerUrl`.")
            st.dataframe(df_audit.drop_duplicates(subset=['Country', 'Detected_Platform']), use_container_width=True)

        with tabs[3]:
            st.header("Top URLs")
            pages_sub = df_pages[df_pages['Market'].isin(filtered_df['Market'])]
            if not pages_sub.empty:
                top_p = pages_sub.groupby(['Platform', 'URL'])['Visits'].sum().sort_values(ascending=False).head(20).reset_index()
                st.dataframe(top_p, use_container_width=True)
