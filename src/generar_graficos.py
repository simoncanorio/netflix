"""
Módulo de Visualización Gráfica para el Proyecto Netflix.
Genera gráficos estáticos de alta resolución (PNG) con Matplotlib/Seaborn
y un Tablero Interactivo completo (HTML) con Plotly para la presentación ejecutiva.
Todos los países se visualizan con su formato completo: 'AR - Argentina'.
"""

from pathlib import Path
import duckdb
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
import plotly.express as px

import sys
sys.path.append(str(Path(__file__).resolve().parent.parent))
from config import PARQUET_FILES, OUTPUT_DIR
from src.paises import formatear_pais

FIGURES_DIR = OUTPUT_DIR / "figures"
FIGURES_DIR.mkdir(parents=True, exist_ok=True)

# Configurar estilo visual profesional de Netflix / Data Science
plt.style.use("seaborn-v0_8-whitegrid" if "seaborn-v0_8-whitegrid" in plt.style.available else "default")
plt.rcParams["font.family"] = "sans-serif"
plt.rcParams["font.size"] = 11

def graficar_evolucion_historica():
    """Gráfico 1: Evolución del Spillover Regional a través de las Eras Tecnológicas."""
    print("-> Generando Gráfico 1: Evolución histórica de internacionalización...")
    con = duckdb.connect()
    master_p = PARQUET_FILES["master"]
    
    query = f"""
    WITH categorized AS (
        SELECT 
            startYear,
            num_regiones,
            bayesian_rating,
            CASE 
                WHEN domestic_region IN ('US', 'GB') THEN 'US/GB - Mercado Anglosajón'
                ELSE 'Producciones Locales Internacionales'
            END AS mercado,
            CASE 
                WHEN startYear BETWEEN 1980 AND 1996 THEN '1. VHS (1980-1996)'
                WHEN startYear BETWEEN 1997 AND 2009 THEN '2. DVD (1997-2009)'
                WHEN startYear BETWEEN 2010 AND 2016 THEN '3. Early Streaming (2010-2016)'
                WHEN startYear BETWEEN 2017 AND 2024 THEN '4. Global SVOD (2017-2024)'
                ELSE NULL
            END AS era
        FROM '{master_p.as_posix()}'
        WHERE domestic_region != 'UNKNOWN'
    )
    SELECT 
        era,
        mercado,
        ROUND(MEDIAN(num_regiones), 1) AS mediana_regiones,
        ROUND(AVG(CASE WHEN num_regiones >= 10 THEN 1.0 ELSE 0.0 END) * 100, 1) AS pct_spillover_global
    FROM categorized
    WHERE era IS NOT NULL
    GROUP BY era, mercado
    ORDER BY era, mercado;
    """
    df = con.execute(query).df()
    
    fig, ax1 = plt.subplots(figsize=(11, 6), dpi=300)
    
    sns.barplot(
        data=df,
        x="era",
        y="pct_spillover_global",
        hue="mercado",
        palette=["#4a4a4a", "#E50914"],  # Gris neutro y Rojo Netflix
        ax=ax1,
        edgecolor="black",
        linewidth=0.8
    )
    
    ax1.set_title("Evolución de la Tasa de Expansión Global (Spillover en >= 10 Regiones)", fontsize=14, fontweight="bold", pad=15)
    ax1.set_xlabel("Hito Tecnológico / Era de Distribución", fontsize=12, labelpad=10)
    ax1.set_ylabel("% de Títulos con Expansión Global (>=10 Regiones)", fontsize=12)
    ax1.set_ylim(0, 100)
    
    for p in ax1.patches:
        height = p.get_height()
        if height > 0:
            ax1.annotate(f"{height:.1f}%",
                         (p.get_x() + p.get_width() / 2., height / 2),
                         ha='center', va='center', fontsize=10, color='white' if height > 30 else 'black', fontweight='bold')

    ax1.legend(title="Origen de Producción", title_fontsize="11", loc="upper left")
    plt.tight_layout()
    
    out_file = FIGURES_DIR / "1_evolucion_spillover_tecnologico.png"
    fig.savefig(out_file)
    plt.close(fig)
    print(f"  [OK] Guardado en: {out_file.name}")
    return out_file

def graficar_matriz_hubs_y_joyas():
    """Gráfico 2: Cuadrante Estratégico (Rating Lift vs Reach Lift con nombres de países completos)."""
    print("-> Generando Gráfico 2: Cuadrante de Hubs y Joyas Escondidas...")
    con = duckdb.connect()
    hubs_p = PARQUET_FILES["hubs"]
    df_hubs = con.execute(f"SELECT * FROM '{hubs_p.as_posix()}'").df()
    
    fig, ax = plt.subplots(figsize=(13, 8), dpi=300)
    
    colors = {
        "Tier 1 Global Hub (Invertir en Estudio Propio)": "#E50914",      # Rojo Netflix
        "Joya Escondida / Alta Calidad (Adquisición de Licencias Baratas)": "#1a1a1a", # Negro Netflix
        "Hub de Distribución Regional": "#564d4d",                        # Gris
        "Retención Doméstica": "#b3b3b3"                                  # Gris claro
    }
    
    for estrategia, grupo in df_hubs.groupby("estrategia_netflix"):
        color = colors.get(estrategia, "#333333")
        ax.scatter(
            grupo["reach_lift"],
            grupo["rating_lift"],
            s=grupo["total_titulos"] * 1.5,
            color=color,
            alpha=0.8,
            edgecolors="black",
            label=estrategia
        )
        
        # Etiquetar con nombre completo (ej: KR - Corea del Sur)
        for _, row in grupo.iterrows():
            if row["rating_lift"] >= 0.12 or abs(row["reach_lift"]) >= 6.0:
                ax.annotate(
                    row["pais"],
                    (row["reach_lift"], row["rating_lift"]),
                    xytext=(5, 5),
                    textcoords="offset points",
                    fontsize=8.5,
                    fontweight="bold"
                )

    ax.axhline(0, color="gray", linestyle="--", linewidth=1)
    ax.axvline(0, color="gray", linestyle="--", linewidth=1)
    
    ax.set_title("Matriz de Decisión Estratégica: Calidad Bayesiana vs. Alcance de Exportación (2015-2024)", fontsize=13, fontweight="bold", pad=15)
    ax.set_xlabel("Reach Lift vs Benchmark Global (Regiones alcanzadas)", fontsize=11)
    ax.set_ylabel("Rating Lift vs Benchmark Global (Puntos de Calificación Bayesiana)", fontsize=11)
    
    ax.text(12, 0.40, "CUADRANTE 1: TIER 1 GLOBAL HUBS\n(Inversión en Estudios Propios)", fontsize=10, color="#E50914", fontweight="bold", ha="right")
    ax.text(-10, 0.40, "CUADRANTE 2: JOYAS ESCONDIDAS\n(Adquisición Exclusiva a Bajo Costo)", fontsize=10, color="#1a1a1a", fontweight="bold", ha="left")

    ax.legend(title="Recomendación Estratégica", loc="lower right", frameon=True, fontsize=9)
    plt.tight_layout()
    
    out_file = FIGURES_DIR / "2_cuadrante_hubs_y_joyas.png"
    fig.savefig(out_file)
    plt.close(fig)
    print(f"  [OK] Guardado en: {out_file.name}")
    return out_file

def graficar_horas_netflix_por_pais():
    """Gráfico 3: Top Países Productores por Horas de Consumo en Netflix Top 10."""
    print("-> Generando Gráfico 3: Horas vistas en Netflix Top 10 por país...")
    con = duckdb.connect()
    hubs_p = PARQUET_FILES["hubs"]
    
    query = f"""
    SELECT pais, millones_horas_netflix, titulos_top10_netflix
    FROM '{hubs_p.as_posix()}'
    WHERE millones_horas_netflix > 0
    ORDER BY millones_horas_netflix DESC
    LIMIT 12;
    """
    df = con.execute(query).df()
    
    fig, ax = plt.subplots(figsize=(11, 7), dpi=300)
    
    # Fix de FutureWarning: asignar y a hue y legend=False
    sns.barplot(
        data=df,
        x="millones_horas_netflix",
        y="pais",
        hue="pais",
        palette="Reds_r",
        legend=False,
        ax=ax,
        edgecolor="black"
    )
    
    ax.set_title("Top Mercados No-Anglosajones por Horas de Streaming (Netflix Top 10 Oficial)", fontsize=14, fontweight="bold", pad=15)
    ax.set_xlabel("Millones de Horas Vistas Acumuladas en Netflix", fontsize=12)
    ax.set_ylabel("País de Producción (Código - Nombre Completo)", fontsize=12)
    
    for p in ax.patches:
        width = p.get_width()
        ax.annotate(f"{width:,.1f} M",
                    (width, p.get_y() + p.get_height() / 2.),
                    xytext=(6, 0), textcoords="offset points",
                    ha='left', va='center', fontsize=9.5, fontweight='bold')

    plt.tight_layout()
    out_file = FIGURES_DIR / "3_top_paises_horas_netflix.png"
    fig.savefig(out_file)
    plt.close(fig)
    print(f"  [OK] Guardado en: {out_file.name}")
    return out_file

def generar_dashboard_interactivo_html():
    """Genera un archivo HTML interactivo con Plotly para abrir en el navegador."""
    print("-> Generando Dashboard Interactivo en HTML con Plotly...")
    con = duckdb.connect()
    hubs_p = PARQUET_FILES["hubs"]
    df_hubs = con.execute(f"SELECT * FROM '{hubs_p.as_posix()}'").df()
    
    fig_scatter = px.scatter(
        df_hubs,
        x="reach_lift",
        y="rating_lift",
        size="total_titulos",
        color="estrategia_netflix",
        hover_name="pais",
        hover_data={
            "pais": False,
            "rating_bayesiano_medio": True,
            "promedio_regiones": True,
            "millones_horas_netflix": True,
            "titulos_top10_netflix": True,
            "reach_lift": False,
            "rating_lift": False
        },
        color_discrete_map={
            "Tier 1 Global Hub (Invertir en Estudio Propio)": "#E50914",
            "Joya Escondida / Alta Calidad (Adquisición de Licencias Baratas)": "#221f1f",
            "Hub de Distribución Regional": "#6c757d",
            "Retención Doméstica": "#adb5bd"
        },
        title="<b>Matriz Interactiva: Dónde Invertir en Producción vs. Licencias</b>"
    )
    fig_scatter.add_hline(y=0, line_dash="dash", line_color="gray")
    fig_scatter.add_vline(x=0, line_dash="dash", line_color="gray")
    fig_scatter.update_layout(template="plotly_white", height=550)

    df_net = df_hubs[df_hubs["millones_horas_netflix"] > 0].sort_values(by="millones_horas_netflix", ascending=True).tail(15)
    fig_bars = px.bar(
        df_net,
        x="millones_horas_netflix",
        y="pais",
        orientation="h",
        color="millones_horas_netflix",
        color_continuous_scale="Reds",
        title="<b>Horas de Visualización Acumuladas en Netflix Top 10 por País (Código y Nombre Completo)</b>",
        labels={"millones_horas_netflix": "Millones de Horas", "pais": "País"}
    )
    fig_bars.update_layout(template="plotly_white", height=520)

    html_content = f"""
    <!DOCTYPE html>
    <html lang="es">
    <head>
        <meta charset="UTF-8">
        <title>Dashboard Ejecutivo - Estrategia Internacional Netflix</title>
        <script src="https://cdn.plot.ly/plotly-2.35.2.min.js"></script>
        <style>
            body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; margin: 0; background-color: #141414; color: #fff; }}
            .header {{ background-color: #000; padding: 25px 40px; border-bottom: 3px solid #E50914; display: flex; justify-content: space-between; align-items: center; }}
            .header h1 {{ margin: 0; color: #E50914; font-size: 26px; }}
            .container {{ max-width: 1300px; margin: 30px auto; padding: 0 20px; }}
            .kpi-row {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 20px; margin-bottom: 30px; }}
            .kpi-card {{ background: #221f1f; padding: 20px; border-radius: 8px; border-left: 4px solid #E50914; }}
            .kpi-title {{ font-size: 13px; text-transform: uppercase; color: #aaa; margin-bottom: 5px; }}
            .kpi-value {{ font-size: 26px; font-weight: bold; color: #fff; }}
            .card {{ background: #fff; border-radius: 8px; padding: 20px; margin-bottom: 30px; color: #333; }}
            .footer {{ text-align: center; padding: 30px; color: #777; font-size: 13px; }}
        </style>
    </head>
    <body>
        <div class="header">
            <div>
                <h1>NETFLIX ENTERTAINMENT ANALYTICS</h1>
                <div style="color: #bbb; font-size: 14px; margin-top: 5px;">Decisión Estratégica: Expansión Internacional y Estrategia Glocal</div>
            </div>
            <div style="background: #E50914; color: white; padding: 6px 14px; border-radius: 4px; font-weight: bold; font-size: 13px;">
                CONFIDENCIAL
            </div>
        </div>
        
        <div class="container">
            <div class="kpi-row">
                <div class="kpi-card">
                    <div class="kpi-title">Títulos Depurados Analizados</div>
                    <div class="kpi-value">132,887</div>
                </div>
                <div class="kpi-card">
                    <div class="kpi-title">Horas Vistas en Top 10 (No-Anglo)</div>
                    <div class="kpi-value">72.7 B hrs</div>
                </div>
                <div class="kpi-card">
                    <div class="kpi-title">Spillover Global SVOD (>=10 Regiones)</div>
                    <div class="kpi-value">63.4%</div>
                </div>
                <div class="kpi-card">
                    <div class="kpi-title">Hubs Tier 1 Prioritarios</div>
                    <div class="kpi-value">KR - Corea, ES - España, DK - Dinamarca</div>
                </div>
            </div>
            
            <div class="card">
                {fig_scatter.to_html(full_html=False, include_plotlyjs=False)}
            </div>
            
            <div class="card">
                {fig_bars.to_html(full_html=False, include_plotlyjs=False)}
            </div>
        </div>
        
        <div class="footer">
            Taller 2 - Data Science & Market Analytics | Basado en IMDb Core Datasets + Netflix Top 10 + TMDB API
        </div>
    </body>
    </html>
    """
    
    out_html = OUTPUT_DIR / "dashboard_netflix.html"
    out_html.write_text(html_content, encoding="utf-8")
    print(f"  [OK] Dashboard interactivo generado en: {out_html.name}")
    return out_html

def main():
    print("=" * 65)
    print("GENERADOR DE GRÁFICOS Y TABLEROS DE DECISIÓN (NETFLIX)")
    print("=" * 65)
    graficar_evolucion_historica()
    graficar_matriz_hubs_y_joyas()
    graficar_horas_netflix_por_pais()
    generar_dashboard_interactivo_html()
    print("=" * 65)
    print(f"[✓] Todas las visualizaciones generadas en: {OUTPUT_DIR.resolve()}")
    print("=" * 65)

if __name__ == "__main__":
    main()
