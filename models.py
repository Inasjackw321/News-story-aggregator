from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from flask_bcrypt import Bcrypt
from datetime import datetime
import json

db = SQLAlchemy()
bcrypt = Bcrypt()


# Association table for users and sources
user_sources = db.Table('user_sources',
    db.Column('user_id', db.Integer, db.ForeignKey('user.id'), primary_key=True),
    db.Column('source_id', db.Integer, db.ForeignKey('news_source.id'), primary_key=True)
)


class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Telegram credentials (encrypted in production)
    telegram_api_id = db.Column(db.String(50))
    telegram_api_hash = db.Column(db.String(100))
    telegram_session = db.Column(db.Text)  # Store session string

    # User preferences
    notification_enabled = db.Column(db.Boolean, default=True)
    dark_mode = db.Column(db.Boolean, default=True)

    # Relationships
    followed_sources = db.relationship('NewsSource', secondary=user_sources,
                                       backref=db.backref('followers', lazy='dynamic'))
    pinned_news = db.relationship('PinnedNews', backref='user', lazy='dynamic',
                                  cascade='all, delete-orphan')

    def set_password(self, password):
        self.password_hash = bcrypt.generate_password_hash(password).decode('utf-8')

    def check_password(self, password):
        return bcrypt.check_password_hash(self.password_hash, password)

    def to_dict(self):
        return {
            'id': self.id,
            'username': self.username,
            'email': self.email,
            'notification_enabled': self.notification_enabled,
            'dark_mode': self.dark_mode,
            'has_telegram': bool(self.telegram_api_id and self.telegram_api_hash)
        }


class NewsSource(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    url = db.Column(db.String(500), nullable=False)
    source_type = db.Column(db.String(20), default='rss')  # 'rss' or 'telegram'
    topic = db.Column(db.String(50), nullable=False)
    logo_url = db.Column(db.String(500))
    is_default = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_fetched = db.Column(db.DateTime)

    # For Telegram sources
    telegram_channel_id = db.Column(db.String(100))

    # Relationships
    news_items = db.relationship('NewsItem', backref='source', lazy='dynamic',
                                 cascade='all, delete-orphan')

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'url': self.url,
            'source_type': self.source_type,
            'topic': self.topic,
            'logo_url': self.logo_url,
            'is_default': self.is_default,
            'telegram_channel_id': self.telegram_channel_id
        }


class NewsItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    source_id = db.Column(db.Integer, db.ForeignKey('news_source.id'), nullable=False)
    title = db.Column(db.String(500), nullable=False)
    summary = db.Column(db.Text)
    content = db.Column(db.Text)
    url = db.Column(db.String(1000))
    image_url = db.Column(db.String(1000))
    author = db.Column(db.String(200))
    published_at = db.Column(db.DateTime, default=datetime.utcnow)
    fetched_at = db.Column(db.DateTime, default=datetime.utcnow)
    guid = db.Column(db.String(500), unique=True)  # Unique identifier from feed

    def to_dict(self):
        return {
            'id': self.id,
            'source_id': self.source_id,
            'source_name': self.source.name if self.source else None,
            'source_logo': self.source.logo_url if self.source else None,
            'topic': self.source.topic if self.source else None,
            'title': self.title,
            'summary': self.summary,
            'content': self.content,
            'url': self.url,
            'image_url': self.image_url,
            'author': self.author,
            'published_at': self.published_at.isoformat() if self.published_at else None,
            'fetched_at': self.fetched_at.isoformat() if self.fetched_at else None
        }


class PinnedNews(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    news_item_id = db.Column(db.Integer, db.ForeignKey('news_item.id'), nullable=False)
    pinned_at = db.Column(db.DateTime, default=datetime.utcnow)

    news_item = db.relationship('NewsItem', backref='pinned_by')

    __table_args__ = (
        db.UniqueConstraint('user_id', 'news_item_id', name='unique_user_pin'),
    )

    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'news_item': self.news_item.to_dict() if self.news_item else None,
            'pinned_at': self.pinned_at.isoformat() if self.pinned_at else None
        }


class ReadNews(db.Model):
    """Track which news items a user has read"""
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    news_item_id = db.Column(db.Integer, db.ForeignKey('news_item.id'), nullable=False)
    read_at = db.Column(db.DateTime, default=datetime.utcnow)

    __table_args__ = (
        db.UniqueConstraint('user_id', 'news_item_id', name='unique_user_read'),
    )
