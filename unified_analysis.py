import re
from urllib.parse import urlparse

from analysis_core import analyze_full_text


URL_PATTERN = re.compile(
    r'https?://[^\s<>"\']+'
)


DOI_PATTERN = re.compile(
    r'10\.\d{4,9}/[-._;()/:A-Z0-9]+',
    re.IGNORECASE
)


MAX_RESOURCE_ANALYSES = 3


RESOURCE_MODULES_AVAILABLE = False
RESOURCE_MODULE_ERROR = None


try:
    from content_extractor import ContentExtractor
    from fair_r2l_scorer import FAIRR2LScorer
    from fair_scorer import FAIRScorer
    from licence_analyzer import LicenceAnalyzer
    from rubric_engine import RubricEngine

    extractor = ContentExtractor()
    fair_scorer = FAIRScorer()
    licence_analyzer = LicenceAnalyzer()
    rubric_engine = RubricEngine()
    fair_r2l_scorer = FAIRR2LScorer()

    RESOURCE_MODULES_AVAILABLE = True

except Exception as error:
    RESOURCE_MODULE_ERROR = str(error)


def analyze_unified(
    user_input="",
    text="",
    source_links=None,
    user_role="reuser",
    manual_answers=None
):
    source_links = clean_links(
        source_links or []
    )

    manual_answers = (
        manual_answers
        or {}
    )

    user_input = str(
        user_input or ""
    ).strip()

    text = str(
        text or ""
    ).strip()

    if (
        not text
        and user_input
        and not is_resource_locator(
            user_input
        )
    ):
        text = user_input

    resource_inputs = collect_resource_inputs(
        user_input,
        text,
        source_links
    )

    resources = analyze_resources(
        resource_inputs,
        user_role,
        manual_answers
    )

    trust_text = text
    trust_links = list(
        source_links
    )

    if (
        not trust_text
        and resources
    ):
        artefact = (
            resources[0].get(
                "artefact"
            )
            or {}
        )

        trust_text = get_resource_text(
            artefact
        )

        if (
            artefact.get("url")
            and artefact["url"]
            not in trust_links
        ):
            trust_links.append(
                artefact["url"]
            )

    trust = analyze_trust(
        trust_text,
        trust_links
    )

    primary = (
        resources[0]
        if resources
        else None
    )

    return {
        "input_type": get_input_type(
            text,
            resources
        ),
        "original_input": user_input,
        "text": text,
        "source_links": source_links,
        "trust": trust,
        "resources": resources,
        "primary_resource_index": (
            0
            if resources
            else None
        ),
        "scores": {
            "trust": score_summary(
                trust,
                "Ethical Analyser"
            ),
            "fair": score_summary(
                (
                    primary.get("fair")
                    if primary
                    else None
                ),
                "F-UJI FAIR assessment"
            ),
            "ip": score_summary(
                (
                    primary.get("ip")
                    if primary
                    else None
                ),
                (
                    "Copyright and licence "
                    "assessment"
                )
            ),
            "fair_r2l": score_summary(
                (
                    primary.get("fair_r2l")
                    if primary
                    else None
                ),
                "FAIR-R²L prototype"
            )
        },
        "warnings": build_interaction_warnings(
            trust,
            primary
        ),
        "resource_modules_available": (
            RESOURCE_MODULES_AVAILABLE
        ),
        "resource_module_error": (
            RESOURCE_MODULE_ERROR
        )
    }


def analyze_trust(
    text,
    source_links
):
    text = str(
        text or ""
    ).strip()

    if len(text) < 20:
        return {
            "available": False,
            "score": None,
            "band": "not_applicable",
            "note": (
                "Not enough meaningful text was "
                "available for trust analysis."
            ),
            "details": None
        }

    try:
        details = analyze_full_text(
            text=text,
            source_links=source_links
        )

    except Exception as error:
        return {
            "available": False,
            "score": None,
            "band": "error",
            "note": (
                f"Trust analysis failed: "
                f"{error}"
            ),
            "details": None
        }

    score = details.get(
        "trust_score"
    )

    return {
        "available": score is not None,
        "score": score,
        "band": score_band(score),
        "note": details.get(
            "ai_explanation",
            ""
        ),
        "details": details
    }


def analyze_resources(
    resource_inputs,
    user_role,
    manual_answers
):
    if not RESOURCE_MODULES_AVAILABLE:
        return []

    resources = []

    for resource_input in (
        resource_inputs[
            :MAX_RESOURCE_ANALYSES
        ]
    ):
        try:
            artefact = extractor.extract(
                resource_input
            )

            target = (
                artefact.get("doi")
                or artefact.get("url")
                or resource_input
            )

            fair_result = (
                fair_scorer.score(
                    target,
                    artefact=artefact
                )
                if target
                else None
            )

            licence_result = (
                licence_analyzer.analyze(
                    artefact.get(
                        "licence_string"
                    )
                )
            )

            copyright_result = (
                rubric_engine.compute(
                    artefact,
                    user_role=user_role
                )
            )

            fair_r2l_result = (
                fair_r2l_scorer.score(
                    artefact=artefact,
                    fair_result=fair_result,
                    manual_answers=manual_answers
                )
            )

            resources.append({
                "input": resource_input,
                "available": True,
                "artefact": artefact,
                "fair": fair_result,
                "licence": licence_result,
                "ip": copyright_result,
                "fair_r2l": fair_r2l_result
            })

        except Exception as error:
            resources.append({
                "input": resource_input,
                "available": False,
                "error": str(error),
                "artefact": None,
                "fair": None,
                "licence": None,
                "ip": None,
                "fair_r2l": None
            })

    return resources


def collect_resource_inputs(
    user_input,
    text,
    source_links
):
    values = []

    if (
        user_input
        and is_resource_locator(
            user_input
        )
    ):
        values.append(
            user_input
        )

    values.extend(
        source_links
    )

    values.extend(
        URL_PATTERN.findall(
            text or ""
        )
    )

    values.extend(
        DOI_PATTERN.findall(
            text or ""
        )
    )

    unique = []

    for value in values:
        value = str(
            value
        ).strip().rstrip(
            ".,;)]}"
        )

        if (
            value
            and value not in unique
        ):
            unique.append(
                value
            )

    return unique


def get_resource_text(
    artefact
):
    for key in (
        "raw_text",
        "description",
        "abstract"
    ):
        value = str(
            artefact.get(key)
            or ""
        ).strip()

        if len(value) >= 80:
            return value

    return ""


def clean_links(
    source_links
):
    if not isinstance(
        source_links,
        list
    ):
        return []

    return list(
        dict.fromkeys(
            link.strip()
            for link in source_links
            if (
                isinstance(link, str)
                and link.strip().startswith(
                    (
                        "http://",
                        "https://"
                    )
                )
            )
        )
    )


def is_resource_locator(
    value
):
    value = str(
        value or ""
    ).strip()

    if DOI_PATTERN.search(
        value
    ):
        return True

    if not value.startswith(
        (
            "http://",
            "https://"
        )
    ):
        return False

    try:
        return bool(
            urlparse(value).netloc
        )

    except ValueError:
        return False


def score_summary(
    result,
    method
):
    if not result:
        return {
            "available": False,
            "score": None,
            "band": "not_applicable",
            "method": method
        }

    score = result.get(
        "readiness",
        result.get("score")
    )

    if score is None:
        return {
            "available": False,
            "score": None,
            "band": "not_applicable",
            "method": method
        }

    band = result.get(
        "band"
    )

    if isinstance(
        band,
        dict
    ):
        band = band.get(
            "label",
            "unknown"
        )

    summary = {
        "available": True,
        "score": score,
        "band": (
            band
            or "unknown"
        ),
        "method": (
            result.get("method_label")
            or result.get("method")
            or method
        ),
        "is_estimate": result.get(
            "is_estimate",
            False
        )
    }

    if "completion" in result:
        summary["completion"] = (
            result.get("completion")
        )

    if "classification_label" in result:
        summary["classification"] = (
            result.get(
                "classification_label"
            )
        )

    return summary


def get_input_type(
    text,
    resources
):
    if (
        text
        and resources
    ):
        return "text_with_resources"

    if text:
        return "text"

    if resources:
        return "research_resource"

    return "unknown"


def score_band(
    score
):
    if score is None:
        return "not_applicable"

    if score >= 75:
        return "high"

    if score >= 50:
        return "medium"

    return "low"


def build_interaction_warnings(
    trust,
    primary_resource
):
    warnings = []

    if (
        not primary_resource
        or not primary_resource.get(
            "available"
        )
    ):
        return warnings

    trust_score = (
        trust or {}
    ).get("score")

    licence = (
        primary_resource.get(
            "licence"
        )
        or {}
    )

    fair_r2l = (
        primary_resource.get(
            "fair_r2l"
        )
        or {}
    )

    copyright_result = (
        primary_resource.get(
            "ip"
        )
        or {}
    )

    if (
        trust_score is not None
        and trust_score < 50
    ):
        warnings.append({
            "level": "warning",
            "title": (
                "Check the factual content"
            ),
            "message": (
                "The text has weak trust signals "
                "and should be verified before reuse."
            )
        })

    if (
        licence.get("detected")
        is not True
    ):
        warnings.append({
            "level": "warning",
            "title": "Licence is unclear",
            "message": (
                "Clear reuse permission "
                "was not detected."
            )
        })

    classification = fair_r2l.get(
        "classification_label"
    )

    if (
        classification
        == "Not recommended"
    ):
        warnings.append({
            "level": "warning",
            "title": (
                "Critical reuse issue"
            ),
            "message": (
                "The FAIR-R²L review found "
                "a confirmed blocker."
            )
        })

    elif fair_r2l.get(
        "pending_critical_reviews"
    ):
        warnings.append({
            "level": "info",
            "title": (
                "Important checks remain"
            ),
            "message": (
                "Complete the critical FAIR-R²L "
                "questions before making a reuse "
                "decision."
            )
        })

    timing_status = (
        copyright_result.get(
            "timing",
            {}
        ).get("status")
    )

    if timing_status == "active_embargo":
        warnings.append({
            "level": "warning",
            "title": "Active embargo",
            "message": (
                "The resource may not yet "
                "be available for reuse."
            )
        })

    return warnings[:4]