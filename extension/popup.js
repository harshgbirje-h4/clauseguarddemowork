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
                        analyzeBtn.style.display = "none"; // Hide button since it's already analyzed
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
                        return; // Completely stop the AI analysis since we are blocked
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

    // (sendToBackend has been removed because content.js handles it now)

    function displayResults(data) {
        hideStatus();
        analyzeBtn.disabled = false;
        resultsDiv.classList.remove('hidden');

        document.getElementById('risk-score').textContent = data.risk.toFixed(1);
        document.getElementById('api-mode').textContent = data.mode;
        
        // Mode styling
        const modeEl = document.getElementById('mode-indicator');
        if (data.mode === "MOCK/DEV") {
            modeEl.style.backgroundColor = "#fef08a"; // yellow
            modeEl.style.color = "#854d0e";
        } else {
            modeEl.style.backgroundColor = "#bbf7d0"; // green
            modeEl.style.color = "#166534";
        }

        const entitiesList = document.getElementById('entities-list');
        entitiesList.innerHTML = '';
        if (data.canonical_entities.length === 0) {
            entitiesList.innerHTML = '<li>None detected</li>';
        } else {
            data.canonical_entities.forEach(ent => {
                const li = document.createElement('li');
                li.textContent = ent;
                entitiesList.appendChild(li);
            });
        }

        document.getElementById('clause-count').textContent = data.clauses.length;

        clausesDetailsDiv.innerHTML = '';
        data.clauses.forEach(c => {
            const card = document.createElement('div');
            card.className = 'clause-card';
            
            // Limit text length in UI
            let text = c.text;
            if (text.length > 150) {
                text = text.substring(0, 150) + '...';
            }

            const risk = ((c.severity_score || 0) + (c.specificity_score || 0)).toFixed(1);

            card.innerHTML = `
                <div class="clause-text">"${text}"</div>
                <div class="clause-meta">
                    <span>Cat: ${c.risk_category || 'N/A'}</span>
                    <span>Risk: ${risk}</span>
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
        document.getElementById('compare-section').style.display = 'block';
        fetchPortfolio();
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

    compareBtn.addEventListener('click', async () => {
        if (!currentAnalysisResult) return;
        const target = document.getElementById('compare-target').value;
        if (!target) {
            compareResults.innerHTML = "<span style='color:#ef4444;'>Please select a website.</span>";
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
                <div style="margin-bottom: 6px;"><strong>⚖️ Overlap with ${target}:</strong> ${data.overlap.length} entities</div>
                <div style="color: #64748b; font-size: 12px; margin-bottom: 12px;">${overlapText}</div>
                
                <div style="margin-bottom: 6px;"><strong>🚨 NEW Risks added:</strong> ${data.new.length} entities</div>
                <div style="color: ${data.new.length > 0 ? '#ef4444' : '#22c55e'}; font-size: 12px; margin-bottom: 8px;">${newText}</div>
                
                <div style="font-weight: bold; color: ${data.new.length > 0 ? '#dc2626' : '#16a34a'}; border-top: 1px solid #e2e8f0; padding-top: 8px; margin-top: 4px;">
                    ${data.new.length > 0 ? '⚠️ Warning: You are exposing new data!' : '✅ Safe: No new data types exposed.'}
                </div>
            `;
            compareResults.innerHTML = html;
            compareResults.classList.remove('hidden');
        } catch (e) {
            compareResults.innerHTML = "<span style='color:#ef4444;'>Error comparing websites.</span>";
            compareResults.classList.remove('hidden');
        } finally {
            compareBtn.disabled = false;
            compareBtn.textContent = "Compare";
        }
    });

    const saveBtn = document.getElementById('save-btn');
    const saveStatus = document.getElementById('save-status');
    
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
            saveStatus.textContent = "Successfully saved!";
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
});
