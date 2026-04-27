# turf_advisor/config.py

# Flaga włączająca zaawansowane modele statystyczne
ENABLE_PROBABILISTIC = True

# Klucze API (do uzupełnienia przez użytkownika lub środowisko)
WEATHER_API_KEY = ""

# Cele MLSN (Minimum Levels for Sustainable Nutrition) w mg/kg
MLSN_TARGETS = {
    'P': 21.0,
    'K': 37.0,
    'Mg': 47.0,
    'Ca': 331.0,
    'S': 7.0,
    'Fe': 50.0
}

DEFAULT_BULK_DENSITY = 1.55
DEFAULT_ROOT_DEPTH_MM = 150

# Parametry nawadniania
IRRIGATION_THRESHOLD_VMC = 0.15  # Próg krytyczny wilgotności
TARGET_IRRIGATION_VMC = 0.25      # Docelowa wilgotność po podlaniu

# Progi dla modułu wizyjnego
VISION_DGCI_OPTIMAL = 0.57        # Cel dla azotu
VISION_COVERAGE_MIN = 95.0        # Minimalne pokrycie darni (%)

# Parametry wejściowe dla silnika biologicznego i mechanicznego
TEMP_BASE_GDD = 10.0
OPTIMAL_GROWTH_TEMP = 20.0
NORMAL_STRESS_PLAYER = 80.0       # kPa (Nacisk korków zawodnika)
FRICTION_ANGLE_MAX = 35.0