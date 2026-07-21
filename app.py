import streamlit as st
import os
import requests
import html
import inspect

from analysis_core import analyze_full_text

st.set_page_config(
    page_title="Ethical Analyser",
    page_icon="⚖️",
    layout="wide",
    initial_sidebar_state="collapsed"
)


# ---------------------------------------------------
# ENV SETTINGS
# ---------------------------------------------------
os.environ["TRANSFORMERS_VERBOSITY"] = "error"
os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"


# ---------------------------------------------------
# ELEGANT WEBSITE UI STYLING
# ---------------------------------------------------
st.markdown("""
<style>
:root {
    --page-bg: #F7F5EF;
    --card-bg: #FFFFFF;
    --card-warm: #FFFDF8;
    --card-cream: #FBF7EF;
    --border: #DDD6CB;
    --border-soft: #ECE5DA;
    --text-main: #24221F;
    --text-muted: #6F6961;
    --muted-2: #9D958A;
    --accent: #80602C;
    --accent-soft: #F3E8D5;
    --ink: #201E1A;
    --green-bg: #EEF6F1;
    --green-border: #C9DED1;
    --green-text: #2D6B4F;
    --red: #B92A30;
    --shadow: 0 14px 36px rgba(48, 40, 28, 0.06);
}

/* Hide Streamlit chrome */
header[data-testid="stHeader"],
[data-testid="stToolbar"],
[data-testid="stDecoration"],
[data-testid="stStatusWidget"],
#MainMenu,
footer {
    display: none !important;
    visibility: hidden !important;
}

html, body, [data-testid="stAppViewContainer"] {
    background: radial-gradient(circle at top left, #FFFFFF 0, #F7F5EF 34%, #F3F0E8 100%) !important;
}

[data-testid="stAppViewContainer"] > .main {
    padding-top: 0 !important;
}
            
.main .block-container,
section.main .block-container,
div.block-container {
    padding-top: 0.6rem !important;
    padding-bottom: 1rem !important;
    padding-left: 0.6rem !important;
    padding-right: 0.6rem !important;
    max-width: calc(100vw - 64px) !important;
    width: calc(100vw - 64px) !important;
}
            
/* Reduce Streamlit's default vertical gaps */
div[data-testid="stVerticalBlock"] {
    gap: 0.72rem !important;
}

/* ---------- Top app bar ---------- */
.app-topbar {
    width: 100%;
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 20px;
    background: rgba(255, 255, 255, 0.92);
    border: 1px solid var(--border);
    border-radius: 22px;
    padding: 14px 18px;
    margin: 0 0 16px 0;
    box-shadow: var(--shadow);
    backdrop-filter: blur(8px);
}

.app-brand {
    display: flex;
    align-items: center;
    gap: 13px;
    min-width: 0;
}

.logo-box {
    width: 44px;
    height: 44px;
    border-radius: 14px;
    background:linear-gradient(145deg, #676161, #4d4537);
    color: #FFF8ED;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    font-size: 14px;
    font-weight: 850;
    letter-spacing: 0.04em;
    flex: 0 0 auto;
    box-shadow: inset 0 0 0 1px rgba(255,255,255,0.07);
}

.app-title {
    font-size: 23px;
    line-height: 1.04;
    font-weight: 850;
    color: var(--text-main);
    margin: 0;
    letter-spacing: -0.01em;
}

.app-subtitle {
    margin-top: 5px;
    color: var(--text-muted);
    font-size: 13.5px;
    line-height: 1.22;
}

.app-actions {
    display: flex;
    align-items: center;
    justify-content: flex-end;
    gap: 8px;
    flex-wrap: wrap;
}

.nav-pill {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    padding: 7px 13px;
    border-radius: 999px;
    border: 1px solid var(--border);
    background: #FBF9F4;
    color: #5C544B;
    font-size: 12.5px;
    font-weight: 760;
    white-space: nowrap;
}

/* ---------- Input / text panels ---------- */
.input-panel {
    background: rgba(255,255,255,0.90);
    border: 1px solid var(--border);
    border-radius: 20px;
    padding: 18px 20px 17px 20px;
    box-shadow: 0 10px 28px rgba(45, 38, 28, 0.045);
}

.panel-label {
    color: var(--muted-2);
    font-size: 11px;
    font-weight: 850;
    letter-spacing: 0.19em;
    text-transform: uppercase;
    margin-bottom: 10px;
}


/* ---------- Score card ---------- */
.score-panel {
    display: flex;
    align-items: center;
    gap: 22px;
    background: linear-gradient(135deg, #FFFDF8 0%, #FAF4E9 100%);
    border: 1px solid #E4DCCF;
    border-radius: 22px;
    padding: 18px 22px;
    box-shadow: var(--shadow);
}

.score-circle {
    width: 98px;
    height: 98px;
    border-radius: 50%;
    display: flex;
    align-items: center;
    justify-content: center;
    flex-shrink: 0;
}

.score-inner {
    width: 72px;
    height: 72px;
    border-radius: 50%;
    background: #FFFFFF;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
}

.score-number {
    font-size: 28px;
    font-weight: 850;
    line-height: 1;
    color: #25211E;
}

.score-total {
    font-size: 11.5px;
    color: #7F776D;
    margin-top: 2px;
}

.score-copy h2 {
    margin: 3px 0 6px 0;
    font-size: 24px;
    color: #25211E;
    letter-spacing: -0.01em;
}

.score-copy p {
    margin: 0;
    color: #6E675F;
    font-size: 14.2px;
    line-height: 1.38;
}

.eyebrow {
    color: var(--accent);
    font-size: 11px;
    font-weight: 850;
    letter-spacing: 0.16em;
    text-transform: uppercase;
}

/* ---------- Section heading ---------- */
.section-title-row {
    display: flex;
    align-items: flex-end;
    justify-content: space-between;
    margin: 0.35rem 0 0.25rem 0;
}

.section-title {
    font-size: 22px;
    font-weight: 850;
    color: var(--text-main);
    margin: 0;
    letter-spacing: -0.01em;
}

.section-subtitle {
    color: var(--text-muted);
    font-size: 13.2px;
    margin-top: 4px;
    line-height: 1.3;
}

/* ---------- Method/result cards ---------- */
.info-card,
.result-card {
    min-height: 188px;
    border-radius: 16px;
    padding: 2px 1px 0 1px;
}

.card-shade-claims { background: linear-gradient(135deg, #FFFDF8 0%, #FAF1E2 100%); }
.card-shade-facts { background: linear-gradient(135deg, #FFFFFF 0%, #F1F5F1 100%); }
.card-shade-bias { background: linear-gradient(135deg, #FFFFFF 0%, #F8EFE9 100%); }
.card-shade-citations { background: linear-gradient(135deg, #FFFFFF 0%, #F3F0E9 100%); }

.card-content-pad {
    min-height: 188px;
    display: flex;
    flex-direction: column;
    justify-content: space-between;
    padding: 2px 2px 1px 2px;
}

.card-kicker {
    color: #968E82;
    font-size: 10.5px;
    font-weight: 850;
    letter-spacing: 0.16em;
    text-transform: uppercase;
    margin-bottom: 9px;
}

.card-title {
    font-size: 16.2px;
    font-weight: 850;
    color: #25211E;
    margin-bottom: 9px;
    letter-spacing: -0.01em;
}

.card-value {
    font-size: 28px;
    font-weight: 850;
    color: #25211E;
    margin-bottom: 6px;
}

.card-status {
    font-size: 12.3px;
    font-weight: 850;
    color: var(--accent);
    margin-bottom: 10px;
}

.card-desc {
    font-size: 13.2px;
    color: #655F57;
    line-height: 1.42;
    min-height: 52px;
}

.model-chip {
    display: inline-block;
    max-width: 100%;
    margin-top: 12px;
    padding: 5px 11px;
    border-radius: 999px;
    background: rgba(132, 97, 42, 0.10);
    color: #60451E;
    font-size: 11.5px;
    line-height: 1.2;
    font-weight: 820;
}

.footer-note {
    margin-top: 4px;
    padding: 13px 16px;
    border: 1px solid var(--border-soft);
    border-radius: 16px;
    color: var(--text-muted);
    background: rgba(255,255,255,0.62);
    font-size: 13px;
}

/* ---------- Streamlit containers and controls ---------- */
div[data-testid="stVerticalBlockBorderWrapper"] {
    border-color: var(--border) !important;
    border-radius: 20px !important;
    background: rgba(255,255,255,0.76) !important;
    box-shadow: 0 7px 22px rgba(43, 35, 25, 0.035) !important;
}

.stButton > button {
    border-radius: 13px !important;
    border-color: #DAD3C8 !important;
    min-height: 38px !important;
    font-weight: 720 !important;
    font-size: 13.5px !important;
    background: rgba(255,255,255,0.86) !important;
}

.stButton > button:hover {
    border-color: #BBAA90 !important;
    color: #2B2118 !important;
    background: #FFFFFF !important;
}

.stButton > button[kind="primary"] {
    background: #24211D !important;
    border-color: #24211D !important;
    color: #FFF8ED !important;
    min-height: 42px !important;
}

.stButton > button[kind="primary"]:hover {
    background: #15130F !important;
    border-color: #15130F !important;
    color: #FFF8ED !important;
}

.stTextArea textarea {
    border-radius: 16px !important;
    border-color: var(--border) !important;
    font-size: 14.8px !important;
    background: #F5F6F9 !important;
    padding: 14px 16px !important;
}

.stTextArea textarea:focus {
    border-color: #BBAA90 !important;
    box-shadow: 0 0 0 1px rgba(132, 97, 42, 0.16) !important;
}

div[data-testid="stExpander"] {
    border-color: var(--border-soft) !important;
    border-radius: 15px !important;
    background: rgba(255, 255, 255, 0.72) !important;
}

hr {
    margin-top: 0.75rem !important;
    margin-bottom: 0.75rem !important;
}

@media (max-width: 960px) {
    .app-topbar {
        flex-direction: column;
        align-items: flex-start;
    }
    .app-actions {
        justify-content: flex-start;
    }
    .score-panel {
        flex-direction: column;
        align-items: flex-start;
    }
}
</style>
""", unsafe_allow_html=True)


# ---------------------------------------------------
# METHOD / MODEL INFORMATION SHOWN BEFORE AND AFTER ANALYSIS
# ---------------------------------------------------
METHOD_CARDS = [
    {
        "key": "claims",
        "shade": "card-shade-claims",
        "title": "Claim Classification",
        "kicker": "Zero-shot NLP",
        "model": "DistilBERT MNLI",
        "full_model": "typeform/distilbert-base-uncased-mnli",
        "short": "Separates factual claims from opinion and speculation.",
        "details": [
            "Uses a zero-shot classification pipeline with labels: factual claim, opinion, and speculation.",
            "The code also applies a factual-signal override for phrases such as according to, study, reports, evidence, causes, and shows.",
            "Meaning: the app first decides whether a sentence is something that can be checked before sending it to verification."
        ]
    },
    {
        "key": "facts",
        "shade": "card-shade-facts",
        "title": "Fact Verification",
        "kicker": "Semantic matching",
        "model": "MiniLM L6 v2",
        "full_model": "all-MiniLM-L6-v2",
        "short": "Compares factual claims with trusted evidence using similarity.",
        "details": [
            "Uses SentenceTransformer embeddings to compare each factual claim with evidence text.",
            "The app first tries trusted source URLs. If no direct trusted source is available, it uses a Wikipedia search fallback.",
            "Meaning: the score is based on semantic similarity, not only exact word matching."
        ]
    },
    {
        "key": "bias",
        "shade": "card-shade-bias",
        "title": "Bias / Emotion",
        "kicker": "Emotion model",
        "model": "DistilRoBERTa",
        "full_model": "j-hartmann/emotion-english-distilroberta-base",
        "short": "Detects emotional tone and loaded wording.",
        "details": [
            "Uses a transformer-based emotion classifier to detect the dominant emotional tone.",
            "The app also checks for loaded words such as shocking, disaster, clearly, dangerous, fake, corrupt, panic, and threat.",
            "Meaning: high emotional tone plus loaded words increases the bias risk score."
        ]
    },
    {
        "key": "citations",
        "shade": "card-shade-citations",
        "title": "Citation Quality",
        "kicker": "Source scoring",
        "model": "Domain rules",
        "full_model": "Trusted/weak domain + named-source rules",
        "short": "Checks whether sources look reliable, weak, or missing.",
        "details": [
            "Extracts URLs and named sources from the text.",
            "Trusted examples include WHO, UNICEF, United Nations, The Lancet, Nature, Reuters, BBC, AP News, CDC, NIH, .gov, and .edu domains.",
            "Meaning: this does not prove a claim is true, but it estimates whether the sources are credible enough to trust."
        ]
    }
]

METHOD_LOOKUP = {card["key"]: card for card in METHOD_CARDS}


# ---------------------------------------------------
# UI HELPER FUNCTIONS
# ---------------------------------------------------
def get_trust_label(score):
    if score >= 75:
        return (
            "High Reliability",
            "The text has strong support signals, but important claims should still be checked."
        )
    if score >= 50:
        return (
            "Needs Review",
            "The text has some useful signals, but claims, citations, or tone need closer checking."
        )
    return (
        "Low Reliability",
        "The text has weak reliability signals and should be verified before trusting it."
    )


def get_score_color(score):
    if score >= 75:
        return "#2E7D32"
    if score >= 50:
        return "#D49A13"
    return "#B9282E"


def render_top_bar():
    """Website-style top bar with no extra blank logo column."""
    st.markdown(
        '<div class="app-topbar">'
        '<div class="app-brand">'
        '<div class="logo-box">⚖️</div>'
        '<div>'
        '<div class="app-title">Ethical Analyser</div>'
        '<div class="app-subtitle">AI text reliability dashboard</div>'
        '</div>'
        '</div>'
        '<div class="app-actions">'
        '<span class="nav-pill">Claim</span>'
        '<span class="nav-pill">Fact</span>'
        '<span class="nav-pill">Bias</span>'
        '<span class="nav-pill">Sources</span>'
        '</div>'
        '</div>',
        unsafe_allow_html=True
    )


def render_section_title(title, subtitle=None):
    subtitle_html = ""
    if subtitle:
        subtitle_html = f'<div class="section-subtitle">{html.escape(subtitle)}</div>'

    st.markdown(
        f'<div class="section-title-row"><div>'
        f'<div class="section-title">{html.escape(title)}</div>'
        f'{subtitle_html}'
        f'</div></div>',
        unsafe_allow_html=True
    )


def render_score_circle(score):
    score = max(0, min(100, int(score)))
    angle = score * 3.6
    color = get_score_color(score)
    label, description = get_trust_label(score)

    st.markdown(f"""
    <div class="score-panel">
        <div class="score-circle" style="background: conic-gradient({color} {angle}deg, #E8E1D6 0deg);">
            <div class="score-inner">
                <div class="score-number">{score}</div>
                <div class="score-total">/100</div>
            </div>
        </div>
        <div class="score-copy">
            <div class="eyebrow">Overall Trust Score</div>
            <h2>{html.escape(label)}</h2>
            <p>{html.escape(description)}</p>
        </div>
    </div>
    """, unsafe_allow_html=True)


def get_dashboard_cards(result, source_links=None):
    if source_links is None:
        source_links = []

    cards = result.get("dashboard_cards")

    if not cards:
        classified_claims = result.get("classified_claims", [])
        fact_results = result.get("fact_results", [])
        bias = result.get("bias_result", {})
        citation = result.get("citation_result", {})

        cards = [
            {
                "key": "claims",
                "title": "Claim Classification",
                "value": len(classified_claims),
                "status": "Sentences analysed",
                "description": "Classifies the text into factual claims, opinions, or other statements."
            },
            {
                "key": "facts",
                "title": "Fact Verification",
                "value": len(fact_results),
                "status": "Claims checked",
                "description": "Checks factual claims using semantic similarity and available evidence."
            },
            {
                "key": "bias",
                "title": "Bias / Emotion",
                "value": f"{bias.get('bias_risk_score', 0)}/100",
                "status": bias.get("top_emotion", "Unknown"),
                "description": "Detects emotional language, bias risk, and loaded wording."
            },
            {
                "key": "citations",
                "title": "Citation Quality",
                "value": f"{citation.get('overall_score', 0)}/100",
                "status": citation.get("level", "Unknown"),
                "description": "Evaluates the quality and reliability of detected sources."
            }
        ]

    if source_links:
        cards.append(
            {
                "key": "hidden_links",
                "title": "Extracted Source Links",
                "value": len(source_links),
                "status": "Clickable links found",
                "description": "Shows hidden or captured source links from the browser extension."
            }
        )

    return cards


def render_card_details(card_key, result, source_links=None):
    if source_links is None:
        source_links = []

    if card_key == "claims":
        classified_claims = result.get("classified_claims", [])
        if not classified_claims:
            st.info("No claims were classified.")
            return

        for item in classified_claims:
            st.markdown(f"**Sentence:** {item.get('sentence', 'N/A')}")
            st.markdown(f"**AI Label:** {item.get('label', 'N/A')}")
            st.markdown(f"**Confidence:** {item.get('confidence', 'N/A')}")
            st.divider()

    elif card_key == "facts":
        fact_results = result.get("fact_results", [])
        if not fact_results:
            st.info("No factual claims found for verification.")
            return

        for item in fact_results:
            st.markdown(f"**Claim:** {item.get('claim', 'N/A')}")
            st.markdown(f"**Status:** {item.get('status', 'N/A')}")
            st.markdown(f"**Similarity:** {item.get('similarity', 'N/A')}")

            if item.get("evidence_type"):
                st.markdown(f"**Evidence Route:** {item.get('evidence_type')}")

            if item.get("source"):
                st.markdown(f"**Source:** {item.get('source')}")

            if item.get("summary"):
                st.info(item.get("summary"))

            st.divider()

    elif card_key == "bias":
        bias = result.get("bias_result", {})
        st.markdown(f"**Top Emotion:** {bias.get('top_emotion', 'N/A')}")
        st.markdown(f"**Emotion Confidence:** {bias.get('emotion_confidence', 'N/A')}")
        st.markdown(f"**Bias Risk Score:** {bias.get('bias_risk_score', 0)} / 100")

        biased_words = bias.get("biased_words", [])
        if biased_words:
            st.warning("Biased words found: " + ", ".join(biased_words))
        else:
            st.success("No strong biased keywords detected.")

    elif card_key == "citations":
        citation = result.get("citation_result", {})
        st.markdown(f"**Citation Score:** {citation.get('overall_score', 0)} / 100")
        st.markdown(f"**Level:** {citation.get('level', 'N/A')}")

        sources = citation.get("sources", [])
        if sources:
            for source in sources:
                source_label = source.get("url", "Detected source")
                quality = source.get("quality", "unknown quality")
                score = source.get("score", 0)
                st.markdown(f"- {source_label} → {quality} ({score}/100)")
        else:
            st.warning("No citations or links were found.")

    elif card_key == "hidden_links":
        if source_links:
            for link in source_links:
                st.markdown(f"- {link}")
        else:
            st.info("No hidden source links were captured.")

    else:
        st.info("No detailed view available for this card.")


def render_method_info(method_key):
    method = METHOD_LOOKUP.get(method_key)
    if not method:
        st.info("No method information available.")
        return

    st.markdown(f"### {method['title']}")
    st.markdown(f"**Approach:** {method['kicker']}")
    st.markdown(f"**Display name:** `{method['model']}`")
    st.markdown(f"**Full model / logic:** `{method['full_model']}`")
    st.write(method["short"])
    st.divider()

    for point in method["details"]:
        st.markdown(f"- {point}")


def render_result_dialog(card, result, source_links=None):
    if source_links is None:
        source_links = []

    st.markdown(f"### {card.get('title', 'Result Details')}")
    st.markdown(f"**Status:** {card.get('status', 'N/A')}")
    st.markdown(f"**Value:** {card.get('value', 'N/A')}")
    st.write(card.get("description", ""))
    st.divider()
    render_card_details(card.get("key"), result, source_links)


# ---------------------------------------------------
# POPUP / MODAL WINDOWS
# ---------------------------------------------------
def make_dialog(title, fn):
    """Use Streamlit dialogs when available, while supporting older signatures."""
    if not hasattr(st, "dialog"):
        return None

    try:
        params = inspect.signature(st.dialog).parameters
        if "dismissible" in params:
            return st.dialog(title, width="large", dismissible=True)(fn)
        return st.dialog(title, width="large")(fn)
    except Exception:
        return None


def _result_dialog_impl(card, result, source_links=None):
    render_result_dialog(card, result, source_links)


def _method_dialog_impl(method_key):
    render_method_info(method_key)


show_result_dialog = make_dialog("Analysis Result", _result_dialog_impl)
show_method_dialog = make_dialog("How this check works", _method_dialog_impl)

if show_result_dialog is None:
    def show_result_dialog(card, result, source_links=None):
        st.warning("Your Streamlit version does not support popup dialogs. Run: pip install --upgrade streamlit")
        render_result_dialog(card, result, source_links)

if show_method_dialog is None:
    def show_method_dialog(method_key):
        st.warning("Your Streamlit version does not support popup dialogs. Run: pip install --upgrade streamlit")
        render_method_info(method_key)


def render_method_cards():
    render_section_title(
        "Analysis methods",
        "Each card shows the model or rule used before you run an analysis."
    )
    st.markdown(
        '<div style="height: 1rem;"></div>',
        unsafe_allow_html=True
    )
    cols = st.columns(4, gap="large")

    for index, (method, col) in enumerate(zip(METHOD_CARDS, cols)):
        with col:
            with st.container(border=True):
                st.markdown(
                    f"""
                    <div class="info-card {html.escape(method['shade'])}">
                        <div class="card-content-pad">
                            <div>
                                <div class="card-kicker">{html.escape(method['kicker'])}</div>
                                <div class="card-title">{html.escape(method['title'])}</div>
                                <div class="card-desc">{html.escape(method['short'])}</div>
                            </div>
                            <div><span class="model-chip">{html.escape(method['model'])}</span></div>
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True
                )

                if st.button(
                    "👁 View method",
                    key=f"method_info_{method['key']}_{index}",
                    use_container_width=True
                ):
                    show_method_dialog(method["key"])


def render_result_cards(result, source_links=None):
    cards = get_dashboard_cards(result, source_links)

    render_section_title(
        "Analysis results",
        "The same four checks now show the actual result for your text."
    )
    st.markdown(
        '<div style="height: 1rem;"></div>',
        unsafe_allow_html=True
    )
    main_cards = [card for card in cards if card.get("key") != "hidden_links"]
    extra_cards = [card for card in cards if card.get("key") == "hidden_links"]

    cols = st.columns(4, gap="large")

    for index, (card, col) in enumerate(zip(main_cards[:4], cols)):
        method = METHOD_LOOKUP.get(card.get("key"), {})
        shade = method.get("shade", "card-shade-citations")

        with col:
            with st.container(border=True):
                st.markdown(
                    f"""
                    <div class="result-card {html.escape(shade)}">
                        <div class="card-content-pad">
                            <div>
                                <div class="card-kicker">{html.escape(method.get('kicker', 'Result'))}</div>
                                <div class="card-title">{html.escape(str(card.get('title', 'Result')))}</div>
                                <div class="card-value">{html.escape(str(card.get('value', '')))}</div>
                                <div class="card-status">{html.escape(str(card.get('status', '')))}</div>
                                <div class="card-desc">{html.escape(str(card.get('description', '')))}</div>
                            </div>
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True
                )

                b1, b2 = st.columns([1, 1])

                with b1:
                    if st.button(
                        "Details",
                        key=f"result_details_{card.get('key', 'card')}_{index}",
                        use_container_width=True
                    ):
                        show_result_dialog(card, result, source_links)

                with b2:
                    if st.button(
                        "👁 Info",
                        key=f"result_info_{card.get('key', 'card')}_{index}",
                        use_container_width=True
                    ):
                        show_method_dialog(card.get("key"))

    if extra_cards:
        st.markdown("")
        for index, card in enumerate(extra_cards):
            with st.container(border=True):
                col1, col2 = st.columns([4, 1])

                with col1:
                    st.markdown(
                        f"""
                        <div class="card-title">{html.escape(str(card.get('title', 'Result')))}</div>
                        <div class="card-status">{html.escape(str(card.get('status', '')))}</div>
                        <div class="card-desc">{html.escape(str(card.get('description', '')))}</div>
                        """,
                        unsafe_allow_html=True
                    )

                with col2:
                    if st.button(
                        "Details",
                        key=f"details_extra_{card.get('key', 'card')}_{index}",
                        use_container_width=True
                    ):
                        show_result_dialog(card, result, source_links)


# ---------------------------------------------------
# REUSABLE RESULT DISPLAY FUNCTION
# ---------------------------------------------------
def display_full_analysis(result, original_text=None, source_links=None):
    if source_links is None:
        source_links = []

    if original_text:
        with st.expander("Show full analyzed text and extracted links", expanded=False):
            st.markdown("### Full Analyzed Text")
            st.write(original_text)

            if source_links:
                st.markdown("### Extracted Clickable Source Links")
                for link in source_links:
                    st.markdown(f"- {link}")

    render_score_circle(result.get("trust_score", 0))

    render_result_cards(
        result=result,
        source_links=source_links
    )

    with st.expander("Generative AI Explanation", expanded=False):
        st.info(result.get("ai_explanation", "No explanation generated."))


# ---------------------------------------------------
# PAGE HEADER
# ---------------------------------------------------
render_top_bar()


# ---------------------------------------------------
# DETAILS MODE — when opened from browser extension
# Example: http://localhost:8501/?analysis_id=503fa4d9-...
# ---------------------------------------------------
analysis_id = st.query_params.get("analysis_id")

if analysis_id:
    try:
        response = requests.get(
            f"http://127.0.0.1:5000/result/{analysis_id}",
            timeout=10
        )

        if response.status_code == 200:
            stored_data = response.json()

            original_text = stored_data["text"]
            source_links = stored_data.get("source_links", [])
            result = stored_data["result"]

            display_full_analysis(
                result=result,
                original_text=original_text,
                source_links=source_links
            )

        else:
            st.error(
                "Analysis result could not be found. "
                "The Flask backend may have been restarted after the analysis."
            )

    except Exception:
        st.error(
            "Could not connect to the browser analysis API. "
            "Make sure browser_api.py is running."
        )

    st.stop()


# ---------------------------------------------------
# NORMAL MANUAL ANALYSIS MODE
# ---------------------------------------------------
if "analysis_result" not in st.session_state:
    st.session_state.analysis_result = None

if "analysis_text" not in st.session_state:
    st.session_state.analysis_text = ""

if "analysis_source_links" not in st.session_state:
    st.session_state.analysis_source_links = []


# Initial input page
if st.session_state.analysis_result is None:
    with st.container(border=True):
        st.markdown(
            '<div class="panel-label">Text to Analyse</div>',
            unsafe_allow_html=True
        )

        text = st.text_area(
            "Paste text to analyze:",
            height=155,
            placeholder="Paste an online article, AI output, or social media post...",
            label_visibility="collapsed"
        )

        analyze_clicked = st.button(
            "Analyze with AI",
            type="primary",
            use_container_width=True
        )

    render_method_cards()

    if analyze_clicked:
        if not text.strip():
            st.warning("Please enter text.")
        else:
            with st.spinner("Running AI analysis..."):
                result = analyze_full_text(
                    text=text,
                    source_links=[]
                )

            st.session_state.analysis_result = result
            st.session_state.analysis_text = text
            st.session_state.analysis_source_links = []
            st.rerun()

# Compact result page
else:
    display_full_analysis(
        result=st.session_state.analysis_result,
        original_text=st.session_state.analysis_text,
        source_links=st.session_state.analysis_source_links
    )

    with st.expander("Analyze another text", expanded=False):
        new_text = st.text_area(
            "Paste new text:",
            height=150,
            value=st.session_state.analysis_text
        )

        col1, col2 = st.columns(2)

        with col1:
            rerun_clicked = st.button(
                "Run new analysis",
                type="primary",
                use_container_width=True
            )

        with col2:
            clear_clicked = st.button(
                "Clear result",
                use_container_width=True
            )

        if rerun_clicked:
            if not new_text.strip():
                st.warning("Please enter text.")
            else:
                with st.spinner("Running AI analysis..."):
                    result = analyze_full_text(
                        text=new_text,
                        source_links=[]
                    )

                st.session_state.analysis_result = result
                st.session_state.analysis_text = new_text
                st.session_state.analysis_source_links = []
                st.rerun()

        if clear_clicked:
            st.session_state.analysis_result = None
            st.session_state.analysis_text = ""
            st.session_state.analysis_source_links = []
            st.rerun()
