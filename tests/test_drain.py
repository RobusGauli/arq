import asyncio

import pytest

from arq import Drain
from arq.drain import TaskError


async def test_drain(redis_pool):
    async with redis_pool.get() as redis:
        await redis.rpush(b'foobar', b'1')
        await redis.rpush(b'foobar', b'2')
        await redis.rpush(b'foobar', b'3')
        await redis.rpush(b'foobar', b'4')
    total = 0

    async def run(job):
        nonlocal total
        total += int(job.decode())

    drain = Drain(redis_pool=redis_pool)
    async with drain:
        async for raw_queue, raw_data in drain.iter(b'foobar'):
            assert raw_queue == b'foobar'
            drain.add(run, raw_data)
    assert total == 10


async def test_drain_error(redis_pool):
    async with redis_pool.get() as redis:
        await redis.rpush(b'foobar', b'1')

    async def run(job):
        raise RuntimeError('snap')

    drain = Drain(redis_pool=redis_pool, raise_task_exception=True)
    with pytest.raises(TaskError) as exc_info:
        async with drain:
            async for raw_queue, raw_data in drain.iter(b'foobar'):
                assert raw_queue == b'foobar'
                drain.add(run, raw_data)
                break
    assert 'TaskError: A processed task failed: RuntimeError, snap' in str(exc_info)


async def test_drain_timeout(redis_pool, caplog):
    async with redis_pool.get() as redis:
        await redis.rpush(b'foobar', b'1')
        await redis.rpush(b'foobar', b'1')

    async def run(v):
        assert v == b'1'
        await asyncio.sleep(0.2)

    drain = Drain(redis_pool=redis_pool, max_concurrent_tasks=1, semaphore_timeout=0.11)
    async with drain:
        async for raw_queue, raw_data in drain.iter(b'foobar'):
            drain.add(run, raw_data)

    assert 'task semaphore acquisition timed after 0.1s' in caplog
