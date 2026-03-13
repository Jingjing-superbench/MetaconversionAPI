import os
import re
import logging

import yaml
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

_clients = {}


def _resolve_env_vars(value):
    """Recursively resolve ${ENV_VAR} placeholders in config values."""
    if isinstance(value, str):
        return re.sub(
            r"\$\{(\w+)\}",
            lambda m: os.environ.get(m.group(1), ""),
            value,
        )
    if isinstance(value, dict):
        return {k: _resolve_env_vars(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_resolve_env_vars(item) for item in value]
    return value


def _validate_client(client_id, config):
    """Validate required keys exist for a client config."""
    errors = []
    chatwoot = config.get("chatwoot", {})
    meta = config.get("meta", {})

    if not chatwoot.get("webhook_secret"):
        errors.append("chatwoot.webhook_secret")
    if not meta.get("pixel_id"):
        errors.append("meta.pixel_id")
    if not meta.get("access_token"):
        errors.append("meta.access_token")
    if not config.get("trigger_labels"):
        errors.append("trigger_labels")

    if errors:
        logger.warning(
            "Client '%s' missing required config: %s", client_id, ", ".join(errors)
        )
        return False
    return True


def load_config(yaml_path=None):
    """Load .env and clients.yaml. Resolve env vars, validate, store in module."""
    global _clients

    load_dotenv()

    if yaml_path is None:
        yaml_path = os.path.join(os.path.dirname(__file__), "clients.yaml")

    with open(yaml_path, "r", encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}

    resolved = _resolve_env_vars(raw)

    _clients = {}
    for client_id, config in resolved.items():
        # Lowercase trigger labels for case-insensitive matching
        labels = config.get("trigger_labels", [])
        config["trigger_labels"] = [l.lower() for l in labels]

        # Default event_name to "Lead"
        meta = config.get("meta", {})
        if not meta.get("event_name"):
            meta["event_name"] = "Lead"
        config["meta"] = meta

        if _validate_client(client_id, config):
            _clients[client_id] = config
            logger.info("Loaded client: %s (%s)", client_id, config.get("name", ""))
        else:
            logger.warning("Skipping client '%s' due to missing config", client_id)

    logger.info("Loaded %d client(s): %s", len(_clients), list(_clients.keys()))
    return _clients


def get_client_config(client_id):
    """Get resolved config for a specific client."""
    return _clients.get(client_id)


def get_all_client_ids():
    """Get list of all loaded client IDs."""
    return list(_clients.keys())
