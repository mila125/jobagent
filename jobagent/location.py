import unicodedata

PORTALS = {
    "chile": "cl",
    "mexico": "mx",
    "colombia": "co",
    "peru": "pe",
    "argentina": "ar",
    "venezuela": "ve",
}

def normalize(text):
    text = str(text or "").strip().lower()
    return "".join(
        c for c in unicodedata.normalize("NFKD", text)
        if not unicodedata.combining(c)
    )

def computrabajo_country_code(country):
    normalized = normalize(country)

    code = PORTALS.get(normalized)

    if code is None:
        raise ValueError(
            f"No hay un portal de Computrabajo configurado "
            f"para {country}. No se utilizará otro país."
        )

    return code

def computrabajo_base(country):
    code = computrabajo_country_code(country)
    return f"https://{code}.computrabajo.com"

def computrabajo_login(country):
    code = computrabajo_country_code(country)
    return f"https://candidato.{code}.computrabajo.com/acceso/"      