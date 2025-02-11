import os
import re
import io
import asyncio
import json
import mimetypes
from aiohttp import web

###########################################
# Global Config & Base Directory
###########################################

global_config = {
    "server_name": "My Python Server"
}

# BASE_DIR is the directory where this script resides.
BASE_DIR = os.path.abspath(os.path.dirname(__file__))

###########################################
# File Access Helpers
###########################################

def is_path_allowed(rel_path: str) -> bool:
    """
    Do not allow serving any file or folder whose name starts with a dot or underscore.
    """
    parts = rel_path.split(os.sep)
    for part in parts:
        if part.startswith(".") or part.startswith("_"):
            return False
    return True

def is_folder_public(file_path: str) -> bool:
    """
    Walk up from the file’s folder. If any folder contains a marker file (".private"),
    then the file should not be served.
    """
    current = os.path.dirname(file_path)
    while current.startswith(BASE_DIR):
        if os.path.exists(os.path.join(current, ".private")):
            return False
        if current == BASE_DIR:
            break
        current = os.path.dirname(current)
    return True

def can_serve_file(file_path: str) -> bool:
    rel = os.path.relpath(file_path, BASE_DIR)
    return is_path_allowed(rel) and is_folder_public(file_path)

def resolve_file_path(url_path: str) -> str:
    """
    Converts a URL path (e.g. "/folder/file.json") to an absolute file system path.
    Returns None if the path is not within BASE_DIR.
    """
    # Remove any query string.
    url_path = url_path.split("?", 1)[0]
    if url_path.startswith("/"):
        url_path = url_path[1:]
    full_path = os.path.abspath(os.path.join(BASE_DIR, url_path))
    if not full_path.startswith(BASE_DIR):
        return None
    return full_path

def get_index_file(directory: str) -> str:
    """
    In a directory, look for an index file. (This can be static or dynamic.)
    For dynamic pages the file must start with "page_" and end with ".py".
    """
    # Try dynamic index pages first.
    for candidate in ["page_home.py", "page_index.py"]:
        candidate_path = os.path.join(directory, candidate)
        if os.path.exists(candidate_path) and can_serve_file(candidate_path):
            return candidate_path
    # Then try some common static index files.
    for candidate in ["index.html", "index.json", "index.zip"]:
        candidate_path = os.path.join(directory, candidate)
        if os.path.exists(candidate_path) and can_serve_file(candidate_path):
            return candidate_path
    return None

def directory_listing(directory: str, rel_dir: str) -> str:
    """
    Generate a simple HTML directory listing.
    """
    entries = os.listdir(directory)
    entries = [e for e in entries if is_path_allowed(e)]
    html = f"<html><head><title>Index of /{rel_dir}</title></head><body>"
    html += f"<h1>Index of /{rel_dir}</h1><ul>"
    # Link to parent directory if not at the base.
    if rel_dir and rel_dir != ".":
        parent = os.path.dirname(rel_dir)
        html += f'<li><a href="/{parent}">../</a></li>'
    for entry in entries:
        full_entry = os.path.join(directory, entry)
        rel_entry = os.path.join(rel_dir, entry) if rel_dir != "." else entry
        if os.path.isdir(full_entry):
            html += f'<li>[DIR] <a href="/{rel_entry}">{entry}/</a></li>'
        else:
            html += f'<li>[FILE] <a href="/{rel_entry}">{entry}</a></li>'
    html += "</ul></body></html>"
    return html

###########################################
# Dynamic Page Helpers
###########################################

def list_dynamic_pages() -> dict:
    pages = {}
    for root, dirs, files in os.walk(BASE_DIR):
        for file in files:
            if file.endswith(".py") and file.startswith("page_"):
                full_path = os.path.join(root, file)
                if can_serve_file(full_path):
                    # Get the relative directory of the file (if any)
                    rel_dir = os.path.relpath(root, BASE_DIR)
                    # Remove "page_" prefix and ".py" suffix from the file name.
                    base_name = file[len("page_"):-3]
                    # Combine folder path and base name if not in the base folder.
                    if rel_dir != ".":
                        page_name = f"{rel_dir}/{base_name}"
                    else:
                        page_name = base_name
                    pages[page_name] = os.path.relpath(full_path, BASE_DIR)
    return pages

def find_dynamic_page(page_name: str) -> str:
    """
    Look up a dynamic page by its name. For example, for page_name="about"
    this looks for a file named "page_about.py" anywhere under BASE_DIR.
    Returns the absolute path if found; otherwise, None.
    """
    pages = list_dynamic_pages()
    if page_name in pages:
        return os.path.join(BASE_DIR, pages[page_name])
    return None

###########################################
# Resources for Dynamic Pages
###########################################

class Resources:
    async def get_public_ip(self):
        # In a real server you might query an external service.
        return "127.0.0.1"
    
    async def list_routes(self):
        # Return the dynamic page names.
        return list(list_dynamic_pages().keys())

###########################################
# Templating Engine for Dynamic Pages
###########################################

import os
# Make sure BASE_DIR is defined globally (it is in our full server code)
# from earlier: BASE_DIR = os.path.abspath(os.path.dirname(__file__))

import os

# Ensure BASE_DIR is defined globally.
BASE_DIR = os.path.abspath(os.path.dirname(__file__))

async def process_template(template_str, env):
    """
    Processes template markers of the form {{ ... }}.

    Special handling:
      - Markers starting with ".\\" are treated as file references relative to BASE_DIR.
      - Markers starting with "./" are treated as file references relative to the current page's directory.
      - Markers starting with "..\\" are treated as file references (allowing upward traversal) relative to BASE_DIR.
      - Markers starting with "../" are treated as file references (allowing upward traversal) relative to the current page's directory.

    Any candidate file found is processed via render_page() and recursively scanned for template markers.
    Otherwise, markers are evaluated as Python expressions (with a fallback include for bare identifiers).
    """
    import re
    pattern = re.compile(r"\{\{\s*(.*?)\s*\}\}", re.DOTALL)

    async def repl(match):
        code = match.group(1).strip()
        candidate = None  # This will hold the absolute path if we detect a file reference.
        relative_path = None

        # Check for file-reference markers:
        if code.startswith(".\\"):
            # e.g. ".\pages\page_home_footer" -> relative to BASE_DIR.
            relative_path = code[2:]
            base = BASE_DIR
            candidate = os.path.abspath(os.path.join(base, relative_path))
        elif code.startswith("./"):
            # e.g. "./page_home_footer" -> relative to the current page directory.
            relative_path = code[2:]
            base = env.get("__page_dir__", BASE_DIR)
            candidate = os.path.abspath(os.path.join(base, relative_path))
        elif code.startswith("..\\"):
            # e.g. "..\subfolder\somefile" -> relative to BASE_DIR (allowing upward traversal)
            relative_path = code  # Keep the "..\\" in the path.
            base = BASE_DIR
            candidate = os.path.abspath(os.path.join(base, relative_path))
        elif code.startswith("../"):
            # e.g. "../subfolder/somefile" -> relative to current page directory (allowing upward traversal)
            relative_path = code  # Keep the "../" in the path.
            base = env.get("__page_dir__", BASE_DIR)
            candidate = os.path.abspath(os.path.join(base, relative_path))
        
        # If candidate was set by one of the above rules, try to include that file.
        if candidate is not None:
            # Security check: Ensure the candidate is within BASE_DIR.
            if candidate.startswith(BASE_DIR) and os.path.exists(candidate):
                try:
                    # Use render_page() to process the file.
                    sub_output, sub_env = await render_page(candidate, env["context"])
                    # Recursively process any template markers in the included file.
                    return await process_template(sub_output, sub_env)
                except Exception as e:
                    return f"[Error including file '{relative_path}': {e}]"
            else:
                return f"[Error: File '{relative_path}' not found or access denied]"

        # Otherwise, treat the marker as a Python expression.
        try:
            if code.startswith("await "):
                expr = code[6:].strip()
                result = await eval(expr, env)
            else:
                result = eval(code, env)
        except NameError as ne:
            # Fallback: if the marker is a bare identifier, try to include a file with that name.
            if code.isidentifier():
                page_dir = env.get("__page_dir__", BASE_DIR)
                candidate = os.path.join(page_dir, f"{code}.py")
                if os.path.exists(candidate):
                    sub_output, sub_env = await render_page(candidate, env["context"])
                    result = await process_template(sub_output, sub_env)
                else:
                    result = f"[Error: {ne}]"
            else:
                result = f"[Error: {ne}]"
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
    Load a dynamic page (a .py file whose name starts with "page_"),
    wrap its source in an async function (to allow await), and capture its output.
    """
    with open(file_path, "r", encoding="utf-8") as f:
        source = f.read()
    
    env = {}
    env["context"] = context
    output = io.StringIO()
    
    def captured_print(*args, **kwargs):
        print(*args, **kwargs, file=output)
    env["print"] = captured_print
    env["debug"] = print
    # Save the directory where the page resides to support includes.
    env["__page_dir__"] = os.path.dirname(file_path)
    
    wrapped_source = "async def __template_main__():\n"
    for line in source.splitlines():
        wrapped_source += "    " + line + "\n"
    
    exec(wrapped_source, env)
    await env["__template_main__"]()
    return output.getvalue(), env

###########################################
# Admin Interface Handlers
###########################################

async def admin_get(request):
    """
    Show an admin panel that includes:
      - A horizontal navigation bar built from the dynamic pages.
      - A form to update the server name.
      - A form to create a new dynamic page.
      - A list of dynamic pages with a delete button for each.
    """
    pages = list_dynamic_pages()
    nav_links = ""
    for page in pages:
        nav_links += f'<a style="margin-right:10px;" href="/{page}">{page}</a>'
    
    page_list = ""
    for page, rel_path in pages.items():
        page_list += f'''
        <li>
            {page} (File: {rel_path})
            <form style="display:inline;" action="/admin/delete" method="POST">
                <input type="hidden" name="file_path" value="{rel_path}">
                <input type="submit" value="Delete">
            </form>
        </li>
        '''
    html = f"""
    <html>
    <head>
      <title>Admin Panel</title>
    </head>
    <body>
      <h1>Admin Panel</h1>
      <div style="background:#eee; padding:10px; margin-bottom:10px;">
        <strong>Navigation:</strong> {nav_links}
      </div>
      
      <h2>Update Server Name</h2>
      <form action="/admin/update_server" method="POST">
        <input type="text" name="server_name" value="{global_config['server_name']}">
        <input type="submit" value="Update">
      </form>
      
      <h2>Create New Dynamic Page</h2>
      <form action="/admin/create_page" method="POST">
        Page Filename (must start with "page_", e.g., page_about.py):<br>
        <input type="text" name="page_name"><br>
        Content:<br>
        <textarea name="page_content" rows="10" cols="50"></textarea><br>
        <input type="submit" value="Create">
      </form>
      
      <h2>Existing Dynamic Pages</h2>
      <ul>
        {page_list}
      </ul>
    </body>
    </html>
    """
    return web.Response(text=html, content_type="text/html")

async def admin_update_server(request):
    data = await request.post()
    new_name = data.get("server_name", "").strip()
    if new_name:
        global_config["server_name"] = new_name
    raise web.HTTPFound("/admin")

async def admin_create_page(request):
    data = await request.post()
    page_name = data.get("page_name", "").strip()
    page_content = data.get("page_content", "")
    if not page_name:
        return web.Response(text="Page name required", status=400)
    # Enforce dynamic page naming.
    if not page_name.startswith("page_"):
        return web.Response(text='Dynamic page filename must start with "page_"', status=400)
    full_path = os.path.abspath(os.path.join(BASE_DIR, page_name))
    if not full_path.startswith(BASE_DIR):
        return web.Response(text="Invalid page name", status=400)
    if os.path.exists(full_path):
        return web.Response(text="File already exists", status=400)
    with open(full_path, "w", encoding="utf-8") as f:
        f.write(page_content)
    raise web.HTTPFound("/admin")

async def admin_delete_page(request):
    data = await request.post()
    rel_path = data.get("file_path", "").strip()
    if not rel_path:
        return web.Response(text="File path required", status=400)
    full_path = os.path.abspath(os.path.join(BASE_DIR, rel_path))
    if not full_path.startswith(BASE_DIR):
        return web.Response(text="Invalid file path", status=400)
    if os.path.exists(full_path) and can_serve_file(full_path):
        os.remove(full_path)
    raise web.HTTPFound("/admin")

###########################################
# Main Request Handler
###########################################

async def handle_request(request):
    """
    This handler maps URLs to files. It obeys these rules:
      - If the requested URL corresponds to a static file (or directory),
        serve it (with special handling for JSON and ZIP files).
      - If the file does not exist, try to resolve a dynamic page.
        Dynamic pages must be named with a "page_" prefix.
      - If the URL is "/" (empty), try to serve the dynamic home page:
          Prefer page_home.py; if not found, try page_index.py.
    """
    url_path = request.match_info.get("tail", "")
    
    # If no specific path was requested, try to serve the dynamic home page.
    if url_path == "":
        file_path = find_dynamic_page("home")
        if not file_path:
            file_path = find_dynamic_page("index")
        if not file_path:
            return web.Response(status=404, text="Home page not found.")
    else:
        file_path = resolve_file_path(url_path)
        # If the static file does not exist, try dynamic page resolution.
        if not file_path or not os.path.exists(file_path):
            file_path = find_dynamic_page(url_path)
            if not file_path:
                return web.Response(status=404, text="File not found")
    
    if not can_serve_file(file_path):
        return web.Response(status=403, text="Access Denied")
    
    # If a directory is requested, look for an index file or generate a listing.
    if os.path.isdir(file_path):
        index_file = get_index_file(file_path)
        if index_file:
            file_path = index_file
        else:
            rel_dir = os.path.relpath(file_path, BASE_DIR)
            listing = directory_listing(file_path, rel_dir)
            return web.Response(text=listing, content_type="text/html")
    
    ext = os.path.splitext(file_path)[1].lower()
    
    # For dynamic pages: only allow .py files that start with "page_"
    if ext == ".py":
        if not os.path.basename(file_path).startswith("page_"):
            return web.Response(status=403, text="Access Denied")
        context = {
            "config": global_config,
            "resources": Resources(),
            "routes": list(list_dynamic_pages().keys())
        }
        try:
            raw_output, env = await render_page(file_path, context)
            final_output = await process_template(raw_output, env)
            return web.Response(text=final_output, content_type="text/html")
        except Exception as e:
            return web.Response(status=500, text=f"Error rendering page: {e}")
    
    elif ext == ".json":
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
            return web.Response(text=content, content_type="application/json")
        except Exception as e:
            return web.Response(status=500, text=f"Error reading JSON: {e}")
    
    elif ext == ".zip":
        headers = {
            "Content-Disposition": f"attachment; filename={os.path.basename(file_path)}"
        }
        return web.FileResponse(file_path, headers=headers)
    
    else:
        return web.FileResponse(file_path)

###########################################
# Application Setup & Routes
###########################################

async def start_server():
    app = web.Application()
    
    # Admin routes.
    app.router.add_get("/admin", admin_get)
    app.router.add_post("/admin/update_server", admin_update_server)
    app.router.add_post("/admin/create_page", admin_create_page)
    app.router.add_post("/admin/delete", admin_delete_page)
    
    # Catch-all route.
    app.router.add_route("*", "/{tail:.*}", handle_request)
    return app

if __name__ == "__main__":
    web.run_app(start_server(), port=8000)
