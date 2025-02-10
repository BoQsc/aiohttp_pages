# server.py (main entry point)
import asyncio
from aiohttp import web
import importlib
import glob

async def handle_dynamic(request):
    page_name = request.match_info['page']
    try:
        module = importlib.import_module(f'pages.page_{page_name}')
        content = await module.render(request)
        return web.Response(text=content, content_type='text/html')
    except ModuleNotFoundError:
        return web.Response(status=404)

async def list_routes(request):
    pages = [f.stem.split('_')[1] for f in Path('pages').glob('page_*.py')]
    html = "<h1>Available Pages:</h1><ul>"
    for page in pages:
        html += f'<li><a href="/{page}">{page}</a></li>'
    return web.Response(text=html, content_type='text/html')

def init_app():
    app = web.Application()
    app.router.add_get('/{page}', handle_dynamic)
    app.router.add_get('/list', list_routes)
    return app

if __name__ == '__main__':
    web.run_app(init_app())