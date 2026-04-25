(function () {
    const configNode = document.getElementById("coding-exercise-config");
    if (!configNode) return;

    const config = JSON.parse(configNode.textContent);
    const editorHost = document.getElementById("coding-editor");
    const languageSelect = document.getElementById("coding-language-select");
    const customInput = document.getElementById("coding-custom-input");
    const runButton = document.getElementById("coding-run-btn");
    const submitButton = document.getElementById("coding-submit-btn");
    const resultNode = document.getElementById("coding-result");
    const statusNode = document.getElementById("coding-status");
    const detailNode = document.getElementById("coding-result-detail");
    const sampleNode = document.getElementById("coding-samples");
    let editorApi = null;

    const storageKey = (language) => `cpwiki:${config.articleId}:${language || "default"}`;

    const setBusy = (isBusy) => {
        [runButton, submitButton, languageSelect].forEach((element) => {
            if (element) element.disabled = isBusy;
        });
    };

    const readStoredSource = (language) => {
        const saved = window.localStorage.getItem(storageKey(language));
        if (saved) return saved;
        return config.starterCodeMap[language] || "";
    };

    const writeStoredSource = (language, source) => {
        window.localStorage.setItem(storageKey(language), source);
    };

    const getEditorValue = () => {
        if (editorApi && typeof editorApi.getValue === "function") return editorApi.getValue();
        return "";
    };

    const setEditorValue = (language, source) => {
        if (editorApi && typeof editorApi.setValue === "function") {
            editorApi.setValue(source);
            if (window.monaco && editorApi.getModel) {
                window.monaco.editor.setModelLanguage(
                    editorApi.getModel(),
                    config.monacoMap[language] || "plaintext"
                );
            }
        }
    };

    const renderResult = (data, actionLabel) => {
        resultNode.classList.remove("d-none");
        resultNode.classList.add("fade-in");
        
        const statusClass = data.status === "accepted" ? "text-success" : (data.status === "running" ? "text-primary" : "text-danger");
        const statusIcon = data.status === "accepted" ? '<i class="fa-solid fa-circle-check me-2"></i>' : (data.status === "running" ? '<i class="fa-solid fa-spinner fa-spin me-2"></i>' : '<i class="fa-solid fa-circle-xmark me-2"></i>');

        statusNode.innerHTML = `<div class="d-flex align-items-center ${statusClass}">${statusIcon}<span>${data.message || data.status_label || data.status}</span></div>`;

        const parts = [];
        if (data.compile_output && data.status === "compile_error") {
            parts.push(`<div class="mb-3"><strong>Lỗi biên dịch:</strong><pre class="bg-dark text-light p-3 rounded-3 mt-2 small shadow-inner">${escapeHtml(data.compile_output)}</pre></div>`);
        }
        
        if (Array.isArray(data.results) && data.results.length) {
            const rows = data.results.map((item) => {
                const itemStatusClass = item.status === "accepted" ? "badge bg-success-soft text-success" : "badge bg-danger-soft text-danger";
                return `
                <tr>
                    <td class="fw-medium">${escapeHtml(item.case_name)}</td>
                    <td><span class="${itemStatusClass}">${escapeHtml(item.status_label || item.status)}</span></td>
                    <td class="text-muted small">${item.runtime_ms}ms</td>
                    <td><pre class="mb-0 bg-light p-1 rounded small">${escapeHtml(item.actual_preview || "")}</pre></td>
                    <td><pre class="mb-0 bg-light p-1 rounded small">${escapeHtml(item.expected_preview || "")}</pre></td>
                </tr>
                `;
            }).join("");
            
            parts.push(`
                <div class="table-responsive">
                    <table class="table table-hover align-middle mt-2 border-top">
                        <thead class="table-light"><tr><th>Test case</th><th>Trạng thái</th><th>Thời gian</th><th>Kết quả</th><th>Kỳ vọng</th></tr></thead>
                        <tbody>${rows}</tbody>
                    </table>
                </div>
            `);
        } else if (data.stdout_preview || data.stderr_preview) {
            if (data.stdout_preview) {
                parts.push(`<div class="mb-2"><strong>stdout:</strong><pre class="bg-light p-2 rounded mt-1 small">${escapeHtml(data.stdout_preview)}</pre></div>`);
            }
            if (data.stderr_preview && data.status !== "compile_error") {
                parts.push(`<div class="mb-2"><strong>stderr:</strong><pre class="bg-light p-2 rounded mt-1 small text-danger">${escapeHtml(data.stderr_preview)}</pre></div>`);
            }
        }

        detailNode.innerHTML = parts.join("");
        resultNode.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    };

    const escapeHtml = (value) => {
        return (value || "")
            .replaceAll("&", "&amp;")
            .replaceAll("<", "&lt;")
            .replaceAll(">", "&gt;");
    };

    const requestJudge = async (url, actionLabel, button) => {
        const language = languageSelect.value;
        const source = getEditorValue();
        writeStoredSource(language, source);
        setBusy(true, button);
        try {
            const response = await fetch(url, {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                    "X-CSRFToken": document.querySelector("[name=csrfmiddlewaretoken]").value,
                },
                body: JSON.stringify({
                    language: language,
                    source_code: source,
                    custom_input: customInput ? customInput.value : "",
                }),
            });
            const data = await response.json();
            if (!data.success) throw new Error(data.message || "Không thể chấm bài.");
            renderResult(data, actionLabel);
        } catch (error) {
            renderResult(
                {
                    status: "error",
                    status_label: "Error",
                    message: error.message || "Có lỗi xảy ra.",
                    stderr_preview: error.message || "Có lỗi xảy ra.",
                    results: [],
                },
                actionLabel
            );
        } finally {
            setBusy(false, button);
        }
    };

    const updateSamples = () => {
        if (!sampleNode) return;
        const rows = config.samples.map((item) => `
            <div class="card bg-light border-0 mb-3">
                <div class="card-body">
                    <div class="fw-semibold mb-2">${escapeHtml(item.name)}</div>
                    <div class="small text-secondary mb-2">input</div>
                    <pre class="mb-3">${escapeHtml(item.input)}</pre>
                    <div class="small text-secondary mb-2">output</div>
                    <pre class="mb-0">${escapeHtml(item.output)}</pre>
                </div>
            </div>
        `).join("");
        sampleNode.innerHTML = rows || '<div class="empty-state centered">Chưa có sample test.</div>';
    };

    const loadMonaco = () => {
        if (!editorHost || !window.require) return;
        window.require.config({
            paths: {
                vs: "https://cdn.jsdelivr.net/npm/monaco-editor@0.52.2/min/vs",
            },
        });
        window.require(["vs/editor/editor.main"], () => {
            const initialLanguage = languageSelect.value;
            editorApi = window.monaco.editor.create(editorHost, {
                value: readStoredSource(initialLanguage),
                language: config.monacoMap[initialLanguage] || "plaintext",
                automaticLayout: true,
                minimap: { enabled: false },
                scrollBeyondLastLine: false,
                fontSize: 14,
                theme: "vs",
            });
            editorApi.onDidChangeModelContent(() => {
                writeStoredSource(languageSelect.value, editorApi.getValue());
            });
        });
    };

    if (languageSelect) {
        languageSelect.addEventListener("change", () => {
            const language = languageSelect.value;
            setEditorValue(language, readStoredSource(language));
        });
    }
    if (runButton) {
        runButton.addEventListener("click", function() { requestJudge(config.runUrl, "run", this); });
    }
    if (submitButton) {
        submitButton.addEventListener("click", function() { requestJudge(config.submitUrl, "submit", this); });
    }

    updateSamples();
    loadMonaco();
})();
