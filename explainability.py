import re
from transformers import AutoModelForSeq2SeqLM
from transformers import AutoTokenizer

model_name = "google/flan-t5-small"
tokenizer = AutoTokenizer.from_pretrained( model_name)
model = AutoModelForSeq2SeqLM.from_pretrained(model_name)


def is_repetitive_text(text):
    words = re.findall(r"\b[\w'-]+\b",text.lower())
    if len(words) < 8:
        return True

    unique_ratio = len(set(words)) / len(words)
    if unique_ratio < 0.35:
        return True

    repeated_phrases = re.findall(
        r"(.{12,80}?)"
        r"(?:\s+\1){2,}",
        text,
        re.IGNORECASE
    )
    if repeated_phrases:
        return True

    trigrams = [
        tuple(words[index:index + 3])
        for index in range(len(words) - 2)
    ]

    if trigrams:
        most_common_count = max(
            trigrams.count(trigram)
            for trigram in set(trigrams)
        )

        if most_common_count >= 4:
            return True

    return False


def is_usable_ai_summary(text):
    text = str(text or "").strip()
    word_count = len(text.split())

    if word_count < 8:
        return False

    if word_count > 100:
        return False

    if is_repetitive_text(text):
        return False

    unwanted_patterns = [
        "the citations for the citations",
        "trust score trust score",
        "factual claims factual claims",
        "citation citation citation"
    ]

    lower = text.lower()

    if any( pattern in lower for pattern in unwanted_patterns):
        return False

    return True


def generate_ai_explanation(
    trust_score,
    classified_claims,
    fact_results,
    bias_result,
    citation_result
):
    factual_claims = [
        item for item in classified_claims
        if item["label"] == "factual claim"
    ]

    review_claims = [
        item for item in fact_results
        if item["status"] != (
            "Strong semantic match"
        )
    ]

    biased_words = bias_result.get(
        "biased_words",
        []
    )

    top_emotion = bias_result.get(
        "top_emotion",
        "unknown"
    )

    bias_score = bias_result.get(
        "bias_risk_score",
        0
    )

    citation_level = citation_result.get(
        "level",
        "unknown"
    )

    citation_score = citation_result.get(
        "overall_score",
        0
    )

    prompt = f"""
                Summarize this reliability assessment in two short sentences.
                Do not repeat information.
                Do not claim that semantic similarity proves factual truth.

                Trust score: {trust_score}/100
                Factual claims: {len(factual_claims)}
                Claims needing review: {len(review_claims)}
                Dominant emotion: {top_emotion}
                Bias risk: {bias_score}/100
                Citation quality: {citation_level}
                Citation score: {citation_score}/100
    """

    try:
        inputs = tokenizer(
            prompt,
            return_tensors="pt",
            truncation=True,
            max_length=512
        )

        outputs = model.generate(
            **inputs,
            max_new_tokens=80,
            num_beams=4,
            no_repeat_ngram_size=3,
            repetition_penalty=1.3,
            early_stopping=True,
            do_sample=False
        )

        ai_text = tokenizer.decode(outputs[0],skip_special_tokens=True).strip()

    except Exception:
        ai_text = ""

    explanation = (f"The content received a trust score "f"of {trust_score}/100.\n\n")

    explanation += (f"The system detected "f"{len(factual_claims)} factual claim(s). ")

    if not factual_claims:
        explanation += (
            "No statements were selected for "
            "semantic fact verification."
        )

    elif not fact_results:
        explanation += (
            "The factual claims could not be "
            "verified against an available "
            "reference source."
        )

    elif review_claims:
        explanation += (
            f"{len(review_claims)} claim(s) did not "
            f"have a strong semantic match with "
            f"the available evidence."
        )

    else:
        explanation += (
            "All checked claims had a strong "
            "semantic match with the retrieved "
            "evidence."
        )

    explanation += (
        "\n\nSemantic similarity measures how "
        "closely two texts are related. It does "
        "not independently prove factual truth."
    )

    explanation += (
        f'\n\nThe dominant emotional tone was '
        f'"{top_emotion}", with a bias risk '
        f"score of {bias_score}/100."
    )

    if biased_words:
        explanation += (
            "\nEmotionally loaded or potentially "
            "biased language was detected, including: "
            + ", ".join(biased_words)
            + "."
        )

    else:
        explanation += (
            "\nNo strong loaded keywords were detected."
        )

    explanation += (
        f'\n\nCitation quality was rated as '
        f'"{citation_level}", with a citation '
        f"score of {citation_score}/100."
    )

    explanation += ("\n\nOverall recommendation: ")

    if trust_score >= 75:
        if factual_claims and citation_score == 0:
            explanation += (
                "the text has relatively strong "
                "reliability signals, but its factual "
                "claims should be checked because no "
                "clear citations were detected."
            )
        else:
            explanation += (
                "the content appears mostly reliable, "
                "but important claims should still "
                "be checked."
            )

    elif trust_score >= 50:
        explanation += (
            "the content should be used with caution "
            "because some claims, citations, or "
            "language signals require review."
        )

    else:
        explanation += (
            "the content should not be fully trusted "
            "without additional verification."
        )

    if is_usable_ai_summary(ai_text):
        explanation += (f"\n\nAI-generated summary: {ai_text}")

    return explanation