"""Compare saved Brain context and card body, offline and without echoing data.

This operator/test diagnostic is not a gateway hook and does not authenticate
the supplied context. It checks a transfer, not customer intent or property
identity. Inputs must belong to the same audited conversation.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

CONFIRMED = {"status", "ad_id", "ad_name", "campaign_id", "campaign_name"}
RAW_KEYS = {
    "external_ad_reply",
    "external_ad_reply_raw_json",
    "ctwaClid",
    "ctwa_clid",
    "sourceUrl",
    "sourceId",
    "thumbnail",
    "thumbnailUrl",
    "originalImageUrl",
}


def _projection(context: object) -> list[dict]:
    if not isinstance(context, dict):
        raise ValueError
    if context.get("status") == "unavailable":
        return []
    if context.get("status") != "ok":
        raise ValueError
    contact, events = context.get("contact"), context.get("events")
    if not isinstance(contact, dict) or not isinstance(events, list):
        raise ValueError
    if not isinstance(contact.get("phone_e164"), str) or not re.fullmatch(
        r"[1-9][0-9]{6,14}", contact["phone_e164"]
    ):
        raise ValueError
    result, seen = [], set()
    for event in events:
        if not isinstance(event, dict) or event.get("transport_kind") not in {
            "ctwa_candidate",
            "ordinary_inbound",
        }:
            raise ValueError
        if event["transport_kind"] != "ctwa_candidate":
            continue
        event_id = event.get("event_id")
        if (
            not isinstance(event_id, str)
            or not re.fullmatch(r"waevt_[A-Za-z0-9_-]{1,128}", event_id)
            or event_id in seen
        ):
            raise ValueError
        seen.add(event_id)
        source = event.get("source_app")
        if source is not None and not isinstance(source, str):
            raise ValueError
        meta = event.get("meta_attribution")
        if meta is not None:
            if not isinstance(meta, dict):
                raise ValueError
            status = meta.get("status")
            if status == "confirmed":
                if set(meta) != CONFIRMED or not all(
                    isinstance(v, str) and v for v in meta.values()
                ):
                    raise ValueError
                if not all(
                    re.fullmatch(r"[0-9]{1,64}", meta[field])
                    for field in ("ad_id", "campaign_id")
                ):
                    raise ValueError
            elif status in {"pending", "unavailable"}:
                if set(meta) not in ({"status"}, {"status", "reason"}) or (
                    "reason" in meta and not isinstance(meta["reason"], str)
                ):
                    raise ValueError
            else:
                raise ValueError
        result.append(
            {"event_id": event_id, "source_app": source, "meta_attribution": meta}
        )
    return result


def _has_raw_field(value: object) -> bool:
    if isinstance(value, dict):
        return bool(RAW_KEYS.intersection(value)) or any(
            _has_raw_field(v) for v in value.values()
        )
    if isinstance(value, list):
        return any(_has_raw_field(v) for v in value)
    return False


def check_handoff(context: object, card: object) -> list[str]:
    """Check the JSON-decoded card body against the same-contact Brain result.

    Only supplied identity fields are checked. A worker card may omit phone when
    its authorized work already has a client ID. No state, network or DB access.
    """
    try:
        expected = _projection(context)
    except (ValueError, TypeError):
        return ["invalid_context"]
    if not isinstance(card, dict) or not isinstance(card.get("contexto"), dict):
        return ["invalid_card"]
    errors = []
    failed = context["status"] == "unavailable"
    if card["contexto"].get("context_resolution_failed") is not failed:
        errors.append("resolution_flag_mismatch")
    actual = card["contexto"].get("ctwa_attributions")
    # Canonical JSON preserves types and list multiplicity; order is not meaning.
    if not isinstance(actual, list) or sorted(
        json.dumps(x, sort_keys=True) for x in actual
    ) != sorted(json.dumps(x, sort_keys=True) for x in expected):
        errors.append("attribution_mismatch")
    contact = card.get("contact", {})
    if not isinstance(contact, dict):
        errors.append("invalid_card")
    elif "phone_e164" in contact:
        if failed:
            errors.append("unverified_contact")
        elif contact["phone_e164"] != context["contact"]["phone_e164"]:
            errors.append("contact_mismatch")
    if _has_raw_field(card):
        errors.append("raw_field_in_card")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--context",
        type=Path,
        required=True,
        help="Saved conversation_context result as JSON",
    )
    parser.add_argument(
        "--card",
        type=Path,
        required=True,
        help="Card body only, decoded to a JSON object",
    )
    args = parser.parse_args()
    try:
        context = json.loads(args.context.read_text(encoding="utf-8"))
        card = json.loads(args.card.read_text(encoding="utf-8"))
        errors = check_handoff(context, card)
    except (OSError, ValueError, TypeError, RecursionError):
        print("FAIL: invalid_input")
        return 2
    if errors:
        print("FAIL: " + ",".join(errors))
        return 1
    print("PASS: CTWA_HANDOFF")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
