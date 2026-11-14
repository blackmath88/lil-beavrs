# Lesson 02 — SQL Injection

CyberZerk CTF · *Tricatel-Cyber HR Portal*. A burnt-out dev builds the login at 4 a.m. and
glues the username straight into a SQL query. You close the string with an apostrophe and
comment out the password check — logging in as admin with no password.

> **Status: scaffold in progress.** Built so far: the **recon** rung + a visual map.
> The rest of the arc follows step by step.

## The arc: manual → script → recon → map → agent

| File | Rung | What it is | Built |
|---|---|---|---|
| `01_solve_cli.py` | manual → script | the hardcoded `admin' -- ` exploit + the flag **oracle** | ☐ planned |
| `recon.py` | recon | derive it live: parse form, fingerprint stack, baseline, fire a fixed probe set, classify | ☑ **done** |
| `index.html` | map | the recon result as a visual attack-surface map | ☑ **done** |
| `brain.py` / agents | agent | a typed LLM layer that *ranks* probes; the oracle still judges | ☐ planned |

## The capability — `recon.py`

Deterministic data layer. Finds shapes, never declares success.

1. **Form probe** — parse `<form>`: method, action, input names.
2. **Fingerprint** — `PHPSESSID` ⇒ PHP; `via: Caddy`.
3. **Baseline + oracle** — one benign failed login defines the LOSE signal (`ERR_AUTH`); WIN = `CyberZerk{…}`.
4. **Fixed probe set** — benign · lone `'` · `admin' -- ` · `' OR '1'='1' -- ` · `admin'#`. Each fired once.
5. **Classify** — `BASELINE / SAME / DIFFERENT / WIN / CANDIDATE` against the baseline through the oracle.

**Unlike Lesson 01, recon here is *active*.** Broken-access-control recon decodes a cookie you
already hold (zero network). SQLi behaviour only exists when you poke the server, so `recon.py`
injects a `fire` dependency: live mode sends real requests; the `__main__` demo replays **real
captured responses** — no network, no key.

## Run

```bash
python3 recon.py          # offline demo on real captured responses (no install)

# live, against the authorized instance (needs `requests`):
python3 -c "import recon; recon.report(recon.recon())"
```

Open [`index.html`](index.html) for the visual map.

## Background

Classic SQL-injection payloads, taxonomy, defenses, and references:
[`SQLI-CLASSICS.md`](SQLI-CLASSICS.md).

## Scope

Authorized CTF instance only. Fixed, tiny probe set — no fuzzing, no wordlists, no spidering.
recon **classifies**; the **oracle** alone says WIN; one pass, then stop.
