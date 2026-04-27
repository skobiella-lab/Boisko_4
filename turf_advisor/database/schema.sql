CREATE TABLE IF NOT EXISTS soil_analysis (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    profile_id INTEGER,
    date_sampled TEXT,
    ph_h2o REAL,
    ph_hcl REAL,
    ec_ds_m REAL,
    m3_p REAL, m3_k REAL, m3_mg REAL, m3_ca REAL, m3_s REAL,
    m3_na REAL, m3_fe REAL, m3_mn REAL, m3_b REAL, m3_cu REAL, m3_zn REAL, m3_al REAL,
    hort_p REAL, hort_k REAL, hort_mg REAL,
    hort_n_no3 REAL, hort_n_nh4 REAL, hort_cl REAL,
    -- Nowe parametry fizyczne (Granulometria)
    sand_pct REAL, silt_pct REAL, clay_pct REAL,
    om_pct REAL, -- Materia organiczna
    bulk_density REAL
);

CREATE TABLE IF NOT EXISTS maintenance_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    profile_id INTEGER,
    action_type TEXT,
    amount REAL,
    product_id TEXT,
    timestamp DATETIME,
    notes TEXT
);

-- Nowa tabela dla bazy dostępnych produktów
CREATE TABLE IF NOT EXISTS fertilizers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    brand TEXT,
    name TEXT,
    n_total REAL, p_total REAL, k_total REAL,
    n_no3 REAL, n_nh4 REAL, n_nh2 REAL, -- Rozbicie form azotu
    mg REAL, ca REAL, s REAL,
    micro_nutrients TEXT, -- JSON z mikroelementami
    is_slow_release INTEGER,
    price_per_kg REAL,
    stock_kg REAL,
    salt_index REAL DEFAULT 0.0
);


CREATE TABLE IF NOT EXISTS weather_history (
    date TEXT PRIMARY KEY,
    temp_max REAL,
    temp_min REAL,
    temp_avg REAL,
    precip_mm REAL,
    humidity REAL,
    et_calculated REAL,
    is_forecast INTEGER
);

CREATE TABLE IF NOT EXISTS vision_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    field_id INTEGER,
    date TEXT,
    dgci REAL,
    bare_pct REAL DEFAULT 0.0
);

CREATE TABLE IF NOT EXISTS recommendations_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    field_id INTEGER,
    timestamp DATETIME,
    tier TEXT,
    summary TEXT,
    details TEXT
);