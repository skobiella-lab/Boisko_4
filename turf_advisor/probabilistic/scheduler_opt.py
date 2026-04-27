# turf_advisor/probabilistic/scheduler_opt.py
import random
from datetime import timedelta, datetime
import pandas as pd

class SchedulerOptimizer:
    def __init__(self):
        # Parametry algorytmu genetycznego
        self.population_size = 50
        self.generations = 100
        self.mutation_rate = 0.1
        self.crossover_rate = 0.8

    def _fitness_function(self, schedule, mlsn_balance, growth_potential, risk_score, weather_forecast_df, fertilizers, dgci_score=None):
        """
        Funkcja oceny dopasowania harmonogramu.
        Wyższa wartość = lepszy harmonogram.
        """
        score = 0
        
        # 1. Ocena zabiegu NAWOŻENIA
        if 'FERTILIZE' in schedule:
            fert_date = schedule['FERTILIZE']['date'].strftime('%Y-%m-%d')
            day_weather = weather_forecast_df[weather_forecast_df['date'] == fert_date]
            
            if not day_weather.empty:
                w = day_weather.iloc[0]
                precip = w.get('precip_mm', 0)
                temp = w.get('temp_avg', 20)
                
                # Model III.19: Ryzyko wypłukania vs wmycie
                if precip > 8:
                    score -= 60 # Kara za silny deszcz (utrata azotu)
                elif 1 <= precip <= 4:
                    score += 20 # Bonus za naturalne wmycie doglebowe
                
                # Bezpieczeństwo chemiczne
                if temp > 28:
                    score -= 40 # Ryzyko przypalenia liści (stres termiczny)
                
                # Wykorzystanie okna wzrostu (Model II.11)
                if growth_potential > 0.7:
                    score += 25
                elif growth_potential < 0.2:
                    score -= 30 # Roślina w spoczynku nie pobierze składników

            # Model III.24: Blokada azotu przy wysokim ryzyku chorobowym (Smith-Kerns)
            if risk_score > 0.5:
                score -= 500 # Potężna kara blokująca zabieg N przy ryzyku > 50%

            # Pilność MLSN (Warstwa 1)
            deficits = sum(1 for d in mlsn_balance.values() if d.get('status') == 'DEFICIT')
            score += deficits * 15

            # 4. Korekta na podstawie wigoru (Model III.25 - DGCI)
            if dgci_score is not None:
                if dgci_score < 0.55:
                    # Wykryto głód azotowy/niski wigor - priorytet dla nawożenia
                    score += 50
                elif dgci_score > 0.65:
                    # Murawa jest nasycona - unikamy nadmiaru N
                    score -= 20

        # 2. Ocena zabiegu KOSZENIA
        if 'MOW' in schedule:
            mow_date = schedule['MOW']['date'].strftime('%Y-%m-%d')
            day_weather = weather_forecast_df[weather_forecast_df['date'] == mow_date]
            
            if not day_weather.empty:
                w = day_weather.iloc[0]
                # Fizyka murawy: nigdy nie kosimy mokrej trawy
                if w.get('precip_mm', 0) > 1:
                    score -= 100
                
                # Regeneracja po koszeniu
                if growth_potential > 0.8:
                    score += 15 

        return score

    def _generate_individual(self, start_date, end_date):
        """Generuje losowy harmonogram (osobnika)."""
        num_days = (end_date - start_date).days
        
        # Losowy dzień na nawożenie
        fert_day_offset = random.randint(0, num_days)
        fert_date = start_date + timedelta(days=fert_day_offset)

        # Losowy dzień na koszenie (może być ten sam)
        mow_day_offset = random.randint(0, num_days)
        mow_date = start_date + timedelta(days=mow_day_offset)

        return {
            'FERTILIZE': {'date': fert_date},
            'MOW': {'date': mow_date}
        }

    def _crossover(self, parent1, parent2):
        """Krzyżowanie - wymiana genów (zabiegów) między rodzicami."""
        child = parent1.copy()
        if random.random() < 0.5:
            child['FERTILIZE'] = parent2['FERTILIZE']
        if random.random() < 0.5:
            child['MOW'] = parent2['MOW']
        return child

    def _mutate(self, individual, start_date, end_date):
        """Mutacja - losowa zmiana daty wybranego zabiegu."""
        num_days = (end_date - start_date).days
        if random.random() < self.mutation_rate:
            target = random.choice(['FERTILIZE', 'MOW'])
            individual[target] = {'date': start_date + timedelta(days=random.randint(0, num_days))}
        return individual

    def optimize_schedule(self, mlsn_balance, growth_potential, risk_score, weather_forecast, fertilizers, dgci_score=None, days_ahead=7):
        """
        Optymalizuje harmonogram zabiegów (nawożenie, koszenie)
        za pomocą algorytmu genetycznego.
        """
        start_date = datetime.now().date()
        end_date = start_date + timedelta(days=days_ahead)

        # Sprawdzenie czy prognoza zawiera wymagane kolumny i dane (Model III.23)
        df_temp = pd.DataFrame(weather_forecast)
        if df_temp.empty or 'temp_avg' not in df_temp.columns:
            return {'error': "Brak aktualnej prognozy w bazie. Kliknij 'Aktualizuj pogodę' w panelu bocznym."}
        
        weather_forecast_df = pd.DataFrame(weather_forecast)

        population = [self._generate_individual(start_date, end_date) for _ in range(self.population_size)]

        for generation in range(self.generations):
            # Ocena populacji
            fitness_scores = [(self._fitness_function(ind, mlsn_balance, growth_potential, risk_score, weather_forecast_df, fertilizers, dgci_score), ind) for ind in population]
            fitness_scores.sort(key=lambda x: x[0], reverse=True)

            # Elityzm - zachowanie 10% najlepszych
            new_population = [ind for _, ind in fitness_scores[:max(1, int(self.population_size * 0.1))]]
            
            # Ewolucja
            while len(new_population) < self.population_size:
                # Selekcja (turniejowa z najlepszej połowy)
                p1 = random.choice(fitness_scores[:self.population_size // 2])[1]
                p2 = random.choice(fitness_scores[:self.population_size // 2])[1]
                
                # Krzyżowanie
                if random.random() < self.crossover_rate:
                    child = self._crossover(p1, p2)
                else:
                    child = p1.copy()
                
                # Mutacja
                child = self._mutate(child, start_date, end_date)
                new_population.append(child)
            
            population = new_population

        # Końcowa ocena
        fitness_scores = [(self._fitness_function(ind, mlsn_balance, growth_potential, risk_score, weather_forecast_df, fertilizers, dgci_score), ind) for ind in population]
        fitness_scores.sort(key=lambda x: x[0], reverse=True)
        best_fitness, best_schedule = fitness_scores[0]
        
        # Dodaj dane pogodowe dla najlepszego dnia
        if 'FERTILIZE' in best_schedule:
            fert_date_str = best_schedule['FERTILIZE']['date'].strftime('%Y-%m-%d')
            fert_weather = weather_forecast_df[weather_forecast_df['date'] == fert_date_str]
            if not fert_weather.empty:
                best_schedule['FERTILIZE']['weather'] = fert_weather.iloc[0].to_dict()
        
        if 'MOW' in best_schedule:
            mow_date_str = best_schedule['MOW']['date'].strftime('%Y-%m-%d')
            mow_weather = weather_forecast_df[weather_forecast_df['date'] == mow_date_str]
            if not mow_weather.empty:
                best_schedule['MOW']['weather'] = mow_weather.iloc[0].to_dict()

        return {
            'best_date_fertilize': best_schedule['FERTILIZE']['date'].strftime('%Y-%m-%d'),
            'best_date_mow': best_schedule['MOW']['date'].strftime('%Y-%m-%d'),
            'best_schedule': best_schedule,
            'best_fitness_score': best_fitness
        }