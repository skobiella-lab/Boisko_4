# turf_advisor/inventory/fertilizer_manager.py
import json

class FertilizerManager:
    def __init__(self, db_manager):
        self.db = db_manager

    def get_available_fertilizers(self):
        """Pobiera wszystkie dostępne nawozy z bazy danych."""
        fertilizers = self.db.get_all_fertilizers()
        # Konwertuj micro_nutrients z JSON string na dict
        for fert in fertilizers:
            if fert.get('micro_nutrients'):
                try:
                    fert['micro_nutrients'] = json.loads(fert['micro_nutrients'])
                except json.JSONDecodeError:
                    fert['micro_nutrients'] = {}
            else:
                fert['micro_nutrients'] = {}
        return fertilizers

    def add_fertilizer_to_db(self, fertilizer_data):
        """Dodaje nowy nawóz do bazy danych."""
        return self.db.add_fertilizer(fertilizer_data)

    def recommend_fertilizer(self, mlsn_balance, cation_saturation, growth_potential, leaching_risk, available_fertilizers, current_temp=20):
        """
        Rekomenduje najlepszy nawóz z dostępnych, aby pokryć deficyty MLSN,
        uwzględniając bilans kationów, potencjał wzrostu i ryzyko wypłukiwania.
        """
        if not available_fertilizers:
            return {'error': "Brak dostępnych nawozów w magazynie."}

        # 1. Określ główny deficyt (największy deficyt MLSN lub problem z kationami)
        main_deficit_nutrient = None
        max_deficit_kg_ha = 0

        for nut, data in mlsn_balance.items():
            if data['status'] == 'DEFICIT' and data['need_kg_ha'] > max_deficit_kg_ha:
                main_deficit_nutrient = nut
                max_deficit_kg_ha = data['need_kg_ha']
        
        # Priorytet dla kationów, jeśli są poza optymalnym zakresem
        if cation_saturation['K_status'] != "OK" and cation_saturation['K_saturation_pct'] < 3:
            main_deficit_nutrient = 'K'
        elif cation_saturation['Mg_status'] != "OK" and cation_saturation['Mg_saturation_pct'] < 10:
            main_deficit_nutrient = 'Mg'
        elif cation_saturation['Ca_status'] != "OK" and cation_saturation['Ca_saturation_pct'] < 65:
            main_deficit_nutrient = 'Ca'

        # 2. Filtruj nawozy, które mogą pomóc w głównym deficycie
        candidate_ferts = []
        if main_deficit_nutrient:
            for fert in available_fertilizers:
                # Sprawdź, czy nawóz zawiera główny deficytowy składnik
                if main_deficit_nutrient == 'N' and fert.get('n_total', 0) > 0:
                    candidate_ferts.append(fert)
                elif main_deficit_nutrient == 'P' and fert.get('p_total', 0) > 0:
                    candidate_ferts.append(fert)
                elif main_deficit_nutrient == 'K' and fert.get('k_total', 0) > 0:
                    candidate_ferts.append(fert)
                elif main_deficit_nutrient in ['Mg', 'Ca', 'S']:
                    if fert.get(main_deficit_nutrient.lower(), 0) > 0:
                        candidate_ferts.append(fert)

        # 3. Wybierz najlepszy nawóz spośród kandydatów
        best_fert = None
        best_dose = 0
        best_n_load = 0
        
        if candidate_ferts:
            for fert in candidate_ferts:
                dose_kg_ha = 0
                if main_deficit_nutrient == 'N':
                    dose_kg_ha = mlsn_balance['N']['need_kg_ha'] / (fert['n_total'] / 100)
                elif main_deficit_nutrient == 'P':
                    dose_kg_ha = mlsn_balance['P']['need_kg_ha'] / (fert['p_total'] / 100)
                elif main_deficit_nutrient == 'K':
                    dose_kg_ha = mlsn_balance['K']['need_kg_ha'] / (fert['k_total'] / 100)
                elif main_deficit_nutrient in ['Mg', 'Ca', 'S']:
                    content = fert.get(main_deficit_nutrient.lower(), 0)
                    if content > 0:
                        dose_kg_ha = mlsn_balance[main_deficit_nutrient]['need_kg_ha'] / (content / 100)

                if dose_kg_ha > 0:
                    n_load_for_dose = dose_kg_ha * (fert.get('n_total', 0) / 100)
                    if best_fert is None:
                        best_fert = fert
                        best_dose = dose_kg_ha
                        best_n_load = n_load_for_dose

        # 4. Analiza mikroelementów (Model I.4) - Obliczanie dawek na podstawie deficytów Mehlich-3
        micro_recommendations = []
        for micro in ['Fe', 'Mn', 'Zn', 'Cu', 'B']:
            if mlsn_balance.get(micro) and mlsn_balance[micro]['status'] == 'DEFICIT':
                need_kg = mlsn_balance[micro]['need_kg_ha']
                
                best_micro_source = None
                best_micro_dose = 0
                
                for fert in available_fertilizers:
                    micros = fert.get('micro_nutrients', {})
                    if not isinstance(micros, dict): continue
                    
                    content_pct = micros.get(micro, 0.0)
                    if content_pct > 0:
                        # Dawka = Potrzeba (kg/ha) / (Zawartość (%) / 100)
                        calc_dose = need_kg / (content_pct / 100)
                        
                        # Wybieramy źródło o najwyższym stężeniu (specjalistyczne)
                        current_max = 0
                        if best_micro_source:
                            current_max = best_micro_source.get('micro_nutrients', {}).get(micro, 0)
                        
                        if best_micro_source is None or content_pct > current_max:
                            best_micro_source = fert
                            best_micro_dose = calc_dose
                
                if best_micro_source:
                    micro_recommendations.append({
                        'nutrient': micro,
                        'need_kg_ha': round(need_kg, 3),
                        'product': best_micro_source['name'],
                        'dose_kg_ha': round(best_micro_dose, 2)
                    })

        if not best_fert and not micro_recommendations:
            return {'message': "Brak deficytów makro i mikroelementów wg MLSN."}

        safety_warning = None
        if growth_potential < 0.2: # Jeśli GP jest bardzo niskie
            safety_warning = "Potencjał wzrostu jest zbyt niski. Nawożenie doglebowe może być nieefektywne lub szkodliwe."
        if leaching_risk['risk_level'] == 'WYSOKIE' and best_fert and not best_fert.get('is_slow_release', 0):
            safety_warning = "Wysokie ryzyko wypłukiwania azotu. Rozważ nawóz wolno uwalniający (CRF)."

        return {
            'main_nutrient': main_deficit_nutrient,
            'best_fert': best_fert,
            'dose': round(best_dose, 2) if best_fert else 0,
            'n_load': round(best_n_load, 2) if best_fert else 0,
            'safety_warning': safety_warning,
            'micro_recommendations': micro_recommendations
        }