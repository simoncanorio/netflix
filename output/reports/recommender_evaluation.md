# Evaluación del Sistema Recomendador Cross-Border (Etapa 5)

### Lógica de Ponderación Híbrida:
$$\text{Final Score} = 0.50 \cdot \text{Similitud Coseno} + 0.35 \cdot \left(\frac{\text{Bayes Rating}}{10}\right) + 0.10 \cdot \text{Reach Factor} + \text{Netflix Top 10 Boost}$$

### Características Clave:
1. **Penalización del 85% a títulos domésticos:** Obliga al sistema a recomendar joyas fuera de las fronteras del título semilla.
2. **Visualización Completa de Países:** Todo país se presenta en el formato solicitado `Código - Nombre Completo` (ej: `AR - Argentina`, `KR - Corea del Sur`).
3. **Flag de Validación en Streaming:** Identifica de forma inmediata los títulos que han comprobado éxito masivo en el Netflix Top 10 Semanal Oficial.
