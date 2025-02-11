print("""<html>
<head><title>Home Page</title></head>
<body>
    <h1>Welcome to {{ context['config']['server_name'] }} Index Page.</h1>
    
    <h2>Available Pages:</h2>
    <ul>""")

for route in context['routes']:
    print(f'<li><a href="/{route}">{route}</a></li>')

print("""</ul>
    
    <section>
        {{  .\\page_home_footer.py }}
    </section>
</body>
</html>""")
