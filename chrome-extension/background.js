chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
    if (request.action === "analyze_page") {
        // 1. Prepare Data
        const payload = {
            org_id: "demo-org", // Hardcoded for MVP or ideally configurable
            project_id: "chrome-ext-session",
            answers: request.data.map(field => ({
                sheet_name: "PASSPort_Web", // Virtual sheet name
                cell_coordinate: field.id,   // Use ID as coordinate
                question: field.label,
                ai_answer: "",
                final_answer: "",
                confidence: "LOW",
                sources: [],
                is_verified: false,
                edited_by_user: false
            }))
        };

        // 2. Call API
        // Note: The backend endpoint /analyze-excel expects a FILE.
        // We need to use /answer for individual questions or create a new endpoint /analyze-json.
        // For MVP, sticking to the user prompt: "send them to the /api/v1/answer endpoint".
        // Wait, /api/v1/answer handles a SINGLE question.
        // If we have 20 inputs, we don't want 20 sequential calls.
        // Let's assume we loop through them here or the USER prompt implies a bulk endpoint.
        // "send them to the /api/v1/answer endpoint" -> implies singular or we parallelize.

        // Let's implement a parallel loop here for the MVP.

        const analyzeField = async (field) => {
            try {
                // Configurable API base — defaults to production, override for local dev
                const API_BASE = "https://api.nyccompliancearchitect.com/api/v1";
                const res = await fetch(`${API_BASE}/answer`, {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({
                        query: field.label,
                        org_id: "demo-org",
                        project_id: "chrome-ext"
                    })
                });
                const data = await res.json();
                return {
                    id: field.id,
                    label: field.label,
                    answer: data.data.answer || "No answer found",
                    sources: data.data.sources
                };
            } catch (e) {
                console.error(e);
                return { id: field.id, label: field.label, answer: "Error", sources: [] };
            }
        };

        Promise.all(request.data.map(analyzeField))
            .then(results => sendResponse({ status: "success", results: results }))
            .catch(err => sendResponse({ status: "error", message: err.toString() }));

        return true; // Keep channel open for async response
    }
});
