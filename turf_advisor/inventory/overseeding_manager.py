# turf_advisor/inventory/overseeding_manager.py

class OverseedingManager:
    def __init__(self):
        # Można tu przechowywać dane o gatunkach traw, ich wymaganiach GDD itp.
        self.grass_species_data = {
            'Lolium perenne': {'gdd_base': 5, 'optimal_temp_min': 15, 'optimal_temp_max': 25, 'icon': '🌾'},
            'Poa pratensis': {'gdd_base': 10, 'optimal_temp_min': 18, 'optimal_temp_max': 28, 'icon': '🌿'},
            # ... inne gatunki
        }

    def recommend_overseeding(self, current_gdd, current_temp_avg, weather_forecast, turf_condition_score, bare_pct=0.0):
        """
        Silnik samodzielnie wylicza potrzebne mu parametry z danych pogodowych i wizyjnych.
        """
        coverage_pct = 100.0 - bare_pct
        forecast_temp_avg = sum(d.get('temp_avg', current_temp_avg) for d in weather_forecast) / len(weather_forecast) if weather_forecast else current_temp_avg

        if turf_condition_score >= 0.7 and coverage_pct >= 95.0:
            return {"status": "Brak pilnej potrzeby dosiewek.", "icon": "✅"}

        if current_gdd < 50 or not (10 <= current_temp_avg <= 25):
            return {"status": "Warunki niesprzyjające kiełkowaniu (GDD/Temp).", "icon": "⏳"}

        # Wybór gatunku na podstawie prognozowanej temperatury
        suggested_species = None
        for species, reqs in self.grass_species_data.items():
            if reqs['optimal_temp_min'] <= forecast_temp_avg <= reqs['optimal_temp_max']:
                suggested_species = species
                break

        if suggested_species:
            icon = self.grass_species_data[suggested_species]['icon']
            return {
                "status": f"Zalecane dosiewki: {suggested_species}. Prognoza: {round(forecast_temp_avg, 1)}°C.",
                "icon": icon
            }
        
        return {"status": "Zalecane dosiewki. Dobierz mieszankę uniwersalną.", "icon": "🌱"}