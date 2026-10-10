"""Reusable, explicit conversational-flow state transitions.

The caller owns its domain-specific draft keys and validates its domain data.
Only the named flow is cleared, so unrelated Telegram user_data survives.
"""
from __future__ import annotations

from collections.abc import MutableMapping


def clear_flow(
    state: MutableMapping,
    *,
    step_key: str,
    flow_key: str,
    flow_name: str,
    draft_keys: tuple[str, ...] = (),
) -> bool:
    """Discard this flow's draft, without clearing another active flow."""
    if state.get(flow_key) != flow_name:
        return False
    for key in (*draft_keys, step_key, flow_key):
        state.pop(key, None)
    return True


def start_flow(
    state: MutableMapping,
    *,
    step_key: str,
    flow_key: str,
    flow_name: str,
    initial_step: str,
    draft_keys: tuple[str, ...] = (),
    initial_values: dict | None = None,
) -> None:
    """Start/restart a named flow, clearing only its previous draft fields."""
    for key in (*draft_keys, step_key, flow_key):
        state.pop(key, None)
    state.update(initial_values or {})
    state[flow_key] = flow_name
    state[step_key] = initial_step


def has_step(
    state: MutableMapping,
    *,
    step_key: str,
    flow_key: str,
    flow_name: str,
    step: str,
    required: tuple[str, ...] = (),
) -> bool:
    """Require the named flow, expected step and non-empty saved prerequisites."""
    return (
        state.get(flow_key) == flow_name
        and state.get(step_key) == step
        and all(key in state and state[key] not in (None, "") for key in required)
    )
