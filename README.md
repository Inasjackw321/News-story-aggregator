# NewsFlow - RSS News Timeline Aggregator

A modern, real-time news aggregator with a beautiful timeline interface. Follow multiple news sources, get instant notifications, and stay informed with live updates.

## Features

- **Real-time Updates**: WebSocket-powered live news feed with instant notifications
- **Timeline View**: Beautiful, chronological display of news stories
- **Multiple Topics**: US News, Ukraine, Middle East, Politics, World News, Weather
- **Personal Accounts**: Create your account, follow sources, pin stories
- **Pin Stories**: Save important news to the top of your feed
- **Telegram Integration**: Add Telegram channels as news sources (requires your own API credentials)
- **Browser Notifications**: Get notified when breaking news arrives
- **Dark/Light Mode**: Stylish UI with theme support
- **Responsive Design**: Works on desktop and mobile devices

## Quick Start

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure Environment

```bash
cp .env.example .env
# Edit .env with your settings
```

### 3. Run the Application

```bash
python app.py
```

The app will be available at `http://localhost:5000`

## Default News Sources

The app comes pre-configured with RSS feeds from:

- **US News**: Reuters, NPR, AP News, CNN, BBC
- **Ukraine**: Kyiv Independent, BBC Europe, Reuters
- **Middle East**: Al Jazeera, Times of Israel, BBC Middle East
- **Politics**: Politico, The Guardian, BBC Politics
- **World News**: BBC World, Reuters, AP News, CNN World
- **Weather**: Weather.gov Alerts, AccuWeather

## Adding Custom Sources

### RSS Feeds

1. Click "Manage Sources" in the sidebar
2. Enter the feed name and RSS URL
3. Select a topic category
4. Click "Add Source"

### Telegram Channels

1. Go to [my.telegram.org](https://my.telegram.org)
2. Create an API application
3. Enter your API ID and Hash in Settings or the Sources modal
4. Add channels by username (e.g., @channel_name)

## Project Structure

```
News-story-aggregator/
├── app.py                 # Main Flask application
├── config.py              # Configuration settings
├── models.py              # Database models
├── rss_fetcher.py         # RSS feed fetching logic
├── telegram_fetcher.py    # Telegram integration
├── news_sources.json      # Default RSS sources
├── requirements.txt       # Python dependencies
├── static/
│   ├── css/
│   │   └── style.css      # Stylesheets
│   └── js/
│       └── main.js        # Frontend JavaScript
└── templates/
    ├── base.html          # Base template
    ├── index.html         # Main news feed
    ├── login.html         # Login page
    ├── register.html      # Registration page
    └── settings.html      # User settings
```

## API Endpoints

### News
- `GET /api/news` - Get news feed (supports `topic`, `source_id`, `page` params)
- `GET /api/news/pinned` - Get pinned news
- `POST /api/news/<id>/pin` - Pin a news item
- `POST /api/news/<id>/unpin` - Unpin a news item

### Sources
- `GET /api/sources` - Get all available sources
- `GET /api/sources/followed` - Get followed sources
- `POST /api/sources/<id>/follow` - Follow a source
- `POST /api/sources/<id>/unfollow` - Unfollow a source
- `POST /api/sources/add` - Add a custom RSS feed

### User
- `PUT /api/user/settings` - Update user settings
- `PUT /api/user/telegram` - Update Telegram credentials
- `POST /api/refresh` - Manually refresh news

### Telegram
- `POST /api/telegram/channels/add` - Add a Telegram channel

## WebSocket Events

- `connect` - Client connected
- `new_news` - New news items available
- `subscribe_topic` - Subscribe to topic updates
- `unsubscribe_topic` - Unsubscribe from topic

## Configuration

Edit `config.py` to customize:

- `RSS_UPDATE_INTERVAL` - How often to check for new news (default: 60 seconds)
- `MAX_NEWS_PER_SOURCE` - Maximum news items to keep per source (default: 100)
- `TOPICS` - Available topic categories

## Technologies Used

- **Backend**: Flask, Flask-SocketIO, SQLAlchemy
- **Frontend**: Vanilla JavaScript, CSS3
- **Database**: SQLite (configurable)
- **Real-time**: WebSockets via Socket.IO
- **RSS Parsing**: feedparser
- **Telegram**: Telethon (optional)

## License

MIT License
