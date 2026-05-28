"""
LangSmith tracing configuration for the JusticeVault pipeline.

LangGraph nodes trace automatically when these env vars are set:
    LANGCHAIN_TRACING_V2=true
    LANGCHAIN_API_KEY=ls__...
    LANGCHAIN_PROJECT=justice-vault   (optional, defaults below)

Call configure_tracing() once at oracle startup. That's it —
every graph run, every retrieval call, every Claude completion
will appear as a nested trace in LangSmith.
"""
import os


def configure_tracing(project: str = "justice-vault") -> bool:
    """
    Enable LangSmith tracing if credentials are present.
    Returns True if tracing is active, False otherwise.
    Safe to call when LangSmith is not installed — degrades gracefully.
    """
    api_key = os.getenv("LANGCHAIN_API_KEY", "")
    tracing_on = os.getenv("LANGCHAIN_TRACING_V2", "false").lower() == "true"

    if not api_key or not tracing_on:
        print("📊 LangSmith: tracing off (set LANGCHAIN_API_KEY + LANGCHAIN_TRACING_V2=true to enable)")
        return False

    os.environ["LANGCHAIN_PROJECT"] = os.getenv("LANGCHAIN_PROJECT", project)
    print(f"📊 LangSmith: tracing active → project '{os.environ['LANGCHAIN_PROJECT']}'")
    return True
