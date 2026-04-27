# turf_advisor/integrations/meteo_api.py
import requests
import sqlite3
import os
from datetime import datetime

class MeteoEngine:
    def __init__(self, lat, lon, api_key=None):
        self.lat = lat
        self.lon = lon
        self.api_key = api_key
        # Ścieżka do bazy danych (ujednolicona na katalog główny projektu root/data)
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        self.db_path = os.path.join(base_dir, 'data', 'turf_system.db')

    def update_weather_data(self, forecast_days=7):
        """Pobiera dane i aktualizuje bazę. Obsługuje Open-Meteo jako standard."""
        # Jeśli mamy klucz, moglibyśmy tu dodać obsługę Visual Crossing, 
        # ale dla Open-Meteo klucz nie jest wymagany.
        return self._fetch_open_meteo(forecast_days)

    def update_historical_weather(self, days_back=30):
        """Pobiera dane historyczne i aktualizuje bazę."""
        return self._fetch_open_meteo_history(days_back)

    def _fetch_open_meteo(self, forecast_days):
        """Implementacja darmowego API Open-Meteo."""
        url = "https://api.open-meteo.com/v1/forecast"
        params = {
            "latitude": self.lat,
            "longitude": self.lon,
            "daily": [
                "temperature_2m_max", 
                "temperature_2m_min", 
                "precipitation_sum", 
                "relative_humidity_2m_max", 
                "et0_fao_evapotranspiration"
            ],
            "timezone": "auto",
            "forecast_days": forecast_days
        }
        
        try:
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()['daily']
            
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            for i in range(len(data['time'])):
                cursor.execute("""
                    INSERT OR REPLACE INTO weather_history 
                    (date, temp_max, temp_min, temp_avg, precip_mm, humidity, et_calculated, is_forecast)
                    VALUES (?, ?, ?, ?, ?, ?, ?, 1)
                """, (
                    data['time'][i], data['temperature_2m_max'][i], data['temperature_2m_min'][i],
                    round((data['temperature_2m_max'][i] + data['temperature_2m_min'][i]) / 2, 1),
                    data['precipitation_sum'][i], data['relative_humidity_2m_max'][i],
                    data['et0_fao_evapotranspiration'][i]
                ))
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            print(f"Błąd Open-Meteo: {e}")
            return False

    def _fetch_open_meteo_history(self, days_back):
        """Pobiera dane historyczne z Open-Meteo."""
        from datetime import timedelta
        end_date = datetime.now().date()
        start_date = end_date - timedelta(days=days_back)
        
        url = "https://archive-api.open-meteo.com/v1/archive"
        params = {
            "latitude": self.lat,
            "longitude": self.lon,
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "daily": [
                "temperature_2m_max", 
                "temperature_2m_min", 
                "precipitation_sum", 
                "relative_humidity_2m_max", 
                "et0_fao_evapotranspiration"
            ],
            "timezone": "auto"
        }
        
        try:
            response = requests.get(url, params=params, timeout=15)
            response.raise_for_status()
            data = response.json()['daily']
            
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            for i in range(len(data['time'])):
                cursor.execute("""
                    INSERT OR REPLACE INTO weather_history 
                    (date, temp_max, temp_min, temp_avg, precip_mm, humidity, et_calculated, is_forecast)
                    VALUES (?, ?, ?, ?, ?, ?, ?, 0)
                """, (
                    data['time'][i], data['temperature_2m_max'][i], data['temperature_2m_min'][i],
                    round((data['temperature_2m_max'][i] + data['temperature_2m_min'][i]) / 2, 1),
                    data['precipitation_sum'][i], data['relative_humidity_2m_max'][i],
                    data['et0_fao_evapotranspiration'][i]
                ))
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            print(f"Błąd Open-Meteo History: {e}")
            return False