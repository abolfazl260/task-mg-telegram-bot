"""Bounded CSV onboarding and permission-scoped, auditable operational exports."""

from __future__ import annotations

import csv
import io
import sqlite3

from services.database import fetch_all_sql, fetch_one_sql, get_db, transaction
from services.healthcare.access import ClinicAccessError, Scope
from services.healthcare.service import audit, new_id, now, require_staff, text

COLUMNS = {"external_id", "display_name", "phone", "doctor_id", "branch_id"}
MAX_ROWS = 500


async def preview_patients(scope: Scope, content: str):
    if not isinstance(content, str) or len(content.encode("utf-8")) > 512_000:
        raise ValueError("import_too_large")
    reader = csv.DictReader(io.StringIO(content.lstrip("\ufeff")))
    if (
        not reader.fieldnames
        or not {"external_id", "display_name", "branch_id"}.issubset(reader.fieldnames)
        or set(reader.fieldnames) - COLUMNS
        or len(reader.fieldnames) != len(set(reader.fieldnames))
    ):
        raise ValueError("invalid_csv_headers")
    rows, seen = [], set()
    for number, row in enumerate(reader, 2):
        if len(rows) >= MAX_ROWS:
            raise ValueError("import_too_large")
        result = {"line": number, "status": "valid", "error": None, "data": None}
        try:
            if None in row or any(value is None for value in row.values()):
                raise ValueError("invalid_csv_row")
            item = {
                "external_id": text(row["external_id"], max_length=100),
                "display_name": text(row["display_name"], max_length=200),
                "unit_id": text(row["branch_id"], max_length=100),
                "phone": text(row.get("phone", ""), max_length=50, required=False),
                "doctor_id": text(
                    row.get("doctor_id", ""), max_length=100, required=False
                ),
            }
            await scope.branch(item["unit_id"], "patients.manage")
            if item["doctor_id"]:
                await require_staff(
                    scope, item["unit_id"], item["doctor_id"], doctor=True
                )
            if item["external_id"] in seen:
                raise ValueError("duplicate_in_file")
            seen.add(item["external_id"])
            # Check duplicates only within branches the actor can read, avoiding
            # a duplicate error that reveals another branch's patient reference.
            pred, args = await scope.predicate("patients.view")
            duplicate = await fetch_one_sql(
                f"SELECT e.id,e.unit_id FROM reference_entities e WHERE {pred} AND e.external_reference=?",  # nosec B608
                args + (item["external_id"],),
            )  # nosec B608
            if duplicate:
                if duplicate["unit_id"] != item["unit_id"]:
                    raise ValueError("conflicting_branch")
                result["status"] = "duplicate"
            result["data"] = item
        except (ClinicAccessError, ValueError):
            result.update(status="invalid", error="invalid_row_or_scope")
        rows.append(result)
    return {
        "rows": rows,
        "valid": sum(r["status"] == "valid" for r in rows),
        "duplicates": sum(r["status"] == "duplicate" for r in rows),
        "invalid": sum(r["status"] == "invalid" for r in rows),
    }


async def import_patients(scope: Scope, content: str, *, confirmed: bool):
    if confirmed is not True:
        raise ValueError("confirmation_required")
    # Never trust a client-supplied preview or parsed row: revalidate source CSV.
    preview = await preview_patients(scope, content)
    if preview["invalid"]:
        raise ValueError("invalid_import_rows")
    db = await get_db()
    imported, duplicates = 0, preview["duplicates"]
    async with db.lock:
        await db.conn.execute("BEGIN IMMEDIATE")
        try:
            for row in preview["rows"]:
                if row["status"] == "duplicate":
                    continue
                item, pid, stamp = row["data"], new_id(), now()
                try:
                    await db.conn.execute(
                        "INSERT INTO reference_entities(id,workspace_id,unit_id,reference_type,external_reference,display_name,contact_value,primary_owner_user_id,created_at,updated_at) VALUES(?,?,?,'patient',?,?,?,?,?,?,?)",
                        (
                            pid,
                            scope.workspace_id,
                            item["unit_id"],
                            item["external_id"],
                            item["display_name"],
                            item["phone"],
                            item["doctor_id"] or None,
                            stamp,
                            stamp,
                        ),
                    )
                except sqlite3.IntegrityError:
                    # Also handles overlapping imports. Cross-branch conflicts
                    # are generic and roll back the entire import.
                    existing = await fetch_one_sql(
                        "SELECT unit_id FROM reference_entities WHERE workspace_id=? AND external_reference=?",
                        (scope.workspace_id, item["external_id"]),
                    )
                    if not existing or existing["unit_id"] != item["unit_id"]:
                        raise ValueError("import_conflict") from None
                    duplicates += 1
                    continue
                sql, args = audit(
                    scope, item["unit_id"], "patient.imported", "patient", pid
                )
                await db.conn.execute(sql, args)
                imported += 1
            await db.conn.commit()
        except BaseException:
            await db.conn.rollback()
            raise
    return {"imported": imported, "duplicates": duplicates}


def _safe_cell(value):
    result = str(value or "")
    # Neutralize spreadsheet formulas on export, including whitespace prefixes.
    if result.lstrip().startswith(("=", "+", "-", "@")) or result.startswith(
        ("\t", "\r", "\n")
    ):
        return "'" + result
    return result


async def export_operations(scope: Scope, kind: str, *, unit_id=None):
    allowed = {
        "tasks": (
            "tasks",
            (
                "id",
                "case_id",
                "reference_id",
                "assignee_id",
                "status",
                "deadline",
                "outcome_id",
            ),
        ),
        "followups": (
            "followups",
            (
                "id",
                "case_id",
                "reference_id",
                "owner_user_id",
                "due_at",
                "attempt_number",
                "status",
                "outcome_id",
                "completed_at",
            ),
        ),
        "cases": (
            "cases",
            (
                "id",
                "reference_id",
                "owner_user_id",
                "primary_owner_user_id",
                "status",
                "current_stage",
                "expected_at",
                "next_action_task_id",
            ),
        ),
        "outcomes": (
            "outcomes",
            ("id", "key", "requires_next_action", "is_terminal"),
        ),
    }
    if kind not in allowed:
        raise ValueError("invalid_export")
    table, columns = allowed[kind]
    pred, params = await scope.predicate("exports.create")
    if kind == "outcomes":
        # No patient data in the tenant's outcome dictionary.
        pred, params = "e.workspace_id=?", (scope.workspace_id,)
    elif unit_id:
        pred += " AND e.unit_id=?"
        params += (unit_id,)
    rows = await fetch_all_sql(
        f"SELECT {','.join('e.' + col for col in columns)} FROM {table} e WHERE {pred} ORDER BY e.id LIMIT 5001",  # nosec B608
        params,
    )  # nosec B608
    if len(rows) > 5000:
        raise ValueError("export_limit_exceeded")
    output = io.StringIO(newline="")
    writer = csv.writer(output)
    writer.writerow(columns)
    writer.writerows([_safe_cell(row[col]) for col in columns] for row in rows)
    await transaction(
        [
            audit(
                scope,
                unit_id if kind != "outcomes" else None,
                "export.created",
                kind,
                new_id(),
            )
        ]
    )
    return {
        "csv": output.getvalue(),
        "encoding": "utf-8",
        "dates": "ISO 8601 UTC",
        "rows": len(rows),
    }
