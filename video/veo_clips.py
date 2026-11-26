"""Generate the story's b-roll clips with Veo on Vertex AI.

Prompts live in video/README.md ("Veo prompts"); they're mirrored here so the run is
reproducible. Output: video/clips/<name>.mp4 (8 s, 16:9, no audio). Veo returns ~35 MB files; re-encode
before committing: ffmpeg -i in.mp4 -an -vf scale=1280:720 -c:v libx264 -crf 26 -g 12 out.mp4
(~30% opacity behind the graphics, so 720p is plenty; -g 12 keeps per-frame seeks fast).

Uses Application Default Credentials (Cloud Shell works as-is). Run from an env with
google-genai installed (e.g. python3 -m venv /tmp/genai-venv && /tmp/genai-venv/bin/pip install google-genai):

  /tmp/genai-venv/bin/python video/veo_clips.py              # all three
  /tmp/genai-venv/bin/python video/veo_clips.py turn         # just one
  VEO_MODEL=veo-3.1-generate-001 ... for the higher-quality (pricier) model
"""
import os
import sys
import time

from google import genai
from google.genai import types

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(REPO, 'video', 'clips')
MODEL = os.environ.get('VEO_MODEL', 'veo-3.1-fast-generate-001')
NEG = 'people, faces, hands, text, letters, numbers, logos, watermarks, buildings, cities, cartoon, low quality'

PROMPTS = {
    'intro': ("Macro shot in near-total darkness. A single glowing orange ember drifts upward, then dozens of tiny "
              "embers rise slowly around it like sparks from a forge, softly out of focus. Warm orange (#FF6B35) "
              "and deep brown-black only. Very slow push-in, shallow depth of field, cinematic film grain, no "
              "people, no text, no logos. Calm, premium, mysterious."),
    'turn': ("Abstract volumetric visualization: thousands of glowing orange light points connect into a vast "
             "three-dimensional neural network floating in a dark void. Pulses of light race along the "
             "connections, which grow brighter as the camera glides slowly forward through the structure. Warm "
             "orange and amber on near-black, subtle haze, anamorphic lens flares, no people, no text, no logos. "
             "Futuristic, awe-inspiring, smooth continuous motion."),
    'finale': ("Dark, minimal space. Streams of orange light particles spiral inward and converge into one bright "
               "point at the centre, which blooms into a soft warm glow and then settles into gentle drifting "
               "sparks. Slow camera pull-back. Warm orange and amber on deep black, elegant and cinematic, film "
               "grain, no people, no text, no logos."),
}


def main():
    names = sys.argv[1:] or list(PROMPTS)
    project = os.environ.get('GOOGLE_CLOUD_PROJECT')
    client = genai.Client(vertexai=True, project=project, location=os.environ.get('VEO_LOCATION', 'us-central1'))
    os.makedirs(OUT, exist_ok=True)
    for name in names:
        print(f'{name}: submitting to {MODEL}', flush=True)
        op = client.models.generate_videos(
            model=MODEL, prompt=PROMPTS[name],
            config=types.GenerateVideosConfig(aspect_ratio='16:9', duration_seconds=8, resolution='1080p',
                                              generate_audio=False, negative_prompt=NEG, number_of_videos=1))
        while not op.done:
            time.sleep(15)
            op = client.operations.get(op)
        if op.error:
            sys.exit(f'{name}: {op.error}')
        vids = (op.response or op.result).generated_videos
        if not vids:
            sys.exit(f'{name}: no video returned (possibly filtered): {op.response}')
        data = vids[0].video.video_bytes
        path = os.path.join(OUT, f'{name}.mp4')
        open(path, 'wb').write(data)
        print(f'{name}: wrote {path} ({len(data) / 1e6:.1f} MB)', flush=True)


if __name__ == '__main__':
    main()
