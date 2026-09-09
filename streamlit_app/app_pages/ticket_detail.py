import api_client
import streamlit as st

st.title("Ticket detail", icon=":material/description:")

ticket_id = st.session_state.get("selected_ticket_id")
if not ticket_id:
    st.info("Pick a ticket from the Tickets page first.")
    st.page_link(
        "app_pages/tickets.py", label="Go to tickets", icon=":material/confirmation_number:"
    )
    st.stop()

try:
    ticket = api_client.get_ticket(st.session_state.access_token, ticket_id)
except api_client.APIError as exc:
    st.error(f"Could not load ticket: {exc.detail}")
    st.stop()

st.subheader(ticket["subject"])
with st.container(horizontal=True):
    st.metric("Status", ticket["status"])
    st.metric("Category", ticket["category"] or "-")
    st.metric("Priority", ticket["priority"] or "-")
    st.metric("Confidence", f"{ticket['ai_confidence']:.0%}" if ticket["ai_confidence"] else "-")

st.write(ticket["body"])
st.caption(f"Created {ticket['created_at']} -- SLA deadline {ticket['sla_deadline'] or 'n/a'}")

if st.session_state.role in ("agent", "admin"):
    st.divider()
    st.subheader("AI suggestion", divider=False)

    try:
        status_code, suggestion = api_client.get_ai_suggestion(
            st.session_state.access_token, ticket_id
        )
    except api_client.APIError as exc:
        st.error(f"Could not load suggestion: {exc.detail}")
        status_code, suggestion = None, None

    if status_code == 202:
        st.info("Still generating -- refresh in a few seconds.")
    elif status_code == 200:
        st.markdown(suggestion["suggested_reply"])
        if suggestion["source_article_ids"]:
            st.caption("Sources: " + ", ".join(suggestion["source_article_ids"]))

    st.divider()
    st.subheader("Assign", divider=False)
    with st.form("assign_form", border=False):
        agent_id = st.text_input(
            "Agent user ID",
            help="No agent directory in this UI yet -- paste an agent's user ID "
            "(see the users table).",
        )
        submitted = st.form_submit_button("Assign", icon=":material/assignment_ind:")
    if submitted:
        if not agent_id:
            st.warning("Enter an agent ID first.")
        else:
            try:
                api_client.assign_ticket(st.session_state.access_token, ticket_id, agent_id)
                st.success("Ticket assigned.")
                st.rerun()
            except api_client.APIError as exc:
                st.error(f"Could not assign ticket: {exc.detail}")
