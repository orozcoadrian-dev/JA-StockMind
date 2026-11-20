from __future__ import annotations

from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class StrictSchema(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True, from_attributes=True)


class SupplierCreate(StrictSchema):
    name: str = Field(min_length=2, max_length=200)
    nit: str | None = Field(default=None, min_length=5, max_length=50)
    contact_info: str | None = Field(default=None, max_length=300)
    is_active: bool = True


class SupplierRead(SupplierCreate):
    id: int
    created_at: datetime


class ProductCreate(StrictSchema):
    supplier_id: int = Field(gt=0)
    supplier_code: str = Field(min_length=1, max_length=100)
    raw_name: str = Field(min_length=1, max_length=500)
    normalized_name: str = Field(min_length=1, max_length=500)
    category: str = Field(min_length=1, max_length=100)
    unit_price: float = Field(ge=0)
    currency: str = Field(default="COP", min_length=3, max_length=10)
    unit_of_measure: str = Field(min_length=1, max_length=50)
    pack_quantity: int = Field(default=1, gt=0)
    price_list_date: date
    raw_row_hash: str = Field(min_length=8, max_length=128)


class ProductRead(ProductCreate):
    id: int
    created_at: datetime


class CanonicalProductCreate(StrictSchema):
    canonical_name: str = Field(min_length=2, max_length=300)
    category: str = Field(min_length=1, max_length=100)
    attributes: dict[str, Any] = Field(default_factory=dict)
    stock_quantity: int = Field(default=0, ge=0)
    min_stock: int = Field(default=0, ge=0)


class CanonicalProductRead(CanonicalProductCreate):
    id: int
    created_at: datetime
    updated_at: datetime


class ProductLinkCreate(StrictSchema):
    product_id: int = Field(gt=0)
    canonical_product_id: int = Field(gt=0)
    confidence_score: float = Field(ge=0, le=1)
    link_source: Literal["rule", "agent_suggestion", "manual_confirmation"]
    confirmed_by: str | None = Field(default=None, max_length=200)


class ProductLinkRead(ProductLinkCreate):
    id: int
    created_at: datetime


class SupplierEquivalenceCondition(StrictSchema):
    type: Literal["supplier_equivalence"]
    match: dict[str, Any] = Field(default_factory=dict)
    suppliers: list[str] = Field(min_length=2)
    action: Literal["merge_to_canonical"] = "merge_to_canonical"
    confidence: float = Field(default=1.0, ge=0, le=1)


class ExclusionCondition(StrictSchema):
    type: Literal["exclusion"]
    match: dict[str, Any] = Field(default_factory=dict)
    suppliers: list[str] = Field(default_factory=list)
    action: Literal["block_merge"] = "block_merge"
    confidence: float = Field(default=1.0, ge=0, le=1)


class PreferenceCondition(StrictSchema):
    type: Literal["preference"]
    match: dict[str, Any] = Field(default_factory=dict)
    suppliers: list[str] = Field(min_length=1)
    action: Literal["prefer_supplier"] = "prefer_supplier"
    confidence: float = Field(default=1.0, ge=0, le=1)


RuleCondition = SupplierEquivalenceCondition | ExclusionCondition | PreferenceCondition


class EquivalenceRuleCreate(StrictSchema):
    raw_prompt_text: str = Field(min_length=5, max_length=500)
    structured_condition: RuleCondition
    suppliers_involved: list[str] = Field(default_factory=list)
    is_active: bool = True
    rule_type: Literal["equivalence", "exclusion", "supplier_preference"]
    times_applied: int = Field(default=0, ge=0)

    @model_validator(mode="after")
    def synchronize_rule_type(self) -> "EquivalenceRuleCreate":
        expected = {"supplier_equivalence": "equivalence", "exclusion": "exclusion", "preference": "supplier_preference"}
        if self.rule_type != expected[self.structured_condition.type]:
            raise ValueError("rule_type no coincide con structured_condition.type")
        if not self.suppliers_involved:
            self.suppliers_involved = self.structured_condition.suppliers
        return self


class EquivalenceRuleRead(EquivalenceRuleCreate):
    id: int
    created_at: datetime


class AgentActionCreate(StrictSchema):
    tool_used: str = Field(min_length=2, max_length=200)
    input_params: dict[str, Any] = Field(default_factory=dict)
    execution_result: dict[str, Any] = Field(default_factory=dict)
    requires_confirmation: bool = False
    is_approved: bool | None = None


class AgentActionRead(AgentActionCreate):
    id: int
    timestamp: datetime