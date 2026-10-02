from datetime import datetime
from typing import Annotated, Any, Literal

from pydantic import Field, field_validator, model_validator

from app.models.enums import RuleType
from app.schemas.common import Schema


class EquivalenceCondition(Schema):
    type: Literal["equivalence"]
    match: dict[str, Any] = Field(min_length=1)
    suppliers: list[str] = Field(min_length=2)
    action: Literal["merge_to_canonical"] = "merge_to_canonical"


class ExclusionCondition(Schema):
    type: Literal["exclusion"]
    match: dict[str, Any] = Field(min_length=1)
    suppliers: list[str] = Field(min_length=2)
    action: Literal["block_merge"] = "block_merge"


class PurchasePreferenceCondition(Schema):
    type: Literal["purchase_preference"]
    match: dict[str, Any] = Field(min_length=1)
    suppliers: list[str] = Field(min_length=1)
    action: Literal["prefer_supplier"] = "prefer_supplier"


RuleCondition = Annotated[
    EquivalenceCondition | ExclusionCondition | PurchasePreferenceCondition,
    Field(discriminator="type"),
]


class EquivalenceRuleCreate(Schema):
    original_text: str = Field(min_length=1)
    rule_type: RuleType
    condition_json: RuleCondition
    suppliers: list[Any] | None = None
    active: bool = True
    times_applied: int = Field(default=0, ge=0)

    @field_validator("rule_type", mode="before")
    @classmethod
    def known_rule_type(cls, value: Any) -> Any:
        try:
            return RuleType(value)
        except (TypeError, ValueError) as exc:
            accepted = ", ".join(item.value for item in RuleType)
            raise ValueError(f"Tipo de regla desconocido. Valores permitidos: {accepted}.") from exc

    @model_validator(mode="after")
    def type_matches_condition(self) -> "EquivalenceRuleCreate":
        if self.rule_type.value != self.condition_json.type:
            raise ValueError("rule_type debe coincidir con condition_json.type.")
        return self


class EquivalenceRuleUpdate(Schema):
    original_text: str | None = Field(default=None, min_length=1)
    rule_type: RuleType | None = None
    condition_json: RuleCondition | None = None
    suppliers: list[Any] | None = None
    active: bool | None = None
    times_applied: int | None = Field(default=None, ge=0)


class EquivalenceRuleRead(EquivalenceRuleCreate):
    id: int
    created_at: datetime