"""
citation_quality.py

1. Registered domain / suffix class   — gov, edu, int, ac.uk, etc.
2. URL hygiene                        — HTTPS, clean path, low tracking noise.
3. Domain pattern                     — academic/news/institutional/weak patterns.
4. Nearby context                     — only words close to the URL can boost it.
5. Evidence signals                   — DOI, date, author/reporter, references.
6. Risk caps                          — social/blog/rumour sources cannot score high.

"""

from __future__ import annotations

import re
from urllib.parse import parse_qs, urlparse

try:
    import tldextract
except ImportError:
    tldextract = None

if tldextract:
    domain_extractor = tldextract.TLDExtract(suffix_list_urls=())
else:
    domain_extractor = None


QUALITY_THRESHOLDS = {
    "high": 75,
    "medium": 50,
}

WEIGHTS = {
    "suffix": 0.28,
    "hygiene": 0.18,
    "domain_pattern": 0.24,
    "evidence": 0.18,
    "near_context": 0.12,
}

SUFFIX_SCORES = {
    "gov": 92,
    "mil": 90,
    "edu": 86,
    "ac": 84,
    "int": 86,
    "org": 60,
    "com": 50,
    "net": 48,
    "io": 45,
    "news": 58,
}
SUFFIX_DEFAULT_SCORE = 42

WEAK_PLATFORM_DOMAINS = {
    "reddit.com",
    "facebook.com",
    "instagram.com",
    "tiktok.com",
    "x.com",
    "twitter.com",
    "medium.com",
    "blogspot.com",
    "wordpress.com",
    "substack.com",
    "quora.com",
    "pinterest.com",
    "youtube.com",
}

BLOG_PLATFORM_DOMAINS = {
    "medium.com",
    "blogspot.com",
    "wordpress.com",
    "substack.com",
    "ghost.io",
}

WEAK_DOMAIN_WORDS = {
    "rumour",
    "rumor",
    "gossip",
    "fanpage",
    "unofficial",
    "viral",
    "clickbait",
    "leak",
    "exposed",
}

POSITIVE_DOMAIN_PATTERNS = [
    (
        r"journal|journals|academic|scholar|pubmed|arxiv|ssrn|doi|"
        r"nature\.com|thelancet|springer|sciencedirect|wiley|cell\.com|"
        r"nejm\.org|bmj\.com|jama|plos|frontiersin",
        88,
        "Academic or scholarly domain pattern",
    ),
    (
        r"reuters|apnews|associatedpress|afp|bbc|npr|pbs|dw\.com|"
        r"france24|aljazeera|abc\.net|rte\.ie",
        80,
        "Recognized professional news domain pattern",
    ),
    (
        r"cdc\.gov|nih\.gov|who\.int|ecdc\.europa|ema\.europa|"
        r"fda\.gov|mhra\.gov|rki\.de",
        92,
        "Health authority domain pattern",
    ),
    (
        r"unicef|undp|unesco|oecd|worldbank|imf\.org|eurostat|europa\.eu",
        86,
        "Intergovernmental or institutional domain pattern",
    ),
    (
        r"ourworldindata|gapminder|census\.gov|data\.gov|eurostat",
        80,
        "Data or statistics source pattern",
    ),
    (
        r"official|federation|association|league|club|ministry|department|agency",
        68,
        "Official or organizational domain wording",
    ),
]

NEGATIVE_DOMAIN_PATTERNS = [
    (
        r"blogspot|wordpress\.com|medium\.com|substack|ghost\.io",
        25,
        "Blog or newsletter platform",
    ),
    (
        r"reddit|twitter|x\.com|facebook|instagram|tiktok|youtube|quora",
        20,
        "Social media, forum, or user-generated platform",
    ),
    (
        r"rumou?r|gossip|fanpage|unofficial|clickbait|viral|leak",
        25,
        "Weak credibility wording in domain",
    ),
]

AUTHORITY_CONTEXT_WORDS = {
    "official",
    "statement",
    "report",
    "statistics",
    "stats",
    "dataset",
    "annual report",
    "press release",
    "government",
    "ministry",
    "department",
    "university",
    "journal",
    "peer reviewed",
    "research",
    "clinical trial",
    "federation",
    "association",
    "league",
    "club statement",
    "match report",
}

REFERENCE_CONTEXT_WORDS = {
    "references",
    "bibliography",
    "cited",
    "citation",
    "source",
    "sources",
    "according to",
    "reported by",
    "published by",
}

TOPIC_RULES = {
    "sports": {
        "topic_words": {
            "football", "soccer", "goal", "match", "league", "player",
            "club", "transfer", "fifa", "uefa", "premier league",
            "champions league", "world cup",
        },
        "authority_words": {
            "official", "league", "association", "federation", "club",
            "governing body", "competition", "stats", "match report",
        },
    },
    "health": {
        "topic_words": {
            "health", "disease", "vaccine", "medicine", "clinical",
            "patient", "virus", "treatment", "symptom", "infection",
        },
        "authority_words": {
            "health organization", "health organisation", "hospital", "clinic",
            "medical", "journal", "research", "government", "public health",
            "clinical trial",
        },
    },
    "science": {
        "topic_words": {
            "research", "study", "paper", "experiment", "dataset",
            "method", "scientific", "model", "analysis",
        },
        "authority_words": {
            "journal", "doi", "conference", "university", "research institute",
            "publication", "peer reviewed", "study",
        },
    },
    "news": {
        "topic_words": {
            "report", "breaking", "election", "war", "minister", "president",
            "economy", "latest", "announced", "statement",
        },
        "authority_words": {
            "news", "press", "agency", "reporting", "journalist", "correspondent",
        },
    },
    "technology": {
        "topic_words": {
            "software", "ai", "machine learning", "model", "github",
            "release", "version", "security", "vulnerability", "api",
        },
        "authority_words": {
            "documentation", "official", "release notes", "repository",
            "security advisory", "developer", "technical report",
        },
    },
}

NAMED_SOURCE_RULES = [
    (re.compile(r"\bworld\s+health\s+organization\b", re.IGNORECASE), "World Health Organization (WHO)", ["who.int"]),
    (re.compile(r"\bWHO\b"), "World Health Organization (WHO)", ["who.int"]),
    (re.compile(r"\bunicef\b", re.IGNORECASE), "UNICEF", ["unicef.org"]),
    (re.compile(r"\bunited\s+nations\b(?!\s+university)", re.IGNORECASE), "United Nations", ["un.org"]),
    (re.compile(r"\bthe\s+lancet\b|\blancet\b", re.IGNORECASE), "The Lancet", ["thelancet.com"]),
    (re.compile(r"\bnature(?:\s+medicine|\s+communications|\s+climate)?\b(?!\s+valley)(?!\s+conservancy)", re.IGNORECASE), "Nature", ["nature.com"]),
    (re.compile(r"\breuters\b", re.IGNORECASE), "Reuters", ["reuters.com"]),
    (re.compile(r"\bassociated\s+press\b|\bap\s+news\b", re.IGNORECASE), "Associated Press / AP News", ["apnews.com"]),
    (re.compile(r"\bbbc(?:\s+news)?\b", re.IGNORECASE), "BBC", ["bbc.com", "bbc.co.uk"]),
    (re.compile(r"\bour\s+world\s+in\s+data\b", re.IGNORECASE), "Our World in Data", ["ourworldindata.org"]),
    (re.compile(r"\bcenters?\s+for\s+disease\s+control\b|\bCDC\b"), "Centers for Disease Control and Prevention", ["cdc.gov"]),
    (re.compile(r"\bnational\s+institutes?\s+of\s+health\b|\bNIH\b"), "National Institutes of Health", ["nih.gov"]),
]
NAMED_SOURCE_SCORE = 70

URL_PATTERN = re.compile(
    r"(?:https?://[^\s<>\])}\"']+|www\.[^\s<>\])}\"']+|(?<!@)\b(?:[a-zA-Z0-9-]+\.)+[a-zA-Z]{2,}(?:/[^\s<>\])}\"']*)?)"
)

DOI_PATTERN = re.compile(
    r"\b10\.\d{4,9}/[-._;()/:A-Z0-9]+\b",
    re.IGNORECASE
)

DATE_PATTERNS = [
    re.compile(r"\b\d{4}-\d{2}-\d{2}\b"),
    re.compile(r"\b\d{1,2}/\d{1,2}/\d{4}\b"),
    re.compile(
        r"\b\d{1,2}\s+(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)"
        r"[a-z]*\s+\d{4}\b",
        re.IGNORECASE
    ),
    re.compile(
        r"\b(january|february|march|april|may|june|july|august|"
        r"september|october|november|december)\s+\d{1,2},?\s+\d{4}\b",
        re.IGNORECASE
    ),
]

AUTHOR_PATTERNS = [
    re.compile(r"\bby\s+[A-Z][a-z]+"),
    re.compile(r"\bauthor\b", re.IGNORECASE),
    re.compile(r"\bwritten\s+by\b", re.IGNORECASE),
    re.compile(r"\breported\s+by\b", re.IGNORECASE),
    re.compile(r"\bedited\s+by\b", re.IGNORECASE),
]

SECOND_LEVEL_SUFFIXES = {
    "ac",
    "co",
    "com",
    "edu",
    "gov",
    "mil",
    "net",
    "org",
}


def _clean_url(url: str) -> str:
    return (url or "").strip().rstrip(".,;:!?)]}'\"")


def normalize_url(url: str) -> str:
    cleaned = _clean_url(url)

    if not cleaned:
        return ""

    if cleaned.startswith(("http://", "https://")):
        return cleaned

    return "https://" + cleaned


def extract_urls(text: str) -> list[str]:
    if not text:
        return []

    urls = [
        _clean_url(match.group(0))
        for match in URL_PATTERN.finditer(text)
    ]

    return list(dict.fromkeys(
        url for url in urls
        if url
    ))


def _domain_matches(domain: str, base_domain: str) -> bool:
    return (
        domain == base_domain
        or domain.endswith("." + base_domain)
    )


def _parse_domain(url: str) -> dict:
    normalized = normalize_url(url)
    parsed = urlparse(normalized)
    host = (parsed.hostname or "").lower().removeprefix("www.")

    if not host:
        return {
            "normalized": normalized,
            "parsed": parsed,
            "host": "",
            "registered_domain": "",
            "suffix": "",
            "suffix_class": "",
        }

    if domain_extractor:
        extracted = domain_extractor(host)

        if extracted.domain and extracted.suffix:
            registered_domain = (
                f"{extracted.domain}.{extracted.suffix}"
            )
        else:
            registered_domain = host

        suffix = extracted.suffix or ""
    else:
        parts = host.split(".")

        if (
            len(parts) >= 3
            and parts[-2] in SECOND_LEVEL_SUFFIXES
        ):
            registered_domain = ".".join(parts[-3:])
            suffix = ".".join(parts[-2:])
        elif len(parts) >= 2:
            registered_domain = ".".join(parts[-2:])
            suffix = parts[-1]
        else:
            registered_domain = host
            suffix = ""

    suffix_parts = suffix.split(".") if suffix else []

    if (
        suffix_parts
        and suffix_parts[0] in {"ac", "edu", "gov", "mil"}
    ):
        suffix_class = suffix_parts[0]
    else:
        suffix_class = (
            suffix_parts[-1]
            if suffix_parts
            else ""
        )

    return {
        "normalized": normalized,
        "parsed": parsed,
        "host": host,
        "registered_domain": registered_domain,
        "suffix": suffix,
        "suffix_class": suffix_class,
    }


def _contains_any(text: str, words: set[str]) -> bool:
    return any(
        re.search(
            rf"(?<!\w){re.escape(word)}(?!\w)",
            text or "",
            re.IGNORECASE
        )
        for word in words
    )


def _matches_domain_pattern(domain: str, pattern: str) -> bool:
    return re.search(
        rf"(?:^|[.-])(?:{pattern})(?=$|[.-])",
        domain or "",
        re.IGNORECASE
    ) is not None


def _find_near_url_context(
    text: str,
    url: str,
    domain: str,
    window: int = 110
) -> str:
    if not text:
        return ""

    candidates = [
        url,
        normalize_url(url),
        domain
    ]

    lower_candidates = [
        candidate.lower()
        for candidate in candidates
        if candidate
    ]

    lines = text.splitlines()

    for index, line in enumerate(lines):
        lower_line = line.lower()

        if any(
            candidate in lower_line
            for candidate in lower_candidates
        ):
            selected = []

            if index > 0:
                previous_line = lines[index - 1].strip()

                if (
                    previous_line
                    and not extract_urls(previous_line)
                ):
                    selected.append(previous_line)

            selected.append(line.strip())

            if index + 1 < len(lines):
                next_line = lines[index + 1].strip()

                if (
                    next_line
                    and not extract_urls(next_line)
                ):
                    selected.append(next_line)

            return " ".join(
                part for part in selected
                if part
            )

    lower_text = text.lower()

    for candidate in lower_candidates:
        position = lower_text.find(candidate)

        if position != -1:
            start = max(0, position - window)
            end = min(
                len(text),
                position + len(candidate) + window
            )

            return text[start:end]

    return ""


def _has_doi(text: str) -> bool:
    return DOI_PATTERN.search(text or "") is not None


def _has_date_signal(text: str) -> bool:
    return any(
        pattern.search(text or "")
        for pattern in DATE_PATTERNS
    )


def _has_author_signal(text: str) -> bool:
    return any(
        pattern.search(text or "")
        for pattern in AUTHOR_PATTERNS
    )


def _detect_topic(text: str) -> str | None:
    best_topic = None
    best_score = 0

    for topic, rules in TOPIC_RULES.items():
        score = sum(
            1 for word in rules["topic_words"]
            if re.search(
                rf"(?<!\w){re.escape(word)}(?!\w)",
                text or "",
                re.IGNORECASE
            )
        )

        if score > best_score:
            best_score = score
            best_topic = topic

    return best_topic


def _classify_quality(score: float) -> str:
    if score >= QUALITY_THRESHOLDS["high"]:
        return "High source quality"

    if score >= QUALITY_THRESHOLDS["medium"]:
        return "Medium source quality"

    return "Low source quality"


def _score_suffix(
    suffix_class: str
) -> tuple[int, list[str]]:
    score = SUFFIX_SCORES.get(
        suffix_class.lower(),
        SUFFIX_DEFAULT_SCORE
    )

    reasons = []

    if suffix_class in {
        "gov",
        "mil",
        "edu",
        "ac",
        "int"
    }:
        reasons.append(
            f"Institutional suffix detected: .{suffix_class}"
        )
    elif suffix_class == "org":
        reasons.append(
            "Organization suffix detected: .org"
        )
    elif suffix_class:
        reasons.append(
            f"General suffix detected: .{suffix_class}"
        )
    else:
        reasons.append(
            "No clear domain suffix detected"
        )

    return score, reasons


def _score_url_hygiene(
    parsed,
    original_url: str = ""
) -> tuple[int, list[str]]:
    score = 50
    reasons = []
    original_url = (
        original_url or ""
    ).strip().lower()

    if original_url.startswith("https://"):
        score += 20
        reasons.append("Uses HTTPS")
    elif original_url.startswith("http://"):
        score -= 10
        reasons.append(
            "Uses HTTP instead of HTTPS"
        )
    else:
        reasons.append(
            "URL scheme was not explicitly provided"
        )

    path_depth = len([
        part for part in parsed.path.split("/")
        if part
    ])

    if path_depth <= 4:
        score += 10
        reasons.append(
            "URL path is reasonably clean"
        )
    elif path_depth > 8:
        score -= 10
        reasons.append(
            "URL path is very deep"
        )

    tracking_params = {
        "utm_source",
        "utm_medium",
        "utm_campaign",
        "fbclid",
        "gclid",
        "ref"
    }

    query_keys = set(
        parse_qs(parsed.query).keys()
    )

    if query_keys & tracking_params:
        score -= 10
        reasons.append(
            "URL contains tracking parameters"
        )

    return max(0, min(100, score)), reasons


def _score_domain_pattern(
    registered_domain: str
) -> tuple[int, list[str], bool, str | None]:
    reasons = []
    positive_scores = []
    negative_scores = []
    source_type = None

    for (
        pattern,
        score,
        reason
    ) in POSITIVE_DOMAIN_PATTERNS:
        if _matches_domain_pattern(
            registered_domain,
            pattern
        ):
            positive_scores.append(score)
            reasons.append(reason)

            if score >= 80:
                source_type = "authority_pattern"

    for (
        pattern,
        score,
        reason
    ) in NEGATIVE_DOMAIN_PATTERNS:
        if _matches_domain_pattern(
            registered_domain,
            pattern
        ):
            negative_scores.append(score)
            reasons.append(reason)
            source_type = "weak_pattern"

    weak_by_platform = any(
        _domain_matches(
            registered_domain,
            domain
        )
        for domain in WEAK_PLATFORM_DOMAINS
    )

    if weak_by_platform:
        negative_scores.append(20)
        reasons.append(
            "Known weak/social/blog platform"
        )
        source_type = "weak_platform"

    if negative_scores:
        return (
            min(negative_scores),
            reasons,
            True,
            source_type
        )

    if positive_scores:
        return (
            max(positive_scores),
            reasons,
            False,
            source_type
        )

    return (
        50,
        ["No strong domain-pattern signal detected"],
        False,
        source_type
    )


def _score_evidence(
    near_context: str,
    full_text: str
) -> tuple[int, list[str]]:
    score = 50
    reasons = []

    if _has_doi(near_context):
        score += 25
        reasons.append(
            "DOI detected near citation"
        )

    if _has_date_signal(near_context):
        score += 10
        reasons.append(
            "Date signal near citation"
        )

    if _has_author_signal(near_context):
        score += 10
        reasons.append(
            "Author/reporter signal near citation"
        )

    if _contains_any(
        near_context,
        REFERENCE_CONTEXT_WORDS
    ):
        score += 8
        reasons.append(
            "Reference/source wording near citation"
        )

    if not reasons:
        reasons.append(
            "No strong evidence metadata detected near citation"
        )

    return max(0, min(100, score)), reasons


def _score_near_context(
    near_context: str,
    full_text: str
) -> tuple[int, list[str]]:
    score = 50
    reasons = []

    if _contains_any(
        near_context,
        AUTHORITY_CONTEXT_WORDS
    ):
        score += 18
        reasons.append(
            "Authority wording appears near the citation"
        )

    topic = _detect_topic(full_text)

    if (
        topic
        and _contains_any(
            near_context,
            TOPIC_RULES[topic]["authority_words"]
        )
    ):
        score += 14
        reasons.append(
            f"Citation context matches authority signals for {topic}"
        )

    if _contains_any(
        near_context,
        WEAK_DOMAIN_WORDS
    ):
        score -= 18
        reasons.append(
            "Weak credibility wording appears near the citation"
        )

    if not reasons:
        reasons.append(
            "No strong nearby-context signal detected"
        )

    return max(0, min(100, score)), reasons


def _apply_risk_caps(
    score: float,
    registered_domain: str,
    pattern_is_weak: bool
) -> tuple[float, list[str]]:
    reasons = []
    capped_score = score

    is_weak_platform = any(
        _domain_matches(
            registered_domain,
            domain
        )
        for domain in WEAK_PLATFORM_DOMAINS
    )

    is_blog_platform = any(
        _domain_matches(
            registered_domain,
            domain
        )
        for domain in BLOG_PLATFORM_DOMAINS
    )

    has_weak_word = _contains_any(
        registered_domain,
        WEAK_DOMAIN_WORDS
    )

    if (
        is_weak_platform
        and capped_score > 55
    ):
        capped_score = 55
        reasons.append(
            "Score capped because the source is a "
            "social/forum/user-generated platform"
        )

    if (
        is_blog_platform
        and capped_score > 62
    ):
        capped_score = 62
        reasons.append(
            "Score capped because the source is a "
            "blog/newsletter platform"
        )

    if (
        pattern_is_weak
        or has_weak_word
    ) and capped_score > 60:
        capped_score = 60
        reasons.append(
            "Score capped because weak credibility "
            "signals were detected"
        )

    return capped_score, reasons


def score_single_url(
    url: str,
    context_text: str = "",
    full_text: str = ""
) -> dict:
    parsed_data = _parse_domain(url)

    normalized = parsed_data["normalized"]
    parsed = parsed_data["parsed"]
    registered_domain = (
        parsed_data["registered_domain"]
    )
    suffix_class = parsed_data["suffix_class"]

    full_text = (
        full_text
        or context_text
        or ""
    )

    near_context = (
        context_text
        or _find_near_url_context(
            full_text,
            url,
            registered_domain
        )
    )

    suffix_score, suffix_reasons = (
        _score_suffix(suffix_class)
    )

    hygiene_score, hygiene_reasons = (
        _score_url_hygiene(
            parsed,
            url
        )
    )

    (
        pattern_score,
        pattern_reasons,
        pattern_is_weak,
        source_type
    ) = _score_domain_pattern(
        registered_domain
    )

    evidence_score, evidence_reasons = (
        _score_evidence(
            near_context,
            full_text
        )
    )

    context_score, context_reasons = (
        _score_near_context(
            near_context,
            full_text
        )
    )

    signals = {
        "suffix": suffix_score,
        "hygiene": hygiene_score,
        "domain_pattern": pattern_score,
        "evidence": evidence_score,
        "near_context": context_score,
    }

    raw_score = sum(
        signals[key] * WEIGHTS[key]
        for key in WEIGHTS
    )

    final_score, cap_reasons = (
        _apply_risk_caps(
            raw_score,
            registered_domain,
            pattern_is_weak
        )
    )

    reasons = []

    for group in [
        suffix_reasons,
        hygiene_reasons,
        pattern_reasons,
        evidence_reasons,
        context_reasons,
        cap_reasons
    ]:
        for reason in group:
            if reason not in reasons:
                reasons.append(reason)

    return {
        "type": "url",
        "label": url,
        "url": normalized,
        "domain": registered_domain,
        "quality": _classify_quality(
            final_score
        ),
        "score": round(final_score, 1),
        "signals": signals,
        "source_type": (
            source_type
            or "unknown_or_general"
        ),
        "reasons": reasons,
    }


def extract_named_sources(
    text: str
) -> list[dict]:
    if not text:
        return []

    seen = set()
    sources = []

    for (
        regex,
        display_name,
        domain_hints
    ) in NAMED_SOURCE_RULES:
        if regex.search(text):
            key = display_name.lower()

            if key in seen:
                continue

            seen.add(key)

            sources.append({
                "type": "named_source",
                "label": display_name,
                "url": None,
                "domain": None,
                "quality": _classify_quality(
                    NAMED_SOURCE_SCORE
                ),
                "score": NAMED_SOURCE_SCORE,
                "signals": {
                    "named_source": NAMED_SOURCE_SCORE
                },
                "source_type": (
                    "named_source_without_url"
                ),
                "domain_hints": domain_hints,
                "reasons": [
                    (
                        "Recognized named source mentioned, "
                        "but no direct URL was provided"
                    ),
                    (
                        "Named source mentions are displayed "
                        "but do not increase the overall "
                        "citation score"
                    ),
                ],
            })

    return sources


def _deduplicate_sources(
    url_sources: list[dict],
    named_sources: list[dict]
) -> list[dict]:
    url_domains = {
        source.get("domain")
        for source in url_sources
        if source.get("domain")
    }

    deduped_named = []

    for named in named_sources:
        hints = named.get(
            "domain_hints",
            []
        )

        already_has_url = any(
            any(
                _domain_matches(
                    domain,
                    hint
                )
                for hint in hints
            )
            for domain in url_domains
        )

        if not already_has_url:
            named_copy = dict(named)
            named_copy.pop(
                "domain_hints",
                None
            )
            deduped_named.append(
                named_copy
            )

    return url_sources + deduped_named


def _calculate_overall_score(
    sources: list[dict]
) -> float:
    url_sources = [
        source for source in sources
        if source.get("type") == "url"
    ]

    if not url_sources:
        return 0.0

    average = sum(
        source["score"]
        for source in url_sources
    ) / len(url_sources)

    weak_count = sum(
        1 for source in url_sources
        if source["score"] < 40
    )

    high_count = sum(
        1 for source in url_sources
        if source["score"] >= 75
    )

    final = average

    if weak_count >= 2:
        final -= 8

    if high_count >= 2:
        final += 4

    return round(
        max(0, min(100, final)),
        2
    )


def score_citations(
    text: str,
    extra_urls: list[str] | None = None
) -> dict:
    extra_urls = extra_urls or []

    visible_urls = extract_urls(text)

    all_urls = list(dict.fromkeys(
        visible_urls + extra_urls
    ))

    url_sources = []

    for url in all_urls:
        domain_info = _parse_domain(url)

        if not domain_info["registered_domain"]:
            continue

        near_context = _find_near_url_context(
            text,
            url,
            domain_info["registered_domain"]
        )

        url_sources.append(
            score_single_url(
                url,
                near_context,
                text
            )
        )

    named_sources = extract_named_sources(
        text
    )

    all_sources = _deduplicate_sources(
        url_sources,
        named_sources
    )

    if not all_sources:
        return {
            "overall_score": 0,
            "level": "No citations found",
            "sources": [],
        }

    if not url_sources:
        return {
            "overall_score": 0,
            "level": (
                "No verifiable URL citations found"
            ),
            "sources": all_sources,
        }

    overall_score = _calculate_overall_score(
        all_sources
    )

    return {
        "overall_score": overall_score,
        "level": _classify_quality(
            overall_score
        ),
        "sources": all_sources,
    }