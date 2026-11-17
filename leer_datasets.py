"""
Script para la lectura y carga de los datasets de IMDb, Netflix Top 10 y configuración de API TMDB.
Asignatura: Taller 2 - Proyecto Netflix
"""

import os
from pathlib import Path
import pandas as pd

# ==============================================================================
# 1. CONFIGURACIÓN DE TMDB API KEY (Credenciales configuradas por el usuario)
# ==============================================================================
TMDB_API_KEY = os.getenv("TMDB_API_KEY", "4fe9ee1862037288934c7308aec0df1e")
TMDB_READ_ACCESS_TOKEN = os.getenv(
    "TMDB_READ_ACCESS_TOKEN",
    "eyJhbGciOiJIUzI1NiJ9.eyJhdWQiOiI0ZmU5ZWUxODYyMDM3Mjg4OTM0YzczMDhhZWMwZGYxZSIsIm5iZiI6MTc5MzM2MDk5My40Mywic3ViIjoiNmFlNDg0NjEzNDM1NjVhN2MxY2Q3YmUyIiwic2NvcGVzIjpbImFwaV9yZWFkIl0sInZlcnNpb24iOjF9.sSV30kZ_za1VDFBjonP2lkP2gvL5ydPweBjj_yrKlGk"
)

# ==============================================================================
# 2. DEFINICIÓN DE RUTAS Y DATASETS EN LA CARPETA 'data/'
# ==============================================================================
BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data" if (BASE_DIR / "data").exists() else BASE_DIR

DATASETS = {
    # IMDb Datasets
    "ratings": "title.ratings.tsv.gz",
    "basics": "title.basics.tsv.gz",
    "akas": "title.akas.tsv.gz",
    "crew": "title.crew.tsv.gz",
    "episode": "title.episode.tsv.gz",
    "principals": "title.principals.tsv.gz",
    "names": "name.basics.tsv.gz",
    # Netflix Top 10 Oficial
    "netflix_global": "netflix_top10_global.tsv",
    "netflix_countries": "netflix_top10_countries.tsv",
}

# ==============================================================================
# 3. FUNCIÓN GENERAL DE CARGA
# ==============================================================================
def leer_dataset(nombre_o_archivo: str, nrows: int | None = None, usecols: list[str] | None = None, chunksize: int | None = None) -> pd.DataFrame:
    """
    Lee un archivo de datos (TSV comprimido de IMDb o TSV de Netflix Top 10) desde la carpeta 'data/'.
    """
    archivo = DATASETS.get(nombre_o_archivo, nombre_o_archivo)
    ruta = DATA_DIR / archivo
    if not ruta.exists():
        # Fallback a directorio base si no se movió aún
        ruta = BASE_DIR / archivo

    if not ruta.exists():
        raise FileNotFoundError(f"No se encontró el archivo: {ruta}")

    print(f"-> Cargando '{archivo}' desde {ruta.parent.name}/...")

    # Detectar compresión
    compression = "gzip" if str(archivo).endswith(".gz") else None
    
    # Valores nulos de IMDb (\N) o estándar
    na_values = ["\\N"] if "tsv.gz" in str(archivo) else None

    df = pd.read_csv(
        ruta,
        sep="\t",
        na_values=na_values,
        compression=compression,
        nrows=nrows,
        usecols=usecols,
        chunksize=chunksize,
        low_memory=False,
    )
    return df


# ==============================================================================
# 4. FUNCIONES INDIVIDUALES (ACCESO RÁPIDO)
# ==============================================================================
def leer_ratings(nrows=None, usecols=None):
    """Carga title.ratings.tsv.gz (Puntajes y votos)"""
    return leer_dataset("ratings", nrows=nrows, usecols=usecols)

def leer_basics(nrows=None, usecols=None):
    """Carga title.basics.tsv.gz (Títulos, año, duración, géneros, tipo)"""
    return leer_dataset("basics", nrows=nrows, usecols=usecols)

def leer_akas(nrows=None, usecols=None):
    """Carga title.akas.tsv.gz (Títulos localizados, regiones, idiomas)"""
    return leer_dataset("akas", nrows=nrows, usecols=usecols)

def leer_crew(nrows=None, usecols=None):
    """Carga title.crew.tsv.gz (Directores y escritores)"""
    return leer_dataset("crew", nrows=nrows, usecols=usecols)

def leer_episodes(nrows=None, usecols=None):
    """Carga title.episode.tsv.gz (Relación serie-temporada-episodio)"""
    return leer_dataset("episode", nrows=nrows, usecols=usecols)

def leer_principals(nrows=None, usecols=None):
    """Carga title.principals.tsv.gz (Reparto principal y roles)"""
    return leer_dataset("principals", nrows=nrows, usecols=usecols)

def leer_names(nrows=None, usecols=None):
    """Carga name.basics.tsv.gz (Personas, actores, directores, etc.)"""
    return leer_dataset("names", nrows=nrows, usecols=usecols)

def leer_netflix_top10_global(nrows=None, usecols=None):
    """Carga netflix_top10_global.tsv (Top 10 Global semanal de Netflix con horas vistas)"""
    return leer_dataset("netflix_global", nrows=nrows, usecols=usecols)

def leer_netflix_top10_countries(nrows=None, usecols=None):
    """Carga netflix_top10_countries.tsv (Top 10 Semanal desglosado por país)"""
    return leer_dataset("netflix_countries", nrows=nrows, usecols=usecols)


# ==============================================================================
# PRUEBA RÁPIDA
# ==============================================================================
if __name__ == "__main__":
    print("=" * 65)
    print("ESTADO DE CONFIGURACIÓN TMDB:")
    print(f"[OK] TMDB_API_KEY activa: {TMDB_API_KEY[:6]}...{TMDB_API_KEY[-4:]}")
    print(f"[OK] Directorio de datos: {DATA_DIR.resolve()}")
    print("=" * 65)

    print("\nVerificando muestra de Netflix Top 10 Global:")
    df_net_glob = leer_netflix_top10_global(nrows=3)
    print(df_net_glob[["week", "category", "show_title", "weekly_hours_viewed"]])

    print("\nVerificando muestra de Netflix Top 10 por Países:")
    df_net_cou = leer_netflix_top10_countries(nrows=3)
    print(df_net_cou[["country_name", "country_iso2", "week", "show_title", "weekly_rank"]])
