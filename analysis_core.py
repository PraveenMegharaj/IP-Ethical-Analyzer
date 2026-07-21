import re

from claim_classifier import classify_all_claims
from fact_verification import verify_factual_claims
from bias_classifier import detect_bias
from citation_quality import score_citations
from explainability import generate_ai_explanation


def split_sentences(text):
    text = re.sub(
        r'(?m)^\s*(?:[-*•]|\d+[.)])\s+',
        '',
        text
    )

    sentences = re.split(
        r'(?<=[.!?])\s+|\n+',
        text
    )

    return [
        sentence.strip()
        for sentence in sentences
        if sentence.strip()
    ]


def calculate_final_trust_score(
    classified_claims,
    fact_results,
    bias_result,
    citation_result
):
    score = 100

    # ---------------------------------------------------
    # 1. Fact verification penalties
    # ---------------------------------------------------
    for item in fact_results:
        status = item.get("status", "")

        if status == "Strong semantic match":
            score -= 0

        elif status == "Partial semantic match / needs review":
            score -= 6

        elif status == "Weak semantic match":
            score -= 12

        elif status == "No reference source found":
            score -= 4

        else:
            score -= 6

    # ---------------------------------------------------
    # 2. Bias / emotional language penalty
    # ---------------------------------------------------
    score -= bias_result["bias_risk_score"] * 0.25

    # ---------------------------------------------------
    # 3. Citation quality adjustment
    # ---------------------------------------------------
    citation_score = citation_result["overall_score"]

    factual_claims = [
        item for item in classified_claims
        if item["label"] == "factual claim"
    ]

    if factual_claims:
        if citation_score == 0:
            score -= 20

        elif citation_score < 45:
            score -= 10

        elif citation_score >= 75:
            score += 5

    # ---------------------------------------------------
    # 4. If factual claims exist but no verification ran
    # ---------------------------------------------------
    if len(factual_claims) > 0 and len(fact_results) == 0:
        score -= 10

    return max(0, min(100, round(score)))


def build_dashboard_cards(
    classified_claims,
    fact_results,
    bias_result,
    citation_result
):
    factual_claims = [
        item for item in classified_claims
        if item.get("label") == "factual claim"
    ]

    review_claims = [
        item for item in fact_results
        if item.get("status") != "Strong semantic match"
    ]

    bias_score = bias_result.get("bias_risk_score", 0)
    citation_score = citation_result.get("overall_score", 0)

    if bias_score >= 70:
        bias_status = "High Risk"
    elif bias_score >= 40:
        bias_status = "Medium Risk"
    else:
        bias_status = "Low Risk"

    if citation_score >= 75:
        citation_status = "Strong Sources"
    elif citation_score >= 45:
        citation_status = "Moderate Sources"
    elif citation_score > 0:
        citation_status = "Weak Sources"
    else:
        citation_status = "No Sources Found"

    return [
        {
            "key": "claims",
            "title": "Claim Classification",
            "value": len(classified_claims),
            "status": f"{len(factual_claims)} factual claims",
            "description": "Classifies sentences as factual claims, opinions, or other text."
        },
        {
            "key": "facts",
            "title": "Fact Verification",
            "value": len(fact_results),
            "status": f"{len(review_claims)} need review",
            "description": "Checks factual claims against available evidence and semantic similarity."
        },
        {
            "key": "bias",
            "title": "Bias / Emotion",
            "value": f"{bias_score}/100",
            "status": bias_status,
            "description": "Detects emotional tone, biased wording, and manipulation signals."
        },
        {
            "key": "citations",
            "title": "Citation Quality",
            "value": f"{citation_score}/100",
            "status": citation_status,
            "description": "Evaluates whether the text provides reliable and clear sources."
        }
    ]


def analyze_full_text(text, source_links=None):
    if source_links is None:
        source_links = []

    sentences = split_sentences(text)

    classified_claims = classify_all_claims(
        sentences
    )

    fact_results = verify_factual_claims(
        classified_claims=classified_claims,
        full_text=text,
        source_links=source_links
    )

    bias_result = detect_bias(text)

    citation_result = score_citations(
        text=text,
        extra_urls=source_links
    )

    trust_score = calculate_final_trust_score(
        classified_claims,
        fact_results,
        bias_result,
        citation_result
    )

    ai_explanation = generate_ai_explanation(
        trust_score,
        classified_claims,
        fact_results,
        bias_result,
        citation_result
    )

    dashboard_cards = build_dashboard_cards(
        classified_claims,
        fact_results,
        bias_result,
        citation_result
    )

    return {
        "classified_claims": classified_claims,
        "fact_results": fact_results,
        "bias_result": bias_result,
        "citation_result": citation_result,
        "trust_score": trust_score,
        "ai_explanation": ai_explanation,
        "dashboard_cards": dashboard_cards
    }