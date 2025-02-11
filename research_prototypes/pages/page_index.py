print("""<html>
<head><title>Home Page</title></head>
<body>
    <h1>Welcome to {{ context['server_name'] }}</h1>
    
    <h2>Available Pages:</h2>
    <ul>""")

for route in context['routes']:
    print(f'<li><a href="/{route}">{route}</a></li>')

print("""</ul>
    
    <section>
        {{  page_home_footer }}
    </section>
</body>
</html>""")
