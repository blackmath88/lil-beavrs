# Lesson 03 — IDOR (Insecure Direct Object Reference)

CyberZerk CTF · *Tricatel-Cyber absence portal*. You are logged in as Employé **#8472**
and can read your own leave request. A colleague went on sick leave yesterday after
unbearable pressure from management — his file sits right before yours. The whole
exploit is one keystroke: change `?dossier_id=1042` to `?dossier_id=1041`.

> **Status: the lesson runs.** `recon.py` performs the bounded enumeration offline
> against the two real captured dossiers and confirms the broken authorization;
> `index.html` is the visual walk. No agent rung — and that absence is the point
> (see below).

## The vulnerability in one line

The server **authenticated** you (it knows you are #8472) and then never
**authorized** the request (it never checked that #8472 is allowed to read dossier
1041). Authentication ≠ authorization. The object reference is a plain sequential
integer in the URL, and it is not bound to your identity — so you pick the number.

```
?dossier_id=1042   → your own file   (Demande de Congés · REFUSÉ)
?dossier_id=1041   → NOT yours        (Arrêt Maladie · SECRET MÉDICAL) → flag
CyberZerk{ID0R_M4n4g3m3nt_T0x1qu3}
```

## Where it sits in the arc — effort goes *down*, not up

| Lesson | Family (OWASP) | What you touch | Effort |
|---|---|---|---|
| 01 · Broken Access Control | A01 | **forge** a credential you hold (the `profil` cookie) | decode + edit |
| 02 · SQL Injection | A03 | **craft** a payload the parser mis-reads (`admin' -- `) | probe the input |
| **03 · IDOR** | **A01** | **nothing** — you change a number already in the URL | one keystroke |

IDOR is the lowest-effort member of the Broken Access Control family: no forging, no
crafting, no tooling. That is exactly why it is one of the most common real-world bugs
— there is nothing to *defeat*, only an authorization check the developer never wrote.
See [`EVOLUTION.md`](EVOLUTION.md) for the full what-changed spine.

## The capability — `recon.py`

Deterministic data layer, same role as Lessons 01 & 02: it finds shapes and
classifies behaviour; it **never** declares success — the WIN oracle is the single
judge *of success*. (The LEAK **rule** below is a separate thing: a classifier for
*access*, not a second success judge.) Here "recon" is a **bounded enumeration**,
not a payload ladder:

1. **Hold the reference** — the URL carries `?dossier_id=<int>`, a *direct* object
   reference, and it is not bound to the session.
2. **Note the grant** — we are #8472; the file legitimately linked to us is `1042`.
3. **Walk neighbouring ids** — a tiny fixed range (`1042, 1041, 1040, 1039`), one
   request each. Never a fuzzer.
4. **Classify** — `OWN / LEAK / SCOPED / MISSING` (plus `CANDIDATE` for an id in the
   walk that wasn't fetched offline). A **LEAK** is the access-control *rule* modelling
   the check the server forgot: any id *outside our grant* that still returns
   `200 + content` should have been a `403`.

Like Lesson 02, the network call is an injected dependency: live mode uses `requests`
with your authenticated session cookie; the `__main__` demo replays the **real
captured responses** for dossiers 1041 and 1042 — no network, no key, just runs.

## Why there is no agent rung here

Lessons 01 and 02 climb toward a fenced LLM advisor because they have a *search space*
— which cookie field, which injection payload, which mechanism class. IDOR has a
search space of **size ~1**: one reference, and its integer neighbours. There is
nothing for a model to rank, invent, or interpret; the bounded enumeration *is* the
whole solution. Adding an agent would be pure ceremony. Reaching for the smallest
capability that solves the problem — and stopping — is the series' whole thesis:
**capabilities, not agents.**

## Run

```bash
python3 recon.py          # offline demo: the walk, classified against the grant

# live, against the authorized instance (needs `requests` + your session cookie):
ABSENCES_COOKIE="SESSION=..." python3 -c "import recon; recon.report(recon.recon())"
```

Open [`index.html`](index.html) for the visual walk.

## Scope

Authorized CTF instance only. Fixed, tiny id range — no enumeration sweeps, no
wordlists, no spidering. recon **classifies**; the **oracle** alone says WIN; one
pass, then stop. The leaked dossier is lab content; the flag is LAB-only.
