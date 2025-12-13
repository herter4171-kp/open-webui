from typing import Optional, List, Dict, Any
from aiobotocore.session import get_session 
from botocore.config import Config
from urllib.parse import urlparse
import asyncio

__rag_header = "Retrieved Context\n------------------\n"

async def retrieve_from_kb(user_prompt: str, kb_id: str, top_k: int, hybrid=True, aws_region="us-gov-west-1") -> list:
    """Retrieves top k from given KB, and returns list of hit dicts"""
    payload = {
        "knowledgeBaseId": kb_id,
        "retrievalQuery": {"text": user_prompt},
        "retrievalConfiguration": {
            "vectorSearchConfiguration": {"numberOfResults": top_k}
        },
    }

    if hybrid:
        payload["retrievalConfiguration"]["vectorSearchConfiguration"]["overrideSearchType"] = "HYBRID"

    async with get_session().create_client(
        "bedrock-agent-runtime",
        region_name=aws_region,
        config=Config(retries={"max_attempts": 5, "mode": "standard"})
    ) as client:
        resp = await client.retrieve(**payload)

    hits = []

    for r in resp.get("retrievalResults", []):
        content = (r.get("content") or {})
        txt = (content.get("text") or "").strip()
        md = r.get("metadata") or {}
        loc = r.get("location") or {}
        uri = None

        if isinstance(loc.get("s3Location"), dict):
            uri = loc["s3Location"].get("uri") or loc["s3Location"].get("url")

        kp_md = {}

        for curr_key in ["doc_number", "preparer", "release_date"]:
            kp_key = f"kp_{curr_key}"
            kp_md[kp_key] = md.get(kp_key) or ""

        hits.append({
            "text": txt,
            "title": md.get("title") or "Untitled",
            "uri": uri,
            "score": r.get("score")
        } | kp_md)

    return hits

def format_context(hits: list, max_chars) -> str:
    """Converts the hit list to a GPT-readable string"""
    if not hits:
        return "No results found in the Knowledge Base."
    
    seen = set()
    uniq: List[Dict[str, Any]] = []

    for h in hits:
        t = h.get("text", "")
        if t and t not in seen:
            seen.add(t)
            uniq.append(h)
            
    uniq.sort(key=lambda h: (h.get("score") is None, -(h.get("score") or 0)))

    buf = [__rag_header]
    total = len(__rag_header)

    for i, h in enumerate(uniq, 1):
        text = h.get("text", "")
        block = f"[{i}] {text}\n— title: {h.get('title','Untitled')}, uri: {h.get('uri','N/A')}, kp_doc_number: {h.get('kp_doc_number', 'N/A')}\n\n"

        # TODO: Necessary?
        if total + len(block) > max_chars:
            break

        buf.append(block)
        total += len(block)

    buf.append("When you rely on a passage from here, cite it like [n].")

    return "".join(buf)

def prior_message_is_rag(all_prior_messages: list) -> bool:
    """Returns true when the prior message (one before latest) is RAG"""
    is_rag = False

    if all_prior_messages:
        prior_content = all_prior_messages[-1]["content"]
        is_rag = prior_content.startswith(__rag_header)

    return is_rag

async def embed_linked_citations(assistant_msg: dict, redis, aws_region="us-gov-west-1"):
    """Adds a sources list with links to source content"""
    # Establish all hits from Redis
    hits = await redis.get_rag_results()
    
    sources_sec = "\n\n**Sources:**\n"

    user_cite_num = 1
    user_cite_map = {}
    num_cites = 0

    # Establish all hits from Redis
    hits = await redis.get_rag_results()

    # Clear Redis keyspace
    t_clear_redis = asyncio.create_task(redis.clear_keys())

    async with get_session().create_client(
        "s3", region_name=aws_region
    ) as s3_client:
        for i, curr_hit in enumerate(hits):
            cite_str = f"[{i+1}]"
            user_cite_map[cite_str] = f"[{user_cite_num}]"
            msg = assistant_msg["content"]

            if cite_str in msg:
                msg = msg.replace(cite_str, user_cite_map[cite_str])
                assistant_msg["content"] = msg

                curr_txt = curr_hit.get('title')
                doc_num = curr_hit.get("kp_doc_number")

                if doc_num:
                    curr_txt += f", {doc_num}"
                
                curr_uri = curr_hit.get('uri')

                if curr_uri:
                    s3_url = await _get_s3_url(s3_client, curr_uri)
                    final_txt = f"[{curr_txt}]({s3_url})"
                else:
                    final_txt = curr_txt + "(No download available)"
                
                sources_sec += f"{user_cite_num}. {final_txt}\n"
                user_cite_num += 1
                num_cites += 1
    
    if num_cites:
        assistant_msg["content"] += sources_sec
    
    await asyncio.gather(t_clear_redis)

    return assistant_msg

async def _get_s3_url(s3_client, s3_uri: str, expires=300):
    """Returns a temp pre-signed S3 url for the given URI"""
    s3_uri_parsed = urlparse(s3_uri)
    bucket, key = s3_uri_parsed.netloc, s3_uri_parsed.path.lstrip("/")
    filename = key.split("/")[-1]

    response_content_type = "application/pdf"
        
    if key.endswith(".yml"):
        response_content_type = "text/plain"
        filename = filename.replace(".yml", ".txt")

    return await s3_client.generate_presigned_url(
        ClientMethod="get_object",
        Params={
            "Bucket": bucket,
            "Key": key,
            "ResponseContentType": response_content_type,
            # Cache control per cyber sec
            "ResponseCacheControl": "no-store, private",
            # Force download per cyber sec
            "ResponseContentDisposition": f'attachment; filename="{filename}"',
        },
        ExpiresIn=expires,
    )