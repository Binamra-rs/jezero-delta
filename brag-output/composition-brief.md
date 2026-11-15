# Hyperframes Composition Brief: Jezero Delta Explorer

## Objective
Create a short launch-style brag video for Jezero Delta Explorer, with narration.

## Output
- Composition directory: `brag-output/composition/`
- Rendered video: `brag-output/brag.mp4`
- Format: landscape, 1920x1080 @ 30 fps
- Duration: ~23 s (15–25 s window)

## Source Material
- Project root: `jezero-delta/`
- Files read: `README.md`, `frontend/index.html`, `frontend/tailwind.config.js`, `frontend/src/index.css`, `App.tsx`, `components/{TopBar,LayerPanel,RightPanel,BottomBar,SurvivalHub}.tsx`, `lib/format.ts`, `config/project.yaml`, `backend/jezero/raster/colormap.py`, `backend/jezero/routing/*`, `docs/results/astar-validation.md`
- Product name: Jezero Delta Explorer
- Strongest claim: "Interactive, scientifically traceable exploration of the Jezero western delta, Mars — and nothing beyond it."
- Real assets generated from `data/processed/` (in `composition/assets/img/`):
  - `ctx_ortho.png`: CTX orthomosaic, 2255×2135, 5.00 m/px
  - `ctx_elevation.png`, `ctx_slope.png`, `ctx_hillshade.png`: CTX 20 m layers in the project's own ramps
  - `route.json`: a real A* route (Balanced profile) from the landing area (18.4447 N, 77.4508 E) to the delta top (18.4930 N, 77.3640 E), path normalised to ortho image coordinates, with stats
- Copy that must appear verbatim:
  - "— and nothing beyond it."
  - "Values are native pixels — never interpolated or extrapolated."
  - "terrain-aware A* · estimates only"
  - "240/240 A* = Dijkstra" (from "240/240 cases agree with Dijkstra")
  - "Scientific surface exploration of the Jezero western delta, Mars."

## Creative Direction
- Tone: cinematic held back toward polished; a quiet mission-control briefing
- Angle, hook, outro: see `brag-plan.md`
- Avoid: generic SaaS language, abstract filler, redesigning the app, waveform visuals, bounce on UI, click rings

## Visual Identity
- Ground `#0c1622`, top bar `#101c2a`, panel `#132131`, card `#1a2a3c`, rim `#203247`, rim2 `#2b3f57`
- Ink `#e8eef5`, dim `#a3b3c5`, faint `#6f8398`
- Signal teal `#7cd4c4` (A, selection), ochre `#f2a76f` (route, B), caution `#f2cc72`
- Inter for UI/display, IBM Plex Mono for coordinates and values (both bundled)

## Storyboard
See `brag-plan.md`. Six scenes: Hook → Layers → Inspect → Route → Proof → Outro.

## Audio
- Narration: six Kokoro `af_heart` clips in `assets/vo/`, one per scene; scene starts follow the clip lengths
- Music: `assets/music/happy-beats-business-moves-vol-12-by-ende-dot-app.mp3` at ~0.3 with fade-in/out, ducked to ~0.13 under the narration
- Cue guidance: `assets/music/cues/…vol-12….music-cues.json`; lock the proof reveal near 17.47 s if the narration timing allows
- Audio-reactive: subtle RMS glow on the route line and the outro title; skip it if extraction is unavailable
- SFX: chosen after the animation exists, from `<skill-dir>/assets/sfx/` and `sfx-analysis.md` (low-HF picks); clicks on cursor presses, a soft card slide on layer rows, a soft impact on 240/240, and a bell on the name

## Hyperframes Instructions
Follow the `hyperframes`, `hyperframes-cli` and `media-use` skills (bundled with CLI 0.9.52). Skip storylines, SPEC.md, usage, history, feedback and REVIEW.md. `npx hyperframes check` is the gate. Render locally.
