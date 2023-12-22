import base64
import json

import aiohttp.web


async def testhandle(request):
    return aiohttp.web.Response(text="Hello Fixie!")


async def websocket_handler(request):
    print("Websocket connection starting")
    ws = aiohttp.web.WebSocketResponse()
    await ws.prepare(request)
    print("Websocket connection ready")
    media_count = 0

    async for msg in ws:
        if msg.type == aiohttp.WSMsgType.TEXT:
            # Messages are a JSON encoded string
            data = json.loads(msg.data)

            # Using the event type you can determine what type of msg you are receiving
            if data["event"] == "connected":
                print("Connected Message received: {}".format(msg))
            if data["event"] == "start":
                print("Start Message received: {}".format(msg))
            if data["event"] == "media":
                payload = data["media"]["payload"]
                chunk = base64.b64decode(payload)
                if not media_count % 100:
                    print(
                        "{}th media message {}: Payload bytes {}".format(
                            media_count, msg, len(chunk)
                        )
                    )
                media_count = media_count + 1
            if data["event"] == "closed":
                print("Closed Message received: {}".format(msg))
                await ws.close()

    print("Websocket connection closed")
    return ws


if __name__ == "__main__":
    app = aiohttp.web.Application()
    app.router.add_route("GET", "/", testhandle)
    app.router.add_route("GET", "/media", websocket_handler)
    aiohttp.web.run_app(app, host="localhost", port=5000)
