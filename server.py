# web_utils.py
from aiohttp import web

async def start_server():
    app = web.Application()
    return app

if __name__ == "__main__":
    web.run_app(start_server(), port=8000)

