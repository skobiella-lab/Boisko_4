# database/db_manager.py
import sqlite3
import os
from datetime import datetime
import json

class DatabaseManager:
    def __init__(self, db_path=None):
        if db_path is None:
            # Ustawia ścieżkę bezwzględną względem katalogu głównego projektu
            base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            self.db_path = os.path.join(base_dir, 'data', 'turf_system.db')
        else:
            self.db_path = db_path
        # Upewnij się, że katalog data istnieje
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self.init_db()

    def get_connection(self):
        """Tworzy połączenie z bazą danych i ustawia Row jako słownik."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def init_db(self):
        """Inicjalizuje bazę danych na podstawie pliku schema.sql"""
        # Jeśli plik bazy nie istnieje, zostanie utworzony przy pierwszym połączeniu
        schema_path = os.path.join(os.path.dirname(__file__), 'schema.sql')
        if os.path.exists(schema_path):
            with open(schema_path, 'r') as f:
                schema = f.read()
            with self.get_connection() as conn:
                conn.executescript(schema)
        
        # Wykonaj migrację schematu, aby dodać ewentualne brakujące kolumny
        self.check_and_migrate_schema()

    def save_soil_analysis(self, data_dict):
        """Zapisuje kompletny wynik Mehlich-3 i Metody Ogrodniczej (28 parametrów)"""
        # Walidacja spójności danych przed zapisem
        errors = self.validate_soil_data(data_dict)
        if errors:
            print(">>> BŁĄD WALIDACJI: Dane glebowe nie są spójne:")
            for error in errors:
                print(f"    - {error}")
            return False

        query = """
            INSERT INTO soil_analysis (
                profile_id, date_sampled, ph_h2o, ph_hcl, ec_ds_m,
                m3_p, m3_k, m3_mg, m3_ca, m3_s, m3_na, m3_fe, m3_mn, 
                m3_b, m3_cu, m3_zn, m3_al,
                hort_p, hort_k, hort_mg, hort_n_no3, hort_n_nh4, hort_cl,
                sand_pct, silt_pct, clay_pct, om_pct, bulk_density
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        try:
            values = (
                data_dict.get('profile_id', 1),
                data_dict.get('date_sampled', datetime.now().date().strftime('%Y-%m-%d')),
                data_dict.get('ph_h2o', 6.5),
                data_dict.get('ph_hcl', 0.0),
                data_dict.get('ec_ds_m', 0.0),
                data_dict.get('m3_p', 0.0),
                data_dict.get('m3_k', 0.0),
                data_dict.get('m3_mg', 0.0),
                data_dict.get('m3_ca', 0.0),
                data_dict.get('m3_s', 0.0),
                data_dict.get('m3_na', 0.0),
                data_dict.get('m3_fe', 0.0),
                data_dict.get('m3_mn', 0.0),
                data_dict.get('m3_b', 0.0),
                data_dict.get('m3_cu', 0.0),
                data_dict.get('m3_zn', 0.0),
                data_dict.get('m3_al', 0.0),
                data_dict.get('hort_p', 0.0),
                data_dict.get('hort_k', 0.0),
                data_dict.get('hort_mg', 0.0),
                data_dict.get('hort_n_no3', 0.0),
                data_dict.get('hort_n_nh4', 0.0), 
                data_dict.get('hort_cl', 0.0),
                # Nowe wartości
                data_dict.get('sand_pct', 0.0),
                data_dict.get('silt_pct', 0.0),
                data_dict.get('clay_pct', 0.0),
                data_dict.get('om_pct', 0.0),
                data_dict.get('bulk_density', 0.0)
            )
            with self.get_connection() as conn:
                conn.execute(query, values)
                conn.commit()
                print(">>> SUKCES: Dane glebowe zapisane pomyślnie.")
                return True
        except Exception as e:
            print(f">>> BŁĄD ZAPISU DO BAZY: {e}")
            return False

    def get_latest_soil_analysis(self, profile_id):
        """Pobiera absolutnie ostatni rekord analizy dla danego boiska."""
        query = "SELECT * FROM soil_analysis WHERE profile_id = ? ORDER BY id DESC LIMIT 1"
        try:
            with self.get_connection() as conn:
                row = conn.execute(query, (profile_id,)).fetchone()
                if row:
                    return dict(row) # Zamiana na słownik, aby NutritionEngine mógł czytać klucze
                return None
        except Exception as e:
            print(f">>> BŁĄD ODCZYTU Z BAZY: {e}")
            return None

    def add_maintenance_record(self, profile_id, action_type, amount, product_id=None, timestamp=None):
        """Zapisuje zabieg pielęgnacyjny w dzienniku."""
        if timestamp is None:
            timestamp = datetime.now()
        query = """
            INSERT INTO maintenance_log (profile_id, action_type, amount, product_id, timestamp)
            VALUES (?, ?, ?, ?, ?)
        """
        try:
            with self.get_connection() as conn:
                conn.execute(query, (profile_id, action_type, amount, product_id, timestamp))
                conn.commit()
                print(f">>> DB: Zapisano zabieg {action_type} dla boiska {profile_id}")
                return True
        except Exception as e:
            print(f">>> BŁĄD ZAPISU ZABIEGU: {e}")
            return False

    def delete_maintenance_record(self, record_id):
        """Usuwa wpis z dziennika zabiegów."""
        query = "DELETE FROM maintenance_log WHERE id = ?"
        try:
            with self.get_connection() as conn:
                conn.execute(query, (record_id,))
                conn.commit()
                return True
        except Exception as e:
            print(f">>> BŁĄD USUWANIA ZABIEGU: {e}")
            return False

    def update_maintenance_record(self, record_id, action_type, amount, product_id):
        """Aktualizuje istniejący rekord zabiegu."""
        query = "UPDATE maintenance_log SET action_type = ?, amount = ?, product_id = ? WHERE id = ?"
        try:
            with self.get_connection() as conn:
                conn.execute(query, (action_type, amount, product_id, record_id))
                conn.commit()
                return True
        except Exception as e:
            print(f">>> BŁĄD EDYCJI ZABIEGU: {e}")
            return False

    def get_irrigation_sum(self, profile_id, days=7):
        """Pobiera sumę nawadniania w mm z ostatnich X dni."""
        query = """
            SELECT SUM(amount) FROM maintenance_log 
            WHERE profile_id = ? AND action_type = 'NAWADNIANIE' 
            AND timestamp >= datetime('now', ?)
        """
        try:
            with self.get_connection() as conn:
                row = conn.execute(query, (profile_id, f'-{days} days')).fetchone()
                return row[0] if row and row[0] else 0.0
        except Exception as e:
            return 0.0

    def get_maintenance_records(self, profile_id):
        """Pobiera historię wszystkich zabiegów dla danego boiska."""
        query = "SELECT * FROM maintenance_log WHERE profile_id = ? ORDER BY timestamp DESC"
        try:
            with self.get_connection() as conn:
                rows = conn.execute(query, (profile_id,)).fetchall()
                return [dict(row) for row in rows]
        except Exception as e:
            print(f">>> BŁĄD ODCZYTU DZIENNIKA: {e}")
            return []

    def get_weather_history(self, days=7):
        """Pobiera historię pogody do wykresów i modeli (tylko rzeczywiste dane)."""
        query = "SELECT * FROM weather_history WHERE is_forecast = 0 ORDER BY date DESC LIMIT ?"
        try:
            with self.get_connection() as conn:
                rows = conn.execute(query, (days,)).fetchall()
                # Zwracamy listę słowników dla czytelności w Pandas
                return [dict(row) for row in rows]
        except Exception as e:
            print(f">>> BŁĄD ODCZYTU POGODY: {e}")
            return []

    def get_last_weather_update_date(self):
        """Zwraca datę najnowszego rekordu historycznego zapisanego w bazie danych."""
        query = "SELECT MAX(date) FROM weather_history WHERE is_forecast = 0"
        try:
            with self.get_connection() as conn:
                row = conn.execute(query).fetchone()
                return row[0] if row and row[0] else None
        except Exception as e:
            print(f">>> BŁĄD ODCZYTU OSTATNIEJ DATY POGODY: {e}")
            return None

    def get_weather_forecast(self):
        """Pobiera prognozę pogody (tylko dane prognozy)."""
        from datetime import datetime
        today = datetime.now().date()
        query = "SELECT * FROM weather_history WHERE date >= ? AND is_forecast = 1 ORDER BY date ASC"
        try:
            with self.get_connection() as conn:
                rows = conn.execute(query, (today,)).fetchall()
                # Zwracamy listę słowników dla czytelności w Pandas
                return [dict(row) for row in rows]
        except Exception as e:
            print(f">>> BŁĄD ODCZYTU PROGNOZY: {e}")
            return []

    def save_vision_analysis(self, field_id, dgci, bare_pct=0.0):
        """Zapisuje wynik analizy DGCI i ubytków do historii."""
        query = "INSERT INTO vision_history (field_id, date, dgci, bare_pct) VALUES (?, ?, ?, ?)"
        try:
            with self.get_connection() as conn:
                conn.execute(query, (field_id, datetime.now().strftime('%Y-%m-%d'), dgci, bare_pct))
                conn.commit()
                return True
        except Exception as e:
            print(f">>> BŁĄD ZAPISU ANALIZY WIZYJNEJ: {e}")
            return False

    def get_vision_history(self, field_id):
        """Pobiera historię analiz wizyjnych dla wykresu trendu."""
        query = "SELECT * FROM vision_history WHERE field_id = ? ORDER BY date ASC"
        try:
            with self.get_connection() as conn:
                rows = conn.execute(query, (field_id,)).fetchall()
                return [dict(row) for row in rows]
        except Exception as e:
            print(f">>> BŁĄD ODCZYTU DGCI: {e}")
            return []

    def add_fertilizer(self, fertilizer_data):
        """Dodaje nowy nawóz do bazy danych."""
        query = """
            INSERT INTO fertilizers (
                brand, name, n_total, p_total, k_total, n_no3, n_nh4, n_nh2,
                mg, ca, s, micro_nutrients, is_slow_release, price_per_kg, salt_index
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        try:
            with self.get_connection() as conn:
                conn.execute(query, (
                    fertilizer_data.get('brand', 'N/A'),
                    fertilizer_data.get('name'),
                    fertilizer_data.get('n_total', 0.0),
                    fertilizer_data.get('p_total', 0.0),
                    fertilizer_data.get('k_total', 0.0),
                    fertilizer_data.get('n_no3', 0.0),
                    fertilizer_data.get('n_nh4', 0.0),
                    fertilizer_data.get('n_nh2', 0.0),
                    fertilizer_data.get('mg', 0.0),
                    fertilizer_data.get('ca', 0.0),
                    fertilizer_data.get('s', 0.0),
                    json.dumps(fertilizer_data.get('micro_nutrients', {})), # Zapis jako poprawny JSON
                    fertilizer_data.get('is_slow_release', 0),
                    fertilizer_data.get('price_per_kg', 0.0),
                    fertilizer_data.get('salt_index', 0.0)
                ))
                conn.commit()
                print(f">>> SUKCES: Nawóz '{fertilizer_data.get('name')}' dodany pomyślnie.")
                return True
        except Exception as e:
            print(f">>> BŁĄD DODAWANIA NAWOZU: {e}")
            return False

    def get_all_fertilizers(self):
        """Pobiera wszystkie nawozy z bazy danych."""
        query = "SELECT * FROM fertilizers"
        try:
            with self.get_connection() as conn:
                rows = conn.execute(query).fetchall()
                return [dict(row) for row in rows]
        except Exception as e:
            print(f">>> BŁĄD ODCZYTU NAWOZÓW: {e}")
            return []


    def delete_fertilizer(self, fertilizer_id):
        """Usuwa nawóz z bazy danych."""
        query = "DELETE FROM fertilizers WHERE id = ?"
        try:
            with self.get_connection() as conn:
                conn.execute(query, (fertilizer_id,))
                conn.commit()
                return True
        except Exception as e:
            print(f">>> BŁĄD USUWANIA NAWOZU: {e}")
            return False

    def update_fertilizer(self, fertilizer_id, salt_index):
        """Aktualizuje indeks solny dla istniejącego nawozu."""
        query = "UPDATE fertilizers SET salt_index = ? WHERE id = ?"
        try:
            with self.get_connection() as conn:
                conn.execute(query, (salt_index, fertilizer_id))
                conn.commit()
                return True
        except Exception as e:
            print(f">>> BŁĄD AKTUALIZACJI NAWOZU: {e}")
            return False

    def add_recommendation_record(self, field_id, tier, summary, details):
        """Zapisuje wygenerowaną rekomendację w bazie."""
        query = "INSERT INTO recommendations_log (field_id, timestamp, tier, summary, details) VALUES (?, ?, ?, ?, ?)"
        try:
            with self.get_connection() as conn:
                conn.execute(query, (field_id, datetime.now(), tier, summary, details))
                conn.commit()
                return True
        except Exception as e:
            print(f">>> BŁĄD ZAPISU REKOMENDACJI: {e}")
            return False

    def get_recommendations_history(self, field_id):
        """Pobiera historię rekomendacji dla boiska."""
        query = "SELECT * FROM recommendations_log WHERE field_id = ? ORDER BY timestamp DESC"
        with self.get_connection() as conn:
            return [dict(row) for row in conn.execute(query, (field_id,)).fetchall()]

    def check_and_migrate_schema(self):
        """Sprawdza spójność schematu bazy danych i automatycznie dodaje brakujące kolumny."""
        # Definicja kolumn, które mogły zostać dodane w trakcie rozwoju systemu
        required_migrations = {
            "fertilizers": {
                "salt_index": "REAL DEFAULT 0.0",
                "price_per_kg": "REAL DEFAULT 0.0",
                "n_no3": "REAL DEFAULT 0.0",
                "n_nh4": "REAL DEFAULT 0.0",
                "n_nh2": "REAL DEFAULT 0.0",
                "mg": "REAL DEFAULT 0.0",
                "ca": "REAL DEFAULT 0.0",
                "s": "REAL DEFAULT 0.0",
                "micro_nutrients": "TEXT DEFAULT '{}'",
                "is_slow_release": "INTEGER DEFAULT 0"
            },
            "soil_analysis": {
                "sand_pct": "REAL DEFAULT 0.0",
                "silt_pct": "REAL DEFAULT 0.0",
                "clay_pct": "REAL DEFAULT 0.0",
                "om_pct": "REAL DEFAULT 0.0",
                "bulk_density": "REAL DEFAULT 0.0"
            },
            "vision_history": {
                "bare_pct": "REAL DEFAULT 0.0"
            },
            "recommendations_log": {
                "field_id": "INTEGER",
                "timestamp": "DATETIME",
                "tier": "TEXT",
                "summary": "TEXT",
                "details": "TEXT"
            },
            "weather_history": {
                "is_forecast": "INTEGER DEFAULT 0",
                "humidity": "REAL DEFAULT 70.0"
            }
        }

        with self.get_connection() as conn:
            cursor = conn.cursor()
            for table_name, columns in required_migrations.items():
                # Pobierz listę istniejących kolumn (PRAGMA zwraca id, name, type, notnull, dflt_value, pk)
                cursor.execute(f"PRAGMA table_info({table_name})")
                existing_columns = [row['name'] for row in cursor.fetchall()]
                
                if existing_columns: # Wykonuj tylko jeśli tabela istnieje
                    for col_name, col_def in columns.items():
                        if col_name not in existing_columns:
                            print(f">>> MIGRACJA: Dodawanie brakującej kolumny '{col_name}' do tabeli '{table_name}'...")
                            try:
                                cursor.execute(f"ALTER TABLE {table_name} ADD COLUMN {col_name} {col_def}")
                            except sqlite3.Error as e:
                                print(f">>> BŁĄD MIGRACJI '{col_name}' w tabeli '{table_name}': {e}")
            conn.commit()

    def validate_soil_data(self, data_dict):
        """
        Sprawdza spójność i logiczną poprawność danych glebowych.
        Zwraca listę komunikatów o błędach. Pusta lista oznacza brak błędów.
        """
        errors = []

        # 1. Sprawdzenie zakresu pH (Skala logarytmiczna 0-14)
        for ph_key in ['ph_h2o', 'ph_hcl']:
            val = data_dict.get(ph_key)
            if val is not None and not (0 <= val <= 14):
                errors.append(f"Błąd pH: {ph_key}={val}. Wartość musi mieścić się w zakresie 0-14.")

        # 2. Sprawdzenie wartości ujemnych (Zasobność i EC nie mogą być ujemne)
        numerical_keys = [
            'm3_p', 'm3_k', 'm3_mg', 'm3_ca', 'm3_s', 'm3_na', 'm3_fe', 'm3_mn',
            'm3_b', 'm3_cu', 'm3_zn', 'm3_al', 'hort_p', 'hort_k', 'hort_mg',
            'hort_n_no3', 'hort_n_nh4', 'hort_cl', 'ec_ds_m'
        ]
        for key in numerical_keys:
            val = data_dict.get(key)
            if val is not None and val < 0:
                errors.append(f"Błąd wartości: {key}={val}. Parametry zasobności i EC nie mogą być ujemne.")

        # 3. Sprawdzenie procentowej zawartości frakcji i OM (0-100%)
        pct_keys = ['sand_pct', 'silt_pct', 'clay_pct', 'om_pct']
        for key in pct_keys:
            val = data_dict.get(key)
            if val is not None and not (0 <= val <= 100):
                errors.append(f"Błąd procentowy: {key}={val}. Wartość musi być w zakresie 0-100%.")

        # 4. Sprawdzenie sumy frakcji granulometrycznych (powinna wynosić ok. 100%)
        sand = data_dict.get('sand_pct', 0.0)
        silt = data_dict.get('silt_pct', 0.0)
        clay = data_dict.get('clay_pct', 0.0)
        if any([sand, silt, clay]):
            total_pct = sand + silt + clay
            if not (98.0 <= total_pct <= 102.0):
                errors.append(f"Błąd granulometrii: Suma piasku, pyłu i iłu wynosi {total_pct}%. Powinna oscylować wokół 100%.")

        # 5. Sprawdzenie gęstości objętościowej (musi być dodatnia)
        bd = data_dict.get('bulk_density')
        if bd is not None and bd <= 0:
            errors.append(f"Błąd gęstości objętościowej: {bd}. Wartość musi być większa od zera.")

        return errors
