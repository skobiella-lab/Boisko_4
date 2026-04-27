# turf_advisor/exports/excel_exporter.py
import pandas as pd
import os
from datetime import datetime

class ExcelExporter:
    def __init__(self, db_manager):
        self.db = db_manager

    def export_maintenance_log(self, profile_id, output_dir="reports"):
        """
        Eksportuje historię zabiegów do pliku Excel z automatycznym podziałem na arkusze wg kategorii.
        """
        records = self.db.get_maintenance_records(profile_id)
        if not records:
            return None

        df = pd.DataFrame(records)
        
        # Oczyszczanie danych dla Excela (usuwanie stref czasowych dla kompatybilności)
        if 'timestamp' in df.columns:
            df['timestamp'] = pd.to_datetime(df['timestamp']).dt.tz_localize(None)

        # Generowanie ścieżki pliku
        timestamp_str = datetime.now().strftime("%Y%m%d_%H%M")
        filename = f"Dziennik_Zabiegow_Eksport_{timestamp_str}.xlsx"
        filepath = os.path.join(output_dir, filename)
        
        # Upewnij się, że katalog raportów istnieje
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)

        try:
            # openpyxl jest wymagany jako silnik zapisu Excel
            with pd.ExcelWriter(filepath, engine='openpyxl') as writer:
                # 1. Arkusz zbiorczy (Pełna Historia)
                df.to_excel(writer, sheet_name='Pelna_Historia', index=False)
                
                # 2. Arkusze tematyczne dla każdej kategorii zabiegu (action_type)
                if 'action_type' in df.columns:
                    for action_type in df['action_type'].unique():
                        # Nazwa arkusza: usunięcie znaków specjalnych i limit 31 znaków
                        sheet_name = str(action_type).replace('/', '_').replace(':', '_')[:31]
                        df_subset = df[df['action_type'] == action_type]
                        df_subset.to_excel(writer, sheet_name=sheet_name, index=False)
            
            return filepath
        except Exception as e:
            print(f">>> BŁĄD GENEROWANIA EXCEL: {e}")
            return None