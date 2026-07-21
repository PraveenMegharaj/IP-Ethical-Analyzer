document.addEventListener("DOMContentLoaded", () => {
  const analyzeBtn = document.getElementById("analyzeBtn");

  analyzeBtn.addEventListener("click", analyzeText);
});


async function analyzeText() {
  const text = document.getElementById("text").value;
  const resultDiv = document.getElementById("result");
  const analyzeBtn = document.getElementById("analyzeBtn");

  if (!text.trim()) {
    resultDiv.innerHTML = `
      <div class="error">
        Please paste text first.
      </div>
    `;
    return;
  }

  // Loading state
  analyzeBtn.disabled = true;
  analyzeBtn.innerText = "Analyzing...";
  analyzeBtn.style.opacity = "0.7";
  analyzeBtn.style.cursor = "not-allowed";

  resultDiv.innerHTML = `
    <div class="loading">
      <div class="spinner"></div>
      <div>Analyzing with AI...</div>
    </div>
  `;

  try {
    const response = await fetch("http://127.0.0.1:5000/analyze", {
      method: "POST",
      headers: {
        "Content-Type": "application/json"
      },
      body: JSON.stringify({ text: text })
    });

    if (!response.ok) {
      throw new Error("Backend returned an error.");
    }

    const data = await response.json();

    let reliabilityClass = "medium";
    let reliabilityLabel = "Medium reliability";

    if (data.trust_score >= 75) {
      reliabilityClass = "high";
      reliabilityLabel = "High reliability";
    } else if (data.trust_score < 50) {
      reliabilityClass = "low";
      reliabilityLabel = "Low reliability";
    }

    resultDiv.innerHTML = `
      <div class="score-card">
        <div class="score-title">Overall Trust Score</div>
        <div class="score-value">${data.trust_score}/100</div>

        <div class="score-label ${reliabilityClass}">
          ${reliabilityLabel}
        </div>

        <div class="explanation-title">Quick Explanation</div>
        <div class="explanation-text">
          ${data.explanation}
        </div>

        <button class="details-btn" id="detailsBtn">
          View Full Details
        </button>
      </div>
    `;

    document.getElementById("detailsBtn").addEventListener("click", () => {
      chrome.tabs.create({
        url: `http://localhost:8501/?analysis_id=${data.analysis_id}`
      });
    });

  } catch (error) {
    resultDiv.innerHTML = `
      <div class="error">
        Backend is not running or the analysis failed.
        Start <b>browser_api.py</b> and try again.
      </div>
    `;
  } finally {
    analyzeBtn.disabled = false;
    analyzeBtn.innerText = "Analyze Text";
    analyzeBtn.style.opacity = "1";
    analyzeBtn.style.cursor = "pointer";
  }
}