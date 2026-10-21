// ClauseGuard Background Service Worker (Manifest V3)
// Handles network calls for content scripts to prevent Mixed Content & CSP restrictions

const BACKEND_URL = "http://127.0.0.1:5000";

chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
    if (request.action === "bg_proxy_fetch") {
        fetch(`${BACKEND_URL}/api/proxy-fetch`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ url: request.url })
        })
        .then(async (res) => {
            const data = await res.json().catch(() => ({}));
            sendResponse({ ok: res.ok, status: res.status, data });
        })
        .catch((err) => {
            sendResponse({ ok: false, error: err.message });
        });
        return true; // Keep channel open for async response
    }

    if (request.action === "bg_analyze_policy") {
        fetch(`${BACKEND_URL}/api/analyze-policy`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(request.payload)
        })
        .then(async (res) => {
            const data = await res.json().catch(() => ({}));
            sendResponse({ ok: res.ok, status: res.status, data });
        })
        .catch((err) => {
            sendResponse({ ok: false, error: err.message });
        });
        return true;
    }

    if (request.action === "bg_marginal_risk") {
        fetch(`${BACKEND_URL}/api/marginal-risk`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(request.payload)
        })
        .then(async (res) => {
            const data = await res.json().catch(() => ({}));
            sendResponse({ ok: res.ok, status: res.status, data });
        })
        .catch((err) => {
            sendResponse({ ok: false, error: err.message });
        });
        return true;
    }

    if (request.action === "bg_service_status") {
        fetch(`${BACKEND_URL}/api/service-status?name=${encodeURIComponent(request.name)}`)
        .then(async (res) => {
            const data = await res.json().catch(() => ({}));
            sendResponse({ ok: res.ok, status: res.status, data });
        })
        .catch((err) => {
            sendResponse({ ok: false, error: err.message });
        });
        return true;
    }
});

