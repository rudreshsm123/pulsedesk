import api_client
import streamlit as st

st.title("Knowledge base", icon=":material/menu_book:")

with st.expander("Add an article", icon=":material/add_circle:"):
    with st.form("create_kb_article_form", border=False):
        title = st.text_input("Title")
        body = st.text_area("Body")
        submitted = st.form_submit_button("Save", icon=":material/save:")
    if submitted:
        if not title or not body:
            st.warning("Title and body are both required.")
        else:
            try:
                api_client.create_kb_article(st.session_state.access_token, title, body)
                st.success("Article saved -- chunking and embedding run in the background.")
            except api_client.APIError as exc:
                st.error(f"Could not save article: {exc.detail}")

st.divider()

try:
    articles = api_client.list_kb_articles(st.session_state.access_token)
except api_client.APIError as exc:
    st.error(f"Could not load articles: {exc.detail}")
    articles = []

if not articles:
    st.info("No knowledge base articles yet.")

for article in articles:
    with st.container(border=True):
        st.markdown(f"**{article['title']}**")
        st.caption(article["body"])
