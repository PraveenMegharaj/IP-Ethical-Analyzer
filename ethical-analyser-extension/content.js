let lastAnalyzedSignature = "";
let latestCandidateSignature = "";
let stableTimer = null;
let isAnalyzing = false;
let currentSubmissionId = 0;
let submissionBaselineSignature = "";
let pendingAnalyses = [];
let queuedSignatures = new Set();
let detectionPollTimer = null;
let lastSubmissionText = "";
let lastSubmissionTime = 0;

let latestTypedText = "";
let lastSubmittedUserText = "";
let promptWasSubmitted = false;

let recentGeneratedCandidates = [];
let currentSubmissionSourceLinks = new Set();

const MIN_TEXT_LENGTH = 40;
const STABILITY_WAIT_MS = 7000;


/* =========================================================
   1. Track when the user submits a prompt
========================================================= */

document.addEventListener("input", (event) => {
  const input = getTextInput(event.target);

  if (!input) {
    return;
  }

  latestTypedText = input.innerText || input.value || "";
}, true);


document.addEventListener("keydown", (event) => {
  const input = getTextInput(event.target);

  if (
    input &&
    event.key === "Enter" &&
    !event.shiftKey &&
    !event.isComposing
  ) {
    latestTypedText = input.innerText || input.value || latestTypedText;
    markPromptSubmitted();
  }
}, true);


document.addEventListener("click", (event) => {
  if (!(event.target instanceof Element)) {
    return;
  }

  const button = event.target.closest("button");

  if (!button) {
    return;
  }

  const ariaLabel = button.getAttribute("aria-label")?.toLowerCase() || "";
  const title = button.getAttribute("title")?.toLowerCase() || "";
  const text = button.innerText?.toLowerCase().trim() || "";

  const looksLikeSendButton =
    button.matches('[data-testid="send-button"]') ||
    ariaLabel.includes("send") ||
    ariaLabel.includes("submit") ||
    title.includes("send") ||
    title.includes("submit") ||
    text === "send";

  if (looksLikeSendButton) {
    const input = findActiveTextInput();

    if (input) {
      latestTypedText = input.innerText || input.value || latestTypedText;
    }

    markPromptSubmitted();
  }
}, true);


function getTextInput(target) {
  if (!(target instanceof Element)) {
    return null;
  }

  return target.closest(
    'textarea, [contenteditable="true"], #prompt-textarea'
  );
}


function findActiveTextInput() {
  const inputs = Array.from(document.querySelectorAll(
    '#prompt-textarea, textarea, [contenteditable="true"]'
  ));

  return inputs.find(input => input.offsetParent !== null) || inputs[0] || null;
}


function markPromptSubmitted() {
  const typed = cleanText(latestTypedText);

  if (!typed) {
    return;
  }

  const now = Date.now();

  if (
    typed === lastSubmissionText &&
    now - lastSubmissionTime < 1000
  ) {
    return;
  }

  lastSubmissionText = typed;
  lastSubmissionTime = now;
  lastSubmittedUserText = typed;
  latestTypedText = "";
  currentSubmissionId += 1;

  const existingBundle = extractLatestLLMAnswer();
  submissionBaselineSignature = bundleSignature(existingBundle);

  promptWasSubmitted = true;
  recentGeneratedCandidates = [];
  currentSubmissionSourceLinks = new Set();
  latestCandidateSignature = "";

  clearTimeout(stableTimer);
  startDetectionPolling(currentSubmissionId);
}


function startDetectionPolling(submissionId) {
  clearInterval(detectionPollTimer);

  detectionPollTimer = setInterval(() => {
    if (
      !promptWasSubmitted ||
      submissionId !== currentSubmissionId
    ) {
      clearInterval(detectionPollTimer);
      detectionPollTimer = null;
      return;
    }

    scheduleStableAnswerCheck();
  }, 1000);
}


function stopDetectionPolling(submissionId) {
  if (submissionId !== currentSubmissionId) {
    return;
  }

  clearInterval(detectionPollTimer);
  detectionPollTimer = null;
}


/* =========================================================
   2. Text cleaning
========================================================= */

function cleanText(text) {
  if (!text) {
    return "";
  }

  return text
    .replace(/\u200B/g, "")
    .replace(/\s+/g, " ")
    .replace(/^Gemini said\s*/i, "")
    .replace(/^Claude said\s*/i, "")
    .replace(/^ChatGPT said\s*/i, "")
    .trim();
}


function isSameAsUserPrompt(text) {
  const cleanedText = cleanText(text);
  const cleanedPrompt = cleanText(lastSubmittedUserText);

  if (!cleanedText || !cleanedPrompt) {
    return false;
  }

  return cleanedText === cleanedPrompt;
}


function isNoiseText(text) {
  const cleaned = cleanText(text).toLowerCase();

  const exactNoisePatterns = [
    "gemini is ai and can make mistakes",
    "your privacy and gemini",
    "opens in a new window",
    "terms and privacy",
    "claude can make mistakes",
    "chatgpt can make mistakes",
    "check important info",
    "google apps",
    "new chat",
    "settings and help"
  ];

  return exactNoisePatterns.some(pattern => cleaned === pattern);
}


function isValidCandidateText(text) {
  const cleaned = cleanText(text);

  if (!cleaned) {
    return false;
  }

  if (cleaned.length < MIN_TEXT_LENGTH) {
    return false;
  }

  if (cleaned.length > 12000) {
    return false;
  }

  if (isSameAsUserPrompt(cleaned)) {
    return false;
  }

  if (isNoiseText(cleaned)) {
    return false;
  }

  return true;
}


/* =========================================================
   3. Extract real URLs hidden behind clickable source labels
========================================================= */

const LINK_ELEMENT_SELECTOR = [
  "a",
  "area",
  '[role="link"]',
  "[href]",
  "[cite]",
  "[data-href]",
  "[data-url]",
  "[data-source-url]",
  "[data-citation-url]",
  "[data-redirect-url]",
  "[data-target-url]",
  "[data-link]",
  "[data-source]",
  "[data-citation]"
].join(", ");

const RESPONSE_OR_CITATION_SELECTOR = [
  '[data-message-author-role="assistant"]',
  "model-response",
  "message-content",
  ".model-response-text",
  ".response-container",
  "response-container",
  '[data-testid="assistant-message"]',
  '[data-testid*="assistant"]',
  '[data-testid*="citation"]',
  '[data-testid*="source"]',
  '[class*="citation"]',
  '[class*="source-link"]',
  '[class*="source-card"]',
  '[aria-label*="citation" i]',
  '[aria-label*="source" i]',
  '[role="dialog"]',
  '[role="tooltip"]'
].join(", ");

const REDIRECT_PARAMETER_NAMES = [
  "url",
  "q",
  "target",
  "redirect",
  "redirect_url",
  "destination",
  "dest",
  "href",
  "u",
  "continue",
  "next"
];

const URL_VALUE_PATTERN = /(?:https?:\/\/|\/\/|www\.)[^\s<>"'\\]+|(?<!@)\b(?:[a-zA-Z0-9-]+\.)+[a-zA-Z]{2,}(?:\/[^\s<>"'\\]*)?/gi;


function decodeUrlValue(value) {
  let decoded = String(value || "").replace(/\\\//g, "/").replace(/&amp;/gi, "&");

  for (let attempt = 0; attempt < 3; attempt += 1) {
    try {
      const nextValue = decodeURIComponent(decoded);

      if (nextValue === decoded) {
        break;
      }

      decoded = nextValue;
    } catch (error) {
      break;
    }
  }

  return decoded;
}


function extractUrlCandidates(value) {
  if (!value) {
    return [];
  }

  const decoded = decodeUrlValue(value);
  const matches = decoded.match(URL_VALUE_PATTERN) || [];
  const candidates = [decoded, ...matches];

  return [...new Set(candidates.map(candidate => candidate.trim()).filter(Boolean))];
}


function normalizeExternalSourceUrl(rawHref, depth = 0) {
  if (!rawHref || depth > 4) {
    return null;
  }

  const decodedHref = decodeUrlValue(rawHref)
    .trim()
    .replace(/^["'(<\[]+|["')>\],.;!?]+$/g, "");

  if (!decodedHref || /^(javascript|mailto|tel|data|blob):/i.test(decodedHref)) {
    return null;
  }

  try {
    const preparedHref = decodedHref.startsWith("//")
      ? `${window.location.protocol}${decodedHref}`
      : decodedHref;

    const url = new URL(preparedHref, window.location.href);

    if (!["http:", "https:"].includes(url.protocol)) {
      return null;
    }

    for (const parameterName of REDIRECT_PARAMETER_NAMES) {
      const redirected = url.searchParams.get(parameterName);

      if (!redirected) {
        continue;
      }

      for (const candidate of extractUrlCandidates(redirected)) {
        const normalizedRedirect = normalizeExternalSourceUrl(candidate, depth + 1);

        if (normalizedRedirect) {
          return normalizedRedirect;
        }
      }
    }

    const currentHost = window.location.hostname.toLowerCase();
    const host = url.hostname.toLowerCase();

    const internalHosts = [
      "chatgpt.com",
      "chat.openai.com",
      "gemini.google.com",
      "claude.ai"
    ];

    if (
      host === currentHost ||
      internalHosts.some(internal =>
        host === internal || host.endsWith(`.${internal}`)
      )
    ) {
      return null;
    }

    url.hash = "";
    return url.href;
  } catch (error) {
    return null;
  }
}


function getLinkAttributeValues(element) {
  const values = [];

  if (!(element instanceof Element)) {
    return values;
  }

  if (typeof element.href === "string" && element.href) {
    values.push(element.href);
  }

  Array.from(element.attributes || []).forEach(attribute => {
    const name = attribute.name.toLowerCase();

    if (
      name === "href" ||
      name === "cite" ||
      name === "aria-label" ||
      name === "title" ||
      name.includes("url") ||
      name.includes("href") ||
      name.includes("source") ||
      name.includes("citation") ||
      name.includes("redirect")
    ) {
      values.push(attribute.value);
    }
  });

  if (element.matches('a, area, [role="link"]')) {
    values.push(element.textContent || "");
  }

  return values;
}


function extractSourceLinksFromElement(element) {
  if (!(element instanceof Element)) {
    return [];
  }

  const linkElements = [
    element,
    ...element.querySelectorAll(LINK_ELEMENT_SELECTOR)
  ];

  const rawValues = [
    element.innerText || element.textContent || ""
  ];

  linkElements.forEach(linkElement => {
    rawValues.push(...getLinkAttributeValues(linkElement));
  });

  const links = [];

  rawValues.forEach(value => {
    extractUrlCandidates(value).forEach(candidate => {
      const normalizedUrl = normalizeExternalSourceUrl(candidate);

      if (normalizedUrl) {
        links.push(normalizedUrl);
      }
    });
  });

  return [...new Set(links)];
}


function mergeSourceLinks(...linkGroups) {
  const links = linkGroups.flat().filter(Boolean);
  return [...new Set(links)].sort();
}


function isLikelyResponseOrCitationElement(element) {
  if (!(element instanceof Element)) {
    return false;
  }

  return Boolean(
    element.matches(RESPONSE_OR_CITATION_SELECTOR) ||
    element.closest(RESPONSE_OR_CITATION_SELECTOR) ||
    element.querySelector(RESPONSE_OR_CITATION_SELECTOR)
  );
}


function collectSourceLinksFromNode(node) {
  if (!promptWasSubmitted || !(node instanceof Element)) {
    return;
  }

  if (!isLikelyResponseOrCitationElement(node)) {
    return;
  }

  extractSourceLinksFromElement(node).forEach(link => {
    currentSubmissionSourceLinks.add(link);
  });
}


/* =========================================================
   4. Build a clean response bundle: text + hidden URLs
========================================================= */

function buildResponseBundle(element) {
  if (!element) {
    return null;
  }

  const text = cleanText(element.innerText);

  const sourceLinks = mergeSourceLinks(
    extractSourceLinksFromElement(element),
    [...currentSubmissionSourceLinks]
  );

  if (!isValidCandidateText(text)) {
    return null;
  }

  return {
    text,
    source_links: sourceLinks
  };
}


function bundleSignature(bundle) {
  if (!bundle) {
    return "";
  }

  return `${bundle.text}|||${bundle.source_links.join("|||")}`;
}


/* =========================================================
   5. ChatGPT extraction
========================================================= */

function extractLatestChatGPTAnswer() {
  const assistantMessages = document.querySelectorAll(
    '[data-message-author-role="assistant"]'
  );

  if (!assistantMessages.length) {
    return null;
  }

  const latest = assistantMessages[assistantMessages.length - 1];
  return buildResponseBundle(latest);
}


/* =========================================================
   6. Gemini extraction
========================================================= */

function extractLatestGeminiAnswer() {
  const selectors = [
    "model-response",
    "message-content",
    ".model-response-text",
    ".response-container",
    "response-container",
    '[class*="model-response"]',
    '[class*="response-content"]'
  ];

  const bundles = [];

  selectors.forEach(selector => {
    document.querySelectorAll(selector).forEach(element => {
      const bundle = buildResponseBundle(element);

      if (bundle) {
        bundles.push(bundle);
      }
    });
  });

  if (!bundles.length) {
    return getBestRecentGeneratedCandidate();
  }

  return bundles[bundles.length - 1];
}


/* =========================================================
   7. Claude extraction
========================================================= */

function extractLatestClaudeAnswer() {
  const selectors = [
    '[data-testid="assistant-message"]',
    '[data-testid*="assistant"]',
    ".font-claude-message",
    '[class*="assistant"]',
    "article"
  ];

  const bundles = [];

  selectors.forEach(selector => {
    document.querySelectorAll(selector).forEach(element => {
      const bundle = buildResponseBundle(element);

      if (bundle) {
        bundles.push(bundle);
      }
    });
  });

  if (!bundles.length) {
    return getBestRecentGeneratedCandidate();
  }

  return bundles[bundles.length - 1];
}


/* =========================================================
   8. DOM fallback for Gemini / Claude
========================================================= */

function collectCandidateFromNode(node) {
  if (!promptWasSubmitted) {
    return;
  }

  if (!(node instanceof HTMLElement)) {
    return;
  }

  collectSourceLinksFromNode(node);

  const bundle = buildResponseBundle(node);

  if (!bundle) {
    return;
  }

  recentGeneratedCandidates.push(bundle);

  if (recentGeneratedCandidates.length > 80) {
    recentGeneratedCandidates.shift();
  }
}


function getBestRecentGeneratedCandidate() {
  const valid = recentGeneratedCandidates.filter(bundle =>
    bundle && isValidCandidateText(bundle.text)
  );

  if (!valid.length) {
    return null;
  }

  valid.sort((a, b) => b.text.length - a.text.length);

  return valid[0];
}


/* =========================================================
   9. Platform router
========================================================= */

function extractLatestLLMAnswer() {
  const hostname = window.location.hostname;

  if (
    hostname.includes("chatgpt.com") ||
    hostname.includes("chat.openai.com")
  ) {
    return extractLatestChatGPTAnswer();
  }

  if (hostname.includes("gemini.google.com")) {
    return extractLatestGeminiAnswer();
  }

  if (hostname.includes("claude.ai")) {
    return extractLatestClaudeAnswer();
  }

  return null;
}


/* =========================================================
   10. Floating popup helpers
========================================================= */

function removeOldPopup() {
  const oldPopup = document.getElementById("ethical-analyser-popup");

  if (oldPopup) {
    oldPopup.remove();
  }
}


function getReliabilityInfo(score) {
  if (score >= 75) {
    return {
      label: "High reliability",
      bg: "#dcfce7",
      color: "#166534"
    };
  }

  if (score >= 50) {
    return {
      label: "Medium reliability",
      bg: "#fef3c7",
      color: "#92400e"
    };
  }

  return {
    label: "Low reliability",
    bg: "#fee2e2",
    color: "#991b1b"
  };
}


function injectSpinnerStyle() {
  if (document.getElementById("ethical-spinner-style")) {
    return;
  }

  const style = document.createElement("style");
  style.id = "ethical-spinner-style";

  style.textContent = `
    .ethical-spinner {
      width: 22px;
      height: 22px;
      border: 3px solid #d1d5db;
      border-top: 3px solid #4f46e5;
      border-radius: 50%;
      animation: ethicalSpin 0.8s linear infinite;
    }

    @keyframes ethicalSpin {
      0% {
        transform: rotate(0deg);
      }

      100% {
        transform: rotate(360deg);
      }
    }
  `;

  document.head.appendChild(style);
}


function createLoadingPopup() {
  removeOldPopup();
  injectSpinnerStyle();

  const popup = document.createElement("div");
  popup.id = "ethical-analyser-popup";

  popup.style.position = "fixed";
  popup.style.bottom = "25px";
  popup.style.right = "25px";
  popup.style.width = "320px";
  popup.style.padding = "16px";
  popup.style.background = "white";
  popup.style.border = "1px solid #ddd";
  popup.style.borderRadius = "12px";
  popup.style.boxShadow = "0 4px 16px rgba(0,0,0,0.18)";
  popup.style.zIndex = "999999";
  popup.style.fontFamily = "Arial, sans-serif";
  popup.style.color = "#111";

  popup.innerHTML = `
    <div style="font-size:16px; font-weight:bold; margin-bottom:14px;">
      Ethical Analyser
    </div>

    <div style="display:flex; align-items:center; gap:10px;">
      <div class="ethical-spinner"></div>
      <div style="font-size:14px;">
        Analyzing generated answer...
      </div>
    </div>
  `;

  document.body.appendChild(popup);
}


function createScorePopup(data) {
  removeOldPopup();

  const popup = document.createElement("div");
  popup.id = "ethical-analyser-popup";

  popup.style.position = "fixed";
  popup.style.bottom = "25px";
  popup.style.right = "25px";
  popup.style.width = "320px";
  popup.style.padding = "16px";
  popup.style.background = "white";
  popup.style.border = "1px solid #ddd";
  popup.style.borderRadius = "12px";
  popup.style.boxShadow = "0 4px 16px rgba(0,0,0,0.18)";
  popup.style.zIndex = "999999";
  popup.style.fontFamily = "Arial, sans-serif";
  popup.style.color = "#111";

  const reliability = getReliabilityInfo(data.trust_score);

  popup.innerHTML = `
    <div style="
      display:flex;
      justify-content:space-between;
      align-items:center;
      margin-bottom:10px;
    ">
      <div style="font-size:16px; font-weight:bold;">
        Ethical Analyser
      </div>

      <button id="ethical-close-btn"
        style="
          border:none;
          background:#f3f4f6;
          border-radius:50%;
          width:28px;
          height:28px;
          cursor:pointer;
          font-size:18px;
        ">
        ×
      </button>
    </div>

    <div style="font-size:13px; color:#6b7280;">
      Overall Trust Score
    </div>

    <div style="font-size:30px; font-weight:bold; margin:4px 0 8px 0;">
      ${data.trust_score}/100
    </div>

    <div style="
      display:inline-block;
      padding:6px 10px;
      border-radius:999px;
      font-size:13px;
      font-weight:bold;
      margin-bottom:12px;
      background:${reliability.bg};
      color:${reliability.color};
    ">
      ${reliability.label}
    </div>

    <div style="
      font-size:13px;
      color:#4b5563;
      line-height:1.45;
      margin-bottom:12px;
    ">
      This score was generated automatically from the latest AI response.
    </div>

    <button id="ethical-details-btn"
      style="
        width:100%;
        padding:10px;
        border:none;
        border-radius:8px;
        cursor:pointer;
        font-weight:bold;
        background:#111827;
        color:white;
      ">
      View Details
    </button>
  `;

  document.body.appendChild(popup);

  document.getElementById("ethical-details-btn").addEventListener("click", () => {
    const detailsUrl =
      `http://localhost:8501/?analysis_id=${data.analysis_id}`;

    window.open(detailsUrl, "_blank");
    popup.remove();
  });

  document.getElementById("ethical-close-btn").addEventListener("click", () => {
    popup.remove();
  });
}


function createErrorPopup() {
  removeOldPopup();

  const popup = document.createElement("div");
  popup.id = "ethical-analyser-popup";

  popup.style.position = "fixed";
  popup.style.bottom = "25px";
  popup.style.right = "25px";
  popup.style.width = "320px";
  popup.style.padding = "16px";
  popup.style.background = "white";
  popup.style.border = "1px solid #ddd";
  popup.style.borderRadius = "12px";
  popup.style.boxShadow = "0 4px 16px rgba(0,0,0,0.18)";
  popup.style.zIndex = "999999";
  popup.style.fontFamily = "Arial, sans-serif";
  popup.style.color = "#111";

  popup.innerHTML = `
    <div style="
      display:flex;
      justify-content:space-between;
      align-items:center;
      margin-bottom:10px;
    ">
      <div style="font-size:16px; font-weight:bold;">
        Ethical Analyser
      </div>

      <button id="ethical-close-btn"
        style="
          border:none;
          background:#f3f4f6;
          border-radius:50%;
          width:28px;
          height:28px;
          cursor:pointer;
          font-size:18px;
        ">
        ×
      </button>
    </div>

    <div style="
      background:#fee2e2;
      color:#991b1b;
      padding:10px;
      border-radius:8px;
      font-size:13px;
      line-height:1.4;
    ">
      Could not analyze the generated answer.
      Make sure <b>browser_api.py</b> is running.
    </div>
  `;

  document.body.appendChild(popup);

  document.getElementById("ethical-close-btn").addEventListener("click", () => {
    popup.remove();
  });
}


/* =========================================================
   11. Send bundle to backend
========================================================= */

function analyzeDetectedBundle(bundle, submissionId = currentSubmissionId) {
  if (!bundle || !isValidCandidateText(bundle.text)) {
    return;
  }

  const signature = bundleSignature(bundle);

  if (
    signature === lastAnalyzedSignature ||
    queuedSignatures.has(signature)
  ) {
    return;
  }

  queuedSignatures.add(signature);

  const analysis = {
    bundle,
    submissionId,
    signature
  };

  if (submissionId === currentSubmissionId) {
    promptWasSubmitted = false;
    stopDetectionPolling(submissionId);
  }

  if (isAnalyzing) {
    pendingAnalyses.push(analysis);
    return;
  }

  startAnalysis(analysis);
}


function startAnalysis(analysis) {
  isAnalyzing = true;
  createLoadingPopup();

  try {
    chrome.runtime.sendMessage(
      {
        type: "ANALYZE_TEXT",
        text: analysis.bundle.text,
        source_links: analysis.bundle.source_links
      },
      response => {
        if (chrome.runtime.lastError) {
          console.error(
            "Ethical Analyser message error:",
            chrome.runtime.lastError.message
          );

          createErrorPopup();
          finishAnalysis(analysis, false);
          return;
        }

        if (!response || !response.success) {
          console.error("Ethical Analyser backend error.");
          createErrorPopup();
          finishAnalysis(analysis, false);
          return;
        }

        lastAnalyzedSignature = analysis.signature;
        createScorePopup(response.data);
        finishAnalysis(analysis, true);
      }
    );
  } catch (error) {
    console.error(
      "Extension context invalidated. Refresh this LLM page after reloading the extension.",
      error
    );

    createErrorPopup();
    finishAnalysis(analysis, false);
  }
}


function finishAnalysis(analysis, success) {
  isAnalyzing = false;
  queuedSignatures.delete(analysis.signature);

  if (!success && analysis.submissionId === currentSubmissionId) {
    promptWasSubmitted = false;
    stopDetectionPolling(analysis.submissionId);
  }

  processNextPendingAnalysis();
}


function processNextPendingAnalysis() {
  if (isAnalyzing || !pendingAnalyses.length) {
    return;
  }

  const nextAnalysis = pendingAnalyses.shift();
  startAnalysis(nextAnalysis);
}


function isLLMStillGenerating() {
  const buttons = Array.from(document.querySelectorAll("button"));

  return buttons.some(button => {
    const label = (
      button.getAttribute("aria-label") ||
      button.getAttribute("title") ||
      button.innerText ||
      ""
    ).toLowerCase();

    return (
      label.includes("stop generating") ||
      label.includes("stop streaming") ||
      label.includes("stop response")
    );
  });
}


/* =========================================================
   12. Wait until output stabilizes
========================================================= */

function scheduleStableAnswerCheck(force = false) {
  if (!promptWasSubmitted) {
    return;
  }

  const currentBundle = extractLatestLLMAnswer();

  if (!currentBundle) {
    return;
  }

  const currentSignature = bundleSignature(currentBundle);

  if (currentSignature === submissionBaselineSignature) {
    return;
  }

  if (
    currentSignature !== latestCandidateSignature ||
    force
  ) {
    latestCandidateSignature = currentSignature;

    clearTimeout(stableTimer);

    const scheduledSubmissionId = currentSubmissionId;

    stableTimer = setTimeout(() => {
      if (
        !promptWasSubmitted ||
        scheduledSubmissionId !== currentSubmissionId
      ) {
        return;
      }

      if (isLLMStillGenerating()) {
        scheduleStableAnswerCheck(true);
        return;
      }

      const finalBundle = extractLatestLLMAnswer();

      if (!finalBundle) {
        return;
      }

      const finalSignature = bundleSignature(finalBundle);

      if (
        finalSignature !== submissionBaselineSignature &&
        finalSignature === latestCandidateSignature
      ) {
        analyzeDetectedBundle(finalBundle, scheduledSubmissionId);
      }
    }, STABILITY_WAIT_MS);
  }
}


/* =========================================================
   13. Observe page mutations
========================================================= */

const observer = new MutationObserver((mutations) => {
  if (!promptWasSubmitted) {
    return;
  }

  mutations.forEach(mutation => {
    mutation.addedNodes.forEach(node => {
      collectSourceLinksFromNode(node);
      collectCandidateFromNode(node);
    });

    if (mutation.target instanceof HTMLElement) {
      collectSourceLinksFromNode(mutation.target);
      collectCandidateFromNode(mutation.target);
    }
  });

  scheduleStableAnswerCheck();
});


observer.observe(document.body, {
  childList: true,
  subtree: true,
  characterData: true
});