from motor.motor_asyncio import AsyncIOMotorClient
from .config import settings


class Database:
    client: AsyncIOMotorClient | None = None
    db = None


db = Database()


def connect():
    if db.client is None:
        db.client = AsyncIOMotorClient(settings.mongo_uri)
        db.db = db.client[settings.mongo_db]
    return db.db


def close():
    if db.client:
        db.client.close()
        db.client = None
        db.db = None
