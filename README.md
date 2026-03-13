# Meta Conversion API Webhook Server

Listens for Chatwoot conversation label changes and sends conversion events to Meta Conversions API. When an agent labels a conversation (e.g., "Confirmed"), the server fires a Lead/Purchase event back to Meta so ad delivery can be optimized for downstream conversions.

## Architecture

```
Agent adds label in Chatwoot
        |
        v
Chatwoot webhook (conversation_updated)
        |
        v
POST /webhook/<client_id>
        |
        v
Verify signature -> Detect trigger label -> Dedup check -> Hash contact -> Meta CAPI
```

## Setup

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure secrets

```bash
cp .env.example .env
# Edit .env with your actual secrets
```

### 3. Configure clients

Edit `clients.yaml` to add/modify client configurations:

```yaml
superbench:
  name: "Superbench"
  chatwoot:
    base_url: "https://app.chatwoot.com"
    account_id: 1
    webhook_secret: "${SUPERBENCH_CHATWOOT_WEBHOOK_SECRET}"
  meta:
    pixel_id: "${SUPERBENCH_META_PIXEL_ID}"
    access_token: "${SUPERBENCH_META_ACCESS_TOKEN}"
    event_name: "Lead"  # or "Purchase"
  trigger_labels:
    - "confirmed"
    - "appointment booked"
```

- Secrets use `${ENV_VAR}` placeholders, resolved from `.env` at startup
- `trigger_labels` are case-insensitive
- `event_name` defaults to "Lead" if omitted

### 4. Configure Chatwoot webhook

In your Chatwoot instance:
1. Go to Settings > Integrations > Webhooks
2. Add webhook URL: `https://your-server.com/webhook/superbench`
3. Subscribe to: `conversation_updated`
4. Save the webhook secret — add it to your `.env`

### 5. Run the server

```bash
python app.py
```

Server starts on port 5000. Health check: `GET /health`

## Adding a New Client

1. Add a new section to `clients.yaml` with a unique key (this becomes the client_id)
2. Add the client's secrets to `.env` following the naming convention: `{CLIENTNAME}_{SERVICE}_{KEY}`
3. Configure the webhook URL in the client's Chatwoot: `https://your-server.com/webhook/<client_id>`

## Testing

### Test Meta CAPI connection

```bash
# Uses test event code so events don't affect production
python test_meta_capi.py superbench TEST12345

# Without test code (events go to production!)
python test_meta_capi.py superbench
```

Get your test event code from Meta Events Manager > Your Pixel > Test Events tab.

### Simulate a webhook locally

```bash
curl -X POST http://localhost:5000/webhook/superbench \
  -H "Content-Type: application/json" \
  -H "X-Chatwoot-Signature: <hmac_signature>" \
  -d '{
    "event": "conversation_updated",
    "id": 42,
    "changed_attributes": {
      "labels": {
        "previous_value": [],
        "current_value": ["confirmed"]
      }
    },
    "meta": {
      "sender": {
        "phone_number": "+60123456789",
        "email": "lead@example.com"
      }
    }
  }'
```

## Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Health check, lists loaded clients |
| POST | `/webhook/<client_id>` | Chatwoot webhook receiver |
