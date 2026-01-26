import os
import json
import asyncio
from datetime import datetime
from functools import wraps

from flask import Flask, render_template, request, jsonify, redirect, url_for, flash
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from flask_socketio import SocketIO, emit, join_room, leave_room
from apscheduler.schedulers.background import BackgroundScheduler

from config import Config
from models import db, bcrypt, User, NewsSource, NewsItem, PinnedNews, ReadNews
from rss_fetcher import RSSFetcher
from telegram_fetcher import TelegramFetcher

# Initialize Flask app
app = Flask(__name__)
app.config.from_object(Config)

# Initialize extensions
db.init_app(app)
bcrypt.init_app(app)
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='eventlet')
login_manager = LoginManager(app)
login_manager.login_view = 'login'

# Initialize fetchers
rss_fetcher = None
telegram_fetcher = None

# Scheduler for background fetching
scheduler = BackgroundScheduler()


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


def init_fetchers():
    """Initialize the fetchers after app context is available"""
    global rss_fetcher, telegram_fetcher
    rss_fetcher = RSSFetcher(db, NewsSource, NewsItem)
    telegram_fetcher = TelegramFetcher(db, NewsSource, NewsItem, User)


def load_default_sources():
    """Load default news sources from JSON file"""
    sources_file = os.path.join(os.path.dirname(__file__), 'news_sources.json')

    if not os.path.exists(sources_file):
        return

    with open(sources_file, 'r') as f:
        data = json.load(f)

    for source_data in data.get('sources', []):
        existing = NewsSource.query.filter_by(url=source_data['url']).first()
        if not existing:
            source = NewsSource(
                name=source_data['name'],
                url=source_data['url'],
                topic=source_data['topic'],
                logo_url=source_data.get('logo_url'),
                source_type='rss',
                is_default=True
            )
            db.session.add(source)

    db.session.commit()


def fetch_news_job():
    """Background job to fetch news from all sources"""
    with app.app_context():
        try:
            new_items = rss_fetcher.fetch_all_feeds()

            if new_items:
                # Emit new news to all connected clients
                socketio.emit('new_news', {
                    'count': len(new_items),
                    'items': [item.to_dict() for item in new_items[:10]]
                })

                # Cleanup old news
                rss_fetcher.cleanup_old_news(Config.MAX_NEWS_PER_SOURCE)

        except Exception as e:
            print(f"Error in fetch job: {e}")


# ==================== Routes ====================

@app.route('/')
def index():
    if current_user.is_authenticated:
        return render_template('index.html', user=current_user.to_dict())
    return redirect(url_for('login'))


@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))

    if request.method == 'POST':
        data = request.get_json() if request.is_json else request.form
        username = data.get('username')
        password = data.get('password')

        user = User.query.filter_by(username=username).first()

        if user and user.check_password(password):
            login_user(user, remember=True)
            if request.is_json:
                return jsonify({'success': True, 'user': user.to_dict()})
            return redirect(url_for('index'))

        if request.is_json:
            return jsonify({'success': False, 'error': 'Invalid credentials'}), 401
        flash('Invalid username or password', 'error')

    return render_template('login.html')


@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('index'))

    if request.method == 'POST':
        data = request.get_json() if request.is_json else request.form
        username = data.get('username')
        email = data.get('email')
        password = data.get('password')

        if User.query.filter_by(username=username).first():
            if request.is_json:
                return jsonify({'success': False, 'error': 'Username already exists'}), 400
            flash('Username already exists', 'error')
            return render_template('register.html')

        if User.query.filter_by(email=email).first():
            if request.is_json:
                return jsonify({'success': False, 'error': 'Email already registered'}), 400
            flash('Email already registered', 'error')
            return render_template('register.html')

        user = User(username=username, email=email)
        user.set_password(password)

        # Follow all default sources
        default_sources = NewsSource.query.filter_by(is_default=True).all()
        user.followed_sources = default_sources

        db.session.add(user)
        db.session.commit()

        login_user(user, remember=True)

        if request.is_json:
            return jsonify({'success': True, 'user': user.to_dict()})
        return redirect(url_for('index'))

    return render_template('register.html')


@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))


@app.route('/settings')
@login_required
def settings():
    return render_template('settings.html', user=current_user.to_dict())


# ==================== API Routes ====================

@app.route('/api/news')
@login_required
def get_news():
    """Get news feed for current user"""
    topic = request.args.get('topic')
    source_id = request.args.get('source_id')
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 50, type=int)

    # Get user's followed sources
    source_ids = [s.id for s in current_user.followed_sources]

    query = NewsItem.query.filter(NewsItem.source_id.in_(source_ids))

    if topic:
        topic_sources = [s.id for s in current_user.followed_sources if s.topic == topic]
        query = query.filter(NewsItem.source_id.in_(topic_sources))

    if source_id:
        query = query.filter(NewsItem.source_id == int(source_id))

    # Order by published date, newest first
    query = query.order_by(NewsItem.published_at.desc())

    # Paginate
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)

    return jsonify({
        'news': [item.to_dict() for item in pagination.items],
        'total': pagination.total,
        'pages': pagination.pages,
        'current_page': page,
        'has_next': pagination.has_next,
        'has_prev': pagination.has_prev
    })


@app.route('/api/news/pinned')
@login_required
def get_pinned_news():
    """Get user's pinned news"""
    pinned = PinnedNews.query.filter_by(user_id=current_user.id)\
        .order_by(PinnedNews.pinned_at.desc()).all()

    return jsonify({
        'pinned': [p.to_dict() for p in pinned]
    })


@app.route('/api/news/<int:news_id>/pin', methods=['POST'])
@login_required
def pin_news(news_id):
    """Pin a news item"""
    news_item = NewsItem.query.get_or_404(news_id)

    existing = PinnedNews.query.filter_by(
        user_id=current_user.id,
        news_item_id=news_id
    ).first()

    if existing:
        return jsonify({'success': False, 'error': 'Already pinned'}), 400

    pinned = PinnedNews(user_id=current_user.id, news_item_id=news_id)
    db.session.add(pinned)
    db.session.commit()

    return jsonify({'success': True, 'pinned': pinned.to_dict()})


@app.route('/api/news/<int:news_id>/unpin', methods=['POST'])
@login_required
def unpin_news(news_id):
    """Unpin a news item"""
    pinned = PinnedNews.query.filter_by(
        user_id=current_user.id,
        news_item_id=news_id
    ).first()

    if not pinned:
        return jsonify({'success': False, 'error': 'Not pinned'}), 404

    db.session.delete(pinned)
    db.session.commit()

    return jsonify({'success': True})


@app.route('/api/sources')
@login_required
def get_sources():
    """Get all available news sources"""
    all_sources = NewsSource.query.all()
    followed_ids = [s.id for s in current_user.followed_sources]

    sources = []
    for source in all_sources:
        source_dict = source.to_dict()
        source_dict['is_followed'] = source.id in followed_ids
        sources.append(source_dict)

    return jsonify({'sources': sources})


@app.route('/api/sources/followed')
@login_required
def get_followed_sources():
    """Get user's followed sources"""
    return jsonify({
        'sources': [s.to_dict() for s in current_user.followed_sources]
    })


@app.route('/api/sources/<int:source_id>/follow', methods=['POST'])
@login_required
def follow_source(source_id):
    """Follow a news source"""
    source = NewsSource.query.get_or_404(source_id)

    if source not in current_user.followed_sources:
        current_user.followed_sources.append(source)
        db.session.commit()

    return jsonify({'success': True})


@app.route('/api/sources/<int:source_id>/unfollow', methods=['POST'])
@login_required
def unfollow_source(source_id):
    """Unfollow a news source"""
    source = NewsSource.query.get_or_404(source_id)

    if source in current_user.followed_sources:
        current_user.followed_sources.remove(source)
        db.session.commit()

    return jsonify({'success': True})


@app.route('/api/sources/add', methods=['POST'])
@login_required
def add_source():
    """Add a custom RSS feed"""
    data = request.get_json()

    name = data.get('name')
    url = data.get('url')
    topic = data.get('topic', 'world')

    if not name or not url:
        return jsonify({'success': False, 'error': 'Name and URL required'}), 400

    existing = NewsSource.query.filter_by(url=url).first()
    if existing:
        if existing not in current_user.followed_sources:
            current_user.followed_sources.append(existing)
            db.session.commit()
        return jsonify({'success': True, 'source': existing.to_dict()})

    source = NewsSource(
        name=name,
        url=url,
        topic=topic,
        source_type='rss',
        is_default=False
    )

    db.session.add(source)
    current_user.followed_sources.append(source)
    db.session.commit()

    # Fetch initial news from new source
    rss_fetcher.fetch_feed(source)

    return jsonify({'success': True, 'source': source.to_dict()})


@app.route('/api/topics')
@login_required
def get_topics():
    """Get available topics"""
    return jsonify({'topics': Config.TOPICS})


@app.route('/api/user/settings', methods=['PUT'])
@login_required
def update_settings():
    """Update user settings"""
    data = request.get_json()

    if 'notification_enabled' in data:
        current_user.notification_enabled = data['notification_enabled']

    if 'dark_mode' in data:
        current_user.dark_mode = data['dark_mode']

    db.session.commit()

    return jsonify({'success': True, 'user': current_user.to_dict()})


@app.route('/api/user/telegram', methods=['PUT'])
@login_required
def update_telegram():
    """Update Telegram API credentials"""
    data = request.get_json()

    current_user.telegram_api_id = data.get('api_id')
    current_user.telegram_api_hash = data.get('api_hash')

    db.session.commit()

    return jsonify({'success': True})


@app.route('/api/telegram/channels/add', methods=['POST'])
@login_required
def add_telegram_channel():
    """Add a Telegram channel"""
    if not current_user.telegram_api_id or not current_user.telegram_api_hash:
        return jsonify({
            'success': False,
            'error': 'Telegram API credentials not configured'
        }), 400

    data = request.get_json()
    channel = data.get('channel')
    topic = data.get('topic', 'world')
    name = data.get('name')

    if not channel:
        return jsonify({'success': False, 'error': 'Channel required'}), 400

    # Create the source without full Telegram integration for now
    source = NewsSource(
        name=name or channel,
        url=f"https://t.me/{channel}",
        topic=topic,
        source_type='telegram',
        telegram_channel_id=channel,
        is_default=False
    )

    db.session.add(source)
    current_user.followed_sources.append(source)
    db.session.commit()

    return jsonify({'success': True, 'source': source.to_dict()})


@app.route('/api/refresh', methods=['POST'])
@login_required
def refresh_news():
    """Manually refresh news"""
    try:
        source_ids = [s.id for s in current_user.followed_sources if s.source_type == 'rss']
        sources = NewsSource.query.filter(NewsSource.id.in_(source_ids)).all()

        new_items = rss_fetcher.fetch_all_feeds(sources)

        return jsonify({
            'success': True,
            'new_count': len(new_items),
            'items': [item.to_dict() for item in new_items[:20]]
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


# ==================== WebSocket Events ====================

@socketio.on('connect')
def handle_connect():
    if current_user.is_authenticated:
        join_room(f"user_{current_user.id}")
        emit('connected', {'user_id': current_user.id})


@socketio.on('disconnect')
def handle_disconnect():
    if current_user.is_authenticated:
        leave_room(f"user_{current_user.id}")


@socketio.on('subscribe_topic')
def handle_subscribe_topic(data):
    topic = data.get('topic')
    if topic:
        join_room(f"topic_{topic}")


@socketio.on('unsubscribe_topic')
def handle_unsubscribe_topic(data):
    topic = data.get('topic')
    if topic:
        leave_room(f"topic_{topic}")


# ==================== Initialization ====================

def create_app():
    with app.app_context():
        db.create_all()
        init_fetchers()
        load_default_sources()

        # Initial fetch
        try:
            rss_fetcher.fetch_all_feeds()
        except Exception as e:
            print(f"Initial fetch error: {e}")

    return app


if __name__ == '__main__':
    create_app()

    # Start scheduler
    scheduler.add_job(
        fetch_news_job,
        'interval',
        seconds=Config.RSS_UPDATE_INTERVAL,
        id='fetch_news',
        replace_existing=True
    )
    scheduler.start()

    try:
        socketio.run(app, debug=True, host='0.0.0.0', port=5000)
    except (KeyboardInterrupt, SystemExit):
        scheduler.shutdown()
