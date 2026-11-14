# SQL Injection — Classics, Taxonomy & Resources

A living reference for Lesson 02: what the classic payloads are, why they work, how to tell
detection from exploitation, and how to actually fix it.

## The one mechanic

User input lands *inside* a SQL string: `... WHERE username='<input>' AND password='<input>'`.

- The **apostrophe `'`** is the string fence. Supplying your own `'` **closes it early** — text
  after it stops being data and becomes SQL *code*. That boundary crossing is the whole bug.
- **Comments** (`-- `, `#`, `/* */`) let you **delete** the rest of the query (e.g. the password
  check). MySQL's `-- ` needs a trailing space; `#` does not.

## Taxonomy (how the answer comes back to you)

| Class | Channel | Tell |
|---|---|---|
| **In-band · error-based** | the app echoes a DB error | SQL/driver error text leaks |
| **In-band · UNION-based** | your rows appended to the real result | `UNION SELECT` returns data |
| **Blind · boolean** | page *changes* true vs false, no data echoed | `AND 1=1` vs `AND 1=2` differ |
| **Blind · time** | no visible change — *timing* leaks the bit | `SLEEP(5)` delays the response |
| **Out-of-band** | DB makes a DNS/HTTP call you observe | last resort when all else is blind |

**Auth-bypass** (our challenge) is a *use-case*, usually in-band or blind: don't read data —
just make the `WHERE` clause true, or comment the password check away.

> Our target hid its errors (`display_errors` off), so error-based detection failed. We switched
> to **boolean / logic** detection: change the query's *decision* (WIN vs LOSE), not its *error*.

## Classic payloads (authorized lab use only)

| Payload (in the username field) | Effect |
|---|---|
| `'` | probe — does the fence break? |
| `admin' -- ` | close string, comment out password check → log in as admin |
| `admin'#` | same, MySQL `#` comment (no trailing-space gotcha) |
| `' OR '1'='1' -- ` | tautology — `WHERE` always true (logs in as the first row) |
| `' UNION SELECT 1,2,3 -- ` | map column count / exfiltrate (data-read, not auth-bypass) |
| `' AND SLEEP(5) -- ` | blind confirmation by timing |

More, organized by DBMS: **PayloadsAllTheThings → SQL Injection**.

## Detection vs exploitation (keep them apart)

- **Detection** = "does my input reach the parser?" (one `'`, or a boolean pair). Cheap, low impact.
- **Exploitation** = "use it" (bypass auth, read data). Do the minimum to prove impact, then stop.
- Keep a deterministic **oracle** as the only thing that says "it worked."

## The fix (and the non-fixes)

- ✅ **Parameterised queries / prepared statements** — code and data on separate rails; the
  apostrophe becomes a literal apostrophe. **This is the fix.**
- ✅ **Least-privilege** DB account; **allow-list** input validation — defense in depth.
- ⚠️ **Escaping** (`mysqli_real_escape_string`, `addslashes`) — error-prone, bypassable. A band-aid.
- ❌ **A WAF** buys time, not safety. ❌ **Password hashing / CSRF tokens** are *different bugs*
  (exactly our dev's TODO) — useless against this one.

## References

- OWASP — SQL Injection: https://owasp.org/www-community/attacks/SQL_Injection
- OWASP Top 10 — A03:2021 Injection: https://owasp.org/Top10/A03_2021-Injection/
- OWASP Cheat Sheet — SQL Injection Prevention: https://cheatsheetseries.owasp.org/cheatsheets/SQL_Injection_Prevention_Cheat_Sheet.html
- PortSwigger Web Security Academy — SQL injection: https://portswigger.net/web-security/sql-injection
- PayloadsAllTheThings — SQL Injection: https://github.com/swisskyrepo/PayloadsAllTheThings/tree/master/SQL%20Injection
- CWE-89 — SQL Injection: https://cwe.mitre.org/data/definitions/89.html
