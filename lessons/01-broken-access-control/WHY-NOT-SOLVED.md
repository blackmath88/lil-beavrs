# Why Isn't Broken Access Control Solved? — A Red-Team Perspective

*Companion essay to Lesson 01 (Broken Access Control).*

Broken Access Control has sat at or near the top of the OWASP Top 10 for over a decade,
and its API-world twin — **BOLA**, Broken Object Level Authorization — is **#1 on the OWASP
API Security Top 10**. We just forged a cookie by hand and walked `employe → manager` in
sixty seconds. So the obvious question, the one a red-teamer and a governance person both
ask: *why can't this just be caught and blocked — by the browser, the CDN, the platform,
or a smart enough coding agent?*

The honest answer is that it's the one vuln class **infrastructure structurally cannot own**,
and understanding *why* tells you where the real fix lives.

## 1. It's a layer problem, not a laziness problem

SQL injection and XSS have a **shape** — a recognizable malicious payload — so a WAF can
pattern-match them. Broken Access Control has no shape. The legitimate request and the attack
are **byte-for-byte identical**: `GET /record?id=5` is fine for user 5 and an attack for
user 8. Same URL, same method, same everything.

To judge it, you need three things that live only inside the application: **who** this user
is in the app's model, **what** they're allowed, and **who owns** the object. None of that is
in the bytes on the wire. So:

- **The browser can't.** It's the attacker's own tool. Asking it to block IDOR is asking the
  attacker's tool to refuse to help the attacker. It has no idea what the server's rules are.
- **A WAF / CDN can't** (and it isn't a compute problem). It's a *missing-information* problem:
  the authorization policy isn't written anywhere the infrastructure can read. Give it the
  policy and the check is cheap; the policy just doesn't exist in machine-readable form.
- **The TLS-cert analogy breaks.** A cert works because server *identity* is a universal fact
  with a shared PKI — everyone agrees what "this is really the bank" means. Authorization has
  **no shared PKI**. "Employee #8472 may not see the manager register" is an ontology private
  to one app, living only in a developer's intent. You can't issue a "your authz is correct"
  certificate, because nobody but you knows what *correct* means here.

> The flaw is **intent-relative application logic**. Infrastructure acts on *shapes it can
> see*; this bug is pure *meaning*.

## 2. The edge doesn't save you either

"But I deploy through a Cloudflare Worker — doesn't that help?" A Worker is **your own code**
running at the edge. Cloudflare executes whatever you deploy; it doesn't audit your Worker's
authorization logic. The vulnerable app can *be* the Worker.

What the edge genuinely offers is a **place to enforce policy you declare** — Cloudflare
[API Shield](https://developers.cloudflare.com/api-shield/): upload an API
[schema](https://developers.cloudflare.com/api-shield/products/schema-validation/) and it
validates requests against it; do JWT validation, mTLS, and sequence/anomaly detection that
flags some BOLA-like patterns. But note the direction: **you declare, it enforces.** It can't
*infer* the policy you didn't write, and it can't express object ownership unless you encode
it. Same missing-information problem, one layer out. If anything, the Worker is a fine place
to *put the fix* (edge authorization) — but that's you writing the check, not the platform
detecting its absence. Nobody refuses to deploy a Worker because it contains an IDOR.

## 3. Why "smarter coding agents" won't kill it

The tempting conclusion: AI writes the code now, and AI won't make this mistake. Near-term,
expect the opposite — more BAC, not less, for structural reasons:

- **The shortest path to working code is the vulnerable one.** "Read `role` from the cookie,
  check it" is less code than "centralize authz, deny by default." Agents optimize for code
  that *works* — and the IDOR version works perfectly on the happy path. The bug is invisible
  to "does it run."
- **It's an omission, not a commission** — the check you *didn't* write. Models are good at
  adding present things, weak at guaranteeing absent ones are handled. "Did *every* endpoint
  get an ownership check?" is a global property; next-token generation is weakest at those.
- **Agents ship more surface, faster.** More endpoints → more places to forget the check.
- **The training prior leans insecure** — tutorials are full of "trust the token."

And the deeper correction: **a smarter agent can't fix this, because it lacks your
authorization intent for the same reason Cloudflare does.** It can *enforce a policy you
declared*; it cannot *invent the right one*, because "who should see what" isn't in the
code — it's in your head. "The agent will know better" is the same category error as
"the CDN will catch it." Neither holds the intent.

The real variable isn't model IQ — it's the **default scaffold**. An agent is an *amplifier*:
point it at an insecure-by-default stack and you get IDORs faster; point it at one where
deny-by-default, a policy engine, and abuse-case tests are the path of least resistance, and
the easy thing becomes the safe thing.

## 4. What actually moves the needle — express the intent

BAC shrinks when someone **writes the authorization intent down** in a form both humans and
machines can enforce. The stack that does this:

- **Externalize authorization as policy-as-code**, so authz stops being scattered `if`
  statements per endpoint and becomes one declared, testable truth:
  - [Open Policy Agent (OPA)](https://www.openpolicyagent.org/) — general policy engine
  - [Google Zanzibar](https://research.google/pubs/zanzibar-googles-consistent-global-authorization-system/)
    ([USENIX ATC '19](https://www.usenix.org/conference/atc19/presentation/pang)) and its
    lineage: [OpenFGA](https://openfga.dev/), [SpiceDB](https://authzed.com/spicedb) —
    relationship-based access control ("who is related to this object, how")
  - [AWS Cedar](https://www.cedarpolicy.com/) / Amazon Verified Permissions
- **Deny-by-default** at the framework layer, and per-object checks, not per-route.
- **Abuse-case tests in CI** — negative authorization tests that assert a low-priv user gets
  `403`. Pair with [Burp Autorize](https://portswigger.net/bappstore/f9bbac8c4acf4aefa4d7dc92a991af2f),
  which replays requests under a low-priv session and flags where the response is the same.
- **Production monitoring as a net** — API-security tooling that learns access patterns and
  flags BOLA anomalies. Heuristic, false-positive-prone, *not* a guarantee — because it's
  still inferring a policy no one wrote.

See also the OWASP
[Authorization Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Authorization_Cheat_Sheet.html).

## 5. The governance read

Every platform-level answer fails for the same reason: **none of them can refuse to host or
deploy the *flaw*, because the flaw is intent-relative logic they can't read.** What they
*can* police are concrete, universal facts — a leaked credential (GitHub secret scanning), a
live attack from their infra (observable traffic). Never the *meaning* only your org holds.

This is the James-Bond-vs-Ocean's-Eleven split. "A smarter agent will handle it" is the Bond
fantasy — one brilliant actor who simply doesn't err. The durable answer is the ensemble: the
agent writes the feature, a **policy engine owns authorization**, abuse-case tests verify,
deny-by-default is the frame. BAC doesn't die because the center got smarter. It shrinks when
someone writes the intent down — and once it's written, the agent *and* the infrastructure can
both enforce it.

That "write the intent down, make the safe pattern the default" work is not a dying thing.
It's the enduring job. Agents just raise the stakes on whether the default you hand them is
the safe one.

## For the red-teamer

The flip side explains why access-control testing stays stubbornly **manual and semantic**.
Scanners find shapes; this bug is meaning, so a human (or an intent-carrying agent) has to
hypothesize the *intended* policy and probe for violations of it. Tools surface candidates —
you decide. That's the same discovery/execution split this whole lesson is built on: the
deterministic layer enumerates, something that holds the *intent* judges.

- Practice: [PortSwigger — Access control vulnerabilities](https://portswigger.net/web-security/access-control)
- Classify: CWE-[639](https://cwe.mitre.org/data/definitions/639.html) (IDOR),
  [862](https://cwe.mitre.org/data/definitions/862.html) (missing authz),
  [565](https://cwe.mitre.org/data/definitions/565.html) (cookie trust)
- Context: OWASP [A01:2021](https://owasp.org/Top10/2021/A01_2021-Broken_Access_Control/) ·
  OWASP [API Security Top 10](https://owasp.org/www-project-api-security/) (BOLA = API1)

---

*Why isn't it solved? Because "solved" would mean the whole industry agreeing, in a
machine-readable way, who may see what — and that agreement is the one thing no one but each
organization can author. The tooling is ready. The intent is the bottleneck.*
