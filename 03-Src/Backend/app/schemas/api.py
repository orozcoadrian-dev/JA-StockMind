from datetime import datetime
from typing import Any, Generic, TypeVar

from pydantic import AliasChoices, BaseModel, Field, model_validator


DataT = TypeVar("DataT")


class APIEnvelope(BaseModel, Generic[DataT]):
    data: DataT
    meta: dict[str, Any] = Field(default_factory=dict)


class APIErrorBody(BaseModel):
    code: str
    message: str
    details: dict[str, Any] = Field(default_factory=dict)


class APIError(BaseModel):
    error: APIErrorBody


class SupplierRequest(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    nit: str | None = Field(default=None, max_length=30)
    contact: str | None = Field(default=None, max_length=150)
    active: bool = True


class SupplierPatch(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=120)
    nit: str | None = Field(default=None, max_length=30)
    contact: str | None = Field(default=None, max_length=150)
    active: bool | None = None


class CanonicalRequest(BaseModel):
    name: str = Field(validation_alias=AliasChoices("name", "canonical_name"), min_length=2, max_length=255)
    category: str | None = None
    attributes: dict[str, Any] = Field(default_factory=dict)
    stock_in_bodega: int = Field(default=0, ge=0)
    minimum_stock: int = Field(default=0, ge=0)


class CanonicalPatch(BaseModel):
    name: str | None = Field(default=None, validation_alias=AliasChoices("name", "canonical_name"), min_length=2, max_length=255)
    category: str | None = None
    attributes: dict[str, Any] | None = None
    stock_in_bodega: int | None = Field(default=None, ge=0)
    minimum_stock: int | None = Field(default=None, ge=0)


class RuleRequest(BaseModel):
    original_text: str = Field(min_length=5, max_length=500)
    structured_condition: dict[str, Any] | None = None
    supplier_names: list[str] = Field(default_factory=list)
    active: bool = True
    rule_type: str | None = None
    condition_json: dict[str, Any] | None = None
    suppliers: list[str] | None = None

    @model_validator(mode="before")
    @classmethod
    def accept_both_rule_contracts(cls, value: Any) -> Any:
        if isinstance(value, dict):
            value = dict(value)
            if value.get("structured_condition") is None:
                value["structured_condition"] = value.get("condition_json")
            if not value.get("supplier_names"):
                value["supplier_names"] = value.get("suppliers") or []
            if value.get("structured_condition") and value.get("rule_type"):
                value["structured_condition"].setdefault("type", value["rule_type"])
        return value

    @model_validator(mode="after")
    def validate_rule_condition(self):
        condition = self.structured_condition
        if not isinstance(condition, dict):
            raise ValueError("La condición estructurada de la regla es obligatoria.")
        rule_type = condition.get("type")
        if rule_type == "supplier_equivalence":
            rule_type = "equivalence"
        actions = {"equivalence": "merge_to_canonical", "exclusion": "block_merge", "purchase_preference": "prefer_supplier"}
        if rule_type not in actions:
            raise ValueError("El tipo de regla debe ser equivalence, exclusion o purchase_preference.")
        condition["type"] = rule_type
        condition.setdefault("action", actions[rule_type])
        suppliers = condition.get("suppliers") or self.supplier_names
        if not isinstance(condition.get("match"), dict) or not condition["match"]:
            raise ValueError("La condición debe incluir criterios de coincidencia.")
        minimum = 1 if rule_type == "purchase_preference" else 2
        if len(suppliers) < minimum:
            raise ValueError("La regla no contiene suficientes proveedores.")
        condition["suppliers"] = suppliers
        self.supplier_names = suppliers
        return self


class RulePatch(BaseModel):
    original_text: str | None = Field(default=None, min_length=5, max_length=500)
    active: bool | None = None
    structured_condition: dict[str, Any] | None = None
    supplier_names: list[str] | None = None
    rule_type: str | None = None
    condition_json: dict[str, Any] | None = None

    @model_validator(mode="before")
    @classmethod
    def accept_condition_alias(cls, value: Any) -> Any:
        if isinstance(value, dict):
            value = dict(value)
            if "structured_condition" not in value and "condition_json" in value:
                value["structured_condition"] = value["condition_json"]
            condition = value.get("structured_condition")
            if condition and value.get("rule_type"):
                condition.setdefault("type", value["rule_type"])
        return value


class MatchRejectRequest(BaseModel):
    create_exclusion_rule: bool = False
    original_text: str | None = Field(default=None, max_length=500)


class AgentChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=10000)
    session_id: str = Field(default="default", min_length=1, max_length=64)


class AgentConfirmRequest(BaseModel):
    action_id: int = Field(gt=0)
    approved: bool


class SupplierDTO(BaseModel):
    id: int
    name: str
    nit: str | None = None
    contact: str | None = None
    active: bool
    created_at: datetime


class ProductDTO(BaseModel):
    id: int
    supplier_id: int
    provider_code: str | None = None
    raw_name: str
    normalized_name: str
    category: str | None = None
    unit_price: float
    currency: str
    unit_of_measure: str | None = None
    pack_quantity: int
    price_list_date: str | None = None
    row_hash: str


class CanonicalDTO(BaseModel):
    id: int
    name: str
    category: str | None = None
    attributes: dict[str, Any] = Field(default_factory=dict)
    stock_in_bodega: int
    minimum_stock: int
    suppliers: list[ProductDTO] = Field(default_factory=list)


class ImportDTO(BaseModel):
    id: int
    supplier_id: int
    filename: str
    stored_file_path: str
    summary: dict[str, Any]
    created_at: str


class RuleDTO(BaseModel):
    id: int
    original_text: str
    structured_condition: dict[str, Any]
    supplier_names: list[str] = Field(default_factory=list)
    active: bool
    created_at: str
    applied_count: int


class MatchDTO(BaseModel):
    id: int
    product: ProductDTO
    candidate: ProductDTO
    score: float
    reasons: list[Any] = Field(default_factory=list)
    decision: str
    status: str


ERROR_RESPONSES = {
    code: {"model": APIError, "description": description}
    for code, description in {
        400: "Solicitud incorrecta",
        404: "Recurso no encontrado",
        409: "Conflicto con el estado actual",
        413: "Archivo demasiado grande",
        422: "Error de validación",
        429: "Límite de solicitudes excedido",
        500: "Error interno",
        503: "Servicio no disponible",
    }.items()
}


def responses(*codes: int) -> dict[int, dict[str, Any]]:
    documented_codes = set(codes) | {422}
    return {code: ERROR_RESPONSES[code] for code in documented_codes}