"""Durable, overlap-safe staff notification delivery (never patient-facing)."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from telegram.error import RetryAfter

from services.database import execute_returning_one, fetch_one_sql, transaction
from services.healthcare.access import ClinicAccessError, Scope
from services.healthcare.service import audit, get_entity, now

logger = logging.getLogger(__name__)
MESSAGES = {
    "before_due": "یادآوری داخلی کلینیک: یک اقدام شما تا یک ساعت دیگر موعد دارد. /clinic",
    "at_due": "یادآوری داخلی کلینیک: موعد یک اقدام شما رسیده است. /clinic",
    "overdue": "پیگیری داخلی کلینیک: یک اقدام شما بیش از یک روز عقب افتاده است. /clinic",
}


async def deliver(bot, bot_key: str, *, at=None, batch_size=30):
    stamp = (at or datetime.now(timezone.utc)).strftime("%Y-%m-%dT%H:%M:%SZ")
    results = {"sent": 0, "failed": 0, "cancelled": 0}
    for _ in range(max(1, min(batch_size, 100))):
        # SQLite serializes this claim across loops and processes. A crash after
        # Telegram accepted a message leaves 'sending' for operator review; it
        # is not automatically resent because Telegram has no idempotency key.
        row = await execute_returning_one(
            """UPDATE clinic_notifications SET status='sending',attempt=attempt+1
            WHERE id=(SELECT n.id FROM clinic_notifications n JOIN clinic_organizations o ON o.id=n.organization_id
            WHERE n.status='pending' AND n.send_at<=? AND o.bot_key=? AND o.status='active'
            ORDER BY n.send_at,n.id LIMIT 1) AND status='pending' RETURNING *""",
            (stamp, bot_key),
        )
        if not row:
            break
        scope = Scope(row["organization_id"], row["recipient_id"])
        try:
            task = await get_entity(scope, "tasks", row["task_id"])
            if (
                task["status"] in {"done", "cancelled"}
                or task["assignee_id"] != row["recipient_id"]
            ):
                raise ClinicAccessError("forbidden")
            await bot.send_message(
                chat_id=row["recipient_id"], text=MESSAGES[row["kind"]]
            )
        except ClinicAccessError:
            await _finish(row, "cancelled")
            results["cancelled"] += 1
        except RetryAfter as exc:
            if row["attempt"] < 3:
                delay = (
                    exc.retry_after.total_seconds()
                    if isinstance(exc.retry_after, timedelta)
                    else float(exc.retry_after)
                )
                retry_at = (
                    datetime.now(timezone.utc) + timedelta(seconds=max(1, delay))
                ).strftime("%Y-%m-%dT%H:%M:%SZ")
                await transaction(
                    [
                        (
                            "UPDATE clinic_notifications SET status='pending',send_at=? WHERE id=? AND status='sending'",
                            (retry_at, row["id"]),
                        )
                    ]
                )
            else:
                await _finish(row, "failed")
                results["failed"] += 1
        except Exception as exc:  # noqa: BLE001 -- persist ambiguous delivery without leaking exception text
            # Ambiguous timeouts cannot be retried automatically without risking
            # duplicate delivery. No task titles, patient info, or exception body.
            logger.warning("clinic_notification_failed type=%s", type(exc).__name__)
            await _finish(row, "failed")
            results["failed"] += 1
        else:
            await _finish(row, "sent")
            results["sent"] += 1
    return results


async def _finish(row, status):
    system = Scope(row["organization_id"], "system")
    await transaction(
        [
            (
                "UPDATE clinic_notifications SET status=?,sent_at=? WHERE id=? AND status='sending'",
                (status, now() if status == "sent" else None, row["id"]),
            ),
            audit(
                system,
                row["branch_id"],
                "notification." + status,
                "task",
                row["task_id"],
            ),
        ]
    )


async def staff_notification_job(context):
    profile = context.application.bot_data.get("bot_config")
    if (
        not profile
        or not profile.feature_enabled("healthcare")
        or not profile.feature_enabled("clinic_staff_reminders")
    ):
        return
    # Profile configuration remains authoritative at execution time.
    await deliver(context.bot, profile.key)


async def delivery_state(scope: Scope):
    await scope.predicate("reports.view")
    return await fetch_one_sql(
        "SELECT SUM(status='sending') AS ambiguous,SUM(status='failed') AS failed FROM clinic_notifications WHERE organization_id=?",
        (scope.organization_id,),
    )
