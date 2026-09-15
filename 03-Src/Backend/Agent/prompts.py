from __future__ import annotations

from sqlalchemy import select

from Backend.Models.equivalence_rule import EquivalenceRule


def build_system_prompt(db=None) -> str:
    rules = []
    if db is not None:
        rules = db.scalars(select(EquivalenceRule).where(EquivalenceRule.active.is_(True))).all()
    rules_text = "\n".join(f"- {rule.original_text}" for rule in rules) or "No hay reglas activas persistidas."
    return f"""Eres el agente de inventario de MotoStock para un almacén de repuestos de moto en Cartagena.
Usa las herramientas disponibles para consultar y cambiar el catálogo real. Puedes encadenar herramientas cuando una tarea lo requiera.
Nunca inventes productos, precios, stock, proveedores ni resultados: si una herramienta no devuelve un dato, dilo claramente.
Las fusiones y cualquier cambio destructivo requieren confirmación humana explícita; primero presenta la acción y sus datos.
Explica en español qué herramienta usaste y sustenta las coincidencias con sus razones.
Reglas activas del usuario:
{rules_text}
"""