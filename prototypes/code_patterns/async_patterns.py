"""
Async/Concurrent Processing Patterns
=====================================

Patterns for concurrent OSINT data collection with proper
rate limiting and error handling.
"""

import asyncio
import aiohttp
from typing import List, Dict, Any, Callable, Optional, TypeVar, Coroutine
from dataclasses import dataclass
from datetime import datetime
import logging
from contextlib import asynccontextmanager

T = TypeVar('T')


# Semaphore Pattern for Rate Limiting
# ===================================

class AsyncRateLimiter:
    """
    Async rate limiter using semaphore and timing.

    Usage:
        limiter = AsyncRateLimiter(requests_per_second=5)

        async with limiter:
            await make_request()
    """

    def __init__(self, requests_per_second: float = 5.0, burst: int = 10):
        self.min_interval = 1.0 / requests_per_second
        self.semaphore = asyncio.Semaphore(burst)
        self._last_request = 0.0
        self._lock = asyncio.Lock()

    async def __aenter__(self):
        await self.semaphore.acquire()

        async with self._lock:
            now = asyncio.get_event_loop().time()
            elapsed = now - self._last_request

            if elapsed < self.min_interval:
                await asyncio.sleep(self.min_interval - elapsed)

            self._last_request = asyncio.get_event_loop().time()

    async def __aexit__(self, *args):
        self.semaphore.release()


# Batch Processing Pattern
# ========================

async def process_batch(
    items: List[T],
    processor: Callable[[T], Coroutine[Any, Any, Any]],
    batch_size: int = 10,
    rate_limit: float = 5.0,
    on_error: Optional[Callable[[T, Exception], None]] = None
) -> List[Any]:
    """
    Process items in concurrent batches with rate limiting.

    Usage:
        results = await process_batch(
            items=user_ids,
            processor=fetch_user,
            batch_size=10,
            rate_limit=3.0
        )
    """
    results = []
    limiter = AsyncRateLimiter(requests_per_second=rate_limit, burst=batch_size)

    async def process_item(item: T) -> Any:
        async with limiter:
            try:
                return await processor(item)
            except Exception as e:
                if on_error:
                    on_error(item, e)
                logging.warning(f"Error processing {item}: {e}")
                return None

    # Process in batches
    for i in range(0, len(items), batch_size):
        batch = items[i:i + batch_size]
        batch_results = await asyncio.gather(*[process_item(item) for item in batch])
        results.extend(batch_results)

    return results


# Retry Pattern with Exponential Backoff
# ======================================

@dataclass
class RetryConfig:
    max_retries: int = 3
    base_delay: float = 1.0
    max_delay: float = 60.0
    exponential_base: float = 2.0
    retryable_exceptions: tuple = (aiohttp.ClientError, asyncio.TimeoutError)


async def retry_async(
    coro_func: Callable[[], Coroutine[Any, Any, T]],
    config: Optional[RetryConfig] = None
) -> T:
    """
    Retry async function with exponential backoff.

    Usage:
        result = await retry_async(
            lambda: fetch_data(url),
            config=RetryConfig(max_retries=5)
        )
    """
    config = config or RetryConfig()
    last_exception = None

    for attempt in range(config.max_retries + 1):
        try:
            return await coro_func()

        except config.retryable_exceptions as e:
            last_exception = e

            if attempt < config.max_retries:
                delay = min(
                    config.base_delay * (config.exponential_base ** attempt),
                    config.max_delay
                )
                logging.warning(f"Attempt {attempt + 1} failed: {e}. Retrying in {delay:.1f}s")
                await asyncio.sleep(delay)

    raise last_exception


# Connection Pool Pattern
# =======================

class AsyncHTTPClient:
    """
    HTTP client with connection pooling and rate limiting.

    Usage:
        async with AsyncHTTPClient() as client:
            data = await client.get('https://api.example.com/data')
    """

    def __init__(
        self,
        requests_per_second: float = 10.0,
        max_connections: int = 100,
        timeout: float = 30.0
    ):
        self.limiter = AsyncRateLimiter(requests_per_second, max_connections)
        self.timeout = aiohttp.ClientTimeout(total=timeout)
        self._session: Optional[aiohttp.ClientSession] = None

    async def __aenter__(self):
        connector = aiohttp.TCPConnector(limit=100, limit_per_host=10)
        self._session = aiohttp.ClientSession(
            connector=connector,
            timeout=self.timeout
        )
        return self

    async def __aexit__(self, *args):
        if self._session:
            await self._session.close()

    async def get(self, url: str, **kwargs) -> Dict[str, Any]:
        async with self.limiter:
            async with self._session.get(url, **kwargs) as response:
                response.raise_for_status()
                return await response.json()

    async def post(self, url: str, **kwargs) -> Dict[str, Any]:
        async with self.limiter:
            async with self._session.post(url, **kwargs) as response:
                response.raise_for_status()
                return await response.json()


# Progress Tracking Pattern
# =========================

@dataclass
class ProgressTracker:
    """Track progress of async batch operations"""
    total: int
    completed: int = 0
    failed: int = 0
    start_time: datetime = None

    def __post_init__(self):
        self.start_time = datetime.now()

    def complete(self, success: bool = True):
        self.completed += 1
        if not success:
            self.failed += 1

    @property
    def success_count(self) -> int:
        return self.completed - self.failed

    @property
    def progress_percent(self) -> float:
        return (self.completed / self.total) * 100 if self.total > 0 else 0

    @property
    def elapsed_seconds(self) -> float:
        return (datetime.now() - self.start_time).total_seconds()

    @property
    def items_per_second(self) -> float:
        elapsed = self.elapsed_seconds
        return self.completed / elapsed if elapsed > 0 else 0

    @property
    def eta_seconds(self) -> Optional[float]:
        if self.items_per_second > 0:
            remaining = self.total - self.completed
            return remaining / self.items_per_second
        return None


# Worker Pool Pattern
# ===================

class WorkerPool:
    """
    Pool of async workers for processing tasks.

    Usage:
        pool = WorkerPool(num_workers=5)
        await pool.start()

        for item in items:
            await pool.submit(process_item, item)

        await pool.shutdown()
        results = pool.results
    """

    def __init__(self, num_workers: int = 5):
        self.num_workers = num_workers
        self._queue: asyncio.Queue = asyncio.Queue()
        self._workers: List[asyncio.Task] = []
        self._results: List[Any] = []
        self._errors: List[Exception] = []
        self._shutdown = False

    async def start(self):
        """Start worker tasks"""
        for i in range(self.num_workers):
            worker = asyncio.create_task(self._worker(i))
            self._workers.append(worker)

    async def _worker(self, worker_id: int):
        """Worker coroutine"""
        while not self._shutdown:
            try:
                func, args, kwargs = await asyncio.wait_for(
                    self._queue.get(),
                    timeout=1.0
                )

                try:
                    result = await func(*args, **kwargs)
                    self._results.append(result)
                except Exception as e:
                    self._errors.append(e)
                    logging.error(f"Worker {worker_id} error: {e}")

                self._queue.task_done()

            except asyncio.TimeoutError:
                continue

    async def submit(self, func: Callable, *args, **kwargs):
        """Submit task to pool"""
        await self._queue.put((func, args, kwargs))

    async def shutdown(self, wait: bool = True):
        """Shutdown pool"""
        if wait:
            await self._queue.join()

        self._shutdown = True

        for worker in self._workers:
            worker.cancel()

    @property
    def results(self) -> List[Any]:
        return self._results

    @property
    def errors(self) -> List[Exception]:
        return self._errors


# Timeout Pattern
# ===============

@asynccontextmanager
async def timeout_context(seconds: float, error_message: str = "Operation timed out"):
    """
    Context manager for timeout operations.

    Usage:
        async with timeout_context(30, "API call timed out"):
            await long_running_operation()
    """
    try:
        async with asyncio.timeout(seconds):
            yield
    except asyncio.TimeoutError:
        raise TimeoutError(error_message)
