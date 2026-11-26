"""Render video/story.html into public/media/story.mp4 (+ poster), frame by frame.

story.html draws every frame as a pure function of time (window.STORY.render(t)), so this
captures exact frames rather than screen-recording, then muxes the synthesized soundtrack
(video/make_soundtrack.py) and, if present, voice-over lines from video/narration/
(generate them with video/tts_narration.py), each placed at its cue with the music ducked.

Optional AI b-roll: Veo clips in video/clips/{intro,turn,finale}.mp4 (video/veo_clips.py);
story.html picks them up automatically.

Needs: playwright + chromium, numpy/scipy, and an ffmpeg with libx264
(pip install --target /tmp/pylib imageio-ffmpeg; this script finds it automatically).

Usage:
  PLAYWRIGHT_BROWSERS_PATH=/tmp/ms-playwright PYTHONPATH=/tmp/pylib python3 scripts/render_story.py [--fps 30] [--preview]
"""
import argparse
import functools
import http.server
import os
import shutil
import subprocess
import sys
import threading

from playwright.sync_api import sync_playwright

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MEDIA = os.path.join(REPO, 'public', 'media')


def _speech_secs(path):
    """Seconds from first to last audible sample (ignores TTS padding)."""
    import wave
    import numpy as np
    with wave.open(path) as w:
        x = np.frombuffer(w.readframes(w.getnframes()), '<i2').astype(float) / 32768
        sr = w.getframerate()
    fr = int(sr * 0.02)
    e = np.sqrt(np.convolve(x ** 2, np.ones(fr) / fr, 'same'))
    act = np.where(e > 0.01)[0]
    return (act[-1] - act[0]) / sr if len(act) else 0.0


def narration_lines():
    """(start, wav, tempo) per voice-over line in video/narration/ (see video/tts_narration.py).

    A line that runs slightly past its cue window is sped up (max 1.12x, inaudible);
    anything longer than that needs a shorter text or a new take.
    """
    import json
    spec = json.load(open(os.path.join(REPO, 'video', 'narration.json')))
    found = []
    for i, line in enumerate(spec['lines']):
        path = os.path.join(REPO, 'video', 'narration', line['id'] + '.wav')
        if not os.path.exists(path):
            continue
        secs = _speech_secs(path)
        nxt = spec['lines'][i + 1]['start'] if i + 1 < len(spec['lines']) else 75.0
        window = nxt - line['start'] - 0.3
        tempo = min(1.12, max(1.0, secs / window))
        if secs / tempo > window:
            print(f"warning: narration {line['id']} ({secs:.1f}s) overruns its {window:.1f}s window even at {tempo:.2f}x")
        found.append((line['start'], path, tempo))
    if found:
        print(f'mixing {len(found)} narration line(s)')
    return found


def ffmpeg_exe():
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except ImportError:
        exe = shutil.which('ffmpeg')
        if not exe:
            sys.exit('ffmpeg not found: pip install --target /tmp/pylib imageio-ffmpeg and set PYTHONPATH=/tmp/pylib')
        return exe


class Handler(http.server.SimpleHTTPRequestHandler):
    """Static server with HTTP Range support; without it Chromium can't seek the b-roll clips
    and every clip renders frozen on its first frame."""

    def log_message(self, *a):
        pass

    def handle(self):
        try:
            super().handle()
        except (ConnectionResetError, BrokenPipeError):
            pass  # the browser abandons media streams mid-transfer; harmless

    def send_head(self):
        rng = self.headers.get('Range')
        path = self.translate_path(self.path)
        if not rng or not os.path.isfile(path):
            return super().send_head()
        size = os.path.getsize(path)
        start_s, _, end_s = rng.replace('bytes=', '').partition('-')
        start = int(start_s) if start_s else 0
        end = min(int(end_s) if end_s else size - 1, size - 1)
        f = open(path, 'rb')
        f.seek(start)
        self.send_response(206)
        self.send_header('Content-Type', self.guess_type(path))
        self.send_header('Accept-Ranges', 'bytes')
        self.send_header('Content-Range', f'bytes {start}-{end}/{size}')
        self.send_header('Content-Length', str(end - start + 1))
        self.end_headers()
        self._remaining = end - start + 1
        return f

    def copyfile(self, source, outputfile):
        n = getattr(self, '_remaining', None)
        if n is None:
            return super().copyfile(source, outputfile)
        while n > 0:
            chunk = source.read(min(65536, n))
            if not chunk:
                break
            outputfile.write(chunk)
            n -= len(chunk)

    def translate_path(self, path):
        path = path.split('?')[0].split('#')[0]
        if path.startswith('/video/'):
            return os.path.join(REPO, path.lstrip('/'))
        return os.path.join(REPO, 'public', path.lstrip('/'))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--fps', type=int, default=30)
    ap.add_argument('--preview', action='store_true', help='half-res, 15 fps quick check to /tmp/story-preview.mp4')
    args = ap.parse_args()
    fps = 15 if args.preview else args.fps
    scale = 0.5 if args.preview else 1.0

    os.makedirs(MEDIA, exist_ok=True)
    tmp_audio = '/tmp/story-soundtrack.wav'
    subprocess.run([sys.executable, os.path.join(REPO, 'video', 'make_soundtrack.py'), tmp_audio], check=True)
    lines = narration_lines()

    srv = http.server.ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    url = f'http://127.0.0.1:{srv.server_address[1]}/video/story.html'

    out = '/tmp/story-preview.mp4' if args.preview else os.path.join(MEDIA, 'story.mp4')
    cmd = [ffmpeg_exe(), '-y', '-loglevel', 'error',
           '-f', 'image2pipe', '-framerate', str(fps), '-c:v', 'mjpeg', '-i', '-',
           '-i', tmp_audio]
    if lines:
        parts = []
        for k, (start, path, tempo) in enumerate(lines):
            cmd += ['-i', path]
            ms = int(start * 1000)
            parts.append(f'[{k + 2}:a]silenceremove=start_periods=1:start_threshold=-45dB,atempo={tempo:.3f},'
                         f'aresample=48000,aformat=channel_layouts=stereo,adelay={ms}|{ms}[v{k}]')
        vox = ''.join(f'[v{k}]' for k in range(len(lines)))
        parts.append(f'{vox}amix=inputs={len(lines)}:duration=longest:normalize=0,volume=1.4,apad=whole_dur=76,asplit[vx1][vx2]')
        parts.append('[1:a][vx1]sidechaincompress=threshold=0.02:ratio=5:attack=30:release=500[duck]')
        parts.append('[duck][vx2]amix=inputs=2:duration=first:normalize=0[a]')
        cmd += ['-filter_complex', ';'.join(parts), '-map', '0:v', '-map', '[a]']
    else:
        cmd += ['-map', '0:v', '-map', '1:a']
    cmd += ['-c:v', 'libx264', '-preset', 'medium', '-crf', '24', '-pix_fmt', 'yuv420p',
            '-vf', f'scale={int(1920 * scale)}:{int(1080 * scale)}:out_range=tv,format=yuv420p', '-color_range', 'tv',
            '-c:a', 'aac', '-b:a', '160k', '-movflags', '+faststart', '-shortest', out]
    enc = subprocess.Popen(cmd, stdin=subprocess.PIPE)

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={'width': 1920, 'height': 1080})
        errors = []
        page.on('pageerror', lambda e: errors.append(str(e)))
        page.goto(url)
        page.evaluate('document.fonts.ready.then(() => true)')
        page.evaluate('STORY.loadClips()')
        page.wait_for_timeout(500)
        dur = page.evaluate('STORY.duration')
        total = int(dur * fps)
        for i in range(total):
            page.evaluate(f'STORY.render({i / fps})')
            enc.stdin.write(page.screenshot(type='jpeg', quality=93))
            if i % (fps * 5) == 0:
                print(f'  frame {i}/{total}', flush=True)
        if not args.preview:
            page.evaluate('STORY.render(70.5)')
            page.screenshot(path=os.path.join(MEDIA, 'story-poster.jpg'), type='jpeg', quality=85)
        browser.close()
    enc.stdin.close()
    if enc.wait() != 0:
        sys.exit('ffmpeg failed')
    if errors:
        print('page errors:', errors)
    print('wrote', out, f'{os.path.getsize(out) / 1e6:.1f} MB')


if __name__ == '__main__':
    main()
