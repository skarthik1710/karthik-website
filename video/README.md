# Story video

The homepage's "Watch the story" button plays `public/media/story.mp4`. That file is built
here from source, so it can be re-cut any time the facts change.

| Piece | Source | Made with |
|---|---|---|
| Motion graphics (all scenes, text, diagrams) | `story.html` | code; every frame is `STORY.render(t)` |
| Music + sound design | `make_soundtrack.py` | code (numpy/scipy synthesis, no samples) |
| Voice-over | `narration.json` → `narration/NN.wav` | **Gemini 2.5 Pro TTS** on Vertex AI (`tts_narration.py`) |
| Cinematic b-roll | `clips/{intro,turn,finale}.mp4` | **Veo 3.1 Fast** on Vertex AI (`veo_clips.py`) |

Build (about 5 minutes):

```bash
PLAYWRIGHT_BROWSERS_PATH=/tmp/ms-playwright PYTHONPATH=/tmp/pylib python3 scripts/render_story.py
# quick low-res check:  ... render_story.py --preview   (writes /tmp/story-preview.mp4)
# live in a browser:    serve the repo and open /video/story.html?play
```

Prereqs: `pip install --target /tmp/pylib imageio-ffmpeg` (ffmpeg with x264) and the
Playwright Chromium install in `/tmp/ms-playwright`.

## Rules

- **Facts only from the site** (index.html / experience.html). No client names except Microsoft,
  no team size, no deployment-status wording. If a site fact changes, change `story.html` and
  `narration.json`, then re-render.
- B-roll is **abstract only**: no people, faces, logos, readable text or real places. The story is
  told by the graphics and voice; b-roll is atmosphere at 30–38% opacity behind them.

## Scene map (seconds)

| # | Time | Scene | B-roll slot |
|---|---|---|---|
| 1 | 0–8 | 2007: an ember ignites; AS/400 terminal types out | `intro.mp4` (0–13) |
| 2 | 8–13 | "Trust is earned in production." | `intro.mp4` |
| 3 | 13–30 | Journey rail: 2011 → 2025, nodes light up | — |
| 4 | 30–40 | "Then the industry turned." Neural mesh forms | `turn.mp4` (30–40) |
| 5 | 40–52 | Practice Head: deals · use cases (150+ → 20) · team | — |
| 6 | 52–64 | "Governed by design." Layered architecture + control plane | — |
| 7 | 64–76 | Embers converge, flash, "From slideware to shipped." | `finale.mp4` (64–76) |

## Regenerating the AI assets (Vertex AI)

Both scripts use Application Default Credentials (Cloud Shell works as-is) and need `google-genai`
in a clean venv (`python3 -m venv /tmp/genai-venv && /tmp/genai-venv/bin/pip install google-genai`):

```bash
/tmp/genai-venv/bin/python video/veo_clips.py [intro|turn|finale]   # ~2 min per clip; re-encode as noted in the script
/tmp/genai-venv/bin/python video/tts_narration.py [01 ... 07]       # TTS length varies per take; keep the tightest
```

The renderer trims TTS padding and speeds a line up to 1.12x if it runs slightly past its cue; it
warns if a line still doesn't fit (shorten the text or take another).

## Veo prompts (also usable in Google Flow)

These are mirrored in `veo_clips.py`. In Flow, use Text to Video, 16:9, audio off. Each clip is 8 s; story.html
plays it slowed down (rate per clip in `clipWin`) to fill its scene, and the finale is offset so its burst
lands on the 65.6 s flash.

**1 · `video/clips/intro.mp4`: embers in the dark**
> Macro shot in near-total darkness. A single glowing orange ember drifts upward, then dozens of tiny
> embers rise slowly around it like sparks from a forge, softly out of focus. Warm orange (#FF6B35)
> and deep brown-black only. Very slow push-in, shallow depth of field, cinematic film grain, no
> people, no text, no logos. Calm, premium, mysterious.

**2 · `video/clips/turn.mp4`: the network wakes up**
> Abstract volumetric visualization: thousands of glowing orange light points connect into a vast
> three-dimensional neural network floating in a dark void. Pulses of light race along the
> connections, which grow brighter as the camera glides slowly forward through the structure. Warm
> orange and amber on near-black, subtle haze, anamorphic lens flares, no people, no text, no logos.
> Futuristic, awe-inspiring, smooth continuous motion.

**3 · `video/clips/finale.mp4`: light resolving**
> Dark, minimal space. Streams of orange light particles spiral inward and converge into one bright
> point at the centre, which blooms into a soft warm glow and then settles into gentle drifting
> sparks. Slow camera pull-back. Warm orange and amber on deep black, elegant and cinematic, film
> grain, no people, no text, no logos.
