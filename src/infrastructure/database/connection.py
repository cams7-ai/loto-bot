"""Conexão MongoDB e inicialização do Beanie."""

from __future__ import annotations

from beanie import init_beanie
from pymongo import AsyncMongoClient

from infrastructure.database.models import BetModel


class MongoDatabase:
    def __init__(self, uri: str, database_name: str) -> None:
        self._uri = uri
        self._database_name = database_name
        self._client: AsyncMongoClient | None = None
        self._initialized = False

    async def ensure_initialized(self) -> None:
        if self._initialized:
            return

        if self._client is None:
            self._client = AsyncMongoClient(self._uri)

        await init_beanie(database=self._client[self._database_name], document_models=[BetModel])
        self._initialized = True

    async def close(self) -> None:
        if self._client is not None:
            await self._client.close()

        self._client = None
        self._initialized = False
