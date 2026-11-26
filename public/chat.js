/* ────────────────────────────────────────────────────────────────────────────
   Skipper — shared chat widget for karthikeyanselvam.com
   Loaded by index.html, experience.html and newsletter.html (one source of
   truth — do not re-inline per page). Enhances the existing #chat-pop markup.

   Behaviour:
   • A new answer is revealed from its TOP (the question + start of the reply),
     never pinned to its last line.
   • After every answer, 2–3 follow-up questions are shown as chips (from the
     backend's `followups`, topped up from a curated pool).
   • Keyboard: with the input empty, Tab fills the next suggested question;
     Tab again moves to the next one; after the last, Tab behaves normally
     (no keyboard trap). ↑/↓ also browse suggestions. Enter sends.
   • Errors keep the question and offer Retry; requests time out after 30s.
   • Conversation persists across pages for the session; "New chat" resets.
   Public API: window.Skipper.{open, close, isOpen, ask}; events
   `skipper:open` / `skipper:close` on document.
──────────────────────────────────────────────────────────────────────────── */
(function () {
    'use strict';

    var ENDPOINT = 'https://us-central1-karthik-website-b5801.cloudfunctions.net/askKarthik';
    var CONTACT = 'skarthik1710@gmail.com';
    var STORE_KEY = 'skipperChat.v1';
    var TIMEOUT_MS = 30000;
    var MAX_SUGGESTIONS = 3;
    // Curated fallback follow-ups — every one is answerable from the assistant's facts.
    var POOL = [
        'What AI projects has he built?',
        'How does he approach AI governance?',
        'What did he do for Microsoft?',
        'What is RevokAI?',
        'How does he drive Copilot adoption?',
        'Walk me through his career',
        'What are his operating principles?',
        'Which certifications does he hold?',
        'What awards has he won?',
        'Why hire him as an AI leader?',
        'How can I contact him?'
    ];

    var $ = function (id) { return document.getElementById(id); };
    var pop = $('chat-pop'), fab = $('chat-fab'), log = $('chat-log'), form = $('chat-form'),
        input = $('chat-input'), sendBtn = $('chat-send'), chips = $('chat-chips'), caption = $('fab-caption');
    if (!pop || !log || !form || !input || !sendBtn) return;

    var mq = function (q) { return window.matchMedia ? window.matchMedia(q).matches : false; };
    var reduceMotion = mq('(prefers-reduced-motion: reduce)');
    var isMobile = function () { return mq('(max-width: 600px)'); };
    var hasHover = function () { return !mq('(hover: none)'); };
    var norm = function (s) { return String(s || '').toLowerCase().replace(/[^a-z0-9 ]+/g, ' ').replace(/\s+/g, ' ').trim(); };

    var welcomeHTML = log.innerHTML;          // trusted static markup from the page
    var defaultPlaceholder = input.getAttribute('placeholder') || '';
    var starters = chips ? Array.prototype.map.call(chips.querySelectorAll('.chat-chip'), function (b) { return b.textContent.trim(); }) : [];
    if (!starters.length) starters = POOL.slice(0, MAX_SUGGESTIONS);

    var history = [], busy = false, suggestions = starters.slice(), sugIdx = -1,
        controller = null, generation = 0, pendingReveal = null, lastFocus = null;

    // ── one-time DOM enhancement (a11y + new controls) ──
    var head = pop.querySelector('.chat-head');
    var title = head && head.querySelector('h3');
    if (title) { title.id = title.id || 'chat-title'; pop.setAttribute('aria-labelledby', title.id); pop.removeAttribute('aria-label'); }
    log.setAttribute('role', 'log');
    log.setAttribute('aria-live', 'polite');
    log.setAttribute('aria-relevant', 'additions');
    log.setAttribute('aria-label', 'Conversation with Skipper');
    log.setAttribute('tabindex', '0');        // scrollable region must be keyboard-reachable
    input.setAttribute('aria-label', 'Ask Skipper a question');
    input.setAttribute('enterkeyhint', 'send');
    if (fab) { fab.setAttribute('aria-controls', 'chat-pop'); fab.setAttribute('aria-expanded', 'false'); }
    if (chips) { chips.setAttribute('role', 'group'); chips.setAttribute('aria-label', 'Suggested questions'); }

    var hint = document.createElement('div');
    hint.className = 'chat-hint';
    hint.id = 'chat-hint';
    hint.setAttribute('aria-live', 'off');
    form.insertAdjacentElement('afterend', hint);
    input.setAttribute('aria-describedby', 'chat-hint');

    var resetBtn = document.createElement('button');
    resetBtn.type = 'button';
    resetBtn.className = 'chat-reset';
    resetBtn.setAttribute('aria-label', 'Start a new conversation');
    resetBtn.title = 'New chat';
    resetBtn.innerHTML = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M3 12a9 9 0 1 0 3-6.7"/><path d="M3 4v5h5"/></svg>';
    resetBtn.hidden = true;
    var closeBtn = pop.querySelector('.chat-pop-close');
    if (head) head.insertBefore(resetBtn, closeBtn || null);

    // ── safe rich-text rendering (DOM nodes only — never innerHTML of model text) ──
    function appendInline(parent, text) {
        var re = /\*\*([^*\n]+)\*\*|(https?:\/\/[^\s<>"']+)|([A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,})/g;
        var last = 0, m;
        var pushText = function (t) { if (t) parent.appendChild(document.createTextNode(t.replace(/\*\*/g, ''))); };
        while ((m = re.exec(text)) !== null) {
            pushText(text.slice(last, m.index));
            if (m[1] !== undefined) {
                var b = document.createElement('strong'); b.textContent = m[1]; parent.appendChild(b);
                last = re.lastIndex;
            } else {
                var raw = m[2] || m[3], trail = '';
                while (/[.,;:!?)\]]$/.test(raw)) { trail = raw.slice(-1) + trail; raw = raw.slice(0, -1); }
                var a = document.createElement('a');
                a.textContent = raw;
                if (m[2]) { a.href = raw; a.target = '_blank'; a.rel = 'noopener noreferrer'; }
                else { a.href = 'mailto:' + raw; }
                parent.appendChild(a);
                last = re.lastIndex - trail.length;
            }
        }
        pushText(text.slice(last));
    }
    function renderRich(container, text) {
        var listRe = /^\s*(?:[-*•]|\d+[.)])\s+/, numRe = /^\s*(\d+)[.)]\s+/;
        var lastList = null;   // lets "1. …\n\n2. …" (blank-line separated) continue one list
        String(text).replace(/\r/g, '').split(/\n{2,}/).forEach(function (block) {
            var lines = block.split('\n').filter(function (l) { return l.trim(); });
            var para = null, list = null;
            lines.forEach(function (l) {
                if (listRe.test(l)) {
                    var num = l.match(numRe), tag = num ? 'OL' : 'UL';
                    if (!list) {
                        var canContinue = lastList && lastList.tagName === tag && !para && list === null &&
                            container.lastChild === lastList && (!num || +num[1] === lastList.children.length + (lastList.start || 1));
                        if (canContinue) list = lastList;
                        else {
                            list = document.createElement(tag.toLowerCase());
                            if (num && +num[1] !== 1) list.start = +num[1];
                            container.appendChild(list);
                        }
                    }
                    var li = document.createElement('li'); appendInline(li, l.replace(listRe, '')); list.appendChild(li);
                    para = null; lastList = list;
                } else {
                    if (!para) { para = document.createElement('p'); container.appendChild(para); }
                    else para.appendChild(document.createElement('br'));
                    appendInline(para, l);
                    list = null; lastList = null;
                }
            });
        });
    }

    function addMsg(role, text, isError) {
        var div = document.createElement('div');
        div.className = 'chat-msg ' + (role === 'user' ? 'user' : 'bot rich') + (isError ? ' error' : '');
        var who = document.createElement('span');
        who.className = 'chat-sr';
        who.textContent = role === 'user' ? 'You: ' : 'Skipper: ';
        div.appendChild(who);
        if (role === 'user') div.appendChild(document.createTextNode(text));
        else renderRich(div, text);
        log.appendChild(div);
        return div;
    }

    // ── scrolling ──
    function scrollToBottom() { log.scrollTop = log.scrollHeight; }
    function scrollToTopOf(el, smooth) {
        var top = el.getBoundingClientRect().top - log.getBoundingClientRect().top + log.scrollTop - 10;
        var opts = { top: Math.max(0, top), behavior: smooth && !reduceMotion ? 'smooth' : 'auto' };
        if (typeof log.scrollTo === 'function') log.scrollTo(opts); else log.scrollTop = opts.top;
    }
    // Show the visitor's question and the START of the answer, not its last line.
    function revealReply(userEl, replyEl, smooth) {
        if (!isOpen()) { pendingReveal = { userEl: userEl, replyEl: replyEl }; return; }
        var anchor = userEl && userEl.isConnected && userEl.offsetHeight < log.clientHeight * 0.4 ? userEl : replyEl;
        scrollToTopOf(anchor, smooth);
    }

    // ── suggestions (chips + Tab) ──
    function askedSet() {
        var s = {};
        history.forEach(function (m) { if (m.role === 'user') s[norm(m.content)] = 1; });
        return s;
    }
    function setSuggestions(list) {
        var asked = askedSet(), seen = {}, out = [];
        var add = function (q) {
            if (typeof q !== 'string') return;
            q = q.trim(); var k = norm(q);
            if (!k || asked[k] || seen[k] || out.length >= MAX_SUGGESTIONS) return;
            seen[k] = 1; out.push(q);
        };
        (Array.isArray(list) ? list : []).forEach(add);
        if (out.length < 2) POOL.forEach(add);
        suggestions = out;
        sugIdx = -1;
        renderChips();
        updateHint();
    }
    function renderChips() {
        if (!chips) return;
        var hadFocus = chips.contains(document.activeElement);
        chips.innerHTML = '';
        chips.style.display = '';
        chips.hidden = !suggestions.length;
        if (!suggestions.length) { if (hadFocus) focusInput(); return; }
        var label = document.createElement('span');
        label.className = 'chat-chips-label';
        label.textContent = history.length ? 'Ask next' : 'Try asking';
        label.setAttribute('aria-hidden', 'true');
        chips.appendChild(label);
        suggestions.forEach(function (q, i) {
            var b = document.createElement('button');
            b.type = 'button';
            b.className = 'chat-chip' + (i === sugIdx ? ' active' : '');
            b.textContent = q;
            b.disabled = busy;
            b.addEventListener('click', function () { ask(q); });
            chips.appendChild(b);
        });
        if (history.length && !reduceMotion) { chips.classList.remove('chat-fresh'); void chips.offsetWidth; chips.classList.add('chat-fresh'); }
        if (hadFocus) {
            var first = chips.querySelector('.chat-chip');
            if (first && !busy) first.focus({ preventScroll: true }); else focusInput();
        }
    }
    function markActiveChip() {
        if (!chips) return;
        Array.prototype.forEach.call(chips.querySelectorAll('.chat-chip'), function (b, i) { b.classList.toggle('active', i === sugIdx); });
    }
    function kbd(k) { return '<kbd>' + k + '</kbd>'; }
    function updateHint() {
        var showSug = suggestions.length && !busy;
        input.placeholder = showSug && !input.value ? suggestions[0] : defaultPlaceholder;
        if (!hasHover()) { hint.hidden = true; return; }
        hint.hidden = false;
        if (busy) hint.innerHTML = 'Skipper is answering…';
        else if (sugIdx >= 0 && input.value === suggestions[sugIdx]) {
            hint.innerHTML = (sugIdx < suggestions.length - 1 ? kbd('Tab') + ' next suggestion · ' : '') +
                kbd('Enter') + ' ask · ' + (sugIdx + 1) + '/' + suggestions.length;
        } else if (showSug && !input.value) hint.innerHTML = kbd('Tab') + ' use suggested question · ' + kbd('↑') + kbd('↓') + ' browse';
        else hint.innerHTML = kbd('Enter') + ' to ask';
    }
    function fillSuggestion(i) {
        sugIdx = i;
        input.value = suggestions[i];
        try { input.setSelectionRange(input.value.length, input.value.length); } catch (e) { /* noop */ }
        markActiveChip();
        updateHint();
    }
    input.addEventListener('keydown', function (e) {
        if (e.isComposing || e.altKey || e.ctrlKey || e.metaKey || busy || !suggestions.length) return;
        var v = input.value;
        var onSuggestion = sugIdx >= 0 && v === suggestions[sugIdx];
        if (e.key === 'Tab' && !e.shiftKey) {
            var next = v.trim() === '' ? 0 : (onSuggestion ? sugIdx + 1 : -1);
            if (next < 0) return;                                  // own text: normal Tab
            if (next >= suggestions.length) { sugIdx = -1; markActiveChip(); updateHint(); return; } // past last: normal Tab, no trap
            e.preventDefault();
            fillSuggestion(next);
        } else if ((e.key === 'ArrowDown' || e.key === 'ArrowUp') && (v === '' || onSuggestion)) {
            e.preventDefault();
            var n = suggestions.length, cur = onSuggestion ? sugIdx : (e.key === 'ArrowDown' ? -1 : 0);
            fillSuggestion(((cur + (e.key === 'ArrowDown' ? 1 : -1)) % n + n) % n);
        }
    });
    input.addEventListener('input', function () {
        if (sugIdx >= 0 && input.value !== suggestions[sugIdx]) { sugIdx = -1; markActiveChip(); }
        updateHint();
    });

    // ── busy state ──
    function setBusy(b) {
        busy = b;
        sendBtn.disabled = b;
        if (b) log.setAttribute('aria-busy', 'true'); else log.removeAttribute('aria-busy');
        if (chips) Array.prototype.forEach.call(chips.querySelectorAll('.chat-chip'), function (c) { c.disabled = b; });
        resetBtn.hidden = !history.length && !b;
        updateHint();
    }
    function focusInput() { if (!isMobile()) input.focus({ preventScroll: true }); }

    // ── persistence (session only) ──
    function save() {
        try { sessionStorage.setItem(STORE_KEY, JSON.stringify({ history: history.slice(-24), suggestions: suggestions })); } catch (e) { /* noop */ }
    }
    function restore() {
        var st;
        try { st = JSON.parse(sessionStorage.getItem(STORE_KEY) || 'null'); } catch (e) { st = null; }
        if (!st || !Array.isArray(st.history) || !st.history.length) return;
        history = st.history.filter(function (m) {
            return m && (m.role === 'user' || m.role === 'assistant') && typeof m.content === 'string' && m.content.trim();
        });
        var lastUserEl = null, lastEl = null;
        history.forEach(function (m) {
            lastEl = addMsg(m.role, m.content);
            if (m.role === 'user') lastUserEl = lastEl;
        });
        if (lastEl) pendingReveal = { userEl: lastUserEl, replyEl: lastEl };
        setSuggestions(st.suggestions);
        resetBtn.hidden = !history.length;
    }

    // ── conversation ──
    async function ask(text) {
        text = String(text || '').trim();
        if (!text || busy) return;
        if (!isOpen()) open();
        var gen = ++generation;
        input.value = '';
        sugIdx = -1;
        history.push({ role: 'user', content: text });
        var userEl = addMsg('user', text);
        setBusy(true);

        var typing = document.createElement('div');
        typing.className = 'chat-typing';
        typing.setAttribute('aria-hidden', 'true');
        typing.innerHTML = '<span></span><span></span><span></span>';
        log.appendChild(typing);
        scrollToBottom();

        var ctrl = (typeof AbortController !== 'undefined') ? new AbortController() : null;
        controller = ctrl;
        var timedOut = false;
        var timer = setTimeout(function () { timedOut = true; if (ctrl) ctrl.abort(); }, TIMEOUT_MS);
        var status = 0, data = {}, failure = null;
        try {
            var r = await fetch(ENDPOINT, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ messages: history.slice(-12) }),
                signal: ctrl ? ctrl.signal : undefined
            });
            status = r.status;
            data = await r.json().catch(function () { return {}; });
            if (!r.ok || typeof data.reply !== 'string' || !data.reply.trim()) failure = 'server';
        } catch (err) {
            failure = timedOut ? 'timeout' : 'network';
        }
        clearTimeout(timer);
        if (controller === ctrl) controller = null;
        if (gen !== generation) return;                  // conversation was reset mid-flight — drop this result
        typing.remove();

        if (!failure && data.blocked) {
            // Server refused this prompt: show its message, but drop the turn so the
            // blocked text is never resent with later questions.
            history.pop();
            userEl.classList.add('failed');
            var noteEl = addMsg('bot', data.reply.trim());
            setBusy(false);
            setSuggestions(data.followups);
            revealReply(userEl, noteEl, true);
            save();
        } else if (!failure) {
            var botEl = addMsg('bot', data.reply.trim());
            history.push({ role: 'assistant', content: data.reply.trim() });
            setBusy(false);
            setSuggestions(data.followups);
            revealReply(userEl, botEl, true);
            if (!isOpen() && fab) fab.classList.add('unread');
            save();
        } else {
            history.pop();                               // keep backend role alternation
            userEl.classList.add('failed');
            var msg = failure === 'timeout' ? 'That took too long — please try again.'
                : failure === 'network' ? 'Connection problem — please check your connection and try again.'
                : (data.error || 'Something went wrong — please try again.');
            if (msg.indexOf('@') < 0) msg += ' Or email ' + CONTACT + '.';
            var errEl = addMsg('bot', msg, true);
            var retryable = status !== 429 && status !== 400;
            if (retryable) {
                var retry = document.createElement('button');
                retry.type = 'button';
                retry.className = 'chat-retry';
                retry.textContent = 'Retry';
                retry.addEventListener('click', function () {
                    if (busy) return;
                    errEl.remove(); userEl.remove();
                    ask(text);
                });
                errEl.appendChild(retry);
            } else if (!input.value) {
                input.value = text;                      // keep their question; don't make them retype it
            }
            setBusy(false);
            renderChips();
            revealReply(userEl, errEl, true);
        }
        if (isOpen()) focusInput();
    }

    function reset() {
        generation++;
        if (controller) { try { controller.abort(); } catch (e) { /* noop */ } controller = null; }
        history = [];
        pendingReveal = null;
        log.innerHTML = welcomeHTML;
        try { sessionStorage.removeItem(STORE_KEY); } catch (e) { /* noop */ }
        input.value = '';
        setBusy(false);
        setSuggestions(starters);
        resetBtn.hidden = true;
        log.scrollTop = 0;
        if (isMobile()) { if (closeBtn) closeBtn.focus({ preventScroll: true }); }
        else focusInput();
    }

    // ── open / close ──
    function isOpen() { return pop.classList.contains('open'); }
    function open() {
        if (isOpen()) return;
        lastFocus = document.activeElement;
        pop.classList.add('open');
        document.body.classList.add('chat-open');
        if (fab) { fab.classList.add('open'); fab.classList.remove('unread'); fab.setAttribute('aria-expanded', 'true'); }
        if (caption) caption.classList.add('hide');
        syncViewport();
        if (pendingReveal) { var p = pendingReveal; pendingReveal = null; revealReply(p.userEl, p.replyEl, false); }
        if (isMobile()) { if (closeBtn) closeBtn.focus({ preventScroll: true }); }
        else input.focus({ preventScroll: true });
        document.dispatchEvent(new CustomEvent('skipper:open'));
    }
    function close() {
        if (!isOpen()) return;
        var focusWasInside = pop.contains(document.activeElement);
        pop.classList.remove('open');
        document.body.classList.remove('chat-open');
        if (fab) { fab.classList.remove('open'); fab.setAttribute('aria-expanded', 'false'); }
        if (caption) caption.classList.remove('hide');
        if (focusWasInside) {
            var usable = lastFocus && lastFocus !== document.body && document.contains(lastFocus) &&
                !pop.contains(lastFocus) && lastFocus.getClientRects().length > 0;
            var back = usable ? lastFocus : fab;
            if (back) back.focus({ preventScroll: true });
            if (fab && document.activeElement !== back) fab.focus({ preventScroll: true });
        }
        document.dispatchEvent(new CustomEvent('skipper:close'));
    }

    // Mobile full-screen chat: size to the *visual* viewport so the on-screen
    // keyboard never covers the input.
    // Short screens (landscape phones, on-screen keyboard) get a compact layout so
    // the input row is never clipped.
    function syncViewport() {
        var vv = window.visualViewport;
        var h = vv ? vv.height : window.innerHeight;
        if (vv) {
            document.documentElement.style.setProperty('--chat-vh', vv.height + 'px');
            document.documentElement.style.setProperty('--chat-vt', vv.offsetTop + 'px');
        }
        pop.classList.toggle('chat-compact', h < 560);
    }
    if (window.visualViewport) {
        window.visualViewport.addEventListener('resize', syncViewport);
        window.visualViewport.addEventListener('scroll', syncViewport);
    }
    window.addEventListener('resize', syncViewport);
    syncViewport();

    // ── wiring ──
    if (fab) fab.addEventListener('click', function () { isOpen() ? close() : open(); });
    if (closeBtn) closeBtn.addEventListener('click', close);
    resetBtn.addEventListener('click', reset);
    form.addEventListener('submit', function (e) { e.preventDefault(); ask(input.value); });
    document.addEventListener('keydown', function (e) {
        if (e.key !== 'Escape' || !isOpen()) return;
        // Let page-level modals (story overlay, newsletter article) handle Escape first.
        if (document.querySelector('[aria-modal="true"].open:not(#chat-pop), .modal-overlay.active')) return;
        close();
    });

    restore();
    if (!history.length) renderChips();
    updateHint();

    window.Skipper = { open: open, close: close, isOpen: isOpen, ask: ask };
})();
