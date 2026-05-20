document.addEventListener('DOMContentLoaded', function() {
    // Mobile menu toggle
    const menuToggle = document.querySelector('.mobile-menu-toggle');
    const mainNav = document.querySelector('.main-nav');
    if (menuToggle && mainNav) {
        menuToggle.addEventListener('click', function() {
            mainNav.style.display = mainNav.style.display === 'flex' ? 'none' : 'flex';
        });
    }

    // Simple news loader (placeholder)
    const newsList = document.getElementById('news-list');
    if (newsList) {
        // In production, this will fetch from /api/countries/lka/news/
        newsList.innerHTML = '<p class="loading">News feed will appear here once scrapers are active.</p>';
    }
});
