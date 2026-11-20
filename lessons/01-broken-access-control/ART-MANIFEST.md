# ART-MANIFEST — The Machine Bench (Lesson 1)

Every art slot the build leaves a placeholder for. Phase 1 ships colored-rect / CSS
stand-ins behind each slot; drop real sprites in and the layout holds.

Conventions: sprites are **pixel-art PNG** (or SVG) rendered with `image-rendering:pixelated`.
Colors come from the CSS custom properties in `:root` (see `index.html`) — keep sprites
tintable or ship per-accent variants. Sizes are the authored *world-unit* size (machines
are drawn large; the camera scales them down).

| Slot | Referenced in | Purpose | Suggested size | Status |
|---|---|---|---|---|
| `bench-bg` | `#ambience`, `body` bg | Workbench / world backdrop (per-season variant or tintable base) | full-bleed, tiles | placeholder (CSS gradients) |
| `machine-frame-{kind}` | `.machine .bezel` (kinds: monitor, terminal, script, scanner, mapper, reason, agent, panel) | 8 distinct computer frames — the "more capable hardware" story | ~900×620 each, CRT cutout ~ 16:10 | placeholder (CSS panel) |
| `crt-bezel` | `.crt` | CRT bezel + curvature around the screen cutout | wraps 16:10 screen | placeholder (CSS box-shadow) |
| `crt-glass` | `.glass` | Scanline + glass glare/curvature overlay | matches screen | placeholder (CSS gradients) |
| `cookie` | `.cookie b` | The travelling `profil` cookie sprite | 46×46 (+ transform states per station) | placeholder (CSS rect) |
| `cable` | `#cable .track/.flow` | Rail cable sprite + active/visited states | stroke along path | placeholder (SVG dashes) |
| `capability-leds` | `.bezel .brand .led` | Per-machine indicator lights (count = capability) | 9×9 | placeholder (CSS dots) |
| `port-icons` | `.ports .port` | ①②③ Concept / What-changed / Code buttons (open the info-layer drawer) | 36×36 each | implemented (glyph buttons; sprite art optional) |
| `seasonal-{season}` | `#ambience` | Monthly ambient sprite sets: snow / blossom / leaves / … | particle sprites | stub (Phase 4) |
| `weather-{effect}` | `#ambience` | Weather overlays: rain / sun / fog (open-meteo driven) | particle sprites | stub (Phase 4) |

**Machine kinds → station** (id · name): monitor·01 Target, terminal·02 By Hand,
script·03 Script, scanner·04 Recon, mapper·05 Map, reason·06 Reasoning (SIMULATION),
agent·07 Agent, panel·08 Epilogue.
