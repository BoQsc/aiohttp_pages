# web_utils.py
import aiohttp.web 

async def start_server():
    app = aiohttp.web.Application()
    return app

if __name__ == "__main__":

    aiohttp.web.run_app(start_server(), port=8000)

