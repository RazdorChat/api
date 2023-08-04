import redis
from asyncio import sleep

RDB = redis.Redis(
  host='127.0.0.1',
  port=6379,
  decode_responses=True)


async def prune_offline_nodes():
	while True:
		nodes = RDB.keys(f"nodes")
		for node in nodes:
			print(node)
		await sleep(60)