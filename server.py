import aiohttp.web
import importlib
import pathlib

async def load_routes(app):
    pages = pathlib.Path(__file__).parent.glob("page_*.py")
    
    for page in pages:
        name = page.stem[5:]  # Remove "page_" prefix
        module = importlib.import_module(page.stem)
        
        if hasattr(module, "handler"):
            app.router.add_get(f"/{name}", module.handler)

async def start():
    app = aiohttp.web.Application()
    await load_routes(app)
    return app

if __name__ == "__main__":

    aiohttp.web.run_app(start(), port=8000)

