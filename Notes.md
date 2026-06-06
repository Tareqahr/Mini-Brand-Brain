Input: Dummy Content (txt, MD or PDF), Mock brand Guidelines (PDF or MD), public source material (PDF), example documents

How source material is collected and structured: Source material can be added to the brain manually. Otherwise, the brain should pull documents from internal databases, only pulling relevant documents such as brand Guidelines, etc. Can also scrape Websites such as Celonis Website.

How 3–5 short source documents are ingested or referenced: We use a Chroma Vector database with sentence transformer embedding. Each chunk is converted into a Vector and stored in the database.

How a user asks brand-related Questions: The user can ask the brain a Question, the brain will give an answer using his Knowledge base. Citations will be given to prevent hallucinations. The users asks over a Chat interface and can ask any Question wanted.

How the system retrieves relevant source material: Documents are chunked. Each chunk is converted into a Vector. When Information is to be retrieved, the query is chunked and vectorized the same way, and through cosine similarity we compare which chunks are closest to the query. The top scoring chunks Above a treshold are sent to the LLM as the retireved Information. Each chunk has ist soruce linked to Sources can be tracked and checked.

How answers are grounded in the provided Sources: The brain has to always give a source for references, to ensure it only retrieves the relevant chunks. We also set temperature to almost 0 to gurantee deterministic Output. Furthermore prompt guardrails are introduced to ensure Output is grounded in Sources. One time for the System prompt (only answer from Sources) and one time when using the Retrieval threshold that discards too weak Matches.

How citations or source references are shown: Are shown at the end of the answer. Can be expanded. Relevant passages are highlighted for more Transparency.

How simple Brand Constitution rules are applied: Brand rules are enforced by defining a set of rule in the System (Constitution.py). These can be changed by admins but not by document Uploads to Prevent ambiguity Problems.

How unsupported claims are flagged or refused: Claims below a certain threshold (meaning we only found a weak match with brand documents) are discarded to Prevent weak/unsupported Claims. Morever, a prompt guardrail is introduced that the System Needs to clearly state that the Information is not in the provided Sources.

Where human judgement is still needed: Humans still Need to check the answer, the AI provides the documents and why it Chose this answer, the human still Need to check that this is correct before using that Information for anything.

What systems, tools, or APIs would be required in a real Celonis Version: LLM API (Claude, Gemini, ChatGPT, etc.), Embedding model, Vector database (e.g: chroma), Document store, (web scraper), authentication, Caching.