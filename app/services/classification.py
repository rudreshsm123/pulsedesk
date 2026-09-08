from app.core.enums import TicketPriority

# Deliberately simple keyword rules -- this is the always-available fallback path
# (see Part 5 of the design: classification never blocks on the LLM being reachable).
# Phase 8 adds an LLM-based classifier that this remains the fallback for.
_URGENT_KEYWORDS = {"down", "outage", "critical", "urgent", "asap", "production", "breach"}
_HIGH_KEYWORDS = {"broken", "error", "failing", "can't", "cannot", "blocked"}

_CATEGORY_KEYWORDS: dict[str, set[str]] = {
    "billing": {"invoice", "charge", "payment", "refund", "subscription", "billing"},
    "technical": {"error", "bug", "crash", "api", "integration", "login", "not working"},
    "account": {"password", "account", "access", "locked", "permission", "profile"},
}

_DEFAULT_CATEGORY = "general"
_RULE_BASED_CONFIDENCE = 0.6


def classify_ticket_text(subject: str, body: str) -> tuple[str, TicketPriority, float]:
    text = f"{subject} {body}".lower()

    priority = _classify_priority(text)
    category = _classify_category(text)

    return category, priority, _RULE_BASED_CONFIDENCE


def _classify_priority(text: str) -> TicketPriority:
    if any(keyword in text for keyword in _URGENT_KEYWORDS):
        return TicketPriority.URGENT
    if any(keyword in text for keyword in _HIGH_KEYWORDS):
        return TicketPriority.HIGH
    return TicketPriority.MEDIUM


def _classify_category(text: str) -> str:
    best_category = _DEFAULT_CATEGORY
    best_score = 0

    for category, keywords in _CATEGORY_KEYWORDS.items():
        score = sum(1 for keyword in keywords if keyword in text)
        if score > best_score:
            best_score = score
            best_category = category

    return best_category
