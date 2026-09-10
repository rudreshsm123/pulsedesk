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
    try:
        agents = api_client.list_agents(st.session_state.access_token)
    except api_client.APIError as exc:
        st.error(f"Could not load agents: {exc.detail}")
        agents = []

    if not agents:
        st.caption("No agent accounts exist yet.")
    else:
        agent_emails = [a["email"] for a in agents]
        with st.form("assign_form", border=False):
            selected_email = st.selectbox("Agent", agent_emails)
            submitted = st.form_submit_button("Assign", icon=":material/assignment_ind:")
        if submitted:
            agent_id = next(a["id"] for a in agents if a["email"] == selected_email)
            try:
                api_client.assign_ticket(st.session_state.access_token, ticket_id, agent_id)
                st.success(f"Ticket assigned to {selected_email}.")
                st.rerun()
            except api_client.APIError as exc:
                st.error(f"Could not assign ticket: {exc.detail}")

    st.divider()
    st.subheader("Resolution", divider=False)
    with st.container(horizontal=True):
        if st.button("Mark in progress", icon=":material/play_circle:"):
            try:
                api_client.update_ticket_status(
                    st.session_state.access_token, ticket_id, "IN_PROGRESS"
                )
                st.rerun()
            except api_client.APIError as exc:
                st.error(f"Could not update status: {exc.detail}")
        if st.button("Mark resolved", icon=":material/check_circle:", type="primary"):
            try:
                api_client.update_ticket_status(
                    st.session_state.access_token, ticket_id, "RESOLVED"
                )
                st.rerun()
            except api_client.APIError as exc:
                st.error(f"Could not update status: {exc.detail}")

st.divider()
st.subheader("Conversation", icon=":material/forum:")

try:
    comments = api_client.list_ticket_comments(st.session_state.access_token, ticket_id)
except api_client.APIError as exc:
    st.error(f"Could not load conversation: {exc.detail}")
    comments = []

if not comments:
    st.caption("No messages yet.")

my_user_id = st.session_state.get("user_id")
for comment in comments:
    is_mine = comment["author_id"] == my_user_id
    if comment["is_internal"]:
        label, avatar = "Internal note", ":material/lock:"
    elif is_mine:
        label, avatar = "You", ":material/person:"
    else:
        label, avatar = "Reply", ":material/support_agent:"

    with st.chat_message(label, avatar=avatar):
        if comment["is_internal"]:
            st.badge("Staff only", color="gray")
        st.write(comment["body"])
        st.caption(comment["created_at"])

if st.session_state.role in ("agent", "admin"):
    post_internal = st.checkbox("Post as internal note (not visible to the customer)")
else:
    post_internal = False

if reply := st.chat_input("Write a reply..."):
    try:
        api_client.create_ticket_comment(
            st.session_state.access_token, ticket_id, reply, post_internal
        )
        st.rerun()
    except api_client.APIError as exc:
        st.error(f"Could not post reply: {exc.detail}")
