# Ethical Analyser  
### AI-Powered Trustworthiness Analysis for LLM-Generated and Online Text

Ethical Analyser is a prototype system that evaluates the reliability of AI-generated or online text. It combines Natural Language Processing, machine learning, semantic verification, citation quality scoring, and a browser extension to help users better understand whether a generated answer should be trusted.

The project was developed to address ethical challenges in AI such as:

- Unsupported or weakly supported claims
- Emotional or biased language
- Low-quality or misleading citations
- Lack of transparency in AI-generated content

---

## Key Idea

When a user asks a question in an LLM platform such as **ChatGPT, Gemini, or Claude**, the browser extension automatically waits for the generated answer, analyzes it, and displays a small trust-score popup.

The user can then click **View Details** to open the main Ethical Analyser dashboard, where the full breakdown is shown.

---

## System Workflow

```text
User submits a prompt to ChatGPT / Gemini / Claude
        ↓
LLM generates a response
        ↓
Browser extension captures the final generated answer
        ↓
Hidden clickable source links are also extracted
        ↓
Text and links are sent to the Flask backend
        ↓
Ethical Analyser runs the full analysis pipeline
        ↓
Popup displays Trust Score + Reliability Level
        ↓
User clicks “View Details”
        ↓
Streamlit dashboard opens with complete explanation
