import streamlit as st

# Targets stable, documented hooks only: st.container(key=...) is guaranteed to emit a
# ".st-key-<name>" class (Streamlit docs), and data-testid attributes (stBaseButton-*,
# stMainBlockContainer) are part of Streamlit's public DOM contract. Deliberately not
# targeting internal "st-emotion-cache-*" hashes -- those are implementation details
# that can change between Streamlit versions/reruns.
_CSS = """
<style>
@keyframes pd-fade-in {
    from { opacity: 0; transform: translateY(6px); }
    to { opacity: 1; transform: translateY(0); }
}
[data-testid="stMainBlockContainer"] {
    animation: pd-fade-in 0.35s ease-out;
}

div[class*="st-key-ticket-card-"] {
    transition: box-shadow 0.2s ease, transform 0.2s ease, border-color 0.2s ease;
    border-left-width: 4px !important;
}
div[class*="st-key-ticket-card-"]:hover {
    box-shadow: 0 6px 20px rgba(24, 24, 27, 0.10);
    transform: translateY(-2px);
}
div[class*="st-key-ticket-card-low-"] { border-left-color: #A1A1AA !important; }
div[class*="st-key-ticket-card-medium-"] { border-left-color: #3B82F6 !important; }
div[class*="st-key-ticket-card-high-"] { border-left-color: #F97316 !important; }
div[class*="st-key-ticket-card-urgent-"] { border-left-color: #EF4444 !important; }
div[class*="st-key-ticket-card-none-"] { border-left-color: #E4E4E7 !important; }

div[class*="st-key-kpi-"] {
    transition: box-shadow 0.2s ease, transform 0.2s ease;
    border-top-width: 3px !important;
}
div[class*="st-key-kpi-"]:hover {
    box-shadow: 0 6px 20px rgba(24, 24, 27, 0.10);
    transform: translateY(-2px);
}
.st-key-kpi-total { border-top-color: #3B82F6 !important; }
.st-key-kpi-open { border-top-color: #F97316 !important; }
.st-key-kpi-resolved { border-top-color: #22C55E !important; }
.st-key-kpi-breached { border-top-color: #EF4444 !important; }

[data-testid^="stBaseButton"] {
    transition: transform 0.15s ease, box-shadow 0.15s ease;
}
[data-testid^="stBaseButton"]:hover {
    transform: translateY(-1px);
    box-shadow: 0 2px 10px rgba(24, 24, 27, 0.12);
}
</style>
"""


def inject_custom_css() -> None:
    st.html(_CSS)
