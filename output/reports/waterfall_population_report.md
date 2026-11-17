# Reporte de Auditoría y Cascada de Población (Etapa 2)

- **Total Títulos Filtrados en Basics (Movies/Series no adultas):** 1,130,064
- **Total Títulos con Ratings Registrados:** 1,727,016
- **Catálogo Maestro Final Integrado (Join 1:1 + Filtro Temporal y Votos):** 132,887
- **Títulos con Coincidencia en Netflix Top 10 Semanal Oficial:** 7,276
- **Retención Poblacional Respecto a Basics:** 11.76%

### Parámetros del Promedio Bayesiano:
- **Media Global ($C$):** 6.82
- **Umbral de Votos p75 ($m$):** 1002
- **Fórmula Aplicada:** $WR = \frac{v}{v + m} \cdot R + \frac{m}{v + m} \cdot C$

### Fuentes Integradas en Grano tconst:
1. `title.basics` (Atributos de título, metraje y año)
2. `title.ratings` (Popularidad y calificación bayesiana)
3. `title.akas` pre-agregado (Huella de internacionalización y país doméstico)
4. `Netflix Top 10` (Horas de consumo acumuladas y semanas de permanencia)
