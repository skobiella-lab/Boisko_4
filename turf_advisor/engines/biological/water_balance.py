# turf_advisor/engines/biological/water_balance.py
from datetime import datetime, timedelta

class WaterBalance:
    def __init__(self, static_profile, db_manager=None):
        self.static_profile = static_profile
        self.db_manager = db_manager
        self.weather_history = []
        self.weather_forecast = []
        self.soil_data = {} # Będzie ustawiane dynamicznie

    def set_weather_data(self, weather_history, weather_forecast):
        self.weather_history = weather_history
        self.weather_forecast = weather_forecast

    def set_soil_data(self, soil_data):
        self.soil_data = soil_data

    def calculate_et_for_today(self, is_indoor=False, day_data=None):
        """
        Oblicza Ewapotranspirację (ET) dla dzisiejszego dnia.
        Uproszczony model Penmana-Monteitha lub stała dla warunków indoor.
        """
        if is_indoor:
            # Dla krytej płyty, ET jest stałe lub bazuje na wewnętrznych czujnikach
            return 2.5 # mm/dzień (przykładowa stała wartość dla indoor)

        today_data = day_data if day_data is not None else (self.weather_history[0] if self.weather_history else None)
        if not today_data:
            return 0.0

        temp_avg = today_data.get('temp_avg') if today_data.get('temp_avg') is not None else 15.0
        humidity = today_data.get('humidity') if today_data.get('humidity') is not None else 70.0 # %

        # Brak danych o promieniowaniu słonecznym i wietrze w weather_history, więc upraszczamy
        
        # Współczynnik temperaturowy
        temp_factor = max(0, (temp_avg - 5) / 20) # Wzrost od 5 do 25 stopni
        
        # Współczynnik wilgotności (niższa wilgotność = wyższe ET)
        humidity_factor = (100 - humidity) / 100

        # Bazowa ET (mm/dzień)
        base_et = 3.0
        et_calculated = base_et * temp_factor * (1 + humidity_factor * 0.5) # Uproszczony wpływ
        
        return round(et_calculated, 2)

    def calculate_period_water_balance(self, weather_data, days=7, is_indoor=False, total_irrigation=0.0):
        """
        Oblicza bilans wodny dla określonego okresu (dni).
        Bilans = Suma opadów - Suma ET - Suma nawadniania (z maintenance_log)
        """
        if weather_data is None:
            return 0.0

        # Obsługa DataFrame lub listy słowników
        if hasattr(weather_data, 'to_dict'):
            recent_weather = weather_data.head(days).to_dict('records')
        else:
            recent_weather = weather_data[:days]
            
        if not recent_weather:
            return 0.0
        
        total_precip = sum(d.get('precip_mm', 0.0) for d in recent_weather)
        
        # Oblicz ET dla każdego dnia w okresie
        total_et = 0.0
        for day_data in recent_weather:
            total_et += self.calculate_et_for_today(is_indoor=is_indoor, day_data=day_data)

        water_balance = total_precip + total_irrigation - total_et
        
        return round(water_balance, 1)