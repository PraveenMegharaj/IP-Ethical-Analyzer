import re
import requests

from bs4 import BeautifulSoup
from urllib.parse import urlparse, quote
from functools import lru_cache

from sentence_transformers import SentenceTransformer, util


embedding_model = SentenceTransformer("all-MiniLM-L6-v2")


TRUSTED_DOMAINS = [
    "who.int",
    "unicef.org",
    "un.org",
    "europa.eu",
    "thelancet.com",
    "nature.com",
    "reuters.com",
    "bbc.com",
    "apnews.com",
    "cdc.gov",
    "nih.gov"
]


TRUSTED_SUFFIXES = [
    ".gov",
    ".edu",
    ".gov.uk",
    ".ac.uk",
    ".edu.au"
]


def extract_urls(text):
    pattern = (
        r'https?://[^\s)>\]]+'
        r'|www\.[^\s)>\]]+'
        r'|\b(?:[a-zA-Z0-9-]+\.)+[a-zA-Z]{2,}\b'
    )

    return re.findall(pattern, text)


def normalize_url(url):
    if not url.startswith("http"):
        return "https://" + url

    return url


def get_domain(url):
    normalized = normalize_url(url)
    parsed = urlparse(normalized)

    return parsed.netloc.replace("www.", "").lower()


def is_trusted_domain(domain):
    if any(
        domain == trusted or domain.endswith("." + trusted)
        for trusted in TRUSTED_DOMAINS
    ):
        return True

    return any(
        domain.endswith(suffix)
        for suffix in TRUSTED_SUFFIXES
    )


def get_trusted_urls(full_text, source_links):
    visible_urls = extract_urls(full_text)

    all_urls = list(dict.fromkeys(
        visible_urls + source_links
    ))

    trusted_urls = []

    for url in all_urls:
        normalized = normalize_url(url)
        domain = get_domain(normalized)

        if is_trusted_domain(domain):
            trusted_urls.append(normalized)

    return trusted_urls


@lru_cache(maxsize=100)
def fetch_webpage_text(url):
    try:
        response = requests.get(
            url,
            timeout=12,
            headers={
                "User-Agent": "EthicalAnalyserPrototype/1.0"
            }
        )

        if response.status_code != 200:
            return ""

        content_type = response.headers.get("Content-Type", "").lower()

        if "pdf" in content_type:
            return ""

        soup = BeautifulSoup(response.text, "html.parser")

        for tag in soup([
            "script",
            "style",
            "noscript",
            "header",
            "footer",
            "nav",
            "aside"
        ]):
            tag.decompose()

        text = soup.get_text(" ", strip=True)
        text = re.sub(r"\s+", " ", text).strip()

        return text[:20000]

    except Exception:
        return ""


def collect_direct_trusted_url_evidence(full_text, source_links):
    trusted_urls = get_trusted_urls(
        full_text,
        source_links
    )

    evidence = []

    for url in trusted_urls[:3]:
        page_text = fetch_webpage_text(url)

        if page_text:
            evidence.append({
                "source": url,
                "text": page_text,
                "evidence_type": "Direct trusted source link"
            })

    return evidence


def search_wikipedia(claim):
    search_url = "https://en.wikipedia.org/w/api.php"

    params = {
        "action": "query",
        "list": "search",
        "srsearch": claim,
        "format": "json",
        "utf8": 1,
        "srlimit": 1
    }

    try:
        response = requests.get(
            search_url,
            params=params,
            timeout=8,
            headers={
                "User-Agent": "EthicalAnalyserPrototype/1.0"
            }
        )

        if response.status_code == 200:
            data = response.json()
            results = data.get("query", {}).get("search", [])

            if results:
                return results[0]["title"]

    except Exception:
        pass

    return None


def get_wikipedia_summary(title):
    if not title:
        return {
            "source": None,
            "text": ""
        }

    safe_title = quote(title.replace(" ", "_"))
    url = f"https://en.wikipedia.org/api/rest_v1/page/summary/{safe_title}"

    try:
        response = requests.get(
            url,
            timeout=8,
            headers={
                "User-Agent": "EthicalAnalyserPrototype/1.0"
            }
        )

        if response.status_code == 200:
            data = response.json()

            return {
                "source": data.get("content_urls", {})
                              .get("desktop", {})
                              .get("page", ""),
                "text": data.get("extract", "")
            }

    except Exception:
        pass

    return {
        "source": None,
        "text": ""
    }


def retrieve_wikipedia_evidence(claim):
    title = search_wikipedia(claim)
    summary = get_wikipedia_summary(title)

    if not summary["text"]:
        return []

    return [{
        "source": summary["source"],
        "text": summary["text"],
        "evidence_type": "Wikipedia search fallback"
    }]


def split_into_chunks(text, max_chars=450):
    sentences = re.split(r'(?<=[.!?])\s+', text)

    chunks = []
    current = ""

    for sentence in sentences:
        sentence = sentence.strip()

        if not sentence:
            continue

        if len(current) + len(sentence) + 1 <= max_chars:
            current += " " + sentence if current else sentence
        else:
            if current:
                chunks.append(current)

            current = sentence

    if current:
        chunks.append(current)

    return chunks[:120]


def best_semantic_match(claim, evidence_items):
    chunks = []

    for item in evidence_items:
        for chunk in split_into_chunks(item["text"]):
            chunks.append({
                "source": item["source"],
                "chunk": chunk,
                "evidence_type": item["evidence_type"]
            })

    if not chunks:
        return None

    claim_embedding = embedding_model.encode(
        claim,
        convert_to_tensor=True
    )

    chunk_texts = [
        item["chunk"]
        for item in chunks
    ]

    chunk_embeddings = embedding_model.encode(
        chunk_texts,
        convert_to_tensor=True
    )

    similarities = util.cos_sim(
        claim_embedding,
        chunk_embeddings
    )[0]

    best_index = int(similarities.argmax())
    best_similarity = float(similarities[best_index])

    chosen = chunks[best_index]

    return {
        "source": chosen["source"],
        "summary": chosen["chunk"],
        "similarity": round(best_similarity, 3),
        "evidence_type": chosen["evidence_type"]
    }


def similarity_to_status(similarity):
    if similarity >= 0.70:
        return "Strong semantic match"

    if similarity >= 0.50:
        return "Partial semantic match / needs review"

    return "Weak semantic match"


def should_skip_claim_for_verification(claim):
    lower = claim.lower().strip()

    skip_patterns = [
        "source:",
        "available at:",
        "citation:",
        "references:",
        "this is for informational purposes only",
        "for medical advice or diagnosis, consult a professional",
        "gemini said",
        "claude said",
        "chatgpt said"
    ]

    if any(pattern in lower for pattern in skip_patterns):
        return True

    if len(claim.split()) <= 3 and extract_urls(claim):
        return True

    return False


def format_match_result(claim, match):
    return {
        "claim": claim,
        "status": similarity_to_status(match["similarity"]),
        "similarity": match["similarity"],
        "source": match["source"],
        "summary": match["summary"],
        "evidence_type": match["evidence_type"]
    }


def verify_claim_semantically(claim, direct_evidence):
    direct_match = best_semantic_match(
        claim,
        direct_evidence
    )

    best_match = direct_match

    if not direct_match or direct_match["similarity"] < 0.50:
        wiki_evidence = retrieve_wikipedia_evidence(claim)
        wiki_match = best_semantic_match(claim, wiki_evidence)

        if wiki_match and (
            not best_match
            or wiki_match["similarity"] > best_match["similarity"]
        ):
            best_match = wiki_match

    if best_match and best_match["similarity"] >= 0.30:
        return format_match_result(
            claim,
            best_match
        )

    return {
        "claim": claim,
        "status": "No reference source found",
        "similarity": 0,
        "source": None,
        "summary": "",
        "evidence_type": "No evidence retrieved"
    }


def verify_factual_claims(classified_claims, full_text, source_links=None):
    if source_links is None:
        source_links = []

    factual_claims = [
        item["sentence"]
        for item in classified_claims
        if item["label"] == "factual claim"
    ]

    filtered_claims = [
        claim for claim in factual_claims
        if not should_skip_claim_for_verification(claim)
    ]

    direct_evidence = collect_direct_trusted_url_evidence(
        full_text,
        source_links
    )

    results = []

    for claim in filtered_claims[:8]:
        results.append(
            verify_claim_semantically(
                claim,
                direct_evidence
            )
        )

    return results