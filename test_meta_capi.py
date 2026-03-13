#!/usr/bin/env python3
"""Manual test script for Meta Conversions API integration.

Usage:
    python test_meta_capi.py                           # Test with 'superbench' client
    python test_meta_capi.py <client_id>               # Test with specific client
    python test_meta_capi.py <client_id> <test_code>   # Test with Meta test event code

The test_event_code can be found in Meta Events Manager > Test Events tab.
Using a test code ensures events appear in the test tab, not production.
"""

import sys
import time

from config import load_config, get_client_config
from meta_capi import MetaConversionsAPI
from utils import hash_phone, hash_email


def test_send_event(client_id, test_event_code=None):
    load_config()
    config = get_client_config(client_id)

    if not config:
        print(f"ERROR: Client '{client_id}' not found. Check clients.yaml and .env")
        sys.exit(1)

    meta = config["meta"]
    print(f"Client: {config.get('name', client_id)}")
    print(f"Pixel ID: {meta['pixel_id']}")
    print(f"Event Name: {meta.get('event_name', 'Lead')}")
    print(f"Test Event Code: {test_event_code or 'None (PRODUCTION!)'}")
    print()

    # Test data — use a dummy phone/email
    test_phone = "+60123456789"
    test_email = "test@example.com"

    user_data = {}
    hashed_ph = hash_phone(test_phone)
    hashed_em = hash_email(test_email)
    if hashed_ph:
        user_data["ph"] = [hashed_ph]
    if hashed_em:
        user_data["em"] = [hashed_em]

    print(f"Test phone: {test_phone} -> hashed")
    print(f"Test email: {test_email} -> hashed")
    print()

    capi = MetaConversionsAPI(meta["pixel_id"], meta["access_token"])

    event_name = meta.get("event_name", "Lead")
    event_id = f"test_{client_id}_{int(time.time())}"

    print(f"Sending {event_name} event...")
    try:
        result = capi.send_event(
            event_name=event_name,
            user_data=user_data,
            event_id=event_id,
            test_event_code=test_event_code,
        )
        print(f"SUCCESS: {result}")
    except Exception as e:
        print(f"FAILED: {e}")
        sys.exit(1)


if __name__ == "__main__":
    client = sys.argv[1] if len(sys.argv) > 1 else "superbench"
    test_code = sys.argv[2] if len(sys.argv) > 2 else None
    test_send_event(client, test_code)
