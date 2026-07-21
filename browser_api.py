from flask import Flask, request, jsonify
from analysis_core import analyze_full_text
import uuid

app = Flask(__name__)

ANALYSIS_RESULTS = {}


@app.route("/analyze", methods=["POST"])
def analyze():
    data = request.get_json() or {}
    text = data.get("text", "").strip()
    source_links = data.get("source_links", [])

    if not isinstance(source_links, list):
        source_links = []

    source_links = [
        link for link in source_links
        if isinstance(link, str) and link.startswith(("http://", "https://"))
    ]

    if not text:
        return jsonify({"error": "No text provided"}), 400

    result = analyze_full_text(
        text=text,
        source_links=source_links
    )

    analysis_id = str(uuid.uuid4())

    ANALYSIS_RESULTS[analysis_id] = {
        "text": text,
        "source_links": source_links,
        "result": result
    }

    return jsonify({
        "analysis_id": analysis_id,
        "trust_score": result["trust_score"],
        "explanation": result["ai_explanation"],
        "bias": result["bias_result"],
        "citations": result["citation_result"],
        "source_links": source_links
    })


@app.route("/result/<analysis_id>", methods=["GET"])
def get_result(analysis_id):
    stored = ANALYSIS_RESULTS.get(analysis_id)

    if not stored:
        return jsonify({"error": "Analysis not found"}), 404

    return jsonify(stored)


if __name__ == "__main__":
    app.run(debug=True, use_reloader=False)