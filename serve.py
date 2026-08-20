from http.server import SimpleHTTPRequestHandler, HTTPServer

class NoCache(SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header('Cache-Control', 'no-store, must-revalidate')
        super().end_headers()

HTTPServer(('', 8000), NoCache).serve_forever()