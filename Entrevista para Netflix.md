# TITULO: Entrevista para Netflix

## SUBTITULO: Propuesta para ayudar a Netflix a tomar una decisión

##### Preguntas:

1\. Proponer contenido nuevo

&#x09;> Una serie o película nueva

&#x09;> Importante: Creatividad con Datos -> Como los uso para mi hipótesis

2\. Construir un recomendador

&#x09;> "Qué es lo más popular"

&#x09;> Explicar por qué, cómo, etc.

3\. Detectar tendencias

&#x09;> 2 o 3 tendencias del mercado, cada una con recomendación

&#x09;> Ej: Ahora hay otro tipo de acción (90s -> musculoso héroe mata a todos, 2020s -> Complejizados)

&#x09;> Usar información de los Scripts de las peliculas (Estudiar el wording, pesimista/optimista, que personaje participa más, su desarrollo)

&#x09;> Ej: db Scripts de los Simpsons

4\. Construir una app

&#x09;> Debe agregar valor

&#x09;> Que casos de uso se le puede dar a estos datos

5\. Proponer otro tema

&#x09;> Insights interesantes de los datos

&#x09;> Ej: ¿Cuándo empezó a crecer este contenido? ¿Netflix crecio gracias al cambio tecnológico o por ofrecer un buen producto?



##### Todos los trabajos tienen que tener:

* Las bases de datos utilizadas
* Documento con todos los hallazgos
* Código utilizado
* Presentación



###### TODO DEBE ESTAR FUNDAMENTADO EN DATOS



##### Fuentes de Datos:

* IMDb datasets

  * Qué existe y cómo lo votaron
* API de TMDB

  * De qué trata, cuánto costo y donde se ve
* Netflix Top 10 (info interesante, no es muy grande)

  * Qué se consume en la plataforma
* Google Trends
* Encuestas propias
* Scrapping
* MovieLens
* Wikidata
* Netflix "What we watched"
* Social listening (ver redes sociales)
* Etc.



##### De archivo crudo a base lista para analizar

1. Mirar y medir los archivos antes de cargarlos
2. Entender por qué no entran en memoria
3. Elegir la herramienta y pasar a Parquet
4. Unir tablas sin multiplicar filas
5. Perfilar, filtrar y rankear
6. Formular preguntas que terminen en una decisión



##### Reglas generales

1. Inspeccionar un archivo antes de cargarlo
2. Medir antes de sacar conclusiones
3. Formular la pregunta con precisión antes de analizar





1. ##### Mirar y medir los archivos antes de cargarlos

IMDb son 7 archivos que se unene con dos clasves tconst (títulos) y nconst (personas)

Los archivos están en datasets.imdbs.com -> En la página dice que datos hay en cada columna

Identificar columnas claves, cuales me sirven y cuales no.

Transformar los archivos -> Transformar tsv a csv, genero de la pelicula (son una lista usualmente -> como lo trato?)

Comprimir los archivos -> Archivos.gz (gzip)

En pandas, pueden cambiarse los títulos con "" entre si





##### 2\. Entender por qué no entran en memoria

3 formas de hacerlo -> leer por partes (pandas chunksize), usar SQL (duckdb) -> la mejor, planificar búsqueda de datos (Polars, mejor que pandas)

Cambiar columnas, features para que los datos entren

Bajar la memoria en pandas:

* Cargar columnas que voy a usar
* Elegir el tipo más chico posible (category, int16, int32)
* Filtrar lo antes posible
* Medir el pico de memoria del proceso (archivo entero, pico de memoria, después de procesar)



Parquet lee por columnas, muy eficiente

Cuidado con JOINS (ej: peliculas JOIN akas)





##### 3\. Perfilar, filtrar y rankear

###### Antes de buscar hallazgos, revisa que falta, que es raro y que domina en los datos

Ej: Serie BYU Weekly -> Dice que es de 1900s pero los eps son de los 2000s

Puede ser por errores de carga de datos -> Chequear el dato

Hay ciertas tendencias que se deben a cambios tecnológicos:

&#x09;> video: popularización del vhs (80s)

&#x09;> videoGame: aparecen las primeras consolas (fines de los 70s)

&#x09;> tvEpisode: aparece tv comercial (50s)

Armar las narrativas con fundamentos -> Cuidado con el overfitting -> Esos fundamentos pueden estar equivocados/sobresimplificados -> Las consecuencias de la causa puede darse por delay, tendencia alcista, no inmediato

Filtrar cambia la población -> Mostrar cuantas filas quedan luego de cada filtro, cuanto % perdi del total, que población representa lo que quedo

Cuidado con los ratings -> Puntaje y cantidad de votos (en especial con el bombing de criticas -> por extremidad de votos) -> Usar promedio bayesiano





##### 4\. Formular preguntas que terminen en una decisión

Una buena pregunta cumple 6 condiciones:

* Hay una decisión atrás

&#x09;> Si es A. Netflix hace X, si es B, hace Y

* Esta acotada

&#x09;> No elegir todas las películas -> Especificar en un segmento

* Tiene una métrica explicita

&#x09;> Votos, ratings, regiones, etc. 

* Comparar contra algo

&#x09;> Otro genero, otra época o el promedio

* Se responde con datos

&#x09;> O dice que dato falta y donde conseguirlo

* La respuesta no se conoce de antemano

&#x09;> Si ya se conoce, el análisis no aporta información nueva





























































