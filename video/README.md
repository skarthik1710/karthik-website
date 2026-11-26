# Story video

The homepage's "Watch the story" button plays `public/media/story.mp4`. That file is built
here from source, so it can be re-cut any time the facts change.

| Piece | Source | Made with |
|---|---|---|
| Motion graphics (all scenes, text, diagrams) | `story.html` | code; every frame is `STORY.render(t)` |
| Music + sound design | `make_soundtrack.py` | code (numpy/scipy synthesis, no samples) |
| Voice-over (optional) | `narration.json` → `narration/NN.wav` | **Gemini TTS** (`tts_narration.py` or AI Studio) |
| Cinematic b-roll (optional) | `public/media/clips/*.mp4` | **Veo in Google Flow** (prompts below) |

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

## Veo prompts for Google Flow (Google AI Pro)

In [Flow](https://labs.google/flow), pick **Text to Video**, **16:9**, **Veo 3.1 (Fast is fine)**
and **audio off**, since the soundtrack is ours. Make 2–3 takes of each prompt and keep the best.
Download at 1080p and save to the path shown. Each clip is 8 s; the renderer holds the last frame if
a scene runs longer, so slow, continuous motion works best.

**1 · `public/media/clips/intro.mp4`: embers in the dark**
> Macro shot in near-total darkness. A single glowing orange ember drifts upward, then dozens of tiny
> embers rise slowly around it like sparks from a forge, softly out of focus. Warm orange (#FF6B35)
> and deep brown-black only. Very slow push-in, shallow depth of field, cinematic film grain, no
> people, no text, no logos. Calm, premium, mysterious.

**2 · `public/media/clips/turn.mp4`: the network wakes up**
> Abstract volumetric visualization: thousands of glowing orange light points connect into a vast
> three-dimensional neural network floating in a dark void. Pulses of light race along the
> connections, which grow brighter as the camera glides slowly forward through the structure. Warm
> orange and amber on near-black, subtle haze, anamorphic lens flares, no people, no text, no logos.
> Futuristic, awe-inspiring, smooth continuous motion.

**3 · `public/media/clips/finale.mp4`: light resolving**
> Dark, minimal space. Streams of orange light particles spiral inward and converge into one bright
> point at the centre, which blooms into a soft warm glow and then settles into gentle drifting
> sparks. Slow camera pull-back. Warm orange and amber on deep black, elegant and cinematic, film
> grain, no people, no text, no logos.

Then re-run the build; the clips are picked up automatically.

## Voice-over with Gemini TTS

`narration.json` holds seven timed lines (voice `Charon`, documentary style). Either:

- **API (free tier):** `GEMINI_API_KEY=<personal key> python3 video/tts_narration.py`. Use a
  personal AI Studio key, never the work account; it's read from the environment and never saved.
- **No key:** Google AI Studio → *Generate speech* → paste each line with the same voice and style
  → save as `video/narration/01.wav` … `07.wav`.

The renderer warns if a line runs into the next cue. Shorten the text or move `start` if it does.
