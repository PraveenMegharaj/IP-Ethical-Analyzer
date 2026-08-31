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


STRONG_FACTUAL_PATTERNS = [
    re.compile(
        r"\baccording\s+to\b",
        re.IGNORECASE
    ),

    re.compile(
        r"\b(?:study|studies|research|report|reports|data|evidence)\b"
        r".{0,80}\b(?:show|shows|showed|find|finds|found|indicate|"
        r"indicates|reported|demonstrate|demonstrates)\b",
        re.IGNORECASE
    ),

    re.compile(
        r"\b\d+(?:\.\d+)?\s*(?:%|percent|million|billion|trillion|"
        r"years?|months?|weeks?|days?|hours?|minutes?|seconds?|"
        r"kilometres?|kilometers?|metres?|meters?|degrees?)\b",
        re.IGNORECASE
    ),

    re.compile(
        r"\b(?:19|20)\d{2}\b"
    ),

    re.compile(
        r"\b(?:causes?|increases?|decreases?|reduces?|prevents?|"
        r"leads?\s+to|results?\s+in)\b",
        re.IGNORECASE
    )
]


FACTUAL_RELATION_PATTERNS = [
    re.compile(
        r"\b(?:is|are|was|were|has|have|contains?|consists?|"
        r"includes?|uses?|produces?|provides?|requires?|"
        r"occurs?|exists?|belongs?|orbits?|rotates?|"
        r"measures?|weighs?|covers?|located|founded|published)\b",
        re.IGNORECASE
    )
]


OPINION_PATTERNS = [
    re.compile(
        r"\b(?:i think|i believe|in my opinion|in my view|"
        r"personally|it seems to me)\b",
        re.IGNORECASE
    ),

    re.compile(
        r"\b(?:best|worst|beautiful|ugly|amazing|terrible|"
        r"wonderful|boring|excellent|awful|better|worse)\b",
        re.IGNORECASE
    )
]


SPECULATION_PATTERNS = [
    re.compile(
        r"\b(?:may|might|could|perhaps|possibly|probably|"
        r"likely|unlikely|it is possible|it is unclear|"
        r"appears to|seems to)\b",
        re.IGNORECASE
    )
]


def matches_any_pattern(sentence, patterns):
    return any(
        pattern.search(sentence)
        for pattern in patterns
    )


def looks_like_declarative_fact(sentence):
    words = sentence.split()

    if len(words) < 5:
        return False

    if matches_any_pattern(sentence,OPINION_PATTERNS):
        return False

    if matches_any_pattern(sentence,SPECULATION_PATTERNS):
        return False

    return matches_any_pattern( sentence,FACTUAL_RELATION_PATTERNS)


def classify_claim(sentence):
    result = claim_model(sentence,LABELS)

    scores = dict(zip(
        result["labels"],
        result["scores"]
    ))

    factual_score = scores.get(
        "factual claim",
        0
    )

    opinion_score = scores.get(
        "opinion",
        0
    )

    speculation_score = scores.get(
        "speculation",
        0
    )

    label = result["labels"][0]
    confidence = result["scores"][0]
    classification_reason = "zero-shot model"

    if matches_any_pattern(sentence, STRONG_FACTUAL_PATTERNS):
        label = "factual claim"
        confidence = max(
            factual_score,
            0.90
        )
        classification_reason = (
            "strong factual language pattern"
        )

    elif matches_any_pattern(sentence,OPINION_PATTERNS):
        label = "opinion"
        confidence = max(
            opinion_score,
            0.85
        )
        classification_reason = (
            "opinion language pattern"
        )

    elif matches_any_pattern(sentence,SPECULATION_PATTERNS):
        label = "speculation"
        confidence = max(
            speculation_score,
            0.85
        )
        classification_reason = (
            "uncertainty or speculative language"
        )

    elif looks_like_declarative_fact(sentence):
        label = "factual claim"
        confidence = max(
            factual_score,
            0.72
        )
        classification_reason = (
            "declarative factual statement"
        )

    elif (
        factual_score >= 0.35
        and factual_score >= opinion_score - 0.08
        and factual_score >= speculation_score - 0.08
    ):
        label = "factual claim"
        confidence = factual_score
        classification_reason = (
            "factual model score above threshold"
        )

    return {
        "sentence": sentence,
        "label": label,
        "confidence": round(
            confidence,
            3
        ),
        "classification_reason": (
            classification_reason
        )
    }


def classify_all_claims(sentences):
    return [
        classify_claim(sentence)
        for sentence in sentences
    ]