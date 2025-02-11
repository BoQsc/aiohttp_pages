

# Pure Python templating
# Example page script (page_home.py)
print("""<html>
<head><title>Home Page</title></head>
<body>
    <h1>Welcome to {{context['server_name']}}</h1>
    
    <h2>Available Pages:</h2>
    <ul>""")

for route in context['routes']:
    print(f'<li><a href="/{route}">{route}</a></li>')


# importing pages or parts, the {{  page_home_footer }} is mapping to page_home_footer.py in the current directory, but could be anywhere nested too and should not care.
print("""</ul>
    
    <section>
        {{  page_home_footer }}
    </section>
</body>
</html>""")



# In page script
public_ip = await context.resources.get_public_ip()

# In page script
routes = await context.resources.list_routes()

async def list_content_current_files():
    for file in await context.resources.list_content():
        print(f'<li><a href="/{file}">{file}</a></li>')


# Example page script (page_about.py)
print("""<h1>About Us</h1>
<p>Server Version: {{ context.config.server_name }}</p>
<p>Public IP: {{ await context.resources.get_public_ip() }}</p>

<h2>Available Content:</h2>
""")

print("""
<ul>
    {{ await list_content_current_files() }}
</ul>
""")


# debug("Hello World") might be used for actual print() original behaviour.