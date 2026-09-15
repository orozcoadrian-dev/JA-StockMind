import re
import unicodedata
from decimal import Decimal, InvalidOperation


ABBREVIATIONS = {
    "univ": "universal",
    "univers": "universal",
    "del": "delantero",
    "tras": "trasero",
    "roj": "rojo",
    "roja": "rojo",
    "neg": "negro",
    "blan": "blanco",
    "x": "por",
    "par": "par",
    "grip": "grip",
    "manubrio": "manubrio",
    "moto": "moto",
}


def normalize_name(value: str) -> str:
    if value is None:
        return ""

    text = str(value).lower().strip()
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = text.replace("&", " y ")
    text = text.replace("/", " ")
    text = text.replace(".", " ")
    text = re.sub(r"[^a-z0-9\s]", " ", text)

    tokens = []
    for token in text.split():
        if token.endswith("s") and len(token) > 3 and not token.endswith("ss"):
            token = token[:-1]
        tokens.append(ABBREVIATIONS.get(token, token))

    normalized = " ".join(tokens)
    normalized = re.sub(r"\s+", " ", normalized)
    normalized = normalized.strip()
    return normalized


def parse_price(value: object) -> float:
    if value is None or value == "":
        raise ValueError("Price is required")

    if isinstance(value, (int, float, Decimal)):
        return float(value)

    text = str(value).strip()
    text = text.replace("$", "").replace(" ", "")
    text = text.replace(".", "")
    text = text.replace(",", ".")

    try:
        return float(Decimal(text))
    except (InvalidOperation, ValueError):
        raise ValueError(f"Price format is invalid: {value}")


def extract_attributes(name: str) -> dict:
    normalized = normalize_name(name)
    attributes = {}

    colors = {"rojo": "rojo", "negro": "negro", "azul": "azul", "blanco": "blanco", "gris": "gris"}
    for color, value in colors.items():
        if color in normalized:
            attributes["color"] = value
            break

    size_match = re.search(r"(\d+(?:[.,]\d+)?)\s*(mm|cm)", normalized)
    if size_match:
        attributes["measure"] = size_match.group(0).replace(" ", "")

    if "delantero" in normalized or "del" in normalized:
        attributes["side"] = "delantero"
    if "trasero" in normalized or "tras" in normalized:
        attributes["side"] = "trasero"

    if "grip" in normalized or "manubrio" in normalized:
        attributes["type"] = "grip"
    if "freno" in normalized:
        attributes["type"] = "freno"
    if "filtro" in normalized:
        attributes["type"] = "filtro"

    if "kawasaki" in normalized or "yamaha" in normalized or "honda" in normalized:
        attributes["compatible_brand"] = normalized.split()[0]

    return attributes
