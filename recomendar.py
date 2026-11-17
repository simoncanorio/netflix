"""
Herramienta Interactiva de Recomendaciones Cross-Border para Netflix.
Permite consultar en tiempo real las recomendaciones internacionales para cualquier película o serie.

Uso:
    python recomendar.py "Parasite"
    python recomendar.py "Dark"
    python recomendar.py "Money Heist"
    python recomendar.py                 # Modo interactivo (te pide el nombre)
"""

import sys
from pathlib import Path
from src.stage5_recommender import CrossBorderRecommender

def main():
    print("=" * 75)
    print("NETFLIX CROSS-BORDER AFFINITY RECOMMENDER")
    print("=" * 75)
    
    # Inicializar el recomendador
    recommender = CrossBorderRecommender()
    
    # Si pasó el título como argumento en la terminal
    if len(sys.argv) > 1:
        query = " ".join(sys.argv[1:])
        recs = recommender.recommend(query, top_k=5, force_cross_border=True)
        if not recs.empty:
            print("\nRESULTADOS RECOMENDADOS (Descubrimiento Fuera de Fronteras):")
            print("-" * 75)
            print(recs.to_string(index=False))
            print("-" * 75)
        return

    # Si no pasó argumento, abrir modo interactivo continuo
    print("\nModo Interactivo activado. Escribe 'salir' para terminar.")
    while True:
        try:
            query = input("\nIngresa el nombre de una película o serie (ej: 'Dark', 'Parasite', 'Breaking Bad'): ").strip()
            if not query or query.lower() in ["salir", "exit", "quit"]:
                print("¡Hasta luego!")
                break
                
            recs = recommender.recommend(query, top_k=5, force_cross_border=True)
            if not recs.empty:
                print("\nRECOMENDACIONES CROSS-BORDER (Descubrimiento Global):")
                print("-" * 75)
                print(recs.to_string(index=False))
                print("-" * 75)
        except (KeyboardInterrupt, EOFError):
            print("\n¡Hasta luego!")
            break

if __name__ == "__main__":
    main()

