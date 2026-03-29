function renderMath(container) {
    if (!container || typeof renderMathInElement !== "function") {
        return;
    }

    renderMathInElement(container, {
        delimiters: [
            { left: "$$", right: "$$", display: true },
            { left: "$", right: "$", display: false },
        ],
        throwOnError: false,
    });
}

function renderAllMath() {
    document.querySelectorAll(".markdown-body, .martor-preview").forEach((element) => {
        renderMath(element);
    });
}

function initMartorCleanup() {
    document.querySelectorAll(".main-martor").forEach((wrapper) => {
        const textarea = wrapper.querySelector("textarea.martor");
        if (textarea) {
            textarea.classList.add("martor-native-textarea");
        }

        const preview = wrapper.querySelector(".martor-preview");
        if (!preview) {
            return;
        }

        const observer = new MutationObserver(() => {
            renderMath(preview);
        });
        observer.observe(preview, { childList: true, subtree: true, characterData: true });
    });
}

function slugify(value) {
    return value
        .toLowerCase()
        .normalize("NFD")
        .replace(/[\u0300-\u036f]/g, "")
        .replace(/[^a-z0-9]+/g, "-")
        .replace(/^-+|-+$/g, "")
        .replace(/-{2,}/g, "-");
}

function initArticleSlugSync() {
    const titleInput = document.querySelector("#id_title");
    const slugInput = document.querySelector("#id_slug");

    if (!titleInput || !slugInput) {
        return;
    }

    let touched = slugInput.value.trim().length > 0;

    slugInput.addEventListener("input", () => {
        touched = slugInput.value.trim().length > 0;
    });

    titleInput.addEventListener("input", () => {
        if (touched) {
            return;
        }
        slugInput.value = slugify(titleInput.value);
    });
}

document.addEventListener("DOMContentLoaded", () => {
    initMartorCleanup();
    initArticleSlugSync();
    renderAllMath();

    document.addEventListener("shown.bs.tab", (event) => {
        const targetSelector = event.target?.getAttribute("data-bs-target");
        if (!targetSelector) {
            return;
        }
        const target = document.querySelector(targetSelector);
        if (target) {
            renderMath(target);
        }
    });

    initAjaxVoteForms();
    initWebsocket();
    initCopyLinkButtons();
    initSavedArticles();
    initFocusModeToggle();
    initReadingProgress();
    initKeyboardShortcuts();
    initBackToTop();
    renderSavedArticles();
});

function getCookie(name) {
    const value = `; ${document.cookie}`;
    const parts = value.split(`; ${name}=`);
    if (parts.length === 2) return parts.pop().split(';').shift();
    return null;
}

function getSavedArticles() {
    try {
        const raw = JSON.parse(window.localStorage.getItem("savedArticles") || "[]");
        return Array.isArray(raw) ? raw : [];
    } catch {
        return [];
    }
}

function setSavedArticles(items) {
    window.localStorage.setItem("savedArticles", JSON.stringify(items));
    renderSavedArticles();
}

function renderSavedArticles() {
    const items = getSavedArticles();
    const count = document.getElementById("saved-articles-count");
    const list = document.getElementById("saved-articles-list");

    if (count) {
        count.textContent = items.length;
    }

    if (!list) {
        return;
    }

    if (!items.length) {
        list.innerHTML = '<div class="empty-state centered">Bạn chưa lưu bài viết nào.</div>';
        return;
    }

    list.innerHTML = items.map((item) => `
        <div class="saved-article-item">
            <div>
                <a class="saved-article-item__title" href="${item.url}">${item.title}</a>
                <div class="saved-article-item__meta">${item.savedAtLabel || "Đã lưu gần đây"}</div>
            </div>
            <div class="stack-item__actions">
                <a class="btn btn-sm btn-outline-primary px-3" href="${item.url}">Mở</a>
                <button class="btn btn-sm btn-outline-secondary px-3 saved-remove-btn" type="button" data-key="${item.key}">Bỏ lưu</button>
            </div>
        </div>
    `).join("");

    list.querySelectorAll(".saved-remove-btn").forEach((button) => {
        button.addEventListener("click", () => {
            const nextItems = getSavedArticles().filter((item) => item.key !== button.dataset.key);
            setSavedArticles(nextItems);
        });
    });
}

function initAjaxVoteForms() {
    document.querySelectorAll('.ajax-vote-form').forEach((form) => {
        form.addEventListener('submit', async (event) => {
            event.preventDefault();
            const url = form.getAttribute('action');
            const formData = new FormData(form);
            const csrfToken = getCookie('csrftoken');
            try {
                const response = await fetch(url, {
                    method: 'POST',
                    headers: {
                        'X-Requested-With': 'XMLHttpRequest',
                        'X-CSRFToken': csrfToken || '',
                    },
                    body: formData,
                });
                if (!response.ok) {
                    throw new Error('Network response was not ok');
                }
                const data = await response.json();
                if (!data.success) {
                    throw new Error(data.message || 'Vote failed');
                }

                if (data.article_vote_score !== undefined) {
                    const el = document.getElementById('article-score');
                    if (el) {
                        el.textContent = data.article_vote_score;
                        el.title = `Ủng hộ: ${data.article_upvotes} | Giảm điểm: ${data.article_downvotes}`;
                    }
                }

                if (data.comment_vote_score !== undefined) {
                    const commentPk = url.split('/').slice(-2, -1)[0];
                    const scoreElem = document.getElementById(`comment-${commentPk}-score`);
                    if (scoreElem) {
                        scoreElem.textContent = data.comment_vote_score;
                        scoreElem.title = `Ủng hộ: ${data.comment_upvotes} | Giảm điểm: ${data.comment_downvotes}`;
                    }
                }

                if (data.target_vote_score !== undefined) {
                    const scoreElem = document.getElementById(`user-${data.target_user_pk}-score`);
                    if (scoreElem) {
                        scoreElem.textContent = data.target_vote_score;
                    }
                }

                Swal.fire({
                    icon: 'success',
                    title: 'Cập nhật thành công',
                    text: data.message || 'Cập nhật vote thành công.',
                    timer: 1200,
                    showConfirmButton: false,
                });
            } catch (error) {
                Swal.fire({
                    icon: 'error',
                    title: 'Lỗi',
                    text: error.message || 'Không thể vote giờ.',
                });
            }
        });
    });
}

function initWebsocket() {
    // Không ép WebSocket nếu không cần; tránh lỗi console trên trang login.
    if (!document.querySelector('.article-content') && !document.querySelector('.comment-list')) {
        return;
    }

    const scheme = window.location.protocol === 'https:' ? 'wss' : 'ws';
    const wsUrl = `${scheme}://${window.location.host}/ws/votes/`;
    let socket;
    try {
        socket = new WebSocket(wsUrl);
        socket.onerror = (event) => {
            console.warn('WebSocket error:', event);
        };
        socket.onclose = (event) => {
            console.log('WebSocket closed', event.code, event.reason);
        };
        socket.onmessage = (event) => {
            const data = JSON.parse(event.data);
            if (data.type !== 'vote_update') return;
            const payload = data.payload;
            if (payload.article_vote_score !== undefined) {
                const scoreEl = document.getElementById('article-score');
                if (scoreEl) {
                    scoreEl.textContent = payload.article_vote_score;
                    scoreEl.title = `Ủng hộ: ${payload.article_upvotes} | Giảm điểm: ${payload.article_downvotes}`;
                }
            }
            if (payload.comment_vote_score !== undefined) {
                const commentPk = payload.comment_pk;
                const scoreElem = document.getElementById(`comment-${commentPk}-score`);
                if (scoreElem) {
                    scoreElem.textContent = payload.comment_vote_score;
                    scoreElem.title = `Ủng hộ: ${payload.comment_upvotes} | Giảm điểm: ${payload.comment_downvotes}`;
                }
            }
        };
        socket.onopen = () => {
            console.log('WebSocket connected', wsUrl);
        };
        socket.onclose = () => {
            console.log('WebSocket closed');
        };

    } catch (err) {
        console.warn('WebSocket connect failed:', err);
    }
}

function initCopyLinkButtons() {
    document.querySelectorAll(".article-copy-link").forEach((button) => {
        button.addEventListener("click", async () => {
            const url = button.dataset.copyUrl || window.location.href;
            try {
                if (navigator.clipboard?.writeText) {
                    await navigator.clipboard.writeText(url);
                } else {
                    const temp = document.createElement("input");
                    temp.value = url;
                    document.body.appendChild(temp);
                    temp.select();
                    document.execCommand("copy");
                    temp.remove();
                }

                Swal.fire({
                    icon: "success",
                    title: "Đã sao chép liên kết",
                    text: "Bạn có thể chia sẻ nội dung này ngay bây giờ.",
                    timer: 1200,
                    showConfirmButton: false,
                });
            } catch (error) {
                Swal.fire({
                    icon: "error",
                    title: "Không thể sao chép",
                    text: "Hãy thử sao chép liên kết từ thanh địa chỉ trình duyệt.",
                });
            }
        });
    });
}

function initSavedArticles() {
    const button = document.querySelector(".article-save-toggle");
    const shell = document.getElementById("article-shell");
    if (!button || !shell) {
        return;
    }

    const key = button.dataset.articleKey;
    const title = document.querySelector("h1")?.textContent?.trim() || "Bài viết";
    const url = window.location.href;
    const savedAtLabel = new Date().toLocaleString("vi-VN");

    const sync = () => {
        const items = getSavedArticles();
        const isSaved = items.some((item) => item.key === key);
        shell.classList.toggle("is-saved", isSaved);
        button.textContent = isSaved ? "Đã lưu bài viết" : "Lưu bài viết";
        button.classList.toggle("btn-soft", isSaved);
    };

    sync();
    button.addEventListener("click", () => {
        const items = getSavedArticles();
        const exists = items.some((item) => item.key === key);
        if (exists) {
            setSavedArticles(items.filter((item) => item.key !== key));
        } else {
            setSavedArticles([
                { key, title, url, savedAtLabel },
                ...items.filter((item) => item.key !== key),
            ]);
        }
        sync();
    });
}

function initFocusModeToggle() {
    const button = document.querySelector(".article-focus-toggle");
    if (!button) {
        return;
    }

    button.addEventListener("click", () => {
        const enabled = document.body.classList.toggle("is-focus-mode");
        button.textContent = enabled ? "Thoát chế độ tập trung" : "Chế độ tập trung";
        button.classList.toggle("btn-soft", enabled);
    });
}

function initKeyboardShortcuts() {
    document.addEventListener("keydown", (event) => {
        const target = event.target;
        const isTypingTarget = target && (
            target.tagName === "INPUT" ||
            target.tagName === "TEXTAREA" ||
            target.isContentEditable
        );

        if (event.key === "Escape" && document.body.classList.contains("is-focus-mode")) {
            document.body.classList.remove("is-focus-mode");
            const focusButton = document.querySelector(".article-focus-toggle");
            if (focusButton) {
                focusButton.textContent = "Chế độ tập trung";
                focusButton.classList.remove("btn-soft");
            }
            return;
        }

        if (isTypingTarget) {
            return;
        }

        if (event.key === "/") {
            const searchInput = document.querySelector("#id_q");
            if (searchInput) {
                event.preventDefault();
                searchInput.focus();
                searchInput.select?.();
            }
        }

        if (event.key.toLowerCase() === "s") {
            const saveButton = document.querySelector(".article-save-toggle");
            if (saveButton) {
                event.preventDefault();
                saveButton.click();
            }
        }

        if (event.key.toLowerCase() === "f") {
            const focusButton = document.querySelector(".article-focus-toggle");
            if (focusButton) {
                event.preventDefault();
                focusButton.click();
            }
        }
    });
}

function initReadingProgress() {
    const article = document.querySelector(".article-content");
    const bar = document.getElementById("reading-progress-bar");
    if (!article || !bar) {
        return;
    }

    const updateProgress = () => {
        const rect = article.getBoundingClientRect();
        const articleTop = window.scrollY + rect.top;
        const articleHeight = article.offsetHeight;
        const viewportHeight = window.innerHeight;
        const total = Math.max(articleHeight - viewportHeight, 1);
        const current = Math.min(Math.max(window.scrollY - articleTop, 0), total);
        const progress = current / total;
        bar.style.transform = `scaleX(${progress})`;
    };

    updateProgress();
    window.addEventListener("scroll", updateProgress, { passive: true });
    window.addEventListener("resize", updateProgress);
}

function initBackToTop() {
    const button = document.getElementById("back-to-top");
    if (!button) {
        return;
    }

    const toggleVisibility = () => {
        if (window.scrollY > 280) {
            button.classList.add("is-visible");
        } else {
            button.classList.remove("is-visible");
        }
    };

    toggleVisibility();
    window.addEventListener("scroll", toggleVisibility, { passive: true });
    button.addEventListener("click", () => {
        window.scrollTo({ top: 0, behavior: "smooth" });
    });
}
