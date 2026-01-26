// NewsFlow - Main JavaScript

class NewsApp {
    constructor() {
        this.socket = null;
        this.currentTopic = 'all';
        this.currentPage = 1;
        this.isLoading = false;
        this.hasMore = true;
        this.newNewsItems = [];
        this.pinnedIds = new Set();

        this.init();
    }

    init() {
        // Check if we're on the main page
        if (!document.getElementById('news-feed')) return;

        this.setupSocket();
        this.setupEventListeners();
        this.loadInitialData();
        this.requestNotificationPermission();
        this.setupInfiniteScroll();
    }

    // WebSocket Setup
    setupSocket() {
        this.socket = io();

        this.socket.on('connect', () => {
            console.log('Connected to server');
        });

        this.socket.on('disconnect', () => {
            console.log('Disconnected from server');
        });

        this.socket.on('new_news', (data) => {
            this.handleNewNews(data);
        });

        this.socket.on('connected', (data) => {
            console.log('User connected:', data.user_id);
        });
    }

    // Event Listeners
    setupEventListeners() {
        // Sidebar navigation
        document.querySelectorAll('.nav-item[data-topic]').forEach(item => {
            item.addEventListener('click', (e) => {
                e.preventDefault();
                this.switchTopic(item.dataset.topic);
            });
        });

        // Sidebar toggle (mobile)
        const sidebarToggle = document.getElementById('sidebar-toggle');
        if (sidebarToggle) {
            sidebarToggle.addEventListener('click', () => {
                document.querySelector('.sidebar').classList.toggle('open');
            });
        }

        // Refresh button
        const refreshBtn = document.getElementById('refresh-btn');
        if (refreshBtn) {
            refreshBtn.addEventListener('click', () => this.refreshNews());
        }

        // Load new news banner
        const loadNewNews = document.getElementById('load-new-news');
        if (loadNewNews) {
            loadNewNews.addEventListener('click', () => this.loadNewNewsItems());
        }

        const newNewsBanner = document.getElementById('new-news-banner');
        if (newNewsBanner) {
            newNewsBanner.addEventListener('click', () => this.loadNewNewsItems());
        }

        // Load more button
        const loadMoreBtn = document.getElementById('load-more-btn');
        if (loadMoreBtn) {
            loadMoreBtn.addEventListener('click', () => this.loadMoreNews());
        }

        // Manage sources modal
        const manageSourcesBtn = document.getElementById('manage-sources-btn');
        if (manageSourcesBtn) {
            manageSourcesBtn.addEventListener('click', (e) => {
                e.preventDefault();
                this.openSourcesModal();
            });
        }

        // Close modals
        document.querySelectorAll('.modal-close, .modal-overlay').forEach(el => {
            el.addEventListener('click', () => this.closeAllModals());
        });

        // Modal tabs
        document.querySelectorAll('.tab').forEach(tab => {
            tab.addEventListener('click', () => this.switchTab(tab.dataset.tab));
        });

        // Add source button
        const addSourceBtn = document.getElementById('add-source-btn');
        if (addSourceBtn) {
            addSourceBtn.addEventListener('click', () => this.addSource());
        }

        // Add Telegram channel button
        const addChannelBtn = document.getElementById('add-channel-btn');
        if (addChannelBtn) {
            addChannelBtn.addEventListener('click', () => this.addTelegramChannel());
        }

        // Save Telegram API credentials
        const saveTelegramApi = document.getElementById('save-telegram-api');
        if (saveTelegramApi) {
            saveTelegramApi.addEventListener('click', () => this.saveTelegramApi());
        }

        // Keyboard shortcuts
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape') this.closeAllModals();
            if (e.key === 'r' && !e.ctrlKey && !e.metaKey && document.activeElement.tagName !== 'INPUT') {
                e.preventDefault();
                this.refreshNews();
            }
        });
    }

    // Initial Data Load
    async loadInitialData() {
        await Promise.all([
            this.loadNews(),
            this.loadPinnedNews(),
            this.loadSources()
        ]);
    }

    // Load News
    async loadNews(append = false) {
        if (this.isLoading) return;

        this.isLoading = true;
        this.showLoading(true);

        try {
            let url = `/api/news?page=${this.currentPage}&per_page=20`;
            if (this.currentTopic !== 'all' && this.currentTopic !== 'pinned') {
                url += `&topic=${this.currentTopic}`;
            }

            const response = await fetch(url);
            const data = await response.json();

            if (this.currentTopic === 'pinned') {
                this.renderPinnedOnly();
            } else {
                this.renderNews(data.news, append);
            }

            this.hasMore = data.has_next;
            this.updateLoadMore();

        } catch (error) {
            console.error('Error loading news:', error);
            this.showError('Failed to load news');
        } finally {
            this.isLoading = false;
            this.showLoading(false);
        }
    }

    // Load Pinned News
    async loadPinnedNews() {
        try {
            const response = await fetch('/api/news/pinned');
            const data = await response.json();

            this.pinnedIds = new Set(data.pinned.map(p => p.news_item.id));
            this.renderPinnedSection(data.pinned);
            this.updatePinnedCount(data.pinned.length);

        } catch (error) {
            console.error('Error loading pinned news:', error);
        }
    }

    // Load Sources
    async loadSources() {
        try {
            const response = await fetch('/api/sources/followed');
            const data = await response.json();
            this.renderSourcesList(data.sources);
        } catch (error) {
            console.error('Error loading sources:', error);
        }
    }

    // Render News
    renderNews(items, append = false) {
        const container = document.getElementById('timeline-items');

        if (!append) {
            container.innerHTML = '';
        }

        if (items.length === 0 && !append) {
            container.innerHTML = `
                <div class="empty-state">
                    <i class="fas fa-newspaper"></i>
                    <h3>No news yet</h3>
                    <p>Start following sources to see news here</p>
                </div>
            `;
            return;
        }

        let lastDate = append ? container.dataset.lastDate : null;

        items.forEach((item, index) => {
            const itemDate = this.formatDate(item.published_at);

            // Add date separator if needed
            if (itemDate !== lastDate) {
                const separator = document.createElement('div');
                separator.className = 'date-separator';
                separator.innerHTML = `<span>${itemDate}</span>`;
                container.appendChild(separator);
                lastDate = itemDate;
            }

            const card = this.createNewsCard(item);
            card.style.animationDelay = `${index * 0.05}s`;
            container.appendChild(card);
        });

        container.dataset.lastDate = lastDate;
    }

    // Create News Card
    createNewsCard(item) {
        const isPinned = this.pinnedIds.has(item.id);
        const card = document.createElement('article');
        card.className = `news-card ${isPinned ? 'pinned' : ''}`;
        card.dataset.id = item.id;

        const imageHtml = item.image_url ? `
            <img src="${this.escapeHtml(item.image_url)}" alt="" class="news-card-image"
                 onerror="this.style.display='none'">
        ` : '';

        const logoHtml = item.source_logo ? `
            <img src="${this.escapeHtml(item.source_logo)}" alt="" class="source-logo"
                 onerror="this.style.display='none'">
        ` : '<i class="fas fa-rss source-logo" style="width:24px;text-align:center;color:var(--primary)"></i>';

        card.innerHTML = `
            <div class="news-card-inner">
                ${imageHtml}
                <div class="news-card-content">
                    <div class="news-card-meta">
                        ${logoHtml}
                        <span class="source-name">${this.escapeHtml(item.source_name || 'Unknown')}</span>
                        <span class="news-time">${this.formatTime(item.published_at)}</span>
                        <span class="news-topic">${this.formatTopic(item.topic)}</span>
                    </div>
                    <h3 class="news-card-title">
                        <a href="${this.escapeHtml(item.url || '#')}" target="_blank" rel="noopener">
                            ${this.escapeHtml(item.title)}
                        </a>
                    </h3>
                    <p class="news-card-summary">${this.escapeHtml(item.summary || '')}</p>
                    <div class="news-card-actions">
                        <button class="news-action ${isPinned ? 'pinned' : ''}" data-action="pin" data-id="${item.id}">
                            <i class="fas fa-thumbtack"></i>
                            ${isPinned ? 'Pinned' : 'Pin'}
                        </button>
                        <button class="news-action" data-action="share" data-url="${this.escapeHtml(item.url || '')}">
                            <i class="fas fa-share-alt"></i>
                            Share
                        </button>
                        <a href="${this.escapeHtml(item.url || '#')}" target="_blank" rel="noopener" class="news-action">
                            <i class="fas fa-external-link-alt"></i>
                            Read
                        </a>
                    </div>
                </div>
            </div>
        `;

        // Add event listeners
        const pinBtn = card.querySelector('[data-action="pin"]');
        pinBtn.addEventListener('click', () => this.togglePin(item.id, pinBtn));

        const shareBtn = card.querySelector('[data-action="share"]');
        shareBtn.addEventListener('click', () => this.shareNews(item));

        return card;
    }

    // Render Pinned Section
    renderPinnedSection(pinned) {
        const section = document.getElementById('pinned-section');
        const container = document.getElementById('pinned-items');

        if (pinned.length === 0) {
            section.style.display = 'none';
            return;
        }

        if (this.currentTopic !== 'pinned') {
            section.style.display = 'block';
        }

        container.innerHTML = '';
        pinned.slice(0, 3).forEach(pin => {
            const card = this.createNewsCard(pin.news_item);
            card.classList.add('pinned');
            container.appendChild(card);
        });
    }

    // Render Pinned Only (for pinned topic)
    renderPinnedOnly() {
        const container = document.getElementById('timeline-items');
        container.innerHTML = '';

        const pinnedContainer = document.getElementById('pinned-items');
        if (pinnedContainer.children.length === 0) {
            container.innerHTML = `
                <div class="empty-state">
                    <i class="fas fa-thumbtack"></i>
                    <h3>No pinned stories</h3>
                    <p>Pin stories to save them for later</p>
                </div>
            `;
        }
    }

    // Render Sources List
    renderSourcesList(sources) {
        const container = document.getElementById('sources-list');
        if (!container) return;

        container.innerHTML = '';

        // Group by topic and show top 5
        const topSources = sources.slice(0, 5);
        topSources.forEach(source => {
            const item = document.createElement('a');
            item.href = '#';
            item.className = 'nav-item source-item';
            item.dataset.sourceId = source.id;
            item.innerHTML = `
                <i class="${source.source_type === 'telegram' ? 'fab fa-telegram' : 'fas fa-rss'}"></i>
                <span>${this.escapeHtml(source.name)}</span>
            `;
            item.addEventListener('click', (e) => {
                e.preventDefault();
                this.filterBySource(source.id);
            });
            container.appendChild(item);
        });
    }

    // Switch Topic
    switchTopic(topic) {
        // Update active state
        document.querySelectorAll('.nav-item[data-topic]').forEach(item => {
            item.classList.toggle('active', item.dataset.topic === topic);
        });

        // Update title
        const titles = {
            'all': 'All News',
            'pinned': 'Pinned Stories',
            'us': 'US News',
            'ukraine': 'Ukraine',
            'middle_east': 'Middle East',
            'politics': 'Politics',
            'world': 'World News',
            'weather': 'Weather'
        };
        document.getElementById('current-topic-title').textContent = titles[topic] || 'News';

        // Show/hide pinned section
        const pinnedSection = document.getElementById('pinned-section');
        if (topic === 'pinned') {
            pinnedSection.style.display = 'none';
        } else if (topic === 'all') {
            pinnedSection.style.display = this.pinnedIds.size > 0 ? 'block' : 'none';
        } else {
            pinnedSection.style.display = 'none';
        }

        // Load news for topic
        this.currentTopic = topic;
        this.currentPage = 1;
        this.loadNews();

        // Close sidebar on mobile
        document.querySelector('.sidebar').classList.remove('open');
    }

    // Filter by Source
    filterBySource(sourceId) {
        // This would filter news by a specific source
        console.log('Filter by source:', sourceId);
    }

    // Toggle Pin
    async togglePin(newsId, button) {
        const isPinned = this.pinnedIds.has(newsId);
        const endpoint = isPinned ? 'unpin' : 'pin';

        try {
            const response = await fetch(`/api/news/${newsId}/${endpoint}`, {
                method: 'POST'
            });

            const data = await response.json();

            if (data.success) {
                if (isPinned) {
                    this.pinnedIds.delete(newsId);
                    button.classList.remove('pinned');
                    button.innerHTML = '<i class="fas fa-thumbtack"></i> Pin';
                } else {
                    this.pinnedIds.add(newsId);
                    button.classList.add('pinned');
                    button.innerHTML = '<i class="fas fa-thumbtack"></i> Pinned';
                }

                // Refresh pinned section
                this.loadPinnedNews();
            }
        } catch (error) {
            console.error('Error toggling pin:', error);
            this.showToast('Failed to update pin', 'error');
        }
    }

    // Share News
    async shareNews(item) {
        if (navigator.share) {
            try {
                await navigator.share({
                    title: item.title,
                    text: item.summary,
                    url: item.url
                });
            } catch (error) {
                if (error.name !== 'AbortError') {
                    this.copyToClipboard(item.url);
                }
            }
        } else {
            this.copyToClipboard(item.url);
        }
    }

    copyToClipboard(text) {
        navigator.clipboard.writeText(text).then(() => {
            this.showToast('Link copied to clipboard');
        }).catch(() => {
            this.showToast('Failed to copy link', 'error');
        });
    }

    // Handle New News (WebSocket)
    handleNewNews(data) {
        console.log('New news received:', data);

        this.newNewsItems = [...data.items, ...this.newNewsItems];
        this.showNewNewsBanner(this.newNewsItems.length);

        // Show notification
        if (window.USER_DATA && window.USER_DATA.notification_enabled) {
            this.showNotification(data.items[0]);
        }
    }

    // Show New News Banner
    showNewNewsBanner(count) {
        const banner = document.getElementById('new-news-banner');
        const countEl = document.getElementById('new-news-count');

        if (count > 0) {
            countEl.textContent = count;
            banner.style.display = 'flex';
        } else {
            banner.style.display = 'none';
        }
    }

    // Load New News Items
    loadNewNewsItems() {
        const container = document.getElementById('timeline-items');

        // Prepend new items
        this.newNewsItems.reverse().forEach(item => {
            const card = this.createNewsCard(item);
            container.insertBefore(card, container.firstChild);
        });

        this.newNewsItems = [];
        this.showNewNewsBanner(0);

        // Scroll to top
        window.scrollTo({ top: 0, behavior: 'smooth' });
    }

    // Refresh News
    async refreshNews() {
        const refreshBtn = document.getElementById('refresh-btn');
        refreshBtn.querySelector('i').classList.add('fa-spin');

        try {
            const response = await fetch('/api/refresh', { method: 'POST' });
            const data = await response.json();

            if (data.success && data.new_count > 0) {
                this.showToast(`Found ${data.new_count} new stories`);
                this.currentPage = 1;
                await this.loadNews();
            } else {
                this.showToast('No new stories found');
            }
        } catch (error) {
            console.error('Error refreshing:', error);
            this.showToast('Failed to refresh', 'error');
        } finally {
            refreshBtn.querySelector('i').classList.remove('fa-spin');
        }
    }

    // Load More News
    loadMoreNews() {
        this.currentPage++;
        this.loadNews(true);
    }

    // Infinite Scroll
    setupInfiniteScroll() {
        const observer = new IntersectionObserver((entries) => {
            if (entries[0].isIntersecting && this.hasMore && !this.isLoading) {
                this.loadMoreNews();
            }
        }, { rootMargin: '100px' });

        const loadMore = document.getElementById('load-more');
        if (loadMore) {
            observer.observe(loadMore);
        }
    }

    // Notifications
    requestNotificationPermission() {
        if ('Notification' in window && Notification.permission === 'default') {
            // We'll request when user enables notifications
        }
    }

    showNotification(item) {
        if ('Notification' in window && Notification.permission === 'granted') {
            const notification = new Notification(item.source_name || 'NewsFlow', {
                body: item.title,
                icon: item.source_logo || '/static/images/logo.png',
                tag: `news-${item.id}`,
                requireInteraction: false
            });

            notification.onclick = () => {
                window.focus();
                if (item.url) {
                    window.open(item.url, '_blank');
                }
                notification.close();
            };

            // Update notification badge
            this.updateNotificationBadge(1);
        }
    }

    updateNotificationBadge(count) {
        const badge = document.getElementById('notification-badge');
        if (count > 0) {
            badge.textContent = count;
            badge.style.display = 'block';
        } else {
            badge.style.display = 'none';
        }
    }

    updatePinnedCount(count) {
        const badge = document.getElementById('pinned-count');
        if (badge) {
            badge.textContent = count;
            badge.style.display = count > 0 ? 'inline' : 'none';
        }
    }

    // Sources Modal
    async openSourcesModal() {
        const modal = document.getElementById('sources-modal');
        modal.classList.add('active');

        // Load all sources
        try {
            const response = await fetch('/api/sources');
            const data = await response.json();
            this.renderAllSources(data.sources);
        } catch (error) {
            console.error('Error loading sources:', error);
        }

        // Check if user has Telegram setup
        if (window.USER_DATA && window.USER_DATA.has_telegram) {
            document.getElementById('telegram-setup').style.display = 'none';
            document.getElementById('add-channel-form').style.display = 'block';
        }
    }

    renderAllSources(sources) {
        const container = document.getElementById('all-sources-list');
        container.innerHTML = '';

        sources.forEach(source => {
            const card = document.createElement('div');
            card.className = 'source-card';
            card.innerHTML = `
                ${source.logo_url
                    ? `<img src="${this.escapeHtml(source.logo_url)}" alt="" onerror="this.style.display='none'">`
                    : '<i class="fas fa-rss" style="font-size:24px;color:var(--primary)"></i>'
                }
                <div class="source-card-info">
                    <div class="source-card-name">${this.escapeHtml(source.name)}</div>
                    <div class="source-card-topic">${this.formatTopic(source.topic)}</div>
                </div>
                <button class="source-card-toggle ${source.is_followed ? 'following' : 'not-following'}"
                        data-source-id="${source.id}">
                    ${source.is_followed ? 'Following' : 'Follow'}
                </button>
            `;

            const toggleBtn = card.querySelector('.source-card-toggle');
            toggleBtn.addEventListener('click', () => this.toggleFollow(source.id, toggleBtn));

            container.appendChild(card);
        });
    }

    async toggleFollow(sourceId, button) {
        const isFollowing = button.classList.contains('following');
        const endpoint = isFollowing ? 'unfollow' : 'follow';

        try {
            const response = await fetch(`/api/sources/${sourceId}/${endpoint}`, {
                method: 'POST'
            });

            const data = await response.json();

            if (data.success) {
                if (isFollowing) {
                    button.classList.remove('following');
                    button.classList.add('not-following');
                    button.textContent = 'Follow';
                } else {
                    button.classList.add('following');
                    button.classList.remove('not-following');
                    button.textContent = 'Following';
                }

                // Reload sources list
                this.loadSources();
            }
        } catch (error) {
            console.error('Error toggling follow:', error);
            this.showToast('Failed to update', 'error');
        }
    }

    async addSource() {
        const name = document.getElementById('new-source-name').value.trim();
        const url = document.getElementById('new-source-url').value.trim();
        const topic = document.getElementById('new-source-topic').value;

        if (!name || !url) {
            this.showToast('Please enter name and URL', 'error');
            return;
        }

        try {
            const response = await fetch('/api/sources/add', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ name, url, topic })
            });

            const data = await response.json();

            if (data.success) {
                this.showToast('Source added successfully');
                document.getElementById('new-source-name').value = '';
                document.getElementById('new-source-url').value = '';
                this.openSourcesModal(); // Refresh list
                this.loadSources();
            } else {
                this.showToast(data.error || 'Failed to add source', 'error');
            }
        } catch (error) {
            console.error('Error adding source:', error);
            this.showToast('Failed to add source', 'error');
        }
    }

    async addTelegramChannel() {
        const name = document.getElementById('new-channel-name').value.trim();
        const channel = document.getElementById('new-channel-username').value.trim().replace('@', '');
        const topic = document.getElementById('new-channel-topic').value;

        if (!channel) {
            this.showToast('Please enter channel username', 'error');
            return;
        }

        try {
            const response = await fetch('/api/telegram/channels/add', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ channel, name, topic })
            });

            const data = await response.json();

            if (data.success) {
                this.showToast('Channel added successfully');
                document.getElementById('new-channel-name').value = '';
                document.getElementById('new-channel-username').value = '';
                this.loadSources();
            } else {
                this.showToast(data.error || 'Failed to add channel', 'error');
            }
        } catch (error) {
            console.error('Error adding channel:', error);
            this.showToast('Failed to add channel', 'error');
        }
    }

    async saveTelegramApi() {
        const apiId = document.getElementById('telegram-api-id').value.trim();
        const apiHash = document.getElementById('telegram-api-hash').value.trim();

        if (!apiId || !apiHash) {
            this.showToast('Please enter both API ID and Hash', 'error');
            return;
        }

        try {
            const response = await fetch('/api/user/telegram', {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ api_id: apiId, api_hash: apiHash })
            });

            const data = await response.json();

            if (data.success) {
                this.showToast('Telegram API saved');
                window.USER_DATA.has_telegram = true;
                document.getElementById('telegram-setup').style.display = 'none';
                document.getElementById('add-channel-form').style.display = 'block';
            } else {
                this.showToast('Failed to save', 'error');
            }
        } catch (error) {
            console.error('Error saving Telegram API:', error);
            this.showToast('Failed to save', 'error');
        }
    }

    switchTab(tabName) {
        // Update tab buttons
        document.querySelectorAll('.tab').forEach(tab => {
            tab.classList.toggle('active', tab.dataset.tab === tabName);
        });

        // Update tab content
        document.querySelectorAll('.tab-content').forEach(content => {
            content.classList.toggle('active', content.id === `tab-${tabName}`);
        });
    }

    closeAllModals() {
        document.querySelectorAll('.modal').forEach(modal => {
            modal.classList.remove('active');
        });
    }

    // Utilities
    showLoading(show) {
        const indicator = document.getElementById('loading-indicator');
        if (indicator) {
            indicator.style.display = show ? 'flex' : 'none';
        }
    }

    updateLoadMore() {
        const loadMore = document.getElementById('load-more');
        if (loadMore) {
            loadMore.style.display = this.hasMore ? 'block' : 'none';
        }
    }

    showError(message) {
        const container = document.getElementById('timeline-items');
        container.innerHTML = `
            <div class="empty-state">
                <i class="fas fa-exclamation-circle"></i>
                <h3>Error</h3>
                <p>${this.escapeHtml(message)}</p>
            </div>
        `;
    }

    showToast(message, type = 'success') {
        const toast = document.createElement('div');
        toast.className = `toast toast-${type}`;
        toast.textContent = message;
        document.body.appendChild(toast);

        setTimeout(() => toast.classList.add('show'), 10);
        setTimeout(() => {
            toast.classList.remove('show');
            setTimeout(() => toast.remove(), 300);
        }, 3000);
    }

    formatDate(dateString) {
        if (!dateString) return 'Unknown';
        const date = new Date(dateString);
        const today = new Date();
        const yesterday = new Date(today);
        yesterday.setDate(yesterday.getDate() - 1);

        if (date.toDateString() === today.toDateString()) {
            return 'Today';
        } else if (date.toDateString() === yesterday.toDateString()) {
            return 'Yesterday';
        } else {
            return date.toLocaleDateString('en-US', {
                weekday: 'long',
                month: 'long',
                day: 'numeric'
            });
        }
    }

    formatTime(dateString) {
        if (!dateString) return '';
        const date = new Date(dateString);
        const now = new Date();
        const diff = (now - date) / 1000;

        if (diff < 60) return 'Just now';
        if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
        if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
        if (diff < 604800) return `${Math.floor(diff / 86400)}d ago`;

        return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
    }

    formatTopic(topic) {
        const topics = {
            'us': 'US',
            'ukraine': 'Ukraine',
            'middle_east': 'ME',
            'politics': 'Politics',
            'world': 'World',
            'weather': 'Weather'
        };
        return topics[topic] || topic || 'News';
    }

    escapeHtml(text) {
        if (!text) return '';
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
}

// Initialize app when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    window.newsApp = new NewsApp();
});
