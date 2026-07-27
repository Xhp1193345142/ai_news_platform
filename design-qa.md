# AI Signal authentication visual QA

## Comparison target

- Source visual truth: `/Users/haopu_xi/.codex/attachments/8a2603bd-239a-4187-9d54-eacba0a4a5a3/pasted-text.txt` and the accompanying “Cyberpunk Black Hole with Glitch FX” screenshot.
- Prototype: `http://127.0.0.1:5173/`, desktop login default state.
- Implementation choice: preserve the source’s neon event horizon, cyan/magenta accretion disk, sparse star field, Bloom, and slow orbital flow; remove its grid floor, dense rainbow particles, trigger button, and full-page demo chrome to serve the supplied authentication composition.

## Findings and adjustments

- The former raster black-hole foreground and its CSS masks were removed from the active experience. The black hole is now one transparent WebGL canvas above a still deep-space image, so the cosmic background and black hole remain independent layers.
- The accretion disk is the only prominent moving element. Its flow and orbit are deliberately slow; the page background does not breathe or drift.
- The desktop authentication panel remains capped at 27.5rem to address the reported oversized panel at shorter desktop heights.
- `prefers-reduced-motion` renders a static black-hole frame instead of continuing the animation.

## Checks

- [x] The WebGL canvas exists, is correctly sized, and sits alongside the authentication panel.
- [x] The compact panel width guard passes in the local prototype.
- [x] `npm run build` passes.
- [x] `npm run test:sites` passes (4 tests).
- [x] Login/register switch, validation, password visibility, and success-state transition remain in the Vue UI.

## Follow-up polish

- Tune the cyan-to-magenta ratio and Bloom strength against the user’s preferred screenshot after a visual pass in Figma.
- Replace the simulated successful login with FastAPI authentication when the backend is introduced.

final result: passed
