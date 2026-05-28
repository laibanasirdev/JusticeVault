"""
LangSmith evaluation runner for JusticeVault RAG pipeline.

Uploads eval_dataset.json to LangSmith, runs the brief-generation pipeline
against each of the 10 test cases, and scores on three dimensions:
  - party_recall       : expected party names found in brief
  - claims_recall      : expected claim keywords found in brief
  - structure_compliance: all 4 required section headers present

Usage:
    export LANGCHAIN_API_KEY=ls__...
    export LANGCHAIN_TRACING_V2=true
    export ANTHROPIC_API_KEY=sk-ant-...
    python tests/run_evals.py
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import anthropic
from langsmith import Client, evaluate

from pipeline.rag import ingest_text, generate_brief
from pipeline.observability import configure_tracing

configure_tracing(project="justice-vault-evals")

DATASET_PATH = os.path.join(os.path.dirname(__file__), "eval_dataset.json")
DATASET_NAME = "JusticeVault-Legal-Brief-Evals-v1"
# High case_id offset so eval cases don't collide with real oracle ingests
_EVAL_ID_OFFSET = 90_000

ai_client = anthropic.Anthropic()

_REQUIRED_HEADERS = [
    "**Parties Involved:**",
    "**Key Claims:**",
    "**Date of Incident",
    "**Summary:**",
]


# ---------------------------------------------------------------------------
# Evaluators
# ---------------------------------------------------------------------------

def party_recall(run, example) -> dict:
    """Fraction of expected parties mentioned in the brief."""
    brief = (run.outputs or {}).get("brief", "").lower()
    parties = (example.outputs or {}).get("expected_parties", [])
    if not parties:
        return {"key": "party_recall", "score": 1.0}
    score = sum(1 for p in parties if p.lower() in brief) / len(parties)
    return {"key": "party_recall", "score": round(score, 2)}


def claims_recall(run, example) -> dict:
    """Fraction of expected claim keywords present in the brief."""
    brief = (run.outputs or {}).get("brief", "").lower()
    keywords = (example.outputs or {}).get("expected_claim_keywords", [])
    if not keywords:
        return {"key": "claims_recall", "score": 1.0}
    score = sum(1 for kw in keywords if kw.lower() in brief) / len(keywords)
    return {"key": "claims_recall", "score": round(score, 2)}


def structure_compliance(run, example) -> dict:
    """1.0 if all 4 required section headers are present, else partial score."""
    brief = (run.outputs or {}).get("brief", "")
    found = sum(1 for h in _REQUIRED_HEADERS if h in brief)
    return {"key": "structure_compliance", "score": round(found / len(_REQUIRED_HEADERS), 2)}


# ---------------------------------------------------------------------------
# Pipeline target
# ---------------------------------------------------------------------------

def run_pipeline(inputs: dict) -> dict:
    """
    Target function for LangSmith evaluate().
    Ingests the document excerpt as text, then generates a brief.
    """
    case_id = _EVAL_ID_OFFSET + inputs["id"]
    ingest_text(inputs["document_excerpt"], case_id)
    brief = generate_brief(case_id, ai_client)
    return {"brief": brief}


# ---------------------------------------------------------------------------
# Dataset setup
# ---------------------------------------------------------------------------

def _ensure_dataset(client: Client, cases: list[dict]) -> str:
    existing = {d.name for d in client.list_datasets()}
    if DATASET_NAME in existing:
        print(f"ℹ️  Using existing LangSmith dataset '{DATASET_NAME}'")
        return DATASET_NAME

    dataset = client.create_dataset(
        DATASET_NAME,
        description="JusticeVault: 10 Pakistani legal document brief-generation test cases",
    )
    client.create_examples(
        inputs=[
            {
                "id":                case["id"],
                "document_excerpt":  case["document_excerpt"],
                "description":       case["description"],
            }
            for case in cases
        ],
        outputs=[
            {
                "expected_parties":        case["expected_parties"],
                "expected_claim_keywords": case["expected_claim_keywords"],
            }
            for case in cases
        ],
        dataset_id=dataset.id,
    )
    print(f"✅ Uploaded {len(cases)} examples to LangSmith dataset '{DATASET_NAME}'")
    return DATASET_NAME


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    api_key = os.getenv("LANGCHAIN_API_KEY", "")
    if not api_key:
        print("❌ LANGCHAIN_API_KEY not set — cannot run LangSmith evaluations.")
        sys.exit(1)

    with open(DATASET_PATH) as f:
        cases = json.load(f)

    client = Client()
    dataset_name = _ensure_dataset(client, cases)

    print(f"\n🧪 Running evaluation on {len(cases)} cases...\n")
    results = evaluate(
        run_pipeline,
        data=dataset_name,
        evaluators=[party_recall, claims_recall, structure_compliance],
        experiment_prefix="justice-vault-v2",
        max_concurrency=2,
    )

    print("\n📊 Evaluation complete — results available in LangSmith UI")
    print(f"   Dataset : {DATASET_NAME}")
    print(f"   Experiment prefix: justice-vault-v2")

    # Print a quick local summary
    scores: dict[str, list[float]] = {}
    for result in results:
        for fb in (result.get("feedback") or []):
            scores.setdefault(fb.key, []).append(fb.score)

    if scores:
        print("\n   Aggregate scores:")
        for metric, vals in scores.items():
            avg = sum(vals) / len(vals)
            print(f"   {metric:25s}: {avg:.2f} (n={len(vals)})")


if __name__ == "__main__":
    main()
