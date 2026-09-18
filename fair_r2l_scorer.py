import json
import os
from copy import deepcopy

from licence_analyzer import LicenceAnalyzer
from metadata_evidence import MetadataEvidenceEngine


CHECKLIST_PATH = os.path.join(
    os.path.dirname(__file__),
    "fair_r2l_checklist.json"
)


VALID_ANSWERS = {
    "yes",
    "no",
    "not_applicable",
    "not_assessed"
}


# FAIR is assessed by F-UJI and consumed here; it is NOT re-derived from the
# checklist. These four dimensions are read from the F-UJI result and combined
# with the checklist's AI Readiness and Responsible Licensing dimensions.
FAIR_DIMENSIONS = {
    "findable": "Findable",
    "accessible": "Accessible",
    "interoperable": "Interoperable",
    "reusable": "Reusable"
}


class FAIRR2LScorer:
    def __init__(
        self,
        checklist_path=None
    ):
        self.checklist_path = (
            checklist_path
            or CHECKLIST_PATH
        )

        self.checklist = (
            self._load_checklist()
        )

        self.licence_analyzer = (
            LicenceAnalyzer()
        )

        self.evidence_engine = (
            MetadataEvidenceEngine()
        )

    def get_questions(self):
        return deepcopy(
            self.checklist
        )

    def score(
        self,
        artefact,
        fair_result=None,
        manual_answers=None
    ):
        artefact = artefact or {}
        manual_answers = manual_answers or {}

        licence = self.licence_analyzer.analyze(
            artefact.get(
                "licence_string"
            )
        )

        suggestions = self.evidence_engine.evaluate(
            artefact,
            licence,
            fair_result
        )

        sections = {}
        checks = []

        for section in self.checklist.get(
            "sections",
            []
        ):
            section_checks = []

            for question in section.get(
                "questions",
                []
            ):
                check = self._build_check(
                    section=section,
                    question=question,
                    suggestion=suggestions.get(
                        question["id"],
                        {}
                    ),
                    manual_answers=manual_answers
                )

                section_checks.append(
                    check
                )

                checks.append(
                    check
                )

            section_result = (
                self._calculate_dimension(
                    section_checks
                )
            )

            section_result.update({
                "id": section["id"],
                "title": section["title"],
                "short_description": section.get(
                    "short_description",
                    ""
                ),
                "checks": section_checks
            })

            sections[
                section["id"]
            ] = section_result

        # FAIR comes from F-UJI, not from the checklist (no double assessment).
        # Prepend the four FAIR dimensions, read directly from the F-UJI result,
        # so FAIR-R2L = FAIR (F-UJI) + AI Readiness + Responsible Licensing.
        fair_sections, fair_source = self._fair_sections(
            fair_result
        )

        ordered = {}
        ordered.update(fair_sections)
        ordered.update(sections)
        sections = ordered

        readiness = self._overall_readiness(
            sections
        )

        completion = self._overall_completion(
            checks
        )

        blockers, pending_critical = (
            self._critical_reviews(
                checks
            )
        )

        classification = self._classify(
            readiness=readiness,
            completion=completion,
            sections=sections,
            blockers=blockers,
            pending_critical=pending_critical
        )

        strengths = [
            check
            for check in checks
            if check["working_answer"] == "yes"
        ]

        gaps = [
            check
            for check in checks
            if check["working_answer"] == "no"
        ]

        pending = [
            check
            for check in checks
            if (
                check["working_answer"]
                == "not_assessed"
            )
        ]

        answered = sum(
            1
            for check in checks
            if check["confirmed_answer"] in {
                "yes",
                "no"
            }
        )

        not_applicable = sum(
            1
            for check in checks
            if (
                check["confirmed_answer"]
                == "not_applicable"
            )
        )

        return {
            "score": readiness,
            "readiness": readiness,
            "fair_source": fair_source,
            "completion": completion,
            "band": self._band(
                readiness
            ),
            "classification": classification,
            "classification_label": (
                classification["label"]
            ),
            "provisional": (
                completion < 100
                or bool(
                    pending_critical
                )
            ),
            "official_scoring_model": False,
            "method": (
                "Experimental transparent "
                "rule-based assessment"
            ),
            "method_label": (
                "FAIR-R²L prototype assessment"
            ),
            "checklist_version": (
                self.checklist.get("version")
            ),
            "method_note": self.checklist.get(
                "method_note"
            ),
            "sections": sections,
            "checks": checks,
            "critical_blockers": blockers,
            "pending_critical_reviews": (
                pending_critical
            ),
            "strengths": self._summaries(
                strengths,
                8
            ),
            "missing_elements": self._summaries(
                gaps,
                8
            ),
            "pending_elements": self._summaries(
                pending,
                8
            ),
            "recommendations": (
                self._recommendations(
                    gaps,
                    pending_critical
                )
            ),
            "manual_completion": {
                "answered": answered,
                "total": len(checks),
                "not_applicable": not_applicable,
                "complete": completion == 100
            },
            "suggestions_confirmed": sum(
                1
                for check in checks
                if check["confirmed_answer"] in {
                    "yes",
                    "no",
                    "not_applicable"
                }
            ),
            "suggestions_total": len(checks),
            "licence": licence,
            "note": (
                "Readiness uses confirmed answers and "
                "transparent system suggestions. Completion "
                "shows how much of the checklist has been "
                "confirmed by the user."
            ),
            "disclaimer": (
                "This prototype supports FAIR-R²L review. "
                "It does not provide legal, ethical or "
                "institutional approval."
            )
        }

    def _fair_sections(self, fair_result):
        """Build the four FAIR dimension sections from the F-UJI result.

        FAIR is assessed once, by F-UJI, and consumed here. When F-UJI is
        unavailable, fair_scorer falls back to a transparent metadata estimate
        with the same shape, so this still works; the source is flagged.
        Returns (sections_dict, source_label). Empty dict if no FAIR data.
        """
        fair_result = fair_result or {}
        dimensions = fair_result.get("dimensions") or {}

        if not dimensions:
            return {}, None

        # A populated 'principles' map means F-UJI ran; the metadata fallback
        # leaves it empty.
        source = (
            "metadata-fallback"
            if fair_result.get("is_estimate")
            else "f-uji"
        )

        sections = {}

        for key, title in FAIR_DIMENSIONS.items():
            dim = dimensions.get(key)

            if isinstance(dim, dict):
                percent = dim.get("percent")
                if percent is None:
                    percent = dim.get("score")
                level = dim.get("level")
                earned = dim.get("earned")
                total = dim.get("total")
                maturity = dim.get("maturity")
            elif isinstance(dim, (int, float)):
                percent = dim
                level = earned = total = maturity = None
            else:
                percent = level = earned = total = maturity = None

            readiness = (
                round(float(percent), 2)
                if isinstance(percent, (int, float))
                else None
            )

            sections[key] = {
                "id": key,
                "title": title,
                "short_description": (
                    "FAIR dimension assessed by F-UJI."
                ),
                "readiness": readiness,
                "score": readiness,
                "completion": (
                    100 if readiness is not None else 0
                ),
                "level": (
                    level
                    or self._readiness_level(readiness)
                ),
                "source": source,
                "fair_evidence": {
                    "earned": earned,
                    "total": total,
                    "percent": percent,
                    "maturity": maturity,
                    "level": level
                },
                "checks": [],
                "yes": None,
                "no": None,
                "not_assessed": 0,
                "not_applicable": 0,
                "confirmed": 0,
                "total_applicable": 0
            }

        return sections, source

    def _load_checklist(self):
        with open(
            self.checklist_path,
            "r",
            encoding="utf-8"
        ) as file:
            return json.load(file)

    def _build_check(
        self,
        section,
        question,
        suggestion,
        manual_answers
    ):
        check_id = question["id"]

        submitted = manual_answers.get(
            check_id
        )

        comment = manual_answers.get(
            f"{check_id}_evidence",
            ""
        )

        if isinstance(
            submitted,
            dict
        ):
            confirmed_answer = (
                self._normalise_answer(
                    submitted.get("answer")
                )
            )

            comment = (
                submitted.get("comment")
                or submitted.get("evidence")
                or comment
            )

        else:
            confirmed_answer = (
                self._normalise_answer(
                    submitted
                )
            )

        suggested_answer = (
            self._normalise_answer(
                suggestion.get(
                    "suggested_answer"
                )
            )
        )

        submitted_present = (
            submitted is not None
            and submitted != ""
        )

        confirmed = (
            confirmed_answer in VALID_ANSWERS
            and submitted_present
        )

        if confirmed:
            working_answer = (
                confirmed_answer
            )

            answer_source = "user"

        elif suggested_answer in {
            "yes",
            "no",
            "not_applicable"
        }:
            working_answer = (
                suggested_answer
            )

            answer_source = (
                "system_suggestion"
            )

        else:
            working_answer = (
                "not_assessed"
            )

            answer_source = (
                "manual_review_required"
            )

        return {
            "id": check_id,
            "dimension": section["id"],
            "dimension_title": section["title"],
            "text": question["text"],
            "type": question.get(
                "type",
                "manual"
            ),
            "assessment_mode": question.get(
                "assessment_mode",
                "manual"
            ),
            "critical": bool(
                question.get("critical")
            ),
            "suggested_answer": suggested_answer,
            "confirmed_answer": (
                confirmed_answer
                if confirmed
                else "not_assessed"
            ),
            "working_answer": working_answer,
            "answer": self._answer_as_boolean(
                working_answer
            ),
            "confirmed": confirmed,
            "status": self._status(
                working_answer,
                confirmed
            ),
            "source": answer_source,
            "suggestion_source": suggestion.get(
                "source",
                "manual_review_required"
            ),
            "confidence": suggestion.get(
                "confidence",
                0
            ),
            "reason": suggestion.get(
                "reason",
                "Human review is required."
            ),
            "evidence": suggestion.get(
                "evidence",
                []
            ),
            "user_comment": str(
                comment or ""
            ).strip(),
            "recommendation": question.get(
                "recommendation",
                "Review this checklist item."
            ),
            "evidence_hint": question.get(
                "evidence_hint",
                ""
            )
        }

    def _calculate_dimension(
        self,
        checks
    ):
        applicable = [
            check
            for check in checks
            if (
                check["working_answer"]
                != "not_applicable"
            )
        ]

        assessed = [
            check
            for check in applicable
            if check["working_answer"] in {
                "yes",
                "no"
            }
        ]

        yes_count = sum(
            1
            for check in assessed
            if (
                check["working_answer"]
                == "yes"
            )
        )

        no_count = sum(
            1
            for check in assessed
            if (
                check["working_answer"]
                == "no"
            )
        )

        not_assessed = sum(
            1
            for check in applicable
            if (
                check["working_answer"]
                == "not_assessed"
            )
        )

        not_applicable = (
            len(checks)
            - len(applicable)
        )

        readiness = self._percentage(
            yes_count,
            yes_count + no_count
        )

        confirmed = sum(
            1
            for check in applicable
            if check["confirmed_answer"] in {
                "yes",
                "no"
            }
        )

        completion = self._percentage(
            confirmed,
            len(applicable)
        )

        return {
            "readiness": readiness,
            "score": readiness,
            "completion": completion,
            "level": self._readiness_level(
                readiness
            ),
            "yes": yes_count,
            "no": no_count,
            "not_assessed": not_assessed,
            "not_applicable": not_applicable,
            "confirmed": confirmed,
            "total_applicable": len(
                applicable
            )
        }

    def _overall_readiness(
        self,
        sections
    ):
        values = [
            section["readiness"]
            for section in sections.values()
            if (
                section["readiness"]
                is not None
            )
        ]

        if not values:
            return None

        return round(
            sum(values)
            / len(values),
            2
        )

    def _overall_completion(
        self,
        checks
    ):
        applicable = [
            check
            for check in checks
            if (
                check["working_answer"]
                != "not_applicable"
            )
        ]

        if not applicable:
            return None

        confirmed = sum(
            1
            for check in applicable
            if check["confirmed_answer"] in {
                "yes",
                "no"
            }
        )

        return round(
            confirmed
            / len(applicable)
            * 100,
            2
        )

    def _critical_reviews(
        self,
        checks
    ):
        blockers = []
        pending = []

        for check in checks:
            if not check["critical"]:
                continue

            if (
                check["confirmed"]
                and check["confirmed_answer"]
                == "no"
            ):
                blockers.append(
                    self._check_summary(
                        check
                    )
                )

            elif (
                not check["confirmed"]
                or check["confirmed_answer"]
                == "not_assessed"
            ):
                pending.append(
                    self._check_summary(
                        check
                    )
                )

        return blockers, pending

    def _classify(
        self,
        readiness,
        completion,
        sections,
        blockers,
        pending_critical
    ):
        if blockers:
            return {
                "label": "Not recommended",
                "reason": (
                    "One or more confirmed critical "
                    "blockers must be resolved before reuse."
                )
            }

        if readiness is None:
            return {
                "label": "Needs review",
                "reason": (
                    "There is not enough confirmed or "
                    "suggested evidence to assess readiness."
                )
            }

        if (
            completion is not None
            and completion >= 80
            and readiness < 40
        ):
            return {
                "label": "Not recommended",
                "reason": (
                    "A substantially completed assessment "
                    "shows low readiness."
                )
            }

        ai_readiness = (
            sections.get(
                "ai_readiness",
                {}
            ).get("readiness")
        )

        responsible = (
            sections.get(
                "responsible_licensing",
                {}
            ).get("readiness")
        )

        ready = (
            readiness >= 75
            and completion is not None
            and completion >= 80
            and not pending_critical
            and (
                ai_readiness is None
                or ai_readiness >= 60
            )
            and (
                responsible is None
                or responsible >= 60
            )
        )

        if ready:
            return {
                "label": "Ready for reuse",
                "reason": (
                    "Readiness and completion thresholds "
                    "are met with no unresolved critical "
                    "checks."
                )
            }

        reasons = []

        if (
            completion is None
            or completion < 80
        ):
            reasons.append(
                "the assessment is incomplete"
            )

        if pending_critical:
            reasons.append(
                (
                    "critical checks still require "
                    "confirmation"
                )
            )

        if (
            ai_readiness is not None
            and ai_readiness < 60
        ):
            reasons.append(
                "AI readiness needs improvement"
            )

        if (
            responsible is not None
            and responsible < 60
        ):
            reasons.append(
                (
                    "responsible licensing needs "
                    "improvement"
                )
            )

        if readiness < 75:
            reasons.append(
                (
                    "important requirements are "
                    "not yet met"
                )
            )

        return {
            "label": "Needs improvements",
            "reason": (
                "; ".join(reasons).capitalize()
                + "."
            )
        }

    def _recommendations(
        self,
        gaps,
        pending_critical
    ):
        recommendations = []

        for check in gaps:
            recommendation = check.get(
                "recommendation"
            )

            if (
                recommendation
                and recommendation
                not in recommendations
            ):
                recommendations.append(
                    recommendation
                )

        for item in pending_critical:
            text = (
                f"Confirm: "
                f"{item['text']}"
            )

            if text not in recommendations:
                recommendations.append(
                    text
                )

        return recommendations[:10]

    def _summaries(
        self,
        checks,
        limit
    ):
        return [
            self._check_summary(check)
            for check in checks[:limit]
        ]

    def _check_summary(
        self,
        check
    ):
        return {
            "id": check["id"],
            "dimension": (
                check["dimension_title"]
            ),
            "text": check["text"],
            "answer": check["working_answer"],
            "confirmed": check["confirmed"],
            "recommendation": check.get(
                "recommendation"
            )
        }

    def _normalise_answer(
        self,
        value
    ):
        if isinstance(value, bool):
            return (
                "yes"
                if value
                else "no"
            )

        value = str(
            value or ""
        ).strip().lower().replace(
            " ",
            "_"
        )

        aliases = {
            "true": "yes",
            "pass": "yes",
            "1": "yes",
            "false": "no",
            "fail": "no",
            "0": "no",
            "n/a": "not_applicable",
            "na": "not_applicable",
            "not_answered": "not_assessed",
            "unknown": "not_assessed",
            "system": "not_assessed",
            "suggestion": "not_assessed"
        }

        value = aliases.get(
            value,
            value
        )

        if value in VALID_ANSWERS:
            return value

        return "not_assessed"

    def _status(
        self,
        answer,
        confirmed
    ):
        if answer == "not_applicable":
            return "not_applicable"

        if answer == "not_assessed":
            return "not_assessed"

        if not confirmed:
            return "suggested"

        if answer == "yes":
            return "confirmed_yes"

        return "confirmed_no"

    def _answer_as_boolean(
        self,
        answer
    ):
        if answer == "yes":
            return True

        if answer == "no":
            return False

        return None

    def _percentage(
        self,
        numerator,
        denominator
    ):
        if denominator == 0:
            return None

        return round(
            numerator
            / denominator
            * 100,
            2
        )

    def _readiness_level(
        self,
        score
    ):
        if score is None:
            return "not assessed"

        if score >= 75:
            return "strong"

        if score >= 50:
            return "developing"

        return "early"

    def _band(
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