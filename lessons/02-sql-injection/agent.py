#!/usr/bin/env python3
# agent.py — the agentic rung (console). Lesson 02.
#
# Wires the three layers into one fenced loop:
#   guide.py (deterministic)  -> discover the surface, clues, targets, oracle
#   brain.py (typed LLM)      -> rank the candidates, and INVENT / INTERPRET
#   oracle   (deterministic)  -> the ONLY thing that says WIN
# The LLM proposes; the oracle disposes; the human (or a bounded --auto) fires.
#
# Demo (no key): runs the deterministic guide + a deterministic fallback ranking,
#   fully offline on real captured responses. With MISTRAL_API_KEY it routes the
#   ranking (and invention / interpretation) through brain.py.
#
#   python3 agent.py                 # offline demo, step mode (asks before firing)
#   python3 agent.py --auto          # offline demo, bounded autofire
#   python3 agent.py --live          # against the authorized instance (needs requests)
#   MISTRAL_API_KEY=... python3 agent.py --live --auto   # with the LLM advisor

import os
import sys
import guide
from recon import win_oracle, FAIL_TOKEN, _replay_fire, _live_fire

MAX_ACTIONS = 8                                   # explicit action budget
ATTACK_MECHS = {"auth-bypass", "data-read", "blind-time"}


def transport(live):
    if live:
        return guide._live_get(guide.TARGET), _live_fire(guide.TARGET)
    return guide._demo_get, _replay_fire


def attack_candidates():
    """The actionable exploit probes from the guide's ladder (not the diagnostics)."""
    return [{"label": l, "username": u, "password": p, "mechanism": m, "intent": i}
            for (l, u, p, m, i) in guide.LADDER if m in ATTACK_MECHS]


def fallback_rank(cands):
    """Deterministic ranking when there's no key: simplest bypass first."""
    bucket = {"auth-bypass": 0, "data-read": 1, "blind-time": 2}
    order = [c["label"] for c in sorted(cands, key=lambda c: bucket.get(c["mechanism"], 9))]
    return order, "deterministic fallback: simplest bypass first (no LLM key).", []


def llm_advise(state, cands):
    """Route reasoning through brain.py. Returns (order, why, invented[])."""
    import brain
    labels = {c["label"] for c in cands}
    proj = brain.Projection(
        clues=state["inventory"]["clues"],
        targets=state["targets"],
        candidates=[c["label"] for c in cands],
        oracle=state["oracles"],
        tree=[{"label": c["label"], "mech": c["mechanism"]} for c in cands],
    )
    out = brain.advise(proj).output
    invented, order, why = [], [c["label"] for c in cands], ""
    if out.kind == "rank":
        order = [x for x in out.order if x in labels]
        why = out.rationale
    elif out.kind == "invent":
        for ip in out.candidates[:3]:                 # cap invention (bounded)
            invented.append({"label": "invented", "username": ip.username,
                             "password": ip.password, "mechanism": ip.mechanism,
                             "why": ip.why, "invented": True})
        why = out.rationale + f"  (+{len(invented)} invented)"
    elif out.kind == "interpret":
        why = f"interpretation of {out.about}: {out.meaning}"
    elif out.kind == "ask":
        why = f"LLM asks: {out.question}"
    else:
        why = out.text
    for c in cands:                                   # nothing falls out of the plan
        if c["label"] not in order:
            order.append(c["label"])
    return order, why, invented


def print_header(state):
    inv = state["inventory"]
    print("\n=== agent.py — guide (deterministic) -> brain (LLM) -> oracle (judge) ===")
    print(f"\nURL       {guide.TARGET}")
    print("clues     " + "; ".join(c["text"][:40] for c in inv["clues"][:3]) + " ...")
    print("targets   " + ", ".join(f"{t['param']}({t['score']})" for t in state["targets"]))
    print(f"oracle    WIN=/{state['oracles']['win']}/  LOSE={state['oracles']['lose']!r}")


def main():
    live = "--live" in sys.argv
    auto = "--auto" in sys.argv or not sys.stdin.isatty()   # non-interactive -> auto
    get, fire = transport(live)

    # 1) Deterministic discovery (the guide owns this; fires only the baseline).
    inv = guide.discover(get)
    state = {"inventory": inv, "targets": guide.rank_targets(inv),
             "oracles": guide.derive_oracles(fire)}
    print_header(state)

    # 2) Reasoning: LLM if a key is present, else the deterministic fallback.
    cands = attack_candidates()
    by_label = {c["label"]: c for c in cands}
    if os.getenv("MISTRAL_API_KEY"):
        try:
            order, why, invented = llm_advise(state, cands)
            src = "brain.py (LLM)"
        except Exception as e:                        # the fence: a bad LLM call never fires
            order, why, invented = fallback_rank(cands)
            src = f"fallback (LLM error: {e.__class__.__name__})"
    else:
        order, why, invented = fallback_rank(cands)
        src = "deterministic fallback (no MISTRAL_API_KEY)"

    print(f"\n[reasoning · {src}]")
    print("plan: " + " > ".join(order))
    print("why:  " + why)

    # 3) Fire — bounded, oracle-judged, human-confirmed unless --auto.
    queue = [by_label[l] for l in order if l in by_label] + invented
    fired = 0
    for c in queue:
        if fired >= MAX_ACTIONS:
            print("\n[budget] action budget reached — stopping."); break
        tag = "INVENTED" if c.get("invented") else "ladder"
        note = c.get("why") or c.get("intent") or ""
        print(f"\n-> next [{tag} · {c['mechanism']}] username={c['username']!r}")
        print(f"        {note}")
        if not auto:
            try:
                ans = input("   fire? [Enter=yes / s=skip / q=quit] ").strip().lower()
            except EOFError:
                ans = ""
            if ans == "q":
                print("stopped."); return
            if ans == "s":
                continue
        status, body, _ = fire(c["username"], c["password"])
        fired += 1
        if body is None:
            print("   (no response in offline fixtures — run --live to fire this one)")
            continue
        flag = win_oracle(body)                       # THE ORACLE — the only judge
        if flag:
            print(f"   [WIN] oracle fired -> {flag}")
            print(f"\nDone in {fired} fire(s). The LLM proposed, the oracle judged, you fired.")
            return
        verdict = "ERR_AUTH (lose)" if FAIL_TOKEN in body else "changed, but no flag"
        print(f"   [--] {verdict} — oracle: not a win")

    print("\nNo flag from the attempted candidates within budget.")


if __name__ == "__main__":
    main()
