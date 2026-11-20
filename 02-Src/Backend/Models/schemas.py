from __future__ import annotations

from datetime import date
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


VALID_RULE_TYPES = {"supplier_equivalence", "exclusion", "purchase_preference"}
VALID_RULE_ACTIONS = {"merge_to_canonical", "block_merge", "prefer_supplier"}


class SupplierCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    name: str = Field(..., min_length=2, max_length=200)
    nit: str | None = Field(default=None, min_length=5, max_length=50)
    contact: str | None = Field(default=None, max_length=200)
    active: bool = True

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        if not value or not value.strip():
            raise ValueError("El nombre del proveedor no puede estar vacío.")
        return value.strip()

    @field_validator("nit")
    @classmethod
    def validate_nit(cls, value: str | None) -> str | None:
        if value is not None and value.strip() == "":
            raise ValueError("El NIT no puede estar vacío si se envía.")
        return value.strip() if value else None


class SupplierOut(SupplierCreate):
    id: int
    created_at: str | None = None


class ProductCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    supplier_id: int = Field(..., gt=0)
    provider_code: str = Field(..., min_length=1, max_length=100)
    raw_name: str = Field(..., min_length=1, max_length=500)
    normalized_name: str = Field(..., min_length=1, max_length=500)
    category: str = Field(..., min_length=2, max_length=100)
    unit_price: float = Field(..., gt=0)
    currency: str = Field(default="COP", min_length=3, max_length=10)
    unit_of_measure: str = Field(..., min_length=1, max_length=50)
    pack_quantity: int = Field(..., gt=0)
    price_list_date: date
    row_hash: str = Field(..., min_length=8, max_length=128)

    @field_validator("provider_code", "raw_name", "normalized_name")
    @classmethod
    def validate_non_empty_strings(cls, value: str) -> str:
        if not value or not value.strip():
            raise ValueError("Este campo es obligatorio y no puede estar vacío.")
        return value.strip()


class ProductOut(ProductCreate):
    id: int
    created_at: str | None = None


class CanonicalProductCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    name: str = Field(..., min_length=2, max_length=300)
    category: str = Field(..., min_length=2, max_length=100)
    attributes: dict[str, Any] = Field(default_factory=dict)
    stock_in_bodega: int = Field(default=0, ge=0)
    minimum_stock: int = Field(default=0, ge=0)


class CanonicalProductOut(CanonicalProductCreate):
    id: int
    created_at: str | None = None


class ProductLinkCreate(BaseModel):
    product_id: int = Field(..., gt=0)
    canonical_product_id: int = Field(..., gt=0)
    confidence: float = Field(..., ge=0.0, le=1.0)
    origin: str = Field(default="suggestion", min_length=2, max_length=50)
    confirmed_by: str | None = Field(default=None, max_length=200)


class ProductLinkOut(ProductLinkCreate):
    id: int
    created_at: str | None = None


class StructuredRule(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    type: str = Field(...)
    match: dict[str, Any] = Field(default_factory=dict)
    suppliers: list[str] = Field(default_factory=list)
    action: str = Field(...)
    confidence: float = Field(..., ge=0.0, le=1.0)

    @field_validator("type")
    @classmethod
    def validate_rule_type(cls, value: str) -> str:
        if value not in VALID_RULE_TYPES:
            raise ValueError(
                "El tipo de regla debe ser uno de: supplier_equivalence, exclusion o purchase_preference."
            )
        return value

    @field_validator("action")
    @classmethod
    def validate_rule_action(cls, value: str) -> str:
        if value not in VALID_RULE_ACTIONS:
            raise ValueError(
                "La acción de la regla debe ser una de: merge_to_canonical, block_merge o prefer_supplier."
            )
        return value


class EquivalenceRuleCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    original_text: str = Field(..., min_length=5, max_length=500)
    structured_condition: dict[str, Any] = Field(...)
    supplier_names: list[str] = Field(default_factory=list)
    active: bool = True

    @field_validator("structured_condition")
    @classmethod
    def validate_structured_condition(cls, value: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(value, dict):
            raise ValueError("La condición estructurada debe ser un objeto JSON.")

        rule_type = value.get("type")
        action = value.get("action")
        if rule_type not in VALID_RULE_TYPES:
            raise ValueError(
                "El tipo de regla debe ser uno de: supplier_equivalence, exclusion o purchase_preference."
            )
        if action not in VALID_RULE_ACTIONS:
            raise ValueError(
                "La acción de la regla debe ser una de: merge_to_canonical, block_merge o prefer_supplier."
            )
        if "confidence" not in value or not isinstance(value["confidence"], (int, float)):
            raise ValueError("La regla debe incluir un campo confidence numérico entre 0 y 1.")
        if not 0.0 <= float(value["confidence"]) <= 1.0:
            raise ValueError("El valor de confidence debe estar entre 0 y 1.")
        if "suppliers" in value and value["suppliers"]:
            cleaned_suppliers = [str(item).strip() for item in value["suppliers"] if str(item).strip()]
            if not cleaned_suppliers:
                raise ValueError("Los proveedores de la regla no pueden estar vacíos.")
            value["suppliers"] = cleaned_suppliers
        return value

    @field_validator("supplier_names")
    @classmethod
    def validate_supplier_names(cls, value: list[str]) -> list[str]:
        cleaned = [item.strip() for item in value if item and item.strip()]
        if not cleaned:
            raise ValueError("Debe incluir al menos un proveedor en la regla.")
        return cleaned


class EquivalenceRuleOut(EquivalenceRuleCreate):
    id: int
    created_at: str | None = None
    applied_count: int = 0


class AgentActionCreate(BaseModel):
    tool_name: str = Field(..., min_length=2, max_length=200)
    input_payload: dict[str, Any] = Field(default_factory=dict)
    result: dict[str, Any] = Field(default_factory=dict)
    required_confirmation: bool = False
    approved: bool | None = None


class AgentActionOut(AgentActionCreate):
    id: int
    timestamp: str | None = None
