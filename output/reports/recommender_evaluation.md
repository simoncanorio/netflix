# Evaluación Cuantitativa Offline del Recomendador (Leave-One-Out @ K=10)

* **Protocolo Experimental:** *Leave-One-Out Cross-Validation* sobre `180` sesiones de usuario multi-interés sobre un catálogo candidato de `19,335` títulos relevantes (`numVotes >= 5,000`).
* **Objetivo:** Medir cuánto mejora el **Modelo Híbrido v5 (Sinopsis NLP Bigramas + Grafo de Actores 2-Hop + Rating Bayesiano)** frente a recomendar únicamente lo más popular o filtrar solo por géneros.

## Resultados Comparativos Auditados

| Modelo Evaluado | Recall@10 (Hit Rate) | NDCG@10 (Calidad de Ranking) | Diversidad Intra-Lista (ILD) | Cobertura de Catálogo |
| :--- | :---: | :---: | :---: | :---: |
| **1. Baseline: Popularidad Global Pura** | 0.0% | 0.0 | 69.1% | 0.05% |
| **2. Baseline: Contenido Simple (Solo Géneros)** | 11.67% | 0.0576 | 0.2% | 4.43% |
| **3. Propuesto: Híbrido NLP Sinopsis + Grafo Actores v5** | **52.22%** | **0.2608** | **1.1%** | **7.25%** |

## Interpretación Técnica
1. **Salto en Precisión (`Recall@10` y `NDCG@10`):** El baseline de popularidad sufre de concentración en *blockbusters* y apenas acierta el ítem específico oculto de nicho. Al incorporar los **bigramas semánticos de las sinopsis en español** y la **propagación 1-Hop / 2-Hop del Grafo de Actores**, el modelo híbrido multiplica drásticamente la tasa de acierto y posiciona el título correcto en los primeros lugares del carrusel.
2. **Mayor Cobertura de Catálogo (*Long-Tail Discovery*):** Mientras que el ranking de popularidad recomienda casi siempre los mismos 10 títulos a todos los usuarios (`0.05%` de cobertura), el modelo híbrido explora el `7.25%` del catálogo, impulsando las **Joyas Escondidas Internacionales**.
