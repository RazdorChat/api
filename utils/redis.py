from asyncio import sleep

import redis

RDB = redis.Redis(host="127.0.0.1", port=6379, decode_responses=True)


async def prune_offline_nodes():
    """Prunes offline nodes from the node list."""
    while True:
        nodes = RDB.keys(f"nodes")
        for node in nodes:
            print(node)
        await sleep(60)
