import asyncio
import hashlib
import logging
from datetime import datetime
from typing import Optional, List

try:
    from telethon import TelegramClient
    from telethon.sessions import StringSession
    from telethon.tl.functions.channels import GetFullChannelRequest
    from telethon.tl.types import MessageMediaPhoto, MessageMediaDocument
    TELETHON_AVAILABLE = True
except ImportError:
    TELETHON_AVAILABLE = False

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class TelegramFetcher:
    def __init__(self, db, NewsSource, NewsItem, User):
        self.db = db
        self.NewsSource = NewsSource
        self.NewsItem = NewsItem
        self.User = User
        self.clients = {}  # Store clients per user

    def is_available(self):
        """Check if Telethon is installed"""
        return TELETHON_AVAILABLE

    async def get_client(self, user):
        """Get or create a Telegram client for a user"""
        if not TELETHON_AVAILABLE:
            raise RuntimeError("Telethon is not installed")

        if not user.telegram_api_id or not user.telegram_api_hash:
            raise ValueError("User has not configured Telegram API credentials")

        user_id = user.id

        if user_id in self.clients:
            client = self.clients[user_id]
            if client.is_connected():
                return client

        # Create new client
        session = StringSession(user.telegram_session or '')
        client = TelegramClient(
            session,
            int(user.telegram_api_id),
            user.telegram_api_hash
        )

        await client.connect()

        if not await client.is_user_authorized():
            # Client needs authorization
            return None

        self.clients[user_id] = client
        return client

    async def authorize_client(self, user, phone_number):
        """Start authorization process for a user"""
        if not TELETHON_AVAILABLE:
            raise RuntimeError("Telethon is not installed")

        session = StringSession()
        client = TelegramClient(
            session,
            int(user.telegram_api_id),
            user.telegram_api_hash
        )

        await client.connect()
        result = await client.send_code_request(phone_number)

        # Store temporary client
        self.clients[f"auth_{user.id}"] = {
            'client': client,
            'phone': phone_number,
            'phone_code_hash': result.phone_code_hash
        }

        return True

    async def complete_authorization(self, user, code, password=None):
        """Complete authorization with verification code"""
        auth_key = f"auth_{user.id}"
        if auth_key not in self.clients:
            raise ValueError("No pending authorization")

        auth_data = self.clients[auth_key]
        client = auth_data['client']
        phone = auth_data['phone']

        try:
            await client.sign_in(
                phone=phone,
                code=code,
                phone_code_hash=auth_data['phone_code_hash']
            )
        except Exception as e:
            if '2FA' in str(e) or 'password' in str(e).lower():
                if password:
                    await client.sign_in(password=password)
                else:
                    raise ValueError("2FA password required")
            else:
                raise

        # Save session string
        session_string = client.session.save()
        user.telegram_session = session_string
        self.db.session.commit()

        # Move to active clients
        self.clients[user.id] = client
        del self.clients[auth_key]

        return True

    async def fetch_channel(self, user, source, limit=20):
        """Fetch messages from a Telegram channel"""
        try:
            client = await self.get_client(user)
            if not client:
                logger.warning(f"Client not authorized for user {user.id}")
                return []

            channel_id = source.telegram_channel_id or source.url

            # Get channel entity
            try:
                entity = await client.get_entity(channel_id)
            except Exception as e:
                logger.error(f"Could not find channel {channel_id}: {e}")
                return []

            new_items = []
            messages = await client.get_messages(entity, limit=limit)

            for message in messages:
                if not message.text and not message.message:
                    continue

                news_item = await self._parse_message(message, source, client)
                if news_item:
                    new_items.append(news_item)

            # Update last fetched
            source.last_fetched = datetime.utcnow()
            self.db.session.commit()

            logger.info(f"Found {len(new_items)} new items from {source.name}")
            return new_items

        except Exception as e:
            logger.error(f"Error fetching Telegram channel {source.name}: {e}")
            return []

    async def _parse_message(self, message, source, client):
        """Parse a Telegram message into a NewsItem"""
        # Generate unique GUID
        guid = f"tg_{source.telegram_channel_id}_{message.id}"
        guid_hash = hashlib.md5(guid.encode()).hexdigest()

        # Check if exists
        existing = self.NewsItem.query.filter_by(guid=guid_hash).first()
        if existing:
            return None

        # Extract text
        text = message.text or message.message or ''
        if not text:
            return None

        # Title is first line or first 100 chars
        lines = text.split('\n')
        title = lines[0][:200] if lines else text[:200]

        # Summary is the rest
        summary = text[:500] if len(text) > 500 else text

        # Extract image
        image_url = None
        if message.media:
            if isinstance(message.media, MessageMediaPhoto):
                # Download photo and save locally or get URL
                # For now, we'll note that there's an image
                image_url = f"/api/telegram/image/{source.id}/{message.id}"

        # Create news item
        news_item = self.NewsItem(
            source_id=source.id,
            title=title,
            summary=summary,
            content=text,
            url=f"https://t.me/{source.telegram_channel_id}/{message.id}",
            image_url=image_url,
            author=source.name,
            published_at=message.date,
            fetched_at=datetime.utcnow(),
            guid=guid_hash
        )

        try:
            self.db.session.add(news_item)
            self.db.session.commit()
            return news_item
        except Exception as e:
            self.db.session.rollback()
            logger.error(f"Error saving Telegram message: {e}")
            return None

    async def add_channel(self, user, channel_username, topic, name=None):
        """Add a new Telegram channel as a news source"""
        client = await self.get_client(user)
        if not client:
            raise ValueError("Telegram client not authorized")

        try:
            entity = await client.get_entity(channel_username)
            full = await client(GetFullChannelRequest(entity))

            source = self.NewsSource(
                name=name or entity.title,
                url=f"https://t.me/{channel_username}",
                source_type='telegram',
                topic=topic,
                telegram_channel_id=channel_username,
                logo_url=None  # Could download profile photo
            )

            self.db.session.add(source)
            self.db.session.commit()

            # Add to user's followed sources
            user.followed_sources.append(source)
            self.db.session.commit()

            return source

        except Exception as e:
            logger.error(f"Error adding channel {channel_username}: {e}")
            raise

    async def fetch_all_channels(self, user, sources=None):
        """Fetch all Telegram channels for a user"""
        if sources is None:
            sources = self.NewsSource.query.filter_by(source_type='telegram').all()

        all_items = []
        for source in sources:
            items = await self.fetch_channel(user, source)
            all_items.extend(items)

        return all_items

    def disconnect_client(self, user_id):
        """Disconnect a user's Telegram client"""
        if user_id in self.clients:
            client = self.clients[user_id]
            asyncio.create_task(client.disconnect())
            del self.clients[user_id]
