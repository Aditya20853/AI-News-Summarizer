
import tkinter as tk
from tkinter import messagebox
import requests
import xml.etree.ElementTree as ET
from urllib.parse import quote_plus
from bs4 import BeautifulSoup
import threading
import webbrowser
import ollama


# =========================================================
# CONFIGURATION
# =========================================================

MODEL_NAME = "llama3.2:3b"
articles = []

# Colors
BG = "#F3F6FB"
WHITE = "#FFFFFF"
NAVY = "#172554"
BLUE = "#2563EB"
BLUE_HOVER = "#1D4ED8"
TEXT = "#1E293B"
MUTED = "#64748B"
BORDER = "#E2E8F0"
LIGHT_BLUE = "#EFF6FF"
GREEN = "#15803D"


# =========================================================
# NEWS FETCHING
# =========================================================

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

    rss_root = ET.fromstring(response.content)
    results = []

    for item in rss_root.findall(".//item"):
        title = item.findtext("title", default="No title")
        link = item.findtext("link", default="")
        published = item.findtext("pubDate", default="")

        description_html = item.findtext("description", default="")
        description = BeautifulSoup(
            description_html, "html.parser"
        ).get_text(" ", strip=True)

        results.append({
            "title": title,
            "link": link,
            "published": published,
            "description": description
        })

    return results


# =========================================================
# ARTICLE EXTRACTION
# =========================================================

def extract_article_text(url):
    if not url.startswith(("https://", "http://")):
        return ""

    response = requests.get(
        url,
        timeout=20,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 Chrome/130.0 Safari/537.36"
            )
        }
    )
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")

    for tag in soup([
        "script", "style", "nav", "footer",
        "header", "aside", "form", "noscript"
    ]):
        tag.decompose()

    article_element = soup.find("article")

    if article_element:
        paragraphs = article_element.find_all("p")
    else:
        paragraphs = soup.find_all("p")

    text = " ".join(
        p.get_text(" ", strip=True)
        for p in paragraphs
    )

    return text[:15000] if len(text) > 200 else ""


# =========================================================
# AI SUMMARIZATION
# =========================================================

def generate_summary(article):
    title = article.get("title", "")
    published = article.get("published", "")
    description = article.get("description", "")
    link = article.get("link", "")

    article_content = ""

    try:
        article_content = extract_article_text(link)
    except Exception:
        pass

    if article_content:
        source_text = article_content
        source_type = "Full article text"
    else:
        source_text = (
            f"Headline: {title}\n"
            f"Description: {description}\n"
            f"Publication date: {published}"
        )
        source_type = "Headline and available description"

    prompt = f"""
You are an assistant that summarizes news for students.

Summarize the supplied news information in simple English.

Instructions:
- Write 3 to 5 sentences.
- Include the main points only.
- Use clear, understandable language.
- Do not invent facts or unsupported details.
- If information is insufficient, say so.

News information:
{source_text}
"""

    response = ollama.chat(
        model=MODEL_NAME,
        messages=[{"role": "user", "content": prompt}]
    )

    return response["message"]["content"].strip(), source_type


# =========================================================
# GUI HELPERS
# =========================================================

def set_text(widget, content):
    widget.config(state="normal")
    widget.delete("1.0", tk.END)
    widget.insert("1.0", content)
    widget.config(state="disabled")


def make_button(parent, text, command, primary=False):
    button = tk.Button(
        parent,
        text=text,
        command=command,
        font=("Segoe UI", 10, "bold"),
        bg=BLUE if primary else WHITE,
        fg=WHITE if primary else NAVY,
        activebackground=BLUE_HOVER if primary else LIGHT_BLUE,
        activeforeground=WHITE if primary else NAVY,
        relief="flat",
        bd=0,
        padx=12,
        pady=8,
        cursor="hand2",
        highlightthickness=0
    )

    return button


# =========================================================
# SEARCH NEWS
# =========================================================

def search_news():
    topic = search_entry.get().strip()

    if not topic:
        messagebox.showwarning(
            "Missing Topic",
            "Please enter a topic, such as technology or education."
        )
        return

    search_button.config(state="disabled", text="Loading...")
    news_list.delete(0, tk.END)

    global articles
    articles = []

    set_text(article_text, "Fetching news...")
    set_text(summary_text, "Searching for news articles...")

    def worker():
        try:
            results = fetch_news(topic)
            root.after(0, lambda: show_news(results))
        except Exception as error:
            root.after(
                0,
                lambda msg=str(error): show_news_error(msg)
            )

    threading.Thread(target=worker, daemon=True).start()


def show_news(results):
    global articles
    articles = results

    news_list.delete(0, tk.END)

    for article in articles:
        news_list.insert(tk.END, article["title"])

    search_button.config(state="normal", text="Search News")

    if not articles:
        set_text(article_text, "No articles found.")
        set_text(summary_text, "Try searching for another topic.")

        messagebox.showinfo(
            "No Results",
            "No news articles were found. Try another topic."
        )
    else:
        set_text(
            article_text,
            f"Found {len(articles)} news articles.\n\n"
            "Select a headline to read its details."
        )
        set_text(
            summary_text,
            "Select a headline, then click Summarize Selected News."
        )


def show_news_error(error):
    search_button.config(state="normal", text="Search News")
    set_text(article_text, "Could not fetch news.")
    set_text(summary_text, "Please check your internet connection.")

    messagebox.showerror(
        "News Error",
        "Could not fetch news.\n\n" + error
    )


# =========================================================
# SELECT NEWS
# =========================================================

def show_selected_news(event=None):
    selection = news_list.curselection()

    if not selection:
        return

    index = selection[0]

    if index >= len(articles):
        return

    article = articles[index]

    details = (
        article.get("title", "No title")
        + "\n\nPublished: "
        + article.get("published", "Date unavailable")
        + "\n\nDescription:\n"
        + article.get("description", "No description available")
        + "\n\nArticle link:\n"
        + article.get("link", "No link available")
    )

    set_text(article_text, details)
    set_text(
        summary_text,
        "Ready to summarize!\n\n"
        "Click the blue button below to generate an AI summary."
    )


# =========================================================
# OPEN ORIGINAL ARTICLE
# =========================================================

def open_article():
    selection = news_list.curselection()

    if not selection:
        messagebox.showwarning(
            "Select News",
            "Please select a news headline first."
        )
        return

    link = articles[selection[0]].get("link", "")

    if link.startswith(("https://", "http://")):
        webbrowser.open(link)
    else:
        messagebox.showerror(
            "Error",
            "The article link is not available."
        )


# =========================================================
# SUMMARIZE SELECTED NEWS
# =========================================================

def summarize_news():
    selection = news_list.curselection()

    if not selection:
        messagebox.showwarning(
            "Select News",
            "Please select a news headline first."
        )
        return

    article = articles[selection[0]]

    summarize_button.config(
        state="disabled",
        text="Generating Summary..."
    )

    set_text(
        summary_text,
        "Please wait...\n\n"
        "The AI is reading the available news information "
        "and preparing your summary."
    )

    def worker():
        try:
            summary, source_type = generate_summary(article)

            result = (
                summary
                + "\n\n------------------------------\n"
                + "Summary source: "
                + source_type
            )

            root.after(
                0,
                lambda text=result: show_summary(text)
            )

        except Exception as error:
            root.after(
                0,
                lambda msg=str(error): show_summary_error(msg)
            )

    threading.Thread(target=worker, daemon=True).start()


def show_summary(result):
    set_text(summary_text, result)

    summarize_button.config(
        state="normal",
        text="✦  Summarize Selected News"
    )


def show_summary_error(error):
    set_text(
        summary_text,
        "Could not generate the AI summary.\n\n"
        f"Check that Ollama is running and "
        f"'{MODEL_NAME}' is installed.\n\n"
        f"Details: {error}"
    )

    summarize_button.config(
        state="normal",
        text="✦  Summarize Selected News"
    )


# =========================================================
# COPY SUMMARY
# =========================================================

def copy_summary():
    summary = summary_text.get("1.0", tk.END).strip()

    if (
        not summary
        or summary.startswith("Ready to summarize!")
        or summary.startswith("Select a headline")
        or summary.startswith("Please wait")
        or summary.startswith("Your AI-generated summary")
        or summary.startswith("Could not generate")
        or summary.startswith("Searching for news")
    ):
        messagebox.showwarning(
            "No Summary",
            "Generate an AI summary before copying."
        )
        return

    root.clipboard_clear()
    root.clipboard_append(summary)
    root.update()

    messagebox.showinfo("Copied", "Summary copied to clipboard.")


# =========================================================
# MAIN WINDOW
# =========================================================

root = tk.Tk()
root.title("AI News Summarizer")
root.geometry("1150x780")
root.minsize(850, 600)
root.configure(bg=BG)

# Header
header = tk.Frame(root, bg=NAVY, height=105)
header.pack(fill="x")
header.pack_propagate(False)

tk.Label(
    header,
    text="✦  AI News Summarizer",
    font=("Segoe UI", 23, "bold"),
    bg=NAVY,
    fg=WHITE
).pack(anchor="w", padx=25, pady=(17, 2))

tk.Label(
    header,
    text="Explore current news and understand it with AI",
    font=("Segoe UI", 10),
    bg=NAVY,
    fg="#CBD5E1"
).pack(anchor="w", padx=28)


# Search panel
search_card = tk.Frame(
    root,
    bg=WHITE,
    highlightbackground=BORDER,
    highlightthickness=1
)
search_card.pack(fill="x", padx=20, pady=12)

tk.Label(
    search_card,
    text="SEARCH TOPIC",
    font=("Segoe UI", 9, "bold"),
    bg=WHITE,
    fg=MUTED
).pack(anchor="w", padx=15, pady=(10, 4))

search_row = tk.Frame(search_card, bg=WHITE)
search_row.pack(fill="x", padx=15, pady=(0, 12))

search_entry = tk.Entry(
    search_row,
    font=("Segoe UI", 11),
    bg="#F8FAFC",
    fg=TEXT,
    relief="flat",
    highlightthickness=1,
    highlightbackground=BORDER,
    highlightcolor=BLUE
)
search_entry.pack(
    side="left",
    fill="x",
    expand=True,
    ipady=8,
    padx=(0, 10)
)
search_entry.insert(0, "technology")

search_button = make_button(
    search_row,
    "Search News",
    search_news,
    primary=True
)
search_button.pack(side="right")


# Main content area
content_frame = tk.Frame(root, bg=BG)
content_frame.pack(
    fill="both",
    expand=True,
    padx=20,
    pady=(0, 10)
)

content_frame.grid_columnconfigure(0, weight=1, uniform="panel")
content_frame.grid_columnconfigure(1, weight=1, uniform="panel")
content_frame.grid_rowconfigure(0, weight=1)


# LEFT PANEL: NEWS HEADLINES
news_frame = tk.Frame(
    content_frame,
    bg=WHITE,
    highlightbackground=BORDER,
    highlightthickness=1
)
news_frame.grid(
    row=0,
    column=0,
    sticky="nsew",
    padx=(0, 8)
)

tk.Label(
    news_frame,
    text="News Headlines",
    font=("Segoe UI", 14, "bold"),
    bg=WHITE,
    fg=NAVY
).pack(anchor="w", padx=15, pady=(15, 3))

tk.Label(
    news_frame,
    text="Select a headline to view its details",
    font=("Segoe UI", 9),
    bg=WHITE,
    fg=MUTED
).pack(anchor="w", padx=15, pady=(0, 10))

tk.Frame(news_frame, bg=BORDER, height=1).pack(fill="x")

list_container = tk.Frame(news_frame, bg=WHITE)
list_container.pack(fill="both", expand=True, padx=8, pady=8)

news_scrollbar = tk.Scrollbar(list_container)
news_scrollbar.pack(side="right", fill="y")

news_list = tk.Listbox(
    list_container,
    font=("Segoe UI", 10),
    bg=WHITE,
    fg=TEXT,
    selectbackground=LIGHT_BLUE,
    selectforeground=NAVY,
    activestyle="none",
    relief="flat",
    bd=0,
    highlightthickness=0,
    selectmode=tk.SINGLE,
    exportselection=False,
    yscrollcommand=news_scrollbar.set
)
news_list.pack(side="left", fill="both", expand=True)

news_scrollbar.config(command=news_list.yview)
news_list.bind("<<ListboxSelect>>", show_selected_news)


# RIGHT PANEL
right_frame = tk.Frame(content_frame, bg=BG)
right_frame.grid(row=0, column=1, sticky="nsew", padx=(8, 0))

right_frame.grid_columnconfigure(0, weight=1)

# Keep enough height for the article card and summary card.
right_frame.grid_rowconfigure(0, weight=1, uniform="rightpanels")
right_frame.grid_rowconfigure(1, weight=1, uniform="rightpanels")


# SELECTED ARTICLE CARD
article_frame = tk.Frame(
    right_frame,
    bg=WHITE,
    highlightbackground=BORDER,
    highlightthickness=1
)
article_frame.grid(
    row=0,
    column=0,
    sticky="nsew",
    pady=(0, 8)
)

tk.Label(
    article_frame,
    text="Selected Article",
    font=("Segoe UI", 13, "bold"),
    bg=WHITE,
    fg=NAVY
).pack(anchor="w", padx=14, pady=(12, 2))

tk.Label(
    article_frame,
    text="News information and publication details",
    font=("Segoe UI", 9),
    bg=WHITE,
    fg=MUTED
).pack(anchor="w", padx=14, pady=(0, 8))

tk.Frame(article_frame, bg=BORDER, height=1).pack(fill="x")

article_text = tk.Text(
    article_frame,
    height=5,
    wrap="word",
    font=("Segoe UI", 10),
    bg=WHITE,
    fg=TEXT,
    relief="flat",
    bd=0,
    padx=12,
    pady=8
)
article_text.pack(fill="both", expand=True, padx=3, pady=3)

article_text.insert(
    "1.0",
    "Welcome!\n\nSearch for a topic and select a news headline "
    "to view its details here."
)
article_text.config(state="disabled")

open_button = make_button(
    article_frame,
    "Open Original Article",
    open_article
)
open_button.pack(anchor="w", padx=12, pady=(3, 10))


# AI SUMMARY CARD
summary_frame = tk.Frame(
    right_frame,
    bg=WHITE,
    highlightbackground=BORDER,
    highlightthickness=1
)
summary_frame.grid(row=1, column=0, sticky="nsew")

# Grid layout ensures the action buttons have their own row.
summary_frame.grid_columnconfigure(0, weight=1)
summary_frame.grid_rowconfigure(2, weight=1)

summary_header = tk.Frame(summary_frame, bg=WHITE)
summary_header.grid(
    row=0,
    column=0,
    sticky="ew",
    padx=14,
    pady=(12, 8)
)

tk.Label(
    summary_header,
    text="✦  AI Summary",
    font=("Segoe UI", 14, "bold"),
    bg=WHITE,
    fg=BLUE
).pack(anchor="w")

tk.Label(
    summary_header,
    text="Simple explanations powered by local AI",
    font=("Segoe UI", 9),
    bg=WHITE,
    fg=MUTED
).pack(anchor="w", pady=(2, 0))

tk.Frame(summary_frame, bg=BORDER, height=1).grid(
    row=1,
    column=0,
    sticky="ew"
)

summary_text = tk.Text(
    summary_frame,
    height=4,
    wrap="word",
    font=("Segoe UI", 10),
    bg=WHITE,
    fg=TEXT,
    relief="flat",
    bd=0,
    padx=12,
    pady=8
)
summary_text.grid(
    row=2,
    column=0,
    sticky="nsew",
    padx=3,
    pady=3
)

summary_text.insert(
    "1.0",
    "Your AI-generated summary will appear here.\n\n"
    "Select a headline and click the button below."
)
summary_text.config(state="disabled")

# IMPORTANT: Dedicated action row, outside the text widget.
# These buttons remain visible as the window is resized.
summary_button_frame = tk.Frame(summary_frame, bg=WHITE)
summary_button_frame.grid(
    row=3,
    column=0,
    sticky="ew",
    padx=10,
    pady=(4, 10)
)

summary_button_frame.grid_columnconfigure(0, weight=1)
summary_button_frame.grid_columnconfigure(1, weight=1)

summarize_button = make_button(
    summary_button_frame,
    "✦  Summarize News",
    summarize_news,
    primary=True
)
summarize_button.grid(
    row=0,
    column=0,
    sticky="ew",
    padx=(0, 4),
    ipady=3
)

copy_button = make_button(
    summary_button_frame,
    "Copy Summary",
    copy_summary
)
copy_button.grid(
    row=0,
    column=1,
    sticky="ew",
    padx=(4, 0),
    ipady=3
)


# FOOTER
footer = tk.Frame(root, bg=BG)
footer.pack(fill="x", padx=20, pady=(0, 8))

tk.Label(
    footer,
    text="Python  •  Tkinter  •  Google News RSS  •  Ollama",
    font=("Segoe UI", 9),
    bg=BG,
    fg=MUTED
).pack(side="left")

tk.Label(
    footer,
    text="● Local AI",
    font=("Segoe UI", 9, "bold"),
    bg=BG,
    fg=GREEN
).pack(side="right")


# ENTER KEY SEARCHES NEWS
search_entry.bind(
    "<Return>",
    lambda event: search_news()
)


# START APPLICATION
root.mainloop()
