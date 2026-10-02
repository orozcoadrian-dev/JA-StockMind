from enum import Enum


class ImportStatus(str, Enum):
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class Origin(str, Enum):
    RULE = "rule"
    AGENT_SUGGESTION = "agent_suggestion"
    MANUAL = "manual"


class LinkStatus(str, Enum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    REJECTED = "rejected"


class RuleType(str, Enum):
    EQUIVALENCE = "equivalence"
    EXCLUSION = "exclusion"
    PURCHASE_PREFERENCE = "purchase_preference"