# turf_advisor/engines/physical/soil_physics.py
import math
from turf_advisor.config import NORMAL_STRESS_PLAYER, FRICTION_ANGLE_MAX

class SoilPhysics:
    def __init__(self, static_profile):
        self.static_profile = static_profile # np. bulk_density, sand_pct, silt_pct, clay_pct
        self.soil_data = {} # Będzie ustawiane dynamicznie

    def set_soil_data(self, soil_data):
        """Ustawia dane glebowe dla bieżącej analizy."""
        self.soil_data = soil_data

    def calculate_water_retention(self, vmc_sim):
        """
        Uproszczony model retencji wody na podstawie granulometrii i VMC.
        Zwraca status retencji i sugerowany poziom nawadniania.
        """
        sand_pct = self.soil_data.get('sand_pct') or self.static_profile.get('sand_pct', 70.0)
        silt_pct = self.soil_data.get('silt_pct') or self.static_profile.get('silt_pct', 15.0)
        clay_pct = self.soil_data.get('clay_pct') or self.static_profile.get('clay_pct', 15.0)

        # Uproszczone wartości dla punktu więdnięcia (PWP) i polowej pojemności wodnej (FC)
        # Wartości orientacyjne dla różnych typów gleb (VMC)
        if sand_pct > 80: # Piasek
            pwp = 0.05
            fc = 0.15
        elif clay_pct > 30: # Glina
            pwp = 0.20
            fc = 0.35
        else: # Średnia
            pwp = 0.10
            fc = 0.25

        status = "Optymalna"
        recommendation = "Brak potrzeby nawadniania."
        if vmc_sim < pwp:
            status = "Poniżej punktu więdnięcia"
            recommendation = "Pilne nawadnianie!"
        elif vmc_sim < fc * 0.7: # Poniżej 70% FC
            status = "Niska wilgotność"
            recommendation = "Zalecane nawadnianie."
        elif vmc_sim > fc * 1.1: # Powyżej 110% FC (przesycenie)
            status = "Nadmierna wilgotność"
            recommendation = "Wstrzymaj nawadnianie, ryzyko niedotlenienia."

        return {
            'vmc_sim': vmc_sim,
            'pwp': pwp,
            'fc': fc,
            'status': status,
            'recommendation': recommendation
        }

    def air_filled_porosity(self, vmc_sim):
        """
        Oblicza porowatość wypełnioną powietrzem (AFP) na podstawie VMC i gęstości objętościowej.
        AFP > 10-12% jest optymalne dla wzrostu korzeni.
        """
        bulk_density = self.static_profile.get('bulk_density', 1.4) # g/cm^3
        particle_density = 2.65 # g/cm^3 (standard dla minerałów glebowych)

        total_porosity = 1 - (bulk_density / particle_density)
        air_filled_porosity = total_porosity - vmc_sim

        air_pct = round(air_filled_porosity * 100, 1)
        status = "OK"
        if air_pct < 10:
            status = "NISKIE (ryzyko niedotlenienia)"
        elif air_pct > 30:
            status = "WYSOKIE (szybkie przesychanie)"

        return {
            'total_porosity': round(total_porosity, 2),
            'air_filled_porosity': round(air_filled_porosity, 2),
            'air_pct': air_pct,
            'status': status
        }

    def shear_strength_model(self, vmc_sim, root_density_index=1.0):
        """
        Model Odporności na Ścinanie (Parametr Coulomba-Mohra - Model II.8).
        Przewiduje stabilność murawy pod korkiem zawodnika.
        """
        # Kohezja (c) zależy głównie od gęstości korzeni i w mniejszym stopniu od materii organicznej
        base_cohesion = 12.0
        root_reinforcement = 25.0 * root_density_index
        om_pct = self.soil_data.get('om_pct') or self.static_profile.get('om_pct', 2.0)
        om_effect = om_pct * 1.5

        cohesion = base_cohesion + root_reinforcement + om_effect

        # Kąt tarcia wewnętrznego (phi) maleje wraz z wilgotnością (vmc)
        friction_angle = FRICTION_ANGLE_MAX
        if vmc_sim > 0.25:
            friction_angle -= (vmc_sim - 0.25) * 40

        # Naprężenie normalne (sigma) od zawodnika
        sigma = NORMAL_STRESS_PLAYER

        shear_strength = cohesion + sigma * math.tan(math.radians(friction_angle))

        # Interpretacja wyników
        if shear_strength > 70: status = "EXCELLENT"
        elif shear_strength > 50: status = "GOOD"
        elif shear_strength > 35: status = "SOFT"
        else: status = "UNSTABLE"

        return {'kpa': round(shear_strength, 2), 'status': status}

    def oxygen_diffusion_rate(self, vmc_sim):
        """
        Modelowanie Wymiany Gazowej - ODR (Model II.7).
        Oblicza wskaźnik dyfuzji tlenu (µg/cm²/min) na podstawie AFP.
        """
        bd = self.static_profile.get('bulk_density', 1.55)
        porosity = 1 - (bd / 2.65)
        air_filled_porosity = porosity - vmc_sim

        odr_value = air_filled_porosity * 250
        
        status = "OPTIMAL"
        if odr_value < 20: status = "CRITICAL"
        elif odr_value < 40: status = "LIMITED"

        return {'odr': round(odr_value, 2), 'status': status, 'afp': round(air_filled_porosity, 3)}