// ClauseGuard Popup Controller
// 4-Question UX Redesign & Complete Scanning Engine

const BACKEND_URL = "http://127.0.0.1:5000";
const MAX_POLICY_CHARS = 250000;

document.addEventListener('DOMContentLoaded', () => {
    let currentAnalysisResult = null;
    let currentActiveTab = null;
    let currentHostname = "";
    let isCurrentSavedInPortfolio = false;
    let portfolioServices = [];

    // Elements
    const siteNameEl = document.getElementById('site-name');
    const portfolioBadge = document.getElementById('portfolio-badge');
    const scanBadge = document.getElementById('scan-badge');
    const lastScannedTimeEl = document.getElementById('last-scanned-time');
    const policyLinkContainer = document.getElementById('policy-link-container');
    const policyLink = document.getElementById('policy-link');

    const analyzeBtn = document.getElementById('analyze-btn');
    const togglePasteBtn = document.getElementById('toggle-paste-btn');
    const pasteSection = document.getElementById('paste-section');
    const pasteAnalyzeBtn = document.getElementById('paste-analyze-btn');
    const pasteTextArea = document.getElementById('paste-text');

    const statusDiv = document.getElementById('status');
    const resultsDiv = document.getElementById('results');
    const apiModeEl = document.getElementById('api-mode');

    const saveBtn = document.getElementById('save-btn');
    const saveStatus = document.getElementById('save-status');
    const openDashBtn = document.getElementById('open-dash-btn');

    const compareTargetSelect = document.getElementById('compare-target');
    const compareBtn = document.getElementById('compare-btn');
    const compareResultsDiv = document.getElementById('compare-results');

    const toggleClausesBtn = document.getElementById('toggle-clauses-btn');
    const clausesDetailsDiv = document.getElementById('clauses-details');

    // Setup Accordions for Question Cards
    document.querySelectorAll('.q-header').forEach(header => {
        header.addEventListener('click', () => {
            const bodyId = header.getAttribute('data-toggle');
            const body = document.getElementById(bodyId);
            if (!body) return;
            const isCollapsed = body.classList.contains('hidden');
            body.classList.toggle('hidden', !isCollapsed);
            header.classList.toggle('collapsed', !isCollapsed);
        });
    });

    // Helper: Escaping HTML
    function escapeHtml(str) {
        return String(str ?? '')
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#39;');
    }

    function showStatus(msg, type = "info") {
        statusDiv.textContent = msg;
        statusDiv.className = `status ${type}`;
        statusDiv.classList.remove('hidden');
    }

    function hideStatus() {
        statusDiv.classList.add('hidden');
    }

    // Toggle Manual Paste Box
    if (togglePasteBtn) {
        togglePasteBtn.addEventListener('click', () => {
            const isHidden = pasteSection.classList.contains('hidden');
            pasteSection.classList.toggle('hidden', !isHidden);
            togglePasteBtn.textContent = isHidden ? "Hide manual text box" : "Paste text manually instead";
            if (isHidden) pasteTextArea.focus();
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
            portfolioBadge.textContent = "Restricted";
            portfolioBadge.className = "badge neutral";
            scanBadge.textContent = "Unsupported";
            scanBadge.className = "badge neutral";
            showStatus("ClauseGuard cannot scan protected browser internal pages. Navigate to a standard website to analyze its privacy policy.", "info");
            analyzeBtn.disabled = true;
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

        // Check backend service status & portfolio
        await checkPortfolioStatus(currentHostname);
        await loadPortfolioList();

        // Check cached analysis in chrome.storage.local keyed by hostname
        chrome.storage.local.get([`analysis_${currentHostname}`], (res) => {
            const cached = res[`analysis_${currentHostname}`];

            if (cached && cached.data) {
                const now = Date.now();
                const isFresh = (now - (cached.timestamp || 0)) < (24 * 60 * 60 * 1000); // 24hr freshness
                const currentTabUrl = currentActiveTab ? (currentActiveTab.url || "").toLowerCase() : "";
                const isCurrentTabPolicy = currentTabUrl.includes("privacy") || currentTabUrl.includes("terms");
                const wasCachedPolicyBlocked = (cached.data.status === "blocked" || cached.data.status === "not_a_policy");

                // If cache is stale (> 24 hours), or if user is on policy page but cached state was blocked from login page,
                // do not substitute stale negative/blocked result.
                if (!isFresh) {
                    showStatus("Cached analysis is older than 24 hours. Click 'Scan Website' to refresh.", "info");
                    return;
                }
                if (isCurrentTabPolicy && wasCachedPolicyBlocked) {
                    showStatus("Active page is a privacy policy. Click 'Scan Website' to inspect it directly.", "info");
                    return;
                }

                if (cached.policy_url) {
                    policyLink.href = cached.policy_url;
                    policyLink.textContent = `Open Privacy Policy ↗`;
                    policyLinkContainer.classList.remove('hidden');
                }

                if (cached.timestamp) {
                    const d = new Date(cached.timestamp);
                    lastScannedTimeEl.textContent = d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', month: 'short', day: 'numeric' });
                }
                analyzeBtn.textContent = "Re-scan Website";
                displayResults(cached.data, false);
            }
        });
    });

    // Check if website is saved in portfolio
    async function checkPortfolioStatus(hostname) {
        portfolioBadge.textContent = "Checking...";
        portfolioBadge.className = "badge neutral";
        try {
            const res = await fetch(`${BACKEND_URL}/api/service-status?name=${encodeURIComponent(hostname)}`);
            if (res.ok) {
                const data = await res.json();
                if (data.is_saved) {
                    isCurrentSavedInPortfolio = true;
                    portfolioBadge.textContent = "✓ In Portfolio";
                    portfolioBadge.className = "badge saved";
                    saveBtn.textContent = "Update Portfolio";
                } else {
                    isCurrentSavedInPortfolio = false;
                    portfolioBadge.textContent = "○ Not in Portfolio";
                    portfolioBadge.className = "badge unsaved";
                    saveBtn.textContent = "Add to Portfolio";
                }
            } else {
                portfolioBadge.textContent = "○ Not in Portfolio";
                portfolioBadge.className = "badge unsaved";
            }
        } catch (e) {
            portfolioBadge.textContent = "Offline";
            portfolioBadge.className = "badge neutral";
        }
    }

    // Load list of portfolio services for Quick Compare
    async function loadPortfolioList() {
        try {
            const res = await fetch(`${BACKEND_URL}/api/portfolio`);
            if (res.ok) {
                const data = await res.json();
                portfolioServices = data.services || [];
                populateCompareDropdown();
            }
        } catch (e) {
            console.log("Could not load portfolio list for comparison.");
        }
    }

    function populateCompareDropdown() {
        compareTargetSelect.innerHTML = '<option value="">-- Select a saved service --</option>';
        portfolioServices.forEach(svc => {
            const opt = document.createElement('option');
            opt.value = svc.service_name;
            opt.textContent = `${svc.service_name} (Risk: ${Math.round(svc.service_score || 0)})`;
            compareTargetSelect.appendChild(opt);
        });
    }

    // Main Scan Action
    analyzeBtn.addEventListener('click', () => {
        if (!currentActiveTab) return;
        analyzeBtn.disabled = true;
        resultsDiv.classList.add('hidden');
        scanBadge.textContent = "Scanning...";
        scanBadge.className = "badge scanning";
        showStatus("Inspecting webpage for privacy policy...", "info");

        // Inject content script to inspect DOM
        chrome.scripting.executeScript({
            target: { tabId: currentActiveTab.id },
            files: ['content.js']
        }, () => {
            if (chrome.runtime.lastError) {
                scanBadge.textContent = "Unsupported";
                scanBadge.className = "badge neutral";
                showStatus("Could not access page: " + chrome.runtime.lastError.message, "error");
                pasteSection.classList.remove('hidden');
                analyzeBtn.disabled = false;
                return;
            }

            chrome.tabs.sendMessage(currentActiveTab.id, { action: "extract_text" }, async (pageData) => {
                if (chrome.runtime.lastError || !pageData) {
                    scanBadge.textContent = "Unsupported";
                    scanBadge.className = "badge neutral";
                    showStatus("Unable to read page automatically. Paste policy text below to analyze.", "warning");
                    pasteSection.classList.remove('hidden');
                    analyzeBtn.disabled = false;
                    return;
                }

                // Show policy link if detected
                if (pageData.policyLink && pageData.policyLink.href) {
                    policyLink.href = pageData.policyLink.href;
                    policyLink.textContent = `Open ${pageData.policyLink.text || 'Privacy Policy'} ↗`;
                    policyLinkContainer.classList.remove('hidden');
                }

                // Case 1: Currently on a genuine Privacy Policy page
                const isShortPage = pageData.text && pageData.text.length < 1500;
                const hasDiscoveredLink = Boolean(pageData.policyLink && pageData.policyLink.href);

                // If page is clearly a full policy, or if no linked policy exists, analyze current page
                if (pageData.isLikelyPrivacyPolicy && pageData.text && (!isShortPage || !hasDiscoveredLink)) {
                    showStatus("Analysing current privacy policy page...", "info");
                    await runAnalysis({
                        text: pageData.text,
                        url: pageData.url,
                        title: pageData.title,
                        truncated: pageData.truncated
                    });
                    return;
                }

                // Case 2: Discovered a linked privacy policy
                if (pageData.policyLink && pageData.policyLink.href) {
                    const targetLink = pageData.policyLink;
                    showStatus(`Discovered privacy policy link: ${targetLink.text}. Fetching policy text in background...`, "info");

                    try {
                        const proxyRes = await fetch(`${BACKEND_URL}/api/proxy-fetch`, {
                            method: "POST",
                            headers: { "Content-Type": "application/json" },
                            body: JSON.stringify({ url: targetLink.href })
                        });

                        if (proxyRes.ok) {
                            const proxyData = await proxyRes.json();
                            const parser = new DOMParser();
                            const doc = parser.parseFromString(proxyData.html, "text/html");

                            const elementsToRemove = doc.querySelectorAll('script, style, nav, footer, header, noscript, iframe');
                            elementsToRemove.forEach(el => el.remove());

                            let policyText = (doc.body.innerText || "").replace(/\s+/g, ' ').trim();
                            let truncated = false;
                            if (policyText.length > MAX_POLICY_CHARS) {
                                policyText = policyText.substring(0, MAX_POLICY_CHARS);
                                truncated = true;
                            }

                            if (policyText.length < 200) {
                                scanBadge.textContent = "Unable to assess";
                                scanBadge.className = "badge insufficient";
                                showStatus("Discovered policy page had very little readable text. Please open it directly or paste text below.", "warning");
                                pasteSection.classList.remove('hidden');
                                analyzeBtn.disabled = false;
                                return;
                            }

                            const finalPolicyUrl = proxyData.final_url || targetLink.href;
                            showStatus("Policy fetched successfully. Analysing with ClauseGuard engine...", "info");
                            await runAnalysis({
                                text: policyText,
                                url: finalPolicyUrl,
                                title: pageData.title,
                                truncated: truncated
                            });
                        } else {
                            // Proxy blocked by Cloudflare/anti-bot firewall or login barrier
                            scanBadge.textContent = "Blocked";
                            scanBadge.className = "badge blocked";
                            showStatus("🛡️ Website anti-bot protection or login wall blocked the background crawl. Click 'Open Privacy Policy Page ↗' to scan directly, or paste text below.", "warning");
                            policyLinkContainer.classList.remove('hidden');
                            pasteSection.classList.remove('hidden');
                            analyzeBtn.disabled = false;
                        }
                    } catch (err) {
                        scanBadge.textContent = "Error";
                        scanBadge.className = "badge insufficient";
                        showStatus("Background fetch failed. Please open the privacy policy link directly or paste text below.", "warning");
                        pasteSection.classList.remove('hidden');
                        analyzeBtn.disabled = false;
                    }
                    return;
                }

                // Case 3: Neither on policy nor link discovered
                scanBadge.textContent = "No Policy Found";
                scanBadge.className = "badge insufficient";
                showStatus("No privacy policy link was automatically detected on this page. If this service has a policy, open it or paste the text below.", "warning");
                pasteSection.classList.remove('hidden');
                analyzeBtn.disabled = false;
            });
        });
    });

    // Manual Paste Analysis
    if (pasteAnalyzeBtn) {
        pasteAnalyzeBtn.addEventListener('click', async () => {
            const pastedText = pasteTextArea.value.trim();
            if (!pastedText) {
                showStatus("Please paste privacy policy text before analysing.", "warning");
                return;
            }

            pasteAnalyzeBtn.disabled = true;
            showStatus("Analysing pasted policy text...", "info");

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

            // Save to chrome storage isolated by hostname with origin details
            const now = Date.now();
            const lifecycleState = data.status === "ok" ? "success" : (data.status || "success");
            chrome.storage.local.set({
                [`analysis_${currentHostname}`]: {
                    url: currentHostname,
                    page_url: currentActiveTab ? currentActiveTab.url : "",
                    policy_url: data.policy_url || "",
                    policy_url_source: data.policy_url_source || "direct_page",
                    timestamp: now,
                    data: data,
                    lifecycle: lifecycleState
                }
            });

            // Update scan time display
            const d = new Date(now);
            lastScannedTimeEl.textContent = d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', month: 'short', day: 'numeric' });
            analyzeBtn.textContent = "Re-scan Website";

            displayResults(data, true);
        } catch (e) {
            showStatus(`Analysis failed: ${e.message}`, "error");
            pasteSection.classList.remove('hidden');
        } finally {
            analyzeBtn.disabled = false;
        }
    }

    // Render results in the 4-Question UX
    function displayResults(data, isNewScan = false) {
        currentAnalysisResult = data;
        hideStatus();
        resultsDiv.classList.remove('hidden');

        // Mode badge in header
        if (apiModeEl) {
            apiModeEl.textContent = data.mode || "MOCK/DEV";
            apiModeEl.className = `conn ${(data.mode || '').includes("GEMINI") ? "live" : "mock"}`;
        }

        // Coverage badge on site card
        const coverage = data.coverage || {};
        if (data.status === "blocked") {
            scanBadge.textContent = "Blocked";
            scanBadge.className = "badge blocked";
        } else if (data.status === "insufficient_evidence" || coverage.status === "insufficient") {
            scanBadge.textContent = "Unable to assess";
            scanBadge.className = "badge insufficient";
        } else if (coverage.status === "complete" || data.status === "ok") {
            scanBadge.textContent = "✓ Complete Scan";
            scanBadge.className = "badge complete";
        } else if (coverage.status === "partial" || data.status === "partial") {
            scanBadge.textContent = "⚠️ Partial Scan";
            scanBadge.className = "badge partial";
        } else {
            scanBadge.textContent = "⚠️ Insufficient";
            scanBadge.className = "badge insufficient";
        }

        // Check if service is saved in portfolio
        if (data.is_saved_in_portfolio) {
            isCurrentSavedInPortfolio = true;
            portfolioBadge.textContent = "✓ In Portfolio";
            portfolioBadge.className = "badge saved";
            saveBtn.textContent = "Update Portfolio";
        }

        // ----------------------------------------------------
        // QUESTION 1: What data is collected?
        // ----------------------------------------------------
        const q1Chips = document.getElementById('collection-chips');
        const q1List = document.getElementById('collection-findings-list');
        const q1Sub = document.getElementById('q1-sub');

        q1Chips.innerHTML = '';
        q1List.innerHTML = '';

        const entities = data.canonical_entities || [];
        q1Sub.textContent = entities.length > 0 
            ? `${entities.length} data categories identified in policy` 
            : 'No data categories identified';

        if (entities.length === 0) {
            q1List.innerHTML = '<div class="empty-msg">No specific personal data collection categories were identified in the analysed text.</div>';
        } else {
            // Render chips
            entities.forEach(ent => {
                const chip = document.createElement('span');
                chip.className = 'chip';
                chip.textContent = ent;
                chip.addEventListener('click', () => {
                    document.querySelectorAll('#collection-chips .chip').forEach(c => c.classList.remove('active'));
                    chip.classList.add('active');
                    // Scroll to or highlight matching finding
                    const findingEl = document.getElementById(`finding-ent-${ent.replace(/\s+/g, '-')}`);
                    if (findingEl) {
                        findingEl.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
                        findingEl.style.boxShadow = '0 0 0 2px var(--mark)';
                        setTimeout(() => { findingEl.style.boxShadow = ''; }, 1500);
                    }
                });
                q1Chips.appendChild(chip);
            });

            // Render findings with evidence
            const collectionFindings = data.collection_findings || entities.map(e => ({
                entity: e,
                evidence: (data.entity_sources && data.entity_sources[e] && data.entity_sources[e][0]) || null
            }));

            collectionFindings.forEach(item => {
                const div = document.createElement('div');
                div.className = 'finding-item';
                div.id = `finding-ent-${item.entity.replace(/\s+/g, '-')}`;

                const evidenceHtml = item.evidence 
                    ? `<button class="evidence-btn" type="button">Show policy excerpt ▾</button>
                       <div class="evidence-quote hidden">"${escapeHtml(item.evidence)}"</div>`
                    : `<div class="hint" style="margin-top:2px;">Extracted from context in policy text.</div>`;

                div.innerHTML = `
                    <div class="finding-head">
                        <span class="finding-kind">${escapeHtml(item.entity)}</span>
                    </div>
                    ${evidenceHtml}
                `;

                const btn = div.querySelector('.evidence-btn');
                const quote = div.querySelector('.evidence-quote');
                if (btn && quote) {
                    btn.addEventListener('click', () => {
                        const isHidden = quote.classList.contains('hidden');
                        quote.classList.toggle('hidden', !isHidden);
                        btn.textContent = isHidden ? "Hide policy excerpt ▴" : "Show policy excerpt ▾";
                    });
                }
                q1List.appendChild(div);
            });
        }

        // ----------------------------------------------------
        // QUESTION 2: Who is it shared with?
        // ----------------------------------------------------
        const q2List = document.getElementById('sharing-findings-list');
        const q2Sub = document.getElementById('q2-sub');
        q2List.innerHTML = '';

        const sharingFindings = data.sharing_findings || [];
        q2Sub.textContent = sharingFindings.length > 0 
            ? `${sharingFindings.length} third-party disclosure practices identified`
            : 'Not established in policy text';

        if (sharingFindings.length === 0) {
            q2List.innerHTML = '<div class="empty-msg">Recipients and third-party sharing: Not established in the analysed policy text.</div>';
        } else {
            sharingFindings.forEach(item => {
                const div = document.createElement('div');
                div.className = 'finding-item';

                const isSell = (item.kind || '').toLowerCase().includes('sell');
                const kindClass = isSell ? 'finding-kind sell' : 'finding-kind';

                div.innerHTML = `
                    <div class="finding-head">
                        <span class="${kindClass}">${escapeHtml(item.kind || 'Third-Party Disclosure')}</span>
                    </div>
                    <div class="finding-summary">${escapeHtml(item.summary || 'States disclosure to third parties.')}</div>
                    <button class="evidence-btn" type="button">Show clause excerpt ▾</button>
                    <div class="evidence-quote hidden">"${escapeHtml(item.clause_text || '')}"</div>
                `;

                const btn = div.querySelector('.evidence-btn');
                const quote = div.querySelector('.evidence-quote');
                if (btn && quote) {
                    btn.addEventListener('click', () => {
                        const isHidden = quote.classList.contains('hidden');
                        quote.classList.toggle('hidden', !isHidden);
                        btn.textContent = isHidden ? "Hide clause excerpt ▴" : "Show clause excerpt ▾";
                    });
                }
                q2List.appendChild(div);
            });
        }

        // ----------------------------------------------------
        // QUESTION 3: What can I control?
        // ----------------------------------------------------
        const q3List = document.getElementById('control-findings-list');
        const q3Sub = document.getElementById('q3-sub');
        q3List.innerHTML = '';

        const controlFindings = data.control_findings || [];
        q3Sub.textContent = controlFindings.length > 0 
            ? `${controlFindings.length} documented user privacy controls` 
            : 'Not established in policy text';

        if (controlFindings.length === 0) {
            q3List.innerHTML = '<div class="empty-msg">User settings and opt-outs: Not established in the analysed policy text.</div>';
        } else {
            controlFindings.forEach(item => {
                const div = document.createElement('div');
                div.className = 'finding-item';

                div.innerHTML = `
                    <div class="finding-head">
                        <span class="finding-kind">${escapeHtml(item.kind || 'User Control')}</span>
                    </div>
                    <div class="finding-summary">${escapeHtml(item.summary || 'Documented privacy control mechanism.')}</div>
                    <button class="evidence-btn" type="button">Show policy instruction ▾</button>
                    <div class="evidence-quote hidden">"${escapeHtml(item.clause_text || '')}"</div>
                `;

                const btn = div.querySelector('.evidence-btn');
                const quote = div.querySelector('.evidence-quote');
                if (btn && quote) {
                    btn.addEventListener('click', () => {
                        const isHidden = quote.classList.contains('hidden');
                        quote.classList.toggle('hidden', !isHidden);
                        btn.textContent = isHidden ? "Hide policy instruction ▴" : "Show policy instruction ▾";
                    });
                }
                q3List.appendChild(div);
            });
        }

        // ----------------------------------------------------
        // QUESTION 4: Has anything changed?
        // ----------------------------------------------------
        const q4Box = document.getElementById('change-findings-box');
        const q4Sub = document.getElementById('q4-sub');
        q4Box.innerHTML = '';

        const prev = data.previous_scan;
        if (prev) {
            q4Sub.textContent = `Compared with saved version (${prev.service_name})`;
            const currentScore = Math.round(Number(data.risk_score ?? data.risk ?? 0));
            const prevScore = Math.round(Number(prev.service_score ?? 0));
            const scoreDiff = currentScore - prevScore;

            const prevEntities = prev.entities || [];
            const currentEntities = data.canonical_entities || [];

            const newEntities = currentEntities.filter(e => !prevEntities.includes(e));
            const removedEntities = prevEntities.filter(e => !currentEntities.includes(e));

            let html = '';
            if (scoreDiff > 0) {
                html += `<div class="change-item alert">⚠️ Overall risk score increased by +${scoreDiff} points (from ${prevScore} to ${currentScore}/100).</div>`;
            } else if (scoreDiff < 0) {
                html += `<div class="change-item safe">✓ Overall risk score decreased by ${scoreDiff} points (from ${prevScore} to ${currentScore}/100).</div>`;
            } else {
                html += `<div class="change-item">Overall risk score unchanged (${currentScore}/100).</div>`;
            }

            if (newEntities.length > 0) {
                html += `<div class="change-item alert">⚠️ Newly introduced data types: <b>${escapeHtml(newEntities.join(', '))}</b></div>`;
            } else {
                html += `<div class="change-item">No new data categories introduced.</div>`;
            }

            if (removedEntities.length > 0) {
                html += `<div class="change-item safe">No longer stated as collected: ${escapeHtml(removedEntities.join(', '))}</div>`;
            }

            const currentClauseCount = (data.clauses || []).length;
            const prevClauseCount = prev.clause_count || 0;
            const clauseDiff = currentClauseCount - prevClauseCount;
            html += `<div class="change-item">Policy clauses: ${currentClauseCount} (${clauseDiff >= 0 ? '+' : ''}${clauseDiff} compared to saved version).</div>`;

            q4Box.innerHTML = html;
        } else {
            q4Sub.textContent = 'First recorded scan for this website';
            q4Box.innerHTML = '<div class="empty-msg">This is the first recorded scan for this service. Future scans will display any policy modifications and disclosure changes here.</div>';
        }

        // ----------------------------------------------------
        // Secondary Score & Audit Summary
        // ----------------------------------------------------
        const pres = data.presentation_verdict || {};
        const isInsufficient = (data.status === "insufficient_evidence" || (data.coverage && data.coverage.status === "insufficient"));
        const scoreVal = isInsufficient ? null : Number(data.risk_score ?? data.risk ?? 0);
        document.getElementById('risk-score').textContent = (scoreVal !== null) ? scoreVal.toFixed(0) : "--";

        const category = pres.label || data.risk_category || 'Inconclusive';
        const bandEl = document.getElementById('risk-band');
        if (bandEl) {
            bandEl.textContent = category;
            let bandClass = "Moderate";
            if (category === "Lower Risk" || category === "Low") bandClass = "Low";
            else if (category === "Moderate Risk" || category === "Moderate") bandClass = "Moderate";
            else if (category === "Elevated Risk" || category === "High" || category === "Very High") bandClass = "High";
            else bandClass = "Inconclusive";
            bandEl.className = `band ${bandClass}`;
        }

        const gaugeFill = document.getElementById('gauge-fill');
        if (gaugeFill) {
            const pct = (scoreVal !== null) ? Math.min(100, Math.max(0, Math.round(scoreVal))) : 0;
            gaugeFill.style.width = `${pct}%`;
            if (pct >= 60) gaugeFill.style.backgroundColor = "var(--alert)";
            else if (pct >= 30) gaugeFill.style.backgroundColor = "var(--warning)";
            else gaugeFill.style.backgroundColor = "var(--safe)";
        }

        // Coverage Box
        const coverageEl = document.getElementById('coverage-note');
        if (coverageEl) {
            let covHtml = '';
            if (coverage.status === 'partial' || data.status === 'partial') {
                covHtml = `
                    <div class="cov-status" style="color:var(--warning);">⚠️ Partial Analysis</div>
                    <div>Analysed ${coverage.analysed_chars ?? '?'} characters across segmented chunks (${coverage.clauses_found ?? 0} clauses identified).</div>
                `;
            } else if (coverage.status === 'insufficient' || data.status === 'insufficient_evidence') {
                covHtml = `
                    <div class="cov-status" style="color:var(--alert);">⚠️ Insufficient Evidence</div>
                    <div>Less than 300 characters or no privacy clauses were found. The score is deemed Unable to assess.</div>
                `;
            } else {
                covHtml = `
                    <div class="cov-status" style="color:var(--safe);">✓ Complete Scan</div>
                    <div>Analysed ${coverage.analysed_chars ?? '?'} characters. Extracted ${coverage.clauses_found ?? 0} privacy clauses.</div>
                `;
            }
            if (coverage.is_demo) {
                covHtml += `<div class="hint" style="margin-top:2px;">⚡ Evaluated via local offline demo model.</div>`;
            }
            coverageEl.innerHTML = covHtml;
        }

        // Extracted Clauses
        const clauses = data.clauses || [];
        document.getElementById('clause-count').textContent = clauses.length;
        clausesDetailsDiv.innerHTML = '';
        clauses.forEach(c => {
            const card = document.createElement('div');
            card.className = 'clause-card';
            const sev = Math.min(5, Math.max(0, Number(c.severity_score) || 0));
            const spec = Math.min(5, Math.max(0, Number(c.specificity_score) || 0));
            const cRisk = Math.round(100 * (sev / 5) * (spec / 5));

            card.innerHTML = `
                <div class="clause-quote">"${escapeHtml(c.text || '')}"</div>
                <div class="clause-meta">
                    <span>${escapeHtml(c.risk_category || 'Identified Clause')}</span>
                    <span>Risk: <b>${cRisk}/100</b></span>
                </div>
            `;
            clausesDetailsDiv.appendChild(card);
        });

        // Toggle clauses list
        toggleClausesBtn.onclick = () => {
            const isHidden = clausesDetailsDiv.classList.contains('hidden');
            clausesDetailsDiv.classList.toggle('hidden', !isHidden);
            toggleClausesBtn.textContent = isHidden ? "Hide all clauses" : "View all clauses";
        };
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
                portfolioBadge.textContent = "✓ In Portfolio";
                portfolioBadge.className = "badge saved";
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

    // Quick Compare Action
    if (compareBtn) {
        compareBtn.addEventListener('click', async () => {
            if (!currentAnalysisResult) return;
            const target = compareTargetSelect.value;
            if (!target) {
                compareResultsDiv.innerHTML = '<span style="color:var(--alert);">Please select a website from the dropdown.</span>';
                compareResultsDiv.classList.remove('hidden');
                return;
            }

            compareBtn.disabled = true;
            compareBtn.textContent = "Comparing...";

            try {
                const res = await fetch(`${BACKEND_URL}/api/quick-compare`, {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({
                        candidate: currentAnalysisResult,
                        target: target
                    })
                });

                if (!res.ok) throw new Error("Comparison request failed");
                const comp = await res.json();

                const overlap = comp.overlap || [];
                const newTypes = comp.new || [];

                const overlapText = overlap.length > 0 ? overlap.map(escapeHtml).join(", ") : "None";
                const newText = newTypes.length > 0 ? newTypes.map(escapeHtml).join(", ") : "None";

                const verdictText = newTypes.length > 0
                    ? `⚠️ Adds ${newTypes.length} data types not collected by ${escapeHtml(target)}.`
                    : `No new data types beyond what ${escapeHtml(target)} collects.`;

                compareResultsDiv.innerHTML = `
                    <div style="margin-bottom: 5px;"><b>⚖️ Overlapping data practices with ${escapeHtml(target)}:</b> ${overlap.length} categories</div>
                    <div style="color: var(--ink-3); font-size: 11px; margin-bottom: 8px;">${overlapText}</div>
                    
                    <div style="margin-bottom: 5px;"><b>🚨 Newly introduced data categories:</b> ${newTypes.length} categories</div>
                    <div style="color: ${newTypes.length > 0 ? 'var(--alert)' : 'var(--safe)'}; font-size: 11px; margin-bottom: 8px;">${newText}</div>
                    
                    <div style="font-weight: 700; color: ${newTypes.length > 0 ? 'var(--alert)' : 'var(--safe)'}; border-top: 1px solid var(--line); padding-top: 6px;">
                        ${verdictText}
                    </div>
                    <div class="hint" style="margin-top: 4px; font-style: italic;">
                        Comparison reflects stated website policy disclosures and does not imply browser extension permissions or data transfer between services.
                    </div>
                `;
                compareResultsDiv.classList.remove('hidden');
            } catch (e) {
                compareResultsDiv.innerHTML = '<span style="color:var(--alert);">Error executing comparison.</span>';
                compareResultsDiv.classList.remove('hidden');
            } finally {
                compareBtn.disabled = false;
                compareBtn.textContent = "Compare";
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
