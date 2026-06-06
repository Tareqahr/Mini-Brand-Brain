import os
import json
import urllib.request
from pathlib import Path
import chromadb
from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
OLLAMA_BASE_URL = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "llama3.2")
LOW_SIMILARITY_THRESHOLD = 0.3  # absolute floor; relative filter in query() does the real work

_USE_OLLAMA = not ANTHROPIC_API_KEY

if not _USE_OLLAMA:
    import anthropic


class BrandBrain:
    def __init__(self):
        self.ingested_docs: dict[str, int] = {}

        self._ef = SentenceTransformerEmbeddingFunction(model_name="all-MiniLM-L6-v2")
        self._chroma = chromadb.EphemeralClient()
        self._collection = self._chroma.get_or_create_collection(
            name="brand_docs",
            embedding_function=self._ef,
            metadata={"hnsw:space": "cosine"},
        )

        # Restore ingested_docs from existing collection so sidebar shows correctly after restart
        existing = self._collection.get()
        for meta in existing["metadatas"]:
            src = meta["source"]
            self.ingested_docs[src] = self.ingested_docs.get(src, 0) + 1

        self.anthropic_client = (
            anthropic.Anthropic(api_key=ANTHROPIC_API_KEY) if not _USE_OLLAMA else None
        )
        tone_path = Path(__file__).parent / "brand_config" / "Tone of voice.md"
        self._tone_doc = tone_path.read_text(encoding="utf-8") if tone_path.exists() else ""

    def _chunk_text(self, text: str, chunk_size: int = 250, overlap: int = 40) -> list[str]:
        words = text.split()
        chunks = []
        i = 0
        while i < len(words):
            chunk = " ".join(words[i : i + chunk_size])
            if chunk.strip():
                chunks.append(chunk)
            i += chunk_size - overlap
        return chunks

    def ingest_text(self, text: str, filename: str) -> int:
        new_chunks = self._chunk_text(text)
        if not new_chunks:
            return 0
        ids = [f"{filename}::chunk::{i}" for i in range(len(new_chunks))]
        metadatas = [{"source": filename, "chunk_index": i} for i in range(len(new_chunks))]
        self._collection.upsert(documents=new_chunks, metadatas=metadatas, ids=ids)
        self.ingested_docs[filename] = len(new_chunks)
        return len(new_chunks)

    def ingest_file(self, file) -> tuple[int, str]:
        """Returns (chunk_count, error_message). error_message is empty on success."""
        filename = file.name
        if filename.endswith(".pdf"):
            try:
                import pypdf
            except ImportError:
                return 0, "pypdf is not installed — run: pip install pypdf"
            try:
                file.seek(0)
                reader = pypdf.PdfReader(file)
                text = "\n".join(page.extract_text() or "" for page in reader.pages).strip()
            except Exception as e:
                return 0, f"Could not read PDF: {e}"
            if not text:
                return 0, "No extractable text found — this PDF may be a scanned image."
        else:
            file.seek(0)
            raw = file.read()
            try:
                text = raw.decode("utf-8")
            except UnicodeDecodeError:
                text = raw.decode("latin-1")
        n = self.ingest_text(text, filename)
        return n, ""

    def load_sample_docs(self):
        sample_dir = Path(__file__).parent / "sample_docs"
        if not sample_dir.exists():
            return
        for f in sorted(sample_dir.glob("*.md")):
            probe_id = f"{f.name}::chunk::0"
            try:
                probe = self._collection.get(ids=[probe_id])
                already_indexed = bool(probe["ids"])
            except Exception:
                already_indexed = False
            if not already_indexed:
                try:
                    text = f.read_text(encoding="utf-8")
                    self.ingest_text(text, f.name)
                except Exception:
                    pass

    def retrieve(self, question: str, n_results: int = 5) -> list[dict]:
        count = self._collection.count()
        if count == 0:
            return []
        results = self._collection.query(
            query_texts=[question],
            n_results=min(n_results, count),
        )
        hits = []
        for doc, meta, distance in zip(
            results["documents"][0],
            results["metadatas"][0],
            results["distances"][0],
        ):
            similarity = 1 - distance  # cosine distance → similarity score
            if similarity >= LOW_SIMILARITY_THRESHOLD:
                hits.append({
                    "chunk": doc,
                    "source": meta["source"],
                    "score": round(similarity, 3),
                })
        return hits

    def query(self, question: str, n_results: int = 5) -> dict:
        if self._collection.count() == 0:
            return {
                "answer": "No brand documents have been loaded yet. Please upload documents first.",
                "citations": [],
                "grounded": False,
                "refused": True,
            }

        hits = self.retrieve(question, n_results)

        if not hits:
            return {
                "answer": "I could not find relevant information about this in the brand documents. Please consult the brand team directly.",
                "citations": [],
                "grounded": False,
                "refused": True,
            }

        # Relative filter: drop chunks more than 0.15 below the top score.
        # Prevents every Celonis doc from showing up for every Celonis-adjacent query.
        top_score = max(h["score"] for h in hits)
        hits = [h for h in hits if h["score"] >= top_score - 0.15]

        # Full context for LLM (filtered hits only)
        context = "\n\n---\n\n".join(
            f"[Source: {h['source']}]\n{h['chunk']}" for h in hits
        )

        # Deduplicated citations for UI: one entry per source file (highest-scoring chunk)
        seen: dict[str, dict] = {}
        for hit in hits:
            src = hit["source"]
            if src not in seen or hit["score"] > seen[src]["score"]:
                seen[src] = hit
        citations = [
            {"source": h["source"], "excerpt": h["chunk"]}
            for h in sorted(seen.values(), key=lambda h: h["score"], reverse=True)
        ]

        if _USE_OLLAMA:
            # Small models cannot reliably follow complex competing rules — keep it minimal
            system_prompt = (
                "You answer questions using only the source documents provided by the user. "
                "When the answer is in the sources, state it clearly and concisely. "
                "Only reply 'This information is not in the brand documents' when the sources "
                "genuinely do not contain the answer."
            )
        else:
            tone_section = (
                f"WRITING STYLE — apply this to how you write, not what you include:\n{self._tone_doc}\n\n"
                if self._tone_doc else ""
            )
            system_prompt = (
                "You are the Celonis Brand Brain — a precise, governed brand assistant.\n\n"
                "GROUNDING RULES — these take priority over everything else:\n"
                "1. Answer using ONLY the source documents provided in the user message.\n"
                "2. If the question cannot be answered from those sources, say exactly: "
                "'This information is not in the brand documents.'\n"
                "3. Never invent facts, statistics, or quotes not found in the sources.\n"
                "4. If the answer IS present in the source documents, you MUST provide it. "
                "Do not withhold or refuse an answer that the sources support.\n\n"
                + tone_section
            )

        user_prompt = (
            f"SOURCE DOCUMENTS:\n{context}\n\n"
            f"QUESTION: {question}\n\n"
            "Answer using only the information in the sources above. "
            "Match the length and format to exactly what the question asks for. "
            "Do not copy source document headings or structure. "
            "After each sentence that uses information from a source, add the filename in brackets, "
            "for example: [Brand FAQs.md]. Only cite the specific file the sentence draws from."
        )

        try:
            if _USE_OLLAMA:
                answer = self._query_ollama(system_prompt, user_prompt)
            else:
                response = self.anthropic_client.messages.create(
                    model="claude-sonnet-4-20250514",
                    max_tokens=600,
                    temperature=0.1,
                    system=system_prompt,
                    messages=[{"role": "user", "content": user_prompt}],
                )
                answer = response.content[0].text
        except ConnectionRefusedError:
            answer = (
                f"Could not connect to Ollama at {OLLAMA_BASE_URL}. "
                "Make sure Ollama is running (`ollama serve`) and the model is pulled "
                f"(`ollama pull {OLLAMA_MODEL}`)."
            )
        except Exception as e:
            answer = f"Error generating response: {e}"

        return {
            "answer": answer,
            "citations": citations,
            "grounded": True,
            "refused": False,
        }

    def _query_ollama(self, system_prompt: str, user_prompt: str) -> str:
        payload = {
            "model": OLLAMA_MODEL,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "stream": False,
            "options": {"num_predict": 600, "temperature": 0.1},
        }
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            f"{OLLAMA_BASE_URL}/api/chat",
            data=data,
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=60) as resp:
            result = json.loads(resp.read().decode("utf-8"))
        return result["message"]["content"]
