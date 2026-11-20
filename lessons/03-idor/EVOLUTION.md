# Evolution — how Lesson 03 fits the arc

Lessons 01 and 02 each grew from a one-line exploit up a ladder of rungs into a typed,
LLM-assisted agent. Lesson 03 deliberately does **not**. It has one deterministic
capability (`recon.py`) and one visual walk (`index.html`), and the reason it stops
there *is* the lesson. This file is the what-changed spine — read it to see why effort
goes **down** across the three lessons, not up.

## The spine: same family, less and less to defeat

| | **01 · Broken Access Control** | **02 · SQL Injection** | **03 · IDOR** |
|---|---|---|---|
| OWASP | A01 | A03 | **A01** (again) |
| The flaw | server trusts a client-held **role** | server mis-parses crafted **input** | server trusts a client-supplied **reference** |
| What you do | **forge** — decode the `profil` cookie, edit `role`, re-encode | **craft** — close the SQL string, comment out the check | **change a number** — `1042` → `1041` |
| Tooling | a decoder + a wordlist of roles | a fixed payload ladder | the address bar |
| Search space | which role value | which payload / mechanism class | the integer next door |
| The missing control | *authorization of the asserted role* | *separation of code and data* | *authorization of the asserted object* |

01 and 03 are the **same family** seen from two angles. In 01 the untrusted thing you
control is *who you claim to be* (a role in a cookie). In 03 it is *what you ask for*
(an object id in a URL). Both fail for the same root reason: **the server
authenticated the user and then never checked the authorization of the specific
thing being asserted.** Authentication ≠ authorization — stated with a role in 01,
stated with an object in 03.

## Why IDOR is the low point of the effort curve

- **01** needs you to understand a token format (Base64-JSON) and know which roles to
  try. There is a craft to it.
- **02** needs you to understand how an unparameterised query concatenates your input,
  and to build a payload that survives it. More craft.
- **03** needs nothing. The reference is already in the URL, in plain decimal, and the
  one before yours belongs to someone else. You do not defeat a control — you walk
  through the hole where a control should be.

That inversion is why IDOR is perennially near the top of real breach reports: there
is no skill barrier, and the fix (check that the caller owns the object, on every
request) is one the developer simply didn't write.

## Why no agent rung

The earlier lessons climb toward a fenced LLM advisor because they have something to
reason over — rank the roles, invent a payload, interpret a dev comment. IDOR's search
space is ~1: one reference and its neighbours. The bounded enumeration in `recon.py`
*is* the complete solution; there is nothing left for a model to add. Bolting an agent
on would be ceremony, and ceremony is the exact failure mode the series argues against.

**The capability you reach for should be the smallest one that solves the problem — and
then you stop.** Lesson 03 is where that thesis is cheapest to see: the smallest
capability is a `for` loop over four integers.

## The access-control rule vs. the success oracle

`recon.py` never declares a win. Success has a **single judge**; access is a **separate
classifier** — two distinct roles, not two success oracles:

- **WIN oracle** — the flag regex `CyberZerk\{.*?\}`. The *only* thing that says
  "it worked." This is the single judge of success, exactly as in Lessons 01 & 02.
- **LEAK rule** — *HTTP 200 + content for an id not in the session grant.* This is the
  authorization check the server **should** have performed, run client-side as a
  classifier of *access* (not of success). Every id we were not granted that still
  returns content is, by definition, a record the server leaked. A LEAK says "the
  control is broken here"; only the WIN oracle says "and here is the flag."

The session was granted `{1042}`. `1041` comes back `200 OK` with a confidential
medical file — so the rule fires LEAK, and the flag inside it fires WIN. IDOR
confirmed, with the model of the missing control sitting right next to the evidence.
