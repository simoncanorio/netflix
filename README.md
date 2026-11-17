# 🎬 Netflix Global Streaming, Graph AI & Executive Decision Analytics

**Proyecto Estratégico de Ciencia de Datos y Big Data — Taller 2 (Universidad Austral)**

Plataforma full-stack y pipeline analítico de Big Data que responde a la decisión estratégica de **dónde debe Netflix abrir su próximo centro de producción internacional exclusivo (Escenario A) vs. qué mercados subexplotados adquirir mediante licencias *First-Look* (Escenario B)**, integrando un **motor recomendador adaptativo con Grafo de Colaboración de Actores (1-Hop & 2-Hop)** y **Contextual Artwork Bandits (UCB1)**.

---

## 🚀 Inicio Rápido (1 Comando)

El repositorio ya incluye los archivos binarios procesados en formato **Parquet Snappy** (`output/parquet/`) y la caché enriquecida en español de **TMDB** (`data/tmdb_titles_cache.json`), por lo que la aplicación corre de forma inmediata tras clonar:

```bash
pip install -r requirements.txt
python run_app.py
```

Abrí en tu navegador: **`http://127.0.0.1:8000`**

---

## ✨ Características Principales de la Plataforma Web

1. **Interfaz Tipo Netflix (Dark UI & Español):**
   * **Hero Banner Cinemático** con sinopsis en español, porcentaje de afinidad (`98% para vos`) y reproducción de **Tráiler Oficial de YouTube embebido**.
   * **9 Carruseles Iniciales + Scroll Infinito Dinámico** que genera nuevas categorías personalizadas según tus gustos de género, país y elenco.
   * **Actualización Sutil en Segundo Plano:** El recomendador aprende del tiempo de permanencia en hover ($\ge 800\text{ ms}$), clics, apertura de modales y agregados a *Mi Lista* con decaimiento temporal ($\lambda = 0.95$), actualizando las recomendaciones sin saltos bruscos de pantalla.
2. **Buscador Exclusivo (Por Película, Serie, Actor, Género o País):**
   * Al buscar o elegir un país en el selector superior (`🌍 Filtrar por País`), oculta las categorías de inicio y muestra las coincidencias directas más una grilla de **Películas y Géneros Similares**.
3. **Sección Dedicada `💎 Joyas Escondidas Internacionales`:**
   * Filtra obras maestras fuera de Hollywood con alto **Promedio Bayesiano** ($\ge 7.4$) y volumen comercial moderado, con filtros por región (*Hispanoamérica & España*, *Europa & Nórdicos*, *Asia & Pacífico*, *Balcanes, Turquía & Oriente*).
4. **Sección `Mi Lista`:**
   * Colección personal persistente con su propio motor de recomendaciones derivado de los títulos guardados.
5. **Series con Temporadas, Episodios, Duraciones y "Hook Episode Analysis":**
   * Selector de temporadas, lista de capítulos en español con duración exacta en minutos e identificación automática del **🔥 Episodio Gancho (*Hook Episode*)** y **% de Fidelidad de Temporada**.
6. **Sistema Recomendador con Grafo de Colaboración de Actores (`src/actor_graph.py`):**
   * Grafo de **66,030 actores y 246,350 conexiones ponderadas** por el Rating Bayesiano de los títulos compartidos. Propaga afinidad de **1-Hop** (actores vistos) a **2-Hop** (co-estrellas sugeridas). Visible en vivo presionando **`Ctrl + D` (`⚙ Grafo & IA`)**.
7. **Tablero Ejecutivo `Países con Mayor Potencial`:**
   * **Mapa Mundial Coroplético Interactivo (Plotly)** + **Matriz de Cuadrantes (Reach Lift vs. Rating Lift)** + **Matriz de Doblaje vs. Subtitulado (Language Spillover)** + **Evolución Histórica por Eras Tecnológicas (VHS, DVD, Streaming)**.
   * **Inspector Ejecutivo de País en Vivo** y exportación directa de la matriz a **Excel CSV** y **Reporte PDF**.

---

## 📂 Estructura del Proyecto

* `run_app.py`: Lanzador automático del servidor web en `http://127.0.0.1:8000`.
* `server.py`: Backend REST API con FastAPI, DuckDB, Grafo de Actores y Contextual Bandit.
* `main.py`: Orquestador de las 5 etapas del pipeline de Big Data.
* `src/`:
  * `stage1_ingestion.py`: Ingesta con DuckDB, downcasting (`int16`, `int32`, `category`) y conversión a Parquet Snappy (-87% tamaño).
  * `stage2_eda_cleaning.py`: Pre-agregación 1:1 de `title.akas` sin multiplicación de filas, Promedio Bayesiano y auditoría *Waterfall Funnel*.
  * `stage3_history_trends.py`: Análisis histórico de internacionalización por eras tecnológicas (1980–2024).
  * `stage4_hubs_decision.py`: Matriz de decisión de Hubs Internacionales y Joyas Escondidas bajo las 6 reglas de negocio.
  * `stage5_recommender.py`: Motor híbrido TF-IDF + Grafo de Actores Cross-Border.
  * `actor_graph.py`: Construcción y propagación 1-Hop / 2-Hop del Grafo de Colaboración de Actores.
  * `tmdb_client.py`: Cliente de la API de TMDB (`es-ES`) para pósters, backdrops, sinopsis, temporadas y tráilers.
  * `paises.py`: Normalización ISO-2 / ISO-3 y buscador de países en español (`AR - Argentina`, `KR - Corea del Sur`, etc.).
* `web/`: Frontend SPA (`index.html`, `css/netflix.css`, `js/app.js`).
* `DOCUMENTACION_SISTEMA_NETFLIX.md`: Documentación técnica y matemática detallada.
