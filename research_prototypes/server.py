import os
import re
import io
import asyncio
from aiohttp import web

###############################################
# Resources and Helpers
###############################################

class Resources:
    async def get_public_ip(self):
        # In a real server you might query an external service.
        return "127.0.0.1"

    async def list_routes(self):
        pages_dir = os.path.join(os.path.dirname(__file__), "pages")
        routes = []
        if os.path.exists(pages_dir):
            for filename in os.listdir(pages_dir):
                if filename.startswith("page_") and filename.endswith(".py"):
                    # e.g. "page_home.py" becomes "home"
                    routes.append(filename[len("page_"):-3])
        return routes

    async def list_content(self):
        content_dir = os.path.join(os.path.dirname(__file__), "content")
        if os.path.exists(content_dir):
            return os.listdir(content_dir)
        return []

def list_available_routes():
    pages_dir = os.path.join(os.path.dirname(__file__), "pages")
    routes = []
    if os.path.exists(pages_dir):
        for filename in os.listdir(pages_dir):
            if filename.startswith("page_") and filename.endswith(".py"):
                routes.append(filename[len("page_"):-3])
    return routes

###############################################
# Templating Engine
###############################################

async def process_template(template_str, env):
    """
    Look for markers in the form {{ ... }} and evaluate the contained
    Python expression in the provided environment (env). If the expression
    starts with "await " then await its result.
    """
    pattern = re.compile(r"\{\{\s*(.*?)\s*\}\}", re.DOTALL)

    async def repl(match):
        code = match.group(1).strip()
        try:
            if code.startswith("await "):
                expr = code[6:].strip()
                result = await eval(expr, env)
            else:
                result = eval(code, env)
        except NameError as e:
            # If the code is just a bare identifier (e.g. page_home_footer)
            # then try to load a corresponding file.
            if code.isidentifier():
                page_dir = env.get("__page_dir__", ".")
                part_file = os.path.join(page_dir, f"{code}.py")
                if os.path.exists(part_file):
                    part_output, _ = await render_page(part_file, env["context"])
                    result = await process_template(part_output, env)
                else:
                    result = f"[Error: {e}]"
            else:
                result = f"[Error: {e}]"
        except Exception as e:
            result = f"[Error: {e}]"
        return str(result)

    parts = []
    last = 0
    for m in pattern.finditer(template_str):
        parts.append(template_str[last:m.start()])
        parts.append(await repl(m))
        last = m.end()
    parts.append(template_str[last:])
    return "".join(parts)

async def render_page(file_path, context):
    """
    Loads and “renders” a page script. The page script is a Python file that
    (when executed) prints HTML content. We wrap its source into an async
    function (so that await is allowed) and capture its output.
    
    The page script will see a variable called 'context' that holds configuration,
    routes and resource functions.
    """
    with open(file_path, "r", encoding="utf-8") as f:
        source = f.read()

    # Create an environment where the page will run.
    env = {}
    env["context"] = context

    # Capture print() output.
    output = io.StringIO()
    def captured_print(*args, **kwargs):
        print(*args, **kwargs, file=output)
    env["print"] = captured_print

    # Also provide a debug() that writes directly to stdout.
    env["debug"] = print

    # Save the current page directory so that includes work.
    env["__page_dir__"] = os.path.dirname(file_path)

    # Wrap the page source in an async function so that we can use await.
    wrapped_source = "async def __template_main__():\n"
    for line in source.splitlines():
        wrapped_source += "    " + line + "\n"

    # Execute the wrapped source to create __template_main__.
    exec(wrapped_source, env)
    # Run the async function.
    await env["__template_main__"]()
    # The captured output is the raw page content.
    return output.getvalue(), env

###############################################
# HTTP Request Handlers
###############################################

async def handle_page(request):
    # Determine the requested page (default is "home")
    page = request.match_info.get("page", "home")
    pages_dir = os.path.join(os.path.dirname(__file__), "pages")
    file_name = f"page_{page}.py"
    file_path = os.path.join(pages_dir, file_name)
    if not os.path.exists(file_path):
        return web.Response(status=404, text="Page not found")

    # Build the context passed to the page script.
    config = {"server_name": "My Python Server"}
    resources = Resources()
    context = {
        "server_name": config["server_name"],  # Now available for direct access.
        "config": config,
        "routes": list_available_routes(),
        "resources": resources
    }

    # Render the page and process its template markers.
    raw_output, env = await render_page(file_path, context)
    final_output = await process_template(raw_output, env)
    return web.Response(text=final_output, content_type="text/html")

###############################################
# Start the Server
###############################################

async def start_server():
    app = web.Application()
    app.router.add_get("/", handle_page)
    app.router.add_get("/{page}", handle_page)
    return app

if __name__ == "__main__":
    web.run_app(start_server(), port=8000)
