"""
Módulo de Sistema de Grafos de Actores y Directores (Actor Collaboration & Affinity Graph).
Construye un grafo bipartito proyectado Actor-Título-Actor sobre movie_cast.parquet y
catalogo_internacional_master.parquet para:
1. Propagar afinidad desde los actores que le gustan al usuario hacia actores co-estrellas (1-hop y 2-hop).
2. Recomendar películas basadas en proximidad en el grafo de talento.
3. Explicar recomendaciones por red de colaboración ("Porque te gusta [Actor A], quien colaboró con [Actor B]").
"""

from collections import defaultdict
from pathlib import Path
import duckdb
import pandas as pd
import numpy as np

import sys
sys.path.append(str(Path(__file__).resolve().parent.parent))
from config import PARQUET_FILES


class ActorAffinityGraph:
    def __init__(self):
        # actor_name -> dict of {co_actor_name: edge_weight}
        self.co_actor_adj = defaultdict(lambda: defaultdict(float))
        # actor_name -> list of tconsts
        self.actor_to_titles = defaultdict(list)
        # tconst -> {"actors": [str], "directors": [str]}
        self.title_to_cast = {}
        # (actor_a, actor_b) -> shared representative title name
        self.shared_title_Bridge = {}
        self._build_graph()

    def _build_graph(self):
        cast_p = PARQUET_FILES.get("cast")
        master_p = PARQUET_FILES.get("master")
        if not cast_p or not cast_p.exists() or not master_p or not master_p.exists():
            print("[ActorGraph] Advertencia: No se encontró movie_cast.parquet.")
            return

        print("[ActorGraph] Construyendo Grafo de Colaboración de Actores y Directores...")
        con = duckdb.connect()
        query = f"""
        SELECT 
            c.tconst,
            m.primaryTitle,
            m.bayesian_rating,
            m.numVotes,
            c.actors_str,
            c.directors_str
        FROM '{cast_p.as_posix()}' c
        INNER JOIN '{master_p.as_posix()}' m ON c.tconst = m.tconst
        WHERE m.numVotes >= 1000
        """
        df = con.execute(query).df()

        edge_count = 0
        for _, row in df.iterrows():
            tconst = row["tconst"]
            title_name = row["primaryTitle"]
            rating_weight = float(row["bayesian_rating"] or 6.5) / 10.0

            actors_raw = str(row["actors_str"]) if pd.notna(row["actors_str"]) else ""
            directors_raw = str(row["directors_str"]) if pd.notna(row["directors_str"]) else ""

            actors = list(dict.fromkeys([a.strip() for a in actors_raw.split(",") if a.strip() and a.strip() != "nan"]))
            directors = list(dict.fromkeys([d.strip() for d in directors_raw.split(",") if d.strip() and d.strip() != "nan"]))

            self.title_to_cast[tconst] = {
                "actors": actors,
                "directors": directors
            }

            for act in actors:
                self.actor_to_titles[act].append(tconst)

            # Crear aristas entre co-estrellas del mismo título (proyección del grafo bipartito)
            n_act = len(actors)
            for i in range(n_act):
                u = actors[i]
                for j in range(i + 1, n_act):
                    v = actors[j]
                    self.co_actor_adj[u][v] += rating_weight
                    self.co_actor_adj[v][u] += rating_weight
                    self.shared_title_Bridge[(u, v)] = title_name
                    self.shared_title_Bridge[(v, u)] = title_name
                    edge_count += 1

        print(f"  -> Grafo inicializado: {len(self.actor_to_titles):,} actores únicos y {edge_count:,} conexiones de co-actuación.")

    def get_cast_for_title(self, tconst: str) -> dict:
        return self.title_to_cast.get(tconst, {"actors": [], "directors": []})

    def propagate_actor_affinity(self, direct_actors: dict, decay_hop: float = 0.35, top_k_neighbors: int = 8) -> dict:
        """
        Dado un diccionario de actores que le gustan al usuario {actor: peso},
        propaga el interés por las aristas del grafo hacia co-estrellas que podrían gustarle (1-hop / 2-hop).
        Retorna:
          {
            "suggested_actor": {
                "score": float,
                "via_actor": str,
                "shared_title": str
            }
          }
        """
        if not direct_actors:
            return {}

        suggestions = {}
        # Ordenar actores favoritos del usuario
        sorted_favs = sorted(direct_actors.items(), key=lambda x: x[1], reverse=True)[:8]

        for fav_actor, user_weight in sorted_favs:
            neighbors = self.co_actor_adj.get(fav_actor, {})
            if not neighbors:
                continue

            # Ordenar vecinos por peso de colaboración en el grafo
            for co_actor, collab_weight in sorted(neighbors.items(), key=lambda x: x[1], reverse=True)[:5]:
                if co_actor in direct_actors and direct_actors[co_actor] >= user_weight * 0.8:
                    # Si ya es uno de los principales actores directos, priorizar descubrir nuevos o mantener secundarios
                    continue

                propagated_score = round(user_weight * decay_hop * min(1.8, collab_weight), 2)
                if propagated_score <= 0.1:
                    continue

                shared_movie = self.shared_title_Bridge.get((fav_actor, co_actor), "producciones previas")
                if co_actor not in suggestions or propagated_score > suggestions[co_actor]["score"]:
                    suggestions[co_actor] = {
                        "score": propagated_score,
                        "via_actor": fav_actor,
                        "shared_title": shared_movie
                    }

        # Devolver los top_k_neighbors con mayor puntaje propagado
        sorted_sugg = dict(
            sorted(suggestions.items(), key=lambda x: x[1]["score"], reverse=True)[:top_k_neighbors]
        )
        return sorted_sugg
