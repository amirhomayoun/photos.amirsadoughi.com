// View Switcher for Photo Gallery Layouts
(function() {
    'use strict';

    const STORAGE_KEY = 'photoGalleryView';
    const DEFAULT_VIEW = 'justified';

    // Get saved view preference or default
    function getSavedView() {
        return localStorage.getItem(STORAGE_KEY) || DEFAULT_VIEW;
    }

    // Save view preference
    function saveView(view) {
        localStorage.setItem(STORAGE_KEY, view);
    }

    // Apply view to photo grid
    function applyView(view) {
        const photoGrid = document.querySelector('.photo-grid');
        if (!photoGrid) return;

        // Remove all view classes
        photoGrid.classList.remove('view-masonry', 'view-grid', 'view-justified');

        // Add new view class (justified is default, no class needed)
        if (view === 'masonry') {
            photoGrid.classList.add('view-masonry');
        } else if (view === 'grid') {
            photoGrid.classList.add('view-grid');
        }

        // Update active button
        document.querySelectorAll('.view-btn').forEach(btn => {
            if (btn.dataset.view === view) {
                btn.classList.add('active');
            } else {
                btn.classList.remove('active');
            }
        });
    }

    // Initialize on page load
    function init() {
        const savedView = getSavedView();
        applyView(savedView);

        // Add click handlers to view buttons
        document.querySelectorAll('.view-btn').forEach(btn => {
            btn.addEventListener('click', function() {
                const view = this.dataset.view;
                applyView(view);
                saveView(view);
            });
        });
    }

    // Run when DOM is ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
