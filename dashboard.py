import streamlit as st
import pandas as pd
import json
import glob
import plotly.express as px

# ==================== PAGE CONFIG ====================
st.set_page_config(
    page_title="Executive UX Command Center v4.0",
    page_icon="🛡️",
    layout="wide"
)

# ==================== SESSION STATE ====================
if 'analysis_active' not in st.session_state:
    st.session_state['analysis_active'] = False

# ==================== HELPER: PLATFORM DETECTOR ====================
def detect_platform(country, country_data):
    """
    Determines the platform based on Country rules or URL patterns.
    Rules:
    1. Sweden/Norway -> Netshop
    2. shop.lyreco -> NextGen
    3. webshop -> Webshop (Legacy)
    """
    # Rule 1: Geographic/Legacy exceptions
    if country in ['Sweden', 'Norway']:
        return "Netshop"

    # Extract URLs from PopularPages for heuristic check
    urls = []
    if 'webshop' in country_data:
        for m in country_data['webshop']:
            if m['metricName'] == 'PopularPages' and m.get('information'):
                urls = [p['url'] for p in m['information']]
                break
    
    if not urls:
        return "Unknown"

    # Rule 2: URL Pattern Matching
    str_urls = " ".join(urls).lower()
    if "shop.lyreco" in str_urls:
        return "NextGen"
    elif "webshop" in str_urls or "lyreco.com/webshop" in str_urls:
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
                
                # DETECT PLATFORM
                platform = detect_platform(country, c_data)
                
                # Market Label: "France (NextGen)"
                market_name = f"{country} ({platform})"
                
                m_dict = {m['metricName']: m['information'][0] for m in c_data.get('webshop', []) if m.get('information')}
                
                # Skip Support pages for business analysis
                if platform == "Support":
                    continue

                # 1. Main Data
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

                # 2. Page Details (Added Platform column here too)
                for m in c_data.get('webshop', []):
                    if m['metricName'] == 'PopularPages':
                        for p in m['information']:
                            page_details.append({
                                'Date': date_only, 
                                'Market': market_name,
                                'Platform': platform, # <-- Added
                                'Country': country,
                                'URL': p['url'], 
                                'Visits': int(p['visitsCount'])
                            })
                    # 3. Tech Details (Added Platform column here too - CRITICAL FIX)
                    if m['metricName'] in ['Browser', 'Device', 'OS']:
                        for t in m['information']:
                            tech_details.append({
                                'Date': date_only, 
                                'Market': market_name,
                                'Platform': platform, # <-- Added (Fixes Sunburst)
                                'Country': country,
                                'Category': m['metricName'], 
                                'Name': t['name'], 
                                'Sessions': int(t['sessionsCount'])
                            })
                            
        except Exception:
            continue

    return pd.DataFrame(historical_rows), pd.DataFrame(page_details), pd.DataFrame(tech_details)

# ==================== UI & LOGIC ====================

st.sidebar.title("🎛️ Control Panel")
st.sidebar.markdown("---")

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
    st.markdown("### Ready to analyze Clarity data.")
    st.info("Click **RUN ANALYSIS** in the sidebar to start.")

# --- DASHBOARD ---
else:
    df_main, df_pages, df_tech = load_consolidated_data()

    if df_main.empty:
        st.error("No data found. Please upload `clarity_*.json` files.")
    else:
        # KPI Calculation
        # Formula: Weighted average of Dead Clicks (major friction) and Rage Clicks (extreme frustration)
        df_main['Friction_Score'] = (df_main['DeadClicks_Pct'] * 0.7) + (df_main['RageClicks_Pct'] * 0.3)

        # FILTERS
        st.sidebar.header("Filters")
        
        # Platform Filter
        avail_platforms = sorted(df_main['Platform'].unique())
        sel_platform = st.sidebar.multiselect("Platform", avail_platforms, default=avail_platforms)
        
        # Country Filter
        avail_countries = sorted(df_main['Country'].unique())
        sel_countries = st.sidebar.multiselect("Country", avail_countries, default=avail_countries)

        # Apply Filters
        mask = (df_main['Platform'].isin(sel_platform)) & (df_main['Country'].isin(sel_countries))
        filtered_df = df_main[mask]
        
        if filtered_df.empty:
            st.warning("No data for selected filters.")
            st.stop()

        # DASHBOARD HEADER
        st.title("🛡️ UX Strategy: NextGen vs Webshop vs Netshop")
        st.caption(f"Data Scope: {filtered_df['Date'].min()} to {filtered_df['Date'].max()} | Segments: {len(filtered_df['Market'].unique())}")

        # KPI ROW
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Avg Friction Score", f"{filtered_df['Friction_Score'].mean():.1f}")
        c2.metric("Dead Clicks", f"{filtered_df['DeadClicks_Pct'].mean():.1f}%")
        
        # Comparative Logic
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
        
        tabs = st.tabs(["⚔️ Platform Battle", "📈 Market Trends", "🛠️ Tech & Devices", "📄 Page Analysis"])

        # --- TAB 1: BATTLE ---
        with tabs[0]:
            st.header("Global Benchmark: Platform Comparison")
            
            col_a, col_b = st.columns(2)
            with col_a:
                st.subheader("Friction Score by Platform")
                fig_bar = px.box(df_main[df_main['Country'].isin(sel_countries)], x="Platform", y="Friction_Score", color="Platform", points="all")
                st.plotly_chart(fig_bar, use_container_width=True)
                st.caption("ℹ️ **Calculation:** `Friction Score = (Dead Clicks % * 0.7) + (Rage Clicks % * 0.3)`. Lower is better. Dots represent daily values per country.")
            
            with col_b:
                st.subheader("Technical Debt (JS Errors)")
                fig_tech = px.box(df_main[df_main['Country'].isin(sel_countries)], x="Platform", y="JS_Errors_Pct", color="Platform")
                st.plotly_chart(fig_tech, use_container_width=True)
                st.caption("ℹ️ **Calculation:** Percentage of sessions where a JavaScript error was logged. High values indicate broken code or tracking issues.")
            
            st.subheader("Direct Market Comparison")
            pivot = df_main[df_main['Country'].isin(sel_countries)].groupby(['Country', 'Platform'])['Friction_Score'].mean().reset_index()
            fig_comp = px.bar(pivot, x="Country", y="Friction_Score", color="Platform", barmode="group", title="Average Friction per Country & Platform")
            st.plotly_chart(fig_comp, use_container_width=True)
            st.caption("ℹ️ **Comparison:** Aggregated average friction score over the selected time period. Allows identifying if NextGen performs better than Legacy in specific markets.")

        # --- TAB 2: TRENDS ---
        with tabs[1]:
            st.subheader("Friction Timeline")
            fig_line = px.line(filtered_df, x="Date", y="Friction_Score", color="Market", markers=True)
            st.plotly_chart(fig_line, use_container_width=True)
            st.caption("ℹ️ **Trend:** Daily fluctuation of user frustration. Spikes usually correlate with deployments or infrastructure incidents.")

            col_q1, col_q2 = st.columns(2)
            with col_q1:
                 fig_qb = px.line(filtered_df, x="Date", y="QuickBack_Pct", color="Market", markers=True, title="QuickBack Rate (Navigation Errors)")
                 st.plotly_chart(fig_qb, use_container_width=True)
                 st.caption("ℹ️ **QuickBack:** User goes to a page and immediately returns. Indicates misleading labels or accidental clicks.")

        # --- TAB 3: TECH ---
        with tabs[2]:
            st.header("Technical Segmentation")
            
            # Apply filters to tech data
            tech_sub = df_tech[df_tech['Market'].isin(filtered_df['Market'])]
            
            if not tech_sub.empty:
                col_t1, col_t2 = st.columns(2)
                with col_t1:
                    st.subheader("Sessions by Device & Platform")
                    # FIX: Now tech_sub has 'Platform' column
                    fig_dev = px.sunburst(tech_sub[tech_sub['Category']=='Device'], path=['Platform', 'Name'], values='Sessions')
                    st.plotly_chart(fig_dev, use_container_width=True)
                    st.caption("ℹ️ **Sunburst:** Breakdown of traffic volume. Inner circle = Platform, Outer circle = Device Type.")

                with col_t2:
                    st.subheader("OS Distribution")
                    fig_os = px.bar(tech_sub[tech_sub['Category']=='OS'], x="Sessions", y="Name", color="Platform", barmode="group", orientation='h')
                    st.plotly_chart(fig_os, use_container_width=True)
                    st.caption("ℹ️ **OS Stats:** Volume of sessions per Operating System. Helps prioritize testing (e.g., Windows vs iOS).")
            else:
                st.info("No technical detail data available for current selection.")

        # --- TAB 4: PAGES ---
        with tabs[3]:
            st.header("High Traffic Pages Analysis")
            pages_sub = df_pages[df_pages['Market'].isin(filtered_df['Market'])]
            
            if not pages_sub.empty:
                top_p = pages_sub.groupby(['Platform', 'URL'])['Visits'].sum().sort_values(ascending=False).head(20).reset_index()
                st.dataframe(top_p, use_container_width=True)
                st.caption("ℹ️ **Top Pages:** Most visited URLs in the dataset. Use this to correlate high friction days with specific landing pages.")
            else:
                st.info("No page data available.")
