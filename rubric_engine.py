from datetime import datetime
from datetime import timezone

from licence_analyzer import LicenceAnalyzer


LEVEL_WEIGHT = 0.75
TIMING_WEIGHT = 0.25


class RubricEngine:
    def __init__(self):
        self.licence_analyzer = LicenceAnalyzer()

    def compute(
        self,
        artefact,
        user_role="reuser"
    ):
        focus = self._compute_focus(
            artefact,
            user_role
        )

        level = self._compute_level(
            artefact
        )

        timing = self._compute_timing(
            artefact
        )

        score = self._combine_scores(
            level,
            timing
        )

        return {
            "score": score,
            "band": self._score_band(score),
            "verdict": self._verdict(
                score,
                level,
                timing
            ),
            "focus": focus,
            "level": level,
            "timing": timing,
            "licence": level.get("licence"),
            "audit_trail": self._build_audit_trail(
                artefact,
                focus,
                level,
                timing
            ),
            "disclaimer": (
                "This assessment supports research and "
                "reuse decisions. It does not replace legal, "
                "contractual, privacy, or institutional review."
            )
        }

    def _compute_focus(
        self,
        artefact,
        user_role
    ):
        if user_role not in {
            "producer",
            "reuser"
        }:
            user_role = "reuser"

        if user_role == "producer":
            description = (
                "The user is assessing an intellectual "
                "asset they produce or control."
            )
        else:
            description = (
                "The user is assessing an existing "
                "resource for possible reuse."
            )

        return {
            "role": user_role,
            "source": "user_selected",
            "description": description,
            "resource_type": artefact.get(
                "kind",
                "unknown"
            )
        }

    def _compute_level(
        self,
        artefact
    ):
        licence = self.licence_analyzer.analyze(
            artefact.get("licence_string")
        )

        openness = licence.get("openness")

        if openness is None:
            return {
                "score": None,
                "band": "unknown",
                "licence": licence,
                "description": (
                    "The openness level cannot be "
                    "calculated because no recognised "
                    "licence was found."
                )
            }

        return {
            "score": openness,
            "band": self._score_band(
                openness
            ),
            "licence": licence,
            "description": licence.get(
                "plain_english",
                ""
            )
        }

    def _compute_timing(
        self,
        artefact
    ):
        access_right = str(
            artefact.get("access_right")
            or ""
        ).strip().lower()

        embargo_date = self._parse_date(
            artefact.get("embargo_date")
        )

        publication_date = self._parse_date(
            artefact.get("publication_date")
        )

        now = datetime.now(
            timezone.utc
        )

        if (
            embargo_date
            and embargo_date > now
        ):
            return {
                "score": 30,
                "band": "low",
                "currently_available": False,
                "status": "active_embargo",
                "access_right": access_right or None,
                "publication_date": (
                    publication_date.isoformat()
                    if publication_date
                    else None
                ),
                "embargo_date": (
                    embargo_date.isoformat()
                ),
                "description": (
                    "The resource appears to be under "
                    "an active embargo."
                )
            }

        if (
            publication_date
            and publication_date > now
        ):
            return {
                "score": 30,
                "band": "low",
                "currently_available": False,
                "status": "not_yet_published",
                "access_right": access_right or None,
                "publication_date": (
                    publication_date.isoformat()
                ),
                "embargo_date": None,
                "description": (
                    "The stated publication date is "
                    "in the future."
                )
            }

        if access_right in {
            "open",
            "open access",
            "public",
            "publicly available"
        }:
            return {
                "score": 100,
                "band": "high",
                "currently_available": True,
                "status": "open",
                "access_right": access_right,
                "publication_date": (
                    publication_date.isoformat()
                    if publication_date
                    else None
                ),
                "embargo_date": (
                    embargo_date.isoformat()
                    if embargo_date
                    else None
                ),
                "description": (
                    "The resource is currently marked "
                    "as openly accessible."
                )
            }

        if access_right in {
            "embargoed",
            "embargo"
        }:
            return {
                "score": 45,
                "band": "low",
                "currently_available": False,
                "status": "embargo_status_unknown",
                "access_right": access_right,
                "publication_date": (
                    publication_date.isoformat()
                    if publication_date
                    else None
                ),
                "embargo_date": (
                    embargo_date.isoformat()
                    if embargo_date
                    else None
                ),
                "description": (
                    "The resource is marked as embargoed, "
                    "but no active release date was confirmed."
                )
            }

        if access_right in {
            "restricted",
            "controlled",
            "registration required"
        }:
            return {
                "score": 45,
                "band": "low",
                "currently_available": False,
                "status": "restricted",
                "access_right": access_right,
                "publication_date": (
                    publication_date.isoformat()
                    if publication_date
                    else None
                ),
                "embargo_date": None,
                "description": (
                    "Access is restricted or requires "
                    "additional approval."
                )
            }

        if access_right in {
            "closed",
            "private"
        }:
            return {
                "score": 20,
                "band": "low",
                "currently_available": False,
                "status": "closed",
                "access_right": access_right,
                "publication_date": (
                    publication_date.isoformat()
                    if publication_date
                    else None
                ),
                "embargo_date": None,
                "description": (
                    "The resource is marked as closed "
                    "or private."
                )
            }

        if (
            artefact.get("fetch_status")
            == "success"
            and artefact.get("files")
        ):
            return {
                "score": 90,
                "band": "high",
                "currently_available": True,
                "status": "files_available",
                "access_right": access_right or None,
                "publication_date": (
                    publication_date.isoformat()
                    if publication_date
                    else None
                ),
                "embargo_date": None,
                "description": (
                    "The resource was retrieved and "
                    "downloadable files were detected."
                )
            }

        if artefact.get("fetch_status") == "success":
            return {
                "score": 75,
                "band": "high",
                "currently_available": True,
                "status": "landing_page_available",
                "access_right": access_right or None,
                "publication_date": (
                    publication_date.isoformat()
                    if publication_date
                    else None
                ),
                "embargo_date": None,
                "description": (
                    "The resource landing page is "
                    "currently accessible."
                )
            }

        return {
            "score": 60,
            "band": "medium",
            "currently_available": None,
            "status": "unknown",
            "access_right": access_right or None,
            "publication_date": (
                publication_date.isoformat()
                if publication_date
                else None
            ),
            "embargo_date": None,
            "description": (
                "The current reuse timing and access "
                "status could not be confirmed."
            )
        }

    def _combine_scores(
        self,
        level,
        timing
    ):
        level_score = level.get("score")
        timing_score = timing.get("score")

        if level_score is None:
            return None

        score = (
            level_score * LEVEL_WEIGHT
            + timing_score * TIMING_WEIGHT
        )

        return max(
            0,
            min(
                100,
                round(score)
            )
        )

    def _score_band(
        self,
        score
    ):
        if score is None:
            return "unknown"

        if score >= 75:
            return "high"

        if score >= 50:
            return "medium"

        return "low"

    def _verdict(
        self,
        score,
        level,
        timing
    ):
        if level.get("score") is None:
            return (
                "Reuse conditions are unclear because "
                "no recognised licence was found."
            )

        if timing.get("status") == "active_embargo":
            return (
                "The licence may support reuse, but the "
                "resource is currently under embargo."
            )

        if timing.get("status") in {
            "restricted",
            "closed",
            "not_yet_published"
        }:
            return (
                "Reuse may require access approval or "
                "permission from the rights holder."
            )

        if score >= 75:
            return (
                "The resource appears reusable under "
                "the detected licence conditions."
            )

        if score >= 50:
            return (
                "The resource may be reused with "
                "important conditions or restrictions."
            )

        return (
            "The detected conditions are restrictive. "
            "Permission may be required before reuse."
        )

    def _parse_date(
        self,
        value
    ):
        if not value:
            return None

        text = str(value).strip()

        for format_string in (
            "%Y-%m-%dT%H:%M:%S%z",
            "%Y-%m-%dT%H:%M:%S.%f%z",
            "%Y-%m-%d",
            "%Y-%m",
            "%Y"
        ):
            try:
                parsed = datetime.strptime(
                    text,
                    format_string
                )

                if parsed.tzinfo is None:
                    parsed = parsed.replace(
                        tzinfo=timezone.utc
                    )

                return parsed

            except ValueError:
                continue

        if text.endswith("Z"):
            try:
                parsed = datetime.fromisoformat(
                    text.replace(
                        "Z",
                        "+00:00"
                    )
                )

                return parsed

            except ValueError:
                return None

        try:
            parsed = datetime.fromisoformat(
                text
            )

            if parsed.tzinfo is None:
                parsed = parsed.replace(
                    tzinfo=timezone.utc
                )

            return parsed

        except ValueError:
            return None

    def _build_audit_trail(
        self,
        artefact,
        focus,
        level,
        timing
    ):
        return [
            {
                "dimension": "Focus",
                "value": focus.get("role"),
                "source": "user selection"
            },
            {
                "dimension": "Resource type",
                "value": artefact.get("kind"),
                "source": artefact.get("source")
            },
            {
                "dimension": "Licence",
                "value": level.get(
                    "licence",
                    {}
                ).get("spdx_id"),
                "source": artefact.get("source")
            },
            {
                "dimension": "Access right",
                "value": artefact.get(
                    "access_right"
                ),
                "source": artefact.get("source")
            },
            {
                "dimension": "Publication date",
                "value": artefact.get(
                    "publication_date"
                ),
                "source": artefact.get("source")
            },
            {
                "dimension": "Embargo date",
                "value": artefact.get(
                    "embargo_date"
                ),
                "source": artefact.get("source")
            },
            {
                "dimension": "Timing status",
                "value": timing.get("status"),
                "source": "computed"
            }
        ]