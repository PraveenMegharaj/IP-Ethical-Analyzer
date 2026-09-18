import os

from dotenv import load_dotenv

load_dotenv()

# ---------------------------------------------------------------------------
# Language model (wording only — never used to decide any score)
#
# The tool uses a language model only to read the user's description, ask the
# clarifying questions and write plain-language explanations. All assessment
# (FAIR via F-UJI, FAIR-R2L checklist, licence analysis) is rule-based and
# deterministic. We prefer a European-developed model; reliability comes first.
# ---------------------------------------------------------------------------
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "mistral")
LLM_MODEL = os.getenv("LLM_MODEL", "mistral-small-latest")
MISTRAL_API_KEY = os.getenv("MISTRAL_API_KEY")
MISTRAL_API_URL = os.getenv(
    "MISTRAL_API_URL",
    "https://api.mistral.ai/v1/chat/completions",
)

# Deprecated: kept only for backward compatibility. The tool no longer calls
# OpenAI; set MISTRAL_API_KEY instead.
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# ---------------------------------------------------------------------------
# Scope flags
#
# The "Trust / AI-generated-text" analysis (Hugging Face claim, bias and
# semantic-verification models) is OUT of the core resource-assessment scope
# and parked behind this flag. Left off, the heavy models are never imported.
# ---------------------------------------------------------------------------
ENABLE_TRUST_ANALYSIS = (
    os.getenv("ENABLE_TRUST_ANALYSIS", "false").lower() == "true"
)
