import streamlit as st
import pandas as pd
import json
import requests
from datetime import datetime, timedelta
import plotly.graph_objects as go
import plotly.express as px
from pathlib import Path
from io import StringIO

# ==================== PAGE CONFIG ====================
st.set_page_config(
    page_title="🚀 Clarity Analytics Dashboard",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ==================== DATA LOADING ====================
@st.cache_data(ttl=3600)
def load_clarity_data():
    """Load latest clarity data from GitHub"""
    try:
        repo_raw = "https://raw.githubusercontent.com/jarmoe13/clarity-harvester/main"
        today = datetime.now().strftime("%Y-%m-%d")
        url = f"{repo_raw}/data/clarity_{today}.json"
        
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            data = response.json()
            st.session_state['data_date'] = today
            return data
        else:
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

# ==================== SCORE CALCULATORS ====================
def calculate_frustration_index(country_data):
    """Calculate frustration score (0-100)"""
    if not country_data.get('webshop'):
        return None
    
    dead_clicks = float(get_metric_value(country_data, 'DeadClickCount', 'sessionsWithMetricPercentage') or 0)
    rage_clicks = float(get_metric_value(country_data, 'RageClickCount', 'sessionsWithMetricPercentage') or 0)
    script_errors = float(get_metric_value(country_data, 'ScriptErrorCount', 'sessionsWithMetricPercentage') or 0)
    error_clicks = float(get_metric_value(country_data, 'ErrorClickCount', 'sessionsWithMetricPercentage') or 0)
    quickback = float(get_metric_value(country_data, 'QuickbackClick', 'sessionsWithMetricPercentage') or 0)
    
    frustration = (
        (rage_clicks * 0.35) +
        (dead_clicks * 0.25) +
        (script_errors * 0.20) +
        (error_clicks * 0.15) +
        (quickback * 0.05)
    )
    
    return round(min(frustration, 100), 2)

def calculate_conversion_risk(country_data):
    """Calculate conversion risk score (0-100, higher = worse)"""
    if not country_data.get('webshop'):
        return None
    
    quickback = float(get_metric_value(country_data, 'QuickbackClick', 'sessionsWithMetricPercentage') or 0)
    dead_clicks = float(get_metric_value(country_data, 'DeadClickCount', 'sessionsWithMetricPercentage') or 0)
    error_clicks = float(get_metric_value(country_data, 'ErrorClickCount', 'sessionsWithMetricPercentage') or 0)
    scroll_depth = float(get_metric_value(country_data, 'ScrollDepth', 'averageScrollDepth') or 50)
    
    risk = (
        (quickback * 0.40) +
        (dead_clicks * 0.30) +
        (error_clicks * 0.20) +
        ((100 - scroll_depth) * 0.10)
    )
    
    return round(min(risk, 100), 2)

def calculate_tech_health(country_data):
    """Calculate tech health score (0-100, higher = better)"""
    if not country_data.get('webshop'):
        return None
    
    script_errors = float(get_metric_value(country_data, 'ScriptErrorCount', 'sessionsWithMetricPercentage') or 0)
    error_clicks = float(get_metric_value(country_data, 'ErrorClickCount', 'sessionsWithMetricPercentage') or 0)
    
    health = 100 - (
        (script_errors * 0.60) +
        (error_clicks * 0.40)
    )
    
    return round(max(health, 0), 2)

def calculate_engagement(country_data):
    """Calculate engagement score (0-100)"""
    if not country_data.get('webshop'):
        return None
    
    scroll_depth = float(get_metric_value(country_data, 'ScrollDepth', 'averageScrollDepth') or 0)
    rage_clicks = float(get_metric_value(country_data, 'RageClickCount', 'sessionsWithMetricPercentage') or 0)
    
    engagement = scroll_depth - (rage_clicks * 0.5)
    
    return round(max(engagement, 0), 2)

def calculate_localization_quality(country_data):
    """Calculate localization quality (0-100)"""
    if not country_data.get('webshop'):
        return None
    
    script_errors = float(get_metric_value(country_data, 'ScriptErrorCount', 'sessionsWithMetricPercentage') or 0)
    dead_clicks = float(get_metric_value(country_data, 'DeadClickCount', 'sessionsWithMetricPercentage') or 0)
    rage_clicks = float(get_metric_value(country_data, 'RageClickCount', 'sessionsWithMetricPercentage') or 0)
    
    quality = 100 - (
        (script_errors * 0.30) +
        (dead_clicks * 0.50) +
        (rage_clicks * 0.20)
    )
    
    return round(max(quality, 0), 2)

def get_level_emoji(score, reverse=False):
    """Get emoji for score level"""
    if reverse:
        if score >= 70:
            return "🔴 CRITICAL"
        elif score >= 40:
            return "🟠 HIGH"
        elif score >= 20:
            return "🟡 MEDIUM"
        else:
            return "🟢 GOOD"
    else:
        if score >= 80:
            return "🟢 EXCELLENT"
        elif score >= 60:
            return "🟡 GOOD"
        elif score >= 40:
            return "🟠 FAIR"
        else:
            return "🔴 POOR"

# ==================== MAIN APP ====================
st.markdown("""
    <h1 style="text-align: center; color: #1f77b4; margin-bottom: 30px;">
    🚀 Clarity Analytics Dashboard - Multi-Dimensional Analysis
    </h1>
""", unsafe_allow_html=True)

# Load data
with st.spinner("📊 Loading data..."):
    clarity_data = load_clarity_data()

if clarity_data:
    # ==================== HEADER ====================
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
    
    # ==================== TABS ====================
    tab1, tab2, tab3, tab4, tab5, tab6, tab7 = st.tabs([
        "😡 Frustration",
        "💰 Conversion Risk", 
        "🚨 Tech Health",
        "👥 Engagement",
        "🌐 Localization",
        "📊 Cohorts",
        "📈 Benchmarks"
    ])
    
    # ==================== TAB 1: FRUSTRATION ====================
    with tab1:
        st.header("😡 Frustration Index Analysis")
        
        st.info("""
        **CO MIERZYMY?** Ogólny poziom frustracji użytkowników na stronie.
        
        **KOMPONENTY (wagi):**
        - 🔴 **Rage Clicks** (35%) - użytkownik klika szybko wiele razy ze złości (brak kontroli)
        - 💀 **Dead Clicks** (25%) - kliki na elementy, które nic nie robią (zepsute UI)
        - ⚠️ **Script Errors** (20%) - błędy JavaScript (problemy techniczne)
        - ❌ **Error Clicks** (15%) - kliki na elementy wyrzucające błędy (złe logika)
        - ⚡ **Quickback** (5%) - użytkownik opuszcza natychmiast (źle pierwsze wrażenie)
        
        **INTERPREACJA SCORE (0-100):**
        - 🟢 0-20 = **ŚWIETNIE** - użytkownicy zadowoleni
        - 🟡 20-40 = **OK** - kilka problemów
        - 🟠 40-70 = **ŹLE** - znaczące problemy UX
        - 🔴 70+ = **KRYTYCZNIE** - konieczna natychmiastowa akcja
        """)
        
        frustration_data = []
        for country in clarity_data.keys():
            if clarity_data[country].get('webshop'):
                score = calculate_frustration_index(clarity_data[country])
                if score is not None:
                    frustration_data.append({
                        'Country': country,
                        'Frustration': score,
                        'Level': get_level_emoji(score, reverse=True)
                    })
        
        frustration_df = pd.DataFrame(frustration_data).sort_values('Frustration', ascending=False)
        
        col1, col2 = st.columns(2)
        
        with col1:
            fig = px.bar(
                frustration_df,
                x='Frustration',
                y='Country',
                orientation='h',
                color='Frustration',
                color_continuous_scale='RdYlGn_r',
                title="Frustration by Country"
            )
            st.plotly_chart(fig, use_container_width=True)
        
        with col2:
            st.subheader("🏆 Top Issues")
            for idx, row in frustration_df.head(5).iterrows():
                st.markdown(f"**{row['Country']}** - {row['Frustration']:.1f} {row['Level']}")
        
        st.divider()
        st.subheader("📊 Component Breakdown (All Countries)")
        
        components_data = []
        for country in clarity_data.keys():
            if clarity_data[country].get('webshop'):
                rage = float(get_metric_value(clarity_data[country], 'RageClickCount', 'sessionsWithMetricPercentage') or 0)
                dead = float(get_metric_value(clarity_data[country], 'DeadClickCount', 'sessionsWithMetricPercentage') or 0)
                errors = float(get_metric_value(clarity_data[country], 'ScriptErrorCount', 'sessionsWithMetricPercentage') or 0)
                error_clicks = float(get_metric_value(clarity_data[country], 'ErrorClickCount', 'sessionsWithMetricPercentage') or 0)
                quickback = float(get_metric_value(clarity_data[country], 'QuickbackClick', 'sessionsWithMetricPercentage') or 0)
                
                for comp, val in [('Rage Clicks', rage), ('Dead Clicks', dead), ('Script Errors', errors), ('Error Clicks', error_clicks), ('Quickback', quickback)]:
                    components_data.append({'Country': country, 'Component': comp, 'Value': val})
        
        comp_df = pd.DataFrame(components_data)
        pivot_comp = comp_df.pivot(index='Country', columns='Component', values='Value')
        
        fig = go.Figure(data=go.Heatmap(
            z=pivot_comp.values,
            x=pivot_comp.columns,
            y=pivot_comp.index,
            colorscale='RdYlGn_r'
        ))
        fig.update_layout(title="Frustration Components Heatmap", height=400)
        st.plotly_chart(fig, use_container_width=True)
        
        st.dataframe(frustration_df, use_container_width=True)
    
    # ==================== TAB 2: CONVERSION RISK ====================
    with tab2:
        st.header("💰 Conversion Risk Analysis")
        
        st.info("""
        **CO MIERZYMY?** Ryzyko, że użytkownik NIE dokończy konwersji (zakup, signup, itp).
        
        **KOMPONENTY (wagi):**
        - ⚡ **Quickback** (40%) - opuszcza natychmiast = nie interesuje go zawartość
        - 💀 **Dead Clicks** (30%) - kliki na nic = frustracja, najpewniej wyjście
        - ❌ **Error Clicks** (20%) - błędy podczas interakcji = przeszkody w konwersji
        - 📄 **Low Scroll Depth** (10%) - nie czyta zawartości = brak zainteresowania
        
        **INTERPREACJA SCORE (0-100, WYŻSZY = GORSZY):**
        - 🟢 0-20 = **ŚWIETNIE** - wysokie szanse konwersji
        - 🟡 20-40 = **OK** - zmienność konwersji
        - 🟠 40-70 = **RYZYKO** - znaczna strata konwersji
        - 🔴 70+ = **KRYTYCZNE** - prawie wszyscy odchodzą
        
        **AKCJA:** Jaki % Users porzucił stronę bez konwersji?
        """)
        
        risk_data = []
        for country in clarity_data.keys():
            if clarity_data[country].get('webshop'):
                score = calculate_conversion_risk(clarity_data[country])
                if score is not None:
                    risk_data.append({
                        'Country': country,
                        'Risk': score,
                        'Level': get_level_emoji(score, reverse=True)
                    })
        
        risk_df = pd.DataFrame(risk_data).sort_values('Risk', ascending=False)
        
        col1, col2 = st.columns(2)
        
        with col1:
            fig = px.bar(
                risk_df,
                x='Risk',
                y='Country',
                orientation='h',
                color='Risk',
                color_continuous_scale='RdYlGn_r',
                title="Conversion Risk by Country"
            )
            st.plotly_chart(fig, use_container_width=True)
        
        with col2:
            st.subheader("⚠️ Highest Risk Countries")
            for idx, row in risk_df.head(5).iterrows():
                st.markdown(f"**{row['Country']}** - Risk: {row['Risk']:.1f} {row['Level']}")
        
        st.divider()
        st.subheader("📊 Risk Drivers")
        
        risk_components = []
        for country in clarity_data.keys():
            if clarity_data[country].get('webshop'):
                quickback = float(get_metric_value(clarity_data[country], 'QuickbackClick', 'sessionsWithMetricPercentage') or 0)
                dead = float(get_metric_value(clarity_data[country], 'DeadClickCount', 'sessionsWithMetricPercentage') or 0)
                error_clicks = float(get_metric_value(clarity_data[country], 'ErrorClickCount', 'sessionsWithMetricPercentage') or 0)
                scroll = float(get_metric_value(clarity_data[country], 'ScrollDepth', 'averageScrollDepth') or 50)
                
                for comp, val in [('Quickback', quickback), ('Dead Clicks', dead), ('Error Clicks', error_clicks), ('Low Scroll Depth', 100-scroll)]:
                    risk_components.append({'Country': country, 'Driver': comp, 'Value': val})
        
        risk_comp_df = pd.DataFrame(risk_components)
        pivot_risk = risk_comp_df.pivot(index='Country', columns='Driver', values='Value')
        
        fig = go.Figure(data=go.Heatmap(
            z=pivot_risk.values,
            x=pivot_risk.columns,
            y=pivot_risk.index,
            colorscale='RdYlGn_r'
        ))
        fig.update_layout(title="Risk Drivers Heatmap", height=400)
        st.plotly_chart(fig, use_container_width=True)
        
        st.dataframe(risk_df, use_container_width=True)
    
    # ==================== TAB 3: TECH HEALTH ====================
    with tab3:
        st.header("🚨 Technical Health Score")
        
        st.info("""
        **CO MIERZYMY?** Czy technologia strony działa poprawnie (bez błędów).
        
        **KOMPONENTY (wagi):**
        - ⚠️ **Script Errors** (60%) - błędy JavaScript = breaking functionality
        - ❌ **Error Clicks** (40%) - kliki na elementy z błędami = buggy code
        
        **INTERPREACJA SCORE (0-100, WYŻSZY = LEPSZY):**
        - 🟢 80-100 = **EXCELLENT** - prawie zero błędów, stabilny
        - 🟡 60-80 = **GOOD** - kilka błędów, ale system stabilny
        - 🟠 40-60 = **FAIR** - regularne błędy, problemy z user experience
        - 🔴 0-40 = **POOR** - duże problemy techniczne, strona prawie nie działa
        
        **AKCJA:** Jaki % sesji napotkało błędy techniczne?
        """)
        
        health_data = []
        for country in clarity_data.keys():
            if clarity_data[country].get('webshop'):
                score = calculate_tech_health(clarity_data[country])
                if score is not None:
                    health_data.append({
                        'Country': country,
                        'Health': score,
                        'Level': get_level_emoji(score, reverse=False)
                    })
        
        health_df = pd.DataFrame(health_data).sort_values('Health', ascending=True)
        
        col1, col2 = st.columns(2)
        
        with col1:
            fig = px.bar(
                health_df,
                x='Health',
                y='Country',
                orientation='h',
                color='Health',
                color_continuous_scale='RdYlGn',
                title="Tech Health by Country"
            )
            st.plotly_chart(fig, use_container_width=True)
        
        with col2:
            st.subheader("🔴 Most Critical")
            for idx, row in health_df.head(5).iterrows():
                st.markdown(f"**{row['Country']}** - Health: {row['Health']:.1f} {row['Level']}")
        
        st.divider()
        st.subheader("🛠️ Tech Issues Breakdown")
        
        tech_issues = []
        for country in clarity_data.keys():
            if clarity_data[country].get('webshop'):
                script_err = float(get_metric_value(clarity_data[country], 'ScriptErrorCount', 'sessionsWithMetricPercentage') or 0)
                error_clicks = float(get_metric_value(clarity_data[country], 'ErrorClickCount', 'sessionsWithMetricPercentage') or 0)
                
                for issue, val in [('Script Errors %', script_err), ('Error Clicks %', error_clicks)]:
                    tech_issues.append({'Country': country, 'Issue': issue, 'Value': val})
        
        tech_df = pd.DataFrame(tech_issues)
        pivot_tech = tech_df.pivot(index='Country', columns='Issue', values='Value')
        
        fig = go.Figure(data=go.Heatmap(
            z=pivot_tech.values,
            x=pivot_tech.columns,
            y=pivot_tech.index,
            colorscale='RdYlGn_r'
        ))
        fig.update_layout(title="Technical Issues Heatmap", height=300)
        st.plotly_chart(fig, use_container_width=True)
        
        st.dataframe(health_df, use_container_width=True)
    
    # ==================== TAB 4: ENGAGEMENT ====================
    with tab4:
        st.header("👥 User Engagement Score")
        
        st.info("""
        **CO MIERZYMY?** Jak głęboko i pozytywnie użytkownicy interaktują ze stroną.
        
        **KOMPONENTY:**
        - 📜 **Scroll Depth** (70%) - jak daleko użytkownik czyta (high = zainteresowany)
        - 😡 **No Rage Clicks** (30%) - brak złości = spokojne klikanie (Good UX)
        
        **INTERPREACJA SCORE (0-100, WYŻSZY = LEPSZY):**
        - 🟢 80-100 = **EXCELLENT** - użytkownicy czytają, nie złoszczą się
        - 🟡 60-80 = **GOOD** - przyzwoite zaangażowanie
        - 🟠 40-60 = **FAIR** - nikłe zainteresowanie
        - 🔴 0-40 = **POOR** - użytkownicy nie interaktują
        
        **AKCJA:** Użytkownicy są zainteresowani? Czytają do końca?
        """)
        
        engagement_data = []
        for country in clarity_data.keys():
            if clarity_data[country].get('webshop'):
                score = calculate_engagement(clarity_data[country])
                if score is not None:
                    engagement_data.append({
                        'Country': country,
                        'Engagement': score,
                        'Level': get_level_emoji(score, reverse=False)
                    })
        
        eng_df = pd.DataFrame(engagement_data).sort_values('Engagement', ascending=False)
        
        col1, col2 = st.columns(2)
        
        with col1:
            fig = px.bar(
                eng_df,
                x='Engagement',
                y='Country',
                orientation='h',
                color='Engagement',
                color_continuous_scale='RdYlGn',
                title="Engagement Score by Country"
            )
            st.plotly_chart(fig, use_container_width=True)
        
        with col2:
            st.subheader("⭐ Top Engaged")
            for idx, row in eng_df.head(5).iterrows():
                st.markdown(f"**{row['Country']}** - Score: {row['Engagement']:.1f} {row['Level']}")
        
        st.divider()
        st.subheader("📈 Engagement Components")
        
        eng_components = []
        for country in clarity_data.keys():
            if clarity_data[country].get('webshop'):
                scroll = float(get_metric_value(clarity_data[country], 'ScrollDepth', 'averageScrollDepth') or 0)
                rage = float(get_metric_value(clarity_data[country], 'RageClickCount', 'sessionsWithMetricPercentage') or 0)
                
                for comp, val in [('Scroll Depth %', scroll), ('Rage Clicks (Inverted)', 100-rage)]:
                    eng_components.append({'Country': country, 'Component': comp, 'Value': val})
        
        eng_comp_df = pd.DataFrame(eng_components)
        pivot_eng = eng_comp_df.pivot(index='Country', columns='Component', values='Value')
        
        fig = go.Figure(data=go.Heatmap(
            z=pivot_eng.values,
            x=pivot_eng.columns,
            y=pivot_eng.index,
            colorscale='RdYlGn'
        ))
        fig.update_layout(title="Engagement Drivers Heatmap", height=300)
        st.plotly_chart(fig, use_container_width=True)
        
        st.dataframe(eng_df, use_container_width=True)
    
    # ==================== TAB 5: LOCALIZATION ====================
    with tab5:
        st.header("🌐 Localization Quality Score")
        
        st.info("""
        **CO MIERZYMY?** Jak dobrze strona jest przystosowana do konkretnego kraju (UX + Tech).
        
        **KOMPONENTY (wagi):**
        - ⚠️ **Script Errors** (30%) - błędy tech w localizacji (zepsute tłumaczenia? broken API calls?)
        - 💀 **Dead Clicks** (50%) - przyciskina do nic = złe UI dla konkretnego kraju
        - 🔴 **Rage Clicks** (20%) - frustacja specyficzna dla localizacji
        
        **INTERPREACJA SCORE (0-100, WYŻSZY = LEPSZY):**
        - 🟢 80-100 = **EXCELLENT** - idealna localizacja
        - 🟡 60-80 = **GOOD** - przyzwoita adaptacja
        - 🟠 40-60 = **FAIR** - problemy z adaptacją
        - 🔴 0-40 = **POOR** - localizacja nie działa
        
        **AKCJA:** Które kraje mają problem z lokalizacją? Gdzie trzeba dostosować?
        """)
        
        local_data = []
        for country in clarity_data.keys():
            if clarity_data[country].get('webshop'):
                score = calculate_localization_quality(clarity_data[country])
                if score is not None:
                    local_data.append({
                        'Country': country,
                        'Quality': score,
                        'Level': get_level_emoji(score, reverse=False)
                    })
        
        local_df = pd.DataFrame(local_data).sort_values('Quality', ascending=False)
        
        col1, col2 = st.columns(2)
        
        with col1:
            fig = px.bar(
                local_df,
                x='Quality',
                y='Country',
                orientation='h',
                color='Quality',
                color_continuous_scale='RdYlGn',
                title="Localization Quality by Country"
            )
            st.plotly_chart(fig, use_container_width=True)
        
        with col2:
            st.subheader("✅ Best Localized")
            for idx, row in local_df.head(5).iterrows():
                st.markdown(f"**{row['Country']}** - Quality: {row['Quality']:.1f} {row['Level']}")
        
        st.divider()
        st.subheader("🎯 Localization Issues")
        
        local_issues = []
        for country in clarity_data.keys():
            if clarity_data[country].get('webshop'):
                script_err = float(get_metric_value(clarity_data[country], 'ScriptErrorCount', 'sessionsWithMetricPercentage') or 0)
                dead = float(get_metric_value(clarity_data[country], 'DeadClickCount', 'sessionsWithMetricPercentage') or 0)
                rage = float(get_metric_value(clarity_data[country], 'RageClickCount', 'sessionsWithMetricPercentage') or 0)
                
                for issue, val in [('Script Errors', script_err), ('Dead Clicks (UX)', dead), ('Rage Clicks (Frustration)', rage)]:
                    local_issues.append({'Country': country, 'Issue': issue, 'Value': val})
        
        local_issue_df = pd.DataFrame(local_issues)
        pivot_local = local_issue_df.pivot(index='Country', columns='Issue', values='Value')
        
        fig = go.Figure(data=go.Heatmap(
            z=pivot_local.values,
            x=pivot_local.columns,
            y=pivot_local.index,
            colorscale='RdYlGn_r'
        ))
        fig.update_layout(title="Localization Issues Heatmap", height=400)
        st.plotly_chart(fig, use_container_width=True)
        
        st.dataframe(local_df, use_container_width=True)
    
    # ==================== TAB 6: COHORTS ====================
    with tab6:
        st.header("👥 Browser Cohort Analysis")
        
        st.info("""
        **CO MIERZYMY?** Jak frustracja różni się między przeglądarkami.
        
        **KOMPONENTY:**
        - 🌐 Porównanie frustacji średniej w każdej przeglądarce
        - 📊 Dystrybucja użytkowników (Chrome, Safari, Firefox, itp.)
        
        **INTERPREACJA:**
        - Która przeglądarka ma najwyższe problemy?
        - Czy Safari/Chrome/Firefox mają różne User Experience?
        - Czy trzeba optymalizować dla konkretnej przeglądarki?
        
        **AKCJA:** Gdzie inwestować - w Chrome optimization czy iOS Safari?
        """)
        
        st.info("🔍 Analyzing user frustration by browser type across all countries")
        
        cohort_data = []
        for country in clarity_data.keys():
            if clarity_data[country].get('webshop'):
                browsers = get_top_items(clarity_data[country], 'Browser', limit=10)
                frustration = calculate_frustration_index(clarity_data[country])
                
                for browser in browsers:
                    cohort_data.append({
                        'Country': country,
                        'Browser': browser.get('name', 'Unknown'),
                        'Sessions': int(browser.get('sessionsCount', 0)),
                        'Country_Frustration': frustration
                    })
        
        cohort_df = pd.DataFrame(cohort_data)
        
        # Browser frustration (proxy: sessions weighted by country frustration)
        browser_agg = cohort_df.groupby('Browser').agg({
            'Sessions': 'sum',
            'Country_Frustration': 'mean'
        }).sort_values('Country_Frustration', ascending=False).head(10)
        
        fig = px.bar(
            x=browser_agg.index,
            y=browser_agg['Country_Frustration'],
            title="Average Frustration by Browser",
            labels={'y': 'Avg Frustration', 'index': 'Browser'}
        )
        st.plotly_chart(fig, use_container_width=True)
        
        st.subheader("📊 Top Browsers by Sessions")
        browser_sessions = cohort_df.groupby('Browser')['Sessions'].sum().sort_values(ascending=False).head(10)
        
        fig = px.pie(
            values=browser_sessions.values,
            names=browser_sessions.index,
            title="Browser Distribution (All Countries)"
        )
        st.plotly_chart(fig, use_container_width=True)
    
    # ==================== TAB 7: BENCHMARKS ====================
    with tab7:
        st.header("📈 Country Benchmarking")
        
        st.info("""
        **CO MIERZYMY?** Kompletne porównanie WSZYSTKICH krajów na WSZYSTKICH wymiarach jednocześnie.
        
        **5 WYMIARÓW:**
        - 😡 **Frustration** - ogólna frustracja użytkowników
        - 💰 **Risk** - ryzyko utraty konwersji
        - 🚨 **Tech Health** - czy strona działa technicznie
        - 👥 **Engagement** - jak głębokie interakcje
        - 🌐 **Quality** - jak dobrze localized
        
        **RADAR CHART:**
        - Każdy kraj = jeden profil 5-wymiarowy
        - Idealne = duży, równomierny pentagon
        - Zagrożony = małe obszary (wskazuje słabości)
        
        **AKCJA:** Która kombinacja krajów jest najbardziej/najmniej przystosowana?
        """)
        
        st.info("📊 Compare all metrics at once - each country shown on all dimensions")
        
        benchmark_data = []
        for country in clarity_data.keys():
            if clarity_data[country].get('webshop'):
                frustration = calculate_frustration_index(clarity_data[country]) or 0
                risk = calculate_conversion_risk(clarity_data[country]) or 0
                health = calculate_tech_health(clarity_data[country]) or 0
                engagement = calculate_engagement(clarity_data[country]) or 0
                quality = calculate_localization_quality(clarity_data[country]) or 0
                
                benchmark_data.append({
                    'Country': country,
                    '😡 Frustration': frustration,
                    '💰 Risk': risk,
                    '🚨 Tech Health': health,
                    '👥 Engagement': engagement,
                    '🌐 Quality': quality
                })
        
        benchmark_df = pd.DataFrame(benchmark_data).set_index('Country')
        
        # Radar chart
        fig = go.Figure()
        
        for country in benchmark_df.index:
            fig.add_trace(go.Scatterpolar(
                r=benchmark_df.loc[country].values,
                theta=benchmark_df.columns,
                fill='toself',
                name=country
            ))
        
        fig.update_layout(
            polar=dict(radialaxis=dict(visible=True, range=[0, 100])),
            title="Multi-Dimensional Country Benchmark",
            height=500
        )
        st.plotly_chart(fig, use_container_width=True)
        
        st.subheader("📊 Detailed Benchmark Table")
        st.dataframe(benchmark_df, use_container_width=True)

else:
    st.error("❌ Failed to load data. Please check back later.")

# ==================== FOOTER ====================
st.divider()
col1, col2, col3 = st.columns(3)
with col1:
    st.caption("🚀 Powered by Clarity API")
with col2:
    st.caption("📊 7-Dimensional Analysis")
with col3:
    st.caption("🔄 Auto-updates daily at 05:00 UTC")
