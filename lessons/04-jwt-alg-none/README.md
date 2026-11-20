# Lesson 04 — JWT `alg:none` (algorithm confusion)

CyberZerk CTF · *Tricatel-Cyber Manager Area*. You hold a signed session token that
says `role: employe`. The token is a real JWT with an HMAC-SHA256 signature — integrity
protection *exists* this time. But the server reads **which algorithm to verify with
from the token's own header**, and trusts it. Set `alg: none`, flip `role` to `admin`,
strip the signature, and the server treats the token as already verified.

> **Status: the lesson runs.** `recon.py` decodes the held token, forges the fixed set
> of algorithm-downgrade variants offline against the two real captured responses, and
> confirms the bypass; `index.html` is the visual walk. Like Lesson 03 it has no agent
> rung — the forge set is a handful of known variants, not a search space.

## The vulnerability in one line

The token is signed, so the server *could* verify it — but it asks the token **how** to
verify, and the token is allowed to answer "don't." `alg: none` is a legal (if
deprecated) JWT value meaning "unsecured"; a verifier that honours it skips the
signature check entirely. You never forged a signature. You changed the server's
*instructions for how to check one*.

```
held   : {"alg":"HS256","typ":"JWT"} . {"user":"employe8472","role":"employe"} . <HMAC>
forged : {"alg":"none" ,"typ":"JWT"} . {"user":"employe8472","role":"admin"  } .          ← empty sig, trailing dot
         curl -H 'Cookie: session=<forged>' https://manager.cyberzerk.fr
CyberZerk{JWT_4lg_N0n3_C_3st_N0n}
```

## Where it sits in the arc — the trust failure gets subtler

| Lesson | The protection | What the dev got wrong | One line |
|---|---|---|---|
| 01 · Broken Access Control | none (plain Base64 cookie) | added no integrity protection at all | "no lock" |
| 03 · IDOR | auth, but no per-object check | authenticated you, never checked you own the object | "the lock never checks this door" |
| **04 · JWT `alg:none`** | **a real HMAC signature** | **trusted the token's declaration of *how* to verify** | **"you told the lock which key to use, and it believed you"** |

01 is "no lock." 03 is "the lock exists but doesn't guard this door." 04 is the subtlest:
the lock is real and signed, but the attacker controls the *declaration* of how it should
be checked. See [`EVOLUTION.md`](EVOLUTION.md) for the full what-changed spine, including
how this differs from SQL injection (data vs. declaration).

## The capability — `recon.py`

Deterministic data layer, same role as Lessons 01-03: it finds shapes and classifies
behaviour; it **never** declares success — the WIN oracle is the single judge of success.
Here "recon" is a **bounded set of algorithm-downgrade forgeries**, not a payload ladder:

1. **Decode the held token** — header (`alg`), payload (`role`), signature, with stdlib
   base64/json. No crypto library needed; that's the point — you're not breaking the
   HMAC, you're removing the requirement to have one.
2. **Name the lever** — the server trusts `header.alg`; the privilege lives in
   `payload.role`.
3. **Forge a fixed set** — `alg:none` with a trailing dot, the two-segment form, the
   `None` / `NONE` casing dodges, and an `alg:HS256` empty-signature trick. One request
   each. Never a fuzzer.
4. **Classify** — `BASELINE / WIN / ACCEPTED / REJECTED` (plus `CANDIDATE` for a variant
   not sent offline), through the oracle. `WIN` = the flag regex fires; `REJECTED` = a
   correct verifier threw the forgery back; `ACCEPTED` = the forgery got in even without
   a flag (the signature check was skipped).

Like Lesson 02, the network call is an injected dependency (`send`): live mode posts each
forged token as the `session` cookie with `requests`; the `__main__` demo replays the two
**real captured responses** (the original verifies as *employe*; the `alg:none` forgery is
accepted as *manager* with the flag) — no network, no key, just runs. The offline replay
matches the captured tokens **exactly**, so the `None`/`NONE` casing variants stay
`CANDIDATE` (untested here) rather than pretending they won.

## Why there is no agent rung here

Like IDOR, this has almost no search space: a short, well-known list of `alg:none`
variants. The bounded forge set in `recon.py` *is* the solution; there is nothing for a
model to rank or invent. Reaching for the smallest capability that solves the problem —
and stopping — is the series' thesis: **capabilities, not agents.** (Lessons 01 and 02,
where the candidate space is open, are where the fenced LLM advisor earns its place.)

## Run

```bash
python3 recon.py          # offline demo: decode, forge the set, classify

# live, against the authorized instance (needs `requests`):
python3 -c "import recon; recon.report(recon.recon())"
```

Open [`index.html`](index.html) for the visual walk.

## The fix (what the server should have done)

- Pin the accepted algorithm(s) server-side (`HS256` only); never read `alg` from the token.
- Reject `alg:none` before any other processing.
- Treat a zero-length or absent signature as a verification failure, not a pass.

## Scope

Authorized CTF instance only. Fixed, tiny forge set — no key cracking, no fuzzing, no
wordlists. recon **classifies**; the **oracle** alone says WIN; one pass, then stop. The
token and flag are LAB-only.
