import hmac
import hashlib
import time
import logging

from meta_capi import MetaConversionsAPI
from dedup import DeduplicationCache
from utils import hash_phone, hash_email

logger = logging.getLogger(__name__)

_dedup = DeduplicationCache(ttl_seconds=10)


def verify_signature(payload_body, signature, secret):
    """Verify Chatwoot webhook HMAC-SHA256 signature.

    Args:
        payload_body: Raw request body bytes.
        signature: Value of X-Chatwoot-Signature header.
        secret: Webhook secret from client config.

    Returns:
        True if signature is valid.
    """
    if not signature or not secret:
        return False

    expected = hmac.new(
        secret.encode("utf-8"), payload_body, hashlib.sha256
    ).hexdigest()

    return hmac.compare_digest(expected, signature)


def extract_added_labels(payload):
    """Extract labels that were ADDED in this webhook event.

    Chatwoot sends changed_attributes with previous/current values:
    {"changed_attributes": {"labels": {"previous_value": [...], "current_value": [...]}}}

    Returns list of newly added labels (lowercased).
    """
    changed = payload.get("changed_attributes", {})

    # changed_attributes can be a list or dict depending on Chatwoot version
    if isinstance(changed, list):
        for attr in changed:
            if "labels" in attr:
                changed = attr
                break
        else:
            return []

    labels_change = changed.get("labels")
    if not labels_change:
        return []

    previous = set(l.lower() for l in (labels_change.get("previous_value") or []))
    current = set(l.lower() for l in (labels_change.get("current_value") or []))

    added = current - previous
    return list(added)


def extract_contact_info(payload):
    """Extract phone and email from conversation payload.

    Chatwoot puts contact info at meta.sender.phone_number and meta.sender.email.
    Also checks the contact object at the top level.

    Returns: {"phone": str|None, "email": str|None}
    """
    result = {"phone": None, "email": None}

    # Try meta.sender first
    sender = payload.get("meta", {}).get("sender", {})
    if sender:
        result["phone"] = sender.get("phone_number") or None
        result["email"] = sender.get("email") or None

    # Fallback: top-level contact
    if not result["phone"] and not result["email"]:
        contact = payload.get("contact", {})
        if contact:
            result["phone"] = contact.get("phone_number") or None
            result["email"] = contact.get("email") or None

    return result


def find_matching_trigger(added_labels, trigger_labels):
    """Case-insensitive match of added labels against trigger labels.

    Args:
        added_labels: List of newly added labels (lowercased).
        trigger_labels: Dict mapping label -> Meta event name,
                        e.g. {"appt-booked": "Lead", "sold": "Purchase"}

    Returns (matched_label, event_name) tuple or (None, None).
    """
    for label in added_labels:
        if label.lower() in trigger_labels:
            return label, trigger_labels[label.lower()]
    return None, None


def process_webhook(client_id, payload, client_config):
    """Main processing function.

    Orchestrates: check event type -> extract labels -> match triggers ->
    dedup check -> extract contact -> hash -> send to Meta.

    Returns: {"status": "sent"|"skipped"|"error", "detail": str}
    """
    event_type = payload.get("event")

    if event_type != "conversation_updated":
        return {"status": "skipped", "detail": f"Ignoring event: {event_type}"}

    # Extract newly added labels
    added_labels = extract_added_labels(payload)
    if not added_labels:
        return {"status": "skipped", "detail": "No labels added"}

    # Check source label filter (e.g. only process "meta_ads" conversations)
    source_label = client_config.get("source_label")
    if source_label:
        # Get ALL current labels on the conversation (not just added ones)
        current_labels = set()
        changed = payload.get("changed_attributes", {})
        if isinstance(changed, dict):
            labels_change = changed.get("labels", {})
            current_labels = set(
                l.lower() for l in (labels_change.get("current_value") or [])
            )
        elif isinstance(changed, list):
            for attr in changed:
                if "labels" in attr:
                    current_labels = set(
                        l.lower() for l in (attr["labels"].get("current_value") or [])
                    )
                    break
        # Also check top-level labels field
        if not current_labels:
            current_labels = set(
                l.lower() for l in (payload.get("labels") or [])
            )

        if source_label.lower() not in current_labels:
            return {
                "status": "skipped",
                "detail": f"Missing source label '{source_label}'. Current: {current_labels}",
            }

    # Check if any added label matches trigger labels
    trigger_labels = client_config.get("trigger_labels", {})
    matched_label, event_name = find_matching_trigger(added_labels, trigger_labels)
    if not matched_label:
        return {
            "status": "skipped",
            "detail": f"No trigger match. Added: {added_labels}, Triggers: {list(trigger_labels.keys())}",
        }

    # Deduplication
    conversation_id = payload.get("id") or payload.get("conversation", {}).get("id", "unknown")
    dedup_key = f"{client_id}:{conversation_id}:{matched_label}"
    if _dedup.is_duplicate(dedup_key):
        return {"status": "skipped", "detail": f"Duplicate webhook for {dedup_key}"}

    # Extract contact info
    contact = extract_contact_info(payload)
    if not contact["phone"] and not contact["email"]:
        logger.warning(
            "No contact info found for conversation %s (client: %s)",
            conversation_id,
            client_id,
        )
        return {"status": "skipped", "detail": "No contact phone or email found"}

    # Build user_data with hashed values
    user_data = {}
    if contact["phone"]:
        hashed_ph = hash_phone(contact["phone"])
        if hashed_ph:
            user_data["ph"] = [hashed_ph]
    if contact["email"]:
        hashed_em = hash_email(contact["email"])
        if hashed_em:
            user_data["em"] = [hashed_em]

    if not user_data:
        return {"status": "skipped", "detail": "Failed to hash contact data"}

    # Send to Meta CAPI
    meta_config = client_config["meta"]
    event_id = f"{client_id}_{conversation_id}_{event_name}_{int(time.time())}"

    try:
        capi = MetaConversionsAPI(meta_config["pixel_id"], meta_config["access_token"])
        result = capi.send_event(
            event_name=event_name,
            user_data=user_data,
            event_id=event_id,
        )
        logger.info(
            "Sent %s event for client=%s conversation=%s label=%s",
            event_name,
            client_id,
            conversation_id,
            matched_label,
        )
        return {
            "status": "sent",
            "detail": f"Sent {event_name} event. Meta response: {result}",
        }
    except Exception as e:
        logger.error(
            "Failed to send Meta event for client=%s conversation=%s: %s",
            client_id,
            conversation_id,
            e,
        )
        return {"status": "error", "detail": str(e)}
