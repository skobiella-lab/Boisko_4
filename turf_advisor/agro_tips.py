# turf_advisor/agro_tips.py

def get_mlsn_info():
    """Zwraca opis standardów MLSN."""
    return """
    **MLSN (Minimum Levels for Sustainable Nutrition)** to nowoczesne wytyczne interpretacji wyników badań gleby, 
    opracowane przez PACE Turf i Asian Turfgrass Center. 
    
    W przeciwieństwie do tradycyjnych metod, które często sugerują nadmierne nawożenie, MLSN skupia się na utrzymaniu 
    minimalnej, bezpiecznej ilości składników odżywczych, która gwarantuje wysoką jakość murawy. 
    System analizuje różnicę między obecnym stanem zasobów a progiem krytycznym, uwzględniając zapotrzebowanie 
    rośliny wynikające z tempa jej wzrostu.
    """

def get_model_info():
    """Zwraca opisy głównych modeli decyzyjnych wykorzystywanych w systemie."""
    return """
    ### 🧠 Modele Decyzyjne i Probabilistyczne

    Nasz system łączy klasyczną agrotechnikę z zaawansowaną statystyką, aby dostarczać precyzyjne rekomendacje 
    w ramach **Warstwy 3 (Smart)**.

    #### 🦠 Model Smith-Kerns (Ryzyko Chorobowe)
    Jest to epidemiologiczny model regresji logistycznej służący do szacowania prawdopodobieństwa wystąpienia 
    **Dolarowej Plamistości** (*Sclerotinia homoeocarpa*). 
    *   **Jak działa:** Analizuje kroczące średnie temperatury powietrza oraz wilgotności względnej z ostatnich 5 dni.
    *   **Zastosowanie:** Pozwala na prewencyjne działanie przed pojawieniem się objawów. Jeśli ryzyko przekracza 20%, 
        system sugeruje wzmocnienie odporności rośliny, a powyżej 50-70% — rozważenie zabiegu fungicydowego.

    #### 🎲 Symulacja Monte Carlo (Ryzyko Wypłukiwania Azotu)
    Model probabilistyczny służący do oceny stabilności azotu w profilu glebowym.
    *   **Jak działa:** Silnik wykonuje tysiące losowych symulacji scenariuszy pogodowych w oparciu o prognozę opadów 
        oraz błąd statystyczny prognozy. Uwzględnia przy tym granulometrię gleby (np. wysoką przepuszczalność piasku USGA).
    *   **Zastosowanie:** Określa prawdopodobną stratę azotu (w kg/ha) po ulewnych deszczach. Pomaga zdecydować, 
        czy należy zastosować nawóz o spowolnionym uwalnianiu (CRF/PCU), aby zminimalizować straty ekonomiczne i środowiskowe.

    #### 🧬 Algorytm Genetyczny (Optymalizacja Harmonogramu)
    Zaawansowany silnik optymalizacyjny inspirowany procesem ewolucji naturalnej.
    *   **Jak działa:** System generuje populację tysięcy potencjalnych harmonogramów zabiegów i poddaje je procesowi 
        selekcji, krzyżowania i mutacji. Każdy plan oceniany jest funkcją celu (*fitness*), która faworyzuje:
        *   Zabiegi nawożenia przed lekkim deszczem (naturalne wmycie).
        *   Koszenie w oknach bezopadowych (ochrona struktury liścia).
        *   Unikanie aplikacji w ekstremalnych temperaturach.
    *   **Zastosowanie:** Wyznacza najbardziej optymalne daty wykonania prac w nadchodzącym tygodniu, 
        maksymalizując efektywność zabiegów przy minimalnym stresie dla rośliny.

    #### 🌊 Równanie Richardsa i Model Fizyki Gleby
    Deterministyczny model ruchu wody w ośrodkach porowatych.
    *   **Zastosowanie:** Pozwala na precyzyjne określenie statusu napowietrzenia gleby oraz stabilności mechanicznej 
        murawy (Shear Strength) na podstawie aktualnej wilgotności objętościowej (VMC).
    """

def get_vision_tips():
    """Porady dotyczące analizy obrazu."""
    return """
    **DGCI (Dark Green Color Index)**:
    Wartości powyżej 0.57 zazwyczaj wskazują na optymalne odżywienie azotem. Nagłe spadki trendu DGCI mogą 
    sygnalizować początek stresu suszowego lub głód azotowy, zanim stanie się on widoczny "gołym okiem".
    """

def get_nitrogen_tips(temp):
    """Dynamiczne porady dotyczące form azotu."""
    if temp < 10:
        return "Niska aktywnosc mikrobiologiczna (ponizej 10C). Azot amidowy (mocznik) nie ulegnie hydrolizie. Stosuj NO3 dla natychmiastowej reakcji."
    elif temp > 25:
        return "Wysokie temperatury zwiększają ryzyko strat gazowych (wolatywizacja). Wymagane natychmiastowe wmycie nawozów amidowych."
    return "Warunki optymalne dla większości form azotu."

def get_salt_index_info():
    """Opis znaczenia Indeksu Solnego."""
    return """
    **Indeks Solny (Salt Index)** określa potencjał nawozu do zwiększania ciśnienia osmotycznego roztworu glebowego. 
    Wysoki indeks (> 50) przy niskiej wilgotności i wysokiej temperaturze (> 25°C) grozi 'przypaleniem' liści i uszkodzeniem 
    systemu korzeniowego. System automatycznie obniża ocenę takich produktów w okresach upałów (Model III.19).
    """

def get_cn_ratio_info():
    """Wiedza o mineralizacji azotu."""
    return """
    **Stosunek C:N (Węgiel do Azotu)**:
    *   **< 15:1:** Szybka mineralizacja. Mikroorganizmy uwalniają nadmiar azotu do gleby.
    *   **> 25:1:** Immobilizacja. Mikroorganizmy zużywają dostępny azot do rozkładu materii organicznej, 
        co może powodować okresowy 'głód' rośliny mimo nawożenia.
    """

def get_shear_strength_info():
    """Opis stabilności mechanicznej murawy."""
    return """
    **Odporność na ścinanie (Shear Strength)**:
    Mierzona w kPa, określa zdolność murawy do przenoszenia obciążeń generowanych przez korki zawodników. 
    Wartości poniżej 35 kPa wskazują na ryzyko zrywania darni (Model I.9).
    """

def get_gdd_info():
    """Zastosowanie stopniodni w pielęgnacji."""
    return """
    **GDD (Growing Degree Days)**:
    Skumulowane ciepło pozwala przewidzieć okna dla regulatorów wzrostu (PGR) oraz terminy dosiewek. 
    Optymalne kiełkowanie życicy trwałej następuje po skumulowaniu 50-100 GDD (Model II.11).
    """

def get_tissue_analysis_info():
    """Interpretacja składu liści."""
    return """
    **Analiza Tkankowa (Masa Zielona)**:
    Podczas gdy badanie gleby mówi o zasobach, analiza tkankowa mówi o tym, co roślina faktycznie pobrała. 
    Pomaga wykryć blokady pierwiastków wynikające z antagonizmów kationowych (Model II.17).
    """

def get_dynamic_advice(advice_dict):
    """Generuje listę tekstowych porad operacyjnych na podstawie wyników analizy."""
    tips = []
    if 'nutrition' in advice_dict:
        n_status = advice_dict['nutrition'].get('nitrogen_forms_recommendation', {})
        if n_status.get('current_status', {}).get('interpretation') == 'LOW':
            tips.append("Priorytet: Niskie stężenie azotu mineralnego. Zastosuj sugerowaną dawkę interwencyjną.")
    
    if 'physical' in advice_dict:
        if advice_dict['physical']['shear_strength']['status'] in ['SOFT', 'UNSTABLE']:
            tips.append("Stabilność krytyczna: Ogranicz nawadnianie i rozważ napowietrzanie strefy korzeniowej.")

    if 'risk' in advice_dict:
        if advice_dict['risk'].get('smith_kerns_dollar_spot', 0) > 0.5:
            tips.append("Wysokie ryzyko patogenów: Wstrzymaj nawożenie wysokoazotowe do czasu poprawy warunków.")
    return tips

def get_detailed_agro_descriptions():
    """Zwraca bogate opisy agrotechniczne dla raportów."""
    return {
        'MLSN_STRATEGY': "Strategia MLSN (Minimum Levels for Sustainable Nutrition) pozwala na redukcje nawozenia o 30-50% bez straty jakosci murawy. Skupia sie na roztworze glebowym, a nie na totalnym zapasie w glebie.",
        'WATER_MANAGEMENT': "Zasada 'Deep and Infrequent'. Podlewanie rzadsze (1-2 razy w tygodniu), ale glebokie (do 150mm profilu), buduje gleboki system korzeniowy i zwieksza odpornosc na susze.",
        'SOIL_PHYSICS': "Stosunek powietrza do wody w porach glebowych decyduje o zdrowiu korzeni. AFP (Air Filled Porosity) ponizej 10% przy przesyceniu woda prowadzi do anoksji i obumarcia korzeni w ciagu 24-48h.",
        'NITROGEN_DYNAMICS': "Efektywnosc wykorzystania azotu (NUE) zalezy od temperatury. Przy wysokim GP (Growth Potential) roslina pobiera azot w ciagu kilku godzin od aplikacji dolistnej."
    }

def get_tier_methodology_desc():
    """Opisy metodologii dla poszczególnych poziomów."""
    return {
        'Base': "Analiza statyczna Mehlich-3. Porównuje zasobność gleby z progiem bezpieczeństwa MLSN bez uwzględniania pogody.",
        'Dynamic': "Modelowanie procesów biologicznych. Koryguje potrzeby na podstawie tempa wzrostu (GP) i mineralizacji azotu.",
        'Smart': "Optymalizacja wielokryterialna. Łączy ryzyko chorób, wypłukiwanie i rachunek ekonomiczny przy doborze produktów."
    }

def get_application_guidelines():
    """Zwraca techniczne wskazówki dotyczące sposobów aplikacji nawozów."""
    return {
        'Spoon-feeding': "Aplikacja dolistna małych dawek (2-5 kg N/ha) w odstępach 7-14 dni. Idealna przy wysokim GP i ryzyku wypłukiwania.",
        'Granular Base': "Aplikacja doglebowa nawozów granulowanych (20-35 kg N/ha). Wymaga min. 3-5 mm opadu/nawadniania w celu wmycia.",
        'Fertigation': "Podawanie składników wraz z systemem nawadniania. Najwyższa precyzja, ale wymaga kontroli EC wody.",
        'Correction': "Zabieg interwencyjny mający na celu szybkie uzupełnienie deficytu (np. siarczan magnezu przy chlorozie)."
    }

def get_methodology_details():
    """Zwraca opis techniczny wzorów dla raportu rozszerzonego."""
    return {
        'GDD': "Model: Modified Average. Formula: GDD = ((T_max + T_min) / 2) - T_base. Określa tempo akumulacji energii cieplnej.",
        'GP': "Model: Haney Growth Potential. Formula: GP = exp(-0.5 * ((T_avg - T_opt) / Var)^2). Parametr Gaussa dla optymalizacji metabolizmu.",
        'MLSN': "Minimalne poziomy oparte na rozkładzie statystycznym tysięcy próbek gleby (MLSN 2012-2022). Wylicza deficyt w oparciu o masę gleby na 10cm ornej.",
        'Smith-Kerns': "Epidemiologia: P = 1 / (1 + exp(-(-9.99 + 0.18 * T + 0.05 * RH))). Logistyczna regresja prawdopodobieństwa infekcji.",
        'Monte-Carlo': "Statystyka: 1000 iteracji z szumem Gaussa (sigma=30%) dla prognozy opadów. Oblicza prawdopodobieństwo drenażu grawitacyjnego."
    }