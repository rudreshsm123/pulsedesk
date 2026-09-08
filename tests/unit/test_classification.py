import pytest

from app.core.enums import TicketPriority
from app.services.classification import classify_ticket_text


@pytest.mark.parametrize(
    "subject,body,expected_priority",
    [
        ("Production is down", "Everything is broken", TicketPriority.URGENT),
        ("Login is broken", "I cannot access my account", TicketPriority.HIGH),
        ("Question about my plan", "Just curious about features", TicketPriority.MEDIUM),
    ],
)
def test_priority_classification(subject, body, expected_priority):
    _, priority, _ = classify_ticket_text(subject, body)
    assert priority == expected_priority


@pytest.mark.parametrize(
    "subject,body,expected_category",
    [
        ("Refund request", "Please refund my last invoice charge", "billing"),
        ("API integration error", "Getting a crash on every API call", "technical"),
        ("Locked out", "My account access and password are locked", "account"),
        ("Hello", "Just saying hi", "general"),
    ],
)
def test_category_classification(subject, body, expected_category):
    category, _, _ = classify_ticket_text(subject, body)
    assert category == expected_category


def test_confidence_is_returned():
    _, _, confidence = classify_ticket_text("Subject", "Body")
    assert 0.0 < confidence <= 1.0
