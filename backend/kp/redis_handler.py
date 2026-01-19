import os
import redis
import redis.asyncio as redis_async
from redis.backoff import ExponentialBackoff
import json

_pools = {}

def get_pool(db_num: int, redis_import):
    global _pools
    pool = None

    if redis_import not in _pools:
        _pools[redis_import] = {}
    elif db_num in _pools[redis_import]:
        pool = _pools[redis_import][db_num]


    if pool is None:
        pool = redis_import.ConnectionPool.from_url(
            os.getenv("REDIS_URL"),
            db=db_num,
            decode_responses=True,
            max_connections=150,
            socket_timeout=5.0,
            socket_connect_timeout=5.0,
            health_check_interval=10,
        )
        
        _pools[redis_import][db_num] = pool

    return pool

class RedisHandler(object):
    @property
    def redis(self):
        return self._redis_import.Redis(
            connection_pool=get_pool(self._db_num, self._redis_import),
            db=self._db_num,
            retry=self._retry,
            retry_on_error=[
                ConnectionError,
                TimeoutError,
                redis.ConnectionError
            ]
        )
    
    def __init__(self, redis_import, db_num=0):
        """Get client, then set IDs and roster"""
        self._retry = redis_import.retry.Retry(ExponentialBackoff(base=0.1), retries=3)
        self._db_num = db_num
        self._redis_import = redis_import

class RedisKbHandler(RedisHandler):    
    @property
    def key_pfx(self):
        return f"kalypso:{self._chat_id}"
    
    @property
    def roster_key(self):
        """Key for a list of KB IDs tied to chat ID"""
        return f"{self.key_pfx}:roster"
    
    @property
    def kb_key_pfx(self):
        """Key for knowledge base RAG results list"""
        return f"{self.key_pfx}:{self._kb_id}"
    
    # TODO: Use metadata/message_id instead of chat_id?
    def __init__(self, chat_id: str, kb_id, db_num=0):
        """Get client, then set IDs and roster"""
        super().__init__(redis_async, db_num)
        self._chat_id = chat_id
        self._kb_id = kb_id
        self._db_num

    async def append_roster(self):
        """Add our KB to the roster"""
        await self.redis.rpush(self.roster_key, self._kb_id)


    async def is_delegated_output(self) -> bool:
        """True when our KB ID is last in the list"""
        return self._kb_id == await self.redis.lindex(self.roster_key, -1)
    
    async def get_all_kb_ids(self)-> list:
        """For iterating over our roster"""
        return await self.redis.lrange(self.roster_key, 0, -1)
    
    async def add_rag_results(self, hits: list):
        """Ensures a clean list of RAG results for our chat and KB IDs"""
        rds = self.redis
        await rds.delete(self.kb_key_pfx)
        pipe = rds.pipeline()

        for curr_hit in hits:
            curr_hit_str = json.dumps(curr_hit, separators=(",", ":"), ensure_ascii=False) # TODO: Vet LLM choices...
            pipe.rpush(self.kb_key_pfx, curr_hit_str)
        
        await pipe.execute()
    
    async def get_rag_results(self) -> list:
        """Returns RAG results ordered by roster"""
        all_results = []
        rds = self.redis

        for kb_id in await self.get_all_kb_ids():
            kb_key = f"{self.key_pfx}:{kb_id}"
            all_results += await rds.lrange(kb_key, 0, -1)
        
        results_maps = [json.loads(x) for x in all_results]
        results_maps.sort(key=lambda h: (h.get("score"), h.get("title")), reverse=True)

        return results_maps
    
    async def clear_keys(self):
        """Sanitize keyspace for next time around"""
        all_kb_ids = await self.get_all_kb_ids()
        rds = self.redis
        pipe = rds.pipeline()

        # Remove KB RAG results
        for kb_id in all_kb_ids:
            pipe.delete(f"{self.key_pfx}:{kb_id}")
        
        # Remove roster
        pipe.delete(self.roster_key)
        await pipe.execute()