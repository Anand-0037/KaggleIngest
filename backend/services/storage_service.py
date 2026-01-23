import os
import aiofiles
import logging
from abc import ABC, abstractmethod
from typing import Optional
from backend import config

logger = logging.getLogger(__name__)

class StorageStrategy(ABC):
    @abstractmethod
    async def save(self, key: str, content: str) -> bool:
        pass

    @abstractmethod
    async def get(self, key: str) -> Optional[str]:
        pass

class LocalStorageStrategy(StorageStrategy):
    def __init__(self, base_path: str = "outputs"):
        self.base_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", base_path))
        os.makedirs(self.base_path, exist_ok=True)

    async def save(self, key: str, content: str) -> bool:
        file_path = os.path.join(self.base_path, key)
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        try:
            async with aiofiles.open(file_path, mode='w', encoding='utf-8') as f:
                await f.write(content)
            return True
        except Exception as e:
            logger.error(f"Failed to save to local storage: {e}")
            return False

    async def get(self, key: str) -> Optional[str]:
        file_path = os.path.join(self.base_path, key)
        if not os.path.exists(file_path):
            return None
        try:
            async with aiofiles.open(file_path, mode='r', encoding='utf-8') as f:
                return await f.read()
        except Exception as e:
            logger.error(f"Failed to read from local storage: {e}")
            return None

class S3StorageStrategy(StorageStrategy):
    def __init__(self):
        import aioboto3
        self.session = aioboto3.Session()
        self.bucket = config.S3_BUCKET
        self.client_kwargs = {
            "service_name": "s3",
            "region_name": config.S3_REGION,
            "aws_access_key_id": config.S3_ACCESS_KEY,
            "aws_secret_access_key": config.S3_SECRET_KEY,
            "endpoint_url": config.S3_ENDPOINT,
        }

    async def save(self, key: str, content: str) -> bool:
        try:
            async with self.session.client(**self.client_kwargs) as s3:
                await s3.put_object(Bucket=self.bucket, Key=key, Body=content)
            return True
        except Exception as e:
            logger.error(f"Failed to save to S3: {e}")
            return False

    async def get(self, key: str) -> Optional[str]:
        try:
            async with self.session.client(**self.client_kwargs) as s3:
                response = await s3.get_object(Bucket=self.bucket, Key=key)
                async with response['Body'] as stream:
                    content = await stream.read()
                    return content.decode('utf-8')
        except Exception as e:
            logger.error(f"Failed to read from S3: {e}")
            return None

class StorageService:
    def __init__(self):
        if config.STORAGE_STRATEGY == "s3":
            self.strategy = S3StorageStrategy()
            logger.info("📦 StorageService initialized with S3 strategy")
        else:
            self.strategy = LocalStorageStrategy()
            logger.info("📦 StorageService initialized with local strategy")

    async def save_result(self, identifier: str, content: str, extension: str = "toon") -> bool:
        key = f"{identifier}.{extension}"
        return await self.strategy.save(key, content)

    async def get_result(self, identifier: str, extension: str = "toon") -> Optional[str]:
        key = f"{identifier}.{extension}"
        return await self.strategy.get(key)
