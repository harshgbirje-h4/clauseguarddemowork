document.addEventListener('DOMContentLoaded', () => {
    let currentAnalysisResult = null;
    const siteNameSpan = document.getElementById('site-name');
    const analyzeBtn = document.getElementById('analyze-btn');
    const statusDiv = document.getElementById('status');
    const resultsDiv = document.getElementById('results');
    const toggleClausesBtn = document.getElementById('toggle-clauses-btn');
    const clausesDetailsDiv = document.getElementById('clauses-details');

    // Get current tab info and check for cached analysis
    chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
        const activeTab = tabs[0];
        if (activeTab && activeTab.url) {
            try {
                const url = new URL(activeTab.url);
                siteNameSpan.textContent = url.hostname;
                
                // Check if the Shield already analyzed this
                chrome.storage.local.get(['cachedAnalysis'], (result) => {
                    if (result.cachedAnalysis && result.cachedAnalysis.url === url.hostname) {
                        showStatus("Analyzed automatically by Login Shield.", "success");
                        displayResults(result.cachedAnalysis.data);
                        analyzeBtn.style.display = "none";
                    }
                });
            } catch (e) {
                siteNameSpan.textContent = "Unknown";
            }
        }
    });

    function showStatus(msg, type = "info") {
        statusDiv.textContent = msg;
        statusDiv.className = `status ${type}`;
        statusDiv.classList.remove('hidden');
    }

    function hideStatus() {
        statusDiv.classList.add('hidden');
    }

    function getRiskBand(score) {
        if (score < 15) return "Low";
        if (score < 30) return "Moderate";
        return "High";
    }

    analyzeBtn.addEventListener('click', () => {
        analyzeBtn.disabled = true;
        resultsDiv.classList.add('hidden');
        showStatus("Extracting page text...", "info");

        chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
            const activeTab = tabs[0];
            
            if (activeTab.url.startsWith('chrome://')) {
                showStatus("Cannot analyze chrome:// pages.", "error");
                analyzeBtn.disabled = false;
                return;
            }

            // Inject content script and ask for text
            chrome.scripting.executeScript({
                target: { tabId: activeTab.id },
                files: ['content.js']
            }, () => {
                if (chrome.runtime.lastError) {
                    showStatus("Failed to inject script: " + chrome.runtime.lastError.message, "error");
                    analyzeBtn.disabled = false;
                    return;
                }

                chrome.tabs.sendMessage(activeTab.id, { action: "extract_text" }, (response) => {
                    if (chrome.runtime.lastError || !response) {
                        showStatus("ClauseGuard couldn't analyze this page. Please refresh and try again.", "error");
                        analyzeBtn.disabled = false;
                        return;
                    }

                    if (!response.text || response.text.trim().length === 0) {
                        showStatus("No readable text found on this page.", "error");
                        analyzeBtn.disabled = false;
                        return;
                    }

                    if (response.error && response.blockedBySecurity) {
                        showStatus(response.message, "error");
                        analyzeBtn.disabled = false;
                        return;
                    }

                    if (!response.isLikelyPrivacyPolicy) {
                        if (!confirm("This page does not appear to be a privacy policy. Do you want to scan it anyway?")) {
                            hideStatus();
                            analyzeBtn.disabled = false;
                            return;
                        }
                    }

                    if (response.wasAutoDiscovered) {
                        showStatus("Found hidden policy! Sending to background...", "info");
                    } else if (response.truncated) {
                        showStatus("Sending top 15k characters to background...", "warning");
                    } else {
                        showStatus("Sending to ClauseGuard background...", "info");
                    }

                    // Delegate the fetch to the content script so it doesn't die if popup closes
                    chrome.tabs.sendMessage(activeTab.id, { action: "run_backend_analysis", data: response }, (backendRes) => {
                        if (chrome.runtime.lastError || !backendRes) {
                            showStatus("Analysis was sent to background. Reopen popup soon to check results!", "info");
                            return;
                        }
                        if (backendRes.status === "error") {
                            showStatus(`Analysis failed: ${backendRes.error}`, "error");
                            analyzeBtn.disabled = false;
                        } else {
                            displayResults(backendRes.data);
                        }
                    });
                });
            });
        });
    });

    function displayResults(data) {
        hideStatus();
        analyzeBtn.disabled = false;
        resultsDiv.classList.remove('hidden');

        const score = data.risk || 0;
        document.getElementById('risk-score').textContent = score.toFixed(1);
        
        const band = getRiskBand(score);
        const bandEl = document.getElementById('risk-band');
        if (bandEl) {
            bandEl.textContent = band;
            bandEl.className = `band ${band}`;
        }

        const gaugeFill = document.getElementById('gauge-fill');
        if (gaugeFill) {
            const pct = Math.min(100, Math.round((score / 40) * 100));
            gaugeFill.style.width = `${pct}%`;
        }

        const modeText = document.getElementById('mode-text');
        const apiModeTop = document.getElementById('api-mode');
        if (modeText) modeText.textContent = data.mode;
        if (apiModeTop) {
            apiModeTop.textContent = data.mode;
            apiModeTop.className = `conn ${data.mode.includes("GEMINI") ? "live" : "mock"}`;
        }

        // Detected entities as chips
        const entitiesList = document.getElementById('entities-list');
        entitiesList.innerHTML = '';
        if (!data.canonical_entities || data.canonical_entities.length === 0) {
            entitiesList.innerHTML = '<span class="chip">None detected</span>';
        } else {
            data.canonical_entities.forEach(ent => {
                const chip = document.createElement('span');
                chip.className = 'chip';
                chip.textContent = ent;
                entitiesList.appendChild(chip);
            });
        }

        document.getElementById('clause-count').textContent = data.clauses.length;

        // Clauses list
        clausesDetailsDiv.innerHTML = '';
        data.clauses.forEach(c => {
            const card = document.createElement('div');
            card.className = 'clause-card';
            
            let text = c.text;
            if (text.length > 140) {
                text = text.substring(0, 140) + '...';
            }

            const risk = ((c.severity_score || 0) + (c.specificity_score || 0)).toFixed(1);

            card.innerHTML = `
                <div class="clause-text">"${text}"</div>
                <div class="clause-meta">
                    <span>${c.risk_category || 'General Risk'}</span>
                    <span>Risk: <b>${risk}</b></span>
                </div>
            `;
            clausesDetailsDiv.appendChild(card);
        });

        currentAnalysisResult = data;
        const saveBtn = document.getElementById('save-btn');
        const saveStatus = document.getElementById('save-status');
        saveBtn.disabled = false;
        saveBtn.textContent = "Add to Portfolio";
        saveStatus.classList.add('hidden');
        
        // Show compare section and fetch portfolio
        const compareSection = document.getElementById('compare-section');
        if (compareSection) {
            compareSection.style.display = 'block';
            fetchPortfolio();
        }
    }

    async function fetchPortfolio() {
        try {
            const res = await fetch("http://127.0.0.1:5000/api/portfolio");
            if (res.ok) {
                const data = await res.json();
                const dropdown = document.getElementById('compare-target');
                dropdown.innerHTML = '<option value="">-- Select website --</option>';
                if (data.services) {
                    data.services.forEach(svc => {
                        const opt = document.createElement('option');
                        opt.value = svc.service_name;
                        opt.textContent = svc.service_name;
                        dropdown.appendChild(opt);
                    });
                }
            }
        } catch (e) {
            console.log("Could not load portfolio for comparison.");
        }
    }

    toggleClausesBtn.addEventListener('click', () => {
        if (clausesDetailsDiv.classList.contains('hidden')) {
            clausesDetailsDiv.classList.remove('hidden');
            toggleClausesBtn.textContent = "Hide Details";
        } else {
            clausesDetailsDiv.classList.add('hidden');
            toggleClausesBtn.textContent = "View Details";
        }
    });

    const compareBtn = document.getElementById('compare-btn');
    const compareResults = document.getElementById('compare-results');

    if (compareBtn) {
        compareBtn.addEventListener('click', async () => {
            if (!currentAnalysisResult) return;
            const target = document.getElementById('compare-target').value;
            if (!target) {
                compareResults.innerHTML = "<span style='color:var(--alert);'>Please select a website.</span>";
                compareResults.classList.remove('hidden');
                return;
            }
            
            compareBtn.disabled = true;
            compareBtn.textContent = "Wait...";
            
            try {
                const res = await fetch("http://127.0.0.1:5000/api/quick-compare", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({
                        candidate: currentAnalysisResult,
                        target: target
                    })
                });
                
                if (!res.ok) throw new Error("Comparison failed");
                const data = await res.json();
                
                let overlapText = data.overlap.length > 0 ? data.overlap.join(", ") : "None";
                let newText = data.new.length > 0 ? data.new.join(", ") : "None";
                
                let html = `
                    <div style="margin-bottom: 6px;"><b>⚖️ Overlap with ${target}:</b> ${data.overlap.length} entities</div>
                    <div style="color: var(--ink-3); font-size: 11.5px; margin-bottom: 10px;">${overlapText}</div>
                    
                    <div style="margin-bottom: 6px;"><b>🚨 NEW Risks added:</b> ${data.new.length} entities</div>
                    <div style="color: ${data.new.length > 0 ? 'var(--alert)' : 'var(--safe)'}; font-size: 11.5px; margin-bottom: 8px;">${newText}</div>
                    
                    <div style="font-weight: 700; color: ${data.new.length > 0 ? 'var(--alert)' : 'var(--safe)'}; border-top: 1px solid var(--line); padding-top: 6px; margin-top: 4px;">
                        ${data.new.length > 0 ? '⚠️ Warning: New data types exposed!' : '✅ Safe: No new data types exposed.'}
                    </div>
                `;
                compareResults.innerHTML = html;
                compareResults.classList.remove('hidden');
            } catch (e) {
                compareResults.innerHTML = "<span style='color:var(--alert);'>Error comparing websites.</span>";
                compareResults.classList.remove('hidden');
            } finally {
                compareBtn.disabled = false;
                compareBtn.textContent = "Compare";
            }
        });
    }

    const saveBtn = document.getElementById('save-btn');
    const saveStatus = document.getElementById('save-status');
    
    if (saveBtn) {
        saveBtn.addEventListener('click', async () => {
            if (!currentAnalysisResult) return;
            
            saveBtn.disabled = true;
            saveBtn.textContent = "Saving...";
            saveStatus.classList.add('hidden');
            
            try {
                const res = await fetch("http://127.0.0.1:5000/api/save-service", {
                    method: "POST",
                    headers: {
                        "Content-Type": "application/json"
                    },
                    body: JSON.stringify(currentAnalysisResult)
                });

                if (!res.ok) {
                    let errText = "Failed to save.";
                    try {
                        const errObj = await res.json();
                        errText = errObj.error || errText;
                    } catch(e) {}
                    throw new Error(errText);
                }

                saveBtn.textContent = "Added to Portfolio";
                saveStatus.textContent = "Successfully added to portfolio!";
                saveStatus.className = "status success";
                saveStatus.classList.remove('hidden');
                
            } catch (error) {
                saveBtn.disabled = false;
                saveBtn.textContent = "Retry Add";
                saveStatus.textContent = `Error: ${error.message}`;
                saveStatus.className = "status error";
                saveStatus.classList.remove('hidden');
            }
        });
    }
});
