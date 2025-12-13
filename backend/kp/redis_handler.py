import os
import redis.asyncio as redis
import json

class RedisKbHandler(object):
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
    def __init__(self, chat_id: str, kb_id: str):
        """Get client, then set IDs and roster"""
        self._redis = redis.Redis.from_url(os.getenv("REDIS_URL"), decode_responses=True)
        self._chat_id = chat_id
        self._kb_id = kb_id

    async def append_roster(self):
        """Add our KB to the roster"""
        await self._redis.rpush(self.roster_key, self._kb_id)


    async def is_delegated_output(self) -> bool:
        """True when our KB ID is last in the list"""
        return self._kb_id == await self._redis.lindex(self.roster_key, -1)
    
    async def get_all_kb_ids(self)-> list:
        """For iterating over our roster"""
        return await self._redis.lrange(self.roster_key, 0, -1)
    
    async def add_rag_results(self, hits: list):
        """Ensures a clean list of RAG results for our chat and KB IDs"""
        await self._redis.delete(self.kb_key_pfx)
        pipe = self._redis.pipeline()

        for curr_hit in hits:
            curr_hit_str = json.dumps(curr_hit, separators=(",", ":"), ensure_ascii=False) # TODO: Vet LLM choices...
            pipe.rpush(self.kb_key_pfx, curr_hit_str)
        
        await pipe.execute()
    
    async def get_rag_results(self) -> list:
        """Returns RAG results ordered by roster"""
        all_results = []

        for kb_id in await self.get_all_kb_ids():
            kb_key = f"{self.key_pfx}:{kb_id}"
            all_results += await self._redis.lrange(kb_key, 0, -1)
        
        return [json.loads(x) for x in all_results]
    
    async def clear_keys(self):
        """Sanitize keyspace for next time around"""
        all_kb_ids = await self.get_all_kb_ids()
        pipe = self._redis.pipeline()

        # Remove KB RAG results
        for kb_id in all_kb_ids:
            pipe.delete(f"{self.key_pfx}:{kb_id}")
        
        # Remove roster
        pipe.delete(self.roster_key)
        await pipe.execute()
    
    async def close(self):
        await self._redis.aclose()