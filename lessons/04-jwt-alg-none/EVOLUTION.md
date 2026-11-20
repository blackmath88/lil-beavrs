# Evolution — how Lesson 04 fits the arc

Like Lesson 03, this lesson is deliberately one deterministic capability (`recon.py`)
and one visual walk (`index.html`), with no agent rung. This file is the what-changed
spine — two axes meet here: the **access-control family** (01 → 03 → 04, the trust
failure getting subtler) and the **input-tampering family** (02 → 04, data vs.
declaration).

## Axis 1 — the trust failure gets subtler (01 → 03 → 04)

| | **01 · Broken Access Control** | **03 · IDOR** | **04 · JWT `alg:none`** |
|---|---|---|---|
| Integrity protection? | none — plain Base64 JSON | n/a — it's about *authorization* | **yes — a real HMAC signature** |
| What you control | the role you claim | the object you request | the *algorithm used to verify* you |
| What you change | `role` in a cookie | a number in a URL | `alg` in a token header |
| The missing control | sign/verify the role at all | check you own this object | pin the algorithm; don't trust the token's |
| One line | "no lock" | "the lock doesn't guard this door" | "you told the lock which key to use" |

01 and 04 are the same family — *don't trust client-controlled state* — seen at opposite
ends of effort. In 01 there is no integrity protection to defeat, so you simply edit the
JSON. In 04 the protection is present and cryptographically sound, so instead of breaking
it you **move the trust boundary**: the server believed the token's own claim about how it
should be checked. The HMAC key is never attacked. It is made irrelevant.

## Axis 2 — data vs. declaration (02 → 04)

Both SQL injection and `alg:none` are "input tampering," but at different layers:

| | **02 · SQL Injection** | **04 · JWT `alg:none`** |
|---|---|---|
| What you change | an input field's **value** | the token's **structure** (header `alg`) |
| What you break | the boundary between data and code | the boundary between *declaration* and *fact* |
| The oracle checks | does the DB return the flag | does the server skip the signature and admit you |
| Is the forged thing "legitimate"? | no — `admin' -- ` is not a valid username | **yes — a structurally perfect JWT, just `alg:none`** |
| Essence | not distinguishing data from code | not distinguishing "how I say to verify" from "how you must verify" |

SQL injection fools the parser with *data*. `alg:none` fools the server with a
*declaration*. The injected username is obviously illegitimate; the forged token is a
completely well-formed JWT — the spec even defines `none`. That legitimacy is what makes
it slip past review: nothing looks malformed.

## Why no agent rung

The forge set is a short, well-known list — `none`, the two-segment form, the `None`/
`NONE` casing dodges, the `HS256` empty-signature trick. There is no open candidate space
to rank or invent, so the bounded set in `recon.py` is the complete solution. As in
Lesson 03, bolting an agent on would be ceremony. The lessons that *do* carry an agent
(01, 02) are the ones whose candidate space is genuinely open.

## The oracle (and the forge signal)

`recon.py` never declares a win. Success has a single judge; the forge result is a
separate classification:

- **WIN oracle** — the flag regex `CyberZerk\{.*?\}`. The only thing that says "it worked."
- **Forge classification** — `REJECTED` (a correct verifier threw the token back:
  400/401/403 or an "invalid signature" tell), `ACCEPTED` (the forgery got in with no
  flag — the signature check was skipped), `BASELINE` (your real token), `CANDIDATE` (a
  variant not sent in the offline run).

The offline replay matches the captured tokens exactly, so the `None`/`NONE` casing
variants remain `CANDIDATE` rather than claiming wins we never observed — the same
honesty rule as Lesson 03's unfetched ids. Only the captured `alg:none` + `role:admin`
forgery returns the manager page, and only the WIN oracle calls it a win.
