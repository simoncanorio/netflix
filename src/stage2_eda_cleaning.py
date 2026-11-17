"""
ETAPA 2: Exploración de Datos (EDA) y Limpieza Aumentada.
- Agregación previa de title.akas a nivel tconst (1:N -> 1:1) sin duplicación de filas.
- Enriquecimiento con métricas de streaming del Netflix Top 10 Oficial.
- Joins eficientes con title.basics y title.ratings en DuckDB.
- Cálculo de Promedio Bayesiano de Calificación (evita sesgo de popularidad extrema o review bombing).
- Detección de inconsistencias temporales y reporte de pérdida de población en cascada (Waterfall).
"""

import time
from pathlib import Path
import duckdb
import pandas as pd
import numpy as np

import sys
sys.path.append(str(Path(__file__).resolve().parent.parent))
from config import (
    RAW_DATASETS, PARQUET_FILES, REPORTS_DIR,
    MIN_START_YEAR, MAX_START_YEAR, MIN_RUNTIME, MAX_RUNTIME,
    MIN_VOTES_FILTER, BAYES_VOTES_PERCENTILE
)

def aggregate_akas_no_explosion(force_recompute: bool = False) -> Path:
    """
    Agrega title.akas a nivel titleId (tconst) calculando el número de regiones e idiomas,
    y guardando en Parquet sin multiplicar filas. Si ya existe, lo reutiliza.
    """
    raw_akas = RAW_DATASETS["akas"]
    out_akas_agg = PARQUET_FILES["akas_agg"]
    
    if out_akas_agg.exists() and not force_recompute and out_akas_agg.stat().st_size > 1000:
        print(f"\n[Etapa 2] Utilizando {out_akas_agg.name} ya existente ({out_akas_agg.stat().st_size / (1024**2):.1f} MB)...")
        return out_akas_agg
        
    print(f"\n[Etapa 2] Pre-agregando {raw_akas.name} con DuckDB desde data/ (Prevención de Explosión 1:N)...")
    t0 = time.time()
    
    con = duckdb.connect()
    query = f"""
    COPY (
        SELECT 
            titleId AS tconst,
            COUNT(DISTINCT region) AS num_regiones,
            COUNT(DISTINCT language) AS num_idiomas,
            STRING_AGG(DISTINCT region, ',') FILTER (WHERE region != '\\N' AND region IS NOT NULL) AS regiones_str
        FROM read_csv(
            '{raw_akas.as_posix()}',
            header=true,
            delim='\\t',
            nullstr='\\N',
            compression='gzip',
            columns={{
                'titleId': 'VARCHAR',
                'ordering': 'INTEGER',
                'title': 'VARCHAR',
                'region': 'VARCHAR',
                'language': 'VARCHAR',
                'types': 'VARCHAR',
                'attributes': 'VARCHAR',
                'isOriginalTitle': 'INTEGER'
            }}
        )
        WHERE titleId IS NOT NULL
        GROUP BY titleId
    ) TO '{out_akas_agg.as_posix()}' (FORMAT 'PARQUET', COMPRESSION 'SNAPPY');
    """
    con.execute(query)
    elapsed = time.time() - t0
    count_agg = con.execute(f"SELECT COUNT(*) FROM '{out_akas_agg.as_posix()}'").fetchone()[0]
    print(f"  -> {out_akas_agg.name} generado: {count_agg:,} títulos únicos sintetizados en {elapsed:.2f}s.")
    return out_akas_agg

def build_master_catalog_with_bayes() -> tuple[pd.DataFrame, dict]:
    """
    Realiza los joins 1:1, cruza con Netflix Top 10, calcula el Promedio Bayesiano y audita la población descartada.
    """
    basics_p = PARQUET_FILES["basics"]
    ratings_p = PARQUET_FILES["ratings"]
    akas_agg_p = PARQUET_FILES["akas_agg"]
    netflix_agg_p = PARQUET_FILES["netflix_agg"]
    out_master_p = PARQUET_FILES["master"]
    
    print("\n[Etapa 2] Integrando catálogo maestro (IMDb + Netflix Top 10) y calculando Promedio Bayesiano...")
    con = duckdb.connect()
    
    # 1. Contar universo inicial de Basics
    total_basics = con.execute(f"SELECT COUNT(*) FROM '{basics_p.as_posix()}'").fetchone()[0]
    
    # 2. Obtener métricas globales para Bayes (C_mean y umbral m)
    bayes_stats = con.execute(f"""
        SELECT 
            AVG(averageRating) AS C_mean,
            QUANTILE_CONT(numVotes, {BAYES_VOTES_PERCENTILE}) AS m_threshold
        FROM '{ratings_p.as_posix()}'
        WHERE numVotes >= {MIN_VOTES_FILTER}
    """).fetchone()
    
    C_mean = float(bayes_stats[0])
    m_threshold = float(bayes_stats[1])
    print(f"  -> Parámetros Bayesianos: Media Global (C) = {C_mean:.2f} | Umbral de Votos (m, p75) = {m_threshold:.0f}")

    # 3. Query de integración dimensional con Netflix Top 10
    query_master = f"""
    COPY (
        SELECT 
            b.tconst,
            b.primaryTitle,
            b.titleType,
            b.startYear,
            b.runtimeMinutes,
            b.genres,
            COALESCE(a.num_regiones, 1) AS num_regiones,
            COALESCE(a.num_idiomas, 1) AS num_idiomas,
            COALESCE(SPLIT_PART(a.regiones_str, ',', 1), 'UNKNOWN') AS domestic_region,
            a.regiones_str,
            r.averageRating,
            r.numVotes,
            -- Fórmula de Promedio Bayesiano: (v / (v + m)) * R + (m / (v + m)) * C
            ROUND(
                (r.numVotes::DOUBLE / (r.numVotes + {m_threshold})) * r.averageRating +
                ({m_threshold}::DOUBLE / (r.numVotes + {m_threshold})) * {C_mean}, 
                2
            ) AS bayesian_rating,
            -- Métricas del Netflix Top 10 Semanal Oficial
            COALESCE(net.in_netflix_top10, 0) AS in_netflix_top10,
            COALESCE(net.netflix_semanas_top10, 0) AS netflix_semanas_top10,
            COALESCE(net.netflix_horas_vistas, 0) AS netflix_horas_vistas,
            COALESCE(net.netflix_paises_alcanzados, 0) AS netflix_paises_alcanzados,
            net.netflix_categoria
        FROM '{basics_p.as_posix()}' b
        INNER JOIN '{ratings_p.as_posix()}' r ON b.tconst = r.tconst
        LEFT JOIN '{akas_agg_p.as_posix()}' a ON b.tconst = a.tconst
        LEFT JOIN '{netflix_agg_p.as_posix()}' net ON LOWER(TRIM(b.primaryTitle)) = net.clean_title
        WHERE b.startYear BETWEEN {MIN_START_YEAR} AND {MAX_START_YEAR}
          AND b.runtimeMinutes BETWEEN {MIN_RUNTIME} AND {MAX_RUNTIME}
          AND r.numVotes >= {MIN_VOTES_FILTER}
    ) TO '{out_master_p.as_posix()}' (FORMAT 'PARQUET', COMPRESSION 'SNAPPY');
    """
    con.execute(query_master)
    
    # 4. Auditoría de Cascada (Waterfall)
    final_master_count = con.execute(f"SELECT COUNT(*) FROM '{out_master_p.as_posix()}'").fetchone()[0]
    total_ratings = con.execute(f"SELECT COUNT(*) FROM '{ratings_p.as_posix()}'").fetchone()[0]
    netflix_matched = con.execute(f"SELECT COUNT(*) FROM '{out_master_p.as_posix()}' WHERE in_netflix_top10 = 1").fetchone()[0]
    
    loss_summary = {
        "universo_basics_filtrado": total_basics,
        "universo_ratings_total": total_ratings,
        "catalogo_master_final": final_master_count,
        "titulos_netflix_top10_cruzados": netflix_matched,
        "pct_cobertura_basics": round((final_master_count / total_basics) * 100, 2),
        "bayes_C_mean": round(C_mean, 2),
        "bayes_m_threshold": round(m_threshold, 0)
    }
    
    report_md = f"""# Reporte de Auditoría y Cascada de Población (Etapa 2)

- **Total Títulos Filtrados en Basics (Movies/Series no adultas):** {total_basics:,}
- **Total Títulos con Ratings Registrados:** {total_ratings:,}
- **Catálogo Maestro Final Integrado (Join 1:1 + Filtro Temporal y Votos):** {final_master_count:,}
- **Títulos con Coincidencia en Netflix Top 10 Semanal Oficial:** {netflix_matched:,}
- **Retención Poblacional Respecto a Basics:** {loss_summary['pct_cobertura_basics']}%

### Parámetros del Promedio Bayesiano:
- **Media Global ($C$):** {C_mean:.2f}
- **Umbral de Votos p75 ($m$):** {m_threshold:.0f}
- **Fórmula Aplicada:** $WR = \\frac{{v}}{{v + m}} \\cdot R + \\frac{{m}}{{v + m}} \\cdot C$

### Fuentes Integradas en Grano tconst:
1. `title.basics` (Atributos de título, metraje y año)
2. `title.ratings` (Popularidad y calificación bayesiana)
3. `title.akas` pre-agregado (Huella de internacionalización y país doméstico)
4. `Netflix Top 10` (Horas de consumo acumuladas y semanas de permanencia)
"""
    waterfall_path = REPORTS_DIR / "waterfall_population_report.md"
    waterfall_path.write_text(report_md, encoding="utf-8")
    
    print(f"  -> Catálogo maestro guardado en: {out_master_p.name} ({final_master_count:,} títulos)")
    print(f"  -> Coincidencias validadas con Netflix Top 10: {netflix_matched:,} títulos.")
    print(f"  -> Reporte de cascada generado en: {waterfall_path.name}")
    
    df_sample = con.execute(f"SELECT primaryTitle, startYear, domestic_region, bayesian_rating, in_netflix_top10, netflix_horas_vistas FROM '{out_master_p.as_posix()}' WHERE in_netflix_top10 = 1 LIMIT 5").df()
    return df_sample, loss_summary

def run_stage2():
    aggregate_akas_no_explosion()
    build_master_catalog_with_bayes()

if __name__ == "__main__":
    run_stage2()
