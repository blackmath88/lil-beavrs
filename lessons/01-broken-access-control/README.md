# Lesson 01 — Broken Access Control

CyberZerk CTF · *Pointeuse Fantôme*. A timekeeping app trusts a cookie that says who you
are. The cookie is unsigned Base64 JSON — so you rewrite your role and become a manager.

**Start with the story:** open [`index.html`](index.html) — the deterministic steps run
live in your browser (via Pyodide, against an in-page mock). Then run the real files below.

**Why isn't this whole class of bug just solved by the browser, the CDN, or a smarter agent?** See the companion essay [`WHY-NOT-SOLVED.md`](WHY-NOT-SOLVED.md).

## The arc: manual → script → recon → map → agent

The lesson is a progression you can run stage by stage. Each file is one rung:

| File | Rung | What it is |
|---|---|---|
| [`01_solve_cli.py`](01_solve_cli.py) | manual → script | Level 0: the hardcoded exploit + the regex **oracle** (argv-based, public-safe) |
| [`02_solve_gui.py`](02_solve_gui.py) | script (GUI) | the same exploit in a local web UI |
| [`03_recon_gui.py`](03_recon_gui.py) | recon | nothing hardcoded — `recon.py` derives the exploit live |
| [`04_recon_gui_autumn.py`](04_recon_gui_autumn.py) | recon (skinned) | same logic, the 5 stages made visible |
| [`05_recon_map.py`](05_recon_map.py) | map | linear stepper → interactive attack-surface graph |
| [`06_agent_byok.py`](06_agent_byok.py) | agent (v1) | first LLM layer — fragile `parse_json()` |
| [`07_agent_typed.py`](07_agent_typed.py) | agent (v2) | typed contract via `brain.py` — hope → guarantee |
| [`08_agent_console_batch.py`](08_agent_console_batch.py) | agent (v3) | live thinking stream + ranked batch search |
| **[`agent.py`](agent.py)** | **agent (final)** | **the consolidated app: v3's streaming thinking in v4's map UI, demo mode, per-key BYOK** |

The two shared **capabilities** (imported by name):

| File | Property | Job |
|---|---|---|
| [`recon.py`](recon.py) | deterministic | decode any cookie, find identity/role levers, enumerate escalations |
| [`brain.py`](brain.py) | probabilistic, **typed** | `advise()` (one lever) + `planner`/`plan_stream` (rank all, streaming) + `build_planner` (per-key) |

See [`EVOLUTION.md`](EVOLUTION.md) for the full step-by-step story.

## Run

```bash
pip install -r ../../requirements.txt
cp ../../.env.example ../../.env   # add your MISTRAL_API_KEY

# Level 0 — against the live challenge (needs a fresh cf_clearance from your browser)
python3 01_solve_cli.py "<cf_clearance>"

# Recon — decode + map the levers (no network, no key)
python3 recon.py

# The consolidated agent — open http://127.0.0.1:8780
python3 agent.py
```

**`agent.py` demo mode:** leave `cf_clearance` empty and fires are mocked; leave the UI key
field empty and it uses `MISTRAL_API_KEY` from `.env`. So the whole UI runs offline. With a
key it ranks semantically and streams its live thinking; with `cf_clearance` it fires for real.

## The concepts

- **Unsigned trust token.** Role lives in client-controlled, unsigned data → forgeable.
  (A JWT's signature is the thing this cookie is missing. OWASP A01 · CWE-565 / 862 / 639.)
- **Discovery / execution / verification** kept apart. The oracle is the only judge.
- **Deterministic finds shapes, the LLM supplies meaning.** Recon enumerates; the LLM ranks.
- **Capabilities, not a persona.** Reasoning is one typed module among deterministic ones —
  the probabilistic layer is fenced by deterministic ones on both sides.

## The open edge

The candidate wordlist in `recon.py` is **hardcoded**. The intelligence only *re-orders* a
fixed list — it doesn't yet *invent* values. Letting the planner generate its own candidates
(novel roles, IDOR IDs) is where this lesson points next.
