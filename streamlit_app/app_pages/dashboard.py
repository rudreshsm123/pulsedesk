import api_client
import pandas as pd
import streamlit as st

st.title("Dashboard", icon=":material/dashboard:")

try:
    analytics = api_client.get_ticket_analytics(st.session_state.access_token)
except api_client.APIError as exc:
    st.error(f"Could not load analytics: {exc.detail}")
    st.stop()

by_status = analytics["by_status"]
by_priority = analytics["by_priority"]
by_category = analytics["by_category"]

open_statuses = ("PENDING", "CLASSIFIED", "IN_PROGRESS")
open_count = sum(by_status.get(s, 0) for s in open_statuses)
resolved_count = by_status.get("RESOLVED", 0)
breached_count = by_status.get("BREACHED", 0)

with st.container(horizontal=True):
    with st.container(border=True, key="kpi-total"):
        st.metric("Total tickets", analytics["total_tickets"])
    with st.container(border=True, key="kpi-open"):
        st.metric("Open", open_count)
    with st.container(border=True, key="kpi-resolved"):
        st.metric("Resolved", resolved_count)
    breached_key = "kpi-breached-alert" if breached_count > 0 else "kpi-breached"
    with st.container(border=True, key=breached_key):
        st.metric(
            "Breached SLA",
            breached_count,
            help="Tickets whose SLA deadline passed before resolution.",
        )
if breached_count > 0:
    st.warning(f"{breached_count} ticket(s) have breached their SLA and need attention.")

st.divider()

left, right = st.columns(2)
with left:
    with st.container(border=True):
        st.subheader("By priority")
        if by_priority:
            order = ["LOW", "MEDIUM", "HIGH", "URGENT"]
            series = pd.Series(by_priority).reindex(order).dropna()
            st.bar_chart(series, color="#3B82F6")
        else:
            st.caption("No classified tickets yet.")

with right:
    with st.container(border=True):
        st.subheader("By category")
        if by_category:
            st.bar_chart(pd.Series(by_category).sort_values(ascending=False), color="#8B5CF6")
        else:
            st.caption("No classified tickets yet.")

with st.container(border=True):
    st.subheader("By status")
    if by_status:
        status_order = ["PENDING", "CLASSIFIED", "IN_PROGRESS", "RESOLVED", "BREACHED"]
        series = pd.Series(by_status).reindex(status_order).dropna()
        st.bar_chart(series, color="#18181B")
    else:
        st.caption("No tickets yet.")
