"""Healthcare terminology adapters over the generic operational model."""

from __future__ import annotations


def to_healthcare_record(row: dict | None) -> dict | None:
    if row is None:
        return None
    item = dict(row)
    aliases = {
        "workspace_id": "organization_id",
        "unit_id": "branch_id",
        "reference_id": "patient_id",
        "primary_owner_user_id": "primary_doctor_user_id",
        "contact_value": "phone",
    }
    for generic, healthcare in aliases.items():
        if generic in item and healthcare not in item:
            item[healthcare] = item[generic]
    if "case_type" in item and "external_reference" in item:
        item.setdefault("appointment_reference", item["external_reference"])
    return item


def to_healthcare_payload(value):
    if isinstance(value, dict):
        mapped = to_healthcare_record(value)
        return {key: to_healthcare_payload(item) for key, item in mapped.items()}
    if isinstance(value, list):
        return [to_healthcare_payload(item) for item in value]
    return value
