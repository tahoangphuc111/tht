const getCookie = (n) => {
    let a = `; ${document.cookie}`.split(`; ${n}=`);
    return a.length === 2 ? a.pop().split(';').shift() : null;
};

const getSaved = () => JSON.parse(localStorage.getItem("savedArticles") || "[]");
const setSaved = (i) => {
    localStorage.setItem("savedArticles", JSON.stringify(i));
    renderSaved();
};

const renderSaved = () => {
    const i = getSaved(), l = document.getElementById("saved-articles-list"), c = document.getElementById("saved-articles-count");
    if (c) c.textContent = i.length;
    if (!l) return;
    l.innerHTML = i.length ? i.map(x => `
        <div class="saved-article-item d-flex justify-content-between align-items-center p-3 mb-2 rounded-3 border">
            <a class="text-dark fw-semibold text-decoration-none" href="${x.url}">${x.title}</a>
            <button class="btn btn-sm btn-soft saved-remove-btn" data-key="${x.key}"><i class="fa-solid fa-xmark"></i></button>
        </div>
    `).join("") : '<div class="empty-state centered p-4">Chưa có bài viết nào.</div>';
    l.querySelectorAll(".saved-remove-btn").forEach(b => b.onclick = () => setSaved(getSaved().filter(x => x.key !== b.dataset.key)));
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
        const k = sBtn.dataset.articleKey, sync = () => {
            const is = getSaved().some(x => x.key === k);
            sBtn.classList.toggle("text-primary", is);
            sBtn.querySelector('i').className = is ? "fa-solid fa-bookmark" : "fa-regular fa-bookmark";
        };
        sync();
        sBtn.onclick = () => {
            const i = getSaved(), e = i.some(x => x.key === k);
            setSaved(e ? i.filter(x => x.key !== k) : [{ k, title: document.querySelector("h1").textContent.trim(), url: location.href }, ...i]);
            sync();
        };
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
    renderSaved();
    
    document.addEventListener("keydown", (e) => {
        if (e.key === "Escape" && document.body.classList.contains("is-focus-mode")) document.querySelector(".article-focus-toggle").click();
        if (e.key === "/" && !["INPUT", "TEXTAREA"].includes(e.target.tagName)) { e.preventDefault(); document.querySelector("#id_q")?.focus(); }
    });
});
