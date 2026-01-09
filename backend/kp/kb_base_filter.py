"""
title: KB to GPT
author: Justin Herter
auther_email: herter@kairospower.com
description: >
    This filter feeds the latest user message to a Bedrock knowledge base, and the reply is prepended
    as an assistant message before the prompt itself when sent to the target model, i.e. ChatGPT.
required_open_webui_version: 0.4.0
requirements: aiobotocore==3.1.0
version: 0.0.3
"""
from os import environ
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
import asyncio
import json
import traceback
import time

from aiobotocore.session import get_session 
from botocore.config import Config

from urllib.parse import urlparse

from kp.knowledge_base import retrieve_from_kb, format_context, prior_message_is_rag, embed_linked_citations
from kp.redis_handler import RedisKbHandler

class KbBaseFilter:

    class Valves(BaseModel):
        TOP_K: int = 9
        MAX_CONTEXT_CHARS: int = 32000
        KB_ID: str = environ.get("MAIN_KB_ID", "D3Q2K57HXU") # Fallback is for dev west
        HYBRID: bool = False
        AWS_REGION: str = "us-gov-west-1"

    def __init__(self):
        self.valves = self.Valves()
        self.toggle = True
    
    async def inlet(self, body: dict) -> dict:
        try:
            chat_id = body["metadata"]["chat_id"]
            all_messages = body["messages"]
            user_message = all_messages.pop()

            # Get Redis, and add our KB ID to roster
            redis = RedisKbHandler(chat_id, self.valves.KB_ID)
            await redis.append_roster()

            # Get KB RAG results, and send to Redis
            my_hits = await retrieve_from_kb(user_message["content"], self.valves.KB_ID, self.valves.TOP_K, self.valves.HYBRID, self.valves.AWS_REGION)
            await redis.add_rag_results(my_hits)

            # Get all RAG results, and format
            all_hits = await redis.get_rag_results()
            context_block = format_context(all_hits, self.valves.MAX_CONTEXT_CHARS)

            # Want to overwrite prior RAG message if it was given to us
            if prior_message_is_rag(all_messages):
                all_messages.pop() # Remove old RAG message

            # TODO: Overwrite a message before user's if it starts with "Retrieved Context"
            all_messages += [{"role": "assistant", "content": context_block}, user_message]
            body["messages"] = all_messages
        except Exception as ex:
            print(ex)
            print(traceback.format_exc())

            # Since the logs are a bit chaotic
            with open(f"/tmp/FFS-{time.time()}.txt", "w") as f:
                f.writelines(traceback.format_exc())
        finally:
            return body  

    def stream(self, event: dict) -> dict:
        return event

    async def outlet(self, body: dict) -> dict:
        try:
            chat_id = body["chat_id"] # Note different keying than inlet body!  Silent errors!
            redis = RedisKbHandler(chat_id, self.valves.KB_ID)

            # Only want one KB filter to write output
            if not await redis.is_delegated_output():
                print("Not delegated output")
                return body

            assistant_msg = body["messages"][-1]        
            body["messages"][-1] = await embed_linked_citations(assistant_msg, redis)

            return body
        except Exception as ex:
            print(ex)
            print(traceback.format_exc())
            return body