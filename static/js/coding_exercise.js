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
        statusNode.textContent = `${actionLabel}: ${data.status}`;

        const parts = [];
        if (data.compile_output) {
            parts.push(`<div><strong>compile:</strong><pre class="mb-0">${escapeHtml(data.compile_output)}</pre></div>`);
        }
        if (data.stdout_preview) {
            parts.push(`<div><strong>stdout:</strong><pre class="mb-0">${escapeHtml(data.stdout_preview)}</pre></div>`);
        }
        if (data.stderr_preview) {
            parts.push(`<div><strong>stderr:</strong><pre class="mb-0">${escapeHtml(data.stderr_preview)}</pre></div>`);
        }
        if (typeof data.passed_tests !== "undefined") {
            parts.push(`<div><strong>tests:</strong> ${data.passed_tests} / ${data.total_tests}</div>`);
        }
        if (Array.isArray(data.results) && data.results.length) {
            const rows = data.results.map((item) => `
                <tr>
                    <td>${escapeHtml(item.case_name)}</td>
                    <td>${escapeHtml(item.status)}</td>
                    <td><pre class="mb-0">${escapeHtml(item.actual_preview || "")}</pre></td>
                    <td><pre class="mb-0">${escapeHtml(item.expected_preview || "")}</pre></td>
                </tr>
            `).join("");
            parts.push(`
                <div class="table-responsive">
                    <table class="table table-sm align-middle mt-3">
                        <thead><tr><th>case</th><th>status</th><th>actual</th><th>expected</th></tr></thead>
                        <tbody>${rows}</tbody>
                    </table>
                </div>
            `);
        }

        detailNode.innerHTML = parts.join("");
    };

    const escapeHtml = (value) => {
        return (value || "")
            .replaceAll("&", "&amp;")
            .replaceAll("<", "&lt;")
            .replaceAll(">", "&gt;");
    };

    const requestJudge = async (url, actionLabel) => {
        const language = languageSelect.value;
        const source = getEditorValue();
        writeStoredSource(language, source);
        setBusy(true);
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
                    stderr_preview: error.message || "Có lỗi xảy ra.",
                    results: [],
                },
                actionLabel
            );
        } finally {
            setBusy(false);
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
        runButton.addEventListener("click", () => requestJudge(config.runUrl, "run"));
    }
    if (submitButton) {
        submitButton.addEventListener("click", () => requestJudge(config.submitUrl, "submit"));
    }

    updateSamples();
    loadMonaco();
})();
