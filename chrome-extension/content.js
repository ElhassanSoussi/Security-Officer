// NYC Compliance Architect - Content Script

console.log("NYC Compliance Architect: Active on this page.");

// 1. Inject Sidebar
const sidebar = document.createElement("div");
sidebar.id = "nyc-compliance-sidebar";
sidebar.className = "hidden"; // Start hidden? Or visible? User asked to "Injects a ... sidebar".

// Toggle Button (Floating Action Button)
const toggleBtn = document.createElement("button");
toggleBtn.innerText = "🛡️";
toggleBtn.style.cssText = `
  position: fixed;
  bottom: 20px;
  right: 20px;
  width: 50px;
  height: 50px;
  border-radius: 25px;
  background-color: #1e293b;
  color: white;
  border: none;
  font-size: 24px;
  cursor: pointer;
  z-index: 1000000;
  box-shadow: 0 4px 6px rgba(0,0,0,0.1);
  display: flex;
  align-items: center;
  justify-content: center;
`;
toggleBtn.onclick = () => {
    sidebar.classList.toggle("hidden");
};
document.body.appendChild(toggleBtn);

sidebar.innerHTML = `
  <div class="nyc-header">
    <div class="nyc-title">NYC Compliance Architect</div>
    <button id="nyc-close-btn" style="background:none;border:none;color:white;cursor:pointer;">✕</button>
  </div>
  <div class="nyc-body">
    <button id="nyc-scan-btn" class="nyc-btn-primary">
      🚀 Scan This Page
    </button>
    <div id="nyc-results"></div>
  </div>
`;

document.body.appendChild(sidebar);

// Close Button Logic
sidebar.querySelector("#nyc-close-btn").onclick = () => {
    sidebar.classList.add("hidden");
};

// 2. Scan Logic
const scanBtn = sidebar.querySelector("#nyc-scan-btn");
const resultsContainer = sidebar.querySelector("#nyc-results");

scanBtn.onclick = async () => {
    scanBtn.innerText = "Scanning...";
    scanBtn.disabled = true;
    resultsContainer.innerHTML = '<div style="text-align:center; padding:1rem;">Analysing form fields...</div>';

    // Scrape Data
    const fields = [];
    const labels = document.querySelectorAll("label");

    // Heuristic: Find inputs associated with labels
    labels.forEach((label, index) => {
        const labelText = label.innerText.trim();
        if (!labelText) return;

        let inputId = label.getAttribute("for");
        let input = inputId ? document.getElementById(inputId) : label.querySelector("input, textarea, select");

        if (!input) {
            // Try next sibling
            let next = label.nextElementSibling;
            if (next && (next.tagName === "INPUT" || next.tagName === "TEXTAREA" || next.tagName === "SELECT")) {
                input = next;
            }
        }

        if (input) { // Only keep if we found an input target
            fields.push({
                id: input.id || `field_${index}`,
                label: labelText,
                type: input.tagName.toLowerCase()
            });
        }
    });

    console.log("Scraped Fields:", fields);

    if (fields.length === 0) {
        resultsContainer.innerHTML = '<div style="color:red; text-align:center;">No form fields found.</div>';
        scanBtn.innerText = "🚀 Scan This Page";
        scanBtn.disabled = false;
        return;
    }

    // Send to Background Logic
    chrome.runtime.sendMessage({ action: "analyze_page", data: fields }, (response) => {
        scanBtn.innerText = "🚀 Scan This Page";
        scanBtn.disabled = false;

        if (response && response.status === "success") {
            renderResults(response.results);
        } else {
            resultsContainer.innerHTML = `<div style="color:red;">Error: ${response ? response.message : "Unknown error"}</div>`;
        }
    });
};

function renderResults(results) {
    resultsContainer.innerHTML = "";

    results.forEach(item => {
        const card = document.createElement("div");
        card.className = "nyc-card";

        const answerText = item.answer || "No suggestions found.";

        card.innerHTML = `
            <span class="nyc-label">${item.label}</span>
            <div class="nyc-answer">${answerText}</div>
            <button class="nyc-copy-btn" title="Copy to clipboard">
                📋 Copy
            </button>
        `;

        // Copy Logic
        const copyBtn = card.querySelector(".nyc-copy-btn");
        copyBtn.onclick = () => {
            navigator.clipboard.writeText(answerText);
            copyBtn.innerText = "✅ Copied!";
            setTimeout(() => copyBtn.innerHTML = "📋 Copy", 2000);
        };

        resultsContainer.appendChild(card);
    });
}
