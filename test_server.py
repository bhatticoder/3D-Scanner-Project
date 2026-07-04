import os, urllib.parse, http.server, threading
APP_DIR = "g:/app"
glb_bytes = b"fake glb"
js_files = {}
for js_name in ("three.min.js", "OrbitControls.js", "GLTFLoader.js"):
    js_path = os.path.join(APP_DIR, js_name)
    if os.path.exists(js_path):
        js_files[f"/{js_name}"] = open(js_path, "rb").read()

html = """<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <title>3D Viewer</title>
</head>
<body>
  <div id="container"></div>
  <script src="/three.min.js"></script>
  <script src="/OrbitControls.js"></script>
  <script src="/GLTFLoader.js"></script>
  <script>
    console.log("THREE:", typeof THREE);
    console.log("OrbitControls:", typeof THREE.OrbitControls);
    console.log("GLTFLoader:", typeof THREE.GLTFLoader);
  </script>
</body>
</html>"""
html_bytes = html.encode("utf-8")

class _Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        p = urllib.parse.urlparse(self.path).path
        if p in ("/", "/index.html"):
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers(); self.wfile.write(html_bytes)
        elif p in js_files:
            self.send_response(200)
            self.send_header("Content-Type", "application/javascript")
            self.end_headers(); self.wfile.write(js_files[p])

httpd = http.server.HTTPServer(("127.0.0.1", 8081), _Handler)
threading.Thread(target=httpd.serve_forever, daemon=True).start()
import time; time.sleep(1)
