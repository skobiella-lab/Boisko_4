# turf_advisor/engines/advisor_core.py
import pandas as pd
from datetime import datetime, timedelta

# Importy z nowej, uporządkowanej struktury pakietów
from turf_advisor.engines.physical.nutrition_logic import NutritionLogic
from turf_advisor.engines.physical.soil_physics import SoilPhysics
from turf_advisor.engines.biological.growth_models import GrowthModels
from turf_advisor.engines.biological.water_balance import WaterBalance
from turf_advisor.inventory.fertilizer_manager import FertilizerManager
from turf_advisor.inventory.overseeding_manager import OverseedingManager
from turf_advisor.probabilistic.leaching_sim import LeachingSimulation
from turf_advisor.probabilistic.risk_analysis import RiskAnalysis
from turf_advisor.probabilistic.scheduler_opt import SchedulerOptimizer

ColorAnalysis = None
SpectralAnalysis = None
try:
    from turf_advisor.vision.color_analysis import ColorAnalysis
    from turf_advisor.vision.spectral_core import SpectralAnalysis
except (ImportError, ModuleNotFoundError):
    pass

from turf_advisor import agro_tips
from turf_advisor.config import VISION_DGCI_OPTIMAL, VISION_COVERAGE_MIN

class AdvisorCore:
    def __init__(self, db_manager, static_profile):
        self.db = db_manager
        self.profile = static_profile
        self.nut_logic = NutritionLogic(static_profile)
        self.phys_engine = SoilPhysics(static_profile)
        self.growth_models = GrowthModels(static_profile)
        self.fertilizer_manager = FertilizerManager(db_manager)
        self.hydro_engine = WaterBalance(static_profile, db_manager)
        self.overseeding_manager = OverseedingManager()
        self.risk_analysis = RiskAnalysis() if RiskAnalysis else None
        self.leaching_sim = LeachingSimulation(static_profile) if LeachingSimulation else None
        self.scheduler_opt = SchedulerOptimizer()
        self.color_analysis = ColorAnalysis() if ColorAnalysis else None
        self.spectral_analysis = SpectralAnalysis() if SpectralAnalysis else None

    def get_npk_load_summary(self, field_id, days=30):
        """
        Oblicza sumaryczny ładunek NPK (kg/ha) dostarczony w ciągu ostatnich X dni.
        Wykorzystuje dane z Dziennika Zabiegów i Bazy Nawozów.
        """
        records = self.db.get_maintenance_records(field_id)
        if not records:
            return {'n': 0.0, 'p': 0.0, 'k': 0.0, 'days': days}

        cutoff_date = datetime.now() - timedelta(days=days)
        ferts = self.db.get_all_fertilizers()
        fert_lookup = {f['name']: f for f in ferts}

        total_n, total_p, total_k = 0.0, 0.0, 0.0

        for r in records:
            # Konwersja timestampu na obiekt datetime (SQLite zwraca string)
            ts = r['timestamp']
            if isinstance(ts, str):
                ts = datetime.fromisoformat(ts.split('.')[0]) # Obsługa formatu ISO

            if r['action_type'] == 'NAWOZENIE' and ts >= cutoff_date:
                amount = r['amount'] or 0.0
                prod_name = r['product_id']
                
                if prod_name in fert_lookup:
                    f = fert_lookup[prod_name]
                    total_n += amount * (f.get('n_total', 0.0) / 100.0)
                    total_p += amount * (f.get('p_total', 0.0) / 100.0)
                    total_k += amount * (f.get('k_total', 0.0) / 100.0)

        return {
            'n': round(total_n, 2),
            'p': round(total_p, 2),
            'k': round(total_k, 2),
            'days': days
        }

    def get_water_balance_summary(self, field_id, days=7):
        """
        Brain-method: Oblicza rzeczywisty bilans wodny (mm).
        Łączy sumę nawadniania z Dziennika z danymi ET z historii pogody.
        """
        weather_history = self.db.get_weather_history(days=days)
        irrigation_sum = self.db.get_irrigation_sum(field_id, days=days)
        
        # Delegacja obliczeń do silnika hydrologicznego
        balance = self.hydro_engine.calculate_period_water_balance(
            weather_history, 
            days=days, 
            total_irrigation=irrigation_sum
        )
        return balance

    def get_available_fertilizers(self, as_dataframe=False):
        """Pobiera listę nawozów z magazynu przez FertilizerManager."""
        ferts = self.fertilizer_manager.get_available_fertilizers()
        if as_dataframe:
            df = pd.DataFrame(ferts)
            if not df.empty:
                if 'salt_index' not in df.columns:
                    df['salt_index'] = 0.0
                return df[['id', 'brand', 'name', 'n_total', 'p_total', 'k_total', 'salt_index']].rename(columns={
                    'id': 'ID', 'brand': 'Marka', 'name': 'Nazwa', 
                    'n_total': 'N (%)', 'p_total': 'P (%)', 'k_total': 'K (%)',
                    'salt_index': 'Indeks Solny'
                })
            return df
        return ferts

    def analyze_turf_image(self, image_source):
        """Brain-method: Koordynuje silniki wizyjne w celu analizy zdjęcia."""
        if not self.color_analysis: return None
        
        return {
            'dgci': self.color_analysis.calculate_dgci(image_source),
            'patches': self.color_analysis.detect_bare_patches(image_source),
            'heatmap': self.color_analysis.generate_dgci_heatmap(image_source)
        }

    def process_vision_and_save(self, field_id, image_source):
        """Brain-method: Analizuje obraz i archiwizuje wynik w bazie danych."""
        analysis = self.analyze_turf_image(image_source)
        if not analysis:
            return {'success': False, 'error': "Moduł wizyjny niedostępny."}

        dgci_res = analysis['dgci']
        bare_res = analysis['patches']

        save_success = self.db.save_vision_analysis(
            field_id, 
            dgci_res['dgci'], 
            bare_res['bare_pct']
        )

        return {
            'success': save_success,
            'dgci': dgci_res['dgci'],
            'bare_pct': bare_res['bare_pct'],
            'dgci_status': dgci_res['status'],
            'bare_status': bare_res['status'],
            'bare_mask': bare_res.get('mask')
        }

    def get_satellite_analysis(self, lat, lon):
        """Pobiera i interpretuje najnowsze dane satelitarne dla lokalizacji boiska."""
        if not self.spectral_analysis:
            return None
        return self.spectral_analysis.fetch_satellite_data(lat, lon)

    def archive_current_advice(self, field_id, tier, advice_dict):
        """Zapisuje bieżącą poradę do bazy danych historycznych."""
        guidance = advice_dict.get('tier_guidance', {})
        summary = guidance.get('situation', 'Brak podsumowania')
        treatments = "; ".join(guidance.get('treatments', []))
        
        return self.db.add_recommendation_record(
            field_id, tier, summary, treatments
        )

    def export_maintenance_to_excel(self, field_id):
        """Brain-method: Koordynuje eksport dziennika do formatu Excel."""
        from turf_advisor.exports.excel_exporter import ExcelExporter
        exporter = ExcelExporter(self.db)
        return exporter.export_maintenance_log(field_id)

    def get_integrated_advice(self, field_id, tier, weather_hist, weather_forecast, current_vmc, tissue_data=None, selected_fertilizers=None):
        """
        Główny orkiestrator zbierający dane ze wszystkich warstw inteligencji.
        """
        soil_data = self.db.get_latest_soil_analysis(field_id)
        if not soil_data:
            return None

        # Konfiguracja silników
        self.nut_logic.set_soil_data(soil_data)
        self.phys_engine.set_soil_data(soil_data)
        self.growth_models.set_soil_data(soil_data)
        self.hydro_engine.set_soil_data(soil_data)

        # Definicja nawozów używanych do analizy (wybrane przez użytkownika lub wszystkie dostępne)
        effective_ferts = selected_fertilizers if selected_fertilizers is not None else self.fertilizer_manager.get_available_fertilizers()

        # --- WARSTWA 1: FIZYCZNO-CHEMICZNA (Zawsze aktywna) ---
        ph_data = self.nut_logic.get_ph_interpretation()
        mlsn_balance = self.nut_logic.get_full_mlsn_balance()
        cation_saturation = self.nut_logic.get_cation_saturation_status()
        micros_status = self.nut_logic.get_micros_status()
        
        advice = {
            'nutrition': {
                'mlsn_balance': mlsn_balance,
                'ph_interpretation': ph_data,
                'cation_saturation': cation_saturation,
                'micros_status': micros_status,
                'salinity_risk': self.nut_logic.check_salinity_risk(),
                'nitrogen_forms_recommendation': self.nut_logic.get_nitrogen_forms_recommendation(15),
                'organic_nitrogen_potential': self.nut_logic.get_organic_nitrogen_potential()
            },
            'physical': {
                'shear_strength': self.phys_engine.shear_strength_model(current_vmc),
                'odr': self.phys_engine.oxygen_diffusion_rate(current_vmc)
            },
            'warnings': [],
            'tier_guidance': self._get_base_guidance(mlsn_balance, cation_saturation, effective_ferts)
        }

        # Dodaj interpretację tkanki, jeśli dostępna
        if tissue_data:
            advice['tissue'] = self.nut_logic.get_tissue_status(tissue_data)

        # --- WARSTWA 2: BIO-ŚRODOWISKOWA ---
        if tier != "1. Podstawowy (Fizyczno-Chemiczny)":
            t_avg = weather_hist[0]['temp_avg'] if weather_hist else 15
            t_max = weather_hist[0]['temp_max'] if weather_hist else 20
            t_min = weather_hist[0]['temp_min'] if weather_hist else 10
            
            # Aktualizacja rekomendacji azotowej o realną temperaturę
            advice['nutrition']['nitrogen_forms_recommendation'] = self.nut_logic.get_nitrogen_forms_recommendation(t_avg)
            
            # Delegacja obliczeń biologicznych do silnika
            advice['biology'] = self.growth_models.get_biological_summary(t_max, t_min, t_avg, current_vmc)

            # Pobranie danych wizyjnych (Orkiestracja danych historycznych)
            vision_data = self.db.get_vision_history(field_id)
            
            current_dgci = vision_data[-1]['dgci'] if vision_data else VISION_DGCI_OPTIMAL
            last_bare = vision_data[-1].get('bare_pct', 0.0) if vision_data else 0.0

            # Orkiestracja rekomendacji dosiewek (przekazanie surowych danych do silnika)
            advice['biology']['overseeding'] = self.overseeding_manager.recommend_overseeding(
                current_gdd=advice['biology']['gdd_today'],
                current_temp_avg=t_avg,
                weather_forecast=weather_forecast,
                turf_condition_score=current_dgci,
                bare_pct=last_bare
            )
            advice['recommendation'] = self.fertilizer_manager.recommend_fertilizer(mlsn_balance, cation_saturation, advice['biology']['growth_potential'], {'risk_level': 'NISKIE'}, effective_ferts, current_temp=t_avg)
            # Dodanie surowych danych wizyjnych do raportu
            advice['vision_summary'] = {
                'dgci': current_dgci,
                'bare_pct': last_bare,
                'history': vision_data
            }
            advice['tier_guidance'] = self._get_dynamic_guidance(advice, t_avg, effective_ferts)

        # --- WARSTWA 3: OPTYMALIZACYJNO-PROBABILISTYCZNA ---
        if tier == "3. Inteligentny (Optymalizacja i Ryzyko)":
            import pandas as pd
            df_hist = pd.DataFrame(weather_hist) if weather_hist else pd.DataFrame()
            df_fore = pd.DataFrame(weather_forecast) if weather_forecast else pd.DataFrame()
            
            # Smith-Kerns operuje na oknie 5-dniowym, pobieramy więc bilans z tego okresu
            wb_5d = self.get_water_balance_summary(field_id, days=5)

            advice['risk'] = {
                'smith_kerns_dollar_spot': self.risk_analysis.smith_kerns_dollar_spot(df_hist, water_balance=wb_5d)
            }
            
            precip = df_fore['precip_mm'].mean() if not df_fore.empty else 0
            
            # Konwersja stężenia N (mg/dm3) na ładunek (kg/ha) dla warstwy 10cm (Model III.19)
            # Wzór: mg/dm3 * bulk_density * 1.0 (mnożnik dla 10cm)
            bd = soil_data.get('bulk_density') or self.profile.get('bulk_density', 1.55)
            total_n_conc = advice['nutrition']['nitrogen_forms_recommendation']['current_status']['total_n_mg_dm3']
            total_n_load = total_n_conc * bd
            leaching = self.leaching_sim.simulate_nitrogen_leaching(total_n_load, precip)

            # --- OPTYMALIZACJA HARMONOGRAMU (Algorytm Genetyczny) ---
            available_ferts = effective_ferts # Używamy już przefiltrowanych nawozów

            advice['optimal_schedule'] = self.scheduler_opt.optimize_schedule(
                mlsn_balance=mlsn_balance,
                growth_potential=advice['biology']['growth_potential'],
                risk_score=advice['risk']['smith_kerns_dollar_spot'],
                weather_forecast=weather_forecast,
                fertilizers=available_ferts,
                dgci_score=current_dgci,
                days_ahead=7
            )

            # Rekomendacja nawozowa z FertilizerManager
            advice['recommendation'] = self.fertilizer_manager.recommend_fertilizer(
                mlsn_balance, 
                cation_saturation, 
                advice['biology']['growth_potential'] if 'biology' in advice else 0.5,
                leaching,
                available_ferts,
                current_temp=t_avg if 't_avg' in locals() else 15
            )
            # Generowanie ostrzeżeń dla UI
            self._generate_warnings(advice)
            advice['tier_guidance'] = self._get_smart_guidance(advice)

        return advice

    def _get_base_guidance(self, balance, cation_saturation, available_ferts):
        """Generuje zalecenia dla Tier 1 (Tylko deficyty)."""
        actions = []
        
        # Używamy FertilizerManager do rekomendacji konkretnego nawozu
        rec = self.fertilizer_manager.recommend_fertilizer(
            balance, 
            cation_saturation, 
            growth_potential=0.5, # Neutralna wartość dla Tier 1
            leaching_risk={'risk_level': 'NISKIE'}, # Neutralna wartość dla Tier 1
            available_fertilizers=available_ferts,
            current_temp=15 # Neutralna wartość dla Tier 1
        )

        if rec and rec.get('best_fert'):
            actions.append(f"Zastosuj {rec['best_fert']['name']} w dawce {rec['dose']} kg/ha.")
            if rec.get('safety_warning'):
                actions.append(f"Ostrzeżenie: {rec['safety_warning']}")
        elif rec and rec.get('message'):
            actions.append(rec['message'])
        else:
            actions.append("Zasobność optymalna. Brak konieczności nawożenia.")

        return {
            'situation': "Wykryto luki zasobności w profilu glebowym względem norm MLSN.",
            'treatments': actions if actions else ["Zasobność optymalna. Brak konieczności nawożenia."],
            'schedule': ["Najbliższe okno serwisowe (najszybciej jak to możliwe)."]
        }

    def _get_dynamic_guidance(self, advice, t_avg, available_ferts):
        """Generuje zalecenia dla Tier 2 (Biologia + Pogoda)."""
        gp = advice['biology']['growth_potential']
        n_min = advice['biology']['n_mineralization']
        
        msg = f"Potencjał wzrostu wynosi {int(gp*100)}%. "
        if gp > 0.8:
            msg += "Roślina jest w fazie intensywnego metabolizmu. Zwiększone zapotrzebowanie."
        
        # Pobranie deficytu N z silnika form azotowych (Metoda Ogrodnicza) zamiast MLSN
        n_status = advice['nutrition']['nitrogen_forms_recommendation']['current_status']
        n_deficit = max(0, n_status['target_min'] - n_status['total_n_mg_dm3'])
        adj_dose = max(0, n_deficit - (n_min * 7)) # Uwzględnij 7 dni mineralizacji

        treatments = []
        # Używamy FertilizerManager do rekomendacji konkretnego nawozu
        rec = self.fertilizer_manager.recommend_fertilizer(
            advice['nutrition']['mlsn_balance'], 
            advice['nutrition']['cation_saturation'], 
            gp, 
            advice['nutrition']['salinity_risk'], # Używamy ryzyka zasolenia jako uproszczonego leaching_risk
            available_ferts,
            current_temp=t_avg
        )

        if rec and rec.get('best_fert'):
            # Jeśli główny deficyt to N, korygujemy dawkę
            if rec['main_nutrient'] == 'N':
                rec['dose'] = adj_dose # Nadpisujemy dawkę N
                treatments.append(f"Zastosuj {rec['best_fert']['name']} w dawce {round(rec['dose'], 1)} kg/ha (skorygowano o mineralizację).")
            else:
                treatments.append(f"Zastosuj {rec['best_fert']['name']} w dawce {rec['dose']} kg/ha.")
            
            if rec.get('safety_warning'):
                treatments.append(f"Ostrzeżenie: {rec['safety_warning']}")
        elif rec and rec.get('message'):
            treatments.append(rec['message'])
        else:
            treatments.append("Zasobność optymalna. Brak konieczności nawożenia.")

        return {
            'situation': msg,
            'treatments': treatments,
            'schedule': ["Wykonaj w oknie pogodowym T: 15-22°C (najlepiej rano)."]
        }

    def _get_smart_guidance(self, advice):
        """Generuje zalecenia dla Tier 3 (Smart)."""
        rec = advice['recommendation']
        sched = advice['optimal_schedule']
        
        smart_actions = []
        if rec.get('best_fert'):
            smart_actions.append(f"Zastosuj {rec['best_fert']['name']} w dawce {rec['dose']} kg/ha.")
            if rec.get('safety_warning'):
                smart_actions.append(f"Ostrzeżenie: {rec['safety_warning']}")
        if rec.get('micro_recommendations'):
            for m in rec['micro_recommendations']:
                smart_actions.append(f"Dodatek {m['nutrient']}: {m['product']} ({m['dose_kg_ha']} kg/ha).")

        # Bezpieczne pobieranie harmonogramu (Model III.23)
        schedule_list = []
        if sched and 'error' in sched:
            schedule_list.append(f"⚠️ {sched['error']}")
        elif sched and 'best_date_fertilize' in sched:
            schedule_list.append(f"NAWOŻENIE: {sched['best_date_fertilize']} (Optymalne wmycie)")
            schedule_list.append(f"KOSZENIE: {sched['best_date_mow']} (Suche liście, wysoki wigor)")
        else:
            schedule_list.append("Brak wygenerowanego harmonogramu.")

        # Bezpieczne formatowanie ryzyka (obsługa NaN po migracji bazy)
        risk_val = advice['risk'].get('smith_kerns_dollar_spot', 0.0)
        risk_display = int(risk_val * 100) if pd.notnull(risk_val) else 0

        return {
            'situation': f"Optymalizacja pod kątem ryzyka wypłukiwania i chorób (Smith-Kerns: {risk_display}%).",
            'treatments': smart_actions,
            'schedule': schedule_list
        }

    def _generate_warnings(self, advice):
        """Generuje listę tekstowych ostrzeżeń na podstawie wyników silników."""
        # Ostrzeżenia MLSN
        for nut, data in advice['nutrition']['mlsn_balance'].items():
            if data['status'] == 'DEFICIT':
                advice['warnings'].append(f"⚠️ Deficyt {nut}: Brakuje {data['need_kg_ha']} kg/ha.")
        
        # Ostrzeżenia o mikroelementach
        for micro, data in advice['nutrition']['micros_status'].items():
            if data['status'] == 'LOW':
                advice['warnings'].append(f"🟡 Niski poziom {micro}: Zalecane nawożenie dolistne.")

        # Ostrzeżenia fizyczne
        if advice['physical']['shear_strength']['status'] in ['SOFT', 'UNSTABLE']:
            advice['warnings'].append(f"🔴 Niska stabilność murawy: {advice['physical']['shear_strength']['kpa']} kPa.")
            
        # Ostrzeżenia o pH
        ph_info = advice['nutrition']['ph_interpretation']
        if ph_info['status'] in ['Kwaśna', 'Zasadowa']:
            advice['warnings'].append(f"🟡 Nieoptymalne pH ({ph_info['value']}): Możliwa blokada mikroelementów.")

        # Ostrzeżenia wizyjne (Model II.20 & II.25)
        if 'vision_summary' in advice:
            vs = advice['vision_summary']
            if vs['dgci'] < VISION_DGCI_OPTIMAL:
                advice['warnings'].append(f"🟡 Niski wigor darni (DGCI: {vs['dgci']} < {VISION_DGCI_OPTIMAL}). Rozważ korektę N/Fe.")
            if (100 - vs['bare_pct']) < VISION_COVERAGE_MIN:
                advice['warnings'].append(f"🌱 Słabe pokrycie murawy ({100 - vs['bare_pct']}%). Próg optymalny: {VISION_COVERAGE_MIN}%.")

    def get_report_content(self, advice, tier, extended=False, field_id=1, vision_map=None, vision_heatmap=None):
        """
        Przygotowuje ustrukturyzowaną treść do raportu PDF zależną od wybranego Tieru.
        """
        soil_raw = self.db.get_latest_soil_analysis(field_id)
        report_data = {
            'tier': tier,
            'is_extended': extended,
            'summary_tips': agro_tips.get_dynamic_advice(advice),
            'data': advice,
            'vision_map': vision_map,
            'vision_heatmap': vision_heatmap,
            'educational_blocks': {
                'mlsn': agro_tips.get_mlsn_info(),
                'risk_models': agro_tips.get_model_info(),
                'salt_index': agro_tips.get_salt_index_info()
            }
        }
        
        if extended:
            report_data['technical_reasoning'] = agro_tips.get_methodology_details()
            # Budowanie ścieżki audytu dla walidacji ręcznej
            bd = soil_raw.get('bulk_density') or self.profile.get('bulk_density', 1.55)
            soil_mass_t = bd * 1000  # Masa 10cm warstwy na 1ha w tonach

            tech_calc = []
            tech_calc.append(f"[Fizyka] Masa warstwy ornej (10cm): {bd} g/cm3 * 1000 = {soil_mass_t} t/ha")
            
            # Audyt Bilansu Kationów (meq/100g)
            k_m3 = soil_raw.get('m3_k', 0.0) or 0.0
            mg_m3 = soil_raw.get('m3_mg', 0.0) or 0.0
            ca_m3 = soil_raw.get('m3_ca', 0.0) or 0.0
            
            k_meq = k_m3 / 390
            mg_meq = mg_m3 / 120
            ca_meq = ca_m3 / 200
            cec_sum = k_meq + mg_meq + ca_meq
            
            tech_calc.append(f"[Kationy] meq K: {k_m3} / 390 = {round(k_meq, 3)}")
            tech_calc.append(f"[Kationy] meq Mg: {mg_m3} / 120 = {round(mg_meq, 3)}")
            tech_calc.append(f"[Kationy] meq Ca: {ca_m3} / 200 = {round(ca_meq, 3)}")
            tech_calc.append(f"[Kationy] CEC Audit: {round(k_meq,3)} + {round(mg_meq,3)} + {round(ca_meq,3)} = {round(cec_sum, 3)} meq/100g")
            
            # Audyt MLSN dla Potasu (przykład)
            k_data = advice['nutrition']['mlsn_balance'].get('K', {})
            if k_data.get('status') == 'DEFICIT':
                diff = k_data['target'] - k_data['current']
                calc = (diff * soil_mass_t) / 1000
                tech_calc.append(f"[Chemia] Potas: ({k_data['target']}ppm - {k_data['current']}ppm) * {soil_mass_t}t / 1000 = {round(calc, 2)} kg/ha czystego K")

            if 'biology' in advice:
                t_avg = advice['biology'].get('t_avg', 15)
                gp = advice['biology'].get('growth_potential', 0)
                tech_calc.append(f"[Biologia] GP: exp(-0.5 * (({t_avg}C - 20) / 5.5)^2) = {round(gp*100, 1)}%")
                
                gdd = advice['biology'].get('gdd_today', 0)
                tech_calc.append(f"[Biologia] GDD: (T_max + T_min)/2 - 10C = {gdd}")

            if 'risk' in advice:
                prob = advice['risk'].get('smith_kerns_dollar_spot', 0)
                tech_calc.append(f"[Ryzyko] Smith-Kerns: Logit oparty na 5-dniowych srednich. Wynik końcowy P={prob}")

            report_data['raw_calculations'] = tech_calc
            
        return report_data