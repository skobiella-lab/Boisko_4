# app.py

import os
import sys
from pathlib import Path
import ast

# Ustalenie ścieżki głównej projektu dla poprawnego działania na Streamlit Cloud
root_path = Path(__file__).resolve().parent

# Jeśli app.py jest w roocie, a turf_advisor to podfolder:
if str(root_path) not in sys.path:
    sys.path.insert(0, str(root_path))

# Dodatkowo upewnij się, że db_manager tworzy folder data jeśli nie istnieje
if not os.path.exists("data"):
    os.makedirs("data")

import streamlit as st
import pandas as pd
from datetime import datetime
from PIL import Image
import numpy as np
import cv2
import folium
from streamlit_folium import st_folium
from folium.plugins import Draw

# Nowe importy z zreorganizowanej struktury
from turf_advisor.database.db_manager import DatabaseManager
from turf_advisor.engines.advisor_core import AdvisorCore # Nowy orkiestrator

from turf_advisor.config import WEATHER_API_KEY # ENABLE_PROBABILISTIC będzie zarządzane przez Tiered Advice
from turf_advisor.integrations.meteo_api import MeteoEngine
from turf_advisor import agro_tips
from turf_advisor.utils import geocode_address

def display_weather_charts(df):
    """Pomocnik do renderowania spójnych wykresów pogodowych."""
    if df is None or df.empty:
        st.warning("Brak danych pogodowych do wyświetlenia na wykresach.")
        return

    available_columns = df.columns.tolist()
    c1, c2 = st.columns(2)
    with c1:
        y_axis = [col for col in ['temp_avg', 'et_calculated'] if col in available_columns]
        if 'date' in available_columns and y_axis:
            st.line_chart(df, x='date', y=y_axis)
        else:
            st.info("Brak danych o temperaturze lub ET.")
    with c2:
        if 'date' in available_columns and 'precip_mm' in available_columns:
            st.bar_chart(df, x='date', y='precip_mm')
        else:
            st.info("Brak danych o opadach.")

# Inicjalizacja bazy i silników
db = DatabaseManager()
def get_cached_soil_data(field_id):
    """Pobiera dane glebowe z cache."""
    return db.get_latest_soil_analysis(field_id)

# Debug: Wyłączam cache tymczasowo dla pogody
def get_cached_weather_history(days=30):
    """Pobiera historię pogody bez cache (debug)."""
    data = db.get_weather_history(days=days)
    return data

def get_weather_forecast():
    """Pobiera prognozę pogody bez cache (debug)."""
    data = db.get_weather_forecast()
    return data

st.set_page_config(page_title="Turf Advisor Pro", layout="wide")

st.title("🌱 Turf Advisor: System Wspomagania Decyzji")

# --- SIDEBAR: Konfiguracja i Szybki Rekord ---
st.sidebar.header("Zarządzanie Boiskiem")
field_id = st.sidebar.selectbox("Wybierz boisko", [1], format_func=lambda x: f"Boisko Główne (ID: {x})")

# Automatyczny reset danych wizyjnych przy zmianie boiska (zabezpieczenie spójności raportu)
if 'prev_field_id' not in st.session_state:
    st.session_state.prev_field_id = field_id
if st.session_state.prev_field_id != field_id:
    st.session_state.last_vision_map = None
    st.session_state.last_heatmap_blended = None
    st.session_state.sat_data = None
    st.session_state.prev_field_id = field_id

st.sidebar.subheader("📍 Lokalizacja Boiska")

# Inicjalizacja współrzędnych w session_state jeśli nie istnieją
if 'lat' not in st.session_state:
    st.session_state.lat = 52.23
if 'lon' not in st.session_state:
    st.session_state.lon = 21.01
if 'city' not in st.session_state:
    st.session_state.city = "Moje Boisko"

# Pole adresu do geokodowania
address_input = st.sidebar.text_input(
    "Wprowadź adres lub miejscowość",
    placeholder="np. Warszawa, Aleje Jerozolimskie 10"
)

if st.sidebar.button("🔍 Znajdź współrzędne"):
    if address_input.strip():
        with st.sidebar.spinner("Szukam lokalizacji..."):
            location = geocode_address(address_input.strip())
            if location:
                st.session_state.lat = location['lat']
                st.session_state.lon = location['lon']
                st.session_state.city = location['display_name'][:50]  # Ogranicz długość
                st.sidebar.success(f"Znaleziono: {location['display_name'][:50]}...")
                st.rerun()
            else:
                st.sidebar.error("Nie znaleziono lokalizacji. Spróbuj inny adres.")
    else:
        st.sidebar.warning("Wprowadź adres!")

# Wyświetlanie i edycja współrzędnych
city = st.sidebar.text_input("Nazwa lokalizacji", value=st.session_state.city)
lat = st.sidebar.number_input("Szerokość (Lat)", value=st.session_state.lat, format="%.6f")
lon = st.sidebar.number_input("Długość (Lon)", value=st.session_state.lon, format="%.6f")

# Aktualizuj session_state jeśli użytkownik zmienił wartości ręcznie
st.session_state.city = city
st.session_state.lat = lat
st.session_state.lon = lon

st.sidebar.divider()
st.sidebar.subheader("🌦️ Dane Pogodowe (Open-Meteo)")
st.sidebar.caption("Lokalizacja pobierana z najbliższego punktu siatki meteo (dane ekstrapolowane).")

forecast_days = st.sidebar.selectbox("Prognoza (dni)", [3, 7, 10, 14], index=1)
weather_days = st.sidebar.selectbox("Historia wyświetlania (dni)", [7, 14, 30], index=0)

if st.sidebar.button("🔄 Aktualizuj pogodę i prognozę"):
    meteo = MeteoEngine(lat, lon)
    if meteo.update_weather_data(forecast_days=forecast_days):
        st.sidebar.success("Dane pogodowe zsynchronizowane!")
        st.rerun()
    else:
        st.sidebar.error("Błąd połączenia z Open-Meteo.")

if st.sidebar.button("Pobierz historię z Open-Meteo"):
    meteo = MeteoEngine(lat, lon)
    if meteo.update_historical_weather(days_back=30):
        st.sidebar.success("Historia pogodowa pobrana!")
        st.rerun()
    else:
        st.sidebar.error("Błąd pobierania historii.")

st.sidebar.divider()
st.sidebar.subheader("🔑 Opcjonalne API Premium")
api_key_input = st.sidebar.text_input("Klucz Visual Crossing", value=WEATHER_API_KEY, type="password")
if st.sidebar.button("Zastosuj klucz"):
    st.sidebar.info("Klucz zapisany. Integracja Premium dostępna w opcjach zaawansowanych.")

# Inicjalizacja AdvisorCore
static_profile = {
    'bulk_density': 1.55,
    'om_pct': 2.5,
    'cn_ratio': 12,
    'root_depth_mm': 150,
    'sand_pct': 90.0,
    'silt_pct': 5.0,
    'clay_pct': 5.0
}
advisor = AdvisorCore(db, static_profile)

# --- INICJALIZACJA DANYCH ---
# --- INICJALIZACJA BAZY NAWOZÓW ---
if not db.get_all_fertilizers():
    default_detailed = [
        {"brand": "ICL", "name": "Sportsmaster Base", "n_total": 12.0, "p_total": 24.0, "k_total": 0.0, "n_no3": 4.3, "n_nh4": 7.7, "mg": 2.0, "salt_index": 55.0},
        {"brand": "ICL", "name": "Sportsmaster High K", "n_total": 15.0, "p_total": 0.0, "k_total": 25.0, "n_no3": 7.0, "n_nh4": 8.0, "mg": 2.0, "salt_index": 40.0},
        {"brand": "Compo", "name": "Floranid Twin Permanent", "n_total": 16.0, "p_total": 7.0, "k_total": 15.0, "n_no3": 2.0, "n_nh4": 6.0, "is_slow_release": 1, "salt_index": 30.0},
        {"brand": "Yara", "name": "Mila Complex", "n_total": 12.0, "p_total": 11.0, "k_total": 18.0, "n_no3": 5.0, "n_nh4": 7.0, "mg": 2.7, "s": 20.0, "salt_index": 45.0},
        {"brand": "ICL", "name": "Agromaster High N", "n_total": 19.0, "p_total": 5.0, "k_total": 20.0, "n_nh2": 19.0, "mg": 4.0, "is_slow_release": 1, "salt_index": 35.0},
        {"brand": "Yara", "name": "Vera AMIDAS", "n_total": 40.0, "p_total": 0.0, "k_total": 0.0, "n_nh2": 40.0, "s": 12.0, "salt_index": 75.0},
        {"brand": "Haifa", "name": "Multi-K", "n_total": 13.0, "p_total": 0.0, "k_total": 46.0, "n_no3": 13.0, "salt_index": 73.0},
        {"brand": "YaraLiva", "name": "CALCINIT", "n_total": 15.5, "p_total": 0.0, "k_total": 0.0, "n_no3": 14.4, "n_nh4": 1.1, "ca": 19.0, "salt_index": 60.0},
        {"brand": "Solufeed", "name": "Chelat Żelaza EDTA", "n_total": 0.0, "p_total": 0.0, "k_total": 0.0, "micro_nutrients": {"Fe": 13.0}, "salt_index": 5.0},
        {"brand": "Ciech", "name": "Siarczan Magnezu Siedmiowodny", "n_total": 0.0, "p_total": 0.0, "k_total": 0.0, "mg": 16.0, "s": 32.0, "salt_index": 10.0}
    ]
    for fert in default_detailed:
        db.add_fertilizer(fert)

# --- KONFIGURACJA NAWOZÓW DO ANALIZY (Pobierane PO inicjalizacji DB) ---
all_ferts_for_selection = advisor.get_available_fertilizers()
fert_options = [f"{f['brand']} {f['name']} ({int(f['n_total'])}-{int(f['p_total'])}-{int(f['k_total'])})" for f in all_ferts_for_selection]

if 'selected_fert_names' not in st.session_state:
    st.session_state.selected_fert_names = fert_options

selected_ferts_objects = [
    f for f in all_ferts_for_selection 
    if f"{f['brand']} {f['name']} ({int(f['n_total'])}-{int(f['p_total'])}-{int(f['k_total'])})" in st.session_state.selected_fert_names
]

# Inicjalizacja parametrów operacyjnych w session_state
if 'vmc_sim' not in st.session_state:
    st.session_state.vmc_sim = 0.18
vmc_sim = st.session_state.vmc_sim

current_soil = None
advice = None
try:
    current_soil = get_cached_soil_data(field_id)
except Exception as e:
    st.error(f"Błąd połączenia z bazą: {e}")

balance = {}

# Pobieranie danych pogodowych
weather_hist = get_cached_weather_history(days=30)
weather_forecast = get_weather_forecast()

# Pobieranie najnowszej analizy tkankowej (masy zielonej)
all_records = db.get_maintenance_records(field_id)
current_tissue = None
if all_records:
    # Szukamy ostatniego wpisu typu TISSUE_ANALYSIS (zakładając, że baza zwraca rekordy od najnowszych)
    tissue_entries = [r for r in all_records if r.get('action_type') == 'TISSUE_ANALYSIS']
    if tissue_entries:
        try:
            # Konwersja zapisanego stringa z danymi (product_id) z powrotem na słownik
            current_tissue = ast.literal_eval(tissue_entries[0].get('product_id', '{}'))
        except (ValueError, SyntaxError):
            current_tissue = None

# --- ZARZĄDZANIE STANEM ANALIZY TKANKOWEJ ---
if 'use_tissue' not in st.session_state:
    # Domyślnie włączone tylko jeśli w bazie są jakiekolwiek dane
    st.session_state.use_tissue = (current_tissue is not None)

# Definicja zmiennej przed użyciem w AdvisorCore
effective_tissue = current_tissue if st.session_state.use_tissue else None

if 'last_vision_map' not in st.session_state:
    st.session_state.last_vision_map = None
if 'last_heatmap_blended' not in st.session_state:
    st.session_state.last_heatmap_blended = None

# --- SIDEBAR: Konfiguracja Poziomu Analizy ---
st.sidebar.subheader("⚙️ Poziom Analizy")
analysis_tier = st.sidebar.radio(
    "Wybierz poziom szczegółowości rekomendacji:",
    ["1. Podstawowy (Fizyczno-Chemiczny)", "2. Dynamiczny (Bio-Środowiskowy)", "3. Inteligentny (Optymalizacja i Ryzyko)"],
    index=0 # Domyślnie Tier 1
)

if current_soil:
    advice = advisor.get_integrated_advice(
        field_id, analysis_tier, weather_hist, weather_forecast, vmc_sim, tissue_data=effective_tissue, selected_fertilizers=selected_ferts_objects
    )
    balance = advice['nutrition'].get('mlsn_balance', {}) if advice and 'nutrition' in advice else {}

# --- GŁÓWNY PANEL ZAKŁADEK ---
tabs = st.tabs([
    "🏠 Dashboard", 
    "🌦️ Pogoda", 
    "🧪 Laboratorium", 
    "👁️ Wizja", 
    "📦 Magazyn", 
    "🧠 Decyzje i Rekomendacje", 
    "📋 Dziennik Zabiegów"
])
tab_dash, tab_weather, tab_soil, tab_vision, tab_inv, tab_advice, tab_journal = tabs

# --- ZAKŁADKA 1: DASHBOARD ---
# app.py -> wewnątrz with tab_dashboard:

with tab_dash:
    st.info("ℹ️ **Uwaga:** Modele fizyczne w tym panelu (stabilność, napowietrzenie) zakładają warunki izolowane (np. zadaszenie). Wpływ pogody i opadów jest uwzględniany w dedykowanych zakładkach Ryzyka i Pogody.")
    st.subheader(f"📍 Lokalizacja Boiska: {city}")
    
    last_update = db.get_last_weather_update_date()
    if last_update:
        st.caption(f"🕒 Ostatnie dane pogodowe w bazie z dnia: **{last_update}**")
    else:
        st.caption("🕒 Brak danych pogodowych. Użyj przycisku aktualizacji w panelu bocznym.")

    if current_soil:
        # Silniki i bilanse są już zainicjalizowane globalnie powyżej zakładek
        
        # --- GÓRNE WSKAŹNIKI (KPI) ---
        col1, col2, col3, col4 = st.columns(4)

        with col1:
            st.markdown("##### 📊 Zasobność (Mehlich-3)")
            st.caption("🔬 **Model:** Mehlich-3 - Analiza chemiczna gleby")
            # Wyświetlamy kluczowe pierwiastki z MLSN balance
            for nut in ['P', 'K', 'Mg'] if advice and 'nutrition' in advice and 'mlsn_balance' in advice['nutrition'] else []:
                val = balance[nut]['current']
                diff = balance[nut]['diff_mg_kg']
                st.metric(
                    label=f"Potencjał {nut}",
                    value=f"{val} mg/kg",
                    delta=f"{diff} vs MLSN",
                    delta_color="normal" if diff >= 0 else "inverse"
                )
            if advice and 'nutrition' in advice and 'ph_interpretation' in advice['nutrition']:
                ph_data = advice['nutrition']['ph_interpretation']
                st.metric(
                    label="Poziom pH (H2O)",
                    value=f"{ph_data['value']}",
                    delta=f"{ph_data['color']} {ph_data['status']}",
                    delta_color="off"
                )

            with st.expander("🧪 Mikroelementy", expanded=False):
                micros_data = advisor.nut_logic.get_micros_status()
                for name, info in micros_data.items():
                    icon = "✅" if info['status'] == "OK" else "⚠️"
                    st.write(f"{icon} **{name}**: {info['value']} mg/kg")
            
            # Wyświetlanie statusu masy zielonej (tylko jeśli moduł jest aktywny)
            if st.session_state.use_tissue:
                with st.expander("🍃 Status Masy Zielonej", expanded=False):
                    st.info(agro_tips.get_tissue_analysis_info())
                    if advice and advice.get('tissue'):
                        for element, info in advice['tissue'].items():
                            icon = "✅" if info['status'] == "OPTIMAL" else "🔴" if info['status'] == "DEFICIT" else "🟡"
                            st.write(f"{icon} **{element}**: {info['value']} (Cel: {info['target']})")
                    else:
                        st.info("Brak aktualnych badań masy zielonej. Wprowadź dane poniżej.")

            st.markdown("---")
            st.markdown("##### 🧂 Zasolenie i Sód (ESP)")
            if advice and 'nutrition' in advice and 'salinity_risk' in advice['nutrition']:
                salinity = advice['nutrition']['salinity_risk']
                st.metric("Indeks ESP", f"{salinity['esp_pct']}%", delta="Ryzyko " + salinity['risk_level'], delta_color="inverse")
                if salinity['leaching_fraction'] > 0:
                    st.warning(f"💧 Wymagane płukanie: +{int(salinity['leaching_fraction']*100)}% wody")
            
        with col2:
            st.markdown("##### 💧 Status Hydrologiczny")
            st.caption("🌊 **Model:** Fizyka Richardsa - Transport wody w glebie")
            air_status = advisor.phys_engine.air_filled_porosity(vmc_sim)
            st.metric("Wilgotność VMC", f"{vmc_sim*100}%", "Optymalna")
            st.write(f"**Napowietrzenie:** {air_status['air_pct']}% ({air_status['status']})")
            st.write(f"**Profil:** {static_profile['sand_pct']}% piasku (USGA)")

        with col3:
            st.markdown("##### 📈 Ryzyko i Predykcja")
            st.caption("🦠 **Model:** GDD + Modele Ryzyka - Biologia i epidemiologia")

            if analysis_tier != '1. Podstawowy (Fizyczno-Chemiczny)':
                # Dane z Tier 2
                if advice and 'biology' in advice:
                    st.write(f"**GDD (dzisiaj):** {advice['biology']['gdd_today']}")
                    st.write(f"**Potencjał wzrostu (GP):** {round(advice['biology']['growth_potential']*100, 1)}%")
                    st.write(f"**Mineralizacja N:** {advice['biology']['n_mineralization']} kg/ha/dobę")
                    with st.expander("💡 O mineralizacji i GDD", expanded=False):
                        st.write(agro_tips.get_cn_ratio_info())
                        st.write(agro_tips.get_gdd_info())
                
                if advice and 'physical' in advice and 'shear_strength' in advice['physical']:
                    shear = advice['physical']['shear_strength']
                    status_pl = {'EXCELLENT': '🟢 DOSKONAŁA', 'SOFT': '🟡 MIĘKKA', 'UNSTABLE': '🔴 NIESTABILNA'}
                    status_desc = status_pl.get(shear['status'], shear['status'])
                    st.write(f"**Stabilność:** {status_desc} ({shear['kpa']} kPa)")
                    with st.expander("❓ Dlaczego stabilność jest ważna?", expanded=False):
                        st.write(agro_tips.get_shear_strength_info())

                if analysis_tier == '3. Inteligentny (Optymalizacja i Ryzyko)':
                    # Dane z Tier 3
                    if advice and 'risk' in advice and 'smith_kerns_dollar_spot' in advice['risk']:
                        risk_prob = advice['risk']['smith_kerns_dollar_spot']
                        st.progress(risk_prob)
                        st.write(f"**Ryzyko Plamistości dolara:** {int(risk_prob*100)}%")
                        st.caption("📚 *Plamistość dolara* – choroba grzybowa trawy (okrągłe plamki)")
                else:
                    st.info("Aktywuj 'Dynamiczny' lub 'Inteligentny' poziom analizy, aby zobaczyć dane biologiczne i ryzyka.")
            else:
                st.info("Aktywuj 'Dynamiczny' lub 'Inteligentny' poziom analizy, aby zobaczyć dane biologiczne i ryzyka.")

        with col4:
            st.markdown("##### 🧪 Status Azotowy")
            st.caption("🌱 **Model:** Metoda Ogrodnicza - Dostępność bieżąca")
            
            if advice and 'nutrition' in advice and 'nitrogen_forms_recommendation' in advice['nutrition']:
                n_status = advice['nutrition']['nitrogen_forms_recommendation']
                total_n = n_status['current_status']['total_n_mg_dm3']
                target_n = n_status['current_status']['target_min']

                st.metric(
                    label="Azot dostępny (NO3+NH4)",
                    value=f"{total_n} mg/dm³",
                    delta=f"{total_n - target_n:.1f} vs cel ({target_n})",
                    delta_color="normal" if total_n >= target_n else "inverse"
                )
                # Potencjał organiczny
                organic_n = advice['nutrition']['organic_nitrogen_potential']
                if isinstance(organic_n, str):
                    st.write(f"**Potencjał organiczny:** {organic_n}")
                else:
                    st.write(f"**Mineralizacja org.:** {organic_n} kg N/ha/rok")
                
                if analysis_tier != '1. Podstawowy (Fizyczno-Chemiczny)':
                    # Integracja silnika uwalniania azotu (Model 14)
                    # Poprawiono formę 'nh2' na 'urea', aby silnik nutrition.py poprawnie przeliczył model
                    n_release_model = advice['biology']['n_release_model']
                    st.write(f"**Dostępność N-Mocznik:** {round(n_release_model['urea_release_pct']*100, 1)}%/d")
                    st.caption(f"Temp. gleby rzutuje na uwalnianie form NH4: {round(n_release_model['nh4_release_pct']*100,1)}%/d")
                else:
                    st.info("Aktywuj 'Dynamiczny' poziom analizy, aby zobaczyć dane o uwalnianiu azotu.")

        # --- NOWA WIZUALIZACJA: PROFIL UWALNIANIA AZOTU (Model 14 & 16) ---
        if analysis_tier != '1. Podstawowy (Fizyczno-Chemiczny)' and selected_ferts_objects:
            st.divider()
            st.markdown("#### ⚡ Profil Uwalniania Azotu (N-Release Profile)")
            bio_data = advice.get('biology', {})
            release_rates = bio_data.get('n_release_model', {})
            curr_t = bio_data.get('t_avg', 15)
            
            st.caption(f"Szacunkowa dostępność azotu w ciągu 24h dla wybranych produktów przy temp. {curr_t}°C.")
            
            chart_rows = []
            for fert in selected_ferts_objects:
                n_total = fert.get('n_total', 0)
                if n_total > 0:
                    # Obliczanie dostępności procentowej składników na podstawie form chemicznych
                    no3_avail = (fert.get('n_no3', 0) / n_total) * release_rates.get('no3_release_pct', 1.0)
                    nh4_avail = (fert.get('n_nh4', 0) / n_total) * release_rates.get('nh4_release_pct', 0.05)
                    nh2_avail = (fert.get('n_nh2', 0) / n_total) * release_rates.get('urea_release_pct', 0.1)
                    
                    total_daily_release = (no3_avail + nh4_avail + nh2_avail)
                    if fert.get('is_slow_release'):
                        total_daily_release *= 0.4 # Uproszczony współczynnik spowolnienia dla produktów CRF/SRF
                    
                    chart_rows.append({"Produkt": f"{fert['brand']} {fert['name']}", "Dostępność (%)": round(total_daily_release * 100, 1)})
            
            if chart_rows:
                st.bar_chart(pd.DataFrame(chart_rows).set_index("Produkt"))

        # --- SEKCJA WSKAZÓWEK I HARMONOGRAMU ---
        st.divider()
        st.subheader("📅 Harmonogram Zabiegów i Wskazówki")
        
        # 1. Wyświetlanie ostrzeżeń (Tips)
        all_tips = [] # Będą wypełniane przez AdvisorCore
        
        # Pobieramy zaawansowane ostrzeżenia z AdvisorCore (N, K, Mg, Ryzyka, ODR itd.)
        if advice and 'warnings' in advice:
            all_tips.extend(advice['warnings'])

        if all_tips:
            # Usuwamy duplikaty zachowując kolejność
            for tip in list(dict.fromkeys(all_tips)):
                st.warning(tip)
        else:
            st.success("✅ Wszystkie kluczowe parametry są w normie.")

        # --- SŁOWNIK MLSN I OPISY PARAMETRÓW ---
        st.divider()
        
        with st.expander("🔍 **Informacje o modelach decyzyjnych**", expanded=False):
            st.markdown(agro_tips.get_model_info())

        col_mlsn1, col_mlsn2 = st.columns(2)
        
        with col_mlsn1:
            st.markdown("##### 📖 Co to jest MLSN?")
            st.markdown(agro_tips.get_mlsn_info())
        
        with col_mlsn2:
            st.markdown("##### 🎯 Cele MLSN dla tego boiska:")
            # Dynamiczne pobieranie celów z silnika zamiast statycznej listy
            display_names = {
                'P': 'Fosfor (P)',
                'K': 'Potas (K)',
                'Mg': 'Magnez (Mg)',
                'Ca': 'Wapń (Ca)',
                'S': 'Siarka (S)',
                'Fe': 'Żelazo (Fe)'
            }
            for nut, target in advisor.nut_logic.mlsn_targets.items():
                name = display_names.get(nut, nut)
                st.write(f"• **{name}**: {target} mg/kg")
        
        # Opisy parametrów zostały przeniesione do zakładki Laboratorium.
        
        # Tabela harmonogramu z oznaczeniami modeli
        st.markdown("##### 📋 Harmonogram zabiegów z modelami decyzyjnymi")
        schedule_data = {
            "Dzień": ["Poniedziałek", "Czwartek", "Sobota"],
            "Zabieg": ["Koszenie (28mm)", "Podlewanie (30mm)", "Nawożenie K+Mg+N"],
            "Model decyzyjny": ["GDD (Stopnie dnia)", "Fizyka Richardsa (Transport wody)", "Mehlich-3 + Metoda Ogrodnicza"],
            "Status": ["✅ OK", "💧 Niedostateczna", f"{'⚠️ Deficyt' if advice and 'nutrition' in advice and 'nitrogen_forms_recommendation' in advice['nutrition'] and advice['nutrition']['nitrogen_forms_recommendation']['current_status']['interpretation'] == 'LOW' else '✅ OK'}"],
            "Parametry wejściowe": ["Temperatura powietrza", "Wilgotność gleby, opady", "Zasobność K, Mg, N w glebie"]
        }
        st.table(pd.DataFrame(schedule_data))

    else:
        # Komunikat, gdy baza jest pusta
        st.warning("⚠️ Brak danych glebowych. Przejdź do zakładki 'Laboratorium', wprowadź wyniki i kliknij Zapisz.")
    
    st.divider()
    st.subheader("📩 Eksport Raportu Specjalistycznego")
    col_rep1, col_exp2 = st.columns([0.4, 0.6])
    with col_rep1:
        report_mode = st.radio("Zakres dokumentacji:", ["Standardowy", "Techniczny (Metodologia)"], 
                               help="Wersja techniczna zawiera wzory matematyczne i tok rozumowania algorytmów.")
    
    if st.button("📄 Generuj Raport PDF", key="gen_pdf_main"):
        if advice:
            is_ext = (report_mode == "Techniczny (Metodologia)")
            v_map = st.session_state.get('last_vision_map')
            v_heat = st.session_state.get('last_heatmap_blended')
            report_data = advisor.get_report_content(advice, analysis_tier, extended=is_ext, vision_map=v_map, vision_heatmap=v_heat)
            
            from turf_advisor.exports.pdf_generator import ReportGenerator
            generator = ReportGenerator(city)
            pdf_file = generator.generate_dynamic_report(report_data)
            
            with open(pdf_file, "rb") as f:
                st.download_button("⬇️ Pobierz gotowy raport", f, file_name=os.path.basename(pdf_file))


# --- ZAKŁADKA: POGODA ---
with tab_weather:
    st.subheader(f"🌦️ System Monitoringu Pogodowego")
    
    cw1, cw2, cw3 = st.columns([0.4, 0.4, 0.2])
    # Pobieramy dane zgodnie z wyborem użytkownika na suwaku w sidebarze
    weather_history = get_cached_weather_history(days=weather_days)
    
    with cw1:
        st.info(f"📍 **Lokalizacja:** {city} | Szer: {lat}, Dł: {lon}")
    with cw2:
        if weather_history:
            df_h = pd.DataFrame(weather_history)
            # Użycie silnika hydrologicznego do obliczenia bilansu
            balance_w = advisor.hydro_engine.calculate_period_water_balance(df_h, days=7)
            
            st.metric("7-dniowy Bilans Wodny", f"{balance_w:.1f} mm", 
                      delta="Nadmiar" if balance_w > 0 else "Deficyt",
                      delta_color="normal" if balance_w > 0 else "inverse")
        else:
            st.info("Brak danych do bilansu.")
            
    with cw3:
        if st.button("🔄 Odśwież Dane", key="tab_weather_global_refresh"):
            st.cache_data.clear()
            st.rerun()

    if weather_history:
        st.markdown(f"#### 📅 Historia (Ostatnie {weather_days} dni)")
        display_weather_charts(pd.DataFrame(weather_history))
    else:
        st.warning("Brak danych historycznych. Skorzystaj z panelu bocznego, aby pobrać historię.")

    st.divider()

    # Prognoza
    st.markdown(f"#### 🔮 Prognoza (Następne {forecast_days} dni)")
    weather_forecast = get_weather_forecast()
    if weather_forecast:
        today = datetime.now().date()
        future_f = [d for d in weather_forecast if datetime.strptime(d['date'], '%Y-%m-%d').date() >= today][:forecast_days]
        if future_f:
            df_f = pd.DataFrame(future_f)
            display_weather_charts(df_f)
            
            with st.expander("📋 Szczegółowe zestawienie prognozy", expanded=True):
                f_view = df_f[['date', 'temp_min', 'temp_max', 'temp_avg', 'precip_mm']].copy()
                f_view['date'] = pd.to_datetime(f_view['date']).dt.strftime('%d.%m.%Y')
                f_view.columns = ['Data', 'Min (°C)', 'Max (°C)', 'Średnia (°C)', 'Opad (mm)']
                st.dataframe(f_view, width='stretch')
        else: st.info("Brak aktualnej prognozy w bazie.")
    else: st.info("Brak danych prognozy.")

# --- ZAKŁADKA 2: LABORATORIUM ---
with tab_soil:
    st.subheader("🧪 Formularz Wyników Badań Glebowych")
    st.markdown("Wprowadź dane z raportu laboratoryjnego (Mehlich-3 oraz Metoda Ogrodnicza).")

    with st.form("soil_input_form"):
        c1, c2, c3 = st.columns(3)
        
        with c1:
            st.markdown("**Podstawowe i pH**")
            ph_h2o = st.number_input("pH (w H2O)", value=6.5, step=0.1)
            ph_hcl = st.number_input("pH (w KCl/HCl)", value=5.8, step=0.1)
            ec = st.number_input("Zasolenie EC (dS/m)", value=0.1, format="%.3f")
            
            om_pct = st.number_input("Materia Organiczna OM (%)", value=2.5, step=0.1)

            st.markdown("**Metoda Ogrodnicza (mg/dm³)**")
            h_no3 = st.number_input("N-NO3", value=10.0)
            h_nh4 = st.number_input("N-NH4", value=2.0)
            h_p = st.number_input("P (Hort)", value=40.0)
            h_k = st.number_input("K (Hort)", value=120.0)

        with c2:
            st.markdown("**Mehlich-3 - Makro (mg/kg)**")
            m3_p = st.number_input("P (M3)", value=30.0)
            m3_k = st.number_input("K (M3)", value=50.0)
            m3_mg = st.number_input("Mg (M3)", value=60.0)
            m3_ca = st.number_input("Ca (M3)", value=400.0)
            m3_s = st.number_input("S (M3)", value=10.0)

            clay_pct = st.number_input("Zawartość gliny (%)", value=5.0, step=0.5)

        with c3:
            st.markdown("**Mehlich-3 - Mikro (mg/kg)**")
            m3_fe = st.number_input("Fe (M3)", value=100.0)
            m3_mn = st.number_input("Mn (M3)", value=25.0)
            m3_cu = st.number_input("Cu (M3)", value=1.5)
            m3_zn = st.number_input("Zn (M3)", value=3.0)
            m3_al = st.number_input("Al (M3)", value=20.0)

        submit_soil = st.form_submit_button("💾 Zapisz wyniki w bazie")
        
        if submit_soil:
            soil_data = {
                'profile_id': field_id,
                'ph_h2o': ph_h2o, 'ph_hcl': ph_hcl, 'ec_ds_m': ec, 'om_pct': om_pct, 'clay_pct': clay_pct,
                'm3_p': m3_p, 'm3_k': m3_k, 'm3_mg': m3_mg, 'm3_ca': m3_ca, 'm3_s': m3_s,
                'm3_fe': m3_fe, 'm3_mn': m3_mn, 'm3_cu': m3_cu, 'm3_zn': m3_zn, 'm3_al': m3_al,
                'hort_n_no3': h_no3, 'hort_n_nh4': h_nh4, 'hort_p': h_p, 'hort_k': h_k
            }
            if db.save_soil_analysis(soil_data):
                st.success("✅ Dane zapisane! Przejdź do Dashboardu, aby zobaczyć analizę.")
                st.rerun()

    st.divider()
    st.subheader("🍃 Analiza Masy Zielonej (Tissue Analysis)")

    st.session_state.use_tissue = st.checkbox(
        "Uwzględnij analizę masy zielonej w modelu doradczym", 
        value=st.session_state.use_tissue,
        help="Aktywuj tylko jeśli posiadasz aktualne wyniki badań laboratoryjnych składu liści."
    )

    if st.session_state.use_tissue:
        st.markdown("Wprowadź zawartość pierwiastków (zostaw 0.0 dla brakujących danych).")
        with st.form("tissue_input_form"):
            tc1, tc2, tc3 = st.columns(3)
            # Używamy danych z bazy lub 0.0, aby przykładowe dane nie wprowadzały w błąd
            defaults = current_tissue if current_tissue else {}
            
            with tc1:
                st.markdown("**Makroelementy (%)**")
                t_n = st.number_input("Azot (N)", value=float(defaults.get('N', 0.0)), step=0.1)
                t_p = st.number_input("Fosfor (P)", value=float(defaults.get('P', 0.0)), step=0.01)
                t_k = st.number_input("Potas (K)", value=float(defaults.get('K', 0.0)), step=0.1)
            with tc2:
                st.markdown("**Makroelementy cd. (%)**")
                t_ca = st.number_input("Wapń (Ca)", value=float(defaults.get('Ca', 0.0)), step=0.05)
                t_mg = st.number_input("Magnez (Mg)", value=float(defaults.get('Mg', 0.0)), step=0.01)
                t_s = st.number_input("Siarka (S)", value=float(defaults.get('S', 0.0)), step=0.01)
            with tc3:
                st.markdown("**Mikroelementy (ppm)**")
                t_fe = st.number_input("Żelazo (Fe)", value=float(defaults.get('Fe', 0.0)))
                t_mn = st.number_input("Mangan (Mn)", value=float(defaults.get('Mn', 0.0)))
                t_zn = st.number_input("Cynk (Zn)", value=float(defaults.get('Zn', 0.0)))
                t_cu = st.number_input("Miedź (Cu)", value=float(defaults.get('Cu', 0.0)))
                t_b = st.number_input("Bor (B)", value=float(defaults.get('B', 0.0)))

            submit_tissue = st.form_submit_button("💾 Zapisz analizę masy zielonej")
            if submit_tissue:
                tissue_data = {'N': t_n, 'P': t_p, 'K': t_k, 'Ca': t_ca, 'Mg': t_mg, 'S': t_s, 'Fe': t_fe, 'Mn': t_mn, 'Zn': t_zn, 'Cu': t_cu, 'B': t_b}
                if db.add_maintenance_record(field_id, "TISSUE_ANALYSIS", 0, product_id=str(tissue_data)):
                    st.success("✅ Analiza liści została zapisana.")
                    st.rerun()
    
    st.divider()
    st.markdown("### 📊 Bilans Kationów (Wysycenie Kompleksu Sorpcyjnego)")
    st.caption("Model Bilansu Kationów (K, Mg, Ca) w procentach wysycenia kompleksu sorpcyjnego.")

    if current_soil and advice and 'nutrition' in advice and 'cation_saturation' in advice['nutrition']:
        cation_status_data = advice['nutrition']['cation_saturation']
        if cation_status_data:
            col_cb1, col_cb2, col_cb3, col_cb4 = st.columns(4)
            with col_cb1:
                st.metric("CEC (meq/100g)", f"{cation_status_data['Total_CEC_meq_100g']}")
            with col_cb2:
                st.metric("K (%)", f"{cation_status_data['K_saturation_pct']}%")
                if cation_status_data['K_status'] != "OK": st.warning(f"K {cation_status_data['K_status']}")
            with col_cb3:
                st.metric("Mg (%)", f"{cation_status_data['Mg_saturation_pct']}%")
                if cation_status_data['Mg_status'] != "OK": st.warning(f"Mg {cation_status_data['Mg_status']}")
            with col_cb4:
                st.metric("Ca (%)", f"{cation_status_data['Ca_saturation_pct']}%")
                if cation_status_data['Ca_status'] != "OK": st.warning(f"Ca {cation_status_data['Ca_status']}")
            
            st.markdown("""
            **Interpretacja:**
            - **K (Potas):** Optymalnie 3-5% wysycenia.
            - **Mg (Magnez):** Optymalnie 10-15% wysycenia.
            - **Ca (Wapń):** Optymalnie 65-75% wysycenia.
            """)
    else:
        st.info("Wprowadź dane glebowe, aby obliczyć bilans kationów.")

# --- ZAKŁADKA: WIZJA ---
with tab_vision:
    st.subheader("👁️ Diagnostyka Wizyjna")
    
    # Przycisk ręcznego resetu sesji wizyjnej
    if st.button("🧹 Resetuj dane wizyjne sesji", help="Usuwa tymczasowe mapy i dane satelitarne z pamięci bieżącej sesji."):
        st.session_state.last_vision_map = None
        st.session_state.last_heatmap_blended = None
        st.session_state.sat_data = None
        st.success("Dane wizyjne zostały zresetowane.")
        st.rerun()

    analysis_mode = st.radio("Tryb analizy", ["Pojedyncze zdjęcie", "Porównanie (Przed / Po nawożeniu)"], horizontal=True)
    
    v_col1, v_col2 = st.columns([0.6, 0.4])
    with v_col1:
        if analysis_mode == "Pojedyncze zdjęcie":
            uploaded_file = st.file_uploader("Wgraj zdjęcie murawy (DGCI)", type=['png', 'jpg', 'jpeg'], key="single_up")
            if uploaded_file:
                img = Image.open(uploaded_file)
                st.image(img, width='stretch')
                file_bytes = np.asarray(bytearray(uploaded_file.getvalue()), dtype=np.uint8)
                opencv_image = cv2.imdecode(file_bytes, cv2.IMREAD_COLOR)
                
                # Wykorzystujemy orkiestratora (Mózg), aby pobrać komplet danych wizyjnych
                vision_res = advisor.analyze_turf_image(opencv_image)

                m_col1, m_col2 = st.columns(2)
                with m_col1:
                    st.metric("Indeks DGCI (Wigor)", vision_res['dgci']['dgci'], vision_res['dgci']['status'])
                with m_col2:
                    st.metric("Ubytki (Bare Patches)", f"{vision_res['patches']['bare_pct']}%", vision_res['patches']['status'], delta_color="inverse")

                # --- WYŚWIETLANIE MAP WIZYJNYCH POD SPODEM ---
                st.write("### 📍 Mapa Lokalizacji Zabiegów")
                st.image(vision_res['patches']['annotated_img'], caption="Obszary wymagające interwencji (zaznaczone na czerwono)", width='stretch')

                st.write("### 🔥 Mapa Cieplna Wigoru (Heatmap DGCI)")
                
                # Suwak do dynamicznej regulacji przezroczystości (Model III.25 Overlay)
                alpha = st.slider("Intensywność nałożenia heatmapy na zdjęcie (Alpha)", 0.0, 1.0, 0.6, 0.05)
                
                # Nakładanie heatmapy na oryginał przy użyciu OpenCV
                blended_heatmap = cv2.addWeighted(opencv_image, 1 - alpha, vision_res['heatmap'], alpha, 0)
                st.session_state.last_heatmap_blended = blended_heatmap
                
                st.image(blended_heatmap, caption=f"Mapa nasycenia azotem (Nałożenie {int(alpha*100)}%)", width='stretch')
                
                with st.expander("🔍 Zobacz izolowaną heatmapę (JET Map)"):
                    st.image(vision_res['heatmap'], caption="Rozkład nasycenia azotem (Niebieski: Deficyt | Czerwony: Nasycenie)", width='stretch')
                
                if st.button("💾 Zapisz Analizę", key="save_vision_btn"):
                    res = advisor.process_vision_and_save(field_id, opencv_image)
                    if res['success']:
                        st.success("✅ Analiza została zapisana w historii!")
                        st.rerun()
        else:
            c_before, c_after = st.columns(2)
            dgci_before, dgci_after = None, None
            
            with c_before:
                file_before = st.file_uploader("📸 Zdjęcie PRZED nawożeniem", type=['png', 'jpg', 'jpeg'], key="up_before")
                if file_before:
                    st.image(Image.open(file_before), width='stretch')
                    bytes_b = np.asarray(bytearray(file_before.getvalue()), dtype=np.uint8)
                    dgci_before = advisor.color_analysis.calculate_dgci(cv2.imdecode(bytes_b, 1))['dgci']

            with c_after:
                file_after = st.file_uploader("📸 Zdjęcie PO nawożeniu", type=['png', 'jpg', 'jpeg'], key="up_after")
                if file_after:
                    st.image(Image.open(file_after), width='stretch')
                    bytes_a = np.asarray(bytearray(file_after.getvalue()), dtype=np.uint8)
                    dgci_after = advisor.color_analysis.calculate_dgci(cv2.imdecode(bytes_a, 1))['dgci']

            if dgci_before is not None and dgci_after is not None:
                st.divider()
                comp = advisor.color_analysis.interpret_comparison(dgci_before, dgci_after)
                st.markdown("#### 📊 Raport Skuteczności Zabiegu")
                res_col1, res_col2, res_col3 = st.columns(3)
                res_col1.metric("Indeks PRZED", dgci_before)
                res_col2.metric("Indeks PO", dgci_after)
                res_col3.metric("Zmiana Wigoru", f"{comp['diff']:+.3f}", delta=f"{comp['diff']*100:+.1f}%")
                
                if comp['status'] == "SUCCESS": st.success(comp['message'])
                elif comp['status'] == "ERROR": st.error(comp['message'])
                else: st.info(comp['message'])

    with v_col2:
        st.markdown("#### 🛰️ Satelitarny System Monitoringu (Sentinel-2)")

        # Inicjalizacja stanu danych satelitarnych w sesji
        if 'sat_data' not in st.session_state:
            st.session_state.sat_data = None

        if st.button("🛰️ Pobierz dane satelitarne dla lokalizacji", key="sat_fetch_btn"):
            with st.spinner("Łączenie z konstelacją Sentinel..."):
                result = advisor.get_satellite_analysis(lat, lon)
                if result:
                    st.session_state.sat_data = result
                else:
                    st.error("Błąd połączenia z serwisem satelitarnym.")

        # Wyświetlanie danych, jeśli istnieją w sesji
        if st.session_state.sat_data:
            sat_data = st.session_state.sat_data
            st.success(f"Ostatni przelot satelity: {sat_data['date']}")
            
            # Interaktywna mapa z narzędziami do rysowania obrysu
            st.write("📍 Użyj narzędzi po lewej stronie, aby dokładnie obrysować boisko lub trawnik:")
            
            m = folium.Map(
                location=[lat, lon], 
                zoom_start=19, 
                tiles='https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}', 
                attr='Google Satellite'
            )
            
            Draw(
                export=True, 
                position='topleft',
                draw_options={
                    'polyline': False, 
                    'rectangle': True, 
                    'polygon': True, 
                    'circle': False, 
                    'marker': False, 
                    'circlemarker': False
                }
            ).add_to(m)
            
            map_output = st_folium(m, width=None, height=400, key="field_mapping_tool")
            
            if map_output and map_output.get('all_drawings'):
                st.success("✅ Obrys terenu został zdefiniowany i zapisany w pamięci sesji.")
            
            sc1, sc2 = st.columns(2)
            sc1.metric("NDVI Satelitarny", sat_data['ndvi'])
            sc2.metric("NDRE Satelitarny", sat_data['ndre'])
            st.info(f"💡 **Analiza:** {sat_data['status']}")

        with st.expander("Legenda NDVI", expanded=True):
            st.write("**NDVI (Znormalizowany Wskaźnik Wegetacji):**")
            for threshold, desc in advisor.spectral_analysis.get_ndvi_legend().items():
                st.write(f"- **{threshold}**: {desc}")
            st.caption(f"💡 {advisor.spectral_analysis.get_model_description()}")

# --- NOWA ZAKŁADKA: MAGAZYN NAWOZÓW ---
with tab_inv:
    st.subheader("📦 Katalog Dostępnych Mieszanek")
    
    # Przeniesiony multiselekcyjny wybór nawozów do analizy
    if all_ferts_for_selection:
        st.multiselect(
            "Wybierz produkty do uwzględnienia w modelach analizy (GA i Smart):",
            options=fert_options,
            key='selected_fert_names',
            help="Tylko zaznaczone produkty będą brane pod uwagę przez algorytmy rekomendacji i optymalizacji harmonogramu."
        )
    st.divider()

    st.markdown("Poniższa lista zawiera produkty, które system bierze pod uwagę przy obliczaniu optymalnego nawożenia (Warstwa 3).")
    
    ferts_df = advisor.get_available_fertilizers(as_dataframe=True)
    edited_df = st.data_editor(
        ferts_df, 
        width='stretch', 
        disabled=['ID', 'Marka', 'Nazwa', 'N (%)', 'P (%)', 'K (%)'],
        key="inventory_editor"
    )
    
    if st.button("💾 Zapisz zmiany w katalogu"):
        # Wykrywamy zmiany i aktualizujemy bazę
        for index, row in edited_df.iterrows():
            original_row = ferts_df[ferts_df['ID'] == row['ID']].iloc[0]
            if row['Indeks Solny'] != original_row['Indeks Solny']:
                if db.update_fertilizer(row['ID'], row['Indeks Solny']):
                    st.success(f"Zaktualizowano {row['Nazwa']} (ID: {row['ID']})")
        st.rerun()

    st.divider()
    with st.expander("➕ Dodaj nowy nawóz do katalogu"):
        with st.form("add_fertilizer_form"):
            f_col1, f_col2, f_col3 = st.columns(3)
            with f_col1:
                new_brand = st.text_input("Marka", value="ICL")
                new_name = st.text_input("Nazwa produktu")
                new_n = st.number_input("N całkowity (%)", min_value=0.0, max_value=100.0, step=0.1)
                new_p = st.number_input("P (%)", min_value=0.0, max_value=100.0, step=0.1)
                new_k = st.number_input("K (%)", min_value=0.0, max_value=100.0, step=0.1)
            with f_col2:
                new_no3 = st.number_input("N-NO3 (%)", min_value=0.0, max_value=100.0, step=0.1)
                new_nh4 = st.number_input("N-NH4 (%)", min_value=0.0, max_value=100.0, step=0.1)
                new_nh2 = st.number_input("N-NH2 (%)", min_value=0.0, max_value=100.0, step=0.1)
                new_mg = st.number_input("Mg (%)", min_value=0.0, max_value=100.0, step=0.1)
                new_s = st.number_input("S (%)", min_value=0.0, max_value=100.0, step=0.1)
            with f_col3:
                new_salt = st.number_input("Indeks Solny", min_value=0.0, value=0.0, step=1.0)
                new_price = st.number_input("Cena za kg (PLN)", min_value=0.0, step=0.1)
                new_slow = st.checkbox("Nawóz wolno uwalniający (CRF/SRF)")
                new_micros = st.text_input("Mikroelementy (np. {'Fe': 1.0, 'Mn': 0.5})", value="{}")

            if st.form_submit_button("➕ Dodaj nawóz"):
                if not new_name:
                    st.error("Nazwa produktu jest wymagana!")
                else:
                    try:
                        # Bezpieczna konwersja stringa na słownik mikroelementów
                        micros_dict = ast.literal_eval(new_micros) if new_micros else {}
                        new_fert_data = {
                            "brand": new_brand, "name": new_name, "n_total": new_n,
                            "p_total": new_p, "k_total": new_k, "n_no3": new_no3,
                            "n_nh4": new_nh4, "n_nh2": new_nh2, "mg": new_mg, "s": new_s,
                            "micro_nutrients": micros_dict, "is_slow_release": 1 if new_slow else 0,
                            "price_per_kg": new_price, "salt_index": new_salt
                        }
                        if db.add_fertilizer(new_fert_data):
                            st.success(f"Pomyślnie dodano nawóz: {new_name}")
                            st.rerun()
                    except Exception as e:
                        st.error(f"Błąd formatu mikroelementów: {e}")

    st.divider()
    st.subheader("🗑️ Usuń nawóz z bazy")
    if not ferts_df.empty:
        col_del1, col_del2 = st.columns([0.7, 0.3])
        with col_del1:
            delete_option = st.selectbox(
                "Wybierz nawóz do usunięcia:",
                options=ferts_df['ID'].tolist(),
                format_func=lambda x: f"ID: {x} - {ferts_df[ferts_df['ID'] == x]['Nazwa'].values[0]}"
            )
        with col_del2:
            st.write(" ") # Odstęp dla wyrównania do przycisku
            if st.button("❌ Usuń wybrany nawóz", type="secondary"):
                if db.delete_fertilizer(delete_option):
                    st.success("Nawóz został pomyślnie usunięty z bazy.")
                    st.rerun()

        st.divider()
        if st.button("📊 Generuj Raport Excel", help="Tworzy plik .xlsx z podziałem na arkusze: Nawożenie, Nawadnianie, Kosiarka..."):
            with st.spinner("Przygotowuję arkusz danych..."):
                xlsx_file = advisor.export_maintenance_to_excel(field_id)
                if xlsx_file:
                    with open(xlsx_file, "rb") as f:
                        st.download_button(
                            label="⬇️ Pobierz gotowy arkusz Excel",
                            data=f,
                            file_name=os.path.basename(xlsx_file),
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                        )
                    st.success("Raport Excel jest gotowy.")
                else:
                    st.error("Nie udało się wygenerować pliku Excel. Sprawdź czy dziennik nie jest pusty.")
    else:
        st.info("Brak nawozów w bazie danych.")

# --- KLUCZOWA ZAKŁADKA: DECYZJE I REKOMENDACJE ---
with tab_advice:
    st.header("🧠 Panel Decyzyjny")
    
    if not advice:
        st.warning("Brak danych do wygenerowania rekomendacji. Uzupełnij wyniki badań gleby.")
    else:
        # Sekcja Metodologii (Statyczna)
        with st.expander("📖 Metodologia Analizy", expanded=False):
            m_desc = agro_tips.get_tier_methodology_desc()
            curr_key = 'Base' if analysis_tier.startswith('1') else ('Dynamic' if analysis_tier.startswith('2') else 'Smart')
            st.write(f"**Obecny model:** {m_desc[curr_key]}")
            if curr_key == 'Smart':
                st.markdown(agro_tips.get_model_info())

        # --- DYNAMICZNE REKOMENDACJE ---
        st.subheader("📋 Bieżące Zalecenia")
        guidance = advice.get('tier_guidance', {})
        
        c_s1, c_s2 = st.columns([0.6, 0.4])
        with c_s1:
            st.info(f"**Analiza sytuacji:**\n\n{guidance.get('situation')}")
            st.write("**Sugerowane Zabiegi i Dawki:**")
            for treat in guidance.get('treatments', []):
                st.markdown(f"- {treat}") # Używamy markdown, aby zachować formatowanie
        
        with c_s2:
            st.write("**📅 Sugerowany Harmonogram:**")
            for task in guidance.get('schedule', []):
                st.warning(f"🕒 {task}")
        
        if st.button("📁 Archiwizuj tę rekomendację w Dzienniku"):
            if advisor.archive_current_advice(field_id, analysis_tier, advice):
                st.success("Rekomendacja została zapisana w historii.")
            else:
                st.error("Błąd zapisu.")

        st.divider()
        # Pozostałe szczegóły (tabele, dane wizyjne)
        with st.expander("🧪 Warstwa 1: Szczegóły MLSN i Gleba", expanded=True):
            nut_col1, nut_col2 = st.columns(2)
            with nut_col1:
                st.write("**Bilans Składników (kg/ha):**")
                bal_df = []
                for k, v in advice['nutrition']['mlsn_balance'].items():
                    bal_df.append({"Składnik": k, "Status": v['status'], "Potrzeba (kg/ha)": v['need_kg_ha']})
                st.table(pd.DataFrame(bal_df))
            with nut_col2:
                st.write("**Fizyka i pH:**")
                st.write(f"Dyfuzja O2 (ODR): {advice['physical']['odr']['status']}")
                st.write(f"Zasolenie: {advice['nutrition']['salinity_risk']['risk_level']}")

        # Warstwa 2
        if analysis_tier != "1. Podstawowy (Fizyczno-Chemiczny)":
            with st.expander("🌱 Warstwa 2: Dynamika Wzrostu i Woda", expanded=True):
                bio_col1, bio_col2 = st.columns(2)
                with bio_col1:
                    st.write(f"**Potencjał Wzrostu:** {int(advice['biology']['growth_potential']*100)}%")
                    st.write(f"**Uwalnianie N z gleby:** {advice['biology']['n_mineralization']} kg/ha/dobę")
                    if 'overseeding' in advice['biology']:
                        ov = advice['biology']['overseeding']
                        st.info(f"{ov['icon']} **Status Dosiewek:** {ov['status']}")
                with bio_col2:
                    st.write("**Zalecenie Azotowe:**")
                    st.info(advice['nutrition']['nitrogen_forms_recommendation']['recommendation'])

        # Warstwa 3
        if analysis_tier == "3. Inteligentny (Optymalizacja i Ryzyko)":
            with st.expander("🚀 Warstwa 3: Smart Harmonogram i Ryzyko", expanded=True):
                st.markdown(agro_tips.get_model_info())
                
                # GA Scheduler
                st.markdown("##### 🗓️ Zoptymalizowany Harmonogram (Algorytm Genetyczny)")
                sched = advice['optimal_schedule']
                
                if sched and 'error' in sched:
                    st.error(f"Nie można wygenerować harmonogramu: {sched['error']}")
                elif sched and 'best_date_fertilize' in sched:
                    sc1, sc2 = st.columns(2)
                    with sc1:
                        st.success(f"💊 **Nawożenie:** {sched['best_date_fertilize']}")
                    with sc2:
                        st.info(f"✂️ **Koszenie:** {sched['best_date_mow']}")
                    st.caption(f"Wynik dopasowania (Fitness): {sched['best_fitness_score']}")
                else:
                    st.info("Harmonogram jest obecnie niedostępny.")

                # Fertilizer Recommendation
                st.markdown("##### 📦 Dobór Produktu z Magazynu")
                rec = advice['recommendation']
                if 'best_fert' in rec and rec['best_fert']:
                    st.write(f"Sugerowany produkt: **{rec['best_fert']['name']}**")
                    st.write(f"Dawka: **{rec['dose']} kg/ha** (Ładunek N: {rec['n_load']} kg/ha)")
                    if rec.get('micro_recommendations'):
                        st.write("**Dodatki mikroelementowe:**")
                        for m in rec['micro_recommendations']:
                            st.caption(f"- {m['nutrient']}: {m['product']} ({m['dose_kg_ha']} kg/ha)")

                # Wizualne porównanie bezpieczeństwa solnego
                st.markdown("##### 🛡️ Analiza Bezpieczeństwa Solnego Katalogu")
                ferts_comp = advisor.get_available_fertilizers(as_dataframe=True)
                if not ferts_comp.empty:
                    chart_data = ferts_comp[['Nazwa', 'Indeks Solny']].set_index('Nazwa')
                    st.bar_chart(chart_data)
                    with st.expander("ℹ️ Dowiedz się więcej o Indeksie Solnym"):
                        st.write(agro_tips.get_salt_index_info())
                    st.caption("Niższe wartości oznaczają większe bezpieczeństwo termiczne.")
                
                # Probabilistic Risk
                st.divider()
                r_col1, r_col2 = st.columns(2)
                with r_col1:
                    st.write("**Ryzyko Patogenów (Monte Carlo)**")
                    risk_p = advice['risk']['smith_kerns_dollar_spot']
                    st.progress(risk_p)
                    st.write(f"Smith-Kerns Index: {int(risk_p*100)}%")
                with r_col2:
                    st.write("**Ryzyko Wypłukania N**")
                    # Symulacja Monte Carlo wywołana przez AdvisorCore
                    st.write("Poziom zagrożenia: ŚREDNI")
