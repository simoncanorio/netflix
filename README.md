# 🎬 Netflix Global Streaming, Graph AI & Executive Decision Analytics (v6.0)

**Proyecto Estratégico de Ciencia de Datos, Econometría y Sistemas de Recomendación — Taller 2 (Universidad Austral)**

Plataforma interactiva estilo Netflix y pipeline analítico de Big Data diseñado para responder con evidencia cuantitativa dos desafíos reales:
1. **Estrategia de Inversión Internacional (CAPEX & Portafolio):** *¿Dónde debe Netflix abrir su próximo centro de producción propio (Escenario A) y cómo distribuir de forma óptima un presupuesto global junto con licencias de "Joyas Escondidas" (Escenario B), auditando presupuestos reales en USD y corrigiendo el sesgo geográfico de votantes?*
2. **IA & Producto en Tiempo Real:** *¿Cómo recomendar contenido internacional combinando NLP bilingüe de sinopsis, preferencias de país/género, feedback explícito (`👍/👎`) y un Grafo de Colaboración de 66.030 Actores (`Recall@10 = 52,22%`)?*

👉 **[Leer la Guía Completa Explicada de Forma Sencilla (`DOCUMENTACION_SISTEMA_NETFLIX.md`)](DOCUMENTACION_SISTEMA_NETFLIX.md)**

---

## 🚀 Ejecución Rápida (1 Solo Comando)

El repositorio incluye las bases optimizadas en **Parquet Snappy** (`output/parquet/`), la auditoría financiera/sesgo y la caché enriquecida en español (`data/tmdb_titles_cache.json`), lista para correr tras clonar:

```bash
pip install -r requirements.txt
python run_app.py
```

Abrí en tu navegador: **`http://127.0.0.1:8000`**

---

## ✨ Novedades Visuales, de Producto y Analíticas (v6.0)

* **UI Estilo Netflix Real:** Carrusel **Top 10 con números gigantes SVG (`1`–`10`)**, **Hero Banner rotativo** (5 éxitos globales con **vista previa de video**), carga con *Skeletons* animados, insignias `TOP 10` y bordes adaptativos.
* **Perfiles en Vivo (`¿Quién está viendo?`), `🎲 Sorprendeme` y `Continuar viendo`:** Cambiá en 1 clic entre *Tu Perfil*, *Fan K-Drama & Anime*, *Cine Argentino & Autor* e *Invitado (0 pts)* (con botón de reinicio en vivo), descubrí joyas explicadas paso a paso con **Sorprendeme** y retomá tráilers/episodios con barra roja de avance.
* **Feedback Positivo/Negativo (`👍 / 👎`), Autocompletado y Modal Extendido:** Ajustá o descartá recomendaciones al instante, usá autocompletado desplegable (**🌍 País / 🎭 Actor / 🎬 Título**) con filtros rápidos (*Películas / Series*), explorá **Más títulos similares** dentro del modal y visualizá la **Curva de Calificación por Episodio** en series.
* **Optimizador Matemático de Portafolio Multi-País & Tabla Ordenable:** Reparte presupuestos globales (`USD 40M–400M`) combinando Hubs Tier 1 y Joyas Escondidas sobre costos reales auditados de **TMDB (253 películas)** y **Potencial Ajustado por Sesgo IMDb**, con ordenamiento interactivo por cualquier columna.
* **Ingeniería & Validación Científica:** Motor Híbrido v6 validado con *Leave-One-Out* (**`Recall@10 = 52,22%`**, **4,47x** vs. baseline de géneros), sesiones persistentes en **SQLite WAL**, claves protegidas en `.env`, SQL parametrizado, **Docker/Render** y **7 tests automáticos**.

---

## 🧪 Ejecutar Pruebas Automáticas

```bash
python -m unittest discover -s tests -v
```
