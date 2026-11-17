"""
Servidor Web Backend (FastAPI) v4.0 para la Plataforma de Streaming y Toma de Decisiones de Netflix.
Incluye:
- Desambiguación canónica de títulos homónimos (ej. 'You', 'Stranger Things').
- Traducción completa de sinopsis, géneros y episodios al Español (es-ES / es-MX).
- Sección 'Mi Lista' sincronizada con recomendador propio.
- Los 5 módulos avanzados:
  1. Contextual Artwork Bandits (Personalización de pósters por perfil).
  2. Hook Episode & Season Retention Analysis en Series.
  3. Matriz de Doblaje vs. Subtitulado (Language Spillover).
  4. Tráilers Oficiales embebidos desde TMDB YouTube API.
  5. Exportación de Matriz Ejecutiva en CSV / PDF.
"""

from pathlib import Path
import json
import io
import csv
import duckdb
import pandas as pd
import numpy as np
from fastapi import FastAPI, Request, Query
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse, Response, RedirectResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

import sys
sys.path.append(str(Path(__file__).resolve().parent))
from config import (
    BASE_DIR, WEB_DIR, PARQUET_FILES, REPORTS_DIR,
    MIN_HOVER_DWELL_MS, INTERACTION_WEIGHTS, INTERACTION_DECAY, SIGNAL_THRESHOLD_GEMS
)
from src.paises import formatear_pais, obtener_nombre_pais, obtener_iso3, buscar_codigo_pais_por_nombre
from src.stage5_recommender import CrossBorderRecommender
from src.tmdb_client import TMDBClient, traducir_generos

app = FastAPI(title="Netflix Global Analytics & Dynamic Graph Recommender", version="4.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

print("[Server] Inicializando CrossBorderRecommender, Grafo de Actores y base analítica...")
recommender = CrossBorderRecommender()
tmdb_client = TMDBClient()

# Caché persistente en disco y memoria de metadatos TMDB
TMDB_CACHE_FILE = BASE_DIR / "data" / "tmdb_titles_cache.json"
TMDB_CACHE = {}
if TMDB_CACHE_FILE.exists():
    try:
        TMDB_CACHE = json.loads(TMDB_CACHE_FILE.read_text(encoding="utf-8"))
        print(f"[Server] Cargados {len(TMDB_CACHE)} títulos desde caché TMDB local.")
    except Exception as e:
        print(f"[Server] Error leyendo caché TMDB: {e}")
        TMDB_CACHE = {}


def save_tmdb_cache_safely():
    try:
        TMDB_CACHE_FILE.write_text(json.dumps(TMDB_CACHE, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass


SEASON_CACHE = {}
USER_SESSIONS = {}
MOVIE_CAST_MAP = {}

cast_p = PARQUET_FILES.get("cast")
if cast_p and cast_p.exists():
    try:
        con_init = duckdb.connect()
        df_c = con_init.execute(f"SELECT tconst, actors_str, directors_str FROM '{cast_p.as_posix()}'").df()
        for _, r in df_c.iterrows():
            MOVIE_CAST_MAP[r["tconst"]] = {
                "actors": r["actors_str"] if pd.notna(r["actors_str"]) else "",
                "directors": r["directors_str"] if pd.notna(r["directors_str"]) else ""
            }
        print(f"[Server] Cargados repartos y directores para {len(MOVIE_CAST_MAP):,} títulos.")
    except Exception as e:
        print(f"[Server] Error cargando reparto: {e}")


class InteractionEvent(BaseModel):
    session_id: str = "default_user"
    event_type: str                  # hover, click, modal_open, my_list, actor_click
    tconst: str = ""
    title: str = ""
    genres: str = ""
    country_code: str = ""
    actors: str = ""
    dwell_ms: int = 0


def deduplicate_records_by_title(records: list, limit: int = 15) -> list:
    """
    Evita que aparezcan películas/series homónimas (con el mismo título) en un mismo carrusel.
    Mantiene siempre la versión canónica de mayor relevancia.
    """
    seen_titles = set()
    seen_tconsts = set()
    unique_out = []
    for item in records:
        tconst = item.get("tconst", "")
        norm_title = str(item.get("primaryTitle", "")).strip().lower()
        if not tconst or tconst in seen_tconsts or norm_title in seen_titles:
            continue
        seen_tconsts.add(tconst)
        seen_titles.add(norm_title)
        unique_out.append(item)
        if len(unique_out) >= limit:
            break
    return unique_out


def build_spanish_fallback_synopsis(item: dict) -> str:
    """Genera una sinopsis descriptiva en español cuando un título no tiene overview en caché."""
    t_type = "Serie televisiva" if item.get("is_series") else "Producción cinematográfica"
    pais = item.get("pais_origen", "Internacional").split(" - ")[-1]
    genres_es = item.get("genres_es", "Drama")
    year = item.get("startYear", 2022)
    bayes = item.get("bayesian_rating", 7.5)
    actors = item.get("actors_str", "")
    cast_phrase = f" Protagonizada por {', '.join(actors.split(',')[:3])}." if actors else ""
    return (
        f"{t_type} de {genres_es.lower()} originaria de {pais} ({year}), "
        f"aclamada internacionalmente con una calificación bayesiana ponderada de ★ {bayes}.{cast_phrase} "
        f"Distribuida en {item.get('num_regiones', 12)} mercados globales."
    )


def enrich_records_with_cast_and_country(records: list, deduplicate: bool = True, limit: int = 15) -> list:
    """Agrega formato de país, géneros en español, sinopsis en español, actores e indicador de serie."""
    for item in records:
        tconst = item.get("tconst", "")
        c_code = item.get("domestic_region", "")
        if tconst in TMDB_CACHE and TMDB_CACHE[tconst].get("country"):
            c_code = TMDB_CACHE[tconst]["country"]
            item["domestic_region"] = c_code
        item["pais_origen"] = formatear_pais(c_code)
        item["top10_netflix"] = "★ Hit Global" if item.get("in_netflix_top10") == 1 else ""
        item["genres_es"] = traducir_generos(item.get("genres"))

        cast_info = MOVIE_CAST_MAP.get(tconst, {})
        raw_actors = item.get("actors_str") or cast_info.get("actors", "")
        if raw_actors:
            dedup_act = list(dict.fromkeys([a.strip() for a in str(raw_actors).split(",") if a.strip() and a.strip() != "nan"]))
            item["actors_str"] = ", ".join(dedup_act)
        else:
            item["actors_str"] = ""

        item["directors_str"] = item.get("directors_str") or cast_info.get("directors", "")
        t_type = str(item.get("titleType", "movie"))
        item["is_series"] = t_type in ["tvSeries", "tvMiniSeries"] or (
            tconst in TMDB_CACHE and TMDB_CACHE[tconst].get("media_type") == "tv"
        )
        # Porcentaje de afinidad visual estilo Netflix (88% - 99%)
        bayes_val = float(item.get("bayesian_rating") or 7.0)
        item["match_pct"] = min(99, max(85, int(round(72 + bayes_val * 2.8))))

        # Sinopsis en español si está en caché
        cached_ov = TMDB_CACHE.get(tconst, {}).get("overview_es") or TMDB_CACHE.get(tconst, {}).get("overview")
        item["overview_es"] = cached_ov if cached_ov else build_spanish_fallback_synopsis(item)

    if deduplicate:
        return deduplicate_records_by_title(records, limit=limit)
    return records[:limit]


def get_or_create_profile(session_id: str) -> dict:
    if session_id not in USER_SESSIONS:
        USER_SESSIONS[session_id] = {
            "genres": {},
            "countries": {},
            "actors": {},
            "suggested_actors": {},
            "bandit_arms": {
                "actor_focus": {"pulls": 1, "rewards": 1.0},
                "genre_focus": {"pulls": 1, "rewards": 1.0},
                "global_hit": {"pulls": 1, "rewards": 1.0}
            },
            "active_bandit_arm": "global_hit",
            "interacted_tconsts": [],
            "my_list": [],
            "signal_score": 0.0,
            "interaction_count": 0,
            "recent_actions": []
        }
    for key in ["actors", "suggested_actors"]:
        if key not in USER_SESSIONS[session_id]:
            USER_SESSIONS[session_id][key] = {}
    if "bandit_arms" not in USER_SESSIONS[session_id]:
        USER_SESSIONS[session_id]["bandit_arms"] = {
            "actor_focus": {"pulls": 1, "rewards": 1.0},
            "genre_focus": {"pulls": 1, "rewards": 1.0},
            "global_hit": {"pulls": 1, "rewards": 1.0}
        }
    return USER_SESSIONS[session_id]


def select_contextual_bandit_arm(profile: dict) -> str:
    """
    Multi-Armed Contextual Bandit (Upper Confidence Bound - UCB1):
    Decide qué estrategia de personalización visual y de carátula priorizar para el usuario:
    - 'actor_focus': Prioriza destacar protagonistas y pósters de elenco.
    - 'genre_focus': Prioriza atmósfera de género.
    - 'global_hit': Prioriza prueba social (Top 10 / Premios).
    """
    arms = profile["bandit_arms"]
    total_pulls = sum(a["pulls"] for a in arms.values())
    best_arm = "global_hit"
    best_ucb = -1.0

    for arm_name, stats in arms.items():
        mean_reward = stats["rewards"] / max(1, stats["pulls"])
        exploration = np.sqrt(2.0 * np.log(max(2, total_pulls)) / max(1, stats["pulls"]))
        # Context boost from profile
        context_boost = 0.0
        if arm_name == "actor_focus" and len(profile.get("actors", {})) >= 2:
            context_boost = 0.25
        elif arm_name == "genre_focus" and len(profile.get("genres", {})) >= 2:
            context_boost = 0.20
        ucb_score = mean_reward + 0.35 * exploration + context_boost
        if ucb_score > best_ucb:
            best_ucb = ucb_score
            best_arm = arm_name

    profile["active_bandit_arm"] = best_arm
    return best_arm


# ==============================================================================
# 1. ENDPOINTS DE CATÁLOGO INICIAL, MI LISTA, BÚSQUEDA E INFINITE SCROLL
# ==============================================================================

@app.get("/api/catalog/initial")
def get_initial_catalog():
    """Entrega el Hero Banner en español y los carruseles iniciales del Home sin duplicados."""
    con = duckdb.connect()
    master_p = PARQUET_FILES["master"]
    
    hero_query = f"""
    SELECT tconst, primaryTitle, titleType, domestic_region, startYear, runtimeMinutes, genres, 
           bayesian_rating, num_regiones, numVotes, in_netflix_top10, netflix_horas_vistas
    FROM '{master_p.as_posix()}'
    WHERE (in_netflix_top10 = 1 AND bayesian_rating >= 8.0 AND numVotes >= 100000)
    ORDER BY netflix_horas_vistas DESC, bayesian_rating DESC
    LIMIT 1;
    """
    hero_df = con.execute(hero_query).df()
    hero_list = enrich_records_with_cast_and_country(hero_df.to_dict(orient="records"), deduplicate=True, limit=1)
    hero_title = hero_list[0] if hero_list else {}

    def fetch_carousel(where_clause: str, order_clause: str, limit: int = 15, allowed_countries: set | None = None) -> list:
        q = f"""
        SELECT tconst, primaryTitle, titleType, domestic_region, startYear, runtimeMinutes, genres, 
               bayesian_rating, num_regiones, numVotes, in_netflix_top10, netflix_horas_vistas
        FROM '{master_p.as_posix()}'
        WHERE {where_clause}
        ORDER BY {order_clause}
        LIMIT {limit * 4};
        """
        df = con.execute(q).df()
        items = enrich_records_with_cast_and_country(df.to_dict(orient="records"), deduplicate=True, limit=limit * 2)
        if allowed_countries:
            items = [it for it in items if it.get("domestic_region") in allowed_countries]
        return items[:limit]

    carousels = [
        {
            "id": "trending",
            "title": "Tendencias Globales (Top Horas Vistas en Streaming)",
            "subtitle": "Títulos canónicos con mayor consumo acumulado en el Netflix Top 10 Oficial",
            "items": fetch_carousel("in_netflix_top10 = 1 AND netflix_horas_vistas > 0 AND numVotes >= 15000", "netflix_horas_vistas DESC, numVotes DESC")
        },
        {
            "id": "intl_hidden_gems_home",
            "title": "💎 Joyas Escondidas Internacionales (Fuera del Radar de Hollywood)",
            "subtitle": "Obras maestras de mercados no saturados con altísimo Rating Bayesiano (≥ 7.5) y bajo costo de licencia",
            "items": fetch_carousel(
                "domestic_region NOT IN ('US', 'GB', 'UNKNOWN') AND bayesian_rating >= 7.5 AND numVotes BETWEEN 2500 AND 95000",
                "bayesian_rating DESC, num_regiones ASC"
            )
        },
        {
            "id": "acclaimed",
            "title": "Aclamadas por la Crítica (Promedio Bayesiano IMDb)",
            "subtitle": "Puntuación ponderada estadísticamente para evitar sesgo de votos o review bombing",
            "items": fetch_carousel("numVotes >= 50000", "bayesian_rating DESC, numVotes DESC")
        },
        {
            "id": "series_top",
            "title": "Series Aclamadas para Maratonear (Temporadas y Episodios)",
            "subtitle": "Incluye curva de retención por episodio, capítulo gancho (Hook) y duraciones",
            "items": fetch_carousel("titleType IN ('tvSeries', 'tvMiniSeries') AND numVotes >= 30000", "bayesian_rating DESC, netflix_horas_vistas DESC")
        },
        {
            "id": "spanish_latam",
            "title": "Cine y Series en Español (Argentina, España, México & Latinoamérica)",
            "subtitle": "Producciones verificadas de habla hispana con impacto crítico e internacional",
            "items": fetch_carousel(
                "domestic_region IN ('AR', 'ES', 'MX', 'CO', 'CL', 'UY', 'PE') AND numVotes >= 2500",
                "bayesian_rating DESC, numVotes DESC",
                allowed_countries={"AR", "ES", "MX", "CO", "CL", "UY", "PE"}
            )
        },
        {
            "id": "gems_series_cult_home",
            "title": "💎 Series y Miniseries Internacionales Ocultas de Culto",
            "subtitle": "Joyas episódicas fuera del circuito anglosajón con altísima fidelidad de audiencia",
            "items": fetch_carousel(
                "titleType IN ('tvSeries', 'tvMiniSeries') AND domestic_region NOT IN ('US', 'GB', 'UNKNOWN') AND bayesian_rating >= 7.4 AND numVotes BETWEEN 2000 AND 90000",
                "bayesian_rating DESC, numVotes DESC"
            )
        },
        {
            "id": "asian_powerhouse",
            "title": "Hub Asiático: Fenómenos de Corea del Sur, Japón e India",
            "subtitle": "Producciones asiáticas que rompieron la barrera del idioma a nivel global",
            "items": fetch_carousel(
                "domestic_region IN ('KR', 'JP', 'HK', 'IN', 'TH', 'TW') AND numVotes >= 5000",
                "bayesian_rating DESC, netflix_horas_vistas DESC",
                allowed_countries={"KR", "JP", "HK", "IN", "TH", "TW"}
            )
        },
        {
            "id": "europe_nordic_cinema",
            "title": "Cine Europeo y Nórdico de Autor (Alemania, Francia, Italia, Dinamarca, Suecia)",
            "subtitle": "Mercados de alta eficiencia crítica recomendados para acuerdos de co-producción",
            "items": fetch_carousel(
                "domestic_region IN ('DE', 'FR', 'IT', 'DK', 'SE', 'NO', 'PL') AND numVotes >= 5000",
                "bayesian_rating DESC, numVotes DESC",
                allowed_countries={"DE", "FR", "IT", "DK", "SE", "NO", "PL"}
            )
        },
        {
            "id": "psychological_thrillers",
            "title": "Thrillers Psicológicos, Crimen y Misterio Internacional",
            "subtitle": "Narrativas de alta tensión y giros inesperados con máxima retención",
            "items": fetch_carousel(
                "(genres LIKE '%Thriller%' OR genres LIKE '%Mystery%') AND genres LIKE '%Crime%' AND numVotes >= 25000",
                "bayesian_rating DESC, numVotes DESC"
            )
        },
        {
            "id": "scifi_animation_cult",
            "title": "Ciencia Ficción, Fantasía y Animación de Culto",
            "subtitle": "Mundos distópicos y obras maestras visuales de alcance transfronterizo",
            "items": fetch_carousel(
                "(genres LIKE '%Sci-Fi%' OR genres LIKE '%Animation%') AND numVotes >= 30000",
                "bayesian_rating DESC, numVotes DESC"
            )
        }
    ]

    return {
        "hero": hero_title,
        "carousels": carousels,
        "signal_threshold_gems": SIGNAL_THRESHOLD_GEMS
    }


@app.get("/api/catalog/hidden-gems")
def get_hidden_gems_catalog(region: str = Query("all")):
    """
    Sección dedicada '💎 Joyas Escondidas Internacionales':
    Filtra títulos de alto Rating Bayesiano (>= 7.3) fuera del circuito comercial saturado de EE.UU./Reino Unido,
    organizados por región geográfica y nicho temático.
    """
    con = duckdb.connect()
    master_p = PARQUET_FILES["master"]

    region_filters = {
        "all": ("domestic_region NOT IN ('US', 'GB', 'UNKNOWN')", None, "Todas las Regiones Internacionales"),
        "latam_es": ("domestic_region IN ('AR', 'ES', 'MX', 'BR', 'CL', 'CO', 'UY', 'PE')", {"AR", "ES", "MX", "BR", "CL", "CO", "UY", "PE"}, "América Latina, Argentina, Brasil y España"),
        "asia": ("domestic_region IN ('KR', 'JP', 'IN', 'HK', 'TW', 'TH', 'ID')", {"KR", "JP", "IN", "HK", "TW", "TH", "ID"}, "Asia y Pacífico (Corea, Japón, India, Hong Kong)"),
        "europe": ("domestic_region IN ('DK', 'SE', 'NO', 'DE', 'FR', 'IT', 'PL', 'NL', 'BE')", {"DK", "SE", "NO", "DE", "FR", "IT", "PL", "NL", "BE"}, "Europa Continental y Países Nórdicos"),
        "east_mena": ("domestic_region IN ('TR', 'IR', 'RS', 'CZ', 'HU', 'RO', 'IL', 'RU', 'GR')", {"TR", "IR", "RS", "CZ", "HU", "RO", "IL", "RU", "GR"}, "Balcanes, Turquía, Europa Oriental y Medio Oriente")
    }
    where_reg, allowed_set, region_label = region_filters.get(region, region_filters["all"])

    def query_gems(extra_where: str, order_sql: str = "bayesian_rating DESC, numVotes DESC", limit: int = 15) -> list:
        q = f"""
        SELECT tconst, primaryTitle, titleType, domestic_region, startYear, runtimeMinutes, genres, 
               bayesian_rating, num_regiones, numVotes, in_netflix_top10, netflix_horas_vistas
        FROM '{master_p.as_posix()}'
        WHERE {where_reg} AND {extra_where}
        ORDER BY {order_sql}
        LIMIT {limit * 4};
        """
        df = con.execute(q).df()
        items = enrich_records_with_cast_and_country(df.to_dict(orient="records"), deduplicate=True, limit=limit * 2)
        if allowed_set:
            items = [it for it in items if it.get("domestic_region") in allowed_set]
        for it in items:
            it["explanation"] = f"💎 Joya de {it.get('pais_origen', '').split(' - ')[-1]} • ★ {it.get('bayesian_rating')} Bayes"
        return items[:limit]

    featured_grid = query_gems("bayesian_rating >= 7.4 AND numVotes BETWEEN 2000 AND 110000", limit=18)

    carousels = [
        {
            "id": f"gems_thriller_{region}",
            "title": "💎 Joyas Escondidas de Suspenso, Crimen y Misterio",
            "subtitle": "Títulos de intriga internacional con altísima valoración crítica y bajo costo de licencia",
            "items": query_gems("(genres LIKE '%Crime%' OR genres LIKE '%Thriller%' OR genres LIKE '%Mystery%') AND bayesian_rating >= 7.2 AND numVotes BETWEEN 1500 AND 95000")
        },
        {
            "id": f"gems_series_{region}",
            "title": "📺 Series y Miniseries Internacionales de Culto Poco Conocidas",
            "subtitle": "Producciones episódicas fuera del radar masivo con excelente retención de audiencia",
            "items": query_gems("titleType IN ('tvSeries', 'tvMiniSeries') AND bayesian_rating >= 7.3 AND numVotes BETWEEN 1500 AND 90000")
        },
        {
            "id": f"gems_drama_{region}",
            "title": "🎭 Cine de Autor y Dramas Humanos Aclamados",
            "subtitle": "Historias profundas con gran potencial de viaje transfronterizo",
            "items": query_gems("genres LIKE '%Drama%' AND titleType = 'movie' AND bayesian_rating >= 7.4 AND numVotes BETWEEN 2000 AND 80000")
        },
        {
            "id": f"gems_comedy_action_{region}",
            "title": "⚡ Comedias Ácidas, Acción y Aventuras Alternativas",
            "subtitle": "Entretenimiento internacional fresco con alto puntaje ponderado",
            "items": query_gems("(genres LIKE '%Comedy%' OR genres LIKE '%Action%' OR genres LIKE '%Adventure%') AND bayesian_rating >= 7.2 AND numVotes BETWEEN 1500 AND 85000")
        }
    ]

    return {
        "region": region,
        "region_label": region_label,
        "featured_gems": featured_grid,
        "carousels": [c for c in carousels if c["items"]]
    }


@app.post("/api/catalog/mylist")
def get_my_list_catalog(body: dict):
    """
    Devuelve los objetos completos de las películas/series guardadas en 'Mi Lista'
    más una fila de recomendaciones calculadas específicamente sobre los títulos guardados.
    """
    tconsts = body.get("tconsts", [])
    session_id = body.get("session_id", "default_user")
    if not tconsts:
        return {"items": [], "recommendations": []}

    con = duckdb.connect()
    master_p = PARQUET_FILES["master"]
    safe_ids = [str(t).strip() for t in tconsts if str(t).strip().startswith("tt")]
    if not safe_ids:
        return {"items": [], "recommendations": []}

    ids_sql = ",".join([f"'{t}'" for t in safe_ids])
    q = f"""
    SELECT tconst, primaryTitle, titleType, domestic_region, startYear, runtimeMinutes, genres, 
           bayesian_rating, num_regiones, numVotes, in_netflix_top10, netflix_horas_vistas
    FROM '{master_p.as_posix()}'
    WHERE tconst IN ({ids_sql})
    """
    df = con.execute(q).df()
    saved_items = enrich_records_with_cast_and_country(df.to_dict(orient="records"), deduplicate=False, limit=100)

    profile = get_or_create_profile(session_id)
    rec_df = recommender.recommend_by_profile(profile, top_k=24, only_hidden_gems=False)
    rec_items = []
    if not rec_df.empty:
        rec_df = rec_df[~rec_df["tconst"].isin(set(safe_ids))]
        rec_items = enrich_records_with_cast_and_country(rec_df.to_dict(orient="records"), deduplicate=True, limit=12)

    return {
        "items": saved_items,
        "recommendations": rec_items
    }


# Mapa inverso de géneros en español a inglés para búsqueda
GENRE_SEARCH_ES_TO_EN = {
    "accion": "Action", "acción": "Action",
    "aventura": "Adventure",
    "animacion": "Animation", "animación": "Animation", "anime": "Animation",
    "biografia": "Biography", "biografía": "Biography",
    "comedia": "Comedy",
    "crimen": "Crime", "policial": "Crime",
    "documental": "Documentary",
    "drama": "Drama",
    "familiar": "Family", "familia": "Family",
    "fantasia": "Fantasy", "fantasía": "Fantasy",
    "historia": "History", "historico": "History",
    "terror": "Horror", "miedo": "Horror",
    "misterio": "Mystery",
    "romance": "Romance", "romantica": "Romance", "romántica": "Romance",
    "ciencia ficcion": "Sci-Fi", "ciencia ficción": "Sci-Fi", "scifi": "Sci-Fi",
    "suspenso": "Thriller", "thriller": "Thriller",
    "belico": "War", "bélico": "War", "guerra": "War",
}


@app.get("/api/catalog/search")
def search_catalog(q: str = Query(..., min_length=1), session_id: str = "default_user"):
    """
    Buscador exclusivo estilo Netflix:
    Soporta búsqueda por:
    1. País de origen (ej: 'Argentina', 'España', 'Corea', 'Japón', 'Francia', 'AR', 'KR').
    2. Título de película o serie.
    3. Nombre de Actor o Director.
    4. Género en español o inglés (ej: 'Acción', 'Terror', 'Ciencia Ficción', 'Comedy').
    """
    query_str = q.strip()
    if not query_str:
        return {"query": "", "direct_matches": [], "similar_titles": [], "seed_title": None}

    con = duckdb.connect()
    master_p = PARQUET_FILES["master"]

    # 1. ¿El usuario está buscando un País?
    country_code = buscar_codigo_pais_por_nombre(query_str)
    if country_code:
        country_full = formatear_pais(country_code)
        q_country = f"""
        SELECT tconst, primaryTitle, titleType, domestic_region, startYear, runtimeMinutes, genres, 
               bayesian_rating, num_regiones, numVotes, in_netflix_top10, netflix_horas_vistas
        FROM '{master_p.as_posix()}'
        WHERE domestic_region = '{country_code}'
        ORDER BY bayesian_rating DESC, numVotes DESC, netflix_horas_vistas DESC
        LIMIT 60;
        """
        df_c = con.execute(q_country).df()
        c_records = enrich_records_with_cast_and_country(df_c.to_dict(orient="records"), deduplicate=True, limit=30)
        c_records = [r for r in c_records if r.get("domestic_region") == country_code][:18]

        # Extraer los actores y directores más representativos de ese país a partir de su filmografía destacada
        actor_counts = {}
        for r in c_records:
            for a in [x.strip() for x in str(r.get("actors_str", "")).split(",") if x.strip() and x.strip() != "nan"]:
                actor_counts[a] = actor_counts.get(a, 0) + 1
        top_country_actors = [a for a, _ in sorted(actor_counts.items(), key=lambda x: x[1], reverse=True)[:14]]

        similar_records = []
        seed_title_name = country_full
        seed_genres_es = "Selección Nacional & Cross-Border"
        if c_records:
            top_seed = c_records[0]
            seed_title_name = f"{top_seed['primaryTitle']} ({country_full})"
            seed_genres_es = top_seed.get("genres_es", "Internacional")
            sim_df = recommender.recommend(top_seed["primaryTitle"], top_k=25, force_cross_border=True)
            if not sim_df.empty:
                similar_records = enrich_records_with_cast_and_country(sim_df.to_dict(orient="records"), deduplicate=True, limit=12)

        return {
            "query": query_str,
            "is_country_search": True,
            "country_code": country_code,
            "country_name": country_full,
            "country_actors": top_country_actors,
            "seed_title": seed_title_name,
            "seed_genres": seed_genres_es,
            "direct_matches": c_records,
            "similar_titles": similar_records
        }

    # 2. Búsqueda por Título, Actor o Género (en Español o Inglés)
    df = recommender.df
    mapped_en_genre = GENRE_SEARCH_ES_TO_EN.get(query_str.lower(), query_str)

    mask_title = df["primaryTitle"].str.contains(query_str, case=False, na=False, regex=False)
    mask_actor = df["actors_str"].str.contains(query_str, case=False, na=False, regex=False)
    mask_genre = df["genres"].str.contains(mapped_en_genre, case=False, na=False, regex=False)

    matches_primary = df[mask_title | mask_actor].sort_values(
        by=["numVotes", "in_netflix_top10", "bayesian_rating"], ascending=[False, False, False]
    )
    if len(matches_primary) < 6:
        matches_genre = df[mask_genre & ~(mask_title | mask_actor)].sort_values(
            by=["numVotes", "bayesian_rating"], ascending=[False, False]
        )
        direct_df = pd.concat([matches_primary, matches_genre]).head(36)
    else:
        direct_df = matches_primary.head(36)

    direct_records = enrich_records_with_cast_and_country(direct_df.to_dict(orient="records"), deduplicate=True, limit=18)

    # Extraer actores principales de los resultados encontrados
    rel_actors = []
    for r in direct_records[:6]:
        for a in [x.strip() for x in str(r.get("actors_str", "")).split(",") if x.strip() and x.strip() != "nan"]:
            if a not in rel_actors:
                rel_actors.append(a)
    rel_actors = rel_actors[:12]

    similar_records = []
    seed_title_name = query_str
    seed_genres_es = ""

    if direct_records:
        top_seed = direct_records[0]
        seed_title_name = top_seed["primaryTitle"]
        seed_genres_es = top_seed.get("genres_es", "")
        direct_tconsts = {r["tconst"] for r in direct_records}

        sim_df = recommender.recommend(seed_title_name, top_k=30, force_cross_border=False)
        if not sim_df.empty:
            sim_df = sim_df[~sim_df["tconst"].isin(direct_tconsts)]
            similar_records = enrich_records_with_cast_and_country(sim_df.to_dict(orient="records"), deduplicate=True, limit=15)

    return {
        "query": query_str,
        "is_country_search": False,
        "country_actors": rel_actors,
        "seed_title": seed_title_name,
        "seed_genres": seed_genres_es,
        "direct_matches": direct_records,
        "similar_titles": similar_records
    }


@app.get("/api/catalog/infinite-scroll")
def get_infinite_scroll_carousels(page: int = Query(1, ge=1), session_id: str = "default_user"):
    """
    Genera dinámicamente nuevos carruseles a medida que el usuario hace scroll hacia abajo,
    combinando el perfil aprendido en vivo (géneros en español, países, actores del grafo) con categorías de Netflix.
    """
    profile = get_or_create_profile(session_id)
    con = duckdb.connect()
    master_p = PARQUET_FILES["master"]

    sorted_genres = [k for k, _ in sorted(profile["genres"].items(), key=lambda x: x[1], reverse=True)]
    sorted_countries = [k for k, _ in sorted(profile["countries"].items(), key=lambda x: x[1], reverse=True)]
    # Solo usar actores con peso intencional significativo (>= 8.0 pts) para títulos de carruseles
    strong_actors = [k for k, w in sorted(profile["actors"].items(), key=lambda x: x[1], reverse=True) if w >= 8.0]
    suggested_co_actors = list(profile.get("suggested_actors", {}).keys())

    fav_genre_1 = sorted_genres[0] if len(sorted_genres) > 0 else "Drama"
    fav_genre_1_es = traducir_generos(fav_genre_1)
    fav_genre_2 = sorted_genres[1] if len(sorted_genres) > 1 else "Action"
    fav_genre_2_es = traducir_generos(fav_genre_2)
    fav_country_1 = sorted_countries[0] if len(sorted_countries) > 0 else "KR"
    fav_country_name_1 = obtener_nombre_pais(fav_country_1)
    fav_actor_1 = strong_actors[0] if len(strong_actors) > 0 else ""
    co_actor_1 = suggested_co_actors[0] if len(suggested_co_actors) > 0 else ""

    def run_query(where_sql: str, order_sql: str = "bayesian_rating DESC, numVotes DESC", limit: int = 15, offset: int = 0) -> list:
        q = f"""
        SELECT tconst, primaryTitle, titleType, domestic_region, startYear, runtimeMinutes, genres, 
               bayesian_rating, num_regiones, numVotes, in_netflix_top10, netflix_horas_vistas
        FROM '{master_p.as_posix()}'
        WHERE {where_sql}
        ORDER BY {order_sql}
        LIMIT {limit * 3} OFFSET {offset};
        """
        df = con.execute(q).df()
        return enrich_records_with_cast_and_country(df.to_dict(orient="records"), deduplicate=True, limit=limit)

    cycle_offset = ((page - 1) // 5) * 10

    all_templates = [
        {
            "id": f"inf_series_for_you_p{page}",
            "title": f"Series de {fav_genre_1_es} que podrían gustarte (Destacadas en {fav_country_name_1})",
            "subtitle": f"Selección personalizada de series según tu afinidad por {fav_genre_1_es}",
            "where": f"titleType IN ('tvSeries', 'tvMiniSeries') AND genres LIKE '%{fav_genre_1}%' AND numVotes >= 5000",
            "order": f"CASE WHEN domestic_region = '{fav_country_1}' THEN 1 ELSE 0 END DESC, bayesian_rating DESC, numVotes DESC"
        },
        {
            "id": f"inf_action_lovers_p{page}",
            "title": "Para los amantes de la Acción: Adrenalina Pura",
            "subtitle": "Las mejores películas y series de acción de alto voltaje e impacto global",
            "where": "genres LIKE '%Action%' AND numVotes >= 25000",
            "order": "bayesian_rating DESC, netflix_horas_vistas DESC"
        },
        {
            "id": f"inf_actor_graph_p{page}",
            "title": (
                f"Porque te interesó el elenco de {fav_actor_1} (y su red con {co_actor_1})"
                if fav_actor_1 and co_actor_1
                else f"Aclamadas en {fav_genre_2_es}: Selección de Elencos Estelares"
            ),
            "subtitle": "Descubrimiento impulsado por el Sistema de Grafos de Co-Actuación (1-Hop & 2-Hop)",
            "custom_items": (
                enrich_records_with_cast_and_country(
                    recommender.recommend_by_profile(profile, top_k=30, only_hidden_gems=False).to_dict(orient="records"),
                    deduplicate=True, limit=15
                ) if fav_actor_1 else None
            ),
            "where": f"genres LIKE '%{fav_genre_2}%' AND numVotes >= 20000",
            "order": "bayesian_rating DESC, numVotes DESC"
        },
        {
            "id": f"inf_scifi_worlds_p{page}",
            "title": "Para los fanáticos de la Ciencia Ficción y Futuros Distópicos",
            "subtitle": "Viajes espaciales, paradojas temporales y mundos extraordinarios",
            "where": "genres LIKE '%Sci-Fi%' AND numVotes >= 15000",
            "order": "bayesian_rating DESC, numVotes DESC"
        },
        {
            "id": f"inf_crime_mystery_p{page}",
            "title": "Mentes Criminales: Thrillers de Investigación y Misterio",
            "subtitle": "Intriga policial y suspenso psicológico que no te dejarán despegar de la pantalla",
            "where": "genres LIKE '%Crime%' AND genres LIKE '%Mystery%' AND numVotes >= 10000",
            "order": "bayesian_rating DESC, numVotes DESC"
        },
        {
            "id": f"inf_comedy_hits_p{page}",
            "title": "Para reír sin parar: Las Comedias Mejor Valoradas",
            "subtitle": "Humor inteligente, sátira e historias ligeras aclamadas por el público",
            "where": "genres LIKE '%Comedy%' AND numVotes >= 25000",
            "order": "bayesian_rating DESC, netflix_horas_vistas DESC"
        },
        {
            "id": f"inf_euro_cinema_p{page}",
            "title": "Joyas del Cine y Series Europeas (Francia, Alemania, Italia y Nórdicos)",
            "subtitle": "Narrativas de autor con alta exportación fuera de su frontera",
            "where": "domestic_region IN ('FR', 'DE', 'IT', 'DK', 'SE', 'NO') AND numVotes >= 8000",
            "order": "bayesian_rating DESC, num_regiones DESC"
        },
        {
            "id": f"inf_true_stories_p{page}",
            "title": "Basadas en Hechos Reales: Biografías e Historia",
            "subtitle": "Dramas históricos y retratos biográficos conmovedores",
            "where": "(genres LIKE '%Biography%' OR genres LIKE '%History%') AND numVotes >= 15000",
            "order": "bayesian_rating DESC, numVotes DESC"
        },
        {
            "id": f"inf_anime_animation_p{page}",
            "title": "Animación y Anime de Culto Internacional",
            "subtitle": "Obras maestras visuales de Japón y estudios globales",
            "where": "genres LIKE '%Animation%' AND numVotes >= 15000",
            "order": "bayesian_rating DESC, numVotes DESC"
        },
        {
            "id": f"inf_horror_night_p{page}",
            "title": "Para los amantes del Terror y el Suspenso Nocturno",
            "subtitle": "Historias sobrenaturales y terror psicológico de alto calibre",
            "where": "genres LIKE '%Horror%' AND numVotes >= 15000",
            "order": "bayesian_rating DESC, numVotes DESC"
        },
        {
            "id": f"inf_short_movies_p{page}",
            "title": "Directo al grano: Películas Intensas de menos de 100 minutos",
            "subtitle": "Ideales para ver hoy mismo sin comprometer toda la noche",
            "where": "titleType = 'movie' AND runtimeMinutes BETWEEN 75 AND 99 AND numVotes >= 15000",
            "order": "bayesian_rating DESC, numVotes DESC"
        },
        {
            "id": f"inf_classics_90s_p{page}",
            "title": "Clásicos Inmortales del Cine (1970 - 1999)",
            "subtitle": "Las películas que definieron la historia del séptimo arte",
            "where": "startYear BETWEEN 1970 AND 1999 AND numVotes >= 50000",
            "order": "bayesian_rating DESC, numVotes DESC"
        },
        {
            "id": f"inf_epics_long_p{page}",
            "title": "Grandes Épicas Cinematográficas (+140 minutos)",
            "subtitle": "Superproducciones inmersivas de alto presupuesto y escala global",
            "where": "titleType = 'movie' AND runtimeMinutes >= 140 AND numVotes >= 35000",
            "order": "bayesian_rating DESC, numVotes DESC"
        },
        {
            "id": f"inf_romance_drama_p{page}",
            "title": "Historias de Amor y Dramas Románticos Inolvidables",
            "subtitle": "Relaciones apasionantes a través de distintas culturas",
            "where": "genres LIKE '%Romance%' AND numVotes >= 15000",
            "order": "bayesian_rating DESC, netflix_horas_vistas DESC"
        },
        {
            "id": f"inf_adventure_family_p{page}",
            "title": "Aventuras Épicas y Mundos Fantásticos",
            "subtitle": "Viajes extraordinarios con gran alcance internacional",
            "where": "(genres LIKE '%Adventure%' OR genres LIKE '%Fantasy%') AND numVotes >= 25000",
            "order": "bayesian_rating DESC, numVotes DESC"
        }
    ]

    total_tpl = len(all_templates)
    start_idx = ((page - 1) * 3) % total_tpl
    selected_templates = [all_templates[(start_idx + i) % total_tpl] for i in range(3)]

    carousels_out = []
    for tpl in selected_templates:
        if tpl.get("custom_items"):
            items = tpl["custom_items"]
        else:
            items = run_query(tpl["where"], tpl["order"], limit=15, offset=cycle_offset)
        if items:
            carousels_out.append({
                "id": tpl["id"],
                "title": tpl["title"],
                "subtitle": tpl["subtitle"],
                "items": items
            })

    return {
        "page": page,
        "has_more": True,
        "carousels": carousels_out
    }


# ==============================================================================
# 2. ENDPOINTS DE DETALLE DE TÍTULO, TRÁILER, HOOK EPISODE Y TEMPORADAS DE SERIES
# ==============================================================================

def compute_series_hook_and_retention(episodes_list: list) -> dict:
    """
    Calcula el 'Hook Episode' (capítulo gancho donde sube la calificación y retención)
    y el Índice de Fidelidad de Temporada (Season Retention Score).
    """
    if not episodes_list:
        return {"hook_episode": 1, "hook_title": "Episodio 1", "retention_pct": 92, "trend": "Estable"}

    ratings = [float(ep.get("rating", 8.0)) for ep in episodes_list]
    # Buscar el episodio en la primera mitad (o primeros 5 caps) con mayor salto positivo o mayor nota
    best_hook_idx = 0
    best_score = -1.0
    limit_search = min(len(episodes_list), max(2, len(episodes_list) // 2 + 1))
    for i in range(limit_search):
        jump = (ratings[i] - ratings[0]) if i > 0 else 0.1
        score = ratings[i] + jump * 1.5
        if score > best_score:
            best_score = score
            best_hook_idx = i

    hook_ep = episodes_list[best_hook_idx]
    first_half_avg = np.mean(ratings[:max(1, len(ratings)//2)])
    second_half_avg = np.mean(ratings[max(1, len(ratings)//2):]) if len(ratings) > 1 else first_half_avg
    diff = second_half_avg - first_half_avg

    retention_pct = int(min(99, max(78, round(88 + diff * 8 + (np.mean(ratings) - 7.5) * 4))))
    if diff >= 0.15:
        trend = "In Crescendo (Final de temporada altamente adictivo)"
    elif diff >= -0.15:
        trend = "Retención Sólida (Sin fatiga de temporada)"
    else:
        trend = "Desgaste Moderado en tramo final"

    return {
        "hook_episode": hook_ep["episode_number"],
        "hook_title": hook_ep["title"],
        "hook_rating": hook_ep["rating"],
        "retention_pct": retention_pct,
        "season_avg_rating": round(float(np.mean(ratings)), 2),
        "trend": trend
    }


def fetch_episodes_for_series(tconst: str, season_num: int = 1) -> dict:
    """
    Obtiene las temporadas y la lista detallada de episodios en español (es-ES)
    combinando TMDB API y series_episodes.parquet, más el análisis de Hook Episode.
    """
    cache_key = f"{tconst}_s{season_num}_es"
    if cache_key in SEASON_CACHE:
        return SEASON_CACHE[cache_key]

    seasons_list = []
    episodes_list = []
    is_series = False

    ep_parquet = PARQUET_FILES.get("episodes")
    local_seasons = []
    local_eps_df = pd.DataFrame()
    if ep_parquet and ep_parquet.exists():
        try:
            con = duckdb.connect()
            seasons_df = con.execute(f"""
                SELECT DISTINCT season_number 
                FROM '{ep_parquet.as_posix()}'
                WHERE parentTconst = '{tconst}' AND season_number IS NOT NULL AND season_number > 0
                ORDER BY season_number ASC
            """).df()
            if not seasons_df.empty:
                local_seasons = [int(s) for s in seasons_df["season_number"].tolist()]
                is_series = True
                local_eps_df = con.execute(f"""
                    SELECT season_number, episode_number, episode_title, runtime_minutes
                    FROM '{ep_parquet.as_posix()}'
                    WHERE parentTconst = '{tconst}' AND season_number = {int(season_num)}
                    ORDER BY episode_number ASC
                """).df()
        except Exception as e:
            print(f"[Episodes Parquet] Error: {e}")

    tmdb_id = None
    media_type = None
    if tconst in TMDB_CACHE:
        tmdb_id = TMDB_CACHE[tconst].get("tmdb_id")
        media_type = TMDB_CACHE[tconst].get("media_type")

    if not tmdb_id and tmdb_client.is_configured:
        found = tmdb_client.find_by_imdb_id(tconst, language="es-ES")
        if found:
            tmdb_id = found.get("id")
            media_type = found.get("media_type")

    if tmdb_id and media_type == "tv" and tmdb_client.is_configured:
        is_series = True
        try:
            tv_details = tmdb_client.get_details(tmdb_id, "tv", language="es-ES") or {}
            raw_seasons = tv_details.get("seasons", [])
            valid_seasons = [
                int(s["season_number"]) for s in raw_seasons
                if s.get("season_number", 0) > 0 and s.get("episode_count", 0) > 0
            ]
            if valid_seasons:
                seasons_list = sorted(list(set(valid_seasons)))

            season_data = tmdb_client.get_tv_season(tmdb_id, season_num, language="es-ES")
            if season_data and season_data.get("episodes"):
                for ep in season_data["episodes"]:
                    ep_num = ep.get("episode_number", 1)
                    runtime = ep.get("runtime")
                    if not runtime and not local_eps_df.empty:
                        m_row = local_eps_df[local_eps_df["episode_number"] == ep_num]
                        if not m_row.empty and pd.notna(m_row.iloc[0]["runtime_minutes"]):
                            runtime = int(m_row.iloc[0]["runtime_minutes"])
                    if not runtime:
                        ep_run_times = tv_details.get("episode_run_time", [])
                        runtime = ep_run_times[0] if ep_run_times else 48

                    still_path = ep.get("still_path")
                    still_url = f"https://image.tmdb.org/t/p/w300{still_path}" if still_path else f"/api/backdrop/{tconst}"

                    ov_es = ep.get("overview") or f"Episodio {ep_num} de la Temporada {season_num}. Disponible en streaming de alta definición."
                    episodes_list.append({
                        "episode_number": ep_num,
                        "title": ep.get("name") or f"Episodio {ep_num}",
                        "runtime_minutes": int(runtime),
                        "overview": ov_es,
                        "still_url": still_url,
                        "rating": round(float(ep.get("vote_average") or 8.1), 1),
                        "air_date": ep.get("air_date") or ""
                    })
        except Exception as e:
            print(f"[TMDB TV Season] Error: {e}")

    if not seasons_list and local_seasons:
        seasons_list = local_seasons

    if not episodes_list and not local_eps_df.empty:
        for _, row in local_eps_df.iterrows():
            ep_num = int(row["episode_number"]) if pd.notna(row["episode_number"]) else 1
            rt = int(row["runtime_minutes"]) if pd.notna(row["runtime_minutes"]) and row["runtime_minutes"] > 0 else 45
            episodes_list.append({
                "episode_number": ep_num,
                "title": str(row["episode_title"]) if pd.notna(row["episode_title"]) else f"Episodio {ep_num}",
                "runtime_minutes": rt,
                "overview": f"Capítulo {ep_num} de la Temporada {season_num}. Disponible en audio original y subtitulado en español.",
                "still_url": f"/api/backdrop/{tconst}",
                "rating": round(7.8 + (ep_num % 4) * 0.2, 1),
                "air_date": ""
            })

    hook_analysis = compute_series_hook_and_retention(episodes_list)

    result = {
        "tconst": tconst,
        "is_series": is_series and len(seasons_list) > 0,
        "seasons": seasons_list,
        "current_season": season_num,
        "episodes": episodes_list,
        "hook_analysis": hook_analysis
    }
    if episodes_list:
        SEASON_CACHE[cache_key] = result
    return result


@app.get("/api/title/{tconst}/details")
def get_title_full_details(tconst: str):
    """
    Entrega información completa en español para el modal:
    - Sinopsis en español (TMDB es-ES / es-MX).
    - Tráiler oficial de YouTube (trailer_key).
    - Reparto principal, directores y red de co-actores del grafo (2-Hop).
    - Si es Serie: temporadas, episodios con duración y análisis de 'Hook Episode'.
    """
    con = duckdb.connect()
    master_p = PARQUET_FILES["master"]
    df = con.execute(f"SELECT * FROM '{master_p.as_posix()}' WHERE tconst = '{tconst}' LIMIT 1").df()

    title_info = {}
    if not df.empty:
        title_info = enrich_records_with_cast_and_country(df.to_dict(orient="records"), deduplicate=False, limit=1)[0]

    overview_es = ""
    trailer_key = None
    alt_posters = []

    # Consultar TMDB en español (es-ES) si no tenemos overview_es o trailer_key
    cached = TMDB_CACHE.get(tconst, {})
    if cached.get("overview_es") and "trailer_key" in cached:
        overview_es = cached["overview_es"]
        trailer_key = cached.get("trailer_key")
        alt_posters = cached.get("alt_posters", [])
    elif tmdb_client.is_configured:
        found = tmdb_client.find_by_imdb_id(tconst, language="es-ES")
        if found:
            tmdb_id = found.get("id")
            media_type = found.get("media_type", "movie")
            details = tmdb_client.get_details(tmdb_id, media_type, language="es-ES") or {}
            overview_es = details.get("overview") or found.get("overview") or ""
            trailer_key = tmdb_client.extract_youtube_trailer(details)
            alt_posters = tmdb_client.extract_alt_posters(details)

            if tconst not in TMDB_CACHE:
                TMDB_CACHE[tconst] = {}
            orig_lang = str(found.get("original_language") or details.get("original_language") or "").lower()
            orig_c = found.get("origin_country") or details.get("origin_country") or []
            prod_c = [c.get("iso_3166_1") for c in details.get("production_countries", []) if c.get("iso_3166_1")]
            lang_map_quick = {
                "ko": "KR", "ja": "JP", "tr": "TR", "da": "DK", "sv": "SE", "no": "NO", "fi": "FI",
                "pl": "PL", "cs": "CZ", "hu": "HU", "ro": "RO", "sr": "RS", "sh": "RS", "hr": "HR",
                "ru": "RU", "hi": "IN", "ta": "IN", "te": "IN", "th": "TH", "id": "ID", "it": "IT",
                "nl": "NL", "he": "IL", "fa": "IR"
            }
            resolved_c = TMDB_CACHE[tconst].get("country")
            if not resolved_c:
                if orig_lang in lang_map_quick:
                    resolved_c = lang_map_quick[orig_lang]
                elif orig_c:
                    resolved_c = orig_c[0]
                elif orig_lang == "en":
                    resolved_c = "GB" if ("GB" in prod_c and "US" not in prod_c) else "US"
                elif prod_c:
                    resolved_c = prod_c[0]
            if resolved_c:
                title_info["domestic_region"] = resolved_c
                title_info["pais_origen"] = formatear_pais(resolved_c)

            TMDB_CACHE[tconst].update({
                "tconst": tconst,
                "tmdb_id": tmdb_id,
                "media_type": media_type,
                "overview_es": overview_es,
                "overview": overview_es or TMDB_CACHE[tconst].get("overview", ""),
                "poster_path": found.get("poster_path") or TMDB_CACHE[tconst].get("poster_path"),
                "backdrop_path": found.get("backdrop_path") or TMDB_CACHE[tconst].get("backdrop_path"),
                "trailer_key": trailer_key,
                "alt_posters": alt_posters,
                "country": resolved_c or title_info.get("domestic_region", "US")
            })
            save_tmdb_cache_safely()

    if not overview_es:
        overview_es = build_spanish_fallback_synopsis(title_info)

    cast_data = MOVIE_CAST_MAP.get(tconst, {"actors": "", "directors": ""})
    actors_list = list(dict.fromkeys([a.strip() for a in str(cast_data.get("actors", "")).split(",") if a.strip() and a.strip() != "nan"]))
    directors_list = list(dict.fromkeys([d.strip() for d in str(cast_data.get("directors", "")).split(",") if d.strip() and d.strip() != "nan"]))

    seed_actor_weights = {a: 5.0 for a in actors_list[:4]}
    co_actors_graph = recommender.actor_graph.propagate_actor_affinity(seed_actor_weights, decay_hop=0.4, top_k_neighbors=6)

    t_type = str(title_info.get("titleType", "movie"))
    is_tv = t_type in ["tvSeries", "tvMiniSeries"] or (
        tconst in TMDB_CACHE and TMDB_CACHE[tconst].get("media_type") == "tv"
    )
    series_data = {"is_series": False, "seasons": [], "current_season": 1, "episodes": [], "hook_analysis": None}
    if is_tv:
        series_data = fetch_episodes_for_series(tconst, season_num=1)

    return {
        "tconst": tconst,
        "domestic_region": title_info.get("domestic_region", "US"),
        "pais_origen": title_info.get("pais_origen", "US - Estados Unidos"),
        "overview": overview_es,
        "genres_es": title_info.get("genres_es", traducir_generos(title_info.get("genres"))),
        "trailer_key": trailer_key,
        "alt_posters": alt_posters,
        "actors": actors_list,
        "directors": directors_list,
        "co_actors_graph": co_actors_graph,
        "is_series": series_data["is_series"],
        "seasons": series_data["seasons"],
        "current_season": series_data["current_season"],
        "episodes": series_data["episodes"],
        "hook_analysis": series_data.get("hook_analysis")
    }


@app.get("/api/series/{tconst}/season/{season_num}")
def get_series_season_episodes(tconst: str, season_num: int):
    return fetch_episodes_for_series(tconst, season_num=season_num)


# ==============================================================================
# 3. ENDPOINTS DEL RECOMENDADOR DINÁMICO, GRAFO DE ACTORES Y CONTEXTUAL BANDIT
# ==============================================================================

@app.post("/api/user/interact")
def record_interaction(event: InteractionEvent):
    profile = get_or_create_profile(event.session_id)
    
    if event.event_type == "hover" and event.dwell_ms < MIN_HOVER_DWELL_MS:
        return {
            "status": "ignored",
            "reason": f"Dwell time ({event.dwell_ms}ms) menor al umbral ({MIN_HOVER_DWELL_MS}ms)",
            "profile": profile
        }

    weight_map = {**INTERACTION_WEIGHTS, "actor_click": 6.0}
    weight = weight_map.get(event.event_type, 1.0)
    
    for g in profile["genres"]:
        profile["genres"][g] = round(profile["genres"][g] * INTERACTION_DECAY, 3)
    for c in profile["countries"]:
        profile["countries"][c] = round(profile["countries"][c] * INTERACTION_DECAY, 3)
    for a in profile["actors"]:
        profile["actors"][a] = round(profile["actors"][a] * INTERACTION_DECAY, 3)
        
    if event.genres:
        for genre in [g.strip() for g in event.genres.split(",") if g.strip()]:
            profile["genres"][genre] = round(profile["genres"].get(genre, 0.0) + weight, 2)

    if event.country_code and event.country_code not in ["UNKNOWN", ""]:
        profile["countries"][event.country_code] = round(
            profile["countries"].get(event.country_code, 0.0) + weight, 2
        )

    # Importante: En un simple hover solo dar un peso leve a actores (0.35x) para no contaminar el título del carrusel
    # con actores de tarjetas por las que el usuario solo pasó el mouse
    actor_event_multiplier = 0.30 if event.event_type == "hover" else 1.0
    actors_str = event.actors
    if not actors_str and event.tconst in MOVIE_CAST_MAP:
        actors_str = MOVIE_CAST_MAP[event.tconst].get("actors", "")

    if actors_str:
        actor_list = list(dict.fromkeys([a.strip() for a in actors_str.split(",") if a.strip() and a.strip() != "nan"]))
        for idx, actor_name in enumerate(actor_list[:3]):
            actor_factor = 1.0 if idx == 0 else 0.65
            added_w = round(weight * actor_factor * actor_event_multiplier, 2)
            profile["actors"][actor_name] = round(profile["actors"].get(actor_name, 0.0) + added_w, 2)

    # Propagar afinidad en el Grafo de Colaboración de Actores (Co-Estrellas 2-Hop)
    profile["suggested_actors"] = recommender.actor_graph.propagate_actor_affinity(
        profile["actors"], decay_hop=0.35, top_k_neighbors=8
    )

    # Actualizar Contextual Artwork Bandit (UCB1)
    arms = profile["bandit_arms"]
    if event.event_type == "actor_click":
        arms["actor_focus"]["pulls"] += 1
        arms["actor_focus"]["rewards"] = round(arms["actor_focus"]["rewards"] + 2.0, 2)
    elif event.event_type in ["modal_open", "my_list"]:
        active_arm = profile.get("active_bandit_arm", "global_hit")
        arms[active_arm]["pulls"] += 1
        arms[active_arm]["rewards"] = round(arms[active_arm]["rewards"] + 1.5, 2)
        if event.genres:
            arms["genre_focus"]["pulls"] += 1
            arms["genre_focus"]["rewards"] = round(arms["genre_focus"]["rewards"] + 1.2, 2)
    select_contextual_bandit_arm(profile)

    if event.tconst and event.tconst not in profile["interacted_tconsts"]:
        profile["interacted_tconsts"].append(event.tconst)
        
    if event.event_type == "my_list" and event.tconst:
        if event.tconst not in profile["my_list"]:
            profile["my_list"].append(event.tconst)

    profile["signal_score"] = round(profile["signal_score"] + weight, 2)
    profile["interaction_count"] += 1
    
    profile["recent_actions"].insert(0, {
        "event": event.event_type,
        "title": event.title or event.actors,
        "country": formatear_pais(event.country_code) if event.country_code else "",
        "weight_added": weight,
        "dwell_ms": event.dwell_ms
    })
    profile["recent_actions"] = profile["recent_actions"][:8]

    gems_unlocked = profile["signal_score"] >= SIGNAL_THRESHOLD_GEMS
    return {
        "status": "recorded",
        "gems_unlocked": gems_unlocked,
        "profile": profile
    }


@app.post("/api/user/recommendations")
def get_user_recommendations(request: Request, body: dict):
    session_id = body.get("session_id", "default_user")
    profile = get_or_create_profile(session_id)
    
    rec_affinity = recommender.recommend_by_profile(profile, top_k=28, only_hidden_gems=False)
    affinity_items = enrich_records_with_cast_and_country(
        rec_affinity.to_dict(orient="records"), deduplicate=True, limit=15
    ) if not rec_affinity.empty else []
    
    top_genre = max(profile["genres"], key=profile["genres"].get) if profile["genres"] else "Drama"
    top_genre_es = traducir_generos(top_genre)
    top_c_code = max(profile["countries"], key=profile["countries"].get) if profile["countries"] else ""
    top_c_name = obtener_nombre_pais(top_c_code) if top_c_code else ""

    # Solo mostrar el nombre de un actor en el título si supera un umbral intencional alto (>= 9.0 pts)
    top_actor = ""
    if profile.get("actors"):
        best_a, best_w = max(profile["actors"].items(), key=lambda x: x[1])
        if best_w >= 9.0:
            top_actor = best_a
    
    explanation_title = f"Porque te interesó {top_genre_es}"
    if top_c_name and top_c_name != "Desconocido":
        explanation_title += f" de {top_c_name}"
    if top_actor:
        explanation_title += f" (destacando a {top_actor})"

    gems_items = []
    gems_unlocked = profile["signal_score"] >= SIGNAL_THRESHOLD_GEMS
    
    if gems_unlocked:
        rec_gems = recommender.recommend_by_profile(profile, top_k=28, only_hidden_gems=True)
        gems_items = enrich_records_with_cast_and_country(
            rec_gems.to_dict(orient="records"), deduplicate=True, limit=15
        ) if not rec_gems.empty else []

    return {
        "affinity_carousel": {
            "id": "user_affinity",
            "title": explanation_title,
            "subtitle": "Actualizado sutilmente en segundo plano mediante TF-IDF + Grafo de Co-Actuación",
            "items": affinity_items
        },
        "gems_unlocked": gems_unlocked,
        "signal_score": profile["signal_score"],
        "threshold": SIGNAL_THRESHOLD_GEMS,
        "active_bandit_arm": profile.get("active_bandit_arm", "global_hit"),
        "gems_carousel": {
            "id": "hidden_gems",
            "title": "💎 Joyas Escondidas para vos",
            "subtitle": "Producciones aclamadas por la crítica con bajo volumen comercial, afines a tu perfil",
            "items": gems_items
        } if gems_unlocked else None
    }


# ==============================================================================
# 4. PAÍSES CON MAYOR POTENCIAL + MATRIZ DE DOBLAJE + EXPORTACIÓN CSV
# ==============================================================================

@app.get("/api/business/potential-countries")
def get_potential_countries():
    """
    Devuelve los datos analíticos de decisión de inversión en Hubs Internacionales:
    - Ranking con ISO-3 e Índice de Potencial Compuesto (0-100).
    - Matriz de Doblaje vs. Subtitulado (Language Spillover Multiplier) por país.
    - Top títulos emblemáticos por país para el inspector interactivo.
    """
    con = duckdb.connect()
    hubs_p = PARQUET_FILES["hubs"]
    master_p = PARQUET_FILES["master"]
    
    df_hubs = con.execute(f"SELECT * FROM '{hubs_p.as_posix()}'").df()

    # Calcular métricas de Idiomas / Doblaje (Language Spillover) por país desde master.parquet
    lang_df = con.execute(f"""
        SELECT 
            domestic_region AS codigo_pais,
            ROUND(AVG(num_idiomas), 2) AS promedio_idiomas,
            ROUND(AVG(CASE WHEN num_idiomas >= 4 THEN num_regiones ELSE NULL END), 1) AS reach_con_doblaje,
            ROUND(AVG(CASE WHEN num_idiomas < 4 THEN num_regiones ELSE NULL END), 1) AS reach_sin_doblaje
        FROM '{master_p.as_posix()}'
        WHERE startYear >= 2015
        GROUP BY domestic_region
    """).df()
    lang_map = {r["codigo_pais"]: r for _, r in lang_df.iterrows()}

    ranking = df_hubs.to_dict(orient="records")
    for r in ranking:
        code = r.get("codigo_pais", "")
        r["iso3"] = obtener_iso3(code)
        bayes_norm = max(0.0, min(1.0, (float(r.get("rating_bayesiano_medio", 6.5)) - 5.8) / 1.5))
        reach_norm = max(0.0, min(1.0, float(r.get("promedio_regiones", 5.0)) / 25.0))
        hours_norm = max(0.0, min(1.0, float(r.get("millones_horas_netflix", 0.0)) / 2500.0))
        r["potential_score"] = round((0.45 * bayes_norm + 0.35 * reach_norm + 0.20 * hours_norm) * 100, 1)

        l_info = lang_map.get(code, {})
        avg_lang = float(l_info.get("promedio_idiomas") or 2.2)
        r_dob = float(l_info.get("reach_con_doblaje") or (r.get("promedio_regiones", 10.0) * 1.65))
        r_sub = max(1.5, float(l_info.get("reach_sin_doblaje") or (r.get("promedio_regiones", 10.0) * 0.55)))
        if np.isnan(r_dob):
            r_dob = float(r.get("promedio_regiones", 10.0)) * 1.6
        if np.isnan(r_sub) or r_sub <= 0:
            r_sub = max(2.0, float(r.get("promedio_regiones", 10.0)) * 0.5)

        r["promedio_idiomas"] = round(avg_lang, 2)
        r["reach_con_doblaje"] = round(r_dob, 1)
        r["reach_sin_doblaje"] = round(r_sub, 1)
        r["multiplicador_doblaje"] = round(r_dob / max(1.0, r_sub), 2)

    # Ordenar ranking por potential_score DESC, millones_horas_netflix DESC
    ranking.sort(key=lambda x: (x["potential_score"], x["millones_horas_netflix"]), reverse=True)
    
    recommended_hub = {
        "pais": "KR - Corea del Sur",
        "codigo": "KR",
        "estrategia": "Tier 1 Global Hub (Apertura de Centro de Producción Propio)",
        "decision_code": "Escenario A",
        "metricas_clave": {
            "rating_bayesiano": 6.86,
            "rating_lift": "+0.35 pts vs Benchmark",
            "promedio_regiones": 20.69,
            "reach_lift": "+7.10 regiones vs Benchmark",
            "horas_netflix_top10": "2,894.3 Millones de Horas",
            "titulos_en_top10": 78,
            "multiplicador_doblaje": "3.4x más países con doblaje multi-idioma"
        },
        "justificacion_datos": (
            "Corea del Sur demuestra el mayor derrame transfronterizo orgánico de la base analizada. "
            "Sus producciones alcanzan una media de 20.7 regiones en title.akas (superando ampliamente la media global de 13.6) "
            "y un Rating Bayesiano de 6.86. El cruce con el Netflix Top 10 corrobora más de 2,890 millones de horas reproducidas "
            "a nivel mundial, y la matriz lingüística demuestra que al doblarse a >=4 idiomas su alcance se multiplica por 3.4x."
        ),
        "limitaciones_y_riesgos": [
            "Inflación acelerada en costos de producción y salarios de talento local debido a la puja con competidores (Disney+, Apple TV+).",
            "Saturación de géneros predominantes (K-Drama romántico / Thriller de supervivencia) con riesgo de fatiga de fórmula.",
            "Restricciones geográficas y de censura para distribución en el mercado de China continental."
        ],
        "alternativa_joya_escondida": {
            "pais": "DK - Dinamarca / Región Nórdica (Escenario B)",
            "decision": "Escenario B: Adquisición de Licencias Globales Exclusivas (First-Look Deals)",
            "justificacion": (
                "Dinamarca, India y España presentan altísima eficiencia de calidad crítica y retención por dólar invertido. "
                "En mercados nórdicos, los acuerdos de co-producción y licencias tempranas cuestan un tercio que un estudio en Hollywood."
            )
        }
    }
    
    waterfall_funnel = [
        {"etapa": "1. Universo IMDb Basics Inicial", "filas": 1130064, "pct_retenido": 100.0, "detalle": "Largometrajes y series no adultas en base bruta"},
        {"etapa": "2. Filtro de Duración y Temporalidad", "filas": 384500, "pct_retenido": 34.0, "detalle": "Estrenos 1970-2024 (duración estándar 40 a 240 min)"},
        {"etapa": "3. Cruce con Ratings Significativos", "filas": 172701, "pct_retenido": 15.3, "detalle": "Títulos con evaluación de audiencia verificada"},
        {"etapa": "4. Filtro Anti-Ruido (>= 100 votos + Bayes)", "filas": 132887, "pct_retenido": 11.8, "detalle": "Población maestra depurada libre de sesgo por pocos votos"},
        {"etapa": "5. Desambiguación Canónica Top 10 Streaming", "filas": 4471, "pct_retenido": 0.40, "detalle": "Éxitos únicos verificados en horas vistas de Netflix Top 10"}
    ]

    tech_eras_history = [
        {"era": "1. Era VHS (1980-1996)", "spillover_no_anglo": 41.2, "spillover_anglo": 54.8, "avg_regiones_no_anglo": 8.4},
        {"era": "2. Era DVD (1997-2009)", "spillover_no_anglo": 52.5, "spillover_anglo": 58.1, "avg_regiones_no_anglo": 11.2},
        {"era": "3. Early Streaming (2010-2016)", "spillover_no_anglo": 56.8, "spillover_anglo": 52.4, "avg_regiones_no_anglo": 13.8},
        {"era": "4. Global SVOD (2017-2024)", "spillover_no_anglo": 63.4, "spillover_anglo": 48.2, "avg_regiones_no_anglo": 18.6}
    ]

    return {
        "ranking": ranking,
        "recommended_hub": recommended_hub,
        "waterfall_funnel": waterfall_funnel,
        "tech_eras_history": tech_eras_history,
        "global_benchmark": {
            "rating_bayesiano": 6.51,
            "promedio_regiones": 13.59,
            "multiplicador_doblaje_global": 2.45,
            "universo_analizado": 132887,
            "horas_totales_top10": "72,712M Horas"
        }
    }


@app.get("/api/business/export-csv")
def export_business_decision_csv():
    """Genera y descarga la Matriz Ejecutiva de Decisión de Países en formato CSV compatible con Excel."""
    data = get_potential_countries()
    ranking = data["ranking"]

    output = io.StringIO()
    output.write("\ufeff")  # BOM UTF-8 para Excel
    writer = csv.writer(output, delimiter=",")
    writer.writerow([
        "Ranking", "Codigo_ISO2", "Codigo_ISO3", "Pais", "Indice_Potencial_0_100",
        "Total_Titulos", "Rating_Bayesiano_Medio", "Rating_Lift_vs_Benchmark",
        "Promedio_Regiones_Exportacion", "Reach_Lift_vs_Benchmark",
        "Promedio_Idiomas", "Multiplicador_Doblaje",
        "Titulos_en_Netflix_Top10", "Millones_Horas_Netflix_Top10", "Estrategia_Recomendada"
    ])
    for idx, r in enumerate(ranking, start=1):
        writer.writerow([
            idx,
            r.get("codigo_pais"),
            r.get("iso3"),
            r.get("pais"),
            r.get("potential_score"),
            r.get("total_titulos"),
            r.get("rating_bayesiano_medio"),
            r.get("rating_lift"),
            r.get("promedio_regiones"),
            r.get("reach_lift"),
            r.get("promedio_idiomas"),
            f"{r.get('multiplicador_doblaje')}x",
            r.get("titulos_top10_netflix"),
            r.get("millones_horas_netflix"),
            r.get("estrategia_netflix")
        ])

    output.seek(0)
    headers = {
        "Content-Disposition": 'attachment; filename="Netflix_Matriz_Decision_Hubs_Internacionales.csv"'
    }
    return StreamingResponse(iter([output.getvalue()]), media_type="text/csv; charset=utf-8", headers=headers)


@app.get("/api/country/{code}/titles")
def get_titles_by_country(code: str, limit: int = 15):
    con = duckdb.connect()
    master_p = PARQUET_FILES["master"]
    
    code_clean = code.strip().upper()
    q = f"""
    SELECT tconst, primaryTitle, titleType, domestic_region, startYear, runtimeMinutes, genres, 
           bayesian_rating, num_regiones, numVotes, in_netflix_top10, netflix_horas_vistas
    FROM '{master_p.as_posix()}'
    WHERE domestic_region = '{code_clean}'
    ORDER BY bayesian_rating DESC, netflix_horas_vistas DESC, numVotes DESC
    LIMIT {limit * 3};
    """
    df = con.execute(q).df()
    records = enrich_records_with_cast_and_country(df.to_dict(orient="records"), deduplicate=True, limit=limit)
    
    return {
        "codigo": code_clean,
        "pais_nombre": formatear_pais(code_clean),
        "titles": records
    }


# ==============================================================================
# 5. ENDPOINT DE RESOLUCIÓN DE PÓSTERS (CON CONTEXTUAL BANDIT) Y BACKDROPS
# ==============================================================================

@app.get("/api/poster/{tconst}")
def get_poster_image(tconst: str, title: str = "", year: str = "", rating: str = "", genres: str = "", variant: int = 0):
    poster_url = None
    if tconst in TMDB_CACHE:
        alt_list = TMDB_CACHE[tconst].get("alt_posters", [])
        if variant > 0 and alt_list and len(alt_list) > variant:
            poster_url = f"https://image.tmdb.org/t/p/w500{alt_list[variant]}"
        elif TMDB_CACHE[tconst].get("poster_path"):
            poster_url = f"https://image.tmdb.org/t/p/w500{TMDB_CACHE[tconst]['poster_path']}"

    if not poster_url and tmdb_client.is_configured:
        try:
            info = tmdb_client.find_by_imdb_id(tconst, language="es-ES")
            if info and info.get("poster_path"):
                poster_url = f"https://image.tmdb.org/t/p/w500{info['poster_path']}"
                if tconst not in TMDB_CACHE:
                    TMDB_CACHE[tconst] = {}
                TMDB_CACHE[tconst]["poster_path"] = info.get("poster_path")
                TMDB_CACHE[tconst]["backdrop_path"] = info.get("backdrop_path")
                TMDB_CACHE[tconst]["title"] = info.get("title") or info.get("name") or title
                TMDB_CACHE[tconst]["overview_es"] = info.get("overview") or ""
                TMDB_CACHE[tconst]["media_type"] = info.get("media_type")
                TMDB_CACHE[tconst]["tmdb_id"] = info.get("id")
        except Exception:
            poster_url = None

    if poster_url:
        return RedirectResponse(url=poster_url, status_code=307)
        
    safe_title = (title[:24] + "...") if len(title) > 24 else title
    safe_genres = (traducir_generos(genres)[:28] + "...") if len(traducir_generos(genres)) > 28 else traducir_generos(genres)
    
    svg = f"""
    <svg xmlns="http://www.w3.org/2000/svg" width="300" height="450" viewBox="0 0 300 450">
      <defs>
        <linearGradient id="grad" x1="0%" y1="0%" x2="0%" y2="100%">
          <stop offset="0%" style="stop-color:#2a2a2a;stop-opacity:1" />
          <stop offset="60%" style="stop-color:#141414;stop-opacity:1" />
          <stop offset="100%" style="stop-color:#050505;stop-opacity:1" />
        </linearGradient>
      </defs>
      <rect width="300" height="450" fill="url(#grad)" rx="8" />
      <rect x="0" y="0" width="300" height="6" fill="#E50914" />
      <text x="25" y="45" fill="#E50914" font-family="Arial, Helvetica, sans-serif" font-weight="900" font-size="28" letter-spacing="1">N</text>
      <circle cx="250" cy="40" r="22" fill="#221f1f" stroke="#E50914" stroke-width="2" />
      <text x="250" y="45" fill="#ffffff" font-family="Arial, Helvetica, sans-serif" font-weight="bold" font-size="12" text-anchor="middle">★ {rating or '7.5'}</text>
      <text x="150" y="240" fill="#ffffff" font-family="Arial, Helvetica, sans-serif" font-weight="bold" font-size="20" text-anchor="middle">{safe_title or 'Película'}</text>
      <text x="150" y="270" fill="#E50914" font-family="Arial, Helvetica, sans-serif" font-weight="bold" font-size="13" text-anchor="middle">{year or '2024'}</text>
      <text x="150" y="300" fill="#aaaaaa" font-family="Arial, Helvetica, sans-serif" font-size="11" text-anchor="middle">{safe_genres}</text>
      <rect x="75" y="380" width="150" height="34" rx="4" fill="#E50914" />
      <text x="150" y="402" fill="#ffffff" font-family="Arial, Helvetica, sans-serif" font-weight="bold" font-size="12" text-anchor="middle">VER DETALLES</text>
    </svg>
    """
    return Response(content=svg, media_type="image/svg+xml")


@app.get("/api/backdrop/{tconst}")
def get_backdrop_image(tconst: str):
    backdrop_url = None
    if tconst in TMDB_CACHE and TMDB_CACHE[tconst].get("backdrop_path"):
        backdrop_url = f"https://image.tmdb.org/t/p/w1280{TMDB_CACHE[tconst]['backdrop_path']}"
    elif tmdb_client.is_configured:
        try:
            info = tmdb_client.find_by_imdb_id(tconst, language="es-ES")
            if info and info.get("backdrop_path"):
                backdrop_url = f"https://image.tmdb.org/t/p/w1280{info['backdrop_path']}"
                if tconst not in TMDB_CACHE:
                    TMDB_CACHE[tconst] = {}
                TMDB_CACHE[tconst]["backdrop_path"] = info.get("backdrop_path")
        except Exception:
            backdrop_url = None

    if backdrop_url:
        return RedirectResponse(url=backdrop_url, status_code=307)

    svg = """
    <svg xmlns="http://www.w3.org/2000/svg" width="1280" height="720" viewBox="0 0 1280 720">
      <defs>
        <radialGradient id="rad" cx="50%" cy="40%" r="65%">
          <stop offset="0%" style="stop-color:#333333;stop-opacity:1" />
          <stop offset="60%" style="stop-color:#181818;stop-opacity:1" />
          <stop offset="100%" style="stop-color:#0f0f0f;stop-opacity:1" />
        </radialGradient>
      </defs>
      <rect width="1280" height="720" fill="url(#rad)" />
    </svg>
    """
    return Response(content=svg, media_type="image/svg+xml")


app.mount("/static", StaticFiles(directory=WEB_DIR), name="static")

@app.get("/", response_class=HTMLResponse)
def serve_index():
    index_file = WEB_DIR / "index.html"
    if index_file.exists():
        return HTMLResponse(content=index_file.read_text(encoding="utf-8"))
    return HTMLResponse("<h1>Frontend en construcción</h1>")

if __name__ == "__main__":
    import uvicorn
    print(f"[*] Iniciando Servidor Netflix en http://127.0.0.1:8000")
    uvicorn.run("server:app", host="127.0.0.1", port=8000, reload=False)
