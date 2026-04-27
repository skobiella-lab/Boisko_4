import math
import pandas as pd

class RiskAnalysis:
    """
    Silnik modeli probabilistycznych (Warstwa 3).
    Konsoliduje modele Smith-Kerns oraz sieci Bayesa.
    """
    def __init__(self):
        pass

    def smith_kerns_dollar_spot(self, weather_df, water_balance=0.0):
        """
        Model Smith-Kerns (2011) - Ryzyko wystąpienia Sclerotinia homoeocarpa.
        P = 1 / (1 + exp(-(-9.99 + 0.18 * T + 0.05 * RH)))
        """
        if weather_df is None or weather_df.empty or len(weather_df) < 5:
            return 0.0

        recent = weather_df.head(5)
        t_mean = recent['temp_avg'].mean()
        rh_mean = recent['humidity'].mean()

        logit = -9.99 + (0.18 * t_mean) + (0.05 * rh_mean)
        
        # Jeśli dane są niekompletne (NaN po średniej), zwróć brak ryzyka
        if pd.isna(logit):
            return 0.0
        
        # Integracja z Bilansem Wodnym: nadmiar wody zwiększa presję infekcyjną
        if water_balance > 0:
            # Każde 5mm nadmiaru wody (powyżej ET i opadu) dodaje bonus do logitu
            # Skalowanie: max +0.5 do logitu przy znacznym przelaniu
            logit += min(0.5, (water_balance / 10.0))
        
        try:
            probability = 1 / (1 + math.exp(-logit))
        except OverflowError:
            probability = 1.0 if logit > 0 else 0.0
            
        return round(probability, 3)

    def get_risk_category(self, prob):
        """Kategoryzacja ryzyka na potrzeby interfejsu."""
        if prob >= 0.7:
            return "WYSOKIE", "warning"
        elif prob >= 0.4:
            return "ŚREDNIE", "info"
        return "NISKIE", "success"

    def calculate_risk_trend(self, df_history):
        """Oblicza trend ryzyka dla ostatnich dni."""
        if df_history.empty or 'temp_avg' not in df_history.columns:
            return []
        risks = []
        for i in range(len(df_history)):
            window = df_history.iloc[max(0, i-4):i+1]
            risks.append(self.smith_kerns_dollar_spot(window))
        return risks

    def bayesian_stress_diagnosis(self, evidence):
        """
        Uproszczona diagnostyka przyczyn stresu murawy za pomocą sieci Bayesa.
        """
        diagnosis = []
        if evidence.get('yellowing', False):
            diagnosis.append({'issue': 'Niedobór Azotu', 'prob': 0.6})
            if evidence.get('high_ph', False):
                diagnosis.append({'issue': 'Stres wysokiego pH', 'prob': 0.4})
        if evidence.get('puddles', False):
            diagnosis.append({'issue': 'Zabagnienie (Waterlogging)', 'prob': 0.8})
        if evidence.get('compaction', False):
            diagnosis.append({'issue': 'Zagęszczenie gleby', 'prob': 0.9})

        return sorted(diagnosis, key=lambda x: x['prob'], reverse=True)