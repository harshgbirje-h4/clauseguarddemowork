// Extract text from the page safely
function extractPageText() {
    // Basic heuristic cleanup: remove hidden elements, scripts, styles
    const clone = document.body.cloneNode(true);
    
    const elementsToRemove = clone.querySelectorAll('script, style, nav, footer, header, noscript, iframe');
    elementsToRemove.forEach(el => el.remove());

    let text = clone.innerText || "";
    
    // Normalize excessive whitespace
    text = text.replace(/\s+/g, ' ').trim();
    
    // Sensible text limit (50,000 characters to process the entire document)
    const MAX_LENGTH = 50000;
    const truncated = text.length > MAX_LENGTH;
    if (truncated) {
        text = text.substring(0, MAX_LENGTH);
    }
    
    // Basic heuristic to guess if this is a privacy policy
    const titleLower = document.title.toLowerCase();
    const urlLower = window.location.href.toLowerCase();
    const privacyKeywords = ['privacy policy', 'privacy notice', 'privacy statement', 'data protection', 'data policy', 'privacy'];
    
    let isLikelyPrivacyPolicy = false;
    if (privacyKeywords.some(kw => titleLower.includes(kw) || urlLower.includes(kw.replace(' ', '-')) || urlLower.includes(kw.replace(' ', '')))) {
        isLikelyPrivacyPolicy = true;
    }
    
    if (!isLikelyPrivacyPolicy) {
        const headings = Array.from(document.querySelectorAll('h1, h2, h3')).map(h => h.innerText.toLowerCase());
        if (headings.some(h => privacyKeywords.some(kw => h.includes(kw)))) {
            isLikelyPrivacyPolicy = true;
        }
    }
    
    const textPrefix = text.substring(0, 2000).toLowerCase();
    if (!isLikelyPrivacyPolicy && privacyKeywords.some(kw => textPrefix.includes(kw))) {
         isLikelyPrivacyPolicy = true;
    }

    let title = document.title;
    if (!title || title.trim() === "") {
        try {
            title = new URL(window.location.href).hostname;
        } catch(e) {
            title = "Unknown Service";
        }
    }

    return {
        text: text,
        url: window.location.href,
        title: title,
        truncated: truncated,
        isLikelyPrivacyPolicy: isLikelyPrivacyPolicy
    };
}

chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
    if (request.action === "extract_text") {
        handleExtraction().then(data => sendResponse(data));
        return true; // Keep message channel open for async response
    }
    
    if (request.action === "run_backend_analysis") {
        // This runs in the web page context, so it won't die if the popup closes!
        fetch("http://127.0.0.1:5000/api/analyze-policy", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                text: request.data.text,
                url: request.data.url,
                title: request.data.title
            })
        })
        .then(res => res.json())
        .then(analysisData => {
            // Save it so popup can read it later
            chrome.storage.local.set({
                cachedAnalysis: {
                    url: window.location.hostname,
                    timestamp: Date.now(),
                    data: analysisData,
                    newEntities: []
                }
            });
            sendResponse({status: "success", data: analysisData});
        })
        .catch(err => {
            sendResponse({status: "error", error: err.message});
        });
        
        return true;
    }
});

async function handleExtraction() {
    const basicData = extractPageText();
    
    // If user is already looking at the privacy policy, just use the page text
    if (basicData.isLikelyPrivacyPolicy) {
        return basicData;
    }

    // If they are on a shopping site homepage, let's auto-discover the policy for them!
    const privacyLink = findPrivacyPolicyLink();
    if (privacyLink) {
        try {
            const proxyResponse = await fetch("http://127.0.0.1:5000/api/proxy-fetch", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ url: privacyLink.href })
            });
            
            if (proxyResponse.ok) {
                const proxyData = await proxyResponse.json();
                const parser = new DOMParser();
                const doc = parser.parseFromString(proxyData.html, "text/html");
                
                const elementsToRemove = doc.querySelectorAll('script, style, nav, footer, header, noscript, iframe');
                elementsToRemove.forEach(el => el.remove());
                
                let policyText = doc.body.innerText.replace(/\s+/g, ' ').trim();
                let truncated = false;
                if (policyText.length > 50000) {
                    policyText = policyText.substring(0, 50000);
                    truncated = true;
                }
                
                return {
                    text: policyText,
                    url: privacyLink.href,
                    title: basicData.title,
                    truncated: truncated,
                    isLikelyPrivacyPolicy: true,
                    wasAutoDiscovered: true
                };
            } else {
                return {
                    error: true,
                    blockedBySecurity: true,
                    message: "🛡️ Anti-Bot Security Firewall blocked the background scan. Please click the Privacy Policy link at the bottom of the page to scan it directly."
                };
            }
        } catch (e) {
            console.error("Auto-discovery fetch failed", e);
        }
    }
    
    // Fallback if no link found
    return basicData;
}

/* =========================================
   THE ACTIVE LOGIN SHIELD (Plan A)
========================================= */

async function initActiveLoginShield() {
    // 1. Smart Context Detection (MIME-Type & URL Filtering)
    if (document.contentType !== "text/html") return; // Ignore images/videos

    const urlObj = new URL(window.location.href);
    const path = urlObj.pathname.toLowerCase();
    const host = urlObj.hostname.toLowerCase();
    
    // Ignore search engine result pages completely
    if (host.includes("google.") && path.includes("/search")) return;
    if (host.includes("bing.com") || host.includes("yahoo.com") || path.includes("/search")) return;

    // Look for a password field
    const passwordField = document.querySelector('input[type="password"]');
    
    // Must be in the PATH (e.g. /login), NOT in the search query (e.g. ?q=login)
    const isAuthPath = path.match(/\/(login|signin|auth|oauth|account\/login|wp-login)/) !== null;
    
    // Only wake up if we are 100% sure the user is logging in
    if (!passwordField && !isAuthPath) return;

    // --- NEW: SMART CACHING SYSTEM ---
    const cacheResult = await new Promise(resolve => chrome.storage.local.get(['cachedAnalysis'], resolve));
    if (cacheResult.cachedAnalysis && cacheResult.cachedAnalysis.url === window.location.hostname) {
        const timeElapsed = Date.now() - cacheResult.cachedAnalysis.timestamp;
        // If cache is less than 24 hours old, use it instantly!
        if (timeElapsed < 24 * 60 * 60 * 1000) {
            console.log("[ClauseGuard] Loaded analysis from Smart Cache to save API limits.");
            injectShieldUI();
            const analysisData = cacheResult.cachedAnalysis.data;
            const newEntities = cacheResult.cachedAnalysis.newEntities || [];
            
            if (analysisData.risk > 50 || newEntities.length > 0) {
                let msg = `🚨 High Privacy Risk (Score: ${analysisData.risk.toFixed(1)}).`;
                if (newEntities.length > 0) msg += ` Exposing new data (${newEntities.join(', ')}).`;
                updateShieldUI(msg, "red");
            } else {
                updateShieldUI(`✅ Safe Login (Score: ${analysisData.risk.toFixed(1)}). Limited data exposure.`, "green");
            }
            return; // Stop execution here. No Gemini API calls made!
        }
    }
    // ---------------------------------

    console.log("[ClauseGuard] Active Login Shield Activated. Detecting privacy risks...");

    // Inject Shield Badge near password field (or top of page if none found)
    injectShieldUI();

    // 2. Automated Privacy Policy Discovery
    const privacyLink = findPrivacyPolicyLink();
    if (!privacyLink) {
        updateShieldUI("⚠️ No Privacy Policy found on this login page.", "orange");
        return;
    }

    updateShieldUI("Crawling Privacy Policy...", "blue");

    try {
        // Fetch background policy HTML via Python proxy to bypass CORS blocks
        const proxyResponse = await fetch("http://127.0.0.1:5000/api/proxy-fetch", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ url: privacyLink.href })
        });
        
        if (!proxyResponse.ok) {
            updateShieldUI("🛡️ Anti-Bot Security Firewall blocked background scan. Click the Privacy Policy link to scan directly.", "orange");
            return;
        }
        const proxyData = await proxyResponse.json();
        const html = proxyData.html;
        
        const parser = new DOMParser();
        const doc = parser.parseFromString(html, "text/html");
        
        let policyText = doc.body.innerText.replace(/\s+/g, ' ').trim().substring(0, 15000); // 15k chars to save time

        // 3. Real-Time Interception & Gemini Analysis
        updateShieldUI("Analyzing risks via Gemini...", "blue");
        
        const analyzeRes = await fetch("http://127.0.0.1:5000/api/analyze-policy", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                text: policyText,
                url: window.location.href,
                title: document.title
            })
        });

        if (!analyzeRes.ok) throw new Error("API Failed");
        const analysisData = await analyzeRes.json();

        // 3b. Pre-Login Comparison (Check against portfolio)
        updateShieldUI("Comparing against your portfolio...", "blue");
        const marginalRes = await fetch("http://127.0.0.1:5000/api/marginal-risk", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(analysisData)
        });
        
        let newEntities = [];
        if (marginalRes.ok) {
            const marginalData = await marginalRes.json();
            newEntities = marginalData.new_entities || [];
        }

        // Save everything for the popup and future page reloads
        chrome.storage.local.set({
            cachedAnalysis: {
                url: window.location.hostname,
                timestamp: Date.now(),
                data: analysisData,
                newEntities: newEntities
            }
        });

        // 4. In-Page Warning UI Update
        if (analysisData.risk > 50 || newEntities.length > 0) {
            let msg = `🚨 High Privacy Risk (Score: ${analysisData.risk.toFixed(1)}).`;
            if (newEntities.length > 0) {
                msg += ` Exposing new data (${newEntities.join(', ')}).`;
            }
            updateShieldUI(msg, "red");
        } else {
            updateShieldUI(`✅ Safe Login (Score: ${analysisData.risk.toFixed(1)}). Limited data exposure.`, "green");
        }

    } catch (e) {
        console.error(e);
        updateShieldUI("⚠️ ClauseGuard could not analyze the background policy.", "orange");
    }
}

function findPrivacyPolicyLink() {
    const links = Array.from(document.querySelectorAll('a'));
    for (let a of links) {
        const text = a.innerText.toLowerCase();
        if (text.includes("privacy") || text.includes("terms of service") || text.includes("legal")) {
            return a;
        }
    }
    return null;
}

let shieldBanner = null;

function injectShieldUI() {
    const passwordField = document.querySelector('input[type="password"]');
    
    shieldBanner = document.createElement("div");
    shieldBanner.style.display = "flex";
    shieldBanner.style.alignItems = "center";
    shieldBanner.style.justifyContent = "center";
    shieldBanner.style.backgroundColor = "#f8fafc";
    shieldBanner.style.color = "#334155";
    shieldBanner.style.padding = "10px 14px";
    shieldBanner.style.borderRadius = "8px";
    shieldBanner.style.fontFamily = "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif";
    shieldBanner.style.fontWeight = "600";
    shieldBanner.style.boxShadow = "0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06)";
    shieldBanner.style.border = "1px solid #e2e8f0";
    shieldBanner.style.fontSize = "13px";
    shieldBanner.style.marginTop = "8px";
    shieldBanner.style.marginBottom = "12px";
    shieldBanner.style.zIndex = "999999";
    shieldBanner.style.transition = "all 0.3s ease-in-out";
    shieldBanner.style.width = "100%";
    shieldBanner.style.boxSizing = "border-box";
    shieldBanner.innerHTML = `<span style="margin-right: 8px;">🛡️</span> <span>ClauseGuard: Scanning Login Risks...</span>`;
    
    if (passwordField && passwordField.parentNode) {
        passwordField.parentNode.insertBefore(shieldBanner, passwordField);
    } else {
        shieldBanner.style.position = "fixed";
        shieldBanner.style.top = "16px";
        shieldBanner.style.right = "16px";
        shieldBanner.style.width = "auto";
        document.body.appendChild(shieldBanner);
    }
}

function updateShieldUI(text, colorType) {
    if (!shieldBanner) return;
    shieldBanner.innerHTML = `<span style="margin-right: 8px;">🛡️</span> <span>${text}</span>`;
    
    if (colorType === "red") {
        shieldBanner.style.backgroundColor = "#fef2f2";
        shieldBanner.style.color = "#991b1b";
        shieldBanner.style.border = "1px solid #fecaca";
    } else if (colorType === "green") {
        shieldBanner.style.backgroundColor = "#f0fdf4";
        shieldBanner.style.color = "#166534";
        shieldBanner.style.border = "1px solid #bbf7d0";
    } else if (colorType === "orange") {
        shieldBanner.style.backgroundColor = "#fffbeb";
        shieldBanner.style.color = "#92400e";
        shieldBanner.style.border = "1px solid #fde68a";
    } else if (colorType === "blue") {
        shieldBanner.style.backgroundColor = "#eff6ff";
        shieldBanner.style.color = "#1e40af";
        shieldBanner.style.border = "1px solid #bfdbfe";
    }
}

// Run the shield when the page loads
setTimeout(initActiveLoginShield, 1000);
