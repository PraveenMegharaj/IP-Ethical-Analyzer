import re
from transformers import pipeline

claim_model = pipeline(
    "zero-shot-classification",
    model="typeform/distilbert-base-uncased-mnli"
)

LABELS = [
    "factual claim",
    "opinion",
    "speculation"
]


FACTUAL_PATTERNS = [
    re.compile(r"\baccording\s+to\b", re.IGNORECASE),

    re.compile(
        r"\b(?:study|studies|research|report|reports|data|evidence)\b"
        r".{0,80}\b(?:show|shows|showed|find|finds|found|indicate|"
        r"indicates|reported|demonstrate|demonstrates)\b",
        re.IGNORECASE
    ),

    re.compile(
        r"\b\d+(?:\.\d+)?\s*(?:%|percent|million|billion|years?|"
        r"months?|days?|hours?)\b",
        re.IGNORECASE
    ),

    re.compile(r"\b(?:19|20)\d{2}\b"),

    re.compile(
        r"\b(?:causes?|increases?|decreases?|reduces?|prevents?|"
        r"leads?\s+to|results?\s+in)\b",
        re.IGNORECASE
    )
]


def classify_claim(sentence):
    result = claim_model(sentence, LABELS)
    scores = dict(zip(result["labels"], result["scores"]))

    label = result["labels"][0]

    if any(pattern.search(sentence) for pattern in FACTUAL_PATTERNS):
        label = "factual claim"

    return {
        "sentence": sentence,
        "label": label,
        "confidence": round(scores[label], 3)
    }


def classify_all_claims(sentences):
    return [classify_claim(sentence) for sentence in sentences]