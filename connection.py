"""
Conexión a Postgres — psycopg v3 async.
Driver único. Un pool, una sintaxis (%s), cero deuda técnica.
"""

import os
import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

import psycopg
import psycopg.rows
from psycopg_pool import AsyncConnectionPool

logger = logging.getLogger(__name__)

_pool: AsyncConnectionPool | None = None


async def init_pool() -> None:
    global _pool
    dsn = os.environ["DATABASE_URL"]
    _pool = AsyncConnectionPool(conninfo=dsn, min_size=2, max_size=10, open=False)
    await _pool.open()
    logger.info("Postgres pool inicializado")


async def close_pool() -> None:
    global _pool
    if _pool:
        await _pool.close()
        logger.info("Postgres pool cerrado")


@asynccontextmanager
async def get_conn() -> AsyncGenerator[psycopg.AsyncConnection, None]:
    if _pool is None:
        raise RuntimeError("Pool no inicializado")
    async with _pool.connection() as conn:
        yield conn


async def execute(sql: str, params: tuple = ()) -> None:
    async with get_conn() as conn:
        await conn.execute(sql, params)


async def fetch_one(sql: str, params: tuple = ()) -> dict | None:
    async with get_conn() as conn:
        async with conn.cursor(row_factory=psycopg.rows.dict_row) as cur:
            await cur.execute(sql, params)
            return await cur.fetchone()


async def fetch_all(sql: str, params: tuple = ()) -> list[dict]:
    async with get_conn() as conn:
        async with conn.cursor(row_factory=psycopg.rows.dict_row) as cur:
            await cur.execute(sql, params)
            return await cur.fetchall()
