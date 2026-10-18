// ClauseGuard Content Script
// Extracts text, detects privacy policies & links, and powers the Active Login Shield

const MAX_POLICY_CHARS = 50000;

// Extract readable text from the current page
function extractPageText() {
    const clone = document.body.cloneNode(true);
    
    // Remove scripts, styles, navigation, headers, footers, noscript, iframe
    const elementsToRemove = clone.querySelectorAll('script, style, nav, footer, header, noscript, iframe');
    elementsToRemove.forEach(el => el.remove());

    let text = clone.innerText || "";
    text = text.replace(/\s+/g, ' ').trim();
    
    const truncated = text.length > MAX_POLICY_CHARS;
    if (truncated) {
        text = text.substring(0, MAX_POLICY_CHARS);
    }
    
    // Heuristic detection: is the current page likely a privacy policy?
    const titleLower = (document.title || "").toLowerCase();
    const urlLower = (window.location.href || "").toLowerCase();
    const privacyKeywords = ['privacy policy', 'privacy notice', 'privacy statement', 'data protection', 'data policy', 'privacy'];
    
    let isLikelyPrivacyPolicy = false;
    if (privacyKeywords.some(kw => titleLower.includes(kw) || urlLower.includes(kw.replace(/\s+/g, '-')) || urlLower.includes(kw.replace(/\s+/g, '')))) {
        isLikelyPrivacyPolicy = true;
    }
    
    if (!isLikelyPrivacyPolicy) {
        const headings = Array.from(document.querySelectorAll('h1, h2, h3')).map(h => (h.innerText || '').toLowerCase());
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

// Find a link to the site's privacy policy from the DOM
function findPrivacyPolicyLink() {
    const links = Array.from(document.querySelectorAll('a'));
    
    // Pass 1: exact or high-confidence anchor text
    for (const a of links) {
        const text = (a.innerText || "").toLowerCase().trim();
        const href = (a.href || "").trim();
        if (!href || href.startsWith('javascript:') || href === '#' || href.startsWith('mailto:')) continue;
        if (text === "privacy policy" || text === "privacy notice" || text === "privacy statement") {
            return { href: a.href, text: a.innerText.trim() };
        }
    }
    
    // Pass 2: anchor text contains privacy
    for (const a of links) {
        const text = (a.innerText || "").toLowerCase().trim();
        const href = (a.href || "").trim();
        if (!href || href.startsWith('javascript:') || href === '#' || href.startsWith('mailto:')) continue;
        if (text.includes("privacy policy") || text.includes("privacy notice") || text.includes("data protection policy")) {
            return { href: a.href, text: a.innerText.trim() };
        }
    }
    
    // Pass 3: general 'privacy' link
    for (const a of links) {
        const text = (a.innerText || "").toLowerCase().trim();
        const href = (a.href || "").trim();
        if (!href || href.startsWith('javascript:') || href === '#' || href.startsWith('mailto:')) continue;
        if (text === "privacy" || text.includes("privacy")) {
            return { href: a.href, text: a.innerText.trim() };
        }
    }

    // Pass 4: URL structure
    for (const a of links) {
        const href = (a.href || "").toLowerCase();
        if (!href || href.startsWith('javascript:') || href === '#') continue;
        if (href.includes("/privacy-policy") || href.includes("/privacy") || href.includes("privacy.html") || href.includes("privacypolicy")) {
            return { href: a.href, text: (a.innerText || "").trim() || "Privacy Policy" };
        }
    }

    return null;
}

// Helper to send messages to background service worker safely
function sendBgMessage(action, payload = {}) {
    return new Promise((resolve) => {
        try {
            chrome.runtime.sendMessage({ action, ...payload }, (res) => {
                if (chrome.runtime.lastError) {
                    resolve({ ok: false, error: chrome.runtime.lastError.message });
                } else {
                    resolve(res || { ok: false, error: "No response from background worker" });
                }
            });
        } catch (e) {
            resolve({ ok: false, error: e.message });
        }
    });
}

// Listen for commands from popup
chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
    if (request.action === "extract_text") {
        const basicData = extractPageText();
        const privacyLink = findPrivacyPolicyLink();
        sendResponse({
            text: basicData.text,
            url: window.location.href,
            title: basicData.title,
            truncated: basicData.truncated,
            isLikelyPrivacyPolicy: basicData.isLikelyPrivacyPolicy,
            policyLink: privacyLink
        });
        return false;
    }
});

/* =========================================
   ACTIVE LOGIN SHIELD
========================================= */

async function initActiveLoginShield() {
    if (document.contentType !== "text/html") return;

    const urlObj = new URL(window.location.href);
    const path = urlObj.pathname.toLowerCase();
    const host = urlObj.hostname.toLowerCase();
    
    // Ignore search engine result pages
    if (host.includes("google.") && path.includes("/search")) return;
    if (host.includes("bing.com") || host.includes("yahoo.com") || path.includes("/search")) return;

    // Check if on a login page
    const passwordField = document.querySelector('input[type="password"]');
    const isAuthPath = path.match(/\/(login|signin|auth|oauth|account\/login|wp-login)/) !== null;
    
    if (!passwordField && !isAuthPath) return;

    // Check cache in chrome.storage.local
    try {
        const cacheResult = await new Promise(resolve => chrome.storage.local.get(['cachedAnalysis'], resolve));
        if (cacheResult.cachedAnalysis && cacheResult.cachedAnalysis.url === window.location.hostname) {
            const timeElapsed = Date.now() - cacheResult.cachedAnalysis.timestamp;
            if (timeElapsed < 24 * 60 * 60 * 1000) {
                injectShieldUI();
                showVerdict(cacheResult.cachedAnalysis.data, cacheResult.cachedAnalysis.newEntities || []);
                return;
            }
        }
    } catch (e) {}

    // Automated Policy Discovery
    const privacyLink = findPrivacyPolicyLink();
    if (!privacyLink) {
        injectShieldUI();
        updateShieldUI("⚠️ No Privacy Policy link discovered on this login page.", "orange");
        return;
    }

    injectShieldUI();
    updateShieldUI("Crawling Privacy Policy...", "blue");

    try {
        // Fetch background policy via background service worker to prevent CSP/Mixed Content
        const proxyRes = await sendBgMessage("bg_proxy_fetch", { url: privacyLink.href });
        if (!proxyRes.ok || !proxyRes.data || !proxyRes.data.html) {
            updateShieldUI("🛡️ Background scan blocked by site protection. Open policy page to scan directly.", "orange");
            return;
        }

        const parser = new DOMParser();
        const doc = parser.parseFromString(proxyRes.data.html, "text/html");
        const elementsToRemove = doc.querySelectorAll('script, style, nav, footer, header, noscript, iframe');
        elementsToRemove.forEach(el => el.remove());

        const fullPolicyText = doc.body.innerText.replace(/\s+/g, ' ').trim();
        const policyText = fullPolicyText.substring(0, MAX_POLICY_CHARS);
        const policyTruncated = fullPolicyText.length > MAX_POLICY_CHARS;

        updateShieldUI("Analyzing risks via ClauseGuard engine...", "blue");

        const analyzeRes = await sendBgMessage("bg_analyze_policy", {
            payload: {
                text: policyText,
                url: window.location.href,
                title: document.title,
                truncated: policyTruncated
            }
        });

        if (!analyzeRes.ok || !analyzeRes.data) throw new Error("Analysis failed");
        const analysisData = analyzeRes.data;

        // Check against portfolio
        updateShieldUI("Comparing with portfolio...", "blue");
        let newEntities = [];
        const marginalRes = await sendBgMessage("bg_marginal_risk", { payload: analysisData });
        if (marginalRes.ok && marginalRes.data) {
            newEntities = marginalRes.data.newly_introduced_entities || [];
        }

        // Cache result for popup and reloads
        chrome.storage.local.set({
            cachedAnalysis: {
                url: window.location.hostname,
                timestamp: Date.now(),
                data: analysisData,
                newEntities: newEntities
            }
        });

        showVerdict(analysisData, newEntities);
    } catch (e) {
        updateShieldUI("⚠️ Could not complete background scan of privacy policy.", "orange");
    }
}

function showVerdict(analysisData, newEntities) {
    const score = Number(analysisData.risk_score ?? analysisData.risk ?? 0);
    const category = analysisData.risk_category || "Inconclusive";
    const coverage = analysisData.coverage || {};

    let style = "orange";
    let icon = "⚠️";
    if (category === "Low") { style = "green"; icon = "✓"; }
    else if (category === "Moderate") { style = "orange"; icon = "⚠️"; }
    else if (category === "High" || category === "Very High") { style = "red"; icon = "🚨"; }
    else { style = "orange"; icon = "❔"; }

    if (newEntities.length > 0 && style === "green") style = "orange";

    let note = "";
    if (coverage.status === "partial") note += " (Partial policy analysed)";
    if (coverage.status === "insufficient") note += " (Insufficient text)";

    let newText = "";
    if (newEntities.length > 0) {
        newText = ` | New types: ${newEntities.slice(0, 3).join(', ')}`;
    }

    updateShieldUI(
        `${icon} Privacy Risk: ${category} (${score.toFixed(0)}/100)${note}${newText}`,
        style
    );
}

let shieldBanner = null;

function injectShieldUI() {
    if (shieldBanner) return;
    const passwordField = document.querySelector('input[type="password"]');
    
    shieldBanner = document.createElement("div");
    shieldBanner.style.display = "flex";
    shieldBanner.style.alignItems = "center";
    shieldBanner.style.justifyContent = "center";
    shieldBanner.style.backgroundColor = "#f8fafc";
    shieldBanner.style.color = "#334155";
    shieldBanner.style.padding = "10px 14px";
    shieldBanner.style.borderRadius = "8px";
    shieldBanner.style.fontFamily = "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif";
    shieldBanner.style.fontWeight = "600";
    shieldBanner.style.boxShadow = "0 4px 6px -1px rgba(0, 0, 0, 0.1)";
    shieldBanner.style.border = "1px solid #e2e8f0";
    shieldBanner.style.fontSize = "13px";
    shieldBanner.style.marginTop = "8px";
    shieldBanner.style.marginBottom = "12px";
    shieldBanner.style.zIndex = "999999";
    shieldBanner.style.width = "100%";
    shieldBanner.style.boxSizing = "border-box";
    shieldBanner.innerHTML = `<span style="margin-right: 8px;">🛡️</span> <span>ClauseGuard: Detecting Login Risks...</span>`;
    
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
    shieldBanner.textContent = "";
    const shieldIcon = document.createElement("span");
    shieldIcon.style.marginRight = "8px";
    shieldIcon.textContent = "🛡️";
    const shieldText = document.createElement("span");
    shieldText.textContent = text;
    shieldBanner.appendChild(shieldIcon);
    shieldBanner.appendChild(shieldText);
    
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

// Run shield on page load
setTimeout(initActiveLoginShield, 1000);
