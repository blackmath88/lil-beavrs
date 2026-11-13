# 🦫 Little Beaver

A small learning platform for the **Beaver (BEAVR)** idea — *bounded execution* and
*capabilities, not agents* — taught by solving CTF challenges five ways, from doing it by
hand to a small typed agent. One arc, repeated per topic:

> **manual → script → recon → map → agent**

The flags aren't the point. The point is a way of building software where **some modules are
LLM-powered and the rest stay deterministic** — capabilities, not a magic agent. The
three-layer model below *is* bounded execution made concrete: the probabilistic layer is
fenced by deterministic ones, and the type is the fence.

## The three-layer capability model (every lesson)

| Layer | Property | Job |
|---|---|---|
| **Data / Automation** | deterministic | decode, enumerate — find the shapes |
| **Reasoning** | probabilistic, **typed** | judge / rank — never decides success, never fires |
| **Validation (Oracle)** | deterministic | the **only** thing allowed to say "it worked" |

**The LLM proposes, the oracle disposes, a human pulls the trigger.** In PydanticAI terms:
`output_type` = the contract (the write-back boundary), `deps` = the projection (scoped
state in, the module owns nothing), model-swap = replaceable runtime.

## Lessons

| # | Topic | Challenge | Folder |
|---|---|---|---|
| **01** | Broken Access Control | CyberZerk · *Pointeuse Fantôme* | [`lessons/01-broken-access-control/`](lessons/01-broken-access-control/) |

*(more coming — different topics, same arc)*

Each lesson ships an `index.html` scrollytelling page where the **deterministic Python
actually runs in your browser** (via [Pyodide](https://pyodide.org)) against an in-page mock
target. LLM scenes are marked **SIMULATION** — you run those for real with your own key using
the lesson's `.py` files.

```bash
# the story (no install): open the lesson's index.html, or serve it
cd lessons/01-broken-access-control && python3 -m http.server   # http://localhost:8000

# the real tools
pip install -r requirements.txt
cp .env.example .env        # add your MISTRAL_API_KEY
```

## Notes

- **Authorized targets only.** These lessons reproduce *authorized* CTF challenges in a local
  lab. Flags embedded in the demos are **lab flags**, never the live-platform flags.
- **No secrets in the repo.** `.env` is git-ignored; keys are read at runtime from `.env` or
  entered in the UI.

---

*Working method and the "capabilities, not agents" thesis:*
[from-agents-to-ai-capabilities](https://bridge-work.ai/en/blog/from-agents-to-ai-capabilities/) ·
[maybe-the-agent-shouldnt-own-the-memory](https://bridge-work.ai/en/blog/maybe-the-agent-shouldnt-own-the-memory/)
