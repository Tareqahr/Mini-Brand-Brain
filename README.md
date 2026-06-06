# Mini Brand Brain

A prototype RAG assistant that turns a set of brand documents into a governed, queryable knowledge system. Upload brand guidelines, FAQs, and positioning documents, then ask any brand question in natural language. The system retrieves only the relevant passages, grounds its answer exclusively in those sources, and enforces a set of hard brand rules on every response.

---

## Requirements

**Python 3.10 or later** is required. Verify it is installed by opening a terminal and typing `python --version`.

On first run, the embedding model (`all-MiniLM-L6-v2`, ~80 MB) downloads automatically. This only happens once.

For the AI, you have two options:

**Option A — Claude API (recommended)**
Get an API key at [console.anthropic.com](https://console.anthropic.com). No additional installs needed beyond the requirements file.

**Option B — Local Ollama (no API key, fully offline)**
Download Ollama from [ollama.com](https://ollama.com), then pull a model once:
```
ollama pull llama3.2
```
This downloads ~2 GB and only needs to happen once. Start Ollama before running the app with `ollama serve`.

---

## How to Run

**Step 1 — Install dependencies**

```
pip install -r requirements.txt
```

Only required the first time.

**Step 2 — Configure your AI**

Option A — set your API key in the terminal:
```
set ANTHROPIC_API_KEY=your_key_here
```

Option B — if using Ollama, make sure it is already running (`ollama serve`) before the next step. No environment variable needed.

**Step 3 — Start the app**

```
streamlit run app.py
```

Open [http://localhost:8501](http://localhost:8501). A set of sample Celonis brand documents loads automatically on first run.

---

## Workflow

Please see [Celonis Task 3_ Lucidchart.pdf](Celonis%20Task%203_%20Lucidchart.pdf) in this repo for the workflow map.

---

Please see Notes.md for my general thoughts on my implementation. Also, please see Examples.md for example questions and answers.

---

## Technical Explanation of the Workflow

**Step 1 — Load Documents**
Pre-stored documents are chunked and vectorized on startup (Celosphere, Guidelines, FAQ, Messaging, Process Intelligence). Additional documents can be uploaded at any time using the sidebar uploader.

**Step 2 — Build Index**
Each chunk is embedded into a vector using `all-MiniLM-L6-v2` and stored in a local Chroma vector database, together with a pointer to its source file. This makes retrieval transparent, because every answer can be traced back to its exact source chunk.

**Step 3 — User Question**
The user types a question in the chat interface. The question is vectorized using the same embedding model.

**Step 4 — Matching**
Cosine similarity is computed between the question vector and all stored chunk vectors. The top results above a similarity threshold are returned. A relative filter then drops any chunk whose score is more than 0.15 below the top score. This prevents every Celonis-adjacent document from showing up for every Celonis-related query.

**Step 5 — Hit?**
If no chunk clears the threshold, the system tells the user the question cannot be answered from the available documents. No answer is fabricated.

**Step 6 — Retrieve Chunks**
The relevant chunks are assembled into a context block and passed to the LLM.

**Step 7 — Query and Prompt**
The LLM receives the user's question and the retrieved context chunks. Grounding rules in the system prompt instruct it to answer only from the provided sources. For Claude, the Tone of Voice document is also injected as a writing style guide. For Ollama (smaller models), the system prompt is kept minimal to avoid competing instructions confusing the model.

**Step 8 — Generate Answer**
The LLM generates an answer, citing the source filename inline after each sentence that draws from a specific document.

**Step 9 — Constitution Check**
The generated answer is passed through `constitution.py`, which checks it against a set of hard brand rules — forbidden phrases, wrong category labels, banned jargon.

**Step 10 — Violation?**
If a rule is broken, the answer is still shown but the violation is flagged with the specific rule, the triggering phrase, and a suggested correction. High-severity violations are highlighted in red, medium in amber.

**Step 11 — Answer Delivered**
The answer is shown in the chat with inline citations, an expandable Sources panel showing the relevant passage from each source document with query terms highlighted, and the violation panel if applicable. Users can rate the answer with 👍 or 👎.

---

## What Broke, What Was Hard, What Comes Next

**What broke during development**

*Tone of voice document overriding grounding rules.* The Tone of Voice file includes a "Substantive" section — "If we cannot back it up, we do not say it." When this was injected before the grounding rules in the system prompt, the model treated it as a content restriction and refused to answer questions even when the answer was clearly present in the retrieved sources. For example, "Is Celonis an AI company?" would return "This information is not in the brand documents" even though Brand FAQs.md contained the exact answer. Fixed by placing grounding rules first and labelling the tone section explicitly as writing style, not content policy.

*Documents not all loading.* The `BrandBrain` object was created inside a Streamlit `@st.cache_resource` function, and `load_sample_docs()` was called inside the same cached block. On the first run, before the files existed, the cache stored an empty brain. Subsequent runs returned the cached empty brain and never retried the document load. Fixed by calling `load_sample_docs()` outside the cached function so it runs on every page load and can detect newly available files.

*Citations rendering as broken HTML.* The original citation design used `<details>` and `<summary>` HTML tags to make expandable source panels. Streamlit's HTML sanitiser strips those tags, leaving raw broken markup visible in the chat. Fixed by switching to Streamlit's native `st.expander()` component.

*Silent PDF failures.* The PDF ingestion path caught all exceptions and returned 0 with no message. Users uploading a PDF saw nothing — no success, no error, no explanation. Fixed by surfacing the actual exception message and separately detecting the scanned-image case (text extraction returns empty string).

---

**What was genuinely difficult**

*Threshold tuning for a same-topic corpus.* Because every document in the corpus is about Celonis, an absolute similarity threshold cannot distinguish "very relevant" from "somewhat relevant" — everything scores above 0.3. A fixed threshold of 0.45 still let Celosphere conference content show up as a source for a question about Celonis' AI positioning. The fix was a relative threshold: after retrieving the top results, drop any chunk whose score is more than 0.15 below the best score. This adapts automatically to each query regardless of absolute values.

*Small model instruction following.* `llama3.2` (3B parameters) cannot reliably follow a system prompt with several competing sections — grounding rules, tone guidance, and content restrictions all fight each other. The same prompt that works correctly with Claude produces refusals or verbatim document copy-paste with Ollama. The fix was a separate, minimal system prompt for the Ollama path: three sentences, no competing rules, no tone guidance injected.

*Chroma persistent state vs. in-memory tracking.* The app tracks loaded documents in a Python dict (`ingested_docs`) that is rebuilt at startup by reading the Chroma collection. If a document was never indexed into Chroma (e.g. because it was added to the folder after the first run), it would not appear in the dict — and `load_sample_docs()` would skip it because the dict check assumed it was already handled. Fixed by probing Chroma directly for the existence of each file's first chunk rather than relying on the reconstructed dict.

---

**What would be improved next**

1. **Memory.** The system has no conversation memory — each question is answered in isolation. Adding a short rolling context window would let the user ask follow-up questions and refer back to earlier answers.

2. **Multi-user support.** The current architecture is single-user. A real deployment would need session isolation so one user's uploads do not affect another's view.

3. **Evaluation.** There is no way to measure whether the retrieval and answers are actually correct. A set of labelled question-answer pairs, run against the system automatically, would make threshold and prompt tuning principled rather than manual.

---

## What Would Be Needed to Make This Production-Ready

This prototype covers the full pipeline end-to-end. Turning it into a real tool used by a brand team would require:

**Vector database at scale**
Chroma runs locally and handles a small document set well. A production deployment would need a hosted vector store (e.g. Pinecone, Weaviate) that can hold tens of thousands of document chunks, serve multiple users concurrently, and stay available without a laptop running in the background.

**Document ingestion pipeline**
Right now, documents are uploaded manually or pre-loaded from a folder. A real system would integrate with the internal document management platform, automatically pulling updated brand guidelines whenever they change, and running a web crawler to index relevant public pages (e.g. the Celonis website).

**Admin interface and human review layer**
The Brand Constitution rules are currently hardcoded in `constitution.py`. An admin interface would let brand managers update, add, or remove rules without touching code. A human review layer would let a brand owner approve or edit answers before they are used externally — the system provides the draft and the reasoning, the human makes the final call.

**Production infrastructure**
Authentication is missing entirely — anyone with the URL can upload documents or query the brain. A production version needs identity management (SSO), role-based access (who can upload vs. who can only query), cloud deployment so the app runs without a local machine, caching for repeated questions to reduce API costs, and monitoring to track answer quality over time.

**Feedback loop in production**
The current 👍/👎 system writes ratings to a local CSV. In production, this data would flow into a reranking model or fine-tuning pipeline that continuously improves retrieval quality based on which answers users found useful.

**Language support**
Only English is supported. Multi-language support would allow brand teams in other regions to query the same knowledge base in their own language.

**Image understanding**
Documents with diagrams, infographics, or visual brand guidelines cannot be processed. A vision model would be needed to extract meaning from images and include visual brand rules in the knowledge base.

On the technical side, a production version would require: a hosted LLM API (Claude, Gemini, GPT-4, etc.), a hosted embedding model, a cloud vector database, a document store with versioning, a web scraper, authentication and authorisation, and a caching layer for repeated queries.
