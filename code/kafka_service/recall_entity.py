import re
from typing import Any

# Same reason types as the HW1 form (DOMAIN_SCHEMA.md, field 5).
RECALL_TYPES = (
    "Packaging / Seal Failure",
    "Contamination",
    "Undeclared Allergen",
    "Spoiled or Quality Issue",
)
RECALL_CODE_PATTERN = re.compile(r"^REC-[0-9]{4}$")
MIN_DESCRIPTION_CHARS = 26

REQUIRED_TEXT_FIELDS = {
    "product_name": 255,
    "supplier": 255,
    "description": 2000,
}
REQUIRED_FIELDS = (
    "product_name",
    "supplier",
    "recall_code",
    "recall_type",
    "description",
    "affected_units",
)


def validate_recall_fields(data: Any) -> tuple[dict | None, str | None]:
    """Return (cleaned recall fields, None) or (None, clean error message)."""
    if not isinstance(data, dict):
        return None, "data must be a JSON object"

    # Submitter email is a user-specific field, so it is not part of the Kafka entity.
    unexpected = sorted(set(data) - set(REQUIRED_FIELDS))
    if unexpected:
        return None, f"Unexpected field(s): {', '.join(unexpected)}"

    missing = [name for name in REQUIRED_FIELDS if name not in data]
    if missing:
        return None, f"Missing required field(s): {', '.join(missing)}"

    cleaned: dict[str, Any] = {}
    for name, max_length in REQUIRED_TEXT_FIELDS.items():
        value = data[name]
        if not isinstance(value, str) or not value.strip():
            return None, f"{name} must be a non-empty string"
        value = value.strip()
        if len(value) > max_length:
            return None, f"{name} must be at most {max_length} characters"
        cleaned[name] = value

    if len(cleaned["description"]) < MIN_DESCRIPTION_CHARS:
        return None, "description must be more than 25 characters"

    recall_code = data["recall_code"]
    if not isinstance(recall_code, str) or not RECALL_CODE_PATTERN.match(recall_code.strip()):
        return None, "recall_code must match REC-#### (for example REC-0101)"
    cleaned["recall_code"] = recall_code.strip()

    recall_type = data["recall_type"]
    if recall_type not in RECALL_TYPES:
        return None, f"recall_type must be one of: {', '.join(RECALL_TYPES)}"
    cleaned["recall_type"] = recall_type

    affected_units = data["affected_units"]
    if (
        isinstance(affected_units, bool)
        or not isinstance(affected_units, int)
        or affected_units < 0
    ):
        return None, "affected_units must be an integer >= 0"
    cleaned["affected_units"] = affected_units

    return cleaned, None
