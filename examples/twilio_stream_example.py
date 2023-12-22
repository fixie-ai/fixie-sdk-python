import base64
import json
import logging

import aiohttp.web


async def testhandle(request):
    return aiohttp.web.Response(text="Hello Fixie!")


async def websocket_handler(request):
    logging.info("Websocket connection starting")
    ws = aiohttp.web.WebSocketResponse()
    await ws.prepare(request)
    logging.info("Websocket connection ready")
    media_count = 0

    async for msg in ws:
        if msg.type == aiohttp.WSMsgType.TEXT:
            # Messages are a JSON encoded string
            data = json.loads(msg.data)

            # Using the event type you can determine what type of msg you are receiving
            if data["event"] == "connected":
                logging.info(f"Received connected message: {msg}")
            if data["event"] == "start":
                logging.info(f"Received start message: {msg}")
            if data["event"] == "media":
                payload = data["media"]["payload"]
                chunk = base64.b64decode(payload)
                if not media_count % 100:
                    logging.info(
                        f"(Received {media_count}th media message: {msg} with payload size {len(chunk)}"
                    )
                media_count = media_count + 1
            if data["event"] == "closed":
                logging.info("Received close message: {msg}")
                await ws.close()

    logging.info("Websocket connection closed")
    return ws


if __name__ == "__main__":
    app = aiohttp.web.Application()
    app.router.add_route("GET", "/", testhandle)
    app.router.add_route("GET", "/media", websocket_handler)
    aiohttp.web.run_app(app, host="localhost", port=5000)
