/* fx.js: shared futuristic motion layer for karthikeyanselvam.com.
 *
 * Auto-wires on DOMContentLoaded:
 *   [data-reveal]           scroll-reveal (blur + rise). Optional data-reveal-delay="0.15".
 *                           Siblings inside [data-reveal-stagger] get staggered delays.
 *   .fx-spot                cursor spotlight + glowing border (sets --mx / --my).
 *   canvas.fx-embers        drifting embers that wire into a neural mesh near the cursor.
 *                           data-density="1" scales particle count.
 *   [data-count]            count-up number when it scrolls into view (data-count="19").
 *   [data-fx-video="src"]   click opens a modal video player (data-fx-poster optional).
 *
 * Content is never hidden unless this script runs (it arms <html class="fx-armed">).
 * Everything respects prefers-reduced-motion.
 */
(function () {
    'use strict';
    var reduce = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;

    function ready(fn) {
        if (document.readyState !== 'loading') fn();
        else document.addEventListener('DOMContentLoaded', fn);
    }

    /* ---------------- Scroll reveal ---------------- */
    function initReveal(root) {
        var els = (root || document).querySelectorAll('[data-reveal]:not(.fx-in)');
        if (!els.length) return;
        if (reduce || !('IntersectionObserver' in window)) {
            els.forEach(function (el) { el.classList.add('fx-in'); });
            return;
        }
        document.querySelectorAll('[data-reveal-stagger]').forEach(function (group) {
            var step = parseFloat(group.getAttribute('data-reveal-stagger')) || 0.08;
            var kids = group.querySelectorAll(':scope > [data-reveal]');
            kids.forEach(function (el, i) {
                if (!el.style.getPropertyValue('--fx-delay')) el.style.setProperty('--fx-delay', (i * step).toFixed(2) + 's');
            });
        });
        els.forEach(function (el) {
            var d = el.getAttribute('data-reveal-delay');
            if (d) el.style.setProperty('--fx-delay', d + 's');
        });
        var io = new IntersectionObserver(function (entries) {
            entries.forEach(function (e) {
                if (e.isIntersecting) {
                    e.target.classList.add('fx-in');
                    io.unobserve(e.target);
                }
            });
        }, { rootMargin: '0px 0px -8% 0px', threshold: 0.08 });
        els.forEach(function (el) {
            // anything already on screen at load reveals immediately (no flash of empty hero)
            var r = el.getBoundingClientRect();
            if (r.top < window.innerHeight && r.bottom > 0) {
                requestAnimationFrame(function () { el.classList.add('fx-in'); });
            } else {
                io.observe(el);
            }
        });
    }

    /* ---------------- Spotlight cards ---------------- */
    function initSpot() {
        document.addEventListener('pointermove', function (ev) {
            var t = ev.target && ev.target.closest ? ev.target.closest('.fx-spot') : null;
            if (!t) return;
            var r = t.getBoundingClientRect();
            t.style.setProperty('--mx', (ev.clientX - r.left) + 'px');
            t.style.setProperty('--my', (ev.clientY - r.top) + 'px');
        }, { passive: true });
    }

    /* ---------------- Count-up ---------------- */
    function initCount() {
        var els = document.querySelectorAll('[data-count]');
        if (!els.length) return;
        function run(el) {
            var target = parseFloat(el.getAttribute('data-count'));
            var dec = (el.getAttribute('data-count').split('.')[1] || '').length;
            if (reduce) { el.textContent = target.toFixed(dec); return; }
            var t0 = null, dur = 1400;
            function step(ts) {
                if (!t0) t0 = ts;
                var p = Math.min(1, (ts - t0) / dur);
                var e = 1 - Math.pow(1 - p, 4);
                el.textContent = (target * e).toFixed(dec);
                if (p < 1) requestAnimationFrame(step);
            }
            requestAnimationFrame(step);
        }
        if (!('IntersectionObserver' in window)) { els.forEach(run); return; }
        var io = new IntersectionObserver(function (entries) {
            entries.forEach(function (e) {
                if (e.isIntersecting) { run(e.target); io.unobserve(e.target); }
            });
        }, { threshold: 0.4 });
        els.forEach(function (el) { io.observe(el); });
    }

    /* ---------------- Ember / neural canvas ---------------- */
    function Embers(canvas) {
        var ctx = canvas.getContext('2d');
        var dpr = Math.min(window.devicePixelRatio || 1, 2);
        var density = parseFloat(canvas.getAttribute('data-density')) || 1;
        var W = 0, H = 0, parts = [], mouse = { x: -9999, y: -9999 }, visible = true, raf = 0;
        var host = canvas.parentElement;

        function size() {
            var r = canvas.getBoundingClientRect();
            W = r.width; H = r.height;
            canvas.width = Math.round(W * dpr);
            canvas.height = Math.round(H * dpr);
            ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
            var n = Math.round(Math.min(140, (W * H) / 11000) * density);
            parts = [];
            for (var i = 0; i < n; i++) parts.push(spawn(true));
        }
        function spawn(anywhere) {
            return {
                x: Math.random() * W,
                y: anywhere ? Math.random() * H : H + 10,
                vx: (Math.random() - 0.5) * 0.15,
                vy: -(0.12 + Math.random() * 0.35),
                r: 0.6 + Math.random() * 1.8,
                a: 0.25 + Math.random() * 0.6,
                tw: Math.random() * Math.PI * 2
            };
        }
        function frame() {
            raf = 0;
            if (!visible) return;
            ctx.clearRect(0, 0, W, H);
            var linkDist = 120, mouseDist = 190;
            for (var i = 0; i < parts.length; i++) {
                var p = parts[i];
                p.tw += 0.03;
                p.x += p.vx + Math.sin(p.tw * 0.5) * 0.08;
                p.y += p.vy;
                var dxm = p.x - mouse.x, dym = p.y - mouse.y, dm = Math.sqrt(dxm * dxm + dym * dym);
                if (dm < mouseDist && dm > 0.1) { // gentle attraction toward the cursor
                    p.x -= dxm / dm * 0.25; p.y -= dym / dm * 0.25;
                }
                if (p.y < -10 || p.x < -20 || p.x > W + 20) parts[i] = p = spawn(false);
                var glow = p.a * (0.75 + 0.25 * Math.sin(p.tw));
                ctx.beginPath();
                ctx.fillStyle = 'rgba(255,' + (120 + Math.round(p.r * 25)) + ',70,' + glow.toFixed(3) + ')';
                ctx.shadowColor = 'rgba(255,107,53,0.9)';
                ctx.shadowBlur = 8 * p.r;
                ctx.arc(p.x, p.y, p.r, 0, Math.PI * 2);
                ctx.fill();
            }
            ctx.shadowBlur = 0;
            // neural mesh: link particles that are near each other AND near the cursor
            for (var a = 0; a < parts.length; a++) {
                var pa = parts[a];
                var da = Math.hypot(pa.x - mouse.x, pa.y - mouse.y);
                if (da > mouseDist * 1.4) continue;
                for (var b = a + 1; b < parts.length; b++) {
                    var pb = parts[b];
                    var d = Math.hypot(pa.x - pb.x, pa.y - pb.y);
                    if (d < linkDist) {
                        var k = (1 - d / linkDist) * (1 - da / (mouseDist * 1.4));
                        ctx.strokeStyle = 'rgba(255,140,90,' + (k * 0.55).toFixed(3) + ')';
                        ctx.lineWidth = 0.7;
                        ctx.beginPath(); ctx.moveTo(pa.x, pa.y); ctx.lineTo(pb.x, pb.y); ctx.stroke();
                    }
                }
            }
            raf = requestAnimationFrame(frame);
        }
        function kick() { if (!raf && visible) raf = requestAnimationFrame(frame); }

        size();
        window.addEventListener('resize', function () { size(); kick(); });
        (host || window).addEventListener('pointermove', function (e) {
            var r = canvas.getBoundingClientRect();
            mouse.x = e.clientX - r.left; mouse.y = e.clientY - r.top;
        }, { passive: true });
        (host || window).addEventListener('pointerleave', function () { mouse.x = mouse.y = -9999; });
        if ('IntersectionObserver' in window) {
            new IntersectionObserver(function (en) { visible = en[0].isIntersecting && !document.hidden; kick(); })
                .observe(canvas);
        }
        document.addEventListener('visibilitychange', function () { visible = !document.hidden; kick(); });
        canvas.classList.add('fx-on');
        kick();
    }
    function initEmbers() {
        if (reduce) return;
        document.querySelectorAll('canvas.fx-embers').forEach(function (c) { new Embers(c); });
    }

    /* ---------------- Video modal ---------------- */
    function initVideo() {
        var triggers = document.querySelectorAll('[data-fx-video]');
        if (!triggers.length) return;
        var modal = document.createElement('div');
        modal.className = 'fx-modal';
        modal.setAttribute('role', 'dialog');
        modal.setAttribute('aria-modal', 'true');
        modal.setAttribute('aria-label', 'Story video');
        modal.innerHTML = '<div class="fx-modal-inner"><button type="button" class="fx-modal-close">Close ✕</button>' +
            '<video controls playsinline preload="none"></video></div>';
        document.body.appendChild(modal);
        var video = modal.querySelector('video');
        var closeBtn = modal.querySelector('.fx-modal-close');
        var lastFocus = null;
        function open(src, poster) {
            lastFocus = document.activeElement;
            if (video.getAttribute('src') !== src) video.setAttribute('src', src);
            if (poster) video.setAttribute('poster', poster);
            modal.classList.add('fx-open');
            document.documentElement.style.overflow = 'hidden';
            closeBtn.focus();
            var p = video.play(); if (p && p.catch) p.catch(function () {});
        }
        function close() {
            modal.classList.remove('fx-open');
            video.pause();
            document.documentElement.style.overflow = '';
            if (lastFocus && lastFocus.focus) lastFocus.focus();
        }
        triggers.forEach(function (t) {
            t.addEventListener('click', function (e) {
                e.preventDefault();
                open(t.getAttribute('data-fx-video'), t.getAttribute('data-fx-poster'));
            });
        });
        closeBtn.addEventListener('click', close);
        modal.addEventListener('click', function (e) { if (e.target === modal) close(); });
        document.addEventListener('keydown', function (e) {
            if (e.key === 'Escape' && modal.classList.contains('fx-open')) close();
        });
    }

    // Arm reveal-hiding as early as possible (script is deferred, so before first paint is not
    // guaranteed; elements already on screen reveal on the next frame anyway).
    if (!reduce) document.documentElement.classList.add('fx-armed');

    ready(function () {
        initReveal();
        initSpot();
        initCount();
        initEmbers();
        initVideo();
    });

    // Pages that inject content later (e.g. opening a project) can call FX.reveal(container).
    window.FX = { reveal: initReveal };
})();
