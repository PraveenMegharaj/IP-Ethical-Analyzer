import re
from collections import defaultdict
from transformers import pipeline

emotion_model = pipeline(
    "text-classification",
    model="j-hartmann/emotion-english-distilroberta-base",
    top_k=None
)

BIAS_KEYWORDS = [
    "shocking", "disaster", "obviously", "clearly",
    "worst", "best", "always", "never",
    "dangerous", "fake", "corrupt", "evil",
    "panic", "threat", "destroy"
]

KEYWORD_PATTERNS = {
    word: re.compile(
        rf"\b{re.escape(word)}\b",
        re.IGNORECASE
    )
    for word in BIAS_KEYWORDS
}


def detect_bias(text):
    chunks = [
        text[index:index + 500]
        for index in range(0, min(len(text), 2500), 500)
        if text[index:index + 500].strip()
    ]

    found_keywords = [
        word for word, pattern in KEYWORD_PATTERNS.items()
        if pattern.search(text)
    ]

    if not chunks:
        return {
            "top_emotion": "unknown",
            "emotion_confidence": 0,
            "biased_words": found_keywords,
            "bias_risk_score": min(len(found_keywords) * 10, 100)
        }

    try:
        model_results = emotion_model(chunks)
    except Exception:
        model_results = []

    if model_results and isinstance(model_results[0], dict):
        model_results = [model_results]

    emotion_totals = defaultdict(float)

    for chunk_result in model_results:
        for item in chunk_result:
            emotion_totals[item["label"]] += item["score"]

    emotions = [
        {
            "label": label,
            "score": score / len(chunks)
        }
        for label, score in emotion_totals.items()
    ]

    emotions = sorted(
        emotions,
        key=lambda item: item["score"],
        reverse=True
    )

    if emotions:
        top_emotion = emotions[0]
    else:
        top_emotion = {
            "label": "unknown",
            "score": 0
        }

    emotional_risk = 0

    if (
        top_emotion["label"].lower() in ["anger", "fear", "disgust"]
        and found_keywords
    ):
        emotional_risk += 30

    emotional_risk += len(found_keywords) * 10
    emotional_risk = min(emotional_risk, 100)

    return {
        "top_emotion": top_emotion["label"],
        "emotion_confidence": round(top_emotion["score"], 3),
        "biased_words": found_keywords,
        "bias_risk_score": emotional_risk
    }