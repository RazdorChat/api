import logging
import os
from asyncio import sleep

import redis

logger = logging.getLogger(__name__)

RDB = redis.Redis(host="127.0.0.1", port=6379, decode_responses=True)


async def prune_offline_nodes():
    """Prunes offline nodes from the node list."""
    def ping(node):
        response = os.system('ping -c 1 ' + node)
        if response == 0:
            return True
        else:
            return False
    while True:
        nodes = RDB.keys(f"nodes")
        for node in nodes:
            logger.info(f"Checking node {node}")
            if ping(node) == False:
                keys = []
                keys.extend(RDB.keys(f"nodes:{node}"))
                keys.extend(RDB.keys(f"nodes:available:{node}"))    
                RDB.delete(*keys)
                logger.info(f"Removed Offline node {node}.")
        await sleep(60)
