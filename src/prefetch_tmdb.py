"""
Script de pre-enriquecimiento y caché persistente de TMDb para títulos clave del catálogo.
Guarda póster, backdrop, país de origen verificado y overview en data/tmdb_titles_cache.json.
"""

import json
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
import sys
import duckdb
import pandas as pd

sys.path.append(str(Path(__file__).resolve().parent.parent))
from config import DATA_DIR, PARQUET_FILES
from src.tmdb_client import TMDBClient

CACHE_FILE = DATA_DIR / "tmdb_titles_cache.json"

def load_existing_cache() -> dict:
    if CACHE_FILE.exists():
        try:
            return json.loads(CACHE_FILE.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}

def save_cache(cache: dict):
    CACHE_FILE.write_text(json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8")

def prefetch_tmdb_metadata(limit: int = 300):
    client = TMDBClient()
    if not client.is_configured:
        print("[TMDB Cache] API Key no configurada.")
        return

    cache = load_existing_cache()
    con = duckdb.connect()
    master_p = PARQUET_FILES["master"]

    # Seleccionar títulos destacados: Shawshank, top rated, top netflix, joyas
    query = f"""
    SELECT DISTINCT tconst, primaryTitle, startYear
    FROM (
        -- Forzar Shawshank y clásicos
        SELECT tconst, primaryTitle, startYear, 999999 as sort_order
        FROM '{master_p.as_posix()}'
        WHERE tconst IN ('tt0111161', 'tt0903747', 'tt0185906', 'tt5753856', 'tt6751668', 'tt6468322', 'tt1305806')
        
        UNION ALL
        
        -- Top Bayesiano General
        SELECT tconst, primaryTitle, startYear, 10000 + numVotes as sort_order
        FROM '{master_p.as_posix()}'
        WHERE bayesian_rating >= 8.2 AND numVotes >= 50000
        
        UNION ALL
        
        -- Top Netflix Global
        SELECT tconst, primaryTitle, startYear, 50000 as sort_order
        FROM '{master_p.as_posix()}'
        WHERE in_netflix_top10 = 1 AND bayesian_rating >= 7.0
        
        UNION ALL
        
        -- Joyas Escondidas
        SELECT tconst, primaryTitle, startYear, 30000 as sort_order
        FROM '{master_p.as_posix()}'
        WHERE bayesian_rating >= 7.8 AND num_regiones <= 8 AND numVotes BETWEEN 5000 AND 60000
    )
    ORDER BY sort_order DESC
    LIMIT {limit};
    """

    df = con.execute(query).df()
    print(f"[TMDB Cache] {len(df)} títulos candidatos a enriquecer...")
    
    needed = df[~df["tconst"].isin(cache)]
    print(f"[TMDB Cache] {len(needed)} títulos nuevos a consultar en la API...")

    if needed.empty:
        print("[TMDB Cache] Todo en caché.")
        return

    def fetch_one(row):
        tconst = row["tconst"]
        try:
            found = client.find_by_imdb_id(tconst)
            if not found:
                return tconst, None
            tmdb_id = found["id"]
            media_type = found["media_type"]
            details = client.get_details(tmdb_id, media_type) or {}
            
            prod_countries = [c.get("iso_3166_1") for c in details.get("production_countries", [])]
            orig_country = details.get("origin_country", [])
            primary_country = ""
            if prod_countries:
                primary_country = prod_countries[0]
            elif orig_country:
                primary_country = orig_country[0]
            elif found.get("original_language") == "en":
                primary_country = "US"

            entry = {
                "tconst": tconst,
                "tmdb_id": tmdb_id,
                "media_type": media_type,
                "title": found.get("title") or found.get("name") or row["primaryTitle"],
                "poster_path": found.get("poster_path"),
                "backdrop_path": found.get("backdrop_path") or details.get("backdrop_path"),
                "overview": found.get("overview") or details.get("overview", ""),
                "country": primary_country,
                "production_countries": prod_countries,
                "vote_average": found.get("vote_average", 0.0)
            }
            return tconst, entry
        except Exception as e:
            return tconst, None

    records = needed.to_dict(orient="records")
    with ThreadPoolExecutor(max_workers=8) as executor:
        futures = {executor.submit(fetch_one, r): r["tconst"] for r in records}
        count = 0
        for fut in as_completed(futures):
            tconst, res = fut.result()
            if res:
                cache[tconst] = res
                count += 1
                if count % 25 == 0:
                    print(f"  -> {count}/{len(records)} títulos obtenidos...")

    save_cache(cache)
    print(f"[TMDB Cache] Finalizado. Total en caché: {len(cache)} títulos guardados en {CACHE_FILE.name}.")

if __name__ == "__main__":
    prefetch_tmdb_metadata(limit=250)
