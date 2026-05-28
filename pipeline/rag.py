"""
RAG pipeline: chunk → embed → store in ChromaDB → retrieve → generate brief.
Replaces the single-shot full-PDF Claude call with cited, retrieved answers.
"""
import os
import random
import time

import anthropic
import chromadb
from langchain_text_splitters import RecursiveCharacterTextSplitter
from pypdf import PdfReader

try:
    from langsmith import traceable
except ImportError:
    def traceable(**_kw):
        def _wrap(fn): return fn
        return _wrap

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CHROMA_DIR = os.path.join(BASE_DIR, "chroma_db")

CHUNK_SIZE = 1000
CHUNK_OVERLAP = 200
TOP_K = 5
MAX_CONTEXT_CHUNKS = 12

BRIEF_PROMPT_TEMPLATE = """\
You are an expert legal assistant. Based on the following retrieved excerpts from a legal evidence document, produce a formal Judicial Case Brief.

Use this exact structure with bold section labels:
**Parties Involved:** (names and roles of all parties)
**Key Claims:** (main factual or legal claims made)
**Date of Incident / Relevance:** (all relevant dates and why they matter)
**Summary:** (2–3 bullet points for the judge)

Cite the excerpt index in brackets (e.g. [1], [3]) when you draw on a specific passage.

RETRIEVED DOCUMENT EXCERPTS:

{context}
"""

_RETRIEVAL_QUERIES = [
    "parties involved plaintiff defendant petitioner respondent",
    "key claims allegations charges legal arguments",
    "dates timeline incident occurrence filing",
    "evidence facts circumstances background",
]

_chroma_client: chromadb.PersistentClient | None = None


def _get_client() -> chromadb.PersistentClient:
    global _chroma_client
    if _chroma_client is None:
        os.makedirs(CHROMA_DIR, exist_ok=True)
        _chroma_client = chromadb.PersistentClient(path=CHROMA_DIR)
    return _chroma_client


def _get_collection(case_id: int) -> chromadb.Collection:
    return _get_client().get_or_create_collection(
        name=f"case_{case_id}",
        metadata={"hnsw:space": "cosine"},
    )


def _extract_text(file_path: str) -> str:
    reader = PdfReader(file_path)
    return "\n".join(page.extract_text() or "" for page in reader.pages)


@traceable(name="ingest_document", run_type="tool")
def ingest_document(file_path: str, case_id: int) -> int:
    """
    Chunk a PDF and store embeddings in ChromaDB.
    Returns the number of chunks stored.
    Idempotent — clears any existing chunks for the same case_id first.
    """
    print(f"📄 RAG: Extracting text from document...")
    text = _extract_text(file_path)
    if not text.strip():
        raise ValueError(f"No extractable text in {file_path}")

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        separators=["\n\n", "\n", ". ", " ", ""],
    )
    chunks = splitter.split_text(text)
    print(f"✂️  RAG: Split into {len(chunks)} chunks")

    collection = _get_collection(case_id)

    # Clear stale data from a previous ingest of the same case
    existing = collection.get()
    if existing["ids"]:
        collection.delete(ids=existing["ids"])

    collection.add(
        documents=chunks,
        ids=[f"c{case_id}_chunk_{i}" for i in range(len(chunks))],
        metadatas=[
            {"case_id": case_id, "chunk_index": i, "source": os.path.basename(file_path)}
            for i in range(len(chunks))
        ],
    )
    print(f"💾 RAG: {len(chunks)} chunks stored in ChromaDB (case_{case_id})")
    return len(chunks)


@traceable(name="retrieve_chunks", run_type="retriever")
def retrieve_chunks(case_id: int, query: str, top_k: int = TOP_K) -> list[str]:
    """Return the top_k most relevant chunks for a query."""
    collection = _get_collection(case_id)
    count = collection.count()
    if count == 0:
        return []
    results = collection.query(
        query_texts=[query],
        n_results=min(top_k, count),
    )
    return results["documents"][0]


@traceable(name="generate_brief", run_type="chain")
def generate_brief(case_id: int, ai_client: anthropic.Anthropic) -> str:
    """
    Multi-query retrieval → Claude brief generation.
    Runs 4 targeted queries, deduplicates chunks, sends assembled context to Claude.
    """
    print(f"🔍 RAG: Retrieving relevant chunks across {len(_RETRIEVAL_QUERIES)} queries...")

    seen: set[str] = set()
    context_chunks: list[str] = []
    for query in _RETRIEVAL_QUERIES:
        for chunk in retrieve_chunks(case_id, query, top_k=3):
            if chunk not in seen and len(context_chunks) < MAX_CONTEXT_CHUNKS:
                seen.add(chunk)
                context_chunks.append(chunk)

    print(f"📚 RAG: {len(context_chunks)} unique chunks assembled for context")

    numbered = "\n\n".join(f"[{i+1}] {chunk}" for i, chunk in enumerate(context_chunks))
    prompt = BRIEF_PROMPT_TEMPLATE.format(context=numbered)

    print(f"🤖 RAG: Generating brief with Claude...")
    attempts, max_attempts = 0, 5
    while attempts < max_attempts:
        try:
            response = ai_client.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=1024,
                messages=[{"role": "user", "content": prompt}],
            )
            return response.content[0].text
        except anthropic.RateLimitError:
            attempts += 1
            wait = (2 ** attempts) + random.random()
            print(f"⏳ Rate limit. Retry {attempts}/{max_attempts} in {wait:.1f}s...")
            time.sleep(wait)
        except Exception as exc:
            print(f"❌ Claude error: {exc}")
            raise

    return "❌ Error: Maximum retry attempts reached."


def ingest_text(text: str, case_id: int) -> int:
    """
    Chunk raw text and store in ChromaDB.
    Used by the eval runner so tests don't need real PDFs.
    """
    if not text.strip():
        raise ValueError("Empty text provided to ingest_text")
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        separators=["\n\n", "\n", ". ", " ", ""],
    )
    chunks = splitter.split_text(text)
    collection = _get_collection(case_id)
    existing = collection.get()
    if existing["ids"]:
        collection.delete(ids=existing["ids"])
    collection.add(
        documents=chunks,
        ids=[f"c{case_id}_chunk_{i}" for i in range(len(chunks))],
        metadatas=[{"case_id": case_id, "chunk_index": i} for i in range(len(chunks))],
    )
    return len(chunks)
