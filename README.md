# 🎬 Netflix Global Streaming, Graph AI & Executive Decision Analytics (v5.0)

**Proyecto Estratégico de Ciencia de Datos, Econometría y Sistemas de Recomendación — Taller 2 (Universidad Austral)**

Plataforma interactiva estilo Netflix y pipeline analítico de Big Data diseñado para resolver con evidencia cuantitativa dos desafíos reales:
1. **Estrategia de Inversión Internacional (CAPEX):** *¿Dónde debe Netflix abrir su próximo centro de producción propio (Escenario A) y dónde conviene adquirir licencias exclusivas de "Joyas Escondidas" (Escenario B), auditando presupuestos reales en USD y corrigiendo el sesgo geográfico de votantes?*
2. **IA & Producto en Tiempo Real:** *¿Cómo recomendar contenido internacional combinando comprensión semántica de sinopsis (NLP bilingüe), preferencias de país/género y un Grafo de Colaboración de 66.030 Actores, validado con métricas offline (`Recall@10 = 52,22%`)?*

👉 **[Leer la Guía Completa Explicada de Forma Sencilla (`DOCUMENTACION_SISTEMA_NETFLIX.md`)](DOCUMENTACION_SISTEMA_NETFLIX.md)**

---

## 🚀 Ejecución Rápida (1 Solo Comando)

El repositorio incluye las bases optimizadas en **Parquet Snappy** (`output/parquet/`), la auditoría financiera/sesgo y la caché enriquecida en español (`data/tmdb_titles_cache.json`), lista para correr inmediatamente:

```bash
pip install -r requirements.txt
python run_app.py
```

*(Opcional: si querés descargar pósters nuevos en vivo desde TMDB, copiá `.env.example` a `.env` y colocá tu `TMDB_API_KEY`).*

Abrí en tu navegador: **`http://127.0.0.1:8000`**

---

## 🏆 Principales Diferenciales Técnicos y de Negocio

1. **Ingeniería Big Data sin Explosión de Memoria (`src/stage1` & `stage2`):**
   * Procesa los datasets completos de IMDb (+40M de filas en `title.akas`) con **DuckDB** y *downcasting* hacia **Parquet** (**-87,4% de peso**, **0% de duplicación 1:N**).
   * Aplica **Promedio Bayesiano ($WR$)** contra el ruido de pocos votos, desambigua **2.805 títulos homónimos** (ej. *You*) y cruza con **72.712 millones de horas vistas** del *Netflix Top 10 Oficial*.
2. **Recomendador Híbrido v5 con NLP de Sinopsis + Grafo de Actores (`src/stage5_recommender.py`):**
   * Vectoriza **35.000 features semánticas (unigramas y bigramas TF-IDF sublineales)** sobre sinopsis en español e inglés junto con géneros, países y propagación `1-Hop -> 2-Hop` sobre **66.030 actores y 246.350 aristas**.
   * **Validado científicamente (*Leave-One-Out* @ K=10 en `src/evaluate_recommender.py`):** alcanza **`Recall@10 = 52,22%`** y **`NDCG@10 = 0,2608`**, superando por **4,47x** al baseline de géneros (`11,67%`) y al de popularidad (`0,00%`).
3. **Auditoría de Presupuestos Reales (TMDB) y Corrección de Sesgo Geográfico (`src/audit_budgets_and_bias.py`):**
   * Audita costos reales en USD de **253 producciones internacionales** frente al benchmark de **USD 22,0M** de Hollywood en el Simulador de ROI.
   * Modela la subrepresentación geográfica de votantes de IMDb en mercados emergentes mediante el **Potencial Ajustado por Sesgo (`bias_adjusted_score`)**.
4. **Arquitectura Segura, Persistente y Lista para Producción:**
   * **Persistencia en SQLite WAL (`src/session_store.py`):** Tu perfil aprendido, el *Contextual Artwork Bandit (UCB1)* y **Mi Lista** sobreviven a reinicios del servidor.
   * **Seguridad:** Credenciales aisladas en `.env`, consultas SQL parametrizadas (`?`) en DuckDB/SQLite, suite de **tests automáticos (`tests/test_netflix_system.py`)** y contenedores listos (`Dockerfile` + `render.yaml`).

---

## 🧪 Ejecutar Pruebas Automáticas y Auditorías

```bash
# Correr la suite completa de tests (integridad 1:1, homónimos, SQLite, seguridad SQL, Grafo e IA)
python -m unittest discover -s tests -v

# Recalcular benchmark offline del recomendador (Recall@10 / NDCG@10)
python src/evaluate_recommender.py
```

---

## 📂 Estructura Principal del Proyecto

* `run_app.py` / `server.py` — Lanzador automático y backend FastAPI con SQLite + DuckDB parametrizado.
* `src/` — Pipeline analítico (`stage1` a `stage5`), `actor_graph.py`, `evaluate_recommender.py`, `audit_budgets_and_bias.py`, `session_store.py` y `tmdb_client.py`.
* `web/` — Frontend estilo Netflix (`index.html`, `css/netflix.css`, `js/app.js`) con Mapas Plotly, Simulador CAPEX/ROI real, Series con *Hook Episode* y Panel en Vivo (`Ctrl + D`).
* `tests/test_netflix_system.py` — Pruebas unitarias y de integración de punta a punta.
* `DOCUMENTACION_SISTEMA_NETFLIX.md` — Guía completa explicada paso a paso en lenguaje claro y sencillo.
