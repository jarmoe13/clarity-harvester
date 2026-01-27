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
    page_title="🤖 AI-Ready Clarity Dashboard",
    page_icon="🤖",
    layout="wide"
)

# ==================== DATA ENGINE (LAST KNOWN STATE) ====================
def load_all_clarity_data():
    """
    Skanuje pliki JSON w folderze /data i buduje stan 'Last Known State'.
    """
    # Poprawiona ścieżka do folderu /data
    data_path = os.path.join("data", "clarity_*.json")
    all_files = glob.glob(data_path)
    
    if not all_files:
        # Fallback na główny katalog, jeśli skrypt jest uruchomiony inaczej
        all_files = glob.glob("clarity_*.json")
        
    global_state = {}
    
    # Sortujemy pliki, aby nowsze dane nadpisywały starsze
    for file in sorted(all_files):
        try:
            with open(file, 'r', encoding='utf-8') as f:
                day_data = json.load(f)
            for country, data in day_data.items():
                if country not in global_state:
                    global_state[country] = data
                else:
                    curr_ts = datetime.fromisoformat(global_state[country]['timestamp'].replace('Z', ''))
                    new_ts = datetime.fromisoformat(data['timestamp'].replace('Z', ''))
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

# ==================== ADVANCED METRICS ====================
def calculate_silent_killer_score(country_data):
    """
    Kluczowa metryka: (Dead Clicks % + Error Clicks %) * Waga Stron Transakcyjnych
    """
    pages = next((m['information'] for m in country_data['webshop'] if m['metricName'] == 'PopularPages'), [])
    # Słowa kluczowe wskazujące na dół lejka zakupowego
    tx_keywords = ['cart', 'checkout', 'pay', 'basket', 'login', 'wslogin', 'validate', 'validation']
    
    total_v = sum(int(p.get('visitsCount', 0)) for p in pages)
    if total_v == 0: return 0
    
    # Liczymy jak dużo ruchu odbywa się na stronach krytycznych
    tx_v = sum(int(p.get('visitsCount', 0)) for p in pages if any(kw in p['url'].lower() for kw in tx_keywords))
    tx_density = tx_v / total_v
    
    dead_info = get_metric_info(country_data, 'DeadClickCount')
    dead_p = float(dead_info.get('sessionsWithMetricPercentage', 0)) if dead_info else 0
    
    err_info = get_metric_info(country_data, 'ErrorClickCount')
    err_p = float(err_info.get('sessionsWithMetricPercentage', 0)) if err_info else 0
    
    # Wynik: Błędy podbite przez znaczenie biznesowe stron (tx_density)
    score = (dead_p * 0.7 + err_p * 0.3) * (1 + tx_density * 4)
    return round(min(score, 100), 2)

# ==================== MAIN DASHBOARD ====================
st.title("🤖 Clarity AI-Agent Command Center")
st.caption("Dane znormalizowane: Porównujemy intensywność problemów, a nie wolumen ruchu.")

data = load_all_clarity_data()

if data:
    stats = []
    for country, c_data in data.items():
        sk_score = calculate_silent_killer_score(c_data)
        dead_info = get_metric_info(c_data, 'DeadClickCount')
        sessions = int(dead_info.get('sessionsCount', 0)) if dead_info else 0
        
        # Pobieramy realny % frustracji zamiast sumy kliknięć (Normalizacja!)
        rage_info = get_metric_info(c_data, 'RageClickCount')
        rage_p = float(rage_info.get('sessionsWithMetricPercentage', 0)) if rage_info else 0
        
        stats.append({
            'Country': country,
            'Silent Killer Score': sk_score,
            'Rage Sessions %': rage_p,
            'Total Sessions': sessions,
            'Last Update': c_data['timestamp'][:10]
        })
    
    df = pd.DataFrame(stats)

    # --- KPI ROW ---
    c1, c2, c3 = st.columns(3)
    c1.metric("🌍 Countries in Archive", len(df))
    c2.metric("🔥 Top Risk Score", f"{df['Silent Killer Score'].max():.1f}")
    c3.metric("📅 Latest Data Source", df['Last Update'].max())

    st.divider()

    # --- WIZUALIZACJA: BUBBLE CHART (Znormalizowany) ---
    st.subheader("🎯 Risk Intensity Matrix")
    # Oś Y to teraz czysta intensywność błędu, niezależna od wielkości kraju
    fig_bubble = px.scatter(
        df, x="Total Sessions", y="Silent Killer Score",
        size="Rage Sessions %", color="Silent Killer Score",
        hover_name="Country", text="Country",
        color_continuous_scale="RdYlGn_r",
        title="Wysoko na osi Y = Poważne błędy w koszyku | Wielkość kropki = % wściekłych kliknięć"
    )
    st.plotly_chart(fig_bubble, use_container_width=True)

    # --- LISTA DLA AGENTA ---
    st.markdown("---")
    st.subheader("🚀 Wytyczne dla Agenta AI (TOP Priorytety)")
    
    # Sortujemy po Silent Killer Score - to są sesje do analizy wideo
    priority_df = df.sort_values('Silent Killer Score', ascending=False).head(5)
    
    for _, row in priority_df.iterrows():
        with st.expander(f"🔴 ANALIZA WYMAGANA: {row['Country']} (Score: {row['Silent Killer Score']})"):
            st.write(f"Ten kraj ma najwyższe ryzyko porzucenia koszyka.")
            st.write(f"- **Procent sesji z Rage Clicks:** {row['Rage Sessions %']}%")
            st.write(f"- **Ostatni odczyt:** {row['Last Update']}")
            st.button(f"Uruchom Agenta Vision dla {row['Country']}", key=f"btn_{row['Country']}")

else:
    st.warning("Nie znaleziono plików JSON w folderze /data. Sprawdź czy harvester poprawnie zapisał dane.")
