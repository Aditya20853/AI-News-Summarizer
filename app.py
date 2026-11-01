
import streamlit as st
import requests
import xml.etree.ElementTree as ET
from urllib.parse import quote_plus
from bs4 import BeautifulSoup


# ---------------- CONFIGURATION ----------------

st.set_page_config(
    page_title="AI News Summarizer",
    page_icon="✦",
    layout="wide"
)

st.markdown("""
<style>
.stApp {
    background-color: #F3F6FB;
}
.main-title {
    background: #172554;
    padding: 25px;
    border-radius: 12px;
    color: white;
    margin-bottom: 20px;
}
.news-card {
    background: white;
    padding: 15px;
    border-radius: 10px;
    border: 1px solid #E2E8F0;
    margin-bottom: 10px;
}
</style>
""", unsafe_allow_html=True)

st.markdown("""
<div class="main-title">
    <h1>✦ AI News Summarizer</h1>
    <p>Explore current news and understand it with AI</p>
</div>
""", unsafe_allow_html=True)


# ---------------- NEWS FETCHING ----------------

def fetch_news(topic):
    url = (
        "https://news.google.com/rss/search?q="
        + quote_plus(topic)
        + "&hl=en-IN&gl=IN&ceid=IN:en"
    )

    response = requests.get(
        url,
        timeout=20,
        headers={"User-Agent": "Mozilla/5.0"}
    )
    response.raise_for_status()

    root = ET.fromstring(response.content)
    results = []

    for item in root.findall(".//item"):
        description_html = item.findtext(
            "description", default=""
        )

        description = BeautifulSoup(
            description_html, "html.parser"
        ).get_text(" ", strip=True)

        results.append({
            "title": item.findtext("title", default="No title"),
            "link": item.findtext("link", default=""),
            "published": item.findtext("pubDate", default=""),
            "description": description
        })

    return results


# ---------------- ARTICLE EXTRACTION ----------------

def extract_article_text(url):
    if not url.startswith(("https://", "http://")):
        return ""

    response = requests.get(
        url,
        timeout=20,
        headers={"User-Agent": "Mozilla/5.0"}
    )
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")

    for tag in soup([
        "script", "style", "nav", "footer",
        "header", "aside", "form", "noscript"
    ]):
        tag.decompose()

    article = soup.find("article")

    paragraphs = (
        article.find_all("p")
        if article else soup.find_all("p")
    )

    text = " ".join(
        p.get_text(" ", strip=True)
        for p in paragraphs
    )

    return text[:12000] if len(text) > 200 else ""


# ---------------- AI SUMMARIZATION ----------------

def generate_summary(article):
    api_key = st.secrets.get(
        "GROQ_API_KEY",
        os.getenv("GROQ_API_KEY", "")
    )

    if not api_key:
        raise ValueError(
            "AI API key is not configured. "
            "Add GROQ_API_KEY in Streamlit Secrets."
        )

    content = ""

    try:
        content = extract_article_text(article["link"])
    except Exception:
        pass

    if content:
        source = content
        source_type = "Full article text"
    else:
        source = (
            f"Headline: {article['title']}\n"
            f"Description: {article['description']}\n"
            f"Publication date: {article['published']}"
        )
        source_type = "Headline and available description"

    prompt = f"""
You are an assistant that summarizes news for students.

Summarize the supplied news in simple English.

Instructions:
- Write 3 to 5 sentences.
- Include the main points only.
- Use understandable language.
- Do not invent facts.
- Mention if information is insufficient.

News information:
{source}
"""

    response = requests.post(
        "https://api.groq.com/openai/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        },
        json={
            "model": "llama-3.3-70b-versatile",
            "messages": [
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.3
        },
        timeout=90
    )

    response.raise_for_status()

    summary = response.json()["choices"][0]["message"]["content"]

    return summary.strip(), source_type


# ---------------- SESSION STATE ----------------

if "articles" not in st.session_state:
    st.session_state.articles = []

if "selected_article" not in st.session_state:
    st.session_state.selected_article = None

if "summary" not in st.session_state:
    st.session_state.summary = ""

if "source_type" not in st.session_state:
    st.session_state.source_type = ""


# ---------------- SEARCH SECTION ----------------

st.subheader("Search News")

with st.form("search_form"):
    topic = st.text_input(
        "Enter a topic",
        placeholder="e.g. Technology, Education, Artificial Intelligence",
        value="technology"
    )

    search = st.form_submit_button(
        "🔍 Search News",
        use_container_width=True
    )

if search:
    if not topic.strip():
        st.warning("Please enter a topic.")
    else:
        try:
            with st.spinner("Fetching latest news..."):
                st.session_state.articles = fetch_news(topic.strip())
                st.session_state.selected_article = None
                st.session_state.summary = ""

            if not st.session_state.articles:
                st.info("No articles found. Try another topic.")
            else:
                st.success(
                    f"Found {len(st.session_state.articles)} articles!"
                )

        except Exception as error:
            st.error(f"Could not fetch news: {error}")


# ---------------- MAIN CONTENT ----------------

if st.session_state.articles:

    left, right = st.columns([1, 1])

    with left:
        st.subheader("📰 News Headlines")
        st.caption("Select a headline to view its details.")

        titles = [
            article["title"]
            for article in st.session_state.articles
        ]

        selected_index = st.radio(
            "Available articles",
            range(len(titles)),
            format_func=lambda i: titles[i],
            key="article_choice"
        )

        st.session_state.selected_article = (
            st.session_state.articles[selected_index]
        )

    with right:
        article = st.session_state.selected_article

        st.subheader("📄 Selected Article")

        st.markdown(f"**{article['title']}**")
        st.caption(f"Published: {article['published']}")

        st.write(article["description"])

        st.link_button(
            "Open Original Article ↗",
            article["link"],
            use_container_width=True
        )

        st.divider()

        st.subheader("✦ AI Summary")

        if st.button(
            "✦ Summarize Selected News",
            type="primary",
            use_container_width=True
        ):
            try:
                with st.spinner("AI is preparing your summary..."):
                    summary, source_type = generate_summary(article)

                    st.session_state.summary = summary
                    st.session_state.source_type = source_type

            except Exception as error:
                st.error(f"Could not generate summary: {error}")

        if st.session_state.summary:
            st.markdown(st.session_state.summary)

            st.caption(
                f"Summary source: {st.session_state.source_type}"
            )

            st.button(
                "📋 Copy Summary",
                on_click=lambda: st.session_state.update(
                    copied=True
                )
            )

            if st.session_state.get("copied", False):
                st.code(st.session_state.summary)
                st.info("Select and copy the text above.")

else:
    st.info(
        "Search for a topic to discover news articles."
    )

st.divider()

st.caption(
    "Python • Streamlit • Google News RSS • Groq AI"
)
