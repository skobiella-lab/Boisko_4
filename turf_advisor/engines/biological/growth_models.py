# turf_advisor/engines/biological/growth_models.py
from datetime import datetime

class GrowthModels:
    def __init__(self, static_profile):
        self.static_profile = static_profile # np. om_pct, cn_ratio
        self.weather_history = []
        self.weather_forecast = []
        self.soil_data = {} # Będzie ustawiane dynamicznie

    def set_weather_data(self, weather_history, weather_forecast):
        self.weather_history = weather_history
        self.weather_forecast = weather_forecast

    def set_soil_data(self, soil_data):
        self.soil_data = soil_data

    def calculate_gdd(self, temp_max, temp_min, base_temp=10):
        """
        Oblicza Growing Degree Days (GDD) dla danego dnia.
        Używa metody "Modified Average" (średnia dzienna, jeśli powyżej temp. bazowej).
        """
        avg_temp = (temp_max + temp_min) / 2
        gdd = max(0, avg_temp - base_temp)
        return round(gdd, 1)

    def calculate_gdd_for_today(self, base_temp=10):
        """Oblicza GDD dla dzisiejszego dnia na podstawie danych historycznych."""
        if self.weather_history:
            today_data = self.weather_history[0] # Zakładamy, że pierwszy rekord to dzisiejszy
            temp_max = today_data.get('temp_max', 0)
            temp_min = today_data.get('temp_min', 0)
            return self.calculate_gdd(temp_max, temp_min, base_temp)
        return 0.0

    def get_avg_temp_today(self):
        """Zwraca średnią temperaturę dla dzisiejszego dnia."""
        if self.weather_history:
            return self.weather_history[0].get('temp_avg', 0.0)
        return 0.0

    def growth_potential_pace(self, current_temp_avg=None):
        """
        Oblicza Potencjał Wzrostu (GP) na podstawie temperatury.
        GP = 100% przy optymalnej temperaturze, spada poza nią.
        """
        if current_temp_avg is None:
            current_temp_avg = self.get_avg_temp_today()

        # Optymalny zakres temperatur dla większości traw sportowych (np. życica trwała)
        optimal_min = 18
        optimal_max = 25
        
        # Zakres, w którym wzrost jest możliwy, ale ograniczony
        min_growth_temp = 5
        max_growth_temp = 35

        if current_temp_avg < min_growth_temp or current_temp_avg > max_growth_temp:
            return 0.0 # Brak wzrostu
        elif optimal_min <= current_temp_avg <= optimal_max:
            return 1.0 # 100% potencjału
        elif current_temp_avg < optimal_min:
            # Liniowy spadek od 100% do 0% między optimal_min a min_growth_temp
            return (current_temp_avg - min_growth_temp) / (optimal_min - min_growth_temp)
        else: # current_temp_avg > optimal_max
            # Liniowy spadek od 100% do 0% między optimal_max a max_growth_temp
            return (max_growth_temp - current_temp_avg) / (max_growth_temp - optimal_max)

    def calculate_n_mineralization(self, vmc_sim, current_temp_avg=None):
        """
        Model mineralizacji azotu z materii organicznej (C:N ratio).
        Uproszczony model uwzględniający temperaturę i wilgotność.
        """
        if current_temp_avg is None:
            current_temp_avg = self.get_avg_temp_today()

        om_pct = self.soil_data.get('om_pct') or self.static_profile.get('om_pct', 2.5)
        cn_ratio = self.static_profile.get('cn_ratio', 12) # Typowy dla murawy

        if om_pct <= 0 or cn_ratio <= 0:
            return 0.0

        # Współczynnik temperaturowy (Q10 model, uproszczony)
        temp_factor = max(0, (current_temp_avg - 5) / 20) # Wzrost od 5 do 25 stopni
        
        # Współczynnik wilgotności (optymalny przy VMC ok. 0.2-0.3)
        moisture_factor = 1.0 - abs(vmc_sim - 0.25) * 2 # Spadek, gdy VMC odbiega od 0.25
        moisture_factor = max(0.1, min(moisture_factor, 1.0))

        # Uproszczony współczynnik mineralizacji (kg N/ha/dzień)
        # Zakładamy, że 1-3% azotu organicznego mineralizuje się rocznie
        # i rozkładamy to na dzień, korygując temp. i wilgotnością
        base_mineralization_rate = (om_pct / 100) * 10 # Uproszczony bazowy kg N/ha/rok
        daily_mineralization = (base_mineralization_rate / 365) * temp_factor * moisture_factor

        return round(daily_mineralization, 2)

    def nitrogen_release_model(self, current_temp_avg=None, form='urea'):
        """
        Model uwalniania azotu z różnych form w zależności od temperatury.
        Zwraca procent uwalniania na dzień.
        """
        if current_temp_avg is None:
            current_temp_avg = self.get_avg_temp_today()

        if form == 'urea':
            # Mocznik hydrolizuje szybciej w wyższych temperaturach
            return max(0.01, min(0.15, (current_temp_avg - 5) * 0.005)) # 1-15% dziennie
        elif form == 'nh4':
            # Amonowe formy nitryfikują w zależności od temp. i aktywności mikroorganizmów
            return max(0.005, min(0.1, (current_temp_avg - 8) * 0.003)) # 0.5-10% dziennie
        elif form == 'no3':
            return 1.0 # Azotany są natychmiast dostępne
        return 0.0

    def get_biological_summary(self, t_max, t_min, t_avg, current_vmc):
        """Silnik oblicza kompletny pakiet danych biologicznych."""
        return {
            't_avg': t_avg,
            'gdd_today': self.calculate_gdd(t_max, t_min),
            'growth_potential': self.growth_potential_pace(t_avg),
            'n_mineralization': self.calculate_n_mineralization(current_vmc, t_avg),
            'n_release_model': {
                'urea_release_pct': self.nitrogen_release_model(t_avg, 'urea'),
                'nh4_release_pct': self.nitrogen_release_model(t_avg, 'nh4'),
                'no3_release_pct': self.nitrogen_release_model(t_avg, 'no3')
            }
        }