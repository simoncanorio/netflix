"""
Módulo de Configuración Centralizada para el Proyecto Netflix
Define rutas de datasets en 'data/', credenciales de TMDB sincronizadas con leer_datasets.py,
hiperparámetros, directivas de negocio y configuración del motor de aprendizaje web.
"""

import os
from pathlib import Path

# ==============================================================================
# 1. CARGAR VARIABLES DE ENTORNO (.env) Y CREDENCIALES TMDB
# ==============================================================================
try:
    from leer_datasets import TMDB_API_KEY, TMDB_READ_ACCESS_TOKEN
except ImportError:
    TMDB_API_KEY = os.getenv("TMDB_API_KEY", "")
    TMDB_READ_ACCESS_TOKEN = os.getenv("TMDB_READ_ACCESS_TOKEN", "")

TMDB_BASE_URL = "https://api.themoviedb.org/3"

# ==============================================================================
# 2. RUTAS DEL PROYECTO Y CARPETA data/
# ==============================================================================
BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
OUTPUT_DIR = BASE_DIR / "output"
PARQUET_DIR = OUTPUT_DIR / "parquet"
REPORTS_DIR = OUTPUT_DIR / "reports"
WEB_DIR = BASE_DIR / "web"

PARQUET_DIR.mkdir(parents=True, exist_ok=True)
REPORTS_DIR.mkdir(parents=True, exist_ok=True)
WEB_DIR.mkdir(parents=True, exist_ok=True)

# Datasets crudos ubicados en data/
RAW_DATASETS = {
    # IMDb Datasets
    "ratings": DATA_DIR / "title.ratings.tsv.gz",
    "basics": DATA_DIR / "title.basics.tsv.gz",
    "akas": DATA_DIR / "title.akas.tsv.gz",
    "crew": DATA_DIR / "title.crew.tsv.gz",
    "episode": DATA_DIR / "title.episode.tsv.gz",
    "principals": DATA_DIR / "title.principals.tsv.gz",
    "names": DATA_DIR / "name.basics.tsv.gz",
    # Netflix Top 10 Oficial
    "netflix_global": DATA_DIR / "netflix_top10_global.tsv",
    "netflix_countries": DATA_DIR / "netflix_top10_countries.tsv",
}

# Rutas de los archivos Parquet procesados
PARQUET_FILES = {
    "basics": PARQUET_DIR / "title_basics.parquet",
    "ratings": PARQUET_DIR / "title_ratings.parquet",
    "akas_agg": PARQUET_DIR / "akas_aggregated.parquet",
    "netflix_agg": PARQUET_DIR / "netflix_top10_aggregated.parquet",
    "master": PARQUET_DIR / "catalogo_internacional_master.parquet",
    "hubs": PARQUET_DIR / "international_hubs_metrics.parquet",
    "cast": PARQUET_DIR / "movie_cast.parquet",
    "episodes": PARQUET_DIR / "series_episodes.parquet",
}

# ==============================================================================
# 3. HIPERPARÁMETROS ANALÍTICOS Y REGLAS DE NEGOCIO
# ==============================================================================
MIN_START_YEAR = 1970
MAX_START_YEAR = 2024
MIN_RUNTIME = 40
MAX_RUNTIME = 240
TARGET_TITLE_TYPES = ["movie", "tvSeries", "tvMiniSeries"]

BAYES_VOTES_PERCENTILE = 0.75
MIN_VOTES_FILTER = 100

TECH_ERAS = [
    {"label": "VHS_Era (1980-1996)", "start": 1980, "end": 1996},
    {"label": "DVD_Era (1997-2009)", "start": 1997, "end": 2009},
    {"label": "Early_Streaming (2010-2016)", "start": 2010, "end": 2016},
    {"label": "Global_SVOD (2017-2024)", "start": 2017, "end": 2024},
]

INGESTION_CHUNKSIZE = 250_000

# ==============================================================================
# 4. CONFIGURACIÓN DEL RECOMENDADOR WEB Y APRENDIZAJE DE USUARIO
# ==============================================================================
# Umbral mínimo de permanencia en hover (milisegundos) para descartar hovers accidentales
MIN_HOVER_DWELL_MS = 800

# Ponderaciones de interés por tipo de interacción del usuario
INTERACTION_WEIGHTS = {
    "hover": 1.0,         # Hover sostenido >= 800 ms
    "click": 3.0,         # Clic en tarjeta
    "modal_open": 5.0,    # Apertura de panel de detalle
    "my_list": 10.0,      # Agregado a "Mi Lista" (máxima señal explícita)
}

# Tasa de decaimiento temporal aplicado a interacciones previas al recibir nuevo evento
INTERACTION_DECAY = 0.95

# Umbral acumulado de señal requerido para activar el carrusel de "Joyas Escondidas para vos"
SIGNAL_THRESHOLD_GEMS = 15.0

# Servidor Web (Configurable por entorno para Docker / Render / Local)
SERVER_HOST = os.getenv("SERVER_HOST", "127.0.0.1")
SERVER_PORT = int(os.getenv("PORT", os.getenv("SERVER_PORT", "8000")))
