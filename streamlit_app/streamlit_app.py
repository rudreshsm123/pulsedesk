import api_client
import streamlit as st
from theme import inject_custom_css

st.set_page_config(page_title="PulseDesk", page_icon=":material/support_agent:", layout="wide")
inject_custom_css()

st.session_state.setdefault("access_token", None)
st.session_state.setdefault("role", None)
st.session_state.setdefault("email", None)

if not st.session_state.access_token:
    _, center, _ = st.columns([1, 1.2, 1])
    with center:
        st.title("PulseDesk", icon=":material/support_agent:")
        st.caption(
            "AI-augmented support ticket triage. Sign in or create an account to continue."
        )

        sign_in_tab, create_account_tab = st.tabs(["Sign in", "Create account"])

        with sign_in_tab:
            with st.form("login_form"):
                email = st.text_input("Email")
                password = st.text_input("Password", type="password")
                submitted = st.form_submit_button(
                    "Sign in", icon=":material/login:", width="stretch"
                )
            if submitted:
                try:
                    tokens = api_client.login(email, password)
                    st.session_state.access_token = tokens["access_token"]
                    st.session_state.refresh_token = tokens["refresh_token"]
                    st.session_state.role = api_client.decode_role_from_token(
                        tokens["access_token"]
                    )
                    st.session_state.user_id = api_client.decode_user_id_from_token(
                        tokens["access_token"]
                    )
                    st.session_state.email = email
                    st.rerun()
                except api_client.APIError as exc:
                    st.error(f"Sign-in failed: {exc.detail}")

        with create_account_tab:
            st.caption(
                'New accounts start as "customer". Agent/admin accounts are promoted separately.'
            )
            with st.form("register_form"):
                new_email = st.text_input("Email", key="register_email")
                new_password = st.text_input(
                    "Password",
                    type="password",
                    key="register_password",
                    help="At least 8 characters",
                )
                submitted = st.form_submit_button(
                    "Create account", icon=":material/person_add:", width="stretch"
                )
            if submitted:
                try:
                    api_client.register(new_email, new_password)
                    st.success("Account created -- sign in on the other tab.")
                except api_client.APIError as exc:
                    st.error(f"Registration failed: {exc.detail}")

    st.stop()

pages = []
if st.session_state.role == "admin":
    pages.append(st.Page("app_pages/dashboard.py", title="Dashboard", icon=":material/dashboard:"))
pages += [
    st.Page("app_pages/tickets.py", title="Tickets", icon=":material/confirmation_number:"),
    st.Page("app_pages/ticket_detail.py", title="Ticket detail", icon=":material/description:"),
]
if st.session_state.role == "admin":
    pages.append(
        st.Page("app_pages/kb_articles.py", title="Knowledge base", icon=":material/menu_book:")
    )

with st.sidebar:
    st.caption(f"Signed in as **{st.session_state.email}**")
    st.badge(st.session_state.role, color="violet")
    if st.button("Sign out", icon=":material/logout:"):
        st.session_state.clear()
        st.rerun()

nav = st.navigation(pages)
nav.run()
