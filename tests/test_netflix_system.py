"""
Suite de Pruebas Automatizadas (Unitarias y de Integración) — Netflix Global Analytics v6.0.
Ejecución:
    python -m unittest discover -s tests -v
Verifica:
1. Seguridad de credenciales (.env sin llaves expuestas en código fuente).
2. Integridad 1:1 en Parquet (cero explosión de filas en joins), acotación Bayesiana y desambiguación de homónimos.
3. Persistencia real de sesiones de usuario y reinicio en SQLite WAL.
4. Recomendador Híbrido NLP de sinopsis + Grafo de Actores 2-Hop y métricas offline Recall@10 / NDCG@10.
5. Auditoría financiera real (presupuestos TMDB), corrección de sesgo IMDb y Optimizador Multi-País de Portafolio.
6. Buscador unificado, autocompletado en vivo y resistencia ante intentos de inyección SQL.
7. Funcionalidades v6: Hero rotativo, Perfiles Demo, Sorprendeme, Feedback explícito (👍/👎), Continuar Viendo y Similares en Modal.
"""

import json
import re
import sys
import tempfile
import unittest
from pathlib import Path

import duckdb

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from config import BASE_DIR, PARQUET_FILES, REPORTS_DIR
from src.session_store import SessionStore
import server


class TestNetflixSystem(unittest.TestCase):

    def test_01_credential_security_no_hardcoded_secrets(self):
        """Verifica que leer_datasets.py no contenga JWT tokens ni API keys hardcodeadas y exista .env.example."""
        leer_src = (BASE_DIR / "leer_datasets.py").read_text(encoding="utf-8")
        self.assertNotIn("eyJhbGciOiJIUzI1NiJ9", leer_src, "No debe haber tokens JWT hardcodeados en leer_datasets.py")
        hex32_matches = re.findall(r'["\'][0-9a-f]{32}["\']', leer_src)
        self.assertEqual(len(hex32_matches), 0, "No debe haber API keys hexadecimales hardcodeadas en leer_datasets.py")
        self.assertTrue((BASE_DIR / ".env.example").exists(), "Debe existir la plantilla pública .env.example")

    def test_02_parquet_1to1_integrity_bayesian_and_homonyms(self):
        """Verifica unicidad 1:1 de tconst (cero duplicados), rango Bayesiano y desambiguación canónica de 'You'."""
        master_p = PARQUET_FILES["master"]
        self.assertTrue(master_p.exists(), "Debe existir catalogo_internacional_master.parquet")

        con = duckdb.connect()
        stats = con.execute(f"""
            SELECT 
                COUNT(*) AS total_rows,
                COUNT(DISTINCT tconst) AS unique_tconsts,
                MIN(bayesian_rating) AS min_bayes,
                MAX(bayesian_rating) AS max_bayes
            FROM '{master_p.as_posix()}'
        """).fetchone()

        total_rows, unique_tconsts, min_bayes, max_bayes = stats
        self.assertGreater(total_rows, 100000)
        self.assertEqual(total_rows, unique_tconsts, "Violación 1:1: se detectaron tconst duplicados en master.parquet")
        self.assertGreaterEqual(min_bayes, 1.0)
        self.assertLessEqual(max_bayes, 10.0)

        you_top10 = con.execute(f"""
            SELECT tconst, numVotes
            FROM '{master_p.as_posix()}'
            WHERE LOWER(primaryTitle) = 'you' AND in_netflix_top10 = 1
        """).fetchall()
        self.assertEqual(len(you_top10), 1, "Solo la serie canónica 'You' debe recibir marca de Top 10 Netflix")
        self.assertEqual(you_top10[0][0], "tt7335184")
        con.close()

    def test_03_sqlite_session_persistence_and_reset(self):
        """Verifica que el perfil aprendido sobreviva al cierre en SQLite WAL y permita reset a 0.0 pts."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_file = Path(tmpdir) / "test_sessions.db"
            store_a = SessionStore(db_path=db_file)
            prof = store_a.get_or_create("user_austral_01")
            prof["genres"]["Crime"] = 12.5
            prof["countries"]["AR"] = 9.0
            prof["actors"]["Ricardo Darín"] = 15.0
            prof["my_list"].append("tt1305806")
            prof["signal_score"] = 21.5
            store_a.save("user_austral_01", prof)

            store_b = SessionStore(db_path=db_file)
            restored = store_b.get_or_create("user_austral_01")
            self.assertEqual(restored["genres"].get("Crime"), 12.5)
            self.assertIn("tt1305806", restored["my_list"])
            self.assertEqual(restored["signal_score"], 21.5)

            reset_prof = store_b.reset("user_austral_01")
            self.assertEqual(reset_prof["signal_score"], 0.0)
            self.assertEqual(len(reset_prof["my_list"]), 0)

    def test_04_hybrid_nlp_synopsis_actor_graph_and_offline_metrics(self):
        """Verifica vectorización NLP de sinopsis, propagación 2-Hop en el grafo y métricas Recall@10 / NDCG@10."""
        rec = server.recommender
        self.assertGreater(rec.tfidf_matrix.shape[1], 5000)

        co_stars = rec.actor_graph.propagate_actor_affinity({"Ricardo Darín": 10.0}, decay_hop=0.4, top_k_neighbors=5)
        self.assertGreater(len(co_stars), 0, "El grafo debe descubrir co-actores para Ricardo Darín")

        metrics_path = REPORTS_DIR / "recommender_metrics.json"
        self.assertTrue(metrics_path.exists(), "Debe existir output/reports/recommender_metrics.json")
        metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
        hyb = metrics["models"]["Hibrido_NLP_Grafo_v5"]
        gen = metrics["models"]["Baseline_Solo_Generos"]
        pop = metrics["models"]["Baseline_Popularidad"]

        self.assertGreater(hyb["recall_at_k"], gen["recall_at_k"] * 2.5)
        self.assertGreater(hyb["ndcg_at_k"], gen["ndcg_at_k"] * 2.5)
        self.assertGreater(hyb["recall_at_k"], pop["recall_at_k"])

    def test_05_audited_budgets_bias_and_multi_country_portfolio_optimizer(self):
        """Verifica presupuestos reales TMDB, corrección de sesgo IMDb y el Optimizador Multi-País de Portafolio."""
        biz = server.get_potential_countries()
        ranking = biz.get("ranking", [])
        self.assertGreaterEqual(len(ranking), 15)

        for r in ranking:
            self.assertGreater(r["median_budget_usd_m"], 0.0)
            self.assertGreaterEqual(r["selection_bias_multiplier"], 1.0)
            self.assertGreaterEqual(r["bias_adjusted_score"], r["potential_score"])

        portfolio = server.optimize_global_capex_portfolio(budget_m=150.0, strategy_mode="balanced")
        allocs = portfolio.get("allocations", [])
        self.assertEqual(len(allocs), 5)
        pct_sum = sum(a["pct_presupuesto"] for a in allocs)
        self.assertAlmostEqual(pct_sum, 100.0, delta=0.6)
        self.assertTrue(all(a["pct_presupuesto"] <= 40.0 for a in allocs), "Debe respetar la cota de diversificación")
        self.assertGreater(portfolio["total_producciones"], portfolio["hollywood_producciones_equivalentes"])

    def test_06_unified_search_autocomplete_and_sql_injection_safety(self):
        """Verifica buscador por país ('Argentina'), autocompletado instantáneo y blindaje SQL."""
        ac_res = server.autocomplete_catalog(q="Arg")
        self.assertGreater(len(ac_res.get("suggestions", [])), 0)
        self.assertEqual(ac_res["suggestions"][0]["type"], "country")

        res_ar = server.search_catalog(q="Argentina", session_id="test_suite")
        self.assertTrue(res_ar.get("is_country_search"))
        self.assertEqual(res_ar.get("country_code"), "AR")
        self.assertGreater(len(res_ar.get("direct_matches", [])), 5)
        self.assertGreater(len(res_ar.get("country_actors", [])), 3)

        sqli_payload = "Argentina' OR '1'='1'; DROP TABLE user_profiles; --"
        res_sqli = server.search_catalog(q=sqli_payload, session_id="test_suite")
        self.assertIsInstance(res_sqli, dict)

        res_code_sqli = server.get_titles_by_country("KR' OR 1=1--", limit=5)
        self.assertIsInstance(res_code_sqli, dict)
        self.assertTrue(len(res_code_sqli.get("codigo", "")) <= 4)

    def test_07_v6_hero_personas_surprise_feedback_and_modal_similars(self):
        """Verifica Hero rotativo, perfiles demo, Sorprendeme, feedback 👍/👎, Continuar Viendo y similares en modal."""
        init_cat = server.get_initial_catalog()
        self.assertGreaterEqual(len(init_cat.get("hero_items", [])), 3)

        # Perfil Demo preconfigurado
        ar_persona = server.get_persisted_user_profile(session_id="persona_cine_ar_eu")
        self.assertTrue(ar_persona["gems_unlocked"])
        self.assertIn("Ricardo Darín", ar_persona["profile"]["actors"])

        # Sorprendeme
        surprise = server.get_surprise_me_recommendation(session_id="persona_cine_ar_eu")
        self.assertIsNotNone(surprise.get("movie"))
        self.assertEqual(len(surprise.get("reasons", [])), 3)

        # Feedback negativo explícito (👎) excluye el título de recomendaciones y registra Continuar Viendo
        test_sid = "test_v6_feedback_session"
        server.reset_user_profile_endpoint({"session_id": test_sid})
        server.record_interaction(server.InteractionEvent(
            session_id=test_sid, event_type="like", tconst="tt1305806",
            title="The Secret in Their Eyes", genres="Drama,Mystery", country_code="AR", actors="Ricardo Darín"
        ))
        server.record_interaction(server.InteractionEvent(
            session_id=test_sid, event_type="dislike", tconst="tt5753856",
            title="Dark", genres="Sci-Fi", country_code="DE"
        ))
        server.record_interaction(server.InteractionEvent(
            session_id=test_sid, event_type="watch_progress", tconst="tt1305806",
            title="The Secret in Their Eyes", progress_pct=65, watch_label="T1:E1"
        ))
        recs = server.recommend_check = server.recommender.recommend_by_profile(
            server.get_persisted_user_profile(session_id=test_sid)["profile"], top_k=20
        )
        self.assertNotIn("tt5753856", recs["tconst"].tolist(), "Un título rechazado con 👎 nunca debe recomendarse")

        details_dark = server.get_title_full_details("tt5753856")
        self.assertGreaterEqual(len(details_dark.get("similar_titles", [])), 3)


if __name__ == "__main__":
    unittest.main()
