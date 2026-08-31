let currentResult = null;
let currentAnalysisId = null;
let brainstormQuestions = [];


document.addEventListener("DOMContentLoaded", () => {
    bindMainTabs();
    bindReuseTabs();
    bindAnalysisForm();
    bindBrainstormer();

    const params = new URLSearchParams(window.location.search);
    currentAnalysisId = params.get("analysis_id");
    switchMainTab(params.get("tab") || "analyse");

    if (currentAnalysisId) {
        loadAnalysis(currentAnalysisId);
    } else {
        showEmpty();
        renderReviewer();
        renderChecklist();
    }
});


function bindMainTabs() {
    document.querySelectorAll(".main-tab").forEach(button => {
        button.addEventListener("click", () => {
            switchMainTab(button.dataset.tab);
        });
    });
}


function switchMainTab(tabName) {
    const availableTabs = [
        "analyse",
        "reuse",
        "checklist"
    ];

    const tab = availableTabs.includes(tabName)
        ? tabName
        : "analyse";

    document.querySelectorAll(".main-tab").forEach(button => {
        button.classList.toggle(
            "active",
            button.dataset.tab === tab
        );
    });

    document.querySelectorAll(".tab-panel").forEach(panel => {
        panel.classList.remove("active");
    });

    document.getElementById(`${tab}Tab`).classList.add("active");

    const url = new URL(window.location.href);
    url.searchParams.set("tab", tab);
    window.history.replaceState({}, "", url);

    if (tab === "reuse") {
        renderReviewer();
    } else if (tab === "checklist") {
        renderChecklist();
    }
}


function bindReuseTabs() {
    document.querySelectorAll(".sub-tab").forEach(button => {
        button.addEventListener("click", () => {
            const view = button.dataset.reuseView;

            document.querySelectorAll(".sub-tab").forEach(item => {
                item.classList.toggle(
                    "active",
                    item === button
                );
            });

            document.querySelectorAll(".reuse-view").forEach(panel => {
                panel.classList.remove("active");
            });

            document.getElementById(`${view}View`).classList.add("active");
        });
    });
}


function bindAnalysisForm() {
    document
        .getElementById("analysisForm")
        .addEventListener("submit", submitAnalysis);
}


function bindBrainstormer() {
    document
        .getElementById("clarifyBrainstormBtn")
        .addEventListener("click", clarifyBrainstorm);

    document
        .getElementById("generateStrategyBtn")
        .addEventListener("click", generateBrainstormStrategy);
}


async function loadAnalysis(analysisId) {
    showLoading();

    try {
        const response = await fetch(
            `/api/result/${encodeURIComponent(analysisId)}`
        );

        const data = await response.json();

        if (!response.ok) {
            throw new Error(
                data.error || "Analysis could not be loaded."
            );
        }

        displayAnalysis(data);
    } catch (error) {
        showError(error.message);
    }
}


async function submitAnalysis(event) {
    event.preventDefault();

    const input = document
        .getElementById("analysisInput")
        .value
        .trim();

    const sourceLinks = document
        .getElementById("sourceLinks")
        .value
        .split(/[\n,]+/)
        .map(value => value.trim())
        .filter(value => {
            return (
                value.startsWith("http://")
                || value.startsWith("https://")
            );
        });

    if (!input) {
        showError("Enter text, a DOI or a resource URL.");
        return;
    }

    const resourceInput = isResourceLocator(input);

    const payload = {
        input: resourceInput ? input : "",
        text: resourceInput ? "" : input,
        source_links: sourceLinks,
        role: document.getElementById("userRole").value
    };

    showLoading();

    try {
        const response = await fetch("/api/analyze", {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify(payload)
        });

        const data = await response.json();

        if (!response.ok) {
            throw new Error(
                data.error || "Analysis failed."
            );
        }

        currentAnalysisId = data.analysis_id;

        const url = new URL(window.location.href);
        url.searchParams.set("analysis_id", currentAnalysisId);
        url.searchParams.set("tab", "analyse");
        window.history.replaceState({}, "", url);

        displayAnalysis(data);
    } catch (error) {
        showError(error.message);
    }
}


function isResourceLocator(value) {
    const text = String(value || "").trim();

    return (
        /^https?:\/\/\S+$/i.test(text)
        || /^10\.\d{4,9}\/\S+$/i.test(text)
    );
}


function displayAnalysis(result) {
    currentResult = result;

    hideStates();

    document
        .getElementById("resultsArea")
        .classList
        .remove("hidden");

    renderOverview();
    renderWarnings();
    renderReviewer();
    renderChecklist();
}


function renderOverview() {
    const resource = getPrimaryResource();

    const html = [
        renderTrustCard(currentResult?.trust),
        renderFairCard(resource?.fair),
        renderCopyrightCard(
            resource?.licence,
            resource?.ip
        ),
        renderFairR2LCard(resource?.fair_r2l)
    ].join("");

    const grid = document.getElementById("overviewGrid");
    grid.innerHTML = html;

    grid.querySelectorAll("[data-details]").forEach(button => {
        button.addEventListener("click", () => {
            showDetails(button.dataset.details);
        });
    });

    grid.querySelectorAll("[data-open-tab]").forEach(button => {
        button.addEventListener("click", () => {
            switchMainTab(button.dataset.openTab);
        });
    });
}


function renderTrustCard(trust) {
    if (!trust?.available) {
        return moduleUnavailable(
            "trust",
            "Trust",
            "Checks factual support, bias and citation quality."
        );
    }

    const score = numberOrNull(trust.score);
    const details = trust.details || {};
    const claims = details.fact_results || [];

    const reviewCount = claims.filter(item => {
        return item.status !== "Strong semantic match";
    }).length;

    const status = trustStatus(score);

    const finding = reviewCount
        ? `${reviewCount} factual claim${reviewCount === 1 ? "" : "s"} need review.`
        : "No major factual review issue was detected.";

    return `
        <article class="module-card trust">
            ${moduleHeader(
                "Trust",
                "Checks factual support, bias and citation quality.",
                status
            )}

            <div class="big-result">
                ${formatNumber(score)}
                <small>/ 100</small>
            </div>

            <div class="key-finding">
                ${escapeHtml(finding)}
            </div>

            ${moduleActions(
                "trust",
                "How the trust result is calculated"
            )}
        </article>
    `;
}


function renderFairCard(fair) {
    if (!fair?.principle_summary) {
        return moduleUnavailable(
            "fair",
            "FAIR",
            "Shows how easily the dataset can be found, accessed and reused."
        );
    }

    const order = [
        "findable",
        "accessible",
        "interoperable",
        "reusable"
    ];

    const rows = order.map(key => {
        const item = fair.principle_summary[key] || {};
        const earned = formatPoints(item.earned);
        const total = formatPoints(item.total);
        const level = item.level || "unknown";

        return `
            <div class="fair-row">
                <strong>
                    ${escapeHtml(item.name || titleCase(key))}
                </strong>

                <span class="fair-points">
                    ${earned} of ${total}
                </span>

                <span class="level-badge ${levelClass(level)}">
                    ${escapeHtml(titleCase(level))}
                </span>
            </div>
        `;
    }).join("");

    const estimate = fair.is_estimate
        ? "Metadata estimate"
        : "F-UJI result";

    const status = {
        label: estimate,
        className: fair.is_estimate
            ? "review"
            : "good"
    };

    return `
        <article class="module-card fair">
            ${moduleHeader(
                "FAIR",
                "Shows how easily the dataset can be found, accessed and reused.",
                status
            )}

            <div class="fair-list">
                ${rows}
            </div>

            ${moduleActions(
                "fair",
                "How F-UJI produced these levels"
            )}
        </article>
    `;
}


function renderCopyrightCard(licence, copyrightResult) {
    if (!licence) {
        return moduleUnavailable(
            "copyright",
            "Copyright & Licence",
            "Explains what the detected licence allows and requires."
        );
    }

    const detected = licence.detected === true;

    const name = (
        licence.spdx_id
        || licence.name
        || "Licence not recognised"
    );

    const permissions = [
        permissionChip(
            "Share",
            licence.redistribution
        ),
        permissionChip(
            "Adapt",
            licence.adaptations
        ),
        permissionChip(
            "Commercial",
            licence.commercial
        )
    ].join("");

    const status = detected
        ? {
            label: "Licence detected",
            className: "good"
        }
        : {
            label: "Needs review",
            className: "review"
        };

    let obligation = "Attribution requirements are unclear.";

    if (licence.attribution === true) {
        obligation = "Attribution is required.";
    } else if (licence.attribution === false) {
        obligation = (
            "Attribution is not required by the detected licence."
        );
    }

    return `
        <article class="module-card copyright">
            ${moduleHeader(
                "Copyright & Licence",
                "Explains what the detected licence allows and requires.",
                status
            )}

            <div class="big-result">
                ${escapeHtml(name)}
            </div>

            <div class="permission-row">
                ${permissions}
            </div>

            <div class="key-finding">
                ${escapeHtml(obligation)}
            </div>

            ${moduleActions(
                "copyright",
                "How the licence was interpreted"
            )}
        </article>
    `;
}


function renderFairR2LCard(result) {
    if (!result) {
        return moduleUnavailable(
            "fair_r2l",
            "FAIR-R²L",
            "Guides responsible and AI-ready dataset reuse."
        );
    }

    const label = (
        result.classification_label
        || "Needs review"
    );

    const status = classificationStatus(label);

    const pending = (
        result.pending_critical_reviews
        || []
    ).length;

    const finding = pending
        ? `${pending} critical check${pending === 1 ? "" : "s"} still need confirmation.`
        : "No critical review is pending.";

    return `
        <article class="module-card r2l">
            ${moduleHeader(
                "FAIR-R²L",
                "Guides responsible and AI-ready dataset reuse.",
                status
            )}

            <div class="big-result">
                ${escapeHtml(label)}
            </div>

            <div class="dual-metric">
                ${metricBox(
                    "Readiness",
                    percent(result.readiness)
                )}

                ${metricBox(
                    "Review completion",
                    percent(result.completion)
                )}
            </div>

            <div class="key-finding">
                ${escapeHtml(finding)}
            </div>

            <div class="module-actions">
                <button
                    class="detail-button"
                    data-details="fair_r2l"
                    type="button"
                >
                    Details
                </button>

                <button
                    class="small-button"
                    data-open-tab="checklist"
                    type="button"
                >
                    Open checklist
                </button>
            </div>
        </article>
    `;
}


function moduleHeader(title, description, status) {
    return `
        <div class="module-head">
            <div>
                <span class="eyebrow">
                    Assessment
                </span>

                <div class="module-title">
                    ${escapeHtml(title)}
                </div>

                <p class="module-description">
                    ${escapeHtml(description)}
                </p>
            </div>

            <span class="status-badge ${status.className}">
                ${escapeHtml(status.label)}
            </span>
        </div>
    `;
}


function moduleActions(section, infoLabel) {
    return `
        <div class="module-actions">
            <button
                class="detail-button"
                data-details="${escapeAttribute(section)}"
                type="button"
            >
                Details
            </button>

            <span class="module-description">
                ⓘ ${escapeHtml(infoLabel)}
            </span>
        </div>
    `;
}


function moduleUnavailable(section, title, description) {
    return `
        <article class="module-card ${escapeAttribute(section)}">
            ${moduleHeader(
                title,
                description,
                {
                    label: "Not available",
                    className: "neutral"
                }
            )}

            <div class="big-result">
                N/A
            </div>

            <div class="key-finding">
                Analyse a suitable text or research-resource link.
            </div>
        </article>
    `;
}


function showDetails(section) {
    const panel = document.getElementById("detailsPanel");
    const resource = getPrimaryResource();

    if (section === "trust") {
        panel.innerHTML = renderTrustDetails(
            currentResult?.trust
        );
    } else if (section === "fair") {
        panel.innerHTML = renderFairDetails(
            resource?.fair
        );
    } else if (section === "copyright") {
        panel.innerHTML = renderCopyrightDetails(
            resource?.licence,
            resource?.ip
        );
    } else {
        panel.innerHTML = renderFairR2LDetails(
            resource?.fair_r2l
        );
    }

    panel.classList.remove("hidden");

    panel
        .querySelector(".close-button")
        ?.addEventListener("click", () => {
            panel.classList.add("hidden");
        });

    panel.scrollIntoView({
        behavior: "smooth",
        block: "start"
    });
}


function detailHeader(title, subtitle) {
    return `
        <div class="details-header">
            <div>
                <span class="eyebrow">
                    Details
                </span>

                <h2>
                    ${escapeHtml(title)}
                </h2>

                <p>
                    ${escapeHtml(subtitle)}
                </p>
            </div>

            <button
                class="close-button"
                type="button"
                aria-label="Close details"
            >
                ×
            </button>
        </div>
    `;
}


function renderTrustDetails(trust) {
    if (!trust?.details) {
        return detailHeader(
            "Trust",
            "No trust details are available."
        );
    }

    const details = trust.details;
    const claims = details.classified_claims || [];
    const facts = details.fact_results || [];
    const bias = details.bias_result || {};
    const citations = details.citation_result || {};

    const factRows = facts.map(item => {
        return [
            item.claim || "Claim",
            item.status || "Needs review",
            item.source || "No source"
        ];
    });

    const technicalResult = {
        classified_claims: claims,
        bias_result: bias,
        citation_result: citations
    };

    return `
        ${detailHeader(
            "Trust",
            "A compact view of the most important trust signals."
        )}

        <div class="summary-grid">
            ${summaryBox(
                "Trust score",
                `${formatNumber(trust.score)}/100`
            )}

            ${summaryBox(
                "Sentences",
                claims.length
            )}

            ${summaryBox(
                "Bias risk",
                `${formatNumber(bias.bias_risk_score || 0)}/100`
            )}

            ${summaryBox(
                "Citation quality",
                `${formatNumber(citations.overall_score || 0)}/100`
            )}
        </div>

        <section class="details-section">
            <h3>
                Explanation
            </h3>

            <p class="key-finding">
                ${escapeHtml(
                    details.ai_explanation
                    || trust.note
                    || "No explanation available."
                )}
            </p>
        </section>

        <section class="details-section">
            <h3>
                Claims needing attention
            </h3>

            ${
                factRows.length
                    ? renderTable(
                        [
                            "Claim",
                            "Result",
                            "Source"
                        ],
                        factRows
                    )
                    : `
                        <p class="key-finding">
                            No factual checks were returned.
                        </p>
                    `
            }
        </section>

        <details class="info-box">
            <summary>
                ⓘ Technical information
            </summary>

            <div>
                <pre>${escapeHtml(
                    JSON.stringify(
                        technicalResult,
                        null,
                        2
                    )
                )}</pre>
            </div>
        </details>
    `;
}


function renderFairDetails(fair) {
    if (!fair) {
        return detailHeader(
            "FAIR",
            "No FAIR result is available."
        );
    }

    const principles = Object.values(
        fair.principle_summary || {}
    );

    const rows = principles.map(item => {
        return [
            item.name,
            `${formatPoints(item.earned)} of ${formatPoints(item.total)}`,
            titleCase(item.level || "unknown"),
            percent(item.percent)
        ];
    });

    const failed = (
        fair.checks
        || []
    )
        .filter(item => !item.passed)
        .slice(0, 8);

    return `
        ${detailHeader(
            "FAIR",
            "Points earned and maturity are easier to interpret than one overall percentage."
        )}

        <section class="details-section">
            <h3>
                FAIR dimensions
            </h3>

            ${renderTable(
                [
                    "Dimension",
                    "Points earned",
                    "FAIR level",
                    "Percent"
                ],
                rows
            )}
        </section>

        <section class="details-section">
            <h3>
                What can be improved
            </h3>

            ${
                failed.length
                    ? renderList(
                        failed.map(item => {
                            return (
                                item.label
                                || item.id
                            );
                        })
                    )
                    : `
                        <p class="key-finding">
                            No failed F-UJI metrics were returned.
                        </p>
                    `
            }
        </section>

        <details class="info-box">
            <summary>
                ⓘ Technical F-UJI information
            </summary>

            <div>
                <p class="key-finding">
                    Method:
                    ${escapeHtml(
                        fair.method_label
                        || fair.method
                        || "N/A"
                    )}
                </p>

                <p class="key-finding">
                    Metric version:
                    ${escapeHtml(
                        fair.metric_version
                        || "N/A"
                    )}
                </p>

                <p class="key-finding">
                    Overall percentage:
                    ${percent(fair.score)}
                </p>

                <pre>${escapeHtml(
                    JSON.stringify(
                        fair.checks || [],
                        null,
                        2
                    )
                )}</pre>
            </div>
        </details>
    `;
}


function renderCopyrightDetails(licence, result) {
    if (!licence) {
        return detailHeader(
            "Copyright & Licence",
            "No licence result is available."
        );
    }

    const attribution = licence.attribution === true
        ? "Required"
        : licence.attribution === false
            ? "Not required"
            : "Needs review";

    const rows = [
        [
            "Detected licence",
            (
                licence.spdx_id
                || licence.name
                || "Not recognised"
            )
        ],
        [
            "Share",
            yesNoReview(licence.redistribution)
        ],
        [
            "Adapt",
            yesNoReview(licence.adaptations)
        ],
        [
            "Commercial use",
            yesNoReview(licence.commercial)
        ],
        [
            "Attribution",
            attribution
        ],
        [
            "Share alike",
            yesNoReview(licence.share_alike)
        ]
    ];

    const guidance = (
        result?.verdict
        || licence.plain_english
        || "Review the licence before reuse."
    );

    return `
        ${detailHeader(
            "Copyright & Licence",
            "Permissions and obligations under the detected licence."
        )}

        <section class="details-section">
            ${renderTable(
                [
                    "Condition",
                    "Result"
                ],
                rows
            )}
        </section>

        <section class="details-section">
            <h3>
                Reuse guidance
            </h3>

            <p class="key-finding">
                ${escapeHtml(guidance)}
            </p>
        </section>

        <details class="info-box">
            <summary>
                ⓘ Technical licence information
            </summary>

            <div>
                <pre>${escapeHtml(
                    JSON.stringify(
                        {
                            licence,
                            assessment: result
                        },
                        null,
                        2
                    )
                )}</pre>
            </div>
        </details>
    `;
}


function renderFairR2LDetails(result) {
    if (!result) {
        return detailHeader(
            "FAIR-R²L",
            "No checklist result is available."
        );
    }

    const sections = Object.values(
        result.sections || {}
    );

    const rows = sections.map(section => {
        return [
            section.title,
            percent(section.readiness),
            percent(section.completion),
            titleCase(
                section.level
                || "not assessed"
            )
        ];
    });

    return `
        ${detailHeader(
            "FAIR-R²L",
            "Readiness shows what appears to be met. Completion shows what the user has confirmed."
        )}

        <div class="summary-grid">
            ${summaryBox(
                "Classification",
                result.classification_label
                || "Needs review"
            )}

            ${summaryBox(
                "Readiness",
                percent(result.readiness)
            )}

            ${summaryBox(
                "Completion",
                percent(result.completion)
            )}

            ${summaryBox(
                "Pending critical",
                (
                    result.pending_critical_reviews
                    || []
                ).length
            )}
        </div>

        <section class="details-section">
            <h3>
                Dimensions
            </h3>

            ${renderTable(
                [
                    "Dimension",
                    "Readiness",
                    "Completion",
                    "Level"
                ],
                rows
            )}
        </section>

        ${compactResultSection(
            "Strengths",
            result.strengths
        )}

        ${compactResultSection(
            "Missing elements",
            result.missing_elements
        )}

        ${compactResultSection(
            "Recommendations",
            (
                result.recommendations
                || []
            ).map(text => {
                return {text};
            })
        )}

        <details class="info-box">
            <summary>
                ⓘ How this prototype works
            </summary>

            <div>
                <p class="key-finding">
                    ${escapeHtml(
                        result.method_note
                        || "This is an experimental transparent rule-based model."
                    )}
                </p>

                <p class="key-finding">
                    Classification reason:
                    ${escapeHtml(
                        result.classification?.reason
                        || "N/A"
                    )}
                </p>

                <p class="key-finding">
                    This is not an official IP4OS score.
                </p>
            </div>
        </details>
    `;
}


function compactResultSection(title, items) {
    if (!items?.length) {
        return "";
    }

    const values = items.map(item => {
        return (
            item.text
            || item.recommendation
            || String(item)
        );
    });

    return `
        <section class="details-section">
            <h3>
                ${escapeHtml(title)}
            </h3>

            ${renderList(values)}
        </section>
    `;
}


function renderWarnings() {
    const section = document.getElementById(
        "warningSection"
    );

    const list = document.getElementById(
        "warningList"
    );

    const warnings = currentResult?.warnings || [];

    if (!warnings.length) {
        section.classList.add("hidden");
        list.innerHTML = "";
        return;
    }

    list.innerHTML = warnings.map(item => {
        return `
            <div class="warning-item">
                <strong>
                    ${escapeHtml(
                        item.title
                        || "Review point"
                    )}:
                </strong>

                ${escapeHtml(item.message || "")}
            </div>
        `;
    }).join("");

    section.classList.remove("hidden");
}


function renderReviewer() {
    const container = document.getElementById(
        "reviewerContent"
    );

    const resource = getPrimaryResource();

    if (!resource) {
        container.innerHTML = emptyMessage(
            "No resource analysed",
            "Analyse a DOI or repository URL first."
        );
        return;
    }

    const artefact = resource.artefact || {};
    const licence = resource.licence || {};
    const r2l = resource.fair_r2l || {};

    const allowed = [];
    const conditions = [];

    if (licence.redistribution === true) {
        allowed.push(
            "Share and redistribute the resource."
        );
    }

    if (licence.adaptations === true) {
        allowed.push(
            "Create adaptations."
        );
    }

    if (licence.commercial === true) {
        allowed.push(
            "Use it commercially."
        );
    }

    if (!allowed.length) {
        allowed.push(
            "No permission could be confirmed automatically."
        );
    }

    if (licence.attribution === true) {
        conditions.push(
            "Give appropriate attribution."
        );
    }

    if (licence.share_alike === true) {
        conditions.push(
            "Use the same licence for adaptations."
        );
    }

    conditions.push(
        "Check privacy, contracts and third-party rights."
    );

    const pending = (
        r2l.pending_critical_reviews
        || []
    ).map(item => item.text);

    container.innerHTML = `
        <span class="eyebrow">
            Reviewer
        </span>

        <h2>
            ${escapeHtml(
                artefact.title
                || "Analysed resource"
            )}
        </h2>

        <div class="summary-grid">
            ${summaryBox(
                "Licence",
                licence.spdx_id
                || "Not recognised"
            )}

            ${summaryBox(
                "FAIR-R²L",
                r2l.classification_label
                || "Needs review"
            )}

            ${summaryBox(
                "Readiness",
                percent(r2l.readiness)
            )}

            ${summaryBox(
                "Completion",
                percent(r2l.completion)
            )}
        </div>

        <div class="advisor-grid">
            ${advisorBox(
                "What you may do",
                allowed
            )}

            ${advisorBox(
                "Conditions",
                conditions
            )}

            ${advisorBox(
                "Still check",
                pending.length
                    ? pending
                    : [
                        "No critical check is pending."
                    ]
            )}
        </div>

        <div class="button-row">
            <button
                class="primary-button fit"
                type="button"
                id="openChecklistFromReviewer"
            >
                Open checklist
            </button>
        </div>
    `;

    document
        .getElementById("openChecklistFromReviewer")
        ?.addEventListener("click", () => {
            switchMainTab("checklist");
        });
}


async function clarifyBrainstorm() {
    const description = document
        .getElementById("brainstormDescription")
        .value
        .trim();

    if (!description) {
        showBrainstormMessage(
            "Describe the resource first.",
            true
        );
        return;
    }

    try {
        const response = await fetch(
            "/api/brainstormer/clarify",
            {
                method: "POST",
                headers: {
                    "Content-Type": "application/json"
                },
                body: JSON.stringify({
                    description
                })
            }
        );

        const data = await response.json();

        if (!response.ok) {
            throw new Error(
                data.error
                || "Questions could not be generated."
            );
        }

        brainstormQuestions = data.questions || [];

        document
            .getElementById("brainstormQuestions")
            .innerHTML = brainstormQuestions.map(question => {
                return `
                    <div class="question-card">
                        <label
                            for="brainstorm_${escapeAttribute(question.id)}"
                        >
                            ${escapeHtml(question.text)}
                        </label>

                        <select
                            id="brainstorm_${escapeAttribute(question.id)}"
                        >
                            <option value="">
                                Not answered
                            </option>

                            <option value="yes">
                                Yes
                            </option>

                            <option value="no">
                                No
                            </option>

                            <option value="unsure">
                                Unsure
                            </option>
                        </select>
                    </div>
                `;
            }).join("");
    } catch (error) {
        showBrainstormMessage(
            error.message,
            true
        );
    }
}


async function generateBrainstormStrategy() {
    const description = document
        .getElementById("brainstormDescription")
        .value
        .trim();

    if (!description) {
        showBrainstormMessage(
            "Describe the resource first.",
            true
        );
        return;
    }

    const answers = {};

    brainstormQuestions.forEach(question => {
        const value = document
            .getElementById(`brainstorm_${question.id}`)
            ?.value;

        if (value) {
            answers[question.id] = value;
        }
    });

    try {
        const response = await fetch(
            "/api/brainstormer/strategy",
            {
                method: "POST",
                headers: {
                    "Content-Type": "application/json"
                },
                body: JSON.stringify({
                    description,
                    answers
                })
            }
        );

        const data = await response.json();

        if (!response.ok) {
            throw new Error(
                data.error
                || "The sharing plan could not be created."
            );
        }

        const cautions = (
            data.cautions
            || []
        );

        document
            .getElementById("brainstormResult")
            .innerHTML = `
                <div class="advisor-grid">
                    ${advisorBox(
                        "Repository",
                        data.repositories || []
                    )}

                    ${advisorBox(
                        "Licence options",
                        data.licence_options || []
                    )}

                    ${advisorBox(
                        "Before publishing",
                        data.actions || []
                    )}
                </div>

                ${
                    cautions.length
                        ? `
                            <section class="details-section">
                                <h3>
                                    Cautions
                                </h3>

                                ${renderList(cautions)}
                            </section>
                        `
                        : ""
                }
            `;
    } catch (error) {
        showBrainstormMessage(
            error.message,
            true
        );
    }
}


function showBrainstormMessage(message, error) {
    document
        .getElementById("brainstormResult")
        .innerHTML = `
            <div class="state-card ${error ? "error" : ""}">
                <p>
                    ${escapeHtml(message)}
                </p>
            </div>
        `;
}


function renderChecklist() {
    const container = document.getElementById(
        "checklistContent"
    );

    const result = getPrimaryResource()?.fair_r2l;

    if (!currentAnalysisId || !result) {
        container.innerHTML = emptyMessage(
            "No checklist available",
            "Analyse a dataset DOI or repository URL first."
        );
        return;
    }

    const sections = Object.values(
        result.sections || {}
    );

    container.innerHTML = `
        <span class="eyebrow">
            Guided review
        </span>

        <h2>
            ${escapeHtml(
                getPrimaryResource()?.artefact?.title
                || "Research resource"
            )}
        </h2>

        <div class="summary-grid">
            ${summaryBox(
                "Classification",
                result.classification_label
                || "Needs review"
            )}

            ${summaryBox(
                "Readiness",
                percent(result.readiness)
            )}

            ${summaryBox(
                "Completion",
                percent(result.completion)
            )}

            ${summaryBox(
                "Critical pending",
                (
                    result.pending_critical_reviews
                    || []
                ).length
            )}
        </div>

        <div class="checklist-toolbar">
            <p class="module-description">
                Confirm system suggestions or change them where needed.
            </p>

            <button
                id="confirmSuggestionsBtn"
                class="secondary-button"
                type="button"
            >
                Confirm clear suggestions
            </button>
        </div>

        <form id="checklistForm">
            ${sections
                .map(renderChecklistSection)
                .join("")
            }

            <button
                class="primary-button"
                type="submit"
            >
                Save review
            </button>
        </form>

        <div id="checklistMessage"></div>

        <details class="info-box">
            <summary>
                ⓘ How readiness and completion are calculated
            </summary>

            <div>
                <p class="key-finding">
                    Readiness = Yes ÷ (Yes + No).
                    Not assessed answers reduce completion,
                    not readiness.
                </p>

                <p class="key-finding">
                    The six dimensions are treated equally
                    in this experimental prototype.
                </p>

                <p class="key-finding">
                    A confirmed critical No creates a blocker.
                </p>
            </div>
        </details>
    `;

    document
        .getElementById("checklistForm")
        .addEventListener("submit", saveChecklist);

    document
        .getElementById("confirmSuggestionsBtn")
        .addEventListener("click", confirmSuggestions);
}


function renderChecklistSection(section) {
    const open = [
        "ai_readiness",
        "responsible_licensing"
    ].includes(section.id);

    return `
        <details
            class="checklist-section"
            ${open ? "open" : ""}
        >
            <summary>
                ${escapeHtml(section.title)}
                · Readiness ${percent(section.readiness)}
                · Completion ${percent(section.completion)}
            </summary>

            <div>
                ${
                    (section.checks || [])
                        .map(renderChecklistQuestion)
                        .join("")
                }
            </div>
        </details>
    `;
}


function renderChecklistQuestion(check) {
    const selected = check.confirmed
        ? check.confirmed_answer
        : "not_assessed";

    const suggestion = (
        check.suggested_answer
        && check.suggested_answer !== "not_assessed"
    )
        ? `${titleCase(check.suggested_answer)} · ${check.reason || "System suggestion"}`
        : "Manual confirmation required";

    const criticalText = check.critical
        ? " · Critical"
        : "";

    return `
        <div
            class="check-item"
            data-check-id="${escapeAttribute(check.id)}"
            data-suggestion="${escapeAttribute(
                check.suggested_answer
                || "not_assessed"
            )}"
        >
            <div class="check-top">
                <div>
                    <span class="check-text">
                        ${escapeHtml(check.text)}
                    </span>

                    <div class="check-meta">
                        ${escapeHtml(check.dimension_title)}
                        ${criticalText}
                    </div>
                </div>

                <span class="check-badge ${checkStatusClass(check)}">
                    ${escapeHtml(checkStatusLabel(check))}
                </span>
            </div>

            <div class="suggestion-box">
                <strong>
                    System:
                </strong>

                ${escapeHtml(suggestion)}
            </div>

            ${renderEvidence(check.evidence)}

            <div class="answer-options">
                ${answerOption(
                    check.id,
                    "yes",
                    "Yes",
                    selected
                )}

                ${answerOption(
                    check.id,
                    "no",
                    "No",
                    selected
                )}

                ${answerOption(
                    check.id,
                    "not_applicable",
                    "Not applicable",
                    selected
                )}

                ${answerOption(
                    check.id,
                    "not_assessed",
                    "Not assessed",
                    selected
                )}
            </div>

            <textarea
                class="evidence-input"
                data-comment-for="${escapeAttribute(check.id)}"
                placeholder="Optional comment or evidence"
            >${escapeHtml(check.user_comment || "")}</textarea>

            <div class="evidence-hint">
                ${escapeHtml(check.evidence_hint || "")}
            </div>
        </div>
    `;
}


function renderEvidence(evidence) {
    if (!evidence?.length) {
        return "";
    }

    const values = evidence
        .slice(0, 3)
        .map(item => {
            return (
                `${item.field || "Evidence"}: `
                + `${readable(item.value)}`
            );
        });

    return `
        <div class="check-meta">
            <strong>
                Evidence:
            </strong>

            ${escapeHtml(values.join(" · "))}
        </div>
    `;
}


function answerOption(id, value, label, selected) {
    return `
        <label>
            <input
                type="radio"
                name="answer_${escapeAttribute(id)}"
                value="${escapeAttribute(value)}"
                ${selected === value ? "checked" : ""}
            >

            ${escapeHtml(label)}
        </label>
    `;
}


function confirmSuggestions() {
    document.querySelectorAll(".check-item").forEach(item => {
        const suggestion = item.dataset.suggestion;

        if (![
            "yes",
            "no",
            "not_applicable"
        ].includes(suggestion)) {
            return;
        }

        const input = item.querySelector(
            `input[value="${suggestion}"]`
        );

        if (input) {
            input.checked = true;
        }
    });

    document
        .getElementById("checklistMessage")
        .innerHTML = `
            <div class="state-card">
                <p>
                    Clear suggestions selected.
                    Review them, then click Save review.
                </p>
            </div>
        `;
}


async function saveChecklist(event) {
    event.preventDefault();

    const manualAnswers = {};

    document.querySelectorAll(".check-item").forEach(item => {
        const id = item.dataset.checkId;

        const selected = item.querySelector(
            `input[name="answer_${cssEscape(id)}"]:checked`
        );

        const comment = item.querySelector(
            `[data-comment-for="${cssEscape(id)}"]`
        );

        manualAnswers[id] = (
            selected?.value
            || "not_assessed"
        );

        if (comment?.value.trim()) {
            manualAnswers[`${id}_evidence`] = (
                comment.value.trim()
            );
        }
    });

    const message = document.getElementById(
        "checklistMessage"
    );

    message.innerHTML = `
        <div class="state-card">
            <p>
                Saving review...
            </p>
        </div>
    `;

    try {
        const response = await fetch(
            `/api/result/${encodeURIComponent(currentAnalysisId)}/checklist`,
            {
                method: "POST",
                headers: {
                    "Content-Type": "application/json"
                },
                body: JSON.stringify({
                    manual_answers: manualAnswers
                })
            }
        );

        const data = await response.json();

        if (!response.ok) {
            throw new Error(
                data.error
                || "Checklist could not be saved."
            );
        }

        currentResult = data.result;

        renderOverview();
        renderWarnings();
        renderReviewer();
        renderChecklist();

        document
            .getElementById("checklistMessage")
            .innerHTML = `
                <div class="state-card">
                    <p>
                        Saved.
                        Readiness ${percent(data.fair_r2l?.readiness)},
                        completion ${percent(data.fair_r2l?.completion)}.
                    </p>
                </div>
            `;
    } catch (error) {
        message.innerHTML = `
            <div class="state-card error">
                <p>
                    ${escapeHtml(error.message)}
                </p>
            </div>
        `;
    }
}


function getPrimaryResource() {
    const resources = currentResult?.resources || [];

    if (!resources.length) {
        return null;
    }

    const index = Number.isInteger(
        currentResult.primary_resource_index
    )
        ? currentResult.primary_resource_index
        : 0;

    return (
        resources[index]
        || resources[0]
    );
}


function permissionChip(label, value) {
    let text = `${label}: review`;
    let className = "review";

    if (value === true) {
        text = `${label}: allowed`;
        className = "good";
    } else if (value === false) {
        text = `${label}: restricted`;
        className = "blocked";
    }

    return `
        <span class="permission-chip ${className}">
            ${escapeHtml(text)}
        </span>
    `;
}


function metricBox(label, value) {
    return `
        <div class="metric-box">
            <span>
                ${escapeHtml(label)}
            </span>

            <strong>
                ${escapeHtml(value)}
            </strong>
        </div>
    `;
}


function summaryBox(label, value) {
    return `
        <div class="summary-box">
            <span>
                ${escapeHtml(label)}
            </span>

            <strong>
                ${escapeHtml(
                    String(value ?? "N/A")
                )}
            </strong>
        </div>
    `;
}


function advisorBox(title, items) {
    return `
        <div class="advisor-box">
            <h3>
                ${escapeHtml(title)}
            </h3>

            <ul>
                ${
                    (items || [])
                        .map(item => {
                            return `
                                <li>
                                    ${escapeHtml(item)}
                                </li>
                            `;
                        })
                        .join("")
                }
            </ul>
        </div>
    `;
}


function renderTable(headers, rows) {
    return `
        <div class="table-wrap">
            <table>
                <thead>
                    <tr>
                        ${
                            headers.map(header => {
                                return `
                                    <th>
                                        ${escapeHtml(header)}
                                    </th>
                                `;
                            }).join("")
                        }
                    </tr>
                </thead>

                <tbody>
                    ${
                        rows.map(row => {
                            return `
                                <tr>
                                    ${
                                        row.map(value => {
                                            return `
                                                <td>
                                                    ${escapeHtml(readable(value))}
                                                </td>
                                            `;
                                        }).join("")
                                    }
                                </tr>
                            `;
                        }).join("")
                    }
                </tbody>
            </table>
        </div>
    `;
}


function renderList(items) {
    return `
        <ul class="simple-list">
            ${
                (items || [])
                    .map(item => {
                        return `
                            <li>
                                ${escapeHtml(readable(item))}
                            </li>
                        `;
                    })
                    .join("")
            }
        </ul>
    `;
}


function emptyMessage(title, message) {
    return `
        <div class="empty-card">
            <div class="empty-icon">
                EA
            </div>

            <h2>
                ${escapeHtml(title)}
            </h2>

            <p>
                ${escapeHtml(message)}
            </p>
        </div>
    `;
}


function showLoading() {
    hideStates();

    document
        .getElementById("loadingPanel")
        .classList
        .remove("hidden");
}


function showError(message) {
    hideStates();

    document
        .getElementById("errorMessage")
        .textContent = (
            message
            || "Make sure browser_api.py is running."
        );

    document
        .getElementById("errorPanel")
        .classList
        .remove("hidden");
}


function showEmpty() {
    hideStates();

    document
        .getElementById("emptyPanel")
        .classList
        .remove("hidden");
}


function hideStates() {
    [
        "loadingPanel",
        "errorPanel",
        "emptyPanel",
        "resultsArea"
    ].forEach(id => {
        document
            .getElementById(id)
            .classList
            .add("hidden");
    });
}


function trustStatus(score) {
    if (score === null) {
        return {
            label: "Not available",
            className: "neutral"
        };
    }

    if (score >= 75) {
        return {
            label: "Strong",
            className: "good"
        };
    }

    if (score >= 50) {
        return {
            label: "Needs review",
            className: "review"
        };
    }

    return {
        label: "Weak",
        className: "blocked"
    };
}


function classificationStatus(label) {
    if (label === "Ready for reuse") {
        return {
            label,
            className: "good"
        };
    }

    if (label === "Not recommended") {
        return {
            label,
            className: "blocked"
        };
    }

    return {
        label,
        className: "review"
    };
}


function checkStatusLabel(check) {
    if (check.confirmed_answer === "yes") {
        return "Confirmed yes";
    }

    if (check.confirmed_answer === "no") {
        return "Confirmed no";
    }

    if (check.confirmed_answer === "not_applicable") {
        return "Not applicable";
    }

    if ([
        "yes",
        "no"
    ].includes(check.suggested_answer)) {
        return "Suggestion";
    }

    return "Not assessed";
}


function checkStatusClass(check) {
    if (check.confirmed_answer === "yes") {
        return "good";
    }

    if (check.confirmed_answer === "no") {
        return "blocked";
    }

    if (check.confirmed_answer === "not_applicable") {
        return "neutral";
    }

    return "review";
}


function levelClass(level) {
    if (level === "advanced") {
        return "good";
    }

    if (level === "moderate") {
        return "review";
    }

    if (
        level === "initial"
        || level === "incomplete"
    ) {
        return "blocked";
    }

    return "neutral";
}


function yesNoReview(value) {
    if (value === true) {
        return "Yes";
    }

    if (value === false) {
        return "No";
    }

    return "Needs review";
}


function numberOrNull(value) {
    const number = Number(value);

    return Number.isFinite(number)
        ? number
        : null;
}


function formatNumber(value) {
    const number = Number(value);

    if (!Number.isFinite(number)) {
        return "N/A";
    }

    if (Number.isInteger(number)) {
        return String(number);
    }

    return number
        .toFixed(2)
        .replace(/0+$/, "")
        .replace(/\.$/, "");
}


function formatPoints(value) {
    const formatted = formatNumber(value);

    return formatted === "N/A"
        ? "0"
        : formatted;
}


function percent(value) {
    const formatted = formatNumber(value);

    return formatted === "N/A"
        ? "N/A"
        : `${formatted}%`;
}


function readable(value) {
    if (
        value === null
        || value === undefined
        || value === ""
    ) {
        return "N/A";
    }

    if (typeof value === "boolean") {
        return value
            ? "Yes"
            : "No";
    }

    if (Array.isArray(value)) {
        return value
            .map(readable)
            .join(", ");
    }

    if (typeof value === "object") {
        return JSON.stringify(value);
    }

    return String(value).replace(/_/g, " ");
}


function titleCase(value) {
    return String(value || "")
        .replace(/_/g, " ")
        .split(" ")
        .filter(Boolean)
        .map(word => {
            return (
                word.charAt(0).toUpperCase()
                + word.slice(1)
            );
        })
        .join(" ");
}


function cssEscape(value) {
    if (window.CSS?.escape) {
        return window.CSS.escape(value);
    }

    return String(value).replace(
        /[^a-zA-Z0-9_-]/g,
        "\\$&"
    );
}


function escapeHtml(value) {
    return String(value ?? "")
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
}


function escapeAttribute(value) {
    return escapeHtml(value);
}