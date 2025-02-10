print("<h1>All Pages</h1><ul>")

for page, route in pages.items():
    print(f"<li><a href='{route}'>{page}</a></li>")

print("</ul>")