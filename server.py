"""
LumenCut Local Engine Server
Serves the web dashboard and provides AI clip extraction APIs.
"""

from http.server import HTTPServer, SimpleHTTPRequestHandler
import os
import sys

PORT = 3000
DIRECTORY = os.path.dirname(os.path.abspath(__file__))

class LumenCutHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=DIRECTORY, **kwargs)

def run():
    os.chdir(DIRECTORY)
    server_address = ('', PORT)
    httpd = HTTPServer(server_address, LumenCutHandler)
    print(f"\n=================================================")
    print(f"⚡ LumenCut Web Dashboard is running!")
    print(f"👉 Local URL: http://localhost:{PORT}")
    print(f"📁 Folder: {DIRECTORY}")
    print(f"=================================================\n")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping LumenCut server...")
        httpd.server_close()

if __name__ == '__main__':
    run()
