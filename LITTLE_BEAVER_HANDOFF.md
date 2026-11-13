# Little Beaver — Project Handoff / Chat Offboarding

> A learning platform for the **Beaver (BEAVR)** framework — teaching *bounded execution*
> and *capabilities, not agents* by solving CTF challenges five ways, from manual to agent.
> Working name: **Little Beaver**. Repo: `github.com/blackmath88/lil-beavrs`.

This doc is the offboarding of the chat that built Lesson 1. It captures the vision, the
architecture, the teaching payload, the gotchas, and the open edges.

---

## 0. The vision

- **What it is:** a series. Each CTF challenge becomes a lesson with the same arc:
  **manual → script → recon → map → agent.** The flags aren't the point; the *way of
  building* is — some modules LLM-powered, the rest deterministic.
- **Why "Beaver":** it's the learning surface for the Beaver/BEAVR bounded-execution idea.
  The three-layer model *is* bounded execution made concrete: the probabilistic layer is
  fenced by deterministic ones, the type is the fence.
- **Lesson 1:** CyberZerk CTF · *Pointeuse Fantôme* — Broken Access Control (unsigned
  Base64 role cookie, forge `employe`→`manager`).

## 1. The journey (the lesson spine)

1. **Manual.** Decode the `profil` cookie, flip `role`, re-encode, submit → flag (DevTools).
2. **Level 0 · `01_solve_cli.py`.** Hardcoded exploit + a regex **oracle** (the only thing
   allowed to say "it worked"). Needs Cloudflare `cf_clearance` + matching UA for the live target.
3. **Recon · `recon.py`.** Decodes *any* cookie, detects encoding, flags identity/role keys,
   enumerates escalation candidates. Deterministic finds *shapes*, not *meaning*.
4. **Map · `05_recon_map.py`.** The linear stepper reframed as an attack-surface **node map**.
5. **Reasoning · `brain.py` (PydanticAI).** The LLM as a **typed module**: `deps` in,
   `Rank | Ask | Answer` out. Replaces fragile `parse_json()` with a validated contract. Adds
   a `planner` returning a ranked `Plan`, and `build_planner` (per-key factory).
6. **Agent · `agent.py`.** Streaming NDJSON console + ranked batch-fire on the map, stop at
   first flag, token-by-token thinking. LLM ranks the deterministic menu; the oracle judges;
   a human (or demo mode) fires.
7. **Story · `index.html`.** A scrollytelling lesson where the deterministic Python runs live
   in-browser via **Pyodide** against an in-page mock. LLM scene marked SIMULATION.

## 2. Architecture — the three-layer capability model

| Layer | File(s) | Property | Job |
|---|---|---|---|
| Data / Automation | `recon.py` | deterministic | decode, enumerate — find shapes |
| Reasoning | `brain.py` | probabilistic, **typed** | rank / judge — never decides success, never fires |
| Validation (Oracle) | regex in the app | deterministic | the **only** "it worked" |

Principle: **LLM proposes, oracle disposes, a human pulls the trigger.** PydanticAI maps on:
`output_type` = contract (write-back boundary), `deps` = projection (scoped state in, module
owns nothing), model-swap = replaceable runtime. The Ocean's-Eleven / library-not-backpack
argument, made runnable.

## 3. Key concepts (the teaching payload)

- **Broken Access Control / unsigned trust token.** Role lives in client-controlled, unsigned
  data → forgeable. A JWT's signature is what this cookie lacks. OWASP **A01**; CWE-565, 862, 639.
- **Discovery / execution / verification** kept apart — the recurring spine.
- **Deterministic menu, semantic order.** Candidates are a hardcoded wordlist; the LLM only
  *re-orders* them, it does not yet *invent* values. ← the honest limit.
- **The oracle must stay deterministic.** If the LLM judges its own success it hallucinates
  wins. Verification is a dumb regex the model can't talk past.
- **Knowledge lives in the app, not the model.** Patterns = injected context (projection),
  re-sent each call. Grows into a pattern library → a governed proposal→eval→promote loop.
- **Map when relational, list when records** (BloodHound/Maltego vs Burp).

## 4. Technical learnings & gotchas

- **pydantic_ai builds the provider at `Agent(...)` construction** → the API key must exist
  *before* construction. For BYOK per request → a **per-key agent factory** (`build_planner`,
  cached by key). Don't build the agent as a module global that needs a key at import.
- **`mistral-large` is a reasoning model**: on the raw `requests` path it returns `content`
  as a list of `thinking`/`text` blocks → needs a normalizer. **PydanticAI abstracts this
  away** — a reason to route through `brain.py`, not raw `requests`.
- **Version drift:** older pydantic_ai uses `result_type` (not `output_type`) and `res.data`
  (not `res.output`). Handle both.
- **Cloudflare `cf_clearance`** is bound to the IP **and** UA that solved the check — the
  script must run from the same machine/UA as the browser. The in-page mock sidesteps this for
  the lesson.
- **Pyodide** runs the pure-stdlib `recon.py` verbatim in-browser (~6 MB from jsdelivr on
  first open). `requests` is NOT available in Pyodide — "firing" hits the in-page mock.
- **Lab flag ≠ real flag.** The scrolly embeds a lab flag so it doesn't spoil the live
  challenge. Keep real flags (and `cf_clearance`, and keys) out of the public repo.
- **Streaming:** `agent.py` uses `ThreadingHTTPServer` + NDJSON so a long run doesn't block
  the UI; token-by-token thinking via `Agent.iter()` + `ThinkingPartDelta` (from v3), wired
  into v4's console.

## 5. Consolidation (done in Slice 1)

Two parallel lineages were merged into one app: **v3's backend** (dotenv secrets,
reasoning-model handling, token-by-token thinking, threading) + **v4's UI** (map + ranked
badges + streaming console + batch + demo mode) + the **per-key BYOK factory**, with
`brain.py` as the single typed reasoning module. Result: `agent.py`. The intermediate rungs
(`01…08`) are kept as the runnable journey; `index.html` is the story entry point.

## 6. Resources & references

- Thesis: bridge-work.ai/en/blog/from-agents-to-ai-capabilities · .../maybe-the-agent-shouldnt-own-the-memory
- Scrollytelling doctrine: github.com/blackmath88/scrollytelling
- Tooling: PydanticAI (pydantic-ai-slim[mistral]) · Pyodide (pyodide.org) · Mistral API
- JWT refs: forkbomb444/JWTweak · ticarpi/jwt_tool · DecodeThis
- Map lens: BloodHound · Maltego · Pixel-OS inspiration: DustinBrett/daedalOS
- Security framing: OWASP Top 10 A01 · CWE-565 / 862 / 639

## 7. Open edges (future lessons / next steps)

- **Semantic generation of candidates.** Let the planner propose novel role values / IDOR IDs
  instead of only re-ordering a hardcoded wordlist (the slow path of a two-speed model).
- **Governed pattern write-back.** New patterns become *proposals*; the oracle is the evidence
  gate before promotion → a growing deterministic library.
- **JWT path.** `recon.py` detects JWTs but doesn't forge them (alg:none, signature) — a
  natural Lesson 2/3.
- **Lesson 2+** = next CyberZerk challenge (e.g. the SQLi one, *L'SQL ou la cuisse?*).

## 8. Slice 2 (not yet built) — pixel-art seasonal homepage

A homepage with a **pixel-art autumn aesthetic** (reuse the falling-leaves canvas + sprites
from `04_recon_gui_autumn.py`), framing the **live Pyodide cells as an actual pixel-art
CRT/monitor** ("a real machine running real code"). Two dynamic ambience layers, both
pixel-art: (1) **monthly season** via a `SEASONS[month]` config; (2) **local weather** —
default ambience, and if the browser grants geolocation, fetch weather (open-meteo, no key)
and overlay matching pixel effects, degrading gracefully. Plain HTML/CSS/JS, self-contained,
reduced-motion friendly, with `// RESOURCE:` placeholders: `[PIXEL ART REF]`,
`[SEASONAL AMBIENCE REF]`, `[CRT FRAME REF]`.

---

*End of handoff.*
