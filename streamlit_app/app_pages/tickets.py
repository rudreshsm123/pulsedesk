import api_client
import streamlit as st

st.title("Tickets", icon=":material/confirmation_number:")

STATUS_COLORS = {
    "PENDING": "gray",
    "CLASSIFIED": "blue",
    "IN_PROGRESS": "yellow",
    "RESOLVED": "green",
    "BREACHED": "red",
}
PRIORITY_COLORS = {"LOW": "gray", "MEDIUM": "blue", "HIGH": "orange", "URGENT": "red"}

if st.session_state.role == "customer":
    with st.expander("Create a new ticket", icon=":material/add_circle:"):
        with st.form("create_ticket_form", border=False):
            subject = st.text_input("Subject")
            body = st.text_area("Describe the issue")
            submitted = st.form_submit_button("Submit ticket", icon=":material/send:")
        if submitted:
            if not subject or not body:
                st.warning("Subject and description are both required.")
            else:
                try:
                    ticket = api_client.create_ticket(st.session_state.access_token, subject, body)
                    st.success(
                        f"Ticket submitted (status: {ticket['status']}). "
                        "Classification runs in the background -- refresh in a few seconds."
                    )
                except api_client.APIError as exc:
                    st.error(f"Could not create ticket: {exc.detail}")

st.divider()

with st.container(horizontal=True):
    status_filter = st.selectbox(
        "Status", ["Any", "PENDING", "CLASSIFIED", "IN_PROGRESS", "RESOLVED", "BREACHED"]
    )
    priority_filter = st.selectbox("Priority", ["Any", "LOW", "MEDIUM", "HIGH", "URGENT"])
    if st.button("Refresh", icon=":material/refresh:"):
        st.rerun()

try:
    tickets = api_client.list_tickets(
        st.session_state.access_token,
        status=None if status_filter == "Any" else status_filter,
        priority=None if priority_filter == "Any" else priority_filter,
    )
except api_client.APIError as exc:
    if exc.status_code == 401:
        st.warning("Your session expired. Please sign out and sign in again.")
    else:
        st.error(f"Could not load tickets: {exc.detail}")
    tickets = []

if not tickets:
    st.info("No tickets to show yet.")

for ticket in tickets:
    priority_slug = (ticket["priority"] or "none").lower()
    with st.container(
        border=True, key=f"ticket-card-{priority_slug}-{ticket['id']}"
    ):
        with st.container(horizontal=True, vertical_alignment="center"):
            st.markdown(f"**{ticket['subject']}**")
            st.badge(ticket["status"], color=STATUS_COLORS.get(ticket["status"], "gray"))
            if ticket["priority"]:
                st.badge(ticket["priority"], color=PRIORITY_COLORS.get(ticket["priority"], "gray"))
        preview = ticket["body"][:160] + ("..." if len(ticket["body"]) > 160 else "")
        st.caption(preview)
        if ticket["category"]:
            st.caption(f"Category: {ticket['category']}")
        if st.button("View details", key=f"view_{ticket['id']}", icon=":material/open_in_new:"):
            st.session_state.selected_ticket_id = ticket["id"]
            st.switch_page("app_pages/ticket_detail.py")
