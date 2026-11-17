"""
ETAPA 5: Sistema Recomendador de Contenido Internacional (Cross-Border Affinity Engine).
Implementa un motor híbrido basado en contenido y embeddings con penalización doméstica,
validación de tracción en Netflix Top 10, nombres de países completos ('AR - Argentina')
y recomendador adaptativo que aprende en tiempo real del perfil del usuario.
"""

from pathlib import Path
import duckdb
import pandas as pd
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

import sys
sys.path.append(str(Path(__file__).resolve().parent.parent))
from config import PARQUET_FILES, REPORTS_DIR, SIGNAL_THRESHOLD_GEMS
from src.paises import formatear_pais, obtener_nombre_pais
from src.actor_graph import ActorAffinityGraph
from src.tmdb_client import traducir_generos

class CrossBorderRecommender:
    def __init__(self, master_parquet_path: Path | None = None, min_votes: int = 500):
        self.path = master_parquet_path or PARQUET_FILES["master"]
        self.min_votes = min_votes
        self.df = None
        self.tfidf_matrix = None
        self.vectorizer = None
        self.actor_graph = ActorAffinityGraph()
        self._load_and_index()
        
    def _load_and_index(self):
        print(f"\n[Etapa 5] Indexando motor recomendador desde {self.path.name}...")
        con = duckdb.connect()
        cast_p = PARQUET_FILES["cast"]
        has_cast = cast_p.exists()

        if has_cast:
            query = f"""
            SELECT 
                m.tconst,
                m.primaryTitle,
                m.titleType,
                m.startYear,
                m.runtimeMinutes,
                m.genres,
                m.domestic_region,
                m.num_regiones,
                m.bayesian_rating,
                m.numVotes,
                m.in_netflix_top10,
                m.netflix_horas_vistas,
                COALESCE(c.actors_str, '') AS actors_str,
                COALESCE(c.directors_str, '') AS directors_str
            FROM '{self.path.as_posix()}' m
            LEFT JOIN '{cast_p.as_posix()}' c ON m.tconst = c.tconst
            WHERE m.numVotes >= {self.min_votes}
              AND m.domestic_region NOT IN ('UNKNOWN', 'XWW', 'XWG')
            """
        else:
            query = f"""
            SELECT 
                tconst,
                primaryTitle,
                titleType,
                startYear,
                runtimeMinutes,
                genres,
                domestic_region,
                num_regiones,
                bayesian_rating,
                numVotes,
                in_netflix_top10,
                netflix_horas_vistas,
                '' AS actors_str,
                '' AS directors_str
            FROM '{self.path.as_posix()}'
            WHERE numVotes >= {self.min_votes}
              AND domestic_region NOT IN ('UNKNOWN', 'XWW', 'XWG')
            """
        self.df = con.execute(query).df().reset_index(drop=True)
        print(f"  -> {len(self.df):,} títulos indexados para recomendaciones cross-border.")
        
        # Sopa de metadatos para el espacio latente (incorporando actores y directores para el sistema de grafos)
        actors_tokens = self.df["actors_str"].str.replace(", ", " ").str.replace(" ", "_")
        self.df["metadata_soup"] = (
            (self.df["genres"].fillna("").str.replace(",", " ") + " ") * 2 +
            self.df["titleType"].astype(str) + " " +
            "orig_" + self.df["domestic_region"].astype(str) + " " +
            actors_tokens.fillna("")
        )
        
        self.vectorizer = TfidfVectorizer(stop_words="english", token_pattern=r"(?u)\b\w+\b")
        self.tfidf_matrix = self.vectorizer.fit_transform(self.df["metadata_soup"])
        print("  -> Matriz TF-IDF y Grafo de Actores construidos exitosamente.")

    def recommend(self, query_title: str, top_k: int = 5, force_cross_border: bool = True) -> pd.DataFrame:
        """
        Recomienda contrapartes internacionales para un título semilla individual.
        """
        q_clean = query_title.strip().lower()
        
        exact_matches = self.df[self.df["primaryTitle"].str.lower() == q_clean]
        if not exact_matches.empty:
            matches = exact_matches
        else:
            matches = self.df[self.df["primaryTitle"].str.contains(query_title, case=False, na=False, regex=False)]
        
        if matches.empty:
            print(f"[!] No se encontró ningún título coincidente con '{query_title}'.")
            return pd.DataFrame()
            
        seed = matches.sort_values(by="numVotes", ascending=False).iloc[0]
        seed_idx = seed.name
        source_country_code = seed["domestic_region"]
        source_country_full = formatear_pais(source_country_code)
        
        print(f"\n[Seed] Título: '{seed['primaryTitle']}' ({seed['startYear']}) | País: {source_country_full} | Géneros: {seed['genres']} | Bayes: {seed['bayesian_rating']}")

        sim_scores = cosine_similarity(self.tfidf_matrix[seed_idx], self.tfidf_matrix).flatten()
        
        if force_cross_border:
            same_country_mask = (self.df["domestic_region"] == source_country_code).values
            sim_scores[same_country_mask] *= 0.15

        sim_scores[seed_idx] = 0.0

        reach_factor = np.minimum(self.df["num_regiones"].values / 15.0, 1.0)
        netflix_boost = np.where(self.df["in_netflix_top10"] == 1, 0.05, 0.0)
        
        final_scores = (
            0.50 * sim_scores +
            0.35 * (self.df["bayesian_rating"].values / 10.0) +
            0.10 * reach_factor +
            netflix_boost
        )
        
        top_indices = np.argsort(final_scores)[::-1][:top_k]
        
        rec_df = self.df.iloc[top_indices][
            ["tconst", "primaryTitle", "titleType", "domestic_region", "startYear", "runtimeMinutes", "genres", "bayesian_rating", "num_regiones", "in_netflix_top10", "netflix_horas_vistas", "actors_str"]
        ].copy()
        
        rec_df["pais_origen"] = rec_df["domestic_region"].apply(formatear_pais)
        rec_df["match_score"] = np.round(final_scores[top_indices], 3)
        rec_df["top10_netflix"] = rec_df["in_netflix_top10"].map({1: "★ Hit Global", 0: "Catálogo"})
        rec_df["explanation"] = f"Similar a '{seed['primaryTitle']}' ({source_country_full})"
        
        return rec_df

    def recommend_by_profile(self, user_profile: dict, top_k: int = 10, only_hidden_gems: bool = False) -> pd.DataFrame:
        """
        Recomienda títulos aprendiendo en tiempo real del perfil dinámico del usuario y del Grafo de Actores.
        """
        genres_profile = user_profile.get("genres", {})
        countries_profile = user_profile.get("countries", {})
        actors_profile = user_profile.get("actors", {})
        interacted_tconsts = set(user_profile.get("interacted_tconsts", []))
        
        # Propagar afinidad en el Grafo de Colaboración de Actores (1-hop -> 2-hop co-estrellas)
        suggested_co_actors = self.actor_graph.propagate_actor_affinity(actors_profile, decay_hop=0.35, top_k_neighbors=8)
        
        # 1. Construir query ponderada de texto a partir del perfil (géneros, países y actores preferidos)
        query_tokens = []
        for g, w in sorted(genres_profile.items(), key=lambda x: x[1], reverse=True)[:5]:
            repeat = max(1, min(int(round(w)), 5))
            query_tokens.append((f"{g} ") * repeat)
            
        for c, w in sorted(countries_profile.items(), key=lambda x: x[1], reverse=True)[:3]:
            repeat = max(1, min(int(round(w)), 4))
            query_tokens.append((f"orig_{c} ") * repeat)

        for a, w in sorted(actors_profile.items(), key=lambda x: x[1], reverse=True)[:4]:
            repeat = max(1, min(int(round(w / 2.5)), 4))
            query_tokens.append((f"{a.replace(' ', '_')} ") * repeat)

        for co_a, info in list(suggested_co_actors.items())[:3]:
            query_tokens.append(f"{co_a.replace(' ', '_')} ")
            
        profile_query = " ".join(query_tokens).strip()
        if not profile_query:
            profile_query = "Drama Crime Thriller"

        # 2. Transformar query del perfil en vector TF-IDF
        user_vec = self.vectorizer.transform([profile_query])
        sim_scores = cosine_similarity(user_vec, self.tfidf_matrix).flatten()

        # 3. Boost de Grafo Bipartito para Actores Directos (1-hop) y Co-Estrellas Propagadas (2-hop)
        actor_boost = np.zeros(len(self.df))
        if actors_profile:
            top_actors = sorted(actors_profile.items(), key=lambda x: x[1], reverse=True)[:6]
            for actor_name, weight in top_actors:
                mask = self.df["actors_str"].str.contains(actor_name, case=False, na=False, regex=False).values
                actor_boost[mask] += min(0.40, weight * 0.06)

        if suggested_co_actors:
            for co_actor_name, info in suggested_co_actors.items():
                mask = self.df["actors_str"].str.contains(co_actor_name, case=False, na=False, regex=False).values
                actor_boost[mask] += min(0.22, info["score"] * 0.04)

        # 4. Excluir títulos ya interactuados para favorecer nuevo descubrimiento
        if interacted_tconsts:
            interacted_mask = self.df["tconst"].isin(interacted_tconsts).values
            sim_scores[interacted_mask] = 0.0
            actor_boost[interacted_mask] = 0.0

        # 5. Máscara para "Joyas Escondidas"
        if only_hidden_gems:
            gem_mask = (self.df["bayesian_rating"] >= 6.8) & (self.df["numVotes"] <= 80_000)
            final_scores = (
                0.35 * sim_scores +
                0.40 * (self.df["bayesian_rating"].values / 10.0) +
                0.15 * actor_boost +
                0.10 * np.where(gem_mask, 0.20, 0.0)
            )
            final_scores[~gem_mask] *= 0.1
        else:
            reach_factor = np.minimum(self.df["num_regiones"].values / 15.0, 1.0)
            netflix_boost = np.where(self.df["in_netflix_top10"] == 1, 0.05, 0.0)
            final_scores = (
                0.42 * sim_scores +
                0.30 * (self.df["bayesian_rating"].values / 10.0) +
                0.18 * actor_boost +
                0.05 * reach_factor +
                netflix_boost
            )

        top_indices = np.argsort(final_scores)[::-1][:top_k]
        
        rec_df = self.df.iloc[top_indices][
            ["tconst", "primaryTitle", "titleType", "domestic_region", "startYear", "runtimeMinutes", "genres", "bayesian_rating", "num_regiones", "in_netflix_top10", "netflix_horas_vistas", "actors_str"]
        ].copy()
        
        rec_df["pais_origen"] = rec_df["domestic_region"].apply(formatear_pais)
        rec_df["match_score"] = np.round(final_scores[top_indices], 3)
        rec_df["top10_netflix"] = rec_df["in_netflix_top10"].map({1: "★ Hit Global", 0: "Catálogo"})

        # Construir explicación humana breve basada en los top intereses del usuario (Actores Directos, Grafo 2-hop, Género o País)
        top_genre = max(genres_profile, key=genres_profile.get) if genres_profile else "Drama"
        top_genre_es = traducir_generos(top_genre)
        top_country_code = max(countries_profile, key=countries_profile.get) if countries_profile else ""
        top_country_name = obtener_nombre_pais(top_country_code) if top_country_code else ""

        explanations = []
        for _, row in rec_df.iterrows():
            cast = row.get("actors_str", "") or ""
            matched_direct_actor = None
            matched_graph_actor = None
            via_fav_actor = None

            if actors_profile:
                for act, w_act in sorted(actors_profile.items(), key=lambda x: x[1], reverse=True):
                    if w_act >= 6.0 and act.lower() in cast.lower():
                        matched_direct_actor = act
                        break

            if not matched_direct_actor and suggested_co_actors:
                for co_act, info in suggested_co_actors.items():
                    if info.get("score", 0) >= 2.5 and co_act.lower() in cast.lower():
                        matched_graph_actor = co_act
                        via_fav_actor = info["via_actor"]
                        break
            
            if matched_direct_actor:
                explanations.append(f"🎭 Porque te gusta {matched_direct_actor}")
            elif matched_graph_actor:
                explanations.append(f"🕸️ Red de {via_fav_actor}: actúa {matched_graph_actor}")
            elif only_hidden_gems:
                if top_country_name and top_country_name != "Desconocido":
                    explanations.append(f"💎 Joya oculta afín a {top_country_name}")
                else:
                    explanations.append(f"💎 Joya escondida crítica en {top_genre_es}")
            else:
                if top_country_name and top_country_name != "Desconocido":
                    explanations.append(f"Porque exploraste {top_genre_es} de {top_country_name}")
                else:
                    explanations.append(f"Basado en tu preferencia por {top_genre_es}")
        
        rec_df["explanation"] = explanations
        return rec_df

def run_stage5():
    recommender = CrossBorderRecommender()
    test_queries = ["Dark", "Parasite", "Money Heist"]
    
    print("\n" + "="*80)
    print("DEMOSTRACIÓN DEL RECOMENDADOR CROSS-BORDER (ENRIQUECIDO CON NETFLIX TOP 10):")
    print("="*80)
    
    for q in test_queries:
        recs = recommender.recommend(q, top_k=5, force_cross_border=True)
        if not recs.empty:
            print(recs.to_string(index=False))
            print("-" * 80)
            
    # Prueba del recomendador por perfil de usuario simulado
    print("\nPROBANDO RECOMENDADOR POR PERFIL DE USUARIO APRENDIDO:")
    simulated_profile = {
        "genres": {"Crime": 12.0, "Drama": 8.0, "Mystery": 6.0},
        "countries": {"KR": 9.0, "ES": 4.0},
        "interacted_tconsts": ["tt5753856"], # Dark ya interactuada
        "signal_score": 25.0
    }
    recs_profile = recommender.recommend_by_profile(simulated_profile, top_k=4, only_hidden_gems=False)
    print("Recomendaciones de Afinidad:")
    print(recs_profile[["primaryTitle", "pais_origen", "bayesian_rating", "explanation"]].to_string(index=False))
    
    recs_gems = recommender.recommend_by_profile(simulated_profile, top_k=4, only_hidden_gems=True)
    print("\nJoyas Escondidas para vos (Activadas por superar umbral):")
    print(recs_gems[["primaryTitle", "pais_origen", "bayesian_rating", "explanation"]].to_string(index=False))
    return recommender

if __name__ == "__main__":
    run_stage5()
