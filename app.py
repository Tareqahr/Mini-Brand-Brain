import streamlit as st
import os
import re
import html
import csv
from datetime import datetime
from pathlib import Path
from brain import BrandBrain
from constitution import check_constitution

FEEDBACK_FILE = Path(__file__).parent / "feedback.csv"
print("hello")

def save_feedback(question: str, answer: str, sources: list, rating: str) -> None:
    file_exists = FEEDBACK_FILE.exists()
    with open(FEEDBACK_FILE, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["timestamp", "rating", "question", "answer", "sources"])
        if not file_exists:
            writer.writeheader()
        writer.writerow({
            "timestamp": datetime.now().isoformat(),
            "rating": rating,
            "question": question,
            "answer": answer,
            "sources": ", ".join(c["source"] for c in sources),
        })


_STOP_WORDS = {"the", "a", "an", "is", "in", "of", "and", "or", "to", "for",
               "what", "how", "does", "do", "are", "was", "were", "be", "it",
               "celonis"}  # brand name appears in every doc — not a useful highlight signal

def _render_excerpt(excerpt: str, query: str = "") -> None:
    # Strip markdown syntax so headings / bold markers don't inflate the font
    text = re.sub(r"#+\s*", "", excerpt)
    text = re.sub(r"[*_`>]", "", text)
    text = html.escape(text.strip())

    if query:
        terms = [w for w in re.split(r"\W+", query.lower())
                 if len(w) > 3 and w not in _STOP_WORDS]
        for term in terms:
            text = re.sub(
                re.escape(term),
                lambda m: (
                    f'<mark style="background:#d4f5e9;color:#085041;'
                    f'border-radius:2px;padding:0 2px">{m.group()}</mark>'
                ),
                text,
                flags=re.IGNORECASE,
            )

    st.markdown(
        f'<div style="font-size:13px;color:#444;line-height:1.7;padding:4px 0">{text}</div>',
        unsafe_allow_html=True,
    )

st.set_page_config(
    page_title="Celonis Brand Brain",
    page_icon="🧠",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
.violation-high {
    background: #FCEBEB;
    border-left: 3px solid #E24B4A;
    border-radius: 0 6px 6px 0;
    padding: 8px 12px;
    margin: 6px 0;
    font-size: 13px;
}
.violation-medium {
    background: #FAEEDA;
    border-left: 3px solid #EF9F27;
    border-radius: 0 6px 6px 0;
    padding: 8px 12px;
    margin: 6px 0;
    font-size: 13px;
}
.refused-box {
    background: #F1EFE8;
    border-left: 3px solid #888;
    border-radius: 0 6px 6px 0;
    padding: 8px 12px;
    margin: 6px 0;
    font-size: 13px;
    color: #555;
}
.doc-pill {
    display: inline-block;
    background: #E1F5EE;
    color: #085041;
    border-radius: 12px;
    padding: 2px 10px;
    font-size: 12px;
    margin: 2px;
}
[data-testid="stChatMessage"] h1,
[data-testid="stChatMessage"] h2,
[data-testid="stChatMessage"] h3,
[data-testid="stChatMessage"] h4 {
    font-size: 15px !important;
    font-weight: 600 !important;
    margin: 4px 0 !important;
}
</style>
""", unsafe_allow_html=True)


@st.cache_resource
def get_brain():
    return BrandBrain()


brain = get_brain()
brain.load_sample_docs()

if "messages" not in st.session_state:
    st.session_state.messages = []

if "ingested_this_session" not in st.session_state:
    st.session_state.ingested_this_session = []

if "feedback_given" not in st.session_state:
    st.session_state.feedback_given = set()


with st.sidebar:
    st.markdown("### 🧠 Brand Brain")
    st.caption("Celonis — Mini Brand Brain prototype")
    st.divider()

    st.markdown("**Upload brand documents**")
    st.caption("Supported: .txt, .md, .pdf")

    uploaded_files = st.file_uploader(
        "Drop files here",
        accept_multiple_files=True,
        type=["txt", "md", "pdf"],
        label_visibility="collapsed",
    )

    if uploaded_files:
        for f in uploaded_files:
            if f.name not in brain.ingested_docs:
                with st.spinner(f"Ingesting {f.name}..."):
                    n, err = brain.ingest_file(f)
                if err:
                    st.error(f"{f.name}: {err}")
                elif n > 0:
                    st.session_state.ingested_this_session.append(f.name)
                    st.success(f"✓ {f.name} — {n} chunks")
                else:
                    st.error(f"{f.name}: no text could be extracted")

    st.divider()
    st.markdown("**Loaded documents**")
    if brain.ingested_docs:
        for doc, n_chunks in brain.ingested_docs.items():
            st.markdown(
                f'<span class="doc-pill">📄 {doc} ({n_chunks} chunks)</span>',
                unsafe_allow_html=True,
            )
    else:
        st.caption("No documents loaded yet.")

    st.divider()
    st.markdown("**How it works**")
    st.caption(
        "1. Upload brand documents above\n"
        "2. They are automatically chunked and embedded\n"
        "3. Ask any brand question in the chat\n"
        "4. Answers are grounded in your documents only\n"
        "5. Brand Constitution rules are enforced automatically"
    )

    if st.button("Clear chat history"):
        st.session_state.messages = []
        st.session_state.feedback_given = set()
        st.rerun()

    st.divider()
    st.markdown("**Feedback**")
    if FEEDBACK_FILE.exists():
        good = bad = 0
        with open(FEEDBACK_FILE, encoding="utf-8") as f:
            for row in csv.DictReader(f):
                if row["rating"] == "good":
                    good += 1
                else:
                    bad += 1
        st.caption(f"👍 {good}  ·  👎 {bad}  total ratings")
    else:
        st.caption("No feedback yet.")


st.markdown("## Celonis Brand Brain")
st.caption(
    "Ask brand questions. Answers are grounded in uploaded documents only — "
    "no outside knowledge, full citations, Brand Constitution enforced."
)

if not brain.ingested_docs:
    st.info(
        "No brand documents loaded. Upload documents in the sidebar, "
        "or the sample Celonis documents will load automatically."
    )

for idx, msg in enumerate(st.session_state.messages):
    with st.chat_message(msg["role"]):
        st.write(msg["content"])

        if msg["role"] == "assistant":
            if msg.get("refused"):
                st.markdown(
                    '<div class="refused-box">⚠️ Could not ground this answer in brand documents. No response generated.</div>',
                    unsafe_allow_html=True,
                )
            else:
                if msg.get("citations"):
                    st.markdown(f"📎 **Sources ({len(msg['citations'])})**")
                    for c in msg["citations"]:
                        with st.expander(f"📄 {c['source']}"):
                            excerpt = c.get("excerpt", "")
                            if excerpt:
                                _render_excerpt(excerpt, msg.get("query", ""))
                            else:
                                st.caption("No excerpt — clear chat and ask again.")

                if msg.get("violations"):
                    with st.expander(f"🚨 Brand Constitution ({len(msg['violations'])} issue{'s' if len(msg['violations'])>1 else ''})"):
                        for v in msg["violations"]:
                            css_class = "violation-high" if v["severity"] == "high" else "violation-medium"
                            st.markdown(
                                f'<div class="{css_class}">'
                                f'<b>{"🔴" if v["severity"] == "high" else "🟡"} {v["rule"]}</b><br>'
                                f'Triggered by: <code>{v["trigger"]}</code><br>'
                                f'Fix: {v["correction"]}'
                                f"</div>",
                                unsafe_allow_html=True,
                            )

                if idx in st.session_state.feedback_given:
                    st.caption("✓ Feedback recorded")
                else:
                    col1, col2, _ = st.columns([1, 1, 10])
                    with col1:
                        if st.button("👍", key=f"up_{idx}"):
                            save_feedback(msg.get("query", ""), msg["content"], msg.get("citations", []), "good")
                            st.session_state.feedback_given.add(idx)
                            st.rerun()
                    with col2:
                        if st.button("👎", key=f"down_{idx}"):
                            save_feedback(msg.get("query", ""), msg["content"], msg.get("citations", []), "bad")
                            st.session_state.feedback_given.add(idx)
                            st.rerun()


if prompt := st.chat_input("Ask a brand question..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.write(prompt)

    with st.chat_message("assistant"):
        with st.spinner("Searching brand documents..."):
            result = brain.query(prompt)

        st.write(result["answer"])

        violations = check_constitution(result["answer"]) if not result["refused"] else []

        if result["refused"]:
            st.markdown(
                '<div class="refused-box">⚠️ No relevant sources found — answer withheld to prevent hallucination.</div>',
                unsafe_allow_html=True,
            )
        else:
            if result.get("citations"):
                st.markdown(f"📎 **Sources ({len(result['citations'])})**")
                for c in result["citations"]:
                    with st.expander(f"📄 {c['source']}"):
                        excerpt = c.get("excerpt", "")
                        if excerpt:
                            _render_excerpt(excerpt, prompt)
                        else:
                            st.caption("No excerpt — clear chat and ask again.")

            if violations:
                with st.expander(f"🚨 Brand Constitution ({len(violations)} issue{'s' if len(violations)>1 else ''})"):
                    for v in violations:
                        css_class = "violation-high" if v["severity"] == "high" else "violation-medium"
                        st.markdown(
                            f'<div class="{css_class}">'
                            f'<b>{"🔴" if v["severity"] == "high" else "🟡"} {v["rule"]}</b><br>'
                            f'Triggered by: <code>{v["trigger"]}</code><br>'
                            f'Fix: {v["correction"]}'
                            f"</div>",
                            unsafe_allow_html=True,
                        )

    st.session_state.messages.append(
        {
            "role": "assistant",
            "content": result["answer"],
            "citations": result.get("citations", []),
            "violations": violations,
            "refused": result.get("refused", False),
            "query": prompt,
        }
    )