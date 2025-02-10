show("""Hello World
this is a new page.
""")


show("Hello World")

show("<h1>All Pages</h1><ul>")

for page, route in pages.items():
    show(f"<li><a href='{route}'>{page}</a></li>")

show("</ul>")


respond()