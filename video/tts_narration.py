"""Generate the voice-over lines in video/narration.json with Gemini text-to-speech.

Writes video/narration/<id>.wav (24 kHz mono). scripts/render_story.py then places each
line at its 'start' time and ducks the music under it.

Gemini TTS works on the free API tier. Use a personal key from https://aistudio.google.com/apikey
(not the work account). The key is read from the environment and never written to disk:

  GEMINI_API_KEY=... python3 video/tts_narration.py            # all lines
  GEMINI_API_KEY=... python3 video/tts_narration.py 03 05      # just these ids

No key? In Google AI Studio choose "Generate speech", paste each line with the same
voice/style, download the WAVs, and save them as video/narration/01.wav ... 07.wav.
"""
import json
import os
import sys
import wave

from google import genai
from google.genai import types

HERE = os.path.dirname(os.path.abspath(__file__))
MODEL = os.environ.get('TTS_MODEL', 'gemini-2.5-flash-preview-tts')


def main():
    key = os.environ.get('GEMINI_API_KEY')
    if not key:
        sys.exit('Set GEMINI_API_KEY (personal AI Studio key).')
    spec = json.load(open(os.path.join(HERE, 'narration.json')))
    only = set(sys.argv[1:])
    os.makedirs(os.path.join(HERE, 'narration'), exist_ok=True)
    client = genai.Client(api_key=key)
    for line in spec['lines']:
        if only and line['id'] not in only:
            continue
        resp = client.models.generate_content(
            model=MODEL,
            contents=f"{spec['style']}\n\n{line['text']}",
            config=types.GenerateContentConfig(
                response_modalities=['AUDIO'],
                speech_config=types.SpeechConfig(
                    voice_config=types.VoiceConfig(
                        prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name=spec['voice'])))))
        pcm = resp.candidates[0].content.parts[0].inline_data.data
        out = os.path.join(HERE, 'narration', f"{line['id']}.wav")
        with wave.open(out, 'wb') as w:
            w.setnchannels(1); w.setsampwidth(2); w.setframerate(24000); w.writeframes(pcm)
        print(f"{line['id']}: {len(pcm) / 48000:.1f}s -> {out}")


if __name__ == '__main__':
    main()
