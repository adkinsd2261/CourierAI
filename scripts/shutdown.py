"""Ask the local singleton to release inputs before the launcher exits."""
import asyncio
import json
import websockets


async def stop():
    async with asyncio.timeout(3):
        async with websockets.connect("ws://127.0.0.1:8000/ws", origin="http://localhost:3000") as ws:
            await ws.send(json.dumps({"command": "stop"}))
            while True:
                if json.loads(await ws.recv()).get("type") == "ack":
                    return


if __name__ == "__main__":
    try:
        asyncio.run(stop())
    except Exception:
        print("Backend did not acknowledge shutdown. Release held game inputs manually if needed.")
