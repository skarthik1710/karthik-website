/* seasons.js: page-wide seasonal backdrop for karthikeyanselvam.com.
 *
 * Reads <html data-season="spring|summer|monsoon|winter"> and draws a fixed canvas behind
 * all content:
 *   spring   blossom petals tumbling down
 *   summer   a slow sun glow with drifting golden motes
 *   monsoon  slanted rain with small ripples at the bottom edge
 *   winter   snowfall with parallax
 * The matching colour tint lives in seasons.css, so pages look right without this script.
 * Under prefers-reduced-motion nothing animates (tint only). Pauses when the tab is hidden.
 */
(function () {
    'use strict';
    var root = document.documentElement;
    var season = root.getAttribute('data-season');
    if (!season) return;
    if (window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;

    function ready(fn) {
        if (document.readyState !== 'loading') fn();
        else document.addEventListener('DOMContentLoaded', fn);
    }

    function rand(a, b) { return a + Math.random() * (b - a); }
    function pick(arr) { return arr[(Math.random() * arr.length) | 0]; }

    function start() {
        var cv = document.createElement('canvas');
        cv.className = 'season-fx';
        cv.setAttribute('aria-hidden', 'true');
        document.body.insertBefore(cv, document.body.firstChild);
        var ctx = cv.getContext('2d');
        if (!ctx) return;

        var W = 0, H = 0, dpr = 1, items = [], extras = [], t0 = 0, running = true, raf = 0;
        var sys = SYSTEMS[season];
        if (!sys) return;

        function resize() {
            dpr = Math.min(window.devicePixelRatio || 1, 1.5);
            W = window.innerWidth; H = window.innerHeight;
            cv.width = Math.round(W * dpr); cv.height = Math.round(H * dpr);
            ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
            var n = Math.min(sys.max, Math.round(W * H / sys.area));
            while (items.length < n) items.push(sys.make(W, H, true));
            items.length = n;
        }

        function frame(ts) {
            if (!running) return;
            var dt = t0 ? Math.min((ts - t0) / 16.667, 3) : 1;   // 1.0 = one 60 fps frame
            t0 = ts;
            ctx.clearRect(0, 0, W, H);
            if (sys.backdrop) sys.backdrop(ctx, W, H, ts);
            for (var i = 0; i < items.length; i++) {
                var p = items[i];
                if (sys.step(p, dt, W, H, ts, extras)) items[i] = p = sys.make(W, H, false);
                sys.draw(ctx, p, ts);
            }
            if (sys.extras) sys.extras(ctx, extras, dt);
            raf = requestAnimationFrame(frame);
        }

        document.addEventListener('visibilitychange', function () {
            running = !document.hidden;
            if (running) { t0 = 0; raf = requestAnimationFrame(frame); } else cancelAnimationFrame(raf);
        });
        var rt;
        window.addEventListener('resize', function () { clearTimeout(rt); rt = setTimeout(resize, 120); });
        resize();
        raf = requestAnimationFrame(frame);
        requestAnimationFrame(function () { cv.classList.add('season-on'); });
    }

    /* ---------------- particle systems ----------------
       make(W,H,initial) -> particle; step(...) -> true when it should respawn; draw(ctx,p). */
    var SYSTEMS = {
        spring: {
            area: 26000, max: 55,
            make: function (W, H, initial) {
                return {
                    x: rand(-40, W + 40), y: initial ? rand(-H, H) : rand(-80, -20),
                    r: rand(5, 11), vy: rand(0.35, 0.9), vx: rand(0.15, 0.55),
                    rot: rand(0, 6.28), vr: rand(-0.02, 0.02), flip: rand(0, 6.28), vf: rand(0.02, 0.05),
                    sway: rand(0.6, 1.6), ph: rand(0, 6.28),
                    col: pick(['255,176,204', '255,198,220', '255,226,236', '250,150,186']),
                    a: rand(0.5, 0.85)
                };
            },
            step: function (p, dt, W, H) {
                p.ph += 0.012 * dt;
                p.x += (p.vx + Math.sin(p.ph) * p.sway * 0.5) * dt;
                p.y += p.vy * dt;
                p.rot += p.vr * dt; p.flip += p.vf * dt;
                return p.y > H + 30 || p.x > W + 60;
            },
            draw: function (ctx, p) {
                var r = p.r;
                ctx.save();
                ctx.translate(p.x, p.y);
                ctx.rotate(p.rot);
                ctx.scale(Math.max(0.15, Math.abs(Math.cos(p.flip))), 1);   // tumbling
                ctx.globalAlpha = p.a;
                ctx.fillStyle = 'rgb(' + p.col + ')';
                ctx.beginPath();                                          // notched petal
                ctx.moveTo(0, r);
                ctx.bezierCurveTo(r * 0.95, r * 0.35, r * 0.7, -r * 0.8, r * 0.22, -r);
                ctx.lineTo(0, -r * 0.72);
                ctx.lineTo(-r * 0.22, -r);
                ctx.bezierCurveTo(-r * 0.7, -r * 0.8, -r * 0.95, r * 0.35, 0, r);
                ctx.fill();
                ctx.restore();
            }
        },

        summer: {
            area: 20000, max: 70,
            backdrop: function (ctx, W, H, ts) {
                var cx = W * 0.86, cy = -H * 0.06, R = Math.max(W, H) * 0.75;
                var pulse = 0.85 + 0.15 * Math.sin(ts / 3200);
                var g = ctx.createRadialGradient(cx, cy, 0, cx, cy, R);
                g.addColorStop(0, 'rgba(255,196,110,' + (0.20 * pulse) + ')');
                g.addColorStop(0.35, 'rgba(255,150,60,' + (0.07 * pulse) + ')');
                g.addColorStop(1, 'rgba(255,140,50,0)');
                ctx.fillStyle = g;
                ctx.fillRect(0, 0, W, H);
                ctx.save();                                               // slow-turning rays
                ctx.translate(cx, cy);
                ctx.rotate(ts / 60000);
                for (var i = 0; i < 12; i++) {
                    ctx.rotate(Math.PI / 6);
                    var rg = ctx.createLinearGradient(0, 0, 0, R);
                    rg.addColorStop(0, 'rgba(255,205,130,' + (0.05 * pulse) + ')');
                    rg.addColorStop(1, 'rgba(255,205,130,0)');
                    ctx.fillStyle = rg;
                    ctx.beginPath();
                    ctx.moveTo(0, 0); ctx.lineTo(-R * 0.06, R); ctx.lineTo(R * 0.06, R);
                    ctx.fill();
                }
                ctx.restore();
            },
            make: function (W, H, initial) {
                return {
                    x: rand(0, W), y: initial ? rand(0, H) : H + rand(5, 30),
                    r: rand(0.8, 2.4), vy: -rand(0.08, 0.35), vx: rand(-0.12, 0.2),
                    ph: rand(0, 6.28), tw: rand(0.01, 0.03), a: rand(0.3, 0.8)
                };
            },
            step: function (p, dt, W, H) {
                p.ph += p.tw * dt;
                p.x += (p.vx + Math.sin(p.ph * 0.7) * 0.15) * dt;
                p.y += p.vy * dt;
                return p.y < -20 || p.x < -20 || p.x > W + 20;
            },
            draw: function (ctx, p) {
                var a = p.a * (0.55 + 0.45 * Math.sin(p.ph * 2));
                var g = ctx.createRadialGradient(p.x, p.y, 0, p.x, p.y, p.r * 5);
                g.addColorStop(0, 'rgba(255,214,140,' + a + ')');
                g.addColorStop(0.3, 'rgba(255,170,80,' + (a * 0.35) + ')');
                g.addColorStop(1, 'rgba(255,150,60,0)');
                ctx.fillStyle = g;
                ctx.beginPath(); ctx.arc(p.x, p.y, p.r * 5, 0, 6.283); ctx.fill();
            }
        },

        monsoon: {
            area: 5200, max: 260,
            make: function (W, H, initial) {
                var z = rand(0.4, 1);                                     // depth: near drops are longer, faster
                return {
                    x: rand(-60, W + 120), y: initial ? rand(-H, H) : rand(-120, -10),
                    len: 10 + 18 * z, v: 7 + 9 * z, a: 0.10 + 0.28 * z, w: 0.6 + 0.8 * z,
                    stop: H - rand(0, H * 0.04)                              // lands at the bottom edge
                };
            },
            step: function (p, dt, W, H, ts, extras) {
                p.y += p.v * dt;
                p.x += -0.22 * p.v * dt;
                if (p.y >= p.stop) {
                    if (extras.length < 40 && Math.random() < 0.35) extras.push({ x: p.x, y: p.stop, r: 1, a: p.a * 1.6 });
                    return true;
                }
                return false;
            },
            draw: function (ctx, p) {
                ctx.strokeStyle = 'rgba(176,200,226,' + p.a + ')';
                ctx.lineWidth = p.w;
                ctx.beginPath();
                ctx.moveTo(p.x, p.y);
                ctx.lineTo(p.x + 0.22 * p.len, p.y - p.len);
                ctx.stroke();
            },
            extras: function (ctx, ripples, dt) {                         // splash rings
                for (var i = ripples.length - 1; i >= 0; i--) {
                    var s = ripples[i];
                    s.r += 0.6 * dt; s.a -= 0.018 * dt;
                    if (s.a <= 0) { ripples.splice(i, 1); continue; }
                    ctx.strokeStyle = 'rgba(176,200,226,' + s.a + ')';
                    ctx.lineWidth = 0.8;
                    ctx.beginPath(); ctx.ellipse(s.x, s.y, s.r * 2.2, s.r * 0.6, 0, 0, 6.283); ctx.stroke();
                }
            }
        },

        winter: {
            area: 9000, max: 170,
            make: function (W, H, initial) {
                var z = rand(0.3, 1);
                return {
                    x: rand(-20, W + 20), y: initial ? rand(-H, H) : rand(-30, -5),
                    r: 0.8 + 2.4 * z, vy: 0.25 + 0.9 * z, sway: 0.3 + 0.7 * z,
                    ph: rand(0, 6.28), a: 0.3 + 0.55 * z
                };
            },
            step: function (p, dt, W, H) {
                p.ph += 0.01 * dt;
                p.x += (Math.sin(p.ph) * p.sway + 0.12) * dt;
                p.y += p.vy * dt;
                return p.y > H + 10;
            },
            draw: function (ctx, p) {
                ctx.fillStyle = 'rgba(236,244,255,' + p.a + ')';
                ctx.beginPath(); ctx.arc(p.x, p.y, p.r, 0, 6.283); ctx.fill();
            }
        }
    };

    ready(start);   // after SYSTEMS is defined: deferred scripts can run this synchronously
})();
