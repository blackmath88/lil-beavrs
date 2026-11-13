# Evolution — how Lesson 01 was built

This lesson grew from a one-line hardcoded exploit into a typed, LLM-assisted agent. Every
rung is a standalone, runnable file — nothing was collapsed, so you can run any stage and see
the progression. The scrollytelling [`index.html`](index.html) tells the same story for
readers; these files are for doers who want to run each stage.

## The two shared capabilities (imported by name — keep these names)

- **`recon.py`** — the deterministic recon capability. `classify(cookie_name, value)` →
  structured finding: encoding, decoded content, and "levers" (role fields with ready-made
  escalation mutations; identity fields flagged as IDOR). Candidate wordlist is fixed:
  `manager, admin, administrator, root, superuser, true, 1`.
- **`brain.py`** — the reasoning capability as a typed PydanticAI module: `advise()` (pick one
  lever → validated `Rank | Ask | Answer`), `planner` / `plan_stream()` (rank *all*
  candidates, streaming the model's live thinking), and `build_planner()` (a per-key factory
  so the app can do BYOK while `brain.py` stays the single reasoning module). On `mistral-large-4`.

## The rungs

### `01_solve_cli.py` — Level 0: the hardcoded exploit
The whole idea in ~15 lines. A forged `profil` cookie (`role=manager`) is sent by hand; a
regex is the **oracle** — the only thing allowed to say "it worked." Takes `cf_clearance` as
an argument (public-safe; no secrets baked in). *Run:* `python3 01_solve_cli.py "<cf_clearance>"`

### `02_solve_gui.py` — the same exploit, as a local GUI
Wraps Level 0 in a tiny local web UI (port 8777). Still fully hardcoded. The request leaves
*your* machine, so Cloudflare accepts your `cf_clearance`.

### `03_recon_gui.py` — nothing hardcoded anymore
First use of `recon.py`. The GUI decodes the cookie live, shows the discovered levers, and
lets you fire a chosen mutation. The exploit is now *derived*, not baked in. (port 8777)

### `04_recon_gui_autumn.py` — the same logic, made legible
Identical behaviour, but the five stages (Cookie → Decode → Lever → Fire → Flag) are visible
pixel tiles that light up as you go. Autumn-leaf skin. Pure UX. (port 8777)

### `05_recon_map.py` — from stepper to attack-surface map
Re-frames recon as an interactive **node graph** (JSON API `/api/recon`, `/api/fire`) instead
of a linear form — the BloodHound lens: show relationships, don't list records. (port 8777)

### `06_agent_byok.py` — the first LLM layer (v1)
Adds a copilot drawer on the map. BYOK Mistral ranks the levers; the human fires. **Fragile
internals**: raw `requests` to the chat API + a hand-rolled `parse_json()` that *hopes* the
model returned valid JSON. (port 8777)

### `07_agent_typed.py` — the typed contract (v2)
Swaps the LLM internals for **`brain.py`**. `parse_json()` / `call_llm()` deleted. Output is a
validated `Rank | Ask | Answer` — off-contract output raises `ValidationError` instead of
leaking through. Hope → guarantee. (port 8778)

### `08_agent_console_batch.py` — see it think, search instead of guess (v3)
Driven by one question: *are the picks actually intelligent?* They were a cold one-shot guess
off a fixed list. Now: a **live console** streaming the model's token-by-token **thinking**,
and **ranked batch auto-fire** (rank all, fire in order, stop at first flag). Guess →
feedback-driven search. (port 8779)

### `agent.py` — the consolidation (final)
The version to run. v4's self-contained map UI (ranked badges, streaming console, demo mode,
per-key BYOK factory, `ThreadingHTTPServer`) **+** v3's token-by-token thinking, routed
through `brain.py` so reasoning lives in exactly one module. Demo mode: empty `cf_clearance`
mocks the fires, empty UI key uses `.env` — the whole UI runs offline. (port 8780)

## Setup

```bash
pip install -r ../../requirements.txt   # requests · pydantic-ai-slim[mistral] · python-dotenv
cp ../../.env.example ../../.env         # add MISTRAL_API_KEY
```

- Steps **01–05** need no API key (deterministic only).
- Steps **06–08** and `agent.py` load the key from `.env` (must exist *before* import —
  PydanticAI builds the Mistral provider at agent-construction time).
- Ports: 01 is CLI; 02–06 share 8777 (run one at a time); 07=8778, 08=8779, `agent.py`=8780.
