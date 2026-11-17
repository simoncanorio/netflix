"""
Módulo de Normalización y Mapeo de Códigos de Países (ISO 3166-1 alpha-2) a Español.
Permite visualizar los nombres completos en el formato solicitado: 'AR - Argentina'.
"""

PAISES_ES = {
    # América del Sur
    "AR": "Argentina",
    "BR": "Brasil",
    "CL": "Chile",
    "CO": "Colombia",
    "UY": "Uruguay",
    "PY": "Paraguay",
    "PE": "Perú",
    "EC": "Ecuador",
    "BO": "Bolivia",
    "VE": "Venezuela",
    
    # América del Norte y Central
    "US": "Estados Unidos",
    "MX": "México",
    "CA": "Canadá",
    "CR": "Costa Rica",
    "PA": "Panamá",
    "GT": "Guatemala",
    "CU": "Cuba",
    "DO": "República Dominicana",
    "PR": "Puerto Rico",
    "SV": "El Salvador",
    "HN": "Honduras",
    "NI": "Nicaragua",
    "JM": "Jamaica",
    "TT": "Trinidad y Tobago",
    "BS": "Bahamas",
    
    # Europa Occidental y Nórdicos
    "ES": "España",
    "GB": "Reino Unido",
    "FR": "Francia",
    "DE": "Alemania",
    "IT": "Italia",
    "PT": "Portugal",
    "IE": "Irlanda",
    "NL": "Países Bajos",
    "BE": "Bélgica",
    "CH": "Suiza",
    "AT": "Austria",
    "DK": "Dinamarca",
    "SE": "Suecia",
    "NO": "Noruega",
    "FI": "Finlandia",
    "IS": "Islandia",
    "LU": "Luxemburgo",
    
    # Europa Oriental y Balcanes
    "PL": "Polonia",
    "CZ": "República Checa",
    "SK": "Eslovaquia",
    "HU": "Hungría",
    "RO": "Rumania",
    "BG": "Bulgaria",
    "GR": "Grecia",
    "HR": "Croacia",
    "RS": "Serbia",
    "SI": "Eslovenia",
    "UA": "Ucrania",
    "RU": "Rusia",
    "BY": "Bielorrusia",
    "LT": "Lituania",
    "LV": "Letonia",
    "EE": "Estonia",
    "BA": "Bosnia y Herzegovina",
    "AL": "Albania",
    "MK": "Macedonia del Norte",
    "ME": "Montenegro",
    
    # Asia y Medio Oriente
    "KR": "Corea del Sur",
    "JP": "Japón",
    "IN": "India",
    "CN": "China",
    "HK": "Hong Kong",
    "TW": "Taiwán",
    "TR": "Turquía",
    "IL": "Israel",
    "TH": "Tailandia",
    "ID": "Indonesia",
    "MY": "Malasia",
    "PH": "Filipinas",
    "SG": "Singapur",
    "VN": "Vietnam",
    "PK": "Pakistán",
    "BD": "Bangladesh",
    "NP": "Nepal",
    "LK": "Sri Lanka",
    "IR": "Irán",
    "IQ": "Irak",
    "SA": "Arabia Saudita",
    "AE": "Emiratos Árabes Unidos",
    "QA": "Catar",
    "KW": "Kuwait",
    "LB": "Líbano",
    "JO": "Jordania",
    "KZ": "Kazajistán",
    "UZ": "Uzbekistán",
    "GE": "Georgia",
    "AM": "Armenia",
    "AZ": "Azerbaiyán",
    
    # África y Oceanía
    "ZA": "Sudáfrica",
    "EG": "Egipto",
    "MA": "Marruecos",
    "NG": "Nigeria",
    "KE": "Kenia",
    "DZ": "Argelia",
    "TN": "Túnez",
    "GH": "Ghana",
    "SN": "Senegal",
    "AU": "Australia",
    "NZ": "Nueva Zelanda",
    
    # Históricos IMDb
    "SUHH": "Unión Soviética",
    "CSHH": "Checoslovaquia",
    "DDDE": "Alemania Oriental",
    "XYU": "Yugoslavia",
}

def formatear_pais(codigo: str | None) -> str:
    """
    Retorna el código y el nombre completo: ej: 'AR - Argentina'.
    Si el código no está en el mapa, retorna 'CODIGO - Desconocido' o el código original.
    """
    if not codigo or codigo in ["UNKNOWN", "\\N", "None", "nan"]:
        return "Desconocido"
    codigo = str(codigo).strip().upper()
    nombre = PAISES_ES.get(codigo)
    if nombre:
        return f"{codigo} - {nombre}"
    return codigo

def obtener_nombre_pais(codigo: str | None) -> str:
    """Retorna únicamente el nombre del país en español."""
    if not codigo or codigo in ["UNKNOWN", "\\N", "None", "nan"]:
        return "Desconocido"
    return PAISES_ES.get(str(codigo).strip().upper(), codigo)

ISO2_TO_ISO3 = {
    "AR": "ARG", "BR": "BRA", "CL": "CHL", "CO": "COL", "UY": "URY", "PY": "PRY", "PE": "PER", "EC": "ECU", "BO": "BOL", "VE": "VEN",
    "US": "USA", "MX": "MEX", "CA": "CAN", "CR": "CRI", "PA": "PAN", "GT": "GTM", "CU": "CUB", "DO": "DOM", "PR": "PRI", "SV": "SLV",
    "HN": "HND", "NI": "NIC", "JM": "JAM", "TT": "TTO", "BS": "BHS",
    "ES": "ESP", "GB": "GBR", "FR": "FRA", "DE": "DEU", "IT": "ITA", "PT": "PRT", "IE": "IRL", "NL": "NLD", "BE": "BEL", "CH": "CHE",
    "AT": "AUT", "DK": "DNK", "SE": "SWE", "NO": "NOR", "FI": "FIN", "IS": "ISL", "LU": "LUX",
    "PL": "POL", "CZ": "CZE", "SK": "SVK", "HU": "HUN", "RO": "ROU", "BG": "BGR", "GR": "GRC", "HR": "HRV", "RS": "SRB", "SI": "SVN",
    "UA": "UKR", "RU": "RUS", "BY": "BLR", "LT": "LTU", "LV": "LVA", "EE": "EST", "BA": "BIH", "AL": "ALB", "MK": "MKD", "ME": "MNE",
    "KR": "KOR", "JP": "JPN", "IN": "IND", "CN": "CHN", "HK": "HKG", "TW": "TWN", "TR": "TUR", "IL": "ISR", "TH": "THA", "ID": "IDN",
    "MY": "MYS", "PH": "PHL", "SG": "SGP", "VN": "VNM", "PK": "PAK", "BD": "BGD", "NP": "NPL", "LK": "LKA", "IR": "IRN", "IQ": "IRQ",
    "SA": "SAU", "AE": "ARE", "QA": "QAT", "KW": "KWT", "LB": "LBN", "JO": "JOR", "KZ": "KAZ", "UZ": "UZB", "GE": "GEO", "AM": "ARM", "AZ": "AZE",
    "ZA": "ZAF", "EG": "EGY", "MA": "MAR", "NG": "NGA", "KE": "KEN", "DZ": "DZA", "TN": "TUN", "GH": "GHA", "SN": "SEN", "AU": "AUS", "NZ": "NZL"
}

def obtener_iso3(codigo: str | None) -> str:
    """Convierte ISO-2 a ISO-3 para gráficos de mapas coropléticos (Plotly)."""
    if not codigo:
        return ""
    return ISO2_TO_ISO3.get(str(codigo).strip().upper(), "")


import unicodedata

def _normalizar_sin_tildes(s: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFD", s.strip().lower())
        if unicodedata.category(c) != "Mn"
    )

ALIAS_PAISES = {
    "corea": "KR", "south korea": "KR", "korea": "KR", "coreano": "KR", "coreana": "KR", "coreanos": "KR",
    "usa": "US", "eeuu": "US", "estados unidos": "US", "united states": "US", "estadounidense": "US", "americano": "US",
    "uk": "GB", "inglaterra": "GB", "gran bretana": "GB", "reino unido": "GB", "britanico": "GB", "britanica": "GB", "ingles": "GB",
    "espana": "ES", "spain": "ES", "espanol": "ES", "espanola": "ES", "espanoles": "ES",
    "argentina": "AR", "argentino": "AR", "argentinos": "AR", "argentinas": "AR",
    "japon": "JP", "japan": "JP", "japones": "JP", "japonesa": "JP", "japoneses": "JP",
    "alemania": "DE", "germany": "DE", "aleman": "DE", "alemana": "DE", "alemanes": "DE",
    "francia": "FR", "france": "FR", "frances": "FR", "francesa": "FR", "franceses": "FR",
    "italia": "IT", "italy": "IT", "italiano": "IT", "italiana": "IT", "italianos": "IT",
    "brasil": "BR", "brazil": "BR", "brasileno": "BR", "brasilena": "BR", "brasilenos": "BR",
    "mexico": "MX", "mexicano": "MX", "mexicana": "MX", "mexicanos": "MX",
    "dinamarca": "DK", "denmark": "DK", "danes": "DK", "danesa": "DK", "daneses": "DK",
    "suecia": "SE", "sweden": "SE", "sueco": "SE", "sueca": "SE",
    "noruega": "NO", "norway": "NO", "noruego": "NO", "noruega": "NO",
    "turquia": "TR", "turkey": "TR", "turco": "TR", "turca": "TR", "turcos": "TR",
    "india": "IN", "indio": "IN", "india": "IN", "bollywood": "IN",
    "colombia": "CO", "colombiano": "CO", "colombiana": "CO",
    "chile": "CL", "chileno": "CL", "chilena": "CL",
    "uruguay": "UY", "uruguayo": "UY",
    "rusia": "RU", "russia": "RU", "ruso": "RU",
    "serbia": "RS", "serbio": "RS",
}

def buscar_codigo_pais_por_nombre(query: str | None) -> str | None:
    """
    Detecta si la búsqueda del usuario corresponde al nombre o código ISO de un país.
    Retorna el código ISO-2 (ej. 'AR', 'KR', 'ES') o None si no coincide con un país.
    """
    if not query:
        return None
    q_raw = query.strip()
    q_upper = q_raw.upper()
    if len(q_upper) == 2 and q_upper in PAISES_ES:
        return q_upper

    # Formato 'AR - Argentina'
    if " - " in q_raw:
        prefix = q_raw.split(" - ")[0].strip().upper()
        if prefix in PAISES_ES:
            return prefix

    q_norm = _normalizar_sin_tildes(q_raw)
    if q_norm in ALIAS_PAISES:
        return ALIAS_PAISES[q_norm]

    for code, name_es in PAISES_ES.items():
        name_norm = _normalizar_sin_tildes(name_es)
        if q_norm == name_norm or (len(q_norm) >= 4 and name_norm.startswith(q_norm)):
            return code
    return None



