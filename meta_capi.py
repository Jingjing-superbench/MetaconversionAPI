import time
import logging

import requests

logger = logging.getLogger(__name__)

BASE_URL = "https://graph.facebook.com/v18.0"


class MetaConversionsAPI:
    def __init__(self, pixel_id, access_token):
        self.pixel_id = pixel_id
        self.access_token = access_token
        self.endpoint = f"{BASE_URL}/{pixel_id}/events"

    def send_event(
        self,
        event_name,
        user_data,
        event_time=None,
        event_id=None,
        custom_data=None,
        test_event_code=None,
    ):
        """Send a conversion event to Meta Conversions API.

        Args:
            event_name: "Lead", "Purchase", or any standard/custom event.
            user_data: Dict with hashed fields, e.g. {"ph": [...], "em": [...]}.
            event_time: Unix timestamp (defaults to now).
            event_id: Unique ID for Meta-side deduplication.
            custom_data: Optional dict (e.g. {"currency": "USD", "value": 100}).
            test_event_code: Optional code from Meta Events Manager for test events.

        Returns:
            Meta API response dict.
        """
        event = {
            "event_name": event_name,
            "event_time": event_time or int(time.time()),
            "action_source": "system_generated",
            "user_data": user_data,
        }

        if event_id:
            event["event_id"] = event_id
        if custom_data:
            event["custom_data"] = custom_data

        payload = {
            "data": [event],
            "access_token": self.access_token,
        }

        if test_event_code:
            payload["test_event_code"] = test_event_code

        return self._make_request(payload)

    def _make_request(self, payload):
        """POST to Meta Graph API."""
        logger.info(
            "Sending event to Meta CAPI: %s -> %s",
            payload["data"][0]["event_name"],
            self.endpoint,
        )

        try:
            response = requests.post(self.endpoint, json=payload, timeout=30)
            response.raise_for_status()
            result = response.json()
            logger.info("Meta CAPI response: %s", result)
            return result
        except requests.exceptions.RequestException as e:
            logger.error("Meta CAPI request failed: %s", e)
            if hasattr(e, "response") and e.response is not None:
                logger.error("Response body: %s", e.response.text)
            raise
