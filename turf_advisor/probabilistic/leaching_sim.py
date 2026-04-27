import numpy as np

class LeachingSimulation:
    """
    Silnik symulacji Monte Carlo dla ryzyka wypłukania azotu (Warstwa 3).
    """
    def __init__(self, static_profile):
        self.profile = static_profile

    def simulate_nitrogen_leaching(self, current_n_total, forecast_precip, iterations=1000):
        """
        Symuluje utratę azotu uwzględniając strukturę gleby i błąd prognozy.
        """
        sand_pct = self.profile.get('sand_pct', 90.0)
        # Współczynnik bazowy: piasek wypłukuje się szybciej
        leach_factor_base = (sand_pct / 100.0) * 0.02

        # Modelowanie niepewności opadu
        std_dev = forecast_precip * 0.3 + 2.0
        simulated_precip = np.random.normal(forecast_precip, std_dev, iterations)
        simulated_precip = np.maximum(0, simulated_precip)

        losses = []
        for p in simulated_precip:
            if p > 5:
                # Nieliniowy efekt ulewy (Model III.19)
                loss_pct = (p * leach_factor_base) * (1 + (p / 20))
                loss_kg = current_n_total * min(loss_pct, 0.8)
            else:
                loss_kg = 0
            losses.append(loss_kg)

        avg_loss = np.mean(losses)
        ci_low = np.percentile(losses, 5)
        ci_high = np.percentile(losses, 95)

        risk_level = "NISKIE"
        if avg_loss > (current_n_total * 0.15):
            risk_level = "WYSOKIE"
        elif avg_loss > (current_n_total * 0.05):
            risk_level = "ŚREDNIE"

        return {
            'avg_loss_kg': round(float(avg_loss), 2),
            'confidence_interval': (round(float(ci_low), 2), round(float(ci_high), 2)),
            'risk_level': risk_level,
            'simulated_precip_avg': round(float(np.mean(simulated_precip)), 1)
        }