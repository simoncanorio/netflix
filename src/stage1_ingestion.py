"""
ETAPA 1: Ingesta, Profiling y Optimización de Memoria.
Convierte los archivos de IMDb y Netflix Top 10 a formato Parquet columnar usando DuckDB,
aplicando downcasting de tipos y exportando métricas de profiling.
"""

import json
import time
from pathlib import Path
import duckdb

import sys
sys.path.append(str(Path(__file__).resolve().parent.parent))
from config import RAW_DATASETS, PARQUET_FILES, REPORTS_DIR, TARGET_TITLE_TYPES

def profile_and_convert_basics() -> dict:
    raw_path = RAW_DATASETS["basics"]
    out_path = PARQUET_FILES["basics"]
    
    print(f"\n[Etapa 1] Procesando {raw_path.name} desde data/ con DuckDB...")
    t0 = time.time()
    con = duckdb.connect()
    types_in = ", ".join(f"'{t}'" for t in TARGET_TITLE_TYPES)
    
    query = f"""
    COPY (
        SELECT 
            tconst::VARCHAR AS tconst,
            titleType::VARCHAR AS titleType,
            primaryTitle::VARCHAR AS primaryTitle,
            isAdult::INT8 AS isAdult,
            TRY_CAST(startYear AS INT16) AS startYear,
            TRY_CAST(runtimeMinutes AS INT32) AS runtimeMinutes,
            genres::VARCHAR AS genres
        FROM read_csv(
            '{raw_path.as_posix()}',
            header=true,
            delim='\\t',
            nullstr='\\N',
            compression='gzip'
        )
        WHERE isAdult = 0 
          AND titleType IN ({types_in})
    ) TO '{out_path.as_posix()}' (FORMAT 'PARQUET', COMPRESSION 'SNAPPY');
    """
    con.execute(query)
    elapsed = time.time() - t0
    total_processed = con.execute(f"SELECT COUNT(*) FROM '{out_path.as_posix()}'").fetchone()[0]
    
    metrics = {
        "dataset": "title.basics",
        "processed_rows": total_processed,
        "parquet_size_mb": round(out_path.stat().st_size / (1024**2), 2),
        "raw_size_mb": round(raw_path.stat().st_size / (1024**2), 2),
        "elapsed_seconds": round(elapsed, 2)
    }
    print(f"  -> Guardado: {out_path.name} ({metrics['processed_rows']:,} filas en {metrics['elapsed_seconds']}s)")
    return metrics

def profile_and_convert_ratings() -> dict:
    raw_path = RAW_DATASETS["ratings"]
    out_path = PARQUET_FILES["ratings"]
    
    print(f"\n[Etapa 1] Procesando {raw_path.name} desde data/ con DuckDB...")
    t0 = time.time()
    con = duckdb.connect()
    
    query = f"""
    COPY (
        SELECT 
            tconst::VARCHAR AS tconst,
            TRY_CAST(averageRating AS FLOAT) AS averageRating,
            TRY_CAST(numVotes AS INT32) AS numVotes
        FROM read_csv(
            '{raw_path.as_posix()}',
            header=true,
            delim='\\t',
            nullstr='\\N',
            compression='gzip'
        )
    ) TO '{out_path.as_posix()}' (FORMAT 'PARQUET', COMPRESSION 'SNAPPY');
    """
    con.execute(query)
    elapsed = time.time() - t0
    total_processed = con.execute(f"SELECT COUNT(*) FROM '{out_path.as_posix()}'").fetchone()[0]
    
    metrics = {
        "dataset": "title.ratings",
        "processed_rows": total_processed,
        "parquet_size_mb": round(out_path.stat().st_size / (1024**2), 2),
        "raw_size_mb": round(raw_path.stat().st_size / (1024**2), 2),
        "elapsed_seconds": round(elapsed, 2)
    }
    print(f"  -> Guardado: {out_path.name} ({metrics['processed_rows']:,} filas en {metrics['elapsed_seconds']}s)")
    return metrics

def profile_and_convert_netflix_top10() -> dict:
    raw_global = RAW_DATASETS["netflix_global"]
    raw_countries = RAW_DATASETS["netflix_countries"]
    out_agg = PARQUET_FILES["netflix_agg"]
    
    print(f"\n[Etapa 1] Procesando y agregando Netflix Top 10 Semanal...")
    t0 = time.time()
    con = duckdb.connect()
    
    query = f"""
    COPY (
        WITH countries_agg AS (
            SELECT 
                LOWER(TRIM(show_title)) AS clean_title,
                COUNT(DISTINCT country_iso2) AS netflix_num_paises,
                MAX(cumulative_weeks_in_top_10) AS netflix_max_semanas_pais,
                STRING_AGG(DISTINCT country_iso2, ',') AS netflix_paises_top10
            FROM read_csv_auto('{raw_countries.as_posix()}', delim='\\t')
            GROUP BY LOWER(TRIM(show_title))
        ),
        global_agg AS (
            SELECT 
                LOWER(TRIM(show_title)) AS clean_title,
                FIRST(category) AS netflix_categoria,
                MAX(cumulative_weeks_in_top_10) AS netflix_semanas_global,
                SUM(TRY_CAST(weekly_hours_viewed AS BIGINT)) AS netflix_total_horas_vistas
            FROM read_csv_auto('{raw_global.as_posix()}', delim='\\t')
            GROUP BY LOWER(TRIM(show_title))
        )
        SELECT 
            COALESCE(g.clean_title, c.clean_title) AS clean_title,
            g.netflix_categoria,
            COALESCE(g.netflix_semanas_global, c.netflix_max_semanas_pais, 1) AS netflix_semanas_top10,
            COALESCE(g.netflix_total_horas_vistas, 0) AS netflix_horas_vistas,
            COALESCE(c.netflix_num_paises, 1) AS netflix_paises_alcanzados,
            c.netflix_paises_top10,
            1 AS in_netflix_top10
        FROM global_agg g
        FULL OUTER JOIN countries_agg c ON g.clean_title = c.clean_title
    ) TO '{out_agg.as_posix()}' (FORMAT 'PARQUET', COMPRESSION 'SNAPPY');
    """
    con.execute(query)
    elapsed = time.time() - t0
    total_processed = con.execute(f"SELECT COUNT(*) FROM '{out_agg.as_posix()}'").fetchone()[0]
    
    metrics = {
        "dataset": "netflix_top10_aggregated",
        "processed_rows": total_processed,
        "parquet_size_mb": round(out_agg.stat().st_size / (1024**2), 2),
        "elapsed_seconds": round(elapsed, 2)
    }
    print(f"  -> Guardado: {out_agg.name} ({metrics['processed_rows']:,} títulos de Netflix Top 10 consolidados en {metrics['elapsed_seconds']}s)")
    return metrics

def run_stage1() -> dict:
    metrics_basics = profile_and_convert_basics()
    metrics_ratings = profile_and_convert_ratings()
    metrics_netflix = profile_and_convert_netflix_top10()
    
    full_report = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "method": "DuckDB C++ Multi-threaded Ingestion + Snappy Parquet",
        "stages": [metrics_basics, metrics_ratings, metrics_netflix]
    }
    
    report_file = REPORTS_DIR / "mem_profile_report.json"
    with open(report_file, "w", encoding="utf-8") as f:
        json.dump(full_report, f, indent=4)
        
    print(f"\n[Etapa 1 Completada] Métricas guardadas en {report_file}")
    return full_report

if __name__ == "__main__":
    run_stage1()
