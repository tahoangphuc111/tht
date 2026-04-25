document.addEventListener('DOMContentLoaded', () => {
    const voteForms = document.querySelectorAll('.ajax-vote-form');
    voteForms.forEach(form => {
        form.addEventListener('submit', async (e) => {
            e.preventDefault();
            const formData = new FormData(form);
            const url = form.getAttribute('action');
            try {
                const response = await fetch(url, {
                    method: 'POST',
                    body: formData,
                    headers: {
                        'X-Requested-With': 'XMLHttpRequest'
                    }
                });
                if (response.ok) {
                    const data = await response.json();
                    if (data.success) {
                        if (data.article_score !== undefined) updateScore('article-score', data.article_score);
                        if (data.comment_score !== undefined) updateScore(`comment-${data.comment_pk}-score`, data.comment_score);
                        if (data.target_user_score !== undefined) updateScore(`user-${data.target_user_pk}-score`, data.target_user_score);
                    } else {
                        alert(data.message);
                    }
                } else if (response.status === 401) {
                    window.location.href = '/login/?next=' + window.location.pathname;
                }
            } catch (err) {
                console.error('Vote error:', err);
            }
        });
    });
    function updateScore(elementId, newScore) {
        const scoreEl = document.getElementById(elementId);
        if (scoreEl) {
            scoreEl.textContent = newScore;
            scoreEl.style.transition = 'all 0.3s ease';
            scoreEl.style.transform = 'scale(1.2)';
            scoreEl.style.color = 'var(--brand)';
            setTimeout(() => {
                scoreEl.style.transform = 'scale(1)';
                scoreEl.style.color = '';
            }, 300);
        }
    }
    const saveToggles = document.querySelectorAll('.article-save-toggle');
    saveToggles.forEach(btn => {
        btn.addEventListener('click', async () => {
            const articleId = btn.getAttribute('data-article-id');
            if (!articleId) return;
            let csrfToken = '';
            const csrfInput = document.querySelector('input[name="csrfmiddlewaretoken"]');
            if (csrfInput) csrfToken = csrfInput.value;
            else csrfToken = getCookie('csrftoken');
            try {
                const response = await fetch(`/toggle-bookmark/${articleId}/`, {
                    method: 'POST',
                    headers: {
                        'X-Requested-With': 'XMLHttpRequest',
                        'X-CSRFToken': csrfToken
                    }
                });
                if (response.ok) {
                    const data = await response.json();
                    if (data.is_bookmarked) {
                        btn.classList.add('text-primary');
                        btn.innerHTML = '<i class="fa-solid fa-bookmark"></i>';
                    } else {
                        btn.classList.remove('text-primary');
                        btn.innerHTML = '<i class="fa-regular fa-bookmark"></i>';
                    }
                    const countEl = document.getElementById('saved-articles-count');
                    if (countEl) countEl.textContent = data.count;
                    btn.style.transition = 'transform 0.2s cubic-bezier(0.175, 0.885, 0.32, 1.275)';
                    btn.style.transform = 'scale(1.2)';
                    setTimeout(() => btn.style.transform = 'scale(1)', 200);
                } else if (response.status === 401 || response.status === 403) {
                    window.location.href = '/login/?next=' + window.location.pathname;
                }
            } catch (err) {
                console.error('Bookmark error:', err);
            }
        });
    });
    function getCookie(name) {
        let cookieValue = null;
        if (document.cookie && document.cookie !== '') {
            const cookies = document.cookie.split(';');
            for (let i = 0; i < cookies.length; i++) {
                const cookie = cookies[i].trim();
                if (cookie.substring(0, name.length + 1) === (name + '=')) {
                    cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                    break;
                }
            }
        }
        return cookieValue;
    }
});