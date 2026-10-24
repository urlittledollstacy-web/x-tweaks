"""Serve the X reading-tweaks filter list over HTTP, for testing before publishing.

Separate project from the filter-list server (port 12000) and the X floating bar
server (port 12001). Ports 12000 and 12001 are the only ones this sandbox exposes
to the internet, so this server defaults to 12002 and is reachable on
http://127.0.0.1:12002 only. That is deliberate: the list ships over the raw
GitHub URL in the README, which does not depend on the sandbox staying alive.

Reads the list from disk on every request, so edits need no restart.

Routes:
  /                       landing page
  /x-tweaks-brave.txt     the adblock list for brave://settings/shields/filters
"""
import http.server
import os
import socketserver

PORT = int(os.environ.get('X_TWEAKS_PORT', 12002))
HERE = os.path.dirname(os.path.abspath(__file__))

FILES = [
    ('x-tweaks-brave.txt',
     'Brave filter list',
     'Bigger tweet text and display names, an evenly spaced action row, a solid '
     'header, a roomier home feed, and a decluttered menu. This is the one to '
     'install.'),
]

TYPES = {
    '.txt': 'text/plain; charset=utf-8',
    '.html': 'text/html; charset=utf-8',
}


def landing():
    rows = []
    for name, title, desc in FILES:
        rows.append(
            '  <a class="card" href="/%s">\n'
            '    <h2>%s</h2>\n'
            '    <p>%s</p>\n'
            '    <code>/%s</code>\n'
            '  </a>\n' % (name, title, desc, name))
    return ('<!doctype html><html lang="en"><head><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width,initial-scale=1">'
            '<title>X reading tweaks</title><style>'
            'body{background:#15202b;color:#e7e9ea;font:16px system-ui,sans-serif;'
            'max-width:760px;margin:0 auto;padding:32px 20px}'
            'h1{font-size:24px;margin:0 0 4px}p.sub{color:#8b98a5;margin:0 0 28px}'
            'a.card{display:block;background:#1e2732;border:1px solid #2f3336;'
            'border-radius:12px;padding:16px 18px;margin:0 0 12px;'
            'text-decoration:none;color:inherit}'
            'a.card:hover{border-color:#1d9bf0}'
            'h2{font-size:17px;margin:0 0 6px;color:#1d9bf0}'
            'p{margin:0 0 10px;color:#e7e9ea}'
            'code{background:#000;padding:2px 6px;border-radius:4px;'
            'font-size:13px;color:#8b98a5}'
            '</style></head><body>'
            '<h1>X reading tweaks</h1>'
            '<p class="sub">Brave cosmetic filter list for x.com</p>\n'
            + ''.join(rows) + '</body></html>')


class Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        path = self.path.split('?', 1)[0]

        if path in ('/', '/index.html'):
            body = landing().encode('utf-8')
            ctype = 'text/html; charset=utf-8'
        else:
            name = path.lstrip('/')
            if name not in [f[0] for f in FILES]:
                self.send_error(404, 'Not found')
                return
            with open(os.path.join(HERE, name), 'rb') as fh:
                body = fh.read()
            ctype = TYPES.get(os.path.splitext(name)[1],
                              'application/octet-stream')

        self.send_response(200)
        self.send_header('Content-Type', ctype)
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt, *args):
        print('%s - %s' % (self.address_string(), fmt % args), flush=True)


class Server(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True


if __name__ == '__main__':
    with Server(('0.0.0.0', PORT), Handler) as httpd:
        print('serving %s on port %d' % (HERE, PORT), flush=True)
        httpd.serve_forever()
