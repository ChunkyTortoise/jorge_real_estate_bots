from locust import HttpUser, User, task, between
import base64
import hashlib
import hmac
import json
import os
import random

try:
    from websocket import create_connection
    WEBSOCKET_AVAILABLE = True
except Exception:
    WEBSOCKET_AVAILABLE = False

try:
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import padding
    CRYPTO_AVAILABLE = True
except Exception:
    CRYPTO_AVAILABLE = False


class JorgeBotsUser(HttpUser):
    wait_time = between(0.5, 2.5)

    def on_start(self):
        token = os.getenv("LOADTEST_JWT")
        self.auth_headers = {"Authorization": f"Bearer {token}"} if token else {}
        self.webhook_secret = os.getenv("GHL_WEBHOOK_SECRET")
        self.webhook_private_key = os.getenv("GHL_WEBHOOK_PRIVATE_KEY")

    def _sign_webhook(self, payload_bytes: bytes) -> str | None:
        if self.webhook_private_key and CRYPTO_AVAILABLE:
            try:
                private_key = serialization.load_pem_private_key(
                    self.webhook_private_key.encode(),
                    password=None,
                )
                signature = private_key.sign(
                    payload_bytes,
                    padding.PKCS1v15(),
                    hashes.SHA256(),
                )
                return base64.b64encode(signature).decode()
            except Exception:
                return None

        if self.webhook_secret:
            digest = hmac.new(self.webhook_secret.encode(), payload_bytes, hashlib.sha256).hexdigest()
            return f"sha256={digest}"

        return None

    @task(3)
    def lead_webhook(self):
        payload = {
            "id": f"lead_{random.randint(1000, 9999)}",
            "name": "Test Lead",
            "email": "lead@example.com",
            "phone": "555-111-2222",
            "source": "locust",
            "tags": ["Dallas"],
        }
        payload_json = json.dumps(payload)
        payload_bytes = payload_json.encode()
        signature = self._sign_webhook(payload_bytes)
        headers = dict(self.auth_headers)
        if signature:
            headers["x-wh-signature"] = signature
        headers.setdefault("Content-Type", "application/json")
        self.client.post("/ghl/webhook/new-lead", data=payload_json, headers=headers)

    @task(2)
    def analyze_lead(self):
        payload = {
            "contact_id": f"lead_{random.randint(1000, 9999)}",
            "location_id": "loc_1",
            "message": "Looking for a 3 bed home in Dallas around 400k",
            "contact_data": {"name": "Test Lead"},
        }
        self.client.post("/analyze-lead", json=payload, headers=self.auth_headers)

    @task(2)
    def seller_process(self):
        payload = {
            "contact_id": f"seller_{random.randint(1000, 9999)}",
            "location_id": "loc_1",
            "message": "House needs minor repairs",
            "contact_info": {"name": "Seller Test"},
        }
        self.client.post("/api/jorge-seller/process", json=payload, headers=self.auth_headers)

    @task(2)
    def buyer_process(self):
        payload = {
            "contact_id": f"buyer_{random.randint(1000, 9999)}",
            "location_id": "loc_1",
            "message": "Looking for 3 beds 2 baths in Plano under 500k",
            "contact_info": {"name": "Buyer Test"},
        }
        self.client.post("/api/jorge-buyer/process", json=payload, headers=self.auth_headers)

    @task(1)
    def buyer_matches(self):
        contact_id = f"buyer_{random.randint(1000, 9999)}"
        self.client.get(f"/api/jorge-buyer/matches/{contact_id}?location_id=loc_1", headers=self.auth_headers)


class DashboardWebsocketUser(User):
    wait_time = between(2, 5)

    def on_start(self):
        self.ws = None
        if not WEBSOCKET_AVAILABLE:
            return

        token = os.getenv("LOADTEST_JWT")
        if not token:
            return

        base_url = os.getenv("LEAD_BOT_WS_URL", "ws://localhost:8001/ws/dashboard")
        client_id = f"locust_{random.randint(1000, 9999)}"
        url = f"{base_url}?token={token}&client_id={client_id}"
        try:
            self.ws = create_connection(url, timeout=5)
        except Exception:
            self.ws = None

    @task
    def websocket_ping(self):
        if not self.ws:
            return
        try:
            self.ws.send("ping")
            self.ws.recv()
        except Exception:
            pass

    def on_stop(self):
        if self.ws:
            try:
                self.ws.close()
            except Exception:
                pass
