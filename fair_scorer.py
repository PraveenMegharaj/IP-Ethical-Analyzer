import os

import requests
from dotenv import load_dotenv

from content_extractor import ContentExtractor
from licence_analyzer import LicenceAnalyzer


load_dotenv()


DEFAULT_TIMEOUT = int(
    os.getenv(
        "FUJI_TIMEOUT",
        "300"
    )
)


MATURITY_LABELS = {
    0: "incomplete",
    1: "initial",
    2: "moderate",
    3: "advanced"
}


class FAIRScorer:
    def __init__(
        self,
        fuji_url=None,
        fuji_username=None,
        fuji_password=None
    ):
        self.fuji_url = (
            fuji_url
            or os.getenv(
                "FUJI_API_URL",
                ""
            )
        ).strip()

        self.fuji_username = (
            fuji_username
            or os.getenv(
                "FUJI_USERNAME",
                ""
            )
        ).strip()

        self.fuji_password = (
            fuji_password
            or os.getenv(
                "FUJI_PASSWORD",
                ""
            )
        ).strip()

        self.extractor = ContentExtractor()
        self.licence_analyzer = LicenceAnalyzer()

    def score(
        self,
        identifier,
        artefact=None
    ):
        identifier = str(
            identifier or ""
        ).strip()

        artefact = (
            artefact
            or self.extractor.extract(
                identifier
            )
        )

        fuji_error = None

        if (
            self.fuji_url
            and identifier
        ):
            fuji_result, fuji_error = (
                self._score_with_fuji(
                    identifier
                )
            )

            if fuji_result:
                return fuji_result

        result = self._score_from_metadata(
            artefact,
            identifier
        )

        if fuji_error:
            result["fuji_error"] = fuji_error
            result["note"] = (
                "F-UJI was unavailable, so this result "
                "uses a transparent metadata estimate."
            )

        return result

    def _score_with_fuji(
        self,
        identifier
    ):
        payload = {
            "object_identifier": self._normalise_identifier(
                identifier
            ),
            "test_debug": False,
            "use_datacite": True,
            "use_github": False,
            "use_headless": False
        }

        authentication = None

        if (
            self.fuji_username
            or self.fuji_password
        ):
            authentication = (
                self.fuji_username,
                self.fuji_password
            )

        try:
            response = requests.post(
                self.fuji_url,
                json=payload,
                auth=authentication,
                timeout=DEFAULT_TIMEOUT,
                headers={
                    "Accept": "application/json",
                    "Content-Type": "application/json"
                }
            )

        except requests.RequestException as error:
            return None, str(error)

        if not response.ok:
            return None, (
                f"F-UJI returned HTTP "
                f"{response.status_code}: "
                f"{response.text[:300]}"
            )

        try:
            data = response.json()

        except ValueError:
            return None, (
                "F-UJI returned invalid JSON."
            )

        result = self._normalise_fuji_result(
            data,
            identifier
        )

        if not result:
            return None, (
                "F-UJI response did not contain "
                "FAIR scores."
            )

        return result, None

    def _normalise_fuji_result(
        self,
        data,
        identifier
    ):
        summary = (
            data.get("summary", {})
            or {}
        )

        percentages = (
            summary.get(
                "score_percent",
                {}
            )
            or {}
        )

        earned = (
            summary.get(
                "score_earned",
                {}
            )
            or {}
        )

        totals = (
            summary.get(
                "score_total",
                {}
            )
            or {}
        )

        maturity = (
            summary.get(
                "maturity",
                {}
            )
            or {}
        )

        passed = (
            summary.get(
                "status_passed",
                {}
            )
            or {}
        )

        status_totals = (
            summary.get(
                "status_total",
                {}
            )
            or {}
        )

        overall_score = self._number(
            percentages.get("FAIR")
        )

        if overall_score is None:
            overall_score = self._percentage(
                self._number(
                    earned.get("FAIR")
                ),
                self._number(
                    totals.get("FAIR")
                )
            )

        if overall_score is None:
            return None

        names = {
            "F": (
                "findable",
                "Findable"
            ),
            "A": (
                "accessible",
                "Accessible"
            ),
            "I": (
                "interoperable",
                "Interoperable"
            ),
            "R": (
                "reusable",
                "Reusable"
            )
        }

        principle_summary = {}
        dimensions = {}

        for code, (
            key,
            label
        ) in names.items():
            percent = self._number(
                percentages.get(code)
            )

            points_earned = self._number(
                earned.get(code)
            )

            points_total = self._number(
                totals.get(code)
            )

            maturity_value = (
                self._maturity_value(
                    maturity.get(code)
                )
            )

            principle_summary[key] = {
                "code": code,
                "name": label,
                "earned": points_earned,
                "total": points_total,
                "percent": percent,
                "maturity": maturity_value,
                "level": MATURITY_LABELS.get(
                    maturity_value,
                    "unknown"
                ),
                "tests_passed": self._number(
                    passed.get(code)
                ),
                "tests_total": self._number(
                    status_totals.get(code)
                )
            }

            dimensions[key] = percent

        metrics = self._normalise_fuji_metrics(
            data.get(
                "results",
                []
            )
        )

        overall_maturity = (
            self._maturity_value(
                maturity.get("FAIR")
            )
        )

        return {
            "score": round(
                overall_score,
                2
            ),
            "band": self._score_band(
                overall_score
            ),
            "method": "F-UJI",
            "method_label": (
                "Automated F-UJI assessment"
            ),
            "is_estimate": False,
            "assessment_status": "completed",
            "identifier": identifier,
            "principle_summary": principle_summary,
            "dimensions": dimensions,
            "principles": {
                key: self._number(value)
                for key, value in percentages.items()
                if key != "FAIR"
            },
            "checks": metrics,
            "recommendations": (
                self._fuji_recommendations(
                    metrics
                )
            ),
            "metric_version": data.get(
                "metric_version"
            ),
            "software_version": data.get(
                "software_version"
            ),
            "total_metrics": data.get(
                "total_metrics"
            ),
            "resolved_url": data.get(
                "resolved_url"
            ),
            "overall": {
                "earned": self._number(
                    earned.get("FAIR")
                ),
                "total": self._number(
                    totals.get("FAIR")
                ),
                "percent": round(
                    overall_score,
                    2
                ),
                "maturity": overall_maturity,
                "level": MATURITY_LABELS.get(
                    overall_maturity,
                    "unknown"
                )
            },
            "note": (
                "F-UJI returned this automated "
                "FAIR assessment."
            ),
            "limitations": (
                "Automated FAIR checks cannot replace "
                "domain-specific or qualitative review."
            )
        }

    def _normalise_fuji_metrics(
        self,
        results
    ):
        metrics = []

        for item in results or []:
            score_data = (
                item.get(
                    "score",
                    {}
                )
                or {}
            )

            earned = self._number(
                score_data.get("earned")
            )

            total = self._number(
                score_data.get("total")
            )

            status = str(
                item.get("test_status")
                or item.get("status")
                or "unknown"
            ).lower()

            passed = status in {
                "pass",
                "passed",
                "true"
            }

            metrics.append({
                "id": item.get(
                    "metric_identifier"
                ),
                "label": item.get(
                    "metric_name"
                ),
                "principle": item.get(
                    "fair_principle"
                ),
                "passed": passed,
                "status": status,
                "score_earned": earned,
                "score_total": total,
                "score_percent": self._percentage(
                    earned,
                    total
                ),
                "maturity": item.get(
                    "maturity"
                ),
                "evidence": item.get(
                    "output"
                ),
                "recommendation": (
                    None
                    if passed
                    else (
                        "Review this FAIR requirement."
                    )
                )
            })

        return metrics

    def _fuji_recommendations(
        self,
        metrics
    ):
        recommendations = []

        for metric in metrics:
            if metric.get("passed"):
                continue

            label = (
                metric.get("label")
                or metric.get("id")
                or "FAIR requirement"
            )

            text = f"Improve: {label}."

            if text not in recommendations:
                recommendations.append(
                    text
                )

        return recommendations[:8]

    def _score_from_metadata(
        self,
        artefact,
        identifier
    ):
        licence = self.licence_analyzer.analyze(
            artefact.get(
                "licence_string"
            )
        )

        checks = {
            "findable": [
                self._check(
                    "Persistent identifier",
                    bool(
                        artefact.get("doi")
                    ),
                    artefact.get("doi")
                ),
                self._check(
                    "Title",
                    bool(
                        artefact.get("title")
                    ),
                    artefact.get("title")
                ),
                self._check(
                    "Creators",
                    bool(
                        artefact.get("authors")
                    ),
                    artefact.get("authors")
                ),
                self._check(
                    "Keywords",
                    bool(
                        artefact.get("keywords")
                    ),
                    artefact.get("keywords")
                ),
                self._check(
                    "Searchable repository",
                    bool(
                        artefact.get("source")
                    ),
                    artefact.get("source")
                )
            ],
            "accessible": [
                self._check(
                    "Metadata retrieved",
                    (
                        artefact.get("fetch_status")
                        == "success"
                    ),
                    artefact.get("fetch_status")
                ),
                self._check(
                    "Standard protocol",
                    str(
                        artefact.get("url")
                        or ""
                    ).startswith(
                        (
                            "http://",
                            "https://"
                        )
                    ),
                    artefact.get("url")
                ),
                self._check(
                    "Access condition",
                    bool(
                        artefact.get(
                            "access_right"
                        )
                    ),
                    artefact.get(
                        "access_right"
                    )
                ),
                self._check(
                    "Repository API",
                    (
                        artefact.get(
                            "repository_api_available"
                        )
                        is True
                    ),
                    artefact.get(
                        "repository_api_available"
                    )
                )
            ],
            "interoperable": [
                self._check(
                    "Machine-readable metadata",
                    (
                        artefact.get(
                            "metadata_machine_readable"
                        )
                        is True
                    ),
                    artefact.get(
                        "metadata_machine_readable"
                    )
                ),
                self._check(
                    "Creator identifiers",
                    self._creator_has_identifier(
                        artefact.get(
                            "author_details"
                        )
                    ),
                    artefact.get(
                        "author_details"
                    )
                ),
                self._check(
                    "Related identifiers",
                    bool(
                        artefact.get(
                            "related_identifiers"
                        )
                    ),
                    artefact.get(
                        "related_identifiers"
                    )
                ),
                self._check(
                    "File formats",
                    self._has_file_format(
                        artefact.get("files")
                    ),
                    artefact.get("files")
                )
            ],
            "reusable": [
                self._check(
                    "Recognised licence",
                    (
                        licence.get("detected")
                        is True
                    ),
                    licence.get("spdx_id")
                ),
                self._check(
                    "Description",
                    (
                        len(
                            str(
                                artefact.get(
                                    "description"
                                )
                                or ""
                            ).split()
                        )
                        >= 20
                    ),
                    self._shorten(
                        artefact.get(
                            "description"
                        )
                    )
                ),
                self._check(
                    "Version",
                    bool(
                        artefact.get("version")
                    ),
                    artefact.get("version")
                ),
                self._check(
                    "Provenance",
                    bool(
                        artefact.get("publisher")
                        or artefact.get("funding")
                    ),
                    {
                        "publisher": artefact.get(
                            "publisher"
                        ),
                        "funding": artefact.get(
                            "funding"
                        )
                    }
                )
            ]
        }

        names = {
            "findable": "Findable",
            "accessible": "Accessible",
            "interoperable": "Interoperable",
            "reusable": "Reusable"
        }

        principle_summary = {}
        dimensions = {}
        all_checks = []

        for key, items in checks.items():
            earned = sum(
                1
                for item in items
                if item["passed"]
            )

            total = len(items)

            percent = self._percentage(
                earned,
                total
            )

            maturity = (
                self._maturity_from_percent(
                    percent
                )
            )

            principle_summary[key] = {
                "code": key[0].upper(),
                "name": names[key],
                "earned": earned,
                "total": total,
                "percent": percent,
                "maturity": maturity,
                "level": MATURITY_LABELS[
                    maturity
                ],
                "tests_passed": earned,
                "tests_total": total
            }

            dimensions[key] = percent
            all_checks.extend(items)

        overall_score = round(
            sum(
                dimensions.values()
            )
            / len(dimensions),
            2
        )

        overall_earned = sum(
            item["earned"]
            for item in principle_summary.values()
        )

        overall_total = sum(
            item["total"]
            for item in principle_summary.values()
        )

        overall_maturity = (
            self._maturity_from_percent(
                overall_score
            )
        )

        return {
            "score": overall_score,
            "band": self._score_band(
                overall_score
            ),
            "method": "metadata_estimate",
            "method_label": (
                "Estimated FAIR signals"
            ),
            "is_estimate": True,
            "assessment_status": "estimated",
            "identifier": identifier,
            "principle_summary": principle_summary,
            "dimensions": dimensions,
            "principles": {},
            "checks": all_checks,
            "recommendations": [
                (
                    f"Improve: "
                    f"{item['label']}."
                )
                for item in all_checks
                if not item["passed"]
            ][:8],
            "overall": {
                "earned": overall_earned,
                "total": overall_total,
                "percent": overall_score,
                "maturity": overall_maturity,
                "level": MATURITY_LABELS[
                    overall_maturity
                ]
            },
            "note": (
                "This is a metadata estimate, not "
                "an official F-UJI result."
            ),
            "limitations": (
                "The estimate only checks metadata "
                "signals available to this application."
            )
        }

    def _check(
        self,
        label,
        passed,
        evidence
    ):
        return {
            "id": label.lower().replace(
                " ",
                "_"
            ),
            "label": label,
            "principle": None,
            "passed": bool(passed),
            "status": (
                "pass"
                if passed
                else "fail"
            ),
            "score_earned": (
                1
                if passed
                else 0
            ),
            "score_total": 1,
            "score_percent": (
                100
                if passed
                else 0
            ),
            "maturity": None,
            "evidence": evidence,
            "recommendation": (
                None
                if passed
                else f"Improve: {label}."
            )
        }

    def _creator_has_identifier(
        self,
        creators
    ):
        for creator in creators or []:
            if not isinstance(
                creator,
                dict
            ):
                continue

            if (
                creator.get("orcid")
                or creator.get("identifier")
                or creator.get(
                    "nameIdentifiers"
                )
            ):
                return True

        return False

    def _has_file_format(
        self,
        files
    ):
        for item in files or []:
            if not isinstance(
                item,
                dict
            ):
                continue

            if (
                item.get("mime_type")
                or item.get("type")
                or item.get("name")
            ):
                return True

        return False

    def _normalise_identifier(
        self,
        identifier
    ):
        value = str(
            identifier or ""
        ).strip()

        if value.lower().startswith(
            "doi:"
        ):
            value = value[4:].strip()

        if value.startswith("10."):
            return (
                f"https://doi.org/"
                f"{value}"
            )

        return value

    def _score_band(
        self,
        score
    ):
        if score is None:
            return "not_applicable"

        if score >= 75:
            return "high"

        if score >= 50:
            return "medium"

        return "low"

    def _maturity_value(
        self,
        value
    ):
        number = self._number(
            value
        )

        if number is None:
            return None

        return max(
            0,
            min(
                3,
                int(
                    round(number)
                )
            )
        )

    def _maturity_from_percent(
        self,
        percent
    ):
        if (
            percent is None
            or percent <= 0
        ):
            return 0

        if percent < 50:
            return 1

        if percent < 80:
            return 2

        return 3

    def _percentage(
        self,
        earned,
        total
    ):
        if (
            earned is None
            or total in {
                None,
                0
            }
        ):
            return None

        return round(
            earned
            / total
            * 100,
            2
        )

    def _number(
        self,
        value
    ):
        try:
            return float(value)

        except (
            TypeError,
            ValueError
        ):
            return None

    def _shorten(
        self,
        value,
        limit=240
    ):
        text = str(
            value or ""
        ).strip()

        if len(text) <= limit:
            return text

        return (
            f"{text[:limit].rstrip()}..."
        )