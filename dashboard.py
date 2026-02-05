import streamlit as st
import pandas as pd
import json
import os
import glob
from datetime import datetime
import plotly.express as px

# ==================== PAGE CONFIG ====================
st.set_page_config(
    page_title="Executive UX Command Center v2.1",
    page_icon="🛡️",
    layout="wide"
)

# ==================== DATA ENGINE ====================
@st.cache_data
def load_consolidated_data():
    """Konsoliduje dane i zabezpiecza przed brakiem plików."""
    # Szukaj plików w głównej ścieżce lub w folderze 'data'
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
                # Obsługa formatu timestampu
                ts_str = c_data['timestamp'].replace('Z', '')
                ts = pd.to_datetime(ts_str)
                date_only = ts.date()
                
                # Bezpieczne wyciąganie metryk do słownika
                m_dict = {m['metricName']: m['information'][0] for m in c_data.get('webshop', []) if m.get('information')}
                
                # Główny wiersz danych
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

                # Dane o stronach i technologii (pozostałe pętle bez zmian...)
                for m in c_data.get('webshop', []):
                    if m['metricName'] == 'PopularPages':
                        for p in m['information']:
                            page_details.append({'Date': date_only, 'Country': country, 'URL': p['url'], 'Visits': int(p['visitsCount'])})
                    if m['metricName'] in ['Browser', 'Device', 'OS']:
                        for t in m['information']:
                            tech_details.append({'Date': date_only, 'Country': country, 'Category': m['metricName'], 'Name': t['name'], 'Sessions': int(t['sessionsCount'])})
                            
        except Exception as e:
            continue

    return pd.DataFrame(historical_rows), pd.DataFrame(page_details), pd.DataFrame(tech_details)

# --- INICJALIZACJA DANYCH ---
df_main, df_pages, df_tech = load_consolidated_data()

# --- SPRAWDZENIE CZY DANE ISTNIEJĄ ---
if df_main.empty:
    st.error("🚨 Nie znaleziono plików danych! Upewnij się, że pliki .json znajdują się w tym samym folderze co skrypt lub w folderze 'data/'.")
    st.info("Oczekiwany format plików: `clarity_RRRR-MM-DD.json`")
    st.stop() # Zatrzymaj renderowanie reszty strony

# --- OBLICZENIA (Teraz bezpieczne) ---
df_main['Friction_Score'] = (df_main['DeadClicks_Pct'] * 0.7) + (df_main['RageClicks_Pct'] * 0.3)

# ==================== APP LAYOUT ====================
st.title("🛡️ Executive UX Command Center")
st.caption(f"Załadowano dane z {len(df_main['Date'].unique())} dni dla {len(df_main['Country'].unique())} rynków.")

# Sidebar - Filtry
st.sidebar.header("Ustawienia")
all_countries = sorted(df_main['Country'].unique())
selected_countries = st.sidebar.multiselect("Wybierz rynki", all_countries, default=all_countries[:3])

# Logika Dashboardu (Trendy, Wykresy, Tabele) - tutaj wstaw resztę kodu wizualizacji z poprzedniej odpowiedzi...
# ...
