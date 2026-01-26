import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-secret-key-change-in-production'
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or 'sqlite:///news_aggregator.db'
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Telegram API credentials (users provide their own)
    TELEGRAM_API_ID = os.environ.get('TELEGRAM_API_ID')
    TELEGRAM_API_HASH = os.environ.get('TELEGRAM_API_HASH')

    # RSS Feed update interval in seconds
    RSS_UPDATE_INTERVAL = 60  # 1 minute for fast updates

    # Maximum news items to keep per source
    MAX_NEWS_PER_SOURCE = 100

    # Topics configuration
    TOPICS = {
        'us': 'US News',
        'ukraine': 'Ukraine',
        'middle_east': 'Middle East',
        'politics': 'Politics (Global)',
        'world': 'World News',
        'weather': 'Weather'
    }
