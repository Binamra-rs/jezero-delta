# Brag Plan: Jezero Delta Explorer

## What is this app?
A web map of one piece of Mars, the Jezero western delta. It stacks CTX, HiRISE and THEMIS layers in one Mars map projection, lets you click any point to read real pixel values, and plans terrain-aware A* routes. Its charm is how strict it is: "and nothing beyond it", "never interpolated or extrapolated", and 240/240 A* = Dijkstra.

## The angle
**A mission briefing for a walk across one delta.** It's played straight and quiet, like a control-room brief. The app refuses to cover all of Mars, and that refusal is the hook. Everything after it is real: the real CTX orthomosaic, real colour ramps rendered from the project's own `colormap.py`, real pixel values sampled at a point, and a real A* route computed by `backend/jezero/routing/astar.py` on the processed CTX DEM. Nothing in the video is mocked except the app chrome around it.

## Hook (first 2–3 seconds)
The real CTX orthomosaic of the delta fills the frame. Mono coordinates "18.4° N 77.4° E" are in the corner. The headline is "The Jezero western delta, Mars." Then a beat, and the README's own words land: "— and nothing beyond it."

## Key moments
- Layers arriving: "Scientific layers" rows slide in one by one (CTX Orthomosaic 5.00 m/px, HiRISE DTM 1 1.01 m/px, THEMIS Thermal Inertia 100 m/px, Slope (CTX 20 m)). The elevation ramp, then the slope ramp, wash over the same terrain.
- Inspect: a cursor clicks the delta. The "Point" panel fills with Latitude 18.45626° N, Longitude 77.40730° E, Elevation −2,527.5 m, Slope 12.58°, Thermal inertia 242 J m⁻² K⁻¹ s⁻½, Roughness 2.19 m, with Source/Derived badges. The notice reads "Values are native pixels — never interpolated or extrapolated."
- Route: A (teal) is set at the Octavia E. Butler landing area and B (ochre) on the delta top. The cursor presses "Compute route". The orange A* path draws across the real image and bends around the crater. Stats tick in: Distance 6.53 km, Cumulative ascent 183.9 m, Maximum slope 9.5°, Search 79,441 cells.

## Outro / punchline
"240/240 A* = Dijkstra cases" slams in as proof, followed by the product name "Jezero Delta Explorer" over the delta and the tagline "Scientific surface exploration of the Jezero western delta, Mars."

## User flow worth showing
Open map → click a point to inspect real values → set A and B → compute an A* route → read the route statistics.

## Tone
- Preset: cinematic, held back toward polished
- Creative direction: quiet mission-control briefing; one planet, one delta, no hype
- Interpretation: big real imagery, slow camera drift on the terrain, titles that land and hold dead still, few cuts, a low music bed and a calm narrator. The precision is the flex.

## Format: landscape — 1920x1080 @ 30 fps
## Duration: ~23 s (scene lengths flex to the generated narration, capped at 25 s)

## Visual identity (from the project)
- Background: `#0c1622` (void); panels `#132131`, top bar `#101c2a`, cards `#1a2a3c`, dividers `#203247`
- Accent: `#7cd4c4` (signal teal, start A / selection); route `#f2a76f` (ochre)
- Text: `#e8eef5` (ink), `#a3b3c5` (dim), `#6f8398` (faint)
- Display font: Inter (600/700); data in IBM Plex Mono (both bundled with Hyperframes)
- Strongest visual element: the real CTX orthomosaic of the delta with the orange route across it

## Share copy (draft)
I built a map of exactly one place on Mars, the Jezero delta, with real orbiter pixels and terrain-aware A* routes checked 240/240 against Dijkstra.

## Audio direction
- Role: cinematic support under narration
- Music: `happy-beats-business-moves-vol-12-by-ende-dot-app.mp3` (steady, clean)
- Music treatment: fade in over 0.6 s; ducked to ~0.13 while the voice speaks, rising to ~0.3 in the gaps; 1.2 s fade-out under the end card
- Music cue guidance: preset `assets/music/cues/happy-beats-business-moves-vol-12-by-ende-dot-app.music-cues.json`, about 110 BPM. Strong cues: 17.47 s (proof "240/240"), 20.19–20.75 s area (outro title), 22.93 s (final hold). Beat grid for the layer rows: 4.39 / 5.34 / 6.00 (every other beat, held after).
- Audio-reactive treatment: subtle. Music RMS gently breathes the glow under the route line and the outro title. No waveform visuals.
- SFX posture: sparse and motion-matched
- Audio-coupled moments: layer rows arriving (soft card slides), cursor clicks (inspect, A, B, Compute route), "240/240" landing (soft impact), outro (bell)
- Restraint rule: no SFX under a narrated word if it masks it; nothing bright or repeated more than twice

## Voiceover script
Kokoro `af_heart`, one line per scene:
1. "This is the Jezero delta, on Mars. And nothing beyond it."
2. "CTX, HiRISE and THEMIS, stacked in one Mars projection."
3. "Click anywhere. You get the real pixel, never interpolated."
4. "Pick two points, and A-star finds a path over the actual terrain. Six and a half kilometres. Nothing steeper than ten degrees."
5. "Checked against Dijkstra. Two hundred forty, for two hundred forty."
6. "Jezero Delta Explorer."

Grounding: "nothing beyond it" is the README; "never interpolated" is the Inspect notice; 6.53 km and 9.47° max slope are this route's computed stats; 240/240 is `docs/results/astar-validation.md`.

## Storyboard

### Scene 1 — Hook — ~3.6 s
Full-bleed real CTX orthomosaic, slow drift. Mono "18.4° N 77.4° E · CTX 5 m" top-left. Headline: "The Jezero western delta, Mars." Second line in teal: "— and nothing beyond it."
Sequential/interaction: two lines, the second after a held beat
Audio intent: music opens; narrator sets the scope
Audio-coupled idea: none (the voice carries it)
Transition mood: soft → app chrome builds around the same image

### Scene 2 — Layers — ~3.5 s
The image shrinks into the map pane as the top bar ("Jezero Delta · Explorer · 18.4° N 77.4° E", Map / Raw images / Survival hub) and the left "Scientific layers" panel build around it. Four layer rows arrive one by one with resolution and Source/Derived badges. The elevation ramp fades over the terrain, then the slope ramp.
Sequential/interaction: four rows, then two eye toggles
Audio intent: soft precision
Audio-coupled idea: card slide on the first and last rows; switch on the toggles
Transition mood: clean → same app

### Scene 3 — Inspect — ~3.6 s
The cursor moves to the delta and clicks; a teal crosshair pings. The right "Point" panel fills: Location rows, then four measured/derived value rows with badges, then the "never interpolated" notice.
Sequential/interaction: simulated click, then rows fill
Audio intent: a precise click
Audio-coupled idea: mouse click on press
Transition mood: clean → same app

### Scene 4 — Route — ~6.8 s
The cursor sets A at the landing area and B on the delta top, then presses "Compute route" (Balanced · ≤20°). The orange path draws A→B across the real image. The Route tab shows Distance 6.53 km, ascent 183.9 m, max slope 9.5°, search 79,441 cells.
Sequential/interaction: three clicks, line draw, four stat rows
Audio intent: the centrepiece; the music opens up a little after the line lands
Audio-coupled idea: clicks on A, B and Compute; a soft drop when the line completes
Transition mood: dramatic → camera pushes onto the route, then cuts to the proof card

### Scene 5 — Proof — ~2.6 s
Deep navy. Giant mono "240/240", with "A* = Dijkstra cases" under it. Beat-locked to 17.47 s.
Audio-coupled idea: soft impact on landing

### Scene 6 — Outro — ~3.4 s
The real delta, dimmed, with the route glowing faintly. "Jezero Delta Explorer" and the tagline. Long hold.
Audio-coupled idea: bell under the name; music fades

**Music mood for this video:** cinematic, restrained
**Audio summary:** a calm bed that sits under a clear narrator, with exact clicks on every real action and one weighty hit each for the proof and the name.
