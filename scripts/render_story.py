"""Render video/story.html into public/media/story.mp4 (+ poster), frame by frame.

story.html draws every frame as a pure function of time (window.STORY.render(t)), so this
captures exact frames rather than screen-recording, then muxes the synthesized soundtrack
(video/make_soundtrack.py) and, if present, voice-over lines from video/narration/
(generate them with video/tts_narration.py), each placed at its cue with the music ducked.

Optional AI b-roll: drop Veo/Flow clips at public/media/clips/{intro,turn,finale}.mp4 and
re-run; story.html picks them up automatically.

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


def narration_lines():
    """(start, wav) for each voice-over line in video/narration/ (see video/tts_narration.py)."""
    import json
    import wave
    spec = json.load(open(os.path.join(REPO, 'video', 'narration.json')))
    found = []
    for i, line in enumerate(spec['lines']):
        path = os.path.join(REPO, 'video', 'narration', line['id'] + '.wav')
        if not os.path.exists(path):
            continue
        with wave.open(path) as w:
            secs = w.getnframes() / w.getframerate()
        nxt = spec['lines'][i + 1]['start'] if i + 1 < len(spec['lines']) else 76
        if line['start'] + secs > nxt:
            print(f"warning: narration {line['id']} runs {line['start'] + secs - nxt:.1f}s past the next cue")
        found.append((line['start'], path))
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
    def log_message(self, *a):
        pass

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
        for k, (start, path) in enumerate(lines):
            cmd += ['-i', path]
            ms = int(start * 1000)
            parts.append(f'[{k + 2}:a]aresample=48000,aformat=channel_layouts=stereo,adelay={ms}|{ms}[v{k}]')
        vox = ''.join(f'[v{k}]' for k in range(len(lines)))
        parts.append(f'{vox}amix=inputs={len(lines)}:duration=longest:normalize=0,volume=1.4,asplit[vx1][vx2]')
        parts.append('[1:a][vx1]sidechaincompress=threshold=0.02:ratio=5:attack=30:release=500[duck]')
        parts.append('[duck][vx2]amix=inputs=2:duration=first:normalize=0[a]')
        cmd += ['-filter_complex', ';'.join(parts), '-map', '0:v', '-map', '[a]']
    else:
        cmd += ['-map', '0:v', '-map', '1:a']
    cmd += ['-c:v', 'libx264', '-preset', 'medium', '-crf', '21', '-pix_fmt', 'yuv420p',
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
