"""
Módulo de Integración con la API de The Movie Database (TMDB) en Español (es-ES / es-MX).
Permite enriquecer los títulos de IMDb con:
- Sinopsis y títulos de episodios traducidos oficialmente al español (es-ES).
- Presupuesto (budget), recaudación (revenue) y países productores verificados.
- Tráilers oficiales en video (YouTube keys) para Auto-Preview y reproducción en modal.
- Variantes de pósters/backdrops para personalización con Contextual Artwork Bandits.
"""

import requests
from pathlib import Path
import sys

sys.path.append(str(Path(__file__).resolve().parent.parent))
from config import TMDB_API_KEY, TMDB_READ_ACCESS_TOKEN, TMDB_BASE_URL

# Diccionario de traducción de géneros de IMDb a Español
GENRES_ES_MAP = {
    "Action": "Acción",
    "Adventure": "Aventura",
    "Animation": "Animación",
    "Biography": "Biografía",
    "Comedy": "Comedia",
    "Crime": "Crimen",
    "Documentary": "Documental",
    "Drama": "Drama",
    "Family": "Familiar",
    "Fantasy": "Fantasía",
    "Film-Noir": "Cine Negro",
    "Game-Show": "Concurso",
    "History": "Historia",
    "Horror": "Terror",
    "Music": "Música",
    "Musical": "Musical",
    "Mystery": "Misterio",
    "News": "Noticias",
    "Reality-TV": "Reality",
    "Romance": "Romance",
    "Sci-Fi": "Ciencia Ficción",
    "Short": "Cortometraje",
    "Sport": "Deportes",
    "Talk-Show": "Entrevistas",
    "Thriller": "Suspenso",
    "War": "Bélico",
    "Western": "Western"
}

def traducir_generos(genres_str: str | None) -> str:
    """Traduce una cadena de géneros separada por comas de inglés a español."""
    if not genres_str or str(genres_str) in ["\\N", "nan", "None"]:
        return "Drama, Internacional"
    parts = [p.strip() for p in str(genres_str).split(",") if p.strip()]
    translated = [GENRES_ES_MAP.get(p, p) for p in parts]
    return ", ".join(translated)


class TMDBClient:
    def __init__(self, api_key: str = TMDB_API_KEY, access_token: str = TMDB_READ_ACCESS_TOKEN):
        self.api_key = api_key
        self.access_token = access_token
        self.base_url = TMDB_BASE_URL
        self.is_configured = bool(self.api_key and self.api_key != "TU_API_KEY_DE_TMDB_AQUI")
        
    def _get_headers(self) -> dict:
        if self.access_token and self.access_token != "TU_BEARER_TOKEN_AQUI":
            return {"Authorization": f"Bearer {self.access_token}", "Content-Type": "application/json;charset=utf-8"}
        return {}

    def _get_params(self, extra_params: dict | None = None, language: str = "es-ES") -> dict:
        params = {"language": language}
        if extra_params:
            params.update(extra_params)
        if not self._get_headers():
            params["api_key"] = self.api_key
        return params

    def find_by_imdb_id(self, imdb_id: str, language: str = "es-ES") -> dict | None:
        """
        Consulta el endpoint /find/{external_id} de TMDB pasando el 'tconst' de IMDb en español (es-ES).
        Si la sinopsis en es-ES está vacía, hace fallback a es-MX o en-US.
        """
        if not self.is_configured:
            return None

        url = f"{self.base_url}/find/{imdb_id}"
        params = self._get_params({"external_source": "imdb_id"}, language=language)
        
        try:
            resp = requests.get(url, params=params, headers=self._get_headers(), timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                result = None
                if data.get("movie_results"):
                    result = data["movie_results"][0]
                    result["media_type"] = "movie"
                elif data.get("tv_results"):
                    result = data["tv_results"][0]
                    result["media_type"] = "tv"
                
                # Si no trajo overview en es-ES, probar es-MX
                if result and not result.get("overview") and language == "es-ES":
                    fallback_mx = self.find_by_imdb_id(imdb_id, language="es-MX")
                    if fallback_mx and fallback_mx.get("overview"):
                        result["overview"] = fallback_mx["overview"]
                return result
        except Exception as e:
            print(f"[TMDB Exception] {e}")
        return None

    def get_details(self, tmdb_id: int, media_type: str = "movie", language: str = "es-ES") -> dict | None:
        """
        Obtiene sinopsis en español, presupuesto, recaudación, países productores, videos e imágenes.
        """
        if not self.is_configured:
            return None

        url = f"{self.base_url}/{media_type}/{tmdb_id}"
        params = self._get_params(
            {"append_to_response": "videos,images", "include_image_language": "es,en,null", "include_video_language": "es,en"},
            language=language
        )
        
        try:
            resp = requests.get(url, params=params, headers=self._get_headers(), timeout=10)
            if resp.status_code == 200:
                return resp.json()
        except Exception as e:
            print(f"[TMDB Details Error] {e}")
        return None

    def get_tv_season(self, tmdb_id: int, season_number: int = 1, language: str = "es-ES") -> dict | None:
        """
        Obtiene la lista completa de episodios, duraciones, sinopsis en español e imágenes para una temporada.
        """
        if not self.is_configured:
            return None

        url = f"{self.base_url}/tv/{tmdb_id}/season/{season_number}"
        params = self._get_params(language=language)
        try:
            resp = requests.get(url, params=params, headers=self._get_headers(), timeout=10)
            if resp.status_code == 200:
                return resp.json()
        except Exception as e:
            print(f"[TMDB Season Error] {e}")
        return None

    def extract_youtube_trailer(self, details: dict) -> str | None:
        """Extrae el key de YouTube del tráiler o teaser oficial desde la respuesta de detalles de TMDB."""
        videos = details.get("videos", {}).get("results", [])
        if not videos:
            return None
        # Priorizar Trailer en español, luego Trailer en inglés, luego Teaser
        for v in videos:
            if v.get("site") == "YouTube" and v.get("type") == "Trailer" and str(v.get("iso_639_1")).startswith("es"):
                return v.get("key")
        for v in videos:
            if v.get("site") == "YouTube" and v.get("type") == "Trailer":
                return v.get("key")
        for v in videos:
            if v.get("site") == "YouTube":
                return v.get("key")
        return None

    def extract_alt_posters(self, details: dict) -> list[str]:
        """Extrae hasta 4 rutas de pósters alternativos para el motor de Contextual Artwork Bandits."""
        posters = details.get("images", {}).get("posters", [])
        paths = [p.get("file_path") for p in posters if p.get("file_path")]
        return paths[:4]

    def enrich_title(self, imdb_id: str) -> dict:
        """
        Función de alto nivel: Dado un tconst de IMDb, extrae métricas financieras, sinopsis en español y tráiler.
        """
        found = self.find_by_imdb_id(imdb_id, language="es-ES")
        if not found:
            return {}
            
        tmdb_id = found["id"]
        media_type = found["media_type"]
        details = self.get_details(tmdb_id, media_type, language="es-ES") or {}
        
        overview_es = details.get("overview") or found.get("overview") or ""
        return {
            "tmdb_id": tmdb_id,
            "media_type": media_type,
            "budget": details.get("budget", 0),
            "revenue": details.get("revenue", 0),
            "popularity": details.get("popularity", 0.0),
            "overview": overview_es,
            "production_countries": [c.get("iso_3166_1") for c in details.get("production_countries", [])],
            "trailer_key": self.extract_youtube_trailer(details),
            "alt_posters": self.extract_alt_posters(details)
        }
