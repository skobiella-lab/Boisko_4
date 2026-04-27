# exports/pdf_generator.py

from fpdf import FPDF
from datetime import datetime
import matplotlib.pyplot as plt
import os
import tempfile
import cv2

class ReportGenerator:
    def __init__(self, field_name):
        self.field_name = field_name
        self.pdf = FPDF()
        self.pdf.set_margins(left=15, top=15, right=15)
        self.pdf.add_page()
        
        self.pdf.set_font("Arial", size=12)

    def _clean_text(self, text):
        """Konwertuje polskie znaki i znaki specjalne na odpowiedniki ASCII."""
        if not isinstance(text, str):
            text = str(text)
        polish_map = str.maketrans(
            "ąćęłńóśźżĄĆĘŁŃÓŚŹŻ•",
            "acelnoszzACELNOSZZ-"
        )
        # Zamiana znanych znaków i usunięcie emoji/nieobsługiwanych symboli
        text = text.translate(polish_map)
        return text.encode('latin-1', 'replace').decode('latin-1')

    def _generate_trend_chart(self, history):
        """Tworzy wykres trendu DGCI i zwraca ścieżkę do pliku tymczasowego PNG."""
        if not history or len(history) < 2:
            return None
        
        dates = [h['date'] for h in history]
        values = [h['dgci'] for h in history]
        
        plt.figure(figsize=(6, 3.5))
        plt.plot(dates, values, marker='o', linestyle='-', color='#2E7D32', linewidth=2)
        plt.title("Trend Wigoru Murawy (Indeks DGCI)", fontsize=12, pad=10)
        plt.ylabel("Wartość DGCI")
        plt.grid(True, linestyle='--', alpha=0.6)
        plt.xticks(rotation=35, fontsize=8)
        plt.tight_layout()
        
        path = os.path.join(tempfile.gettempdir(), f"chart_dgci_{datetime.now().timestamp()}.png")
        plt.savefig(path, dpi=150)
        plt.close() # Zwolnienie pamięci
        return path

    def _save_temp_image(self, image_array, prefix="map"):
        """Zapisuje macierz OpenCV do pliku tymczasowego PNG."""
        if image_array is None:
            return None
        path = os.path.join(tempfile.gettempdir(), f"{prefix}_{datetime.now().timestamp()}.png")
        # OpenCV domyślnie używa BGR, co imwrite obsługuje poprawnie
        cv2.imwrite(path, image_array)
        return path

    def generate_dynamic_report(self, report_data):
        """
        Generuje raport PDF uwzględniający poziom analizy i metodologię (extended).
        """
        advice = report_data['data']
        is_extended = report_data['is_extended']

        # 1. NAGŁÓWEK I METADANE (Użycie szerokości 0 dla auto-marginesów)
        self.pdf.set_font("Arial", 'B', 16)
        self.pdf.cell(0, 10, txt=self._clean_text(f"RAPORT AGROTECHNICZNY: {self.field_name}"), ln=True, align='C')
        self.pdf.set_font("Arial", 'I', 10)
        self.pdf.cell(0, 10, txt=self._clean_text(f"Poziom Inteligencji: {report_data['tier']}"), ln=True, align='C')
        self.pdf.set_font("Arial", size=10)
        self.pdf.cell(0, 10, txt=self._clean_text(f"Data wygenerowania: {datetime.now().strftime('%Y-%m-%d %H:%M')}"), ln=True, align='C')
        self.pdf.ln(10)

        # 2. PODSUMOWANIE OPERACYJNE
        self.pdf.set_font("Arial", 'B', 12)
        self.pdf.cell(0, 10, txt="1. WNIOSKI I REKOMENDACJE DNIA", ln=True)
        self.pdf.set_font("Arial", size=11)
        
        for tip in report_data['summary_tips']:
            self.pdf.multi_cell(0, 8, txt=self._clean_text(f"- {tip}"))
        
        if not report_data['summary_tips']:
            self.pdf.cell(0, 8, txt=self._clean_text("- Brak krytycznych alertow. Kontynuuj standardowa pielegnacje."), ln=True)
        self.pdf.ln(5)

        # 3. DIAGNOSTYKA WIZYJNA (WARUNKOWO)
        if 'vision_summary' in advice and advice['vision_summary'].get('dgci'):
            self.pdf.set_font("Arial", 'B', 11)
            self.pdf.cell(0, 10, txt="Status Wizyjny Murawy:", ln=True)
            v = advice['vision_summary']
            self.pdf.set_font("Arial", size=10)
            self.pdf.cell(0, 7, txt=self._clean_text(f"- Indeks DGCI (Wigor): {v['dgci']} (Cel: >0.57)"), ln=True)
            self.pdf.cell(0, 7, txt=self._clean_text(f"- Pokrycie darni: {100 - v['bare_pct']}% (Ubytki: {v['bare_pct']}%)"), ln=True)

            if 'history' in v:
                chart_path = self._generate_trend_chart(v['history'])
                if chart_path:
                    self.pdf.ln(2)
                    self.pdf.image(chart_path, w=120)
                    self.pdf.ln(5)
                    os.remove(chart_path) # Usunięcie pliku tymczasowego

        # 3a. MAPA PRACY: LOKALIZACJA ZABIEGOW
        if report_data.get('vision_map') is not None:
            self.pdf.add_page() # Mapa pracy na nowej stronie
            self.pdf.set_font("Arial", 'B', 14)
            self.pdf.cell(0, 10, txt="ZALACZNIK: MAPA LOKALIZACJI ZABIEGOW (DOSIEWKI)", ln=True)
            self.pdf.set_font("Arial", size=10)
            self.pdf.multi_cell(0, 6, txt="Obszary zaznaczone na czerwono wymagaja punktowej interwencji agrotechnicznej (dosiewka, regeneracja).")
            map_img_path = self._save_temp_image(report_data['vision_map'])
            if map_img_path:
                self.pdf.image(map_img_path, w=180)
                os.remove(map_img_path)
            self.pdf.ln(5)

        # 4. INTELIGENTNY HARMONOGRAM (TIER 3)
        if report_data['tier'].startswith("3") and 'optimal_schedule' in advice:
            self.pdf.set_font("Arial", 'B', 12)
            self.pdf.cell(0, 10, txt="2. ZOPTYMALIZOWANY PLAN PRAC (GA-Engine)", ln=True)
            self.pdf.set_font("Arial", size=10)
            sched = advice['optimal_schedule']
            self.pdf.cell(0, 7, txt=self._clean_text(f"- Zalecane nawozenie: {sched['best_date_fertilize']}"), ln=True)
            self.pdf.cell(0, 7, txt=self._clean_text(f"- Zalecane koszenie: {sched['best_date_mow']}"), ln=True)
            self.pdf.ln(5)

        # 5. ANALIZA CHEMICZNA GLEBY (Zawsze obecna)
        self.pdf.set_font("Arial", 'B', 12)
        self.pdf.cell(0, 10, txt="3. BILANS SKLADNIKOW (Standard MLSN)", ln=True)
        self.pdf.set_font("Arial", size=10)
        
        for p, d in advice['nutrition']['mlsn_balance'].items():
            line = f"- {p}: {d['current']} mg/kg (MLSN: {d['target']}) - STATUS: {d['status']}"
            self.pdf.cell(0, 7, txt=self._clean_text(line), ln=True)
        self.pdf.ln(5)

        # 2a. KONKRETNE ZABIEGI I HARMONOGRAM
        guidance = advice.get('tier_guidance', {})
        self.pdf.set_font("Arial", 'B', 11)
        self.pdf.cell(0, 8, txt=self._clean_text("KONKRETNE ZABIEGI I DAWKI:"), ln=True)
        self.pdf.set_font("Arial", size=10)
        for treat in guidance.get('treatments', []):
            self.pdf.multi_cell(0, 6, txt=self._clean_text(f"- {treat}"))
        self.pdf.ln(3)
        self.pdf.set_font("Arial", 'B', 11)
        self.pdf.cell(0, 8, txt=self._clean_text("TERMINY REALIZACJI:"), ln=True)
        self.pdf.set_font("Arial", size=10)
        for task in guidance.get('schedule', []):
            self.pdf.cell(0, 6, txt=self._clean_text(f"> {task}"), ln=True)
        self.pdf.ln(5)
        # 6. DODATEK TECHNICZNY (TECHNICAL DEEP DIVE)
        if is_extended and 'technical_reasoning' in report_data:
            self.pdf.add_page()
            self.pdf.set_font("Arial", 'B', 14)
            self.pdf.cell(0, 10, txt="DODATEK TECHNICZNY: DOKUMENTACJA OBLICZEN", ln=True)
            self.pdf.ln(5)
            
            # Sekcja audytu obliczeniowego (Validation Audit)
            self.pdf.set_font("Arial", 'B', 11)
            self.pdf.cell(0, 10, txt="SCIEZKA AUDYTU: Weryfikacja reczna obliczen", ln=True)
            self.pdf.set_font("Arial", size=9)
            for calc in report_data.get('raw_calculations', []):
                self.pdf.cell(0, 6, txt=self._clean_text(f"> {calc}"), ln=True)
            self.pdf.ln(5)

        # 3b. MAPA CIEPLNA: ROZKLAD AZOTU (DGCI HEATMAP OVERLAY)
        if report_data.get('vision_heatmap') is not None:
            self.pdf.add_page()
            self.pdf.set_font("Arial", 'B', 14)
            self.pdf.cell(0, 10, txt="ZALACZNIK: MAPA CZEPLNA WIGORU (DGCI HEATMAP)", ln=True)
            self.pdf.set_font("Arial", size=10)
            self.pdf.multi_cell(0, 6, txt="Ponisza mapa przedstawia nalozenie indeksu DGCI na zdjecie oryginalne, wizualizujac zroznicowanie nasycenia azotem.")
            heatmap_img_path = self._save_temp_image(report_data['vision_heatmap'], prefix="heatmap")
            if heatmap_img_path:
                self.pdf.image(heatmap_img_path, w=180)
                os.remove(heatmap_img_path)
            self.pdf.ln(5)

            # Metodologia wzorów
            self.pdf.set_font("Arial", 'B', 11)
            self.pdf.cell(0, 10, txt="Zastosowane modele matematyczne:", ln=True)
            for model, formula in report_data['technical_reasoning'].items():
                self.pdf.set_font("Arial", 'B', 10)
                self.pdf.cell(0, 8, txt=f"Model: {model}", ln=True)
                self.pdf.set_font("Arial", size=9)
                self.pdf.multi_cell(0, 6, txt=self._clean_text(formula))
                self.pdf.ln(2)

        # Zapis do pliku
        filename = f"reports/Raport_Turf_{datetime.now().strftime('%Y%m%d_%H%M')}.pdf"
        self.pdf.output(filename)
        return filename
