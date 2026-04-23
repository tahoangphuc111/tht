const getCookie = (n) => {
    let a = `; ${document.cookie}`.split(`; ${n}=`);
    return a.length === 2 ? a.pop().split(';').shift() : null;
};

const fetchSaved = async () => {
    const list = document.getElementById("saved-articles-list");
    if (!list) return;
    try {
        const r = await fetch('/saved-articles/');
        if (r.redirected || !r.ok || (r.headers.get('content-type') || '').indexOf('application/json') === -1) {
            renderSaved([]);
            return;
        }
        const d = await r.json();
        renderSaved(d.bookmarks);
    } catch (err) {
        console.error("Error fetching saved articles:", err);
    }
};

const renderSaved = (bookmarks) => {
    const l = document.getElementById("saved-articles-list"), c = document.getElementById("saved-articles-count");
    if (c) c.textContent = bookmarks.length;
    if (!l) return;
    l.innerHTML = bookmarks.length ? bookmarks.map(x => `
        <div class="saved-article-item d-flex justify-content-between align-items-center p-3 mb-2 rounded-3 border">
            <div>
                <a class="text-dark fw-semibold text-decoration-none d-block" href="${x.url}">${x.title}</a>
                <small class="text-muted">${x.category}</small>
            </div>
            <button class="btn btn-sm btn-soft saved-remove-btn" onclick="toggleBookmark(${x.id})"><i class="fa-solid fa-xmark"></i></button>
        </div>
    `).join("") : '<div class="empty-state centered p-4">Bạn chưa lưu bài viết nào.</div>';
};

const toggleBookmark = async (id) => {
    try {
        const r = await fetch(`/toggle-bookmark/${id}/`, {
            method: 'POST',
            headers: { 'X-CSRFToken': getCookie('csrftoken'), 'X-Requested-With': 'XMLHttpRequest' }
        });
        const d = await r.json();
        if (d.is_bookmarked !== undefined) {
            const btn = document.querySelector(`.article-save-toggle[data-article-id="${id}"]`);
            if (btn) {
                btn.classList.toggle("text-primary", d.is_bookmarked);
                btn.querySelector('i').className = d.is_bookmarked ? "fa-solid fa-bookmark" : "fa-regular fa-bookmark";
            }
            fetchSaved(); // Refresh the list
        }
    } catch (err) {
        console.error("Error toggling bookmark:", err);
    }
};

const markAsRead = async (id) => {
    try {
        await fetch(`/notification/${id}/read/`, {
            method: 'POST',
            headers: { 'X-CSRFToken': getCookie('csrftoken'), 'X-Requested-With': 'XMLHttpRequest' }
        });
    } catch (err) {
        console.error("Error marking notification as read:", err);
    }
};

const initAjaxVotes = () => {
    document.querySelectorAll('.ajax-vote-form').forEach(f => f.onsubmit = async (e) => {
        e.preventDefault();
        const btn = f.querySelector('button');
        btn.style.transform = "scale(0.8)";
        try {
            const r = await fetch(f.action, {
                method: 'POST',
                headers: { 'X-Requested-With': 'XMLHttpRequest', 'X-CSRFToken': getCookie('csrftoken') },
                body: new FormData(f)
            });
            const d = await r.json();
            if (!d.success) throw new Error(d.message);

            const scoreEl = document.getElementById('article-score');
            if (scoreEl && d.article_vote_score !== undefined) scoreEl.textContent = d.article_vote_score;

            const cScoreEl = document.getElementById(`comment-${d.comment_pk}-score`);
            if (cScoreEl && d.comment_vote_score !== undefined) cScoreEl.textContent = d.comment_vote_score;
            const userScoreEl = document.getElementById(`user-${d.target_user_pk}-score`);
            if (userScoreEl && d.target_user_score !== undefined) userScoreEl.textContent = d.target_user_score;

        } catch (err) {
            Swal.fire({ icon: 'error', title: 'Lỗi', text: err.message, timer: 2000 });
        } finally {
            setTimeout(() => btn.style.transform = "scale(1)", 150);
        }
    });
};

const initArticleActions = () => {
    const sBtn = document.querySelector(".article-save-toggle"), fBtn = document.querySelector(".article-focus-toggle");
    if (sBtn) {
        sBtn.onclick = () => toggleBookmark(sBtn.dataset.articleId);
    }
    if (fBtn) fBtn.onclick = () => {
        const a = document.body.classList.toggle("is-focus-mode");
        fBtn.querySelector('i').className = a ? "fa-solid fa-eye-slash" : "fa-solid fa-eye";
        fBtn.classList.toggle("text-primary", a);
    };
};

document.addEventListener("DOMContentLoaded", () => {
    initAjaxVotes();
    initArticleActions();
    fetchSaved();

    document.querySelectorAll(".saved-articles-trigger").forEach(b => b.onclick = fetchSaved);
    document.querySelectorAll(".article-copy-link").forEach(btn => {
        btn.onclick = async () => {
            const url = btn.dataset.copyUrl;
            if (!url) return;
            try {
                await navigator.clipboard.writeText(url);
                Swal.fire({ icon: 'success', title: 'Đã sao chép', timer: 1200, showConfirmButton: false });
            } catch (err) {
                console.error("Error copying link:", err);
            }
        };
    });

    document.addEventListener("keydown", (e) => {
        if (e.key === "Escape" && document.body.classList.contains("is-focus-mode")) document.querySelector(".article-focus-toggle").click();     
        if (e.key.toLowerCase() === "s" && !["INPUT", "TEXTAREA"].includes(e.target.tagName)) document.querySelector(".article-save-toggle")?.click();
        if (e.key.toLowerCase() === "f" && !["INPUT", "TEXTAREA"].includes(e.target.tagName)) document.querySelector(".article-focus-toggle")?.click();
        if (e.key === "/" && !["INPUT", "TEXTAREA"].includes(e.target.tagName)) { e.preventDefault(); document.querySelector("#id_q")?.focus(); } 
    });
});
