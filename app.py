import logging

from flask import Flask, request, jsonify

from config import load_config, get_client_config, get_all_client_ids
from webhook_handler import verify_signature, process_webhook

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Load config at startup
load_config()


@app.route("/health", methods=["GET"])
def health():
    """Health check endpoint."""
    client_ids = get_all_client_ids()
    return jsonify({
        "status": "ok",
        "clients": client_ids,
        "client_count": len(client_ids),
    })


@app.route("/webhook/<client_id>", methods=["POST"])
def webhook(client_id):
    """Chatwoot webhook endpoint.

    Always returns 200 to prevent Chatwoot retry storms.
    """
    client_config = get_client_config(client_id)
    if not client_config:
        logger.warning("Unknown client_id: %s", client_id)
        return jsonify({"status": "error", "detail": "Unknown client"}), 404

    # Verify signature
    signature = request.headers.get("X-Chatwoot-Signature", "")
    secret = client_config.get("chatwoot", {}).get("webhook_secret", "")
    if not verify_signature(request.get_data(), signature, secret):
        logger.warning("Invalid signature for client: %s", client_id)
        return jsonify({"status": "error", "detail": "Invalid signature"}), 401

    # Process webhook
    payload = request.get_json(silent=True) or {}
    result = process_webhook(client_id, payload, client_config)

    logger.info("Webhook result for %s: %s", client_id, result)
    return jsonify(result), 200


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
