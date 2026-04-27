# turf_advisor/engines/physical/nutrition_logic.py

class NutritionLogic:
    def __init__(self, static_profile):
        self.static_profile = static_profile # np. bulk_density, om_pct
        self.soil_data = {} # Będzie ustawiane dynamicznie

        # Standardowe cele MLSN (mg/kg)
        self.mlsn_targets = {
            'P': 21,  # Fosfor
            'K': 37,  # Potas
            'Mg': 24, # Magnez
            'Ca': 350, # Wapń (dla trawników)
            'S': 10,  # Siarka
            'Fe': 50, # Żelazo
            'Mn': 15, # Mangan
            'Zn': 5,  # Cynk
            'Cu': 1,  # Miedź
            'B': 0.5  # Bor
        }
        # Optymalne zakresy wysycenia kationami (%)
        self.optimal_cation_saturation = {
            'K': (3, 5),
            'Mg': (10, 15),
            'Ca': (65, 75)
        }
        # Standardowe zakresy zasobności w suchej masie liści (Model II.12)
        self.tissue_ranges = {
            'N': {'min': 3.0, 'max': 5.0},
            'P': {'min': 0.3, 'max': 0.55},
            'K': {'min': 2.0, 'max': 4.0},
            'Ca': {'min': 0.5, 'max': 1.25},
            'Mg': {'min': 0.2, 'max': 0.5},
            'S': {'min': 0.2, 'max': 0.5},
            'Fe': {'min': 50, 'max': 300},
            'Mn': {'min': 25, 'max': 150},
            'Zn': {'min': 20, 'max': 70},
            'Cu': {'min': 5, 'max': 20},
            'B': {'min': 10, 'max': 30}
        }

    def set_soil_data(self, soil_data):
        """Ustawia dane glebowe dla bieżącej analizy."""
        self.soil_data = self._sanitize_data(soil_data)

    def _sanitize_data(self, data):
        """Automatycznie koryguje drobne błędy w danych (np. pH poza zakresem 0-14)."""
        if not isinstance(data, dict):
            return data
            
        clean = data.copy()
        corrections = []
        
        # 1. Korekta pH do skali logarytmicznej 0-14
        for ph_key in ['ph_h2o', 'ph_hcl']:
            if ph_key in clean and clean[ph_key] is not None:
                original_val = clean[ph_key]
                clean[ph_key] = max(0.0, min(14.0, original_val))
                if clean[ph_key] != original_val:
                    corrections.append(f"{ph_key}: {original_val} -> {clean[ph_key]}")
        
        # 2. Korekta wartości procentowych (0-100)
        pct_keys = ['sand_pct', 'silt_pct', 'clay_pct', 'om_pct']
        for key in pct_keys:
            if key in clean and clean[key] is not None:
                original_val = clean[key]
                clean[key] = max(0.0, min(100.0, original_val))
                if clean[key] != original_val:
                    corrections.append(f"{key}: {original_val} -> {clean[key]}")

        # 3. Zapobieganie wartościom ujemnym dla zasobności i parametrów fizycznych
        numerical_keys = [
            'm3_p', 'm3_k', 'm3_mg', 'm3_ca', 'm3_s', 'm3_na', 'm3_fe', 'm3_mn',
            'm3_b', 'm3_cu', 'm3_zn', 'm3_al', 'hort_p', 'hort_k', 'hort_mg',
            'hort_n_no3', 'hort_n_nh4', 'hort_cl', 'ec_ds_m', 'bulk_density'
        ]
        for key in numerical_keys:
            if key in clean and isinstance(clean[key], (int, float)):
                original_val = clean[key]
                clean[key] = max(0.0, original_val)
                if clean[key] != original_val:
                    corrections.append(f"{key}: {original_val} -> {clean[key]}")

        if corrections:
            print(">>> AUTOMATYCZNA KOREKTA DANYCH (Sanitizacja):")
            for msg in corrections:
                print(f"    - {msg}")
                    
        return clean

    def get_full_mlsn_balance(self):
        """Oblicza pełny bilans MLSN dla wszystkich kluczowych pierwiastków."""
        balance = {}
        for nutrient, target in self.mlsn_targets.items():
            val = self.soil_data.get(f'm3_{nutrient.lower()}')
            current_val = val if val is not None else 0.0
            diff = current_val - target
            status = "OK" if diff >= 0 else "DEFICIT"
            
            # Obliczenie potrzeby w kg/ha (uproszczone)
            # Zakładamy warstwę orną 10 cm (100 mm) i gęstość objętościową z static_profile
            bulk_density = self.static_profile.get('bulk_density', 1.4) # g/cm^3
            soil_mass_kg_ha = bulk_density * 1000 * 1000 # kg/m^2 * 10000 m^2/ha = kg/ha (dla 10cm)
            
            need_kg_ha = 0.0
            if status == "DEFICIT":
                # Różnica w mg/kg * masa gleby w kg/ha / 1,000,000 (mg na kg)
                need_kg_ha = abs(diff) * soil_mass_kg_ha / 1_000_000

            balance[nutrient] = {
                'current': current_val,
                'target': target,
                'diff_mg_kg': diff,
                'status': status,
                'need_kg_ha': round(need_kg_ha, 2)
            }
        return balance

    def get_ph_interpretation(self):
        """Interpretuje poziom pH gleby."""
        val = self.soil_data.get('ph_h2o')
        ph = val if val is not None else 6.5
        status = "Optymalne"
        color = "green"
        if ph < 5.5:
            status = "Bardzo kwaśne"
            color = "red"
        elif 5.5 <= ph < 6.0:
            status = "Kwaśne"
            color = "orange"
        elif 6.0 <= ph < 6.5:
            status = "Lekko kwaśne"
            color = "yellow"
        elif 7.0 < ph <= 7.5:
            status = "Lekko zasadowe"
            color = "yellow"
        elif ph > 7.5:
            status = "Zasadowe"
            color = "red"
        return {'value': ph, 'status': status, 'color': color}

    def get_micros_status(self):
        """Sprawdza status mikroelementów na podstawie MLSN."""
        micros_status = {}
        for micro in ['Fe', 'Mn', 'Cu', 'Zn', 'B']:
            val = self.soil_data.get(f'm3_{micro.lower()}')
            current_val = val if val is not None else 0.0
            target = self.mlsn_targets.get(micro, 0.0)
            status = "OK" if current_val >= target else "DEFICIT"
            micros_status[micro] = {
                'value': current_val,
                'target': target,
                'status': status
            }
        return micros_status

    def check_salinity_risk(self):
        """Ocenia ryzyko zasolenia na podstawie EC i sodu."""
        ec = self.soil_data.get('ec_ds_m') or 0.0
        na = self.soil_data.get('m3_na') or 0.0
        ca = self.soil_data.get('m3_ca') or 0.0
        mg = self.soil_data.get('m3_mg') or 0.0

        # Uproszczony wskaźnik ESP (Exchangeable Sodium Percentage)
        # Wymaga przeliczenia mg/kg na meq/100g i CEC
        # Dla uproszczenia, jeśli Na jest wysokie w stosunku do Ca i Mg, zakładamy ryzyko
        esp_pct = 0.0
        risk_level = "NISKIE"
        leaching_fraction = 0.0 # Procent dodatkowej wody do płukania

        if ec > 0.8: # Próg dla murawy
            risk_level = "ŚREDNIE"
        if ec > 1.2:
            risk_level = "WYSOKIE"
            leaching_fraction = (ec - 1.2) / 1.2 # Bardzo uproszczony wzór

        # Bardzo uproszczone ESP bez CEC
        if (ca + mg) > 0:
            esp_pct = (na / 23) / ((ca / 20) + (mg / 12) + (na / 23)) * 100 # Przeliczenie na meq
            if esp_pct > 10: # Próg dla problemów z sodem
                risk_level = "WYSOKIE"
                leaching_fraction = max(leaching_fraction, 0.15) # Minimum 15% dodatkowej wody

        return {
            'ec_ds_m': ec,
            'na_mg_kg': na,
            'esp_pct': round(esp_pct, 1),
            'risk_level': risk_level,
            'leaching_fraction': round(leaching_fraction, 2)
        }

    def get_cation_saturation_status(self):
        """Oblicza procent wysycenia kompleksu sorpcyjnego dla K, Mg, Ca."""
        # Uproszczone przeliczenie z mg/kg na meq/100g (zakładając gęstość objętościową)
        # Wartości w mg/kg
        k_mgkg = self.soil_data.get('m3_k') or 0.0
        mg_mgkg = self.soil_data.get('m3_mg') or 0.0
        ca_mgkg = self.soil_data.get('m3_ca') or 0.0

        # Przeliczniki na meq/100g (przybliżone)
        k_meq = k_mgkg / 390 # K = 39 g/mol, 1 meq = 39 mg
        mg_meq = mg_mgkg / 120 # Mg = 24 g/mol, 1 meq = 12 mg
        ca_meq = ca_mgkg / 200 # Ca = 40 g/mol, 1 meq = 20 mg

        total_cec_meq = k_meq + mg_meq + ca_meq # Uproszczone CEC

        k_sat_pct = (k_meq / total_cec_meq * 100) if total_cec_meq > 0 else 0
        mg_sat_pct = (mg_meq / total_cec_meq * 100) if total_cec_meq > 0 else 0
        ca_sat_pct = (ca_meq / total_cec_meq * 100) if total_cec_meq > 0 else 0

        return {
            'Total_CEC_meq_100g': round(total_cec_meq, 2),
            'K_saturation_pct': round(k_sat_pct, 1),
            'Mg_saturation_pct': round(mg_sat_pct, 1),
            'Ca_saturation_pct': round(ca_sat_pct, 1),
            'K_status': "OK" if self.optimal_cation_saturation['K'][0] <= k_sat_pct <= self.optimal_cation_saturation['K'][1] else "NIEOPTIMALNE",
            'Mg_status': "OK" if self.optimal_cation_saturation['Mg'][0] <= mg_sat_pct <= self.optimal_cation_saturation['Mg'][1] else "NIEOPTIMALNE",
            'Ca_status': "OK" if self.optimal_cation_saturation['Ca'][0] <= ca_sat_pct <= self.optimal_cation_saturation['Ca'][1] else "NIEOPTIMALNE",
        }

    def get_nitrogen_forms_recommendation(self, current_temp_avg):
        """
        Rekomenduje formy azotu na podstawie temperatury i bieżących poziomów.
        Bazując na Metodzie Ogrodniczej (N-NO3, N-NH4).
        """
        n_no3 = self.soil_data.get('hort_n_no3') or 0.0
        n_nh4 = self.soil_data.get('hort_n_nh4') or 0.0
        total_n_hort = n_no3 + n_nh4

        # Cele dla azotu w mg/dm3 (Metoda Ogrodnicza)
        target_min_n = 15 # mg/dm3

        interpretation = "OK"
        if total_n_hort < target_min_n:
            interpretation = "LOW"
        elif total_n_hort > 30:
            interpretation = "HIGH"

        recommendation = "Monitoruj."
        if interpretation == "LOW":
            if current_temp_avg < 10:
                recommendation = "Zalecane nawożenie azotem w formie azotanowej (NO3) dla szybkiego pobrania."
            elif 10 <= current_temp_avg < 18:
                recommendation = "Zalecane nawożenie azotem w formie amonowej (NH4) lub mocznikowej (NH2)."
            else:
                recommendation = "Zalecane nawożenie azotem w formie mocznikowej (NH2) lub wolno uwalniającej."

        return {
            'current_status': {
                'n_no3_mg_dm3': n_no3,
                'n_nh4_mg_dm3': n_nh4,
                'total_n_mg_dm3': total_n_hort,
                'target_min': target_min_n,
                'interpretation': interpretation
            },
            'recommendation': recommendation
        }

    def get_organic_nitrogen_potential(self):
        """
        Szacuje potencjał mineralizacji azotu organicznego na podstawie OM.
        Bardzo uproszczony model.
        """
        om_pct = self.soil_data.get('om_pct') or 0.0
        if om_pct <= 0:
            return "Brak danych o materii organicznej."

        # Uproszczone założenie: 1-3% azotu organicznego mineralizuje się rocznie
        # Zakładamy, że azot stanowi 5% materii organicznej
        # Masa gleby w kg/ha (warstwa 10 cm)
        bulk_density = self.static_profile.get('bulk_density', 1.4) # g/cm^3
        soil_mass_kg_ha = bulk_density * 1000 * 1000 # kg/ha dla 10cm

        organic_matter_kg_ha = soil_mass_kg_ha * (om_pct / 100)
        organic_nitrogen_kg_ha = organic_matter_kg_ha * 0.05 # Azot stanowi ok. 5% OM

        # Roczna mineralizacja 1-3% azotu organicznego
        mineralized_n_kg_ha_year = organic_nitrogen_kg_ha * 0.02 # Średnio 2%

        return round(mineralized_n_kg_ha_year, 2)

    def get_tissue_status(self, tissue_values):
        """
        Analizuje skład pierwiastków z masy zielonej (Model II.12).
        tissue_values: dict { 'N': 4.2, 'P': 0.25, ... }
        """
        if not tissue_values:
            return None
            
        results = {}
        for element, range_limits in self.tissue_ranges.items():
            val = tissue_values.get(element)
            if val is None:
                continue
                
            status = "OPTIMAL"
            if val < range_limits['min']:
                status = "DEFICIT"
            elif val > range_limits['max']:
                status = "EXCESS"
                
            results[element] = {
                'value': val,
                'status': status,
                'target': f"{range_limits['min']}-{range_limits['max']}"
            }
        return results