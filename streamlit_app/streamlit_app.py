import api_client
import streamlit as st
from theme import inject_custom_css

st.set_page_config(page_title="PulseDesk", page_icon=":material/support_agent:", layout="wide")
inject_custom_css()

st.session_state.setdefault("access_token", None)
st.session_state.setdefault("role", None)
st.session_state.setdefault("email", None)

if not st.session_state.access_token:
    hero_col, form_col = st.columns([1.1, 1], gap="large")

    with hero_col:
        st.html(
            """
            <div style="background: linear-gradient(135deg, #4F46E5 0%, #7C3AED 55%, #DB2777 100%);
                        border-radius: 16px; padding: 3rem 2.5rem; min-height: 520px;
                        display: flex; flex-direction: column; justify-content: center;
                        color: white; font-family: 'Inter', sans-serif;">
                <div style="font-size: 2.25rem; font-weight: 700; margin-bottom: 0.75rem;">
                    PulseDesk
                </div>
                <div style="font-size: 1.05rem; opacity: 0.92; margin-bottom: 2.5rem;
                            max-width: 420px; line-height: 1.5;">
                    AI-augmented support ticket triage. Tickets get classified, matched
                    against your knowledge base, and drafted a grounded reply -- while a
                    human always reviews before anything reaches a customer.
                </div>
                <div style="display: flex; flex-direction: column; gap: 1.1rem;
                            font-size: 0.95rem;">
                    <div>&#9889; Tickets auto-classified by category &amp; priority in seconds</div>
                    <div>&#129504; RAG-grounded reply drafts from your own knowledge base</div>
                    <div>&#128202; Real-time SLA tracking and a team dashboard</div>
                </div>
            </div>
            """
        )

    with form_col:
        st.subheader("Welcome back")
        st.caption("Sign in or create an account to continue.")

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
    st.html(
        """
        <div style="display:flex; align-items:center; gap:0.5rem; margin-bottom:0.75rem;">
            <div style="width:28px; height:28px; border-radius:8px;
                        background: linear-gradient(135deg, #4F46E5, #DB2777);
                        display:flex; align-items:center; justify-content:center;
                        color:white; font-weight:700; font-size:0.8rem;">PD</div>
            <div style="font-weight:700; font-size:1.05rem;">PulseDesk</div>
        </div>
        """
    )
    st.caption(f"Signed in as **{st.session_state.email}**")
    st.badge(st.session_state.role, color="violet")
    if st.button("Sign out", icon=":material/logout:"):
        st.session_state.clear()
        st.rerun()

nav = st.navigation(pages)
nav.run()
