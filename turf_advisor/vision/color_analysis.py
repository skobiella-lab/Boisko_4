# vision/color_analysis.py

import cv2
import numpy as np

class ColorAnalysis:
    def __init__(self):
        pass

    def calculate_dgci(self, image_source):
        """
        Oblicza Dark Green Color Index (DGCI).
        image_source: ścieżka do pliku (str) LUB macierz numpy (obraz).
        """
        img = self._load_image(image_source)

        if img is None:
            return {'dgci': 0.0, 'status': "Błąd odczytu obrazu"}

        # Konwersja do przestrzeni HSV (Hue, Saturation, Value) - standard dla DGCI
        hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)

        # MASKOWANIE: Filtrujemy tylko zakresy zbliżone do zieleni/żółcieni
        # Hue 25-95 (w skali OpenCV) obejmuje odcień od żółtawego do ciemnozielonego
        lower_green = np.array([25, 40, 40])
        upper_green = np.array([95, 255, 255])
        mask = cv2.inRange(hsv, lower_green, upper_green)

        # Pobieramy piksele, które przeszły przez maskę (tylko trawa)
        green_pixels = hsv[mask > 0]

        if len(green_pixels) == 0:
            return {'dgci': 0.0, 'status': "Nie wykryto trawy na zdjęciu"}

        # Wyciągamy średnie wartości tylko z zielonych pikseli
        avg_h = np.mean(green_pixels[:, 0])  # Hue (0-179)
        avg_s = np.mean(green_pixels[:, 1])  # Saturation (0-255)
        avg_v = np.mean(green_pixels[:, 2])  # Value (0-255)

        # 1. Przeliczenie Hue na stopnie (OpenCV h * 2) i normalizacja
        # Zakres dla trawy: 60 (żółty) do 120 (zielony). 
        # Formuła: (Hue - 60) / 60
        hue_degrees = avg_h * 2
        h_term = (hue_degrees - 60) / 60
        h_term = max(0, min(1, h_term)) # Ograniczenie do zakresu 0-1

        # 2. Normalizacja Saturation i Brightness (skala 0-1)
        s_norm = avg_s / 255.0
        v_norm = avg_v / 255.0

        # 3. Obliczenie DGCI zgodnie z Karcher & Richardson (2003):
        # DGCI = [(Hue - 60)/60 + (1 - Saturation) + (1 - Brightness)] / 3
        dgci = (h_term + (1 - s_norm) + (1 - v_norm)) / 3

        status = "Optymalny wigor (N/Fe)" if dgci > 0.55 else "Niski wigor - możliwy głód"
        return {'dgci': round(float(dgci), 3), 'status': status}

    def detect_bare_patches(self, image_source):
        """
        Wykrywa ubytki (puste place) na murawie.
        Zwraca procent pokrycia trawy.
        """
        img = self._load_image(image_source)
        if img is None:
            return {'cover_pct': 0.0, 'status': "Błąd odczytu"}

        hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)

        # Rozszerzony zakres zieleni dla lepszej detekcji w różnych warunkach oświetleniowych
        lower_green = np.array([30, 30, 30])
        upper_green = np.array([90, 255, 255])
        mask = cv2.inRange(hsv, lower_green, upper_green)
        
        # Obliczanie proporcji
        total_pixels = mask.shape[0] * mask.shape[1]
        green_pixels = cv2.countNonZero(mask)
        green_ratio = green_pixels / total_pixels

        # GENEROWANIE MAPY ZABIEGÓW (Wizualne wskazanie ubytków)
        # Odwracamy maskę, aby znaleźć "dziury" (ubytki)
        bare_mask = cv2.bitwise_not(mask)
        # Usuwanie szumu (małych kropek)
        kernel = np.ones((5,5), np.uint8)
        bare_mask = cv2.morphologyEx(bare_mask, cv2.MORPH_OPEN, kernel)
        
        # Znajdowanie konturów ubytków
        contours, _ = cv2.findContours(bare_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        # Nakładanie obrysów na kopię oryginału
        annotated_img = img.copy()
        cv2.drawContours(annotated_img, contours, -1, (0, 0, 255), 2) # Czerwone obrysy

        status = "Pełne pokrycie" if green_ratio > 0.95 else "Wykryto ubytki - zalecane dosiewki"
        return {
            'cover_pct': round(green_ratio * 100, 1),
            'bare_pct': round((1 - green_ratio) * 100, 1),
            'status': status,
            'mask': mask,
            'annotated_img': annotated_img
        }

    def generate_dgci_heatmap(self, image_source):
        """
        Generuje mapę cieplną (Heatmap) na podstawie indeksu DGCI.
        Pokazuje przestrzenne zróżnicowanie wigoru i nawożenia azotem.
        """
        img = self._load_image(image_source)
        if img is None:
            return None

        hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
        
        # Maskowanie trawy (zakres standardowy dla DGCI)
        lower_green = np.array([25, 40, 40])
        upper_green = np.array([95, 255, 255])
        mask = cv2.inRange(hsv, lower_green, upper_green)

        # Rozdzielenie kanałów i obliczenia per-pixel
        h, s, v = cv2.split(hsv)
        h_deg = h.astype(float) * 2.0
        
        # Formuła DGCI per pixel
        h_term = np.clip((h_deg - 60.0) / 60.0, 0, 1)
        s_norm = s.astype(float) / 255.0
        v_norm = v.astype(float) / 255.0
        dgci_map = (h_term + (1.0 - s_norm) + (1.0 - v_norm)) / 3.0
        
        # Skalowanie dla wizualizacji (zakres 0.4 - 0.7 jest najbardziej istotny dla murawy)
        # Pozwala to lepiej widzieć różnice w "zieloności"
        vis_map = np.clip((dgci_map - 0.4) / (0.7 - 0.4), 0, 1) * 255
        vis_map = vis_map.astype(np.uint8)

        # Nałożenie mapy kolorów JET i maskowanie tła
        heatmap = cv2.applyColorMap(vis_map, cv2.COLORMAP_JET)
        heatmap = cv2.bitwise_and(heatmap, heatmap, mask=mask)

        return heatmap

    def _load_image(self, image_source):
        """Pomocnicza metoda do bezpiecznego wczytywania obrazów."""
        if isinstance(image_source, str):
            return cv2.imread(image_source)
        elif isinstance(image_source, (np.ndarray, list)):
            return np.array(image_source, dtype=np.uint8)
        return None

    def interpret_comparison(self, dgci_before, dgci_after):
        """Analizuje zmianę między dwoma pomiarami DGCI pod kątem odpowiedzi na azot."""
        diff = dgci_after - dgci_before
        
        # Progi oparte na badaniach nad odpowiedzią darni na azot (N-response)
        if diff >= 0.10:
            status = "SUCCESS"
            msg = f"🌟 Wybitna reakcja azotowa (+{round(diff*100, 1)}%). Darń wykazuje maksymalny wigor i nasycenie koloru."
        elif 0.04 <= diff < 0.10:
            status = "SUCCESS"
            msg = f"✅ Bardzo dobra odpowiedź (+{round(diff*100, 1)}%). Nawożenie skutecznie podniosło poziom chlorofilu."
        elif 0.01 <= diff < 0.04:
            status = "INFO"
            msg = f"⚖️ Stabilizacja (+{round(diff*100, 1)}%). Podtrzymanie koloru bez gwałtownego przyrostu biomasy."
        elif -0.02 <= diff < 0.01:
            status = "INFO"
            msg = "⚖️ Brak istotnej zmiany wizualnej. Potencjał azotowy jest obecnie stabilny."
        elif -0.05 <= diff < -0.02:
            status = "WARNING"
            msg = f"🟡 Wykryto lekki spadek wigoru ({round(diff*100, 1)}%). Możliwe wyczerpanie zapasów N lub stres środowiskowy."
        else: # diff < -0.05
            status = "ERROR"
            msg = f"⚠️ Krytyczny spadek indeksu DGCI ({round(diff*100, 1)}%). Ryzyko głodu azotowego lub silnego stresu biotycznego."
            
        return {"diff": round(diff, 3), "status": status, "message": msg}
