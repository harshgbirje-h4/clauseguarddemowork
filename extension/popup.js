// ClauseGuard Popup Controller
// Standardized Scoring Contract & Plain-Language UX

const BACKEND_URL = "http://127.0.0.1:5000";
const MAX_POLICY_CHARS = 250000;

document.addEventListener('DOMContentLoaded', () => {
    let currentAnalysisResult = null;
    let currentActiveTab = null;
    let currentHostname = "";
    let isCurrentSavedInPortfolio = false;
    let portfolioServices = [];

    // DOM Elements - Site Card
    const siteNameEl = document.getElementById('site-name');
    const portfolioBadge = document.getElementById('portfolio-badge');
    const scanBadge = document.getElementById('scan-badge');
    const lastScannedTimeEl = document.getElementById('last-scanned-time');
    const policyLinkContainer = document.getElementById('policy-link-container');
    const policyLink = document.getElementById('policy-link');

    // Action Buttons
    const analyzeBtn = document.getElementById('analyze-btn');
    const togglePasteBtn = document.getElementById('toggle-paste-btn');
    const pasteSection = document.getElementById('paste-section');
    const pasteAnalyzeBtn = document.getElementById('paste-analyze-btn');
    const pasteTextArea = document.getElementById('paste-text');

    // Status & Reminders
    const statusDiv = document.getElementById('status');
    const unscannedReminder = document.getElementById('unscanned-reminder');
    const resultsDiv = document.getElementById('results');
    const apiModeEl = document.getElementById('api-mode');

    // Score Elements
    const cardScoreSummary = document.getElementById('card-score-summary');
    const riskScoreEl = document.getElementById('risk-score');
    const riskBandEl = document.getElementById('risk-band');
    const gaugeFill = document.getElementById('gauge-fill');
    const scoreExplanationEl = document.getElementById('score-explanation');

    // Compare Elements
    const compareSearchInput = document.getElementById('compare-search-input');
    const compareDatalist = document.getElementById('compare-datalist');
    const compareTargetSelect = document.getElementById('compare-target');
    const compareBtn = document.getElementById('compare-btn');
    const compareResultsDiv = document.getElementById('compare-results');

    // Clauses Elements
    const clauseCountEl = document.getElementById('clause-count');
    const clausesListDiv = document.getElementById('clauses-list');

    // Portfolio Action Elements
    const saveBtn = document.getElementById('save-btn');
    const saveStatus = document.getElementById('save-status');
    const openDashBtn = document.getElementById('open-dash-btn');

    // Helpers
    function escapeHtml(str) {
        return String(str ?? '')
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#39;');
    }

    function showStatus(msg, type = "info") {
        if (!statusDiv) return;
        statusDiv.textContent = msg;
        statusDiv.className = `status ${type}`;
        statusDiv.classList.remove('hidden');
    }

    function hideStatus() {
        if (!statusDiv) return;
        statusDiv.classList.add('hidden');
    }

    // Band key to plain-language display label mapping (Item 2)
    function mapBandLabel(bandKey) {
        const key = String(bandKey || '').toLowerCase();
        switch (key) {
            case 'very_low':
            case 'very low':
                return { label: 'Very low risk', cssClass: 'VeryLow' };
            case 'low':
                return { label: 'Low risk', cssClass: 'Low' };
            case 'typical':
            case 'moderate':
                return { label: 'Typical for everyday apps', cssClass: 'Typical' };
            case 'high':
                return { label: 'High risk', cssClass: 'High' };
            case 'very_high':
            case 'very high':
                return { label: 'Very high risk', cssClass: 'VeryHigh' };
            default:
                return { label: 'Typical for everyday apps', cssClass: 'Typical' };
        }
    }

    // Toggle Manual Paste Box
    if (togglePasteBtn) {
        togglePasteBtn.addEventListener('click', () => {
            const isHidden = pasteSection.classList.contains('hidden');
            pasteSection.classList.toggle('hidden', !isHidden);
            togglePasteBtn.textContent = isHidden ? "Hide manual text box" : "Paste text instead";
            if (isHidden) pasteTextArea.focus();
        });
    }

    // Keep compare inputs synchronized
    if (compareTargetSelect) {
        compareTargetSelect.addEventListener('change', () => {
            if (compareTargetSelect.value) {
                compareSearchInput.value = compareTargetSelect.value;
            }
        });
    }

    // Initialize: inspect active tab
    chrome.tabs.query({ active: true, currentWindow: true }, async (tabs) => {
        currentActiveTab = tabs[0];
        if (!currentActiveTab || !currentActiveTab.url) {
            siteNameEl.textContent = "Unknown Tab";
            showStatus("Cannot determine active tab URL.", "warning");
            analyzeBtn.disabled = true;
            return;
        }

        const urlStr = currentActiveTab.url;
        if (urlStr.startsWith('chrome://') || urlStr.startsWith('edge://') || urlStr.startsWith('about:') || urlStr.startsWith('chrome-extension://')) {
            siteNameEl.textContent = "Browser Internal Page";
            portfolioBadge.classList.add('hidden');
            scanBadge.textContent = "Unsupported";
            scanBadge.className = "badge neutral";
            showStatus("ClauseGuard cannot scan protected browser internal pages. Navigate to a standard website to analyze its privacy policy.", "info");
            analyzeBtn.disabled = true;
            unscannedReminder.classList.add('hidden');
            return;
        }

        try {
            const urlObj = new URL(urlStr);
            currentHostname = urlObj.hostname;
            siteNameEl.textContent = currentHostname;
        } catch (e) {
            currentHostname = "Unknown";
            siteNameEl.textContent = "Unknown";
        }

        // Check backend service status & load portfolio services
        await checkPortfolioStatus(currentHostname);
        await loadPortfolioList();

        // ITEM 1: Group scan state by domain (hostname). Read ONLY per-site key analysis_<hostname> (No cachedAnalysis fallback)
        chrome.storage.local.get([`analysis_${currentHostname}`], (res) => {
            const cached = res[`analysis_${currentHostname}`];

            if (cached && cached.data) {
                const now = Date.now();
                const isFresh = (now - (cached.timestamp || 0)) < (24 * 60 * 60 * 1000); // 24hr freshness
                const currentTabUrl = currentActiveTab ? (currentActiveTab.url || "").toLowerCase() : "";
                const isCurrentTabPolicy = currentTabUrl.includes("privacy") || currentTabUrl.includes("terms");
                const wasCachedPolicyBlocked = (cached.data.status === "blocked" || cached.data.status === "not_a_policy");

                if (!isFresh) {
                    showStatus("Cached analysis is older than 24 hours. Click 'Re-scan' to refresh.", "info");
                    return;
                }
                if (isCurrentTabPolicy && wasCachedPolicyBlocked) {
                    showStatus("Active page is a privacy policy. Click 'Re-scan' to inspect it directly.", "info");
                    return;
                }

                if (cached.policy_url) {
                    policyLink.href = cached.policy_url;
                    policyLink.textContent = `Open Privacy Policy Page ↗`;
                    policyLinkContainer.classList.remove('hidden');
                }

                if (cached.timestamp) {
                    const d = new Date(cached.timestamp);
                    lastScannedTimeEl.textContent = d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', month: 'short', day: 'numeric' });
                }

                analyzeBtn.textContent = "Re-scan Website";
                unscannedReminder.classList.add('hidden');
                displayResults(cached.data, false);
            } else {
                // ITEM 1: Unscanned service reminder
                scanBadge.textContent = "Not scanned";
                scanBadge.className = "badge neutral";
                lastScannedTimeEl.textContent = "Never";
                analyzeBtn.textContent = "Scan Website";
                unscannedReminder.classList.remove('hidden');
                resultsDiv.classList.add('hidden');
            }
        });
    });

    // Check if website is saved in portfolio
    async function checkPortfolioStatus(hostname) {
        try {
            const res = await fetch(`${BACKEND_URL}/api/service-status?name=${encodeURIComponent(hostname)}`);
            if (!res.ok) return;
            const data = await res.json();
            if (data.is_saved) {
                isCurrentSavedInPortfolio = true;
                portfolioBadge.textContent = "In Portfolio";
                portfolioBadge.className = "badge saved";
                portfolioBadge.classList.remove('hidden');
                if (saveBtn) saveBtn.textContent = "Update Portfolio";
            } else {
                isCurrentSavedInPortfolio = false;
                portfolioBadge.classList.add('hidden');
                if (saveBtn) saveBtn.textContent = "Add to Portfolio";
            }
        } catch (e) {
            // Backend offline or unreachable
        }
    }

    // Load portfolio list for comparison dropdown & autocomplete
    async function loadPortfolioList() {
        try {
            const res = await fetch(`${BACKEND_URL}/api/portfolio`);
            if (!res.ok) return;
            const data = await res.json();
            portfolioServices = data.services || [];

            // Populate Dropdown
            compareTargetSelect.innerHTML = '<option value="">-- Select from saved portfolio --</option>';
            // Populate Autocomplete Datalist
            compareDatalist.innerHTML = '';

            portfolioServices.forEach(svc => {
                const name = (svc.service_name || svc.name || '').trim();
                if (!name) return;

                const opt = document.createElement('option');
                opt.value = name;
                opt.textContent = name;
                compareTargetSelect.appendChild(opt);

                const dataOpt = document.createElement('option');
                dataOpt.value = name;
                compareDatalist.appendChild(dataOpt);
            });
        } catch (e) {
            // Offline portfolio
        }
    }

    // Trigger Scan Website Action
    analyzeBtn.addEventListener('click', async () => {
        analyzeBtn.disabled = true;
        hideStatus();
        showStatus("Discovering and analyzing privacy policy...", "info");

        if (!currentActiveTab || !currentActiveTab.id) {
            showStatus("No active browser tab found.", "error");
            analyzeBtn.disabled = false;
            return;
        }

        chrome.tabs.sendMessage(currentActiveTab.id, { action: "extract_text" }, async (pageData) => {
            if (chrome.runtime.lastError || !pageData) {
                showStatus("Please reload the tab to enable ClauseGuard on this page.", "warning");
                pasteSection.classList.remove('hidden');
                analyzeBtn.disabled = false;
                return;
            }

            // Case 1: Active tab itself is the privacy policy document
            if (pageData.isLikelyPrivacyPolicy && pageData.text && pageData.text.length > 300) {
                showStatus("Analyzing active policy page...", "info");
                await runAnalysis({
                    text: pageData.text,
                    url: pageData.url,
                    title: pageData.title,
                    truncated: pageData.truncated
                });
                return;
            }

            // Case 2: Discover policy link from DOM or known mappings
            const targetLink = pageData.policyLink;
            if (targetLink && targetLink.href) {
                policyLink.href = targetLink.href;
                policyLink.textContent = `Open Privacy Policy Page ↗`;
                policyLinkContainer.classList.remove('hidden');

                showStatus("Policy link discovered. Fetching policy text...", "info");

                try {
                    const fetchRes = await fetch(`${BACKEND_URL}/api/proxy-fetch`, {
                        method: "POST",
                        headers: { "Content-Type": "application/json" },
                        body: JSON.stringify({ url: targetLink.href })
                    });

                    if (fetchRes.ok) {
                        const fetchPayload = await fetchRes.json();
                        const parser = new DOMParser();
                        const doc = parser.parseFromString(fetchPayload.html || "", "text/html");
                        doc.querySelectorAll('script, style, nav, footer, header, noscript, iframe').forEach(el => el.remove());
                        const fullText = (doc.body.innerText || "").replace(/\s+/g, ' ').trim();
                        const policyText = fullText.substring(0, MAX_POLICY_CHARS);
                        const truncated = fullText.length > MAX_POLICY_CHARS;

                        if (policyText.length < 200) {
                            scanBadge.textContent = "Blocked";
                            scanBadge.className = "badge blocked";
                            showStatus("Website protections prevented automated text extraction. Open policy page directly or paste text below.", "warning");
                            pasteSection.classList.remove('hidden');
                            analyzeBtn.disabled = false;
                            return;
                        }

                        const finalPolicyUrl = fetchPayload.final_url || targetLink.href;
                        showStatus("Policy fetched. Analyzing risk practices...", "info");
                        await runAnalysis({
                            text: policyText,
                            url: finalPolicyUrl,
                            title: pageData.title,
                            truncated: truncated
                        });
                    } else {
                        scanBadge.textContent = "Blocked";
                        scanBadge.className = "badge blocked";
                        showStatus("Website protections or login barrier blocked the automated scan. Open policy directly or paste text below.", "warning");
                        pasteSection.classList.remove('hidden');
                        analyzeBtn.disabled = false;
                    }
                } catch (err) {
                    scanBadge.textContent = "Error";
                    scanBadge.className = "badge insufficient";
                    showStatus("Network fetch failed. Open the privacy policy link directly or paste text below.", "warning");
                    pasteSection.classList.remove('hidden');
                    analyzeBtn.disabled = false;
                }
                return;
            }

            // Case 3: No policy link detected on page
            scanBadge.textContent = "Not a policy";
            scanBadge.className = "badge insufficient";
            showStatus("No privacy policy link detected on this page. If this service has a policy, open it or paste the text below.", "warning");
            pasteSection.classList.remove('hidden');
            analyzeBtn.disabled = false;
        });
    });

    // Manual Paste Analysis
    if (pasteAnalyzeBtn) {
        pasteAnalyzeBtn.addEventListener('click', async () => {
            const pastedText = pasteTextArea.value.trim();
            if (!pastedText) {
                showStatus("Please paste privacy policy text before analyzing.", "warning");
                return;
            }

            pasteAnalyzeBtn.disabled = true;
            showStatus("Analyzing pasted policy text...", "info");

            const isTruncated = pastedText.length > MAX_POLICY_CHARS;
            const sendText = pastedText.substring(0, MAX_POLICY_CHARS);

            await runAnalysis({
                text: sendText,
                url: currentActiveTab ? currentActiveTab.url : "",
                title: currentActiveTab ? currentActiveTab.title : "",
                truncated: isTruncated,
                source: "pasted"
            });

            pasteAnalyzeBtn.disabled = false;
            pasteSection.classList.add('hidden');
        });
    }

    // Execute backend analysis call
    async function runAnalysis(payload) {
        try {
            const res = await fetch(`${BACKEND_URL}/api/analyze-policy`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(payload)
            });

            const data = await res.json();
            if (!res.ok) {
                throw new Error(data.error || `HTTP ${res.status}`);
            }

            const now = Date.now();
            chrome.storage.local.set({
                [`analysis_${currentHostname}`]: {
                    url: currentHostname,
                    page_url: currentActiveTab ? currentActiveTab.url : "",
                    policy_url: data.policy_url || "",
                    policy_url_source: data.policy_url_source || "direct_page",
                    timestamp: now,
                    data: data
                }
            });

            const d = new Date(now);
            lastScannedTimeEl.textContent = d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', month: 'short', day: 'numeric' });
            analyzeBtn.textContent = "Re-scan Website";
            unscannedReminder.classList.add('hidden');

            displayResults(data, true);
        } catch (e) {
            showStatus(`Analysis failed: ${e.message}`, "error");
            pasteSection.classList.remove('hidden');
        } finally {
            analyzeBtn.disabled = false;
        }
    }

    // ITEM 2: Layout order, status handling, score display, band mapping, clause ordering
    function displayResults(data, isNewScan = false) {
        currentAnalysisResult = data;
        hideStatus();

        if (apiModeEl) {
            apiModeEl.textContent = data.mode || "MOCK/DEV";
            apiModeEl.className = `conn ${(data.mode || '').includes("GEMINI") ? "live" : "mock"}`;
        }

        // ITEM 2 Rule 6: Show message whenever status is not ok. Never show a score when status is "not_a_policy" or "blocked".
        const status = data.status || "ok";
        if (status !== "ok") {
            resultsDiv.classList.add('hidden');
            if (status === "not_a_policy") {
                scanBadge.textContent = "Not a policy";
                scanBadge.className = "badge neutral";
                showStatus(data.message || "This page doesn't look like a privacy policy. Open the policy page directly or paste the text.", "warning");
            } else if (status === "blocked") {
                scanBadge.textContent = "Blocked";
                scanBadge.className = "badge blocked";
                showStatus(data.message || "Automated fetch blocked by website protection. Open the policy page directly or paste the text.", "warning");
            } else {
                scanBadge.textContent = "Error";
                scanBadge.className = "badge insufficient";
                showStatus(data.message || "An error occurred during analysis.", "error");
            }
            return;
        }

        // Status is OK: Display complete scan
        scanBadge.textContent = "✓ Complete Scan";
        scanBadge.className = "badge complete";
        unscannedReminder.classList.add('hidden');
        resultsDiv.classList.remove('hidden');

        if (data.is_saved_in_portfolio) {
            isCurrentSavedInPortfolio = true;
            portfolioBadge.textContent = "In Portfolio";
            portfolioBadge.className = "badge saved";
            portfolioBadge.classList.remove('hidden');
            saveBtn.textContent = "Update Portfolio";
        }

        // 2. Score Section (Large & Prominent)
        const score = (data.score !== null && data.score !== undefined) ? Math.round(Number(data.score)) : 0;
        riskScoreEl.textContent = score;

        const bandInfo = mapBandLabel(data.band);
        riskBandEl.textContent = bandInfo.label;
        riskBandEl.className = `band ${bandInfo.cssClass}`;

        if (gaugeFill) {
            gaugeFill.style.width = `${Math.min(100, Math.max(0, score))}%`;
            if (score >= 60) gaugeFill.style.backgroundColor = "var(--alert)";
            else if (score >= 40) gaugeFill.style.backgroundColor = "#2563eb";
            else gaugeFill.style.backgroundColor = "var(--safe)";
        }

        if (scoreExplanationEl) {
            scoreExplanationEl.textContent = "Calculated from the top 5 highest-risk clauses, compared with everyday apps.";
        }

        // 4. Clause Details (Ordered by importance: refunds, cancellation, deletion, sharing, advertisers)
        const rawClauses = Array.isArray(data.clauses) ? [...data.clauses] : [];
        clauseCountEl.textContent = rawClauses.length;

        function getClausePriority(c) {
            const type = (c.type || '').toLowerCase();
            const meaning = (c.meaning || '').toLowerCase();
            const text = (c.excerpt || c.text || '').toLowerCase();
            const combined = `${type} ${meaning} ${text}`;

            // 1. Refunds, return policy
            if (type === 'refunds' || type === 'return_policy' || combined.includes('refund') || combined.includes('return policy')) {
                return 1;
            }
            // 2. Subscription cancellation, auto-renewal
            if (type === 'subscription_cancellation' || type === 'auto_renewal' || combined.includes('subscription') || combined.includes('cancellation') || combined.includes('renewal')) {
                return 2;
            }
            // 3. Account deletion
            if (type === 'data_deletion' || combined.includes('account deletion') || combined.includes('erase') || combined.includes('deletion')) {
                return 3;
            }
            // 4. Third-party sharing and advertisers
            if (type === 'third_party_sharing' || type === 'targeted_advertising' || type === 'data_selling' || combined.includes('third party') || combined.includes('advertis') || combined.includes('sharing')) {
                return 4;
            }
            // 5. General / Other
            return 5;
        }

        rawClauses.sort((a, b) => getClausePriority(a) - getClausePriority(b));

        clausesListDiv.innerHTML = '';
        if (rawClauses.length === 0) {
            clausesListDiv.innerHTML = '<div class="hint" style="padding: 8px;">No specific policy clauses identified.</div>';
        } else {
            rawClauses.forEach((c) => {
                const itemDiv = document.createElement('div');
                itemDiv.className = 'clause-item';

                const typeLabel = (c.type || 'Privacy Practice').replace(/_/g, ' ');
                const meaning = c.meaning || 'No plain-language summary available.';
                const whatYouCanDo = c.what_you_can_do || 'Review your account privacy choices.';
                const excerpt = c.excerpt || c.text || '';

                itemDiv.innerHTML = `
                    <div class="clause-item-head">
                        <span class="clause-type-tag">${escapeHtml(typeLabel)}</span>
                    </div>
                    <div class="clause-meaning">${escapeHtml(meaning)}</div>
                    <div class="clause-action"><b>What you can do:</b> ${escapeHtml(whatYouCanDo)}</div>
                    ${excerpt ? `
                        <button class="toggle-excerpt-btn" type="button">Show original policy text ▾</button>
                        <div class="clause-excerpt hidden">"${escapeHtml(excerpt)}"</div>
                    ` : ''}
                `;

                const toggleBtn = itemDiv.querySelector('.toggle-excerpt-btn');
                const excerptDiv = itemDiv.querySelector('.clause-excerpt');
                if (toggleBtn && excerptDiv) {
                    toggleBtn.addEventListener('click', () => {
                        const isHidden = excerptDiv.classList.contains('hidden');
                        excerptDiv.classList.toggle('hidden', !isHidden);
                        toggleBtn.textContent = isHidden ? "Hide original policy text ▴" : "Show original policy text ▾";
                    });
                }

                clausesListDiv.appendChild(itemDiv);
            });
        }
    }

    // ITEM 3: Compare with any service (Dropdown + Search box + Unsaved service handling)
    if (compareBtn) {
        compareBtn.addEventListener('click', async () => {
            const target = (compareSearchInput.value || compareTargetSelect.value || '').trim();
            if (!target) {
                compareResultsDiv.innerHTML = '<span style="color:var(--alert);">Please type or choose a service name to compare.</span>';
                compareResultsDiv.classList.remove('hidden');
                return;
            }

            compareBtn.disabled = true;
            compareBtn.textContent = "Comparing...";
            compareResultsDiv.innerHTML = '<div class="hint">Comparing privacy practices...</div>';
            compareResultsDiv.classList.remove('hidden');

            const isSaved = portfolioServices.some(s => {
                const sName = (s.service_name || s.name || '').trim();
                return sName.toLowerCase() === target.toLowerCase();
            });

            try {
                // Call standard compare endpoint
                const res = await fetch(`${BACKEND_URL}/api/compare`, {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({
                        service: target,
                        candidate: currentAnalysisResult
                    })
                });

                if (!res.ok) throw new Error("Comparison request failed");
                const comp = await res.json();

                const targetName = comp.service || target;
                const statusLabel = isSaved ? '' : '<span class="badge neutral" style="margin-left:6px;">Not in portfolio yet</span>';

                if (comp.status && comp.status !== "ok") {
                    compareResultsDiv.innerHTML = `
                        <div style="font-weight:700; margin-bottom:4px;">${escapeHtml(targetName)} ${statusLabel}</div>
                        <div style="color:var(--warning); font-size:11.5px;">${escapeHtml(comp.message || "Could not retrieve comparison details.")}</div>
                    `;
                    return;
                }

                const targetScore = comp.score !== null ? Math.round(comp.score) : "--";
                const targetBand = mapBandLabel(comp.band);
                const clauseCount = (comp.clauses || []).length;

                compareResultsDiv.innerHTML = `
                    <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:6px;">
                        <span style="font-weight:800; font-size:13px;">${escapeHtml(targetName)}</span>
                        ${statusLabel}
                    </div>
                    <div style="display:flex; align-items:center; gap:8px; margin-bottom:8px;">
                        <span style="font-size:12px;">Risk Score: <b>${targetScore}/100</b></span>
                        <span class="band ${targetBand.cssClass}" style="font-size:10.5px; padding:2px 6px;">${targetBand.label}</span>
                    </div>
                    <div class="hint" style="line-height:1.4;">
                        ${clauseCount > 0 ? `Identified ${clauseCount} key privacy clauses in ${escapeHtml(targetName)}'s policy terms.` : `Scanned policy terms for ${escapeHtml(targetName)}.`}
                    </div>
                `;
            } catch (e) {
                compareResultsDiv.innerHTML = `<span style="color:var(--alert);">Comparison error: ${escapeHtml(e.message)}</span>`;
            } finally {
                compareBtn.disabled = false;
                compareBtn.textContent = "Compare";
            }
        });
    }

    // Save to Portfolio Action
    if (saveBtn) {
        saveBtn.addEventListener('click', async () => {
            if (!currentAnalysisResult) return;
            saveBtn.disabled = true;
            saveBtn.textContent = "Saving...";
            saveStatus.classList.add('hidden');

            try {
                const res = await fetch(`${BACKEND_URL}/api/save-service`, {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify(currentAnalysisResult)
                });

                if (!res.ok) {
                    const errData = await res.json().catch(() => ({}));
                    throw new Error(errData.error || `HTTP ${res.status}`);
                }

                isCurrentSavedInPortfolio = true;
                portfolioBadge.textContent = "In Portfolio";
                portfolioBadge.className = "badge saved";
                portfolioBadge.classList.remove('hidden');
                saveBtn.textContent = "Added to Portfolio";
                saveStatus.textContent = "Successfully saved to your privacy portfolio!";
                saveStatus.className = "status success";
                saveStatus.classList.remove('hidden');

                // Refresh comparison list
                loadPortfolioList();
            } catch (err) {
                saveBtn.disabled = false;
                saveBtn.textContent = "Retry Add";
                saveStatus.textContent = `Save failed: ${err.message}`;
                saveStatus.className = "status error";
                saveStatus.classList.remove('hidden');
            }
        });
    }

    // Open Web Dashboard
    if (openDashBtn) {
        openDashBtn.addEventListener('click', () => {
            chrome.tabs.create({ url: BACKEND_URL });
        });
    }
});
