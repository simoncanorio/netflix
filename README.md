# 🎬 Netflix Global Streaming, Graph AI & Executive Decision Analytics

**Proyecto Estratégico de Ciencia de Datos y Big Data — Taller 2 (Universidad Austral)**

Plataforma web interactiva estilo Netflix y pipeline de Big Data diseñado para responder con datos reales a dos preguntas clave:
1. **Negocio:** *¿Dónde debe Netflix abrir su próximo centro de producción propio (Escenario A) y dónde conviene comprar licencias de "Joyas Escondidas" a bajo costo (Escenario B)?*
2. **Producto & IA:** *¿Cómo recomendar cine y series internacionales aprendiendo en tiempo real de los gustos del usuario mediante texto (TF-IDF) y un Grafo de Colaboración de Actores?*

👉 **[Leer la Guía Completa Explicada de Forma Sencilla (`DOCUMENTACION_SISTEMA_NETFLIX.md`)](DOCUMENTACION_SISTEMA_NETFLIX.md)**

---

## 🚀 Cómo Ejecutarlo (1 Solo Comando)

El repositorio ya incluye las tablas limpias y comprimidas en **Parquet Snappy** (`output/parquet/`) y la caché de **TMDB en español** (`data/tmdb_titles_cache.json`), lista para usar tras clonar:

```bash
pip install -r requirements.txt
python run_app.py
```

Abrí en tu navegador: **`http://127.0.0.1:8000`**

---

## 🧠 ¿Cómo funciona todo en resumen simple?

1. **Compresión e Ingeniería Big Data (`src/stage1` y `stage2`):**
   * Procesa los datasets crudos de IMDb (+40 millones de filas en `title.akas`) usando **DuckDB**, reduciendo tipos de datos (*downcasting*) y exportando a **Parquet** (-87% de peso en disco, 0% de filas duplicadas).
   * Calcula una **"Nota Justa" (Promedio Bayesiano)** para evitar que películas con pocos votos engañen al ranking, limpia homónimos y cruza con los **72.712 millones de horas vistas** del *Netflix Top 10 Oficial*.
2. **Catálogo Tipo Netflix con Aprendizaje Sutil (`web/` + `server.py`):**
   * **Sinopsis, géneros y episodios en español** + reproductor de **Tráiler Oficial de YouTube** integrado en el modal.
   * **Aprende en vivo:** Registra cuánto tiempo mirás una tarjeta ($\ge 800\text{ ms}$), tus clics y lo que guardás en **Mi Lista**, actualizando las recomendaciones de forma suave en segundo plano y generando nuevas filas con **Scroll Infinito**.
   * **Grafo de Actores (1-Hop y 2-Hop):** Conecta a **66.030 actores** según las películas en las que trabajaron juntos para sugerirte elencos afines. Podés ver la red dibujada en vivo presionando **`Ctrl + D`** (`⚙ Grafo & IA`).
   * **Series Completas:** Incluye selector de temporadas, duración de cada capítulo e identificación automática del **🔥 Episodio Gancho (*Hook Episode*)**.
   * **Buscador Unificado:** Escribí una película, serie, género, actor o **país** (ej. *"Argentina"*, *"Corea"*, *"España"*) para ver exclusivamente sus actores destacados, sus producciones y títulos similares.
3. **Tablero Ejecutivo `Países con Mayor Potencial`:**
   * **Mapa Mundial Interactivo (Plotly)**, **Matriz de Cuadrantes**, **Efecto del Doblaje Multi-Idioma**, **Evolución Histórica (VHS a Streaming)**, **Simulador de Presupuesto (CAPEX / ROI)**, **Comparador Mano a Mano entre 2 países** y descarga a **Excel (CSV) / PDF**.

---

## 📂 Mapa Rápido de Carpetas

* `run_app.py` — Arranca el servidor y abre el navegador automáticamente.
* `server.py` — Servidor FastAPI que responde las búsquedas, recomendaciones y métricas.
* `main.py` — Ejecuta las 5 etapas del procesamiento de datos por consola.
* `src/` — Módulos de datos (`stage1` a `stage5`, `actor_graph.py`, `tmdb_client.py`, `paises.py`, `generar_graficos.py`).
* `web/` — Interfaz visual estilo Netflix (`index.html`, `css/netflix.css`, `js/app.js`).
* `output/` — Tablas optimizadas `.parquet`, reportes `.md` y gráficos `.png`.
* `DOCUMENTACION_SISTEMA_NETFLIX.md` — Explicación paso a paso en lenguaje claro de todo el sistema.
