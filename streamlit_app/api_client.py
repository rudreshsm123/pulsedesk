import base64
import json
import os
import uuid

import requests

API_BASE_URL = os.environ.get("PULSEDESK_API_URL", "http://localhost:8000/api/v1")


class APIError(Exception):
    def __init__(self, status_code: int, detail: str):
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail


def _handle(response: requests.Response) -> dict | list | None:
    if response.status_code >= 400:
        try:
            detail = response.json().get("detail", response.text)
        except ValueError:
            detail = response.text
        raise APIError(response.status_code, str(detail))
    if not response.content:
        return None
    return response.json()


def _auth_headers(access_token: str) -> dict:
    return {"Authorization": f"Bearer {access_token}"}


def _decode_token_payload(access_token: str) -> dict:
    """Decodes the JWT payload client-side (no signature verification) purely to pick
    what UI to show. This is not a security boundary: the API independently enforces
    real authorization on every request, so a tampered token here could only ever
    change which buttons render locally, never what the backend actually allows."""
    payload_segment = access_token.split(".")[1]
    padded = payload_segment + "=" * (-len(payload_segment) % 4)
    return json.loads(base64.urlsafe_b64decode(padded))


def decode_role_from_token(access_token: str) -> str:
    return _decode_token_payload(access_token)["role"]


def decode_user_id_from_token(access_token: str) -> str:
    return _decode_token_payload(access_token)["sub"]


def register(email: str, password: str) -> dict:
    return _handle(
        requests.post(f"{API_BASE_URL}/auth/register", json={"email": email, "password": password})
    )


def login(email: str, password: str) -> dict:
    return _handle(
        requests.post(f"{API_BASE_URL}/auth/login", json={"email": email, "password": password})
    )


def create_ticket(access_token: str, subject: str, body: str) -> dict:
    return _handle(
        requests.post(
            f"{API_BASE_URL}/tickets",
            json={"subject": subject, "body": body},
            headers={**_auth_headers(access_token), "Idempotency-Key": str(uuid.uuid4())},
        )
    )


def list_tickets(access_token: str, status: str | None, priority: str | None) -> list[dict]:
    params = {k: v for k, v in {"status": status, "priority": priority}.items() if v}
    data = _handle(
        requests.get(f"{API_BASE_URL}/tickets", params=params, headers=_auth_headers(access_token))
    )
    return data["items"]


def get_ticket(access_token: str, ticket_id: str) -> dict:
    return _handle(
        requests.get(f"{API_BASE_URL}/tickets/{ticket_id}", headers=_auth_headers(access_token))
    )


def get_ai_suggestion(access_token: str, ticket_id: str) -> tuple[int, dict]:
    """Returns (status_code, body). 202 means still generating -- not an error."""
    response = requests.get(
        f"{API_BASE_URL}/tickets/{ticket_id}/ai-suggestion", headers=_auth_headers(access_token)
    )
    if response.status_code in (200, 202):
        return response.status_code, response.json()
    return response.status_code, _handle(response)


def assign_ticket(access_token: str, ticket_id: str, agent_id: str) -> dict:
    return _handle(
        requests.patch(
            f"{API_BASE_URL}/tickets/{ticket_id}/assign",
            json={"agent_id": agent_id},
            headers=_auth_headers(access_token),
        )
    )


def update_ticket_status(access_token: str, ticket_id: str, new_status: str) -> dict:
    return _handle(
        requests.patch(
            f"{API_BASE_URL}/tickets/{ticket_id}/status",
            json={"status": new_status},
            headers=_auth_headers(access_token),
        )
    )


def list_ticket_comments(access_token: str, ticket_id: str) -> list[dict]:
    return _handle(
        requests.get(
            f"{API_BASE_URL}/tickets/{ticket_id}/comments", headers=_auth_headers(access_token)
        )
    )


def create_ticket_comment(
    access_token: str, ticket_id: str, body: str, is_internal: bool
) -> dict:
    return _handle(
        requests.post(
            f"{API_BASE_URL}/tickets/{ticket_id}/comments",
            json={"body": body, "is_internal": is_internal},
            headers=_auth_headers(access_token),
        )
    )


def get_ticket_analytics(access_token: str) -> dict:
    return _handle(
        requests.get(f"{API_BASE_URL}/tickets/analytics/sla", headers=_auth_headers(access_token))
    )


def create_kb_article(access_token: str, title: str, body: str) -> dict:
    return _handle(
        requests.post(
            f"{API_BASE_URL}/kb-articles",
            json={"title": title, "body": body},
            headers=_auth_headers(access_token),
        )
    )


def list_kb_articles(access_token: str) -> list[dict]:
    return _handle(requests.get(f"{API_BASE_URL}/kb-articles", headers=_auth_headers(access_token)))
