import feedparser
import requests
from bs4 import BeautifulSoup
from datetime import datetime
from dateutil import parser as date_parser
import hashlib
import re
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class RSSFetcher:
    def __init__(self, db, NewsSource, NewsItem):
        self.db = db
        self.NewsSource = NewsSource
        self.NewsItem = NewsItem
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })

    def fetch_feed(self, source):
        """Fetch and parse a single RSS feed"""
        try:
            logger.info(f"Fetching feed: {source.name} ({source.url})")
            feed = feedparser.parse(source.url)

            if feed.bozo and not feed.entries:
                logger.error(f"Error parsing feed {source.name}: {feed.bozo_exception}")
                return []

            new_items = []
            for entry in feed.entries:
                news_item = self._parse_entry(entry, source)
                if news_item:
                    new_items.append(news_item)

            # Update last fetched time
            source.last_fetched = datetime.utcnow()
            self.db.session.commit()

            logger.info(f"Found {len(new_items)} new items from {source.name}")
            return new_items

        except Exception as e:
            logger.error(f"Error fetching feed {source.name}: {e}")
            return []

    def _parse_entry(self, entry, source):
        """Parse a single feed entry into a NewsItem"""
        # Generate unique GUID
        guid = entry.get('id') or entry.get('link') or entry.get('title', '')
        guid_hash = hashlib.md5(f"{source.id}:{guid}".encode()).hexdigest()

        # Check if item already exists
        existing = self.NewsItem.query.filter_by(guid=guid_hash).first()
        if existing:
            return None

        # Extract title
        title = entry.get('title', 'No Title')
        if hasattr(title, 'value'):
            title = title.value
        title = self._clean_html(title)

        # Extract summary
        summary = entry.get('summary', '') or entry.get('description', '')
        if hasattr(summary, 'value'):
            summary = summary.value
        summary = self._clean_html(summary)
        if len(summary) > 500:
            summary = summary[:497] + '...'

        # Extract content
        content = ''
        if 'content' in entry:
            content = entry.content[0].get('value', '')
        elif 'description' in entry:
            content = entry.description

        # Extract image
        image_url = self._extract_image(entry, content or summary)

        # Extract URL
        url = entry.get('link', '')

        # Extract author
        author = entry.get('author', '')
        if not author and 'authors' in entry:
            authors = entry.get('authors', [])
            if authors:
                author = authors[0].get('name', '')

        # Parse published date
        published_at = self._parse_date(entry)

        # Create news item
        news_item = self.NewsItem(
            source_id=source.id,
            title=title,
            summary=summary,
            content=self._clean_html(content),
            url=url,
            image_url=image_url,
            author=author,
            published_at=published_at,
            fetched_at=datetime.utcnow(),
            guid=guid_hash
        )

        try:
            self.db.session.add(news_item)
            self.db.session.commit()
            return news_item
        except Exception as e:
            self.db.session.rollback()
            logger.error(f"Error saving news item: {e}")
            return None

    def _extract_image(self, entry, content):
        """Extract image URL from feed entry"""
        # Check for media content
        if 'media_content' in entry:
            for media in entry.media_content:
                if 'url' in media:
                    return media['url']

        # Check for media thumbnail
        if 'media_thumbnail' in entry:
            for thumb in entry.media_thumbnail:
                if 'url' in thumb:
                    return thumb['url']

        # Check for enclosures
        if 'enclosures' in entry:
            for enc in entry.enclosures:
                if enc.get('type', '').startswith('image'):
                    return enc.get('href') or enc.get('url')

        # Check for image in links
        if 'links' in entry:
            for link in entry.links:
                if link.get('type', '').startswith('image'):
                    return link.get('href')

        # Try to extract from content HTML
        if content:
            soup = BeautifulSoup(content, 'lxml')
            img = soup.find('img')
            if img and img.get('src'):
                return img['src']

        return None

    def _parse_date(self, entry):
        """Parse publication date from entry"""
        date_fields = ['published_parsed', 'updated_parsed', 'created_parsed']

        for field in date_fields:
            if field in entry and entry[field]:
                try:
                    return datetime(*entry[field][:6])
                except Exception:
                    pass

        # Try parsing string dates
        date_str_fields = ['published', 'updated', 'created']
        for field in date_str_fields:
            if field in entry and entry[field]:
                try:
                    return date_parser.parse(entry[field])
                except Exception:
                    pass

        return datetime.utcnow()

    def _clean_html(self, text):
        """Remove HTML tags and clean up text"""
        if not text:
            return ''

        # Remove HTML tags
        soup = BeautifulSoup(text, 'lxml')
        text = soup.get_text(separator=' ')

        # Clean up whitespace
        text = re.sub(r'\s+', ' ', text).strip()

        return text

    def fetch_all_feeds(self, sources=None):
        """Fetch all RSS feeds concurrently"""
        if sources is None:
            sources = self.NewsSource.query.filter_by(source_type='rss').all()

        all_new_items = []

        with ThreadPoolExecutor(max_workers=10) as executor:
            future_to_source = {
                executor.submit(self.fetch_feed, source): source
                for source in sources
            }

            for future in as_completed(future_to_source):
                source = future_to_source[future]
                try:
                    new_items = future.result()
                    all_new_items.extend(new_items)
                except Exception as e:
                    logger.error(f"Error fetching {source.name}: {e}")

        return all_new_items

    def cleanup_old_news(self, max_per_source=100):
        """Remove old news items to prevent database bloat"""
        sources = self.NewsSource.query.all()

        for source in sources:
            count = source.news_items.count()
            if count > max_per_source:
                # Get oldest items to delete
                old_items = self.NewsItem.query.filter_by(source_id=source.id)\
                    .order_by(self.NewsItem.published_at.asc())\
                    .limit(count - max_per_source).all()

                for item in old_items:
                    self.db.session.delete(item)

        self.db.session.commit()
