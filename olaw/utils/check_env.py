import os

REQUIRED_ENV_VARS = [
    "RATE_LIMIT_STORAGE_URI",
    "API_MODELS_RATE_LIMIT",
    "API_EXTRACT_SEARCH_STATEMENT_RATE_LIMIT",
    "API_SEARCH_RATE_LIMIT",
    "API_COMPLETE_RATE_LIMIT",
    "COURT_LISTENER_MAX_RESULTS",
    "EXTRACT_SEARCH_STATEMENT_PROMPT",
    "COURT_LISTENER_API_URL",
    "COURT_LISTENER_BASE_URL",
    "TEXT_COMPLETION_BASE_PROMPT",
    "TEXT_COMPLETION_RAG_PROMPT",
    "TEXT_COMPLETION_HISTORY_PROMPT",
]

def check_env(strict: bool = True) -> bool:
    """
    Verifies that all required environment variables are defined.
    If strict=True (default), raises Exception if any variable is missing.
    If strict=False, prints warnings but allows app to continue.
    """
    missing = [var for var in REQUIRED_ENV_VARS if var not in os.environ or not os.environ[var].strip()]

    if missing:
        msg = f"⚠️  Missing environment variables: {', '.join(missing)}"
        if strict:
            raise Exception(msg)
        else:
            print(msg)
            return False

    print("✅ All required environment variables are set.")
    return True
