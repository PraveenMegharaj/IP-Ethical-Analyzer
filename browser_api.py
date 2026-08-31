import uuid
from datetime import datetime, timezone

from flask import Flask, jsonify, redirect, render_template, request, url_for

from fair_r2l_scorer import FAIRR2LScorer
from unified_analysis import analyze_unified, build_interaction_warnings


app = Flask(__name__, template_folder="templates", static_folder="static")

ANALYSIS_RESULTS = {}
MAX_STORED_RESULTS = 100
CHECKLIST_SCORER = FAIRR2LScorer()


@app.after_request
def add_cors_headers(response):
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    return response


def clean_source_links(source_links):
    if not isinstance(source_links, list):
        return []

    cleaned = []

    for link in source_links:
        if not isinstance(link, str):
            continue

        link = link.strip()

        if link.startswith(("http://", "https://")) and link not in cleaned:
            cleaned.append(link)

    return cleaned


def clean_manual_answers(manual_answers):
    if not isinstance(manual_answers, dict):
        return {}

    return {
        key.strip(): value
        for key, value in manual_answers.items()
        if isinstance(key, str) and key.strip()
    }


def create_analysis(data):
    user_input = str(
        data.get("input")
        or data.get("user_input")
        or ""
    ).strip()

    text = str(
        data.get("text")
        or ""
    ).strip()

    source_links = clean_source_links(
        data.get("source_links", [])
    )

    user_role = str(
        data.get("role")
        or data.get("user_role")
        or "reuser"
    ).strip().lower()

    manual_answers = clean_manual_answers(
        data.get("manual_answers", {})
    )

    if not user_input and not text and not source_links:
        raise ValueError(
            "No text, DOI, URL, or source link was provided."
        )

    result = analyze_unified(
        user_input=user_input,
        text=text,
        source_links=source_links,
        user_role=user_role,
        manual_answers=manual_answers
    )

    analysis_id = str(uuid.uuid4())

    record = {
        "analysis_id": analysis_id,
        "created_at": datetime.now(
            timezone.utc
        ).isoformat(),
        "request": {
            "input": user_input,
            "text": text,
            "source_links": source_links,
            "role": user_role,
            "manual_answers": manual_answers
        },
        "result": result
    }

    ANALYSIS_RESULTS[analysis_id] = record
    remove_old_results()

    return analysis_id, result


def remove_old_results():
    if len(ANALYSIS_RESULTS) <= MAX_STORED_RESULTS:
        return

    ordered = sorted(
        ANALYSIS_RESULTS.items(),
        key=lambda item: item[1].get(
            "created_at",
            ""
        )
    )

    remove_count = (
        len(ANALYSIS_RESULTS)
        - MAX_STORED_RESULTS
    )

    for analysis_id, _ in ordered[:remove_count]:
        ANALYSIS_RESULTS.pop(
            analysis_id,
            None
        )


def build_dashboard_url(analysis_id):
    return url_for(
        "dashboard",
        analysis_id=analysis_id,
        _external=True
    )


def get_primary_resource(result):
    resources = result.get(
        "resources",
        []
    )

    if not resources:
        return None

    index = result.get(
        "primary_resource_index"
    )

    if (
        not isinstance(index, int)
        or index < 0
        or index >= len(resources)
    ):
        index = 0

    return resources[index]


def make_score_summary(result, fallback_method):
    if not result or result.get("score") is None:
        return {
            "available": False,
            "score": None,
            "band": "not_applicable",
            "method": fallback_method
        }

    band = result.get("band")

    if isinstance(band, dict):
        band = band.get(
            "label",
            "unknown"
        )

    return {
        "available": True,
        "score": result.get("score"),
        "band": band or "unknown",
        "method": (
            result.get("method_label")
            or result.get("method")
            or fallback_method
        ),
        "is_estimate": result.get(
            "is_estimate",
            False
        )
    }


def public_result(record):
    response = {
        "analysis_id": record["analysis_id"],
        "created_at": record.get(
            "created_at"
        )
    }

    response.update(
        record.get("result", {})
    )

    return response


def describe_resource_type(text):
    lower = text.lower()
    resource_types = []

    if any(
        word in lower
        for word in (
            "dataset",
            "data set",
            "csv",
            "training data"
        )
    ):
        resource_types.append("dataset")

    if any(
        word in lower
        for word in (
            "code",
            "software",
            "python",
            "repository",
            "package"
        )
    ):
        resource_types.append("software")

    if any(
        word in lower
        for word in (
            "paper",
            "article",
            "publication",
            "report"
        )
    ):
        resource_types.append("publication")

    if any(
        word in lower
        for word in (
            "model",
            "weights",
            "checkpoint",
            "machine learning"
        )
    ):
        resource_types.append("AI model")

    return resource_types or [
        "research resource"
    ]


def build_clarification_questions(description):
    resource_types = describe_resource_type(
        description
    )

    questions = [
        {
            "id": "ownership",
            "text": (
                "Do you own all rights, or are there "
                "co-creators or employer rights?"
            )
        },
        {
            "id": "third_party",
            "text": (
                "Does the resource contain third-party "
                "data, code, images, or text?"
            )
        },
        {
            "id": "personal_data",
            "text": (
                "Does it contain personal, confidential, "
                "or sensitive information?"
            )
        },
        {
            "id": "commercial_goal",
            "text": (
                "Do you want to preserve commercialisation "
                "or exclusive-licensing options?"
            )
        },
        {
            "id": "reuse_goal",
            "text": (
                "Should others be allowed to adapt, redistribute, "
                "or train AI systems with it?"
            )
        }
    ]

    if "software" in resource_types:
        questions.append({
            "id": "dependencies",
            "text": (
                "Which third-party software dependencies "
                "and licences are included?"
            )
        })

    if "dataset" in resource_types:
        questions.append({
            "id": "consent",
            "text": (
                "Do consent, collection notices, and "
                "data-sharing terms permit publication?"
            )
        })

    return questions


def build_brainstorm_strategy(description, answers):
    lower = description.lower()
    resource_types = describe_resource_type(
        description
    )

    repositories = []
    licence_options = []
    actions = []
    cautions = []

    if "software" in resource_types:
        repositories.extend([
            "GitHub or GitLab for development",
            "Zenodo for a DOI-backed release"
        ])

        licence_options.extend([
            "MIT for permissive reuse with attribution",
            (
                "Apache-2.0 for permissive reuse with "
                "an explicit patent grant"
            ),
            (
                "GPL-3.0 when derivatives should "
                "remain open"
            )
        ])

        actions.append(
            "Create a dependency and third-party licence inventory."
        )

    if "dataset" in resource_types:
        repositories.extend([
            "Zenodo",
            (
                "An institutional or discipline-specific "
                "data repository"
            )
        ])

        licence_options.extend([
            (
                "CC BY 4.0 when attribution should "
                "be required"
            ),
            (
                "CC0 when maximum unrestricted data "
                "reuse is intended"
            )
        ])

        actions.extend([
            (
                "Provide a data dictionary, schema, provenance, "
                "collection method, and quality notes."
            ),
            (
                "Document representativeness, known bias, "
                "exclusions, and intended uses."
            )
        ])

    if "publication" in resource_types:
        repositories.extend([
            "Institutional repository",
            "Zenodo for supplementary material"
        ])

        licence_options.append(
            "CC BY 4.0 for broad sharing with attribution"
        )

    if "AI model" in resource_types:
        repositories.extend([
            "Hugging Face Hub",
            "Zenodo for an archived release"
        ])

        actions.extend([
            (
                "Add a model card covering training data, "
                "limitations, evaluation, and misuse risks."
            ),
            (
                "State whether the model and training data "
                "have different licence conditions."
            )
        ])

    if any(
        word in lower
        for word in (
            "commercial",
            "company",
            "partner",
            "startup",
            "patent"
        )
    ):
        cautions.append(
            (
                "Review patent, trade-secret, sponsorship, and "
                "commercialisation options before public disclosure."
            )
        )

        licence_options.append(
            (
                "Dual licensing when open and commercial "
                "terms must coexist"
            )
        )

    personal_answer = str(
        answers.get("personal_data", "")
    ).lower()

    if (
        personal_answer in {"yes", "true"}
        or any(
            word in lower
            for word in (
                "personal data",
                "patient",
                "medical",
                "confidential"
            )
        )
    ):
        cautions.append(
            (
                "Do not publish until consent, lawful basis, "
                "anonymisation, access controls, and data-protection "
                "duties are reviewed."
            )
        )

    third_party_answer = str(
        answers.get("third_party", "")
    ).lower()

    if third_party_answer in {"yes", "true"}:
        cautions.append(
            (
                "Verify that every third-party component permits "
                "the proposed publication and licence."
            )
        )

    commercial_answer = str(
        answers.get("commercial_goal", "")
    ).lower()

    if commercial_answer in {"yes", "true"}:
        cautions.append(
            (
                "Use staged disclosure or dual licensing so public "
                "release does not unintentionally remove commercial options."
            )
        )

    actions.extend([
        (
            "Confirm ownership and obtain agreement from all "
            "creators or rights holders."
        ),
        (
            "Add a clear licence file and plain-language "
            "reuse statement."
        ),
        "Assign a version and persistent identifier.",
        "Provide citation and attribution instructions.",
        (
            "Document third-party rights, limitations, "
            "and intended uses."
        )
    ])

    return {
        "resource_types": resource_types,
        "repositories": (
            list(dict.fromkeys(repositories))
            or [
                "Zenodo or an institutional repository"
            ]
        ),
        "licence_options": (
            list(dict.fromkeys(licence_options))
            or [
                (
                    "Select a licence only after confirming "
                    "ownership and intended reuse permissions."
                )
            ]
        ),
        "actions": list(
            dict.fromkeys(actions)
        ),
        "cautions": list(
            dict.fromkeys(cautions)
        ),
        "disclaimer": (
            "These are planning suggestions, not legal advice "
            "or a final licence determination."
        )
    }


@app.route("/", methods=["GET"])
def index():
    return redirect(
        url_for("dashboard")
    )


@app.route("/dashboard", methods=["GET"])
def dashboard():
    return render_template(
        "dashboard.html"
    )


@app.route("/api/health", methods=["GET"])
def health():
    return jsonify({
        "status": "ok",
        "service": "Ethical Analyser API",
        "stored_results": len(
            ANALYSIS_RESULTS
        )
    })


@app.route("/api/analyze", methods=["POST"])
def analyze_unified_route():
    data = request.get_json(
        silent=True
    ) or {}

    try:
        analysis_id, result = create_analysis(
            data
        )

    except ValueError as error:
        return jsonify({
            "error": str(error)
        }), 400

    except Exception as error:
        app.logger.exception(
            "Unified analysis failed."
        )

        return jsonify({
            "error": "Analysis failed.",
            "details": str(error)
        }), 500

    response = {
        "analysis_id": analysis_id,
        "dashboard_url": build_dashboard_url(
            analysis_id
        )
    }

    response.update(result)

    return jsonify(response)


@app.route(
    "/api/result/<analysis_id>",
    methods=["GET"]
)
def get_unified_result(analysis_id):
    stored = ANALYSIS_RESULTS.get(
        analysis_id
    )

    if not stored:
        return jsonify({
            "error": "Analysis not found."
        }), 404

    return jsonify(
        public_result(stored)
    )


@app.route("/api/checklist", methods=["GET"])
def get_checklist():
    return jsonify(
        CHECKLIST_SCORER.get_questions()
    )


@app.route(
    "/api/result/<analysis_id>/checklist",
    methods=["POST"]
)
def update_checklist(analysis_id):
    stored = ANALYSIS_RESULTS.get(
        analysis_id
    )

    if not stored:
        return jsonify({
            "error": "Analysis not found."
        }), 404

    data = request.get_json(
        silent=True
    ) or {}

    submitted_answers = clean_manual_answers(
        data.get("manual_answers", {})
    )

    saved_answers = (
        stored.get("request", {})
        .get("manual_answers", {})
    )

    saved_answers.update(
        submitted_answers
    )

    stored["request"]["manual_answers"] = (
        saved_answers
    )

    result = stored.get(
        "result",
        {}
    )

    resource = get_primary_resource(
        result
    )

    if not resource or not resource.get("artefact"):
        return jsonify({
            "error": (
                "No research resource is available "
                "for checklist scoring."
            )
        }), 400

    fair_r2l = CHECKLIST_SCORER.score(
        artefact=resource["artefact"],
        fair_result=resource.get("fair"),
        manual_answers=saved_answers
    )

    resource["fair_r2l"] = fair_r2l

    result.setdefault(
        "scores",
        {}
    )["fair_r2l"] = make_score_summary(
        fair_r2l,
        "FAIR-R2L checklist"
    )

    result["warnings"] = (
        build_interaction_warnings(
            result.get("trust", {}),
            resource
        )
    )

    return jsonify({
        "analysis_id": analysis_id,
        "fair_r2l": fair_r2l,
        "scores": result.get(
            "scores",
            {}
        ),
        "warnings": result.get(
            "warnings",
            []
        ),
        "result": public_result(
            stored
        )
    })


@app.route(
    "/api/brainstormer/clarify",
    methods=["POST"]
)
def brainstormer_clarify():
    data = request.get_json(
        silent=True
    ) or {}

    description = str(
        data.get("description")
        or ""
    ).strip()

    if not description:
        return jsonify({
            "error": (
                "Describe the resource or "
                "publication plan first."
            )
        }), 400

    return jsonify({
        "resource_types": describe_resource_type(
            description
        ),
        "questions": build_clarification_questions(
            description
        )
    })


@app.route(
    "/api/brainstormer/strategy",
    methods=["POST"]
)
def brainstormer_strategy():
    data = request.get_json(
        silent=True
    ) or {}

    description = str(
        data.get("description")
        or ""
    ).strip()

    answers = data.get(
        "answers",
        {}
    )

    if not description:
        return jsonify({
            "error": (
                "Describe the resource or "
                "publication plan first."
            )
        }), 400

    if not isinstance(answers, dict):
        answers = {}

    return jsonify(
        build_brainstorm_strategy(
            description,
            answers
        )
    )


@app.route("/analyze", methods=["POST"])
def analyze_legacy():
    data = request.get_json(
        silent=True
    ) or {}

    text = str(
        data.get("text")
        or ""
    ).strip()

    if not text:
        return jsonify({
            "error": "No text provided."
        }), 400

    try:
        analysis_id, unified_result = create_analysis({
            "text": text,
            "source_links": data.get(
                "source_links",
                []
            ),
            "role": data.get(
                "role",
                "reuser"
            )
        })

    except Exception as error:
        app.logger.exception(
            "Legacy analysis failed."
        )

        return jsonify({
            "error": "Analysis failed.",
            "details": str(error)
        }), 500

    trust = unified_result.get(
        "trust",
        {}
    )

    trust_details = trust.get(
        "details"
    ) or {}

    return jsonify({
        "analysis_id": analysis_id,
        "trust_score": trust.get("score"),
        "explanation": trust.get(
            "note",
            ""
        ),
        "bias": trust_details.get(
            "bias_result",
            {}
        ),
        "citations": trust_details.get(
            "citation_result",
            {}
        ),
        "source_links": unified_result.get(
            "source_links",
            []
        ),
        "scores": unified_result.get(
            "scores",
            {}
        ),
        "dashboard_url": build_dashboard_url(
            analysis_id
        )
    })


@app.route(
    "/result/<analysis_id>",
    methods=["GET"]
)
def get_legacy_result(analysis_id):
    stored = ANALYSIS_RESULTS.get(
        analysis_id
    )

    if not stored:
        return jsonify({
            "error": "Analysis not found."
        }), 404

    unified_result = stored.get(
        "result",
        {}
    )

    trust = unified_result.get(
        "trust",
        {}
    )

    return jsonify({
        "text": (
            unified_result.get("text")
            or stored.get(
                "request",
                {}
            ).get("text", "")
        ),
        "source_links": unified_result.get(
            "source_links",
            []
        ),
        "result": trust.get(
            "details"
        ) or {}
    })


if __name__ == "__main__":
    app.run(
        host="127.0.0.1",
        port=5000,
        debug=True,
        use_reloader=False
    )