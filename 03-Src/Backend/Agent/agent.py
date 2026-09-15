import re
from difflib import SequenceMatcher


class SemanticAgent:
    """Simula un agente de IA para comparar SKUs ambiguos."""

    DOMAIN_SYNONYMS = {
        "manilar": "grip",
        "manillar": "grip",
        "grip": "grip",
        "mango": "grip",
        "aso": "asiento",
        "asiento": "asiento",
        "sillin": "asiento",
        "faro": "faro",
        "cabina": "carroceria",
        "carroceria": "carroceria",
        "llanta": "llanta",
        "neumatico": "llanta",
        "mec": "motor",
        "motor": "motor",
        "cadena": "cadena",
        "filtro": "filtro",
        "aceite": "aceite",
        "amortiguador": "amortiguador",
        "suspension": "amortiguador",
    }

    @staticmethod
    def normalize_text(text: str) -> str:
        text = text.lower().strip()
        text = re.sub(r"[^a-z0-9\s]", " ", text)
        text = re.sub(r"\s+", " ", text)
        return text

    def _expand_synonyms(self, text: str):
        tokens = []
        for token in text.split():
            token = self.DOMAIN_SYNONYMS.get(token, token)
            tokens.append(token)
        return tokens

    def compare_skus(self, sku_a: str, sku_b: str) -> dict:
        if not sku_a or not sku_b:
            raise ValueError("Ambas descripciones de SKU son requeridas.")

        sku_a_norm = self.normalize_text(sku_a)
        sku_b_norm = self.normalize_text(sku_b)

        tokens_a = self._expand_synonyms(sku_a_norm)
        tokens_b = self._expand_synonyms(sku_b_norm)

        set_a = set(tokens_a)
        set_b = set(tokens_b)

        token_overlap = len(set_a & set_b) / max(len(set_a | set_b), 1)
        token_similarity = 1 - (len(set_a ^ set_b) / max(len(set_a | set_b), 1))

        string_similarity = SequenceMatcher(None, sku_a_norm, sku_b_norm).ratio()

        score = (0.45 * token_similarity) + (0.35 * string_similarity) + (0.20 * token_overlap)

        if len(tokens_a) <= 2 and len(tokens_b) <= 2:
            score = min(0.98, score + 0.08)

        confidence = round(score * 100, 2)
        recommendation = "Fusionar" if confidence >= 72 else "Revisar"

        return {
            "similarity": confidence,
            "confidence": confidence,
            "recommendation": recommendation,
            "evidence": {
                "token_overlap": round(token_overlap * 100, 2),
                "string_similarity": round(string_similarity * 100, 2),
                "shared_terms": sorted(set_a & set_b),
            },
            "message": (
                "Se recomienda fusionar los SKUs por alta similitud semántica."
                if recommendation == "Fusionar"
                else "Se recomienda revisar manualmente la coincidencia antes de fusionar."
            ),
        }
