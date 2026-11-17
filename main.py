"""
Orquestador Principal del Pipeline de Analítica y Big Data para Netflix.
Permite ejecutar etapas individuales o el pipeline completo de punta a punta.

Uso:
    python main.py --all           # Ejecuta las 5 etapas completas
    python main.py --stage 1       # Solo Etapa 1 (Ingesta y Profiling)
    python main.py --stage 2       # Solo Etapa 2 (Pre-agregación, Joins y Bayes)
    python main.py --stage 3       # Solo Etapa 3 (Análisis Histórico y Spillover)
    python main.py --stage 4       # Solo Etapa 4 (Hubs y Decisión de Negocio)
    python main.py --stage 5       # Solo Etapa 5 (Motor Recomendador Cross-Border)
"""

import argparse
import sys
import time
from pathlib import Path

from config import REPORTS_DIR, PARQUET_DIR
from src.stage1_ingestion import run_stage1
from src.stage2_eda_cleaning import run_stage2
from src.stage3_history_trends import run_stage3
from src.stage4_hubs_decision import run_stage4
from src.stage5_recommender import run_stage5

def main():
    parser = argparse.ArgumentParser(description="Pipeline de Expansión Internacional para Netflix")
    parser.add_argument("--stage", type=int, choices=[1, 2, 3, 4, 5], help="Ejecutar una etapa específica (1 a 5)")
    parser.add_argument("--all", action="store_true", help="Ejecutar todas las etapas en orden secuencial")
    
    args = parser.parse_args()
    
    # Si no pasa argumentos, ejecutamos todo por defecto de forma interactiva
    run_all = args.all or (args.stage is None)
    
    t_start = time.time()
    print("=" * 75)
    print("PIPELINE DE DATA SCIENCE & BIG DATA: EXPANSIÓN INTERNACIONAL DE NETFLIX")
    print("=" * 75)
    
    if run_all or args.stage == 1:
        print("\n>>> INICIANDO ETAPA 1: Ingesta, Profiling y Optimización de Memoria")
        run_stage1()
        
    if run_all or args.stage == 2:
        print("\n>>> INICIANDO ETAPA 2: Exploración (EDA), Joins Anti-Explosión y Bayes")
        run_stage2()
        
    if run_all or args.stage == 3:
        print("\n>>> INICIANDO ETAPA 3: Análisis Histórico de Globalización y Spillover")
        run_stage3()
        
    if run_all or args.stage == 4:
        print("\n>>> INICIANDO ETAPA 4: Hubs de Producción y Joyas Escondidas (Decisión)")
        run_stage4()
        
    if run_all or args.stage == 5:
        print("\n>>> INICIANDO ETAPA 5: Sistema Recomendador Cross-Border")
        run_stage5()
        
    t_total = time.time() - t_start
    print("\n" + "=" * 75)
    print(f"PIPELINE FINALIZADO EXITOSAMENTE en {t_total:.2f} segundos.")
    print(f"Archivos Parquet generados en: {PARQUET_DIR.resolve()}")
    print(f"Informes ejecutivos guardados en: {REPORTS_DIR.resolve()}")
    print("=" * 75)

if __name__ == "__main__":
    main()

