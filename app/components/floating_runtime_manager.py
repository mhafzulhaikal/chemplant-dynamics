# app/components/floating_runtime_manager.py

"""Floating, draggable Runtime Manager dialog.

Mounts the Runtime Manager card inside a ``ui.dialog`` so it floats
above the page (Quasar portal). The card can be dragged by the header
and resized via 8-direction handles. Position + size are persisted to
``sessionStorage`` (per tab).

Pointer Events (not HTML5 DnD) are used because ``dragend`` reports
``clientX=0`` in WebKit/Gecko and has no touch support.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

from nicegui import ui

logger = logging.getLogger(__name__)


def _ensure_namespace_js() -> str:
    """Return JS that initializes the shared client-side namespaces.

    Both the drag script and the re-apply script need these maps to
    exist before they run. Calling this script is idempotent — running
    it multiple times is a no-op after the first.
    """
    return """window.__floatingRuntimeManagerCtl =
           window.__floatingRuntimeManagerCtl || {};
           window.__floatingRuntimeManagerPositions =
           window.__floatingRuntimeManagerPositions || {};"""


def _drag_script(card_id: str, case_slug: str) -> str:
    """Return the JS that binds pointer-based drag to ``card_id``.

    Targets the ``.runtime-manager-page-header`` row of the card
    (the card chrome the body renderer already emits — so we don't
    need a new DOM element just to act as a drag handle). The script
    is self-contained: it skips drags that started on interactive
    children (buttons, inputs, selects, q-field, role=button) so the
    user can still click the close button, status label, and any
    other control inside the header.

    The controller for the active drag listeners is stored at
    ``window.__floatingRuntimeManagerCtl[caseSlug]``, keyed by case
    slug. Storing it off-DOM (not on the card element) is what makes
    teardown survive Quasar destroying and recreating the card on
    close/open.

    The script registers a persistent document-level listener for the
    ``__floatingRuntimeManagerRebind:<case>`` CustomEvent so the
    re-apply script can request a full rebind when needed (controller
    aborted, card replaced, etc.).
    """
    return f"""
    (function() {{
        var cardId = {card_id!r};
        var caseSlug = {case_slug!r};

        window.__floatingRuntimeManagerCtl =
            window.__floatingRuntimeManagerCtl || {{}};
        window.__floatingRuntimeManagerPositions =
            window.__floatingRuntimeManagerPositions || {{}};

        // Idempotent install — re-running this script (e.g. on
        // hot-reload) must not stack rebind listeners.
        var installFlag = '__floatingRuntimeManagerInstalled_' + caseSlug;
        if (window[installFlag]) {{
            // Update the registered card id (in case the dialog was
            // rebuilt) and ask the existing install to rebind.
            window.__floatingRuntimeManagerCardId =
                window.__floatingRuntimeManagerCardId || {{}};
            window.__floatingRuntimeManagerCardId[caseSlug] = cardId;
            document.dispatchEvent(new CustomEvent(
                '__floatingRuntimeManagerRebind:' + caseSlug,
            ));
            return;
        }}
        window[installFlag] = true;
        window.__floatingRuntimeManagerCardId =
            window.__floatingRuntimeManagerCardId || {{}};
        window.__floatingRuntimeManagerCardId[caseSlug] = cardId;

        // Seed the position namespace from sessionStorage if the JS
        // map does not already know about this case.
        if (!window.__floatingRuntimeManagerPositions[caseSlug]) {{
            var stored = null;
            try {{
                var raw = window.sessionStorage.getItem(
                    'floatingRuntimeManager:' + caseSlug,
                );
                if (raw) {{ stored = JSON.parse(raw); }}
            }} catch (_) {{ stored = null; }}
            if (stored && typeof stored.left === 'number'
                && typeof stored.top === 'number') {{
                window.__floatingRuntimeManagerPositions[caseSlug] = stored;
            }}
        }}

        function persist(left, top) {{
            var rounded = {{ left: Math.round(left), top: Math.round(top) }};
            window.__floatingRuntimeManagerPositions[caseSlug] = rounded;
            try {{
                window.sessionStorage.setItem(
                    'floatingRuntimeManager:' + caseSlug,
                    JSON.stringify(rounded),
                );
            }} catch (_) {{ /* private mode etc. */ }}
        }}

        function getCard() {{
            var liveCardId = (
                window.__floatingRuntimeManagerCardId || {{}}
            )[caseSlug] || cardId;
            // Walk live Quasar dialogs first. The card stays in the
            // slot even when the dialog is hidden.
            var dialogs = document.querySelectorAll('.q-dialog');
            for (var i = dialogs.length - 1; i >= 0; i--) {{
                var c = dialogs[i].querySelector(
                    '.runtime-manager-page-card',
                );
                if (c) {{
                    if (!c.id) {{ c.id = liveCardId; }}
                    if (!c.classList.contains(
                        'floating-runtime-manager-card',
                    )) {{
                        c.classList.add('floating-runtime-manager-card');
                    }}
                    return c;
                }}
            }}
            // Fallback: id-based lookup, but only if the result is
            // actually attached to the live document. A detached
            // node is never what we want.
            var byId = document.getElementById(liveCardId);
            if (byId && document.body.contains(byId)) {{ return byId; }}
            return null;
        }}

        function centeredDefault(card) {{
            // Center the card inside the *content* area, not the
            // full viewport. ``getContentRect`` accounts for any
            // open left drawer so the dialog appears centered on
            // the visible content, both when the drawer is open
            // and when it is closed.
            var content = getContentRect();
            var rect = card.getBoundingClientRect();
            // Guard against zero / unmeasured dimensions. The
            // card is ``position: fixed`` with a CSS width of
            // ``min(720px, calc(100vw - 2rem))``, so before the
            // first paint ``getBoundingClientRect`` can return
            // 0×0. ``offsetWidth`` / ``offsetHeight`` are
            // typically populated by the time the double-rAF in
            // ``applyPosition`` runs, but we still defend with a
            // sane fallback.
            var width = Math.max(
                320,
                rect.width || card.offsetWidth || 360,
            );
            var height = Math.max(
                240,
                rect.height || card.offsetHeight || 480,
            );
            // Center within ``[content.left, content.right]``.
            // ``Math.max(content.left, ...)`` guarantees the card
            // never sits under the drawer even if the math
            // computes a negative offset for a very wide card.
            return {{
                left: Math.max(content.left + 8, Math.round(
                    content.left + (content.right - content.left - width) / 2,
                )),
                top: Math.max(8, Math.round(
                    (content.bottom - height) / 2,
                )),
            }};
        }}

        function clampToViewport(card, left, top) {{
            var content = getContentRect();
            var width = Math.max(
                1,
                card.offsetWidth || card.getBoundingClientRect().width || 1,
            );
            var height = Math.max(
                1,
                card.offsetHeight || card.getBoundingClientRect().height || 1,
            );
            // Clamp to the content area: the card can never sit
            // under the open left drawer, and never exceed the
            // viewport's right / bottom edges.
            var maxLeft = Math.max(content.left, content.right - width - 4);
            var maxTop = Math.max(0, content.bottom - height - 4);
            return {{
                left: Math.max(content.left, Math.min(maxLeft, left)),
                top: Math.max(0, Math.min(maxTop, top)),
            }};
        }}

        // Return the content area excluding the left drawer.  We
        // read the ``control-panel-drawer-open`` class on ``<body>``
        // instead of measuring the drawer directly because Quasar's
        // transition can make the drawer's rect racy.
        // exact source of truth for "is the drawer open right
        // now". The drawer width is read from the same CSS
        // variable the drawer's own width uses
        // (``--control-left-drawer-w``), with a 260 px
        // fallback that matches the project's drawer.py
        // ``width=260`` prop.
        function getContentRect() {{
            var viewportW = document.documentElement.clientWidth
                || window.innerWidth;
            var viewportH = document.documentElement.clientHeight
                || window.innerHeight;
            var contentLeft = 0;
            try {{
                var body = document.body;
                if (
                    body
                    && body.classList
                    && body.classList.contains('control-panel-drawer-open')
                ) {{
                    var w = 260;
                    try {{
                        var cssW = getComputedStyle(body)
                            .getPropertyValue('--control-left-drawer-w');
                        if (cssW) {{
                            var parsed = parseFloat(cssW);
                            if (parsed > 0) {{ w = parsed; }}
                        }}
                    }} catch (_) {{ /* keep fallback */ }}
                    contentLeft = Math.round(w);
                }}
            }} catch (_) {{ /* fall through to full-viewport */ }}
            return {{
                left: contentLeft,
                right: viewportW,
                top: 0,
                bottom: viewportH,
            }};
        }}

        // Snap-to-edge visual hint: when the user releases the drag
        // within 24 px of a viewport edge, add a class to the card
        // so the edge glows cyan (the same accent color used by the
        // controller tag). The position is NOT snapped — the user can
        // always drag it away again.
        function updateSnapClass(card) {{
            var rect = card.getBoundingClientRect();
            var snapThreshold = 24;
            var leftSnap = rect.left <= snapThreshold;
            var rightSnap =
                window.innerWidth - (rect.left + rect.width) <= snapThreshold;
            var topSnap = rect.top <= snapThreshold;
            card.classList.toggle(
                'runtime-manager-snapped-left', leftSnap,
            );
            card.classList.toggle(
                'runtime-manager-snapped-right', rightSnap,
            );
            card.classList.toggle(
                'runtime-manager-snapped-top', topSnap,
            );
        }}

        function applyPosition(card) {{
            if (!card) {{ return null; }}
            // The CSS now does the centering itself
            // (``top: 50%; left: 50%; transform:
            // translate(-50%, -50%);``). The drag handler sets
            // inline ``left``/``top`` for the dragged position
            // and clears the inline transform so the card sits
            // exactly where the user dropped it. To re-center on
            // the next open we just clear the inline ``left``,
            // ``top``, and ``transform`` so the CSS rules win
            // again. No JS math needed — the browser centers
            // the card automatically, which is race-free even
            // when Quasar's show-transition is in flight.
            card.style.left = '';
            card.style.top = '';
            card.style.transform = '';
            void card.offsetWidth;
            card.style.visibility = 'visible';
            updateSnapClass(card);
            return {{ left: 0, top: 0 }};
        }}

        function bind(card, attempts) {{
            if (!card) {{ return; }}
            attempts = attempts || 0;
            var header = card.querySelector(
                '.runtime-manager-page-header',
            );
            if (!header) {{
                if (attempts > 300) {{ return; }}
                // Body renderer hasn't appended the header yet —
                // try again on the next frame.
                requestAnimationFrame(function() {{
                    bind(card, attempts + 1);
                }});
                return;
            }}

            // Tear down any prior listeners for this case before
            // attaching a new set.
            var existing = window.__floatingRuntimeManagerCtl[caseSlug];
            if (existing && existing.controller) {{
                try {{ existing.controller.abort(); }} catch (_) {{}}
            }}
            // Also clear any leftover global drag state (e.g. a
            // mid-drag close that left body.userSelect === 'none'
            // because Quasar destroyed the header between the abort
            // and the cleanup). Without this, the next open() would
            // inherit a 'none' body userSelect that blocks text
            // selection across the whole page.
            document.body.style.userSelect = '';

            var controller = new AbortController();
            var signal = controller.signal;
            var dragState = null;

            header.style.cursor = 'grab';
            header.style.userSelect = 'none';

            // Restore body.userSelect and cursor if the controller is
            // aborted mid-drag (close-while-dragging path). Use the
            // *current* live header so a Quasar swap doesn't leave
            // a stale 'grabbing' cursor on a now-orphaned element.
            signal.addEventListener('abort', function() {{
                if (dragState) {{
                    try {{
                        (dragState.boundHeader || header)
                            .releasePointerCapture(dragState.pointerId);
                    }} catch (_) {{}}
                    dragState = null;
                }}
                document.body.style.userSelect = '';
                try {{
                    var lh = (getCard() || card).querySelector(
                        '.runtime-manager-page-header',
                    );
                    if (lh && lh.style) {{ lh.style.cursor = 'grab'; }}
                }} catch (_) {{}}
            }});

            function shouldSkipDrag(target) {{
                if (!target || !target.closest) {{ return false; }}
                return !!target.closest(
                    'button, input, select, textarea, .q-field, '
                    + '.q-select, .q-checkbox, a, label, '
                    + '[role="button"], [role="option"], '
                    + '[role="checkbox"], [role="status"], '
                    + '[contenteditable], .runtime-manager-window-btn',
                );
            }}

            // Live-card reference. The DOM ``card`` (and its
            // ``header``) that we bound on may be replaced by Quasar
            // between open/close cycles — when that happens, the
            // card element is detached from the document and writing
            // ``.style.left`` to it is a silent no-op, which is what
            // made the second drag attempt look "dead" in the
            // original report. We solve this by re-querying the live
            // card on every pointer event from a class selector
            // stored in the closure, so a Quasar swap mid-drag is
            // self-healing.
            function liveCard() {{
                return getCard() || card;
            }}
            function liveHeader(lc) {{
                var c = lc || liveCard();
                return (c && c.querySelector(
                    '.runtime-manager-page-header',
                )) || header;
            }}

            function onPointerDown(e) {{
                // Left-click / primary touch only.
                if (e.button !== 0 && e.pointerType === 'mouse') {{ return; }}
                if (shouldSkipDrag(e.target)) {{ return; }}
                // Defensive: reset any stuck prior dragState (e.g.
                // from a missed pointercancel on alt-tab).
                if (dragState) {{
                    try {{
                        header.releasePointerCapture(dragState.pointerId);
                    }} catch (_) {{}}
                    dragState = null;
                    document.body.style.userSelect = '';
                }}
                // Re-resolve the live card *now* so the starting
                // rect is from the current DOM, not from a possibly-
                // detached closure.
                var lc = liveCard();
                var lh = liveHeader(lc);
                // The card is ``position: absolute`` inside
                // Quasar's ``.q-dialog__inner`` (which is
                // ``position: fixed; inset: 0``). Setting
                // ``left``/``top`` on the card during a drag
                // positions it relative to the inner =
                // relative to the viewport. No transform
                // needed; the previous ``transform: 'none'``
                // was for the legacy ``top: 50%/left: 50% +
                // translate`` centering which is no longer
                // used.
                void 0;
                var rect = lc.getBoundingClientRect();
                var captured = false;
                try {{
                    lh.setPointerCapture(e.pointerId);
                    captured = true;
                }} catch (_) {{
                    captured = false;
                }}
                dragState = {{
                    pointerId: e.pointerId,
                    startX: e.clientX,
                    startY: e.clientY,
                    origLeft: rect.left,
                    origTop: rect.top,
                    captured: captured,
                    // Track which card/header we captured on so we
                    // can release on the *same* element after a
                    // Quasar DOM swap, and so a subsequent
                    // pointermove can re-resolve cleanly.
                    boundCard: lc,
                    boundHeader: lh,
                }};
                lh.style.cursor = 'grabbing';
                document.body.style.userSelect = 'none';
                e.preventDefault();
            }}

            function onPointerMove(e) {{
                if (!dragState || e.pointerId !== dragState.pointerId) {{
                    return;
                }}
                var dx = e.clientX - dragState.startX;
                var dy = e.clientY - dragState.startY;
                // Always operate on the *live* card, and recompute
                // its size on every move so a Quasar-driven resize
                // (e.g. the dialog show-transition settling AFTER
                // bind() ran) doesn't make the clamp use stale
                // dimensions and the card visually jump.
                var lc = liveCard();
                if (!lc) {{ return; }}
                var clamped = clampToViewport(
                    lc,
                    dragState.origLeft + dx,
                    dragState.origTop + dy,
                );
                lc.style.left = clamped.left + 'px';
                lc.style.top = clamped.top + 'px';
                // No inline transform needed — the card is
                // ``position: absolute`` inside Quasar's
                // ``.q-dialog__inner`` (``position: fixed;
                // inset: 0``), so ``left``/``top`` are
                // relative to the viewport. Flex centering
                // resumes when the next ``open()`` clears
                // ``left``/``top``.
                updateSnapClass(lc);
            }}

            function endDrag(e) {{
                if (!dragState) {{ return; }}
                if (e && e.pointerId !== undefined
                    && e.pointerId !== dragState.pointerId) {{ return; }}
                // Release on whichever header we captured on, even
                // if the live card is now a different element.
                try {{
                    (dragState.boundHeader || header).releasePointerCapture(
                        dragState.pointerId,
                    );
                }} catch (_) {{}}
                // Reset cursor/userSelect on the *current* live
                // header so the next open() starts with a clean grab
                // cursor and the body is selectable again.
                var lc = liveCard();
                var lh = liveHeader(lc);
                if (lh && lh.style) {{ lh.style.cursor = 'grab'; }}
                document.body.style.userSelect = '';
                if (lc) {{
                    var rect = lc.getBoundingClientRect();
                    persist(rect.left, rect.top);
                    updateSnapClass(lc);
                }}
                dragState = null;
            }}

            // Header-level listeners: setPointerCapture routes
            // subsequent move/up here even when the cursor leaves
            // the header. signal-bound so we can detach cleanly.
            header.addEventListener(
                'pointerdown', onPointerDown, {{ signal }},
            );
            header.addEventListener(
                'pointermove', onPointerMove, {{ signal }},
            );
            header.addEventListener('pointerup', endDrag, {{ signal }});
            header.addEventListener('pointercancel', endDrag, {{ signal }});
            header.addEventListener(
                'lostpointercapture', endDrag, {{ signal }},
            );
            // Defensive end-drag: if the pointer leaves the header
            // mid-drag (fast motion past the dialog edge, OS palm
            // rejection, etc.) release the pointer capture so the
            // drag does not stick. ``endDrag`` is itself
            // pointerId-gated, so this is a no-op on a stale event.
            header.addEventListener(
                'pointerleave',
                function(e) {{
                    if (
                        dragState
                        && dragState.pointerId === e.pointerId
                    ) {{
                        try {{
                            (dragState.boundHeader || header)
                                .releasePointerCapture(dragState.pointerId);
                        }} catch (_) {{}}
                    }}
                }},
                {{ signal }},
            );

            // Document-level fallback for the rare case where the
            // pointer crosses into an iframe/cross-origin region and
            // setPointerCapture is bypassed. Same handlers — they
            // only need clientX/clientY.
            document.addEventListener(
                'pointermove', onPointerMove, {{ signal }},
            );
            document.addEventListener('pointerup', endDrag, {{ signal }});
            document.addEventListener('pointercancel', endDrag, {{ signal }});

            // Defensive end-drag on visibility/window blur (handles
            // alt-tab / lock-screen / OS palm rejection).
            function defensiveEnd() {{ endDrag(); }}
            window.addEventListener('blur', defensiveEnd, {{ signal }});
            document.addEventListener(
                'visibilitychange',
                function() {{
                    if (document.hidden) {{ defensiveEnd(); }}
                }},
                {{ signal }},
            );

            // Re-clamp on viewport resize so a narrowed window
            // doesn't leave the card off-screen. Use the live card
            // so a mid-life Quasar DOM swap doesn't crash the
            // handler on a detached node.
            var resizeTimer = null;
            function onResize() {{
                if (resizeTimer) {{ return; }}
                resizeTimer = setTimeout(function() {{
                    resizeTimer = null;
                    var rc = liveCard();
                    if (!rc) {{ return; }}
                    var rect = rc.getBoundingClientRect();
                    var clamped = clampToViewport(
                        rc, rect.left, rect.top,
                    );
                    rc.style.left = clamped.left + 'px';
                    rc.style.top = clamped.top + 'px';
                    persist(clamped.left, clamped.top);
                }}, 120);
            }}
            window.addEventListener('resize', onResize, {{ signal }});

            // Double-rAF so the dialog's show-transition has a
            // frame to settle before we measure the card.
            requestAnimationFrame(function() {{
                requestAnimationFrame(function() {{
                    applyPosition(liveCard() || card);
                }});
            }});

            window.__floatingRuntimeManagerCtl[caseSlug] = {{
                controller: controller,
                card: card,
                cardId: card.id || cardId,
                reapply: function(targetCard) {{
                    return applyPosition(targetCard || liveCard() || card);
                }},
                rebind: function(targetCard) {{
                    return bind(targetCard || getCard() || card);
                }},
                remountHandles: function(targetCard) {{
                    mountResizeHandles(targetCard || liveCard() || card);
                }},
            }};
        }}

        // Persistent listener for rebind requests from the re-apply
        // script. Lives on document, NOT on the card — survives
        // Quasar destroying & recreating the card.
        document.addEventListener(
            '__floatingRuntimeManagerRebind:' + caseSlug,
            function(e) {{
                var card = (e && e.detail && e.detail.card) || getCard();
                if (card) {{ bind(card); }}
            }},
        );

        // Initial bind attempt with a generous retry budget so slow
        // Quasar mounts on low-end devices don't drop the bind.
        function tryBind(attempts) {{
            var card = getCard();
            if (card) {{
                bind(card);
                return;
            }}
            if (attempts > 300) {{ return; }}  // ~5s max
            requestAnimationFrame(function() {{ tryBind(attempts + 1); }});
        }}
        tryBind(0);

        // ── Multi-edge resize (8 handles: N/E/S/W + NE/SE/SW/NW) ──
        // The CSS ``resize: both`` shortcut would give the user only
        // one grip in the bottom-right corner — the user explicitly
        // asked for handles on the left, right, and bottom as well.
        // We mount 8 invisible handles ourselves as direct children
        // of the card and drive them with the same Pointer Events
        // API the header drag already uses (see ``onPointerDown``
        // above). This keeps behaviour consistent: identical capture
        // semantics, identical detach-on-blur fallback, and the
        // handles transparently coexist with the header drag because
        // each handle gets its own pointerdown that ``stopPropagation``
        // so the header drag logic never fires.
        // Persistence is identical to the drag persistence pattern
        // a few hundred lines up — same sessionStorage key shape,
        // same idempotent install guard, same getCard() walk for
        // Quasar rebuilds.
        var SIDES = [
            'n', 'e', 's', 'w', 'ne', 'se', 'sw', 'nw',
        ];
        var MIN_W = 360, MIN_H = 220;

        function persistSize(width, height) {{
            var rounded = {{
                width: Math.round(width),
                height: Math.round(height),
            }};
            window.__floatingRuntimeManagerSizes =
                window.__floatingRuntimeManagerSizes || {{}};
            window.__floatingRuntimeManagerSizes[caseSlug] = rounded;
            try {{
                window.sessionStorage.setItem(
                    'floatingRuntimeManagerSize:' + caseSlug,
                    JSON.stringify(rounded),
                );
            }} catch (_) {{ /* private mode etc. */ }}
        }}

        function seedSizeFromStorage(card) {{
            // Apply the stored size as inline CSS custom-properties
            // so the card has the user's preferred dimensions on
            // first paint (before the user starts dragging). The
            // CSS defaults in ``--frm-width`` / ``--frm-height``
            // remain the fallback for fresh sessions.
            var stored = null;
            try {{
                var raw = window.sessionStorage.getItem(
                    'floatingRuntimeManagerSize:' + caseSlug,
                );
                if (raw) {{ stored = JSON.parse(raw); }}
            }} catch (_) {{ stored = null; }}
            if (!stored
                || typeof stored.width !== 'number'
                || typeof stored.height !== 'number') {{
                return;
            }}
            try {{
                card.style.setProperty(
                    '--frm-width', stored.width + 'px',
                );
                card.style.setProperty(
                    '--frm-height', stored.height + 'px',
                );
            }} catch (_) {{ /* card detached etc. */ }}
        }}

        function clampSize(width, height) {{
            var maxW = Math.max(
                MIN_W,
                document.documentElement.clientWidth - 16,
            );
            var maxH = Math.max(
                MIN_H,
                document.documentElement.clientHeight - 16,
            );
            return {{
                width: Math.max(MIN_W, Math.min(maxW, width)),
                height: Math.max(MIN_H, Math.min(maxH, height)),
            }};
        }}

        function mountResizeHandles(card) {{
            if (!card) {{ return; }}
            // Guard against double-mount by looking at the live DOM
            // instead of a JS property.  Vue/Quasar may recreate the
            // card's children on dialog open/close, which removes
            // foreign appended handles.  Re-querying the DOM makes
            // the mount idempotent even after a Vue patch.
            if (card.querySelector('.runtime-manager-resize-handle')) {{
                seedSizeFromStorage(card);
                return;
            }}
            seedSizeFromStorage(card);
            SIDES.forEach(function(side) {{
                var h = document.createElement('div');
                h.className =
                    'runtime-manager-resize-handle '
                    + 'runtime-manager-resize-handle-' + side;
                h.dataset.side = side;
                card.appendChild(h);
                bindOneHandle(card, h, side);
            }});
        }}

        function bindOneHandle(card, handle, side) {{
            var dragInfo = null;
            handle.addEventListener('pointerdown', function(e) {{
                // Left button / primary touch only — same gate as
                // the header drag.
                if (e.button !== 0 && e.pointerType === 'mouse') {{
                    return;
                }}
                // Don't resize while minimized — the strip is
                // header-only and has no body to size against.
                if (card.classList.contains('runtime-manager-minimized')) {{
                    return;
                }}
                var rect = card.getBoundingClientRect();
                dragInfo = {{
                    pointerId: e.pointerId,
                    startX: e.clientX,
                    startY: e.clientY,
                    startW: rect.width,
                    startH: rect.height,
                    startLeft: rect.left,
                    startTop: rect.top,
                }};
                try {{ handle.setPointerCapture(e.pointerId); }}
                catch (_) {{}}
                document.body.style.userSelect = 'none';
                // Stop propagation so the header-drag pointerdown
                // (which only listens on the header anyway) and any
                // ancestor click handler never see this event.
                e.stopPropagation();
                e.preventDefault();
            }});

            handle.addEventListener('pointermove', function(e) {{
                if (!dragInfo || e.pointerId !== dragInfo.pointerId) {{
                    return;
                }}
                var dx = e.clientX - dragInfo.startX;
                var dy = e.clientY - dragInfo.startY;
                var newW = dragInfo.startW;
                var newH = dragInfo.startH;
                var newLeft = dragInfo.startLeft;
                var newTop = dragInfo.startTop;
                // Side flags
                if (side.indexOf('e') !== -1) {{ newW += dx; }}
                if (side.indexOf('s') !== -1) {{ newH += dy; }}
                if (side.indexOf('w') !== -1) {{
                    newW -= dx;
                    newLeft += dx;
                }}
                if (side.indexOf('n') !== -1) {{
                    newH -= dy;
                    newTop += dy;
                }}
                var clamped = clampSize(newW, newH);
                // If the clamp shrank the dimension, the
                // corresponding left/top offset also has to be
                // recomputed so the un-grabbed edge stays put.
                if (side.indexOf('w') !== -1) {{
                    newLeft = dragInfo.startLeft
                        + (dragInfo.startW - clamped.width);
                }}
                if (side.indexOf('n') !== -1) {{
                    newTop = dragInfo.startTop
                        + (dragInfo.startH - clamped.height);
                }}
                card.style.setProperty(
                    '--frm-width', clamped.width + 'px',
                );
                card.style.setProperty(
                    '--frm-height', clamped.height + 'px',
                );
                // For W/N drags, also adjust the card's left/top
                // so the un-grabbed edge appears stationary.
                if (side.indexOf('w') !== -1
                    || side.indexOf('n') !== -1) {{
                    if (side.indexOf('w') !== -1) {{
                        card.style.left = newLeft + 'px';
                    }}
                    if (side.indexOf('n') !== -1) {{
                        card.style.top = newTop + 'px';
                    }}
                }}
            }});

            function endResize(e) {{
                if (!dragInfo) {{ return; }}
                if (e && e.pointerId !== undefined
                    && e.pointerId !== dragInfo.pointerId) {{
                    return;
                }}
                try {{
                    handle.releasePointerCapture(dragInfo.pointerId);
                }} catch (_) {{}}
                document.body.style.userSelect = '';
                var rect = card.getBoundingClientRect();
                persistSize(rect.width, rect.height);
                dragInfo = null;
            }}

            handle.addEventListener('pointerup', endResize);
            handle.addEventListener('pointercancel', endResize);
            handle.addEventListener('lostpointercapture', endResize);
        }}

        function tryMountHandles(attempts) {{
            var card = getCard();
            if (card) {{
                mountResizeHandles(card);
                return;
            }}
            if (attempts > 300) {{ return; }}  // ~5s max
            requestAnimationFrame(function() {{
                tryMountHandles(attempts + 1);
            }});
        }}
        tryMountHandles(0);
        // Re-mount on rebind events so a Quasar DOM swap doesn't
        // leave the user with a card that has no handles.
        document.addEventListener(
            '__floatingRuntimeManagerRebind:' + caseSlug,
            function() {{
                tryMountHandles(0);
            }},
        );
    }})();
    """


def _reapply_script(card_id: str, case_slug: str) -> str:
    """Return JS that ensures drag is bound and position re-applied.

    Called on every ``open()``. If the card was *not* replaced and a
    live controller exists, this just re-applies the saved position. If
    the card was replaced or the controller was aborted (e.g., via
    ``_abort_script`` after a mid-drag close), this dispatches the
    rebind CustomEvent — the drag script's persistent document listener
    picks it up and re-binds onto the live card.
    """
    return f"""
    (function() {{
        var cardId = {card_id!r};
        var caseSlug = {case_slug!r};
        window.__floatingRuntimeManagerCtl =
            window.__floatingRuntimeManagerCtl || {{}};
        window.__floatingRuntimeManagerCardId =
            window.__floatingRuntimeManagerCardId || {{}};
        // Always point the registry at the latest cardId — the
        // dialog's DOM may have been rebuilt with a different id.
        window.__floatingRuntimeManagerCardId[caseSlug] = cardId;

        function getCard() {{
            // Always walk the live Quasar dialogs first. The card
            // is always in the slot (the dialog is hidden, not
            // destroyed, between close and reopen — confirmed in
            // the NiceGUI source at dialog.py:14-29 and dialog.js).
            // We do NOT filter on ``inner.offsetParent`` because
            // Quasar's show-transition can leave the inner briefly
            // with ``offsetParent === null`` for a few frames,
            // which would make the walk miss the runtime manager's
            // own card and return null (and then retry for ~5 s).
            // The id/class re-assertion below is idempotent.
            var dialogs = document.querySelectorAll('.q-dialog');
            for (var i = dialogs.length - 1; i >= 0; i--) {{
                var c = dialogs[i].querySelector(
                    '.runtime-manager-page-card',
                );
                if (c) {{
                    if (!c.id) {{ c.id = cardId; }}
                    if (!c.classList.contains(
                        'floating-runtime-manager-card',
                    )) {{
                        c.classList.add('floating-runtime-manager-card');
                    }}
                    return c;
                }}
            }}
            // Fallback: id-based lookup, but only if the result is
            // actually attached to the live document. A detached
            // node is never what we want.
            var byId = document.getElementById(cardId);
            if (byId && document.body.contains(byId)) {{ return byId; }}
            return null;
        }}

        function tick(attempts) {{
            var liveCard = getCard();
            if (!liveCard) {{
                if (attempts > 300) {{ return; }}  // ~5s max
                requestAnimationFrame(function() {{ tick(attempts + 1); }});
                return;
            }}
            if (!liveCard.id) {{ liveCard.id = cardId; }}
            var cl = liveCard.classList;
            if (!cl.contains('floating-runtime-manager-card')) {{
                cl.add('floating-runtime-manager-card');
            }}
            var ctl = window.__floatingRuntimeManagerCtl[caseSlug];
            // ``alreadyBound`` requires *positive proof* that the
            // live card is the one the existing controller is bound
            // to AND that the controller is alive AND that the
            // recorded card is still attached to the document.
            // Anything less → force a synchronous rebind against
            // the live card. This replaces the prior
            // ``needsRebind`` heuristic which trusted the cached
            // ``ctl.card`` and could be fooled by a stale
            // ``getElementById`` returning a detached node.
            var alreadyBound = (
                ctl
                && ctl.controller
                && !ctl.controller.signal.aborted
                && ctl.card === liveCard
                && liveCard !== null
                && document.body.contains(liveCard)
            );
            if (!alreadyBound) {{
                if (ctl && typeof ctl.rebind === 'function') {{
                    // The drag install's ``bind`` is exposed on
                    // ``ctl.rebind`` — calling it directly avoids
                    // the round-trip through the document-level
                    // CustomEvent listener and is the
                    // close-then-reopen path's hot path.
                    try {{ ctl.rebind(liveCard); }} catch (_) {{}}
                }} else {{
                    // Fallback for the very first open() before the
                    // drag install has registered its controller.
                    document.dispatchEvent(new CustomEvent(
                        '__floatingRuntimeManagerRebind:' + caseSlug,
                        {{ detail: {{ card: liveCard }} }},
                    ));
                }}
            }} else if (ctl.reapply) {{
                ctl.reapply(liveCard);
            }}
            // Resize handles are DOM children that Vue/Quasar may
            // remove on dialog transitions.  Re-mount on every
            // open() so they are always present.
            if (ctl && typeof ctl.remountHandles === 'function') {{
                try {{ ctl.remountHandles(liveCard); }} catch (_) {{}}
            }}

            // Belt-and-braces: explicitly flip the card to
            // visible. ``applyPosition`` (called from
            // ``ctl.rebind → bind → double-rAF`` and from
            // ``ctl.reapply``) also does this, but Quasar's
            // show-transition can briefly re-apply its own
            // ``visibility: hidden`` to slot children during the
            // transition. Writing the inline style AFTER the
            // reapply/rebind work guarantees the user sees the
            // card on the second and subsequent opens.
            try {{ liveCard.style.visibility = 'visible'; }} catch (_) {{}}
        }}

        // Double-rAF so Quasar's show-transition has a frame to
        // settle before we measure.
        requestAnimationFrame(function() {{
            requestAnimationFrame(function() {{ tick(0); }});
        }});
    }})();
    """


def _abort_script(_case_slug: str) -> str:
    """Return JS that clears any stuck global drag state on close.

    This used to abort the JS drag controller on every close, but that
    turned out to be the source of the "first open works, second open
    shows only the backdrop" symptom. Aborting the controller forced the
    reapply script's next ``open()`` to take the ``!alreadyBound``
    rebind path, whose double-rAF fired faster than Quasar's ~200-400 ms
    show-transition, and Quasar's transition handler then re-applied its
    own ``visibility: hidden`` to the slot children, overwriting the
    ``applyPosition`` flip and leaving the card invisible.

    The function is kept (with a no-op body) for backward compatibility
    with any caller that may still import it. The drag controller is no
    longer aborted on close; the reapply script's positive-proof check
    on the next ``open()`` will rebind only if the controller has
    actually become stale.
    """
    return """
    (function() {
        // Clear any stuck global drag state. The drag script may
        // have set ``body.userSelect='none'`` during a prior drag
        // that wasn't cleanly ended. Restoring '' is a no-op when
        // the dialog is hidden and the CSS default of 'auto'
        // takes over.
        document.body.style.userSelect = '';
    })();
    """


class FloatingRuntimeManager:
    """Floating, draggable Runtime Manager dialog for one case."""

    _next_card_id = 0

    def __init__(
        self,
        *,
        case_slug: str,
        process_label: str,
        build_store: Callable[[], Any],
        on_run: Callable[[], None] | None = None,
        on_stop: Callable[[], None] | None = None,
        eager_build: bool = True,
    ) -> None:
        self.case_slug = case_slug
        self.process_label = process_label
        self._build_store = build_store
        # Optional Run/Stop hooks forwarded straight into the
        # runtime manager body. The control-panel page wires these
        # to ``hub.engine_control.run`` / ``stop`` so the dialog
        # offers the same Run/Pause affordance as the PID navbar.
        self._on_run = on_run
        self._on_stop = on_stop

        self._dialog: ui.dialog | None = None
        self._card_id: str = self._make_card_id()
        self._minimized: bool = False
        # References to every minimize button the renderer emits for
        # this dialog. The list lets ``toggle_minimize()`` keep the
        # button icon/tooltip in sync with the server-side state even
        # though the click that flipped the state came from the
        # client. NiceGUI does not offer a class-binding primitive
        # for ``ui.button``, so we hold the references explicitly and
        # mutate them through ``_sync_minimize_buttons``.
        self._minimize_button_refs: list = []

        # Eager build: when ``eager_build`` is True (the default)
        # we construct the dialog body, drag script, and resize
        # observer right now so the *first* ``toggle()`` is a pure
        # visibility flip instead of a 1-2 s build. The dialog
        # starts closed (``value=False``); the user only sees it
        # after the first ``toggle()`` call.
        # The eager build MUST run after NiceGUI's per-page
        # context is set up, which is why it's invoked from the
        # control-panel page builder (where
        # ``build_sthr_hub`` / ``build_biodiesel_hub`` has already
        # been called) rather than at module import. We use a
        # ``ui.timer(0.0, ...)`` so the click handler that
        # constructed the FloatingRuntimeManager returns
        # immediately; the actual build runs on the next tick.
        if eager_build:
            try:
                ui.timer(0.0, self._eager_build_safe, once=True)
            except Exception:
                # Older NiceGUI without ``once=``: fall back to a
                # plain timer; the function is idempotent.
                try:
                    ui.timer(0.0, self._eager_build_safe)
                except Exception:
                    pass

    def _eager_build_safe(self) -> None:
        """Run :meth:`_build` once, on the next NiceGUI tick.

        Idempotent: a second call is a no-op because
        ``self._dialog is not None``.
        """
        if self._dialog is not None:
            return
        try:
            self._build()
        except Exception:
            # Fall back to lazy build on the first ``open()`` if
            # the eager build fails (e.g. engine not yet ready,
            # store importable but case config missing).
            logger.debug(
                'FloatingRuntimeManager: eager build failed; falling back to lazy build',
                exc_info=True,
            )

    @classmethod
    def _make_card_id(cls) -> str:
        cls._next_card_id += 1
        return f'floating-runtime-manager-card-{cls._next_card_id}'

    # ── Public API ──

    def open(self) -> None:
        """Mount the dialog (if not already mounted) and show it.

        After the dialog is shown, the re-apply script runs to ensure
        drag is bound (re-binding if the controller was aborted or the
        card was replaced) and the saved position is re-applied.

        Note: we deliberately do NOT run any DOM-mutating JS before
        ``self._dialog.open()``. The earlier "pre-open snippets" that
        aborted the prior controller and re-asserted the card's
        class+id actually *caused* the "first open works, second
        open shows only the backdrop" symptom — aborting the
        controller before Quasar's show-transition completed forced
        the reapply script into the rebind path, whose double-rAF
        fires faster than Quasar's ~200-400 ms transition. Quasar's
        transition handler then re-applied its own ``visibility:
        hidden`` to the slot children, overwriting the
        ``applyPosition`` flip and leaving the card invisible.
        Letting Quasar run its show-transition cleanly, then handing
        control to the reapply script, is race-free.
        """
        if self._dialog is None:
            self._build()
        if self._dialog is not None:
            self._dialog.open()
            ui.run_javascript(_ensure_namespace_js())
            # Force-center the card on every open. We run this
            # immediately (no rAF) so the user does not see the
            # card flash at its prior position before the
            # reapply script's double-rAF fires. The reapply
            # script's later ``applyPosition`` call (via
            # ``ctl.reapply``) is still the source of truth —
            # this is just a synchronous, immediate force-center
            # that uses the same math.
            ui.run_javascript(f"""
                (function() {{
                    var card = document.getElementById({self._card_id!r});
                    if (!card) {{ return; }}
                    // The CSS now does the centering itself
                    // (``top: 50%; left: 50%; transform:
                    // translate(-50%, calc(-50% + var(
                    // --frm-drawer-offset, 0px)))``). All we
                    // need to do is (a) clear any inline
                    // ``left``/``top``/``transform`` from a prior
                    // drag, and (b) update the drawer's offset
                    // CSS variable so the center shifts to the
                    // content area when the drawer is open.
                    card.style.left = '';
                    card.style.top = '';
                    card.style.transform = '';
                    void card.offsetWidth;
                    // Set the drawer's offset on the card itself
                    // (a CSS custom property is read by the
                    // card's own transform). When the drawer is
                    // open, shift the center by half the drawer
                    // width so the dialog appears centered in
                    // the content area, not the full viewport.
                    var offsetPx = '0px';
                    try {{
                        if (
                            document.body
                            && document.body.classList
                            && document.body.classList.contains(
                                'control-panel-drawer-open',
                            )
                        ) {{
                            var dw = 260;
                            try {{
                                var cssW = getComputedStyle(document.body)
                                    .getPropertyValue(
                                        '--control-left-drawer-w',
                                    );
                                if (cssW) {{
                                    var parsed = parseFloat(cssW);
                                    if (parsed > 0) {{ dw = parsed; }}
                                }}
                            }} catch (_) {{ /* keep fallback */ }}
                            offsetPx = Math.round(dw / 2) + 'px';
                        }}
                    }} catch (_) {{ /* keep offsetPx = '0px' */ }}
                    card.style.setProperty(
                        '--frm-drawer-offset', offsetPx,
                    );
                    card.style.visibility = 'visible';
                }})();
                """)
            ui.run_javascript(
                _reapply_script(self._card_id, self.case_slug),
            )
            if self._minimized:
                # Re-showing after a previous minimize — restore the
                # full body so the user can interact with the form.
                ui.run_javascript(f"""
                    (function() {{
                        var card = document.getElementById({self._card_id!r});
                        if (card) {{
                            card.classList.remove('runtime-manager-minimized');
                        }}
                    }})();
                    """)
                self._minimized = False
                # Bring every minimize button back to its "Minimize"
                # affordance so the icon/tooltip mirror the freshly
                # restored body. Done unconditionally so the buttons
                # are also coherent on the very first open() (the
                # renderer may have built them while a different
                # case's state lingered in the registry).
                self._sync_minimize_buttons()

    def close(self) -> None:
        """Hide the dialog.

        We deliberately do NOT call ``_abort_script`` here. Aborting
        the JS drag controller on close was the previous failure
        mode: the next ``open()`` then took the ``!alreadyBound``
        path in the reapply script, which scheduled a rebind via
        double-rAF — racing against Quasar's show-transition and
        leaving the card invisible. Leaving the controller alive is
        safe: the dialog is hidden, so no pointer events reach the
        card. The reapply script's positive-proof check on the next
        ``open()`` will rebind the controller against the live card
        only if it has actually become stale.
        """
        if self._dialog is not None:
            self._dialog.close()
            # Belt-and-braces: clear any stuck global drag state.
            # The drag script may have set ``body.userSelect='none'``
            # during a prior drag that wasn't cleanly ended.
            ui.run_javascript('(function() {{ document.body.style.userSelect = ""; }})();')

    def toggle_minimize(self) -> None:
        """Toggle the floating card's minimized (header-only) state.

        When minimized, the form and status bar are hidden via CSS so
        the user sees only the draggable header strip + the hero
        "Current Time" — the same affordance a real HMI workstation
        offers when the operator "shelves" a faceplate. The card
        stays in place at the same viewport position.

        Implementation notes:

        * Target state is computed BEFORE the Python attribute is
          flipped, then handed to JavaScript as an explicit boolean.
          The earlier implementation read ``self._minimized`` after
          self-update and embedded ``str(...).lower()`` directly in
          the JS template, which works but is brittle if the value
          is ever shared with an async caller between the flip and
          the JS dispatch. Using
          ``card.classList.toggle('runtime-manager-minimized', target)``
          with an explicit boolean makes the JS path idempotent and
          self-healing: if the card already has the class, the
          ``true`` form is a no-op (it does NOT re-toggle).
        * ``_sync_minimize_buttons()`` is called AFTER the JS runs so
          the icon/tooltip on every minimize button mirrors the new
          server-side state. Without this, the user sees no visual
          confirmation of the click and the button "looks dead" on
          some toggle cycles.
        """
        if self._dialog is None:
            return
        target = not self._minimized
        target_js = 'true' if target else 'false'
        ui.run_javascript(f"""
            (function() {{
                var cardId = {self._card_id!r};
                var card = document.getElementById(cardId);
                // Fallback: if the id was lost (Quasar rebuild), walk
                // the live dialogs for the runtime-manager card.
                if (!card) {{
                    var dialogs = document.querySelectorAll('.q-dialog');
                    for (var i = dialogs.length - 1; i >= 0; i--) {{
                        var c = dialogs[i].querySelector(
                            '.floating-runtime-manager-card',
                        );
                        if (c) {{ card = c; break; }}
                    }}
                }}
                if (!card) {{
                    var cards = document.querySelectorAll(
                        '.runtime-manager-page-card',
                    );
                    card = cards[cards.length - 1] || null;
                }}
                if (!card) {{ return; }}
                // Re-assert the id so future toggles hit fast-path.
                if (!card.id) {{ card.id = cardId; }}
                // Explicit boolean force-form of classList.toggle is
                // idempotent — repeated invocations with the same
                // target leave the class set exactly once.
                var cls = 'runtime-manager-minimized';
                card.classList.toggle(cls, {target_js});
            }})();
            """)
        self._minimized = target
        self._sync_minimize_buttons()

    def _sync_minimize_buttons(self) -> None:
        """Update every registered minimize button to mirror state.

        Called from ``toggle_minimize`` (after the class toggle) and
        from ``open()`` (after the minimize state is force-reset to
        ``False`` on re-show). Each button gets a fresh ``icon`` and
        ``aria-label`` so the user always sees an unambiguous
        affordance:

        * ``horizontal_rule`` + "Minimize" when the body is expanded.
        * ``crop_square`` + "Restore" when the body is collapsed.

        ``aria-label`` is the canonical screen-reader / accessibility
        hook and (unlike ``ui.button.tooltip``) is idempotent on
        update — NiceGUI's ``tooltip()`` helper is additive (appends
        a new ``q-tooltip`` child on every call). The tooltip text
        is driven from a registered ``ui.tooltip`` ref (see the
        ``(button, tooltip)`` tuple convention below); legacy entries
        that registered only the button are still supported.

        Best-effort: any individual button that no longer exists
        (e.g. the dialog was rebuilt) is skipped silently.
        """
        icon = 'crop_square' if self._minimized else 'horizontal_rule'
        label_text = 'Restore' if self._minimized else 'Minimize'
        for entry in list(self._minimize_button_refs):
            if isinstance(entry, tuple):
                btn, tooltip = entry
            else:
                btn, tooltip = entry, None
            try:
                btn.props(f'icon={icon}')
            except Exception:
                continue
            try:
                btn.props(f'aria-label="{label_text}"')
            except Exception:
                pass
            if tooltip is not None:
                try:
                    tooltip.text = label_text
                except Exception:
                    pass

    def toggle(self) -> None:
        """Open the dialog if hidden, close it if visible."""
        if self._dialog is None:
            self.open()
            return
        if self.is_open:
            self.close()
        else:
            self.open()

    # ── Internals ──

    def _build(self) -> None:
        """Construct the dialog DOM once.

        Idempotent within an instance.
        """
        # Idempotency: a second ``_build`` after the first is a
        # no-op. The eager-build path in :meth:`__init__` may
        # fire the timer twice if the page is rebuilt (e.g. on
        # hot-reload), so this guard is essential.
        if self._dialog is not None:
            return
        try:
            from gateway.registry.config_registry import get_case_config

            case_cfg = get_case_config(self.case_slug)
        except Exception as exc:
            ui.label(
                f'Runtime Manager unavailable: could not load case '
                f'config for "{self.case_slug}" ({exc}).',
            )
            return

        store = self._build_store()
        if store is None:
            ui.label(
                'Runtime Manager unavailable: engine gateway is not '
                'importable. Start the app with the engine package '
                'on the import path to drive the simulation from '
                'this window.',
            )
            return

        bridge = getattr(store, 'bridge', None)
        if bridge is None:
            ui.label(
                'Runtime Manager unavailable: bridge store does not expose its underlying bridge.',
            )
            return

        from app.pages.runtime_manager_page import render_runtime_manager_body

        # ``value=False`` keeps the dialog closed on first paint.
        # The user opens it via the navbar Runtime Manager button
        # (or, on a later visit, via ``toggle()``). When the
        # eager-build path is used, this is the dialog's first
        # and only construction; subsequent ``open()`` calls are
        # pure visibility flips.
        dialog = ui.dialog().props(
            'persistent model-value=false transition-show="scale" transition-hide="scale"'
        )
        self._dialog = dialog

        with dialog:
            # The body renderer creates its own ``ui.card()`` with
            # the ``runtime-manager-page-card`` class. We add
            # the floating card class here so the body works the
            # same way as in the centered-page context, but with
            # the floating-card CSS overrides (position: fixed,
            # z-index, etc.) applied.
            # ``is_dialog_open=self.is_open`` is a bound method
            # passed to the body renderer so the mode-pill timer
            # (and any future client-side poll) can gate itself on
            # the dialog's visibility. When the dialog is closed
            # the timer is a no-op, so a stale ``mode_pill``
            # reference cannot trigger a Vue re-render of the slot
            # during the next show-transition.
            render_runtime_manager_body(
                case_cfg=case_cfg,
                bridge=bridge,
                store=store,
                process_label=self.process_label,
                on_close=self.close,
                on_minimize=self.toggle_minimize,
                is_dialog_open=lambda: self.is_open,
                is_minimized=lambda: self._minimized,
                on_minimize_button_ready=(
                    lambda btn, tooltip=None: self._minimize_button_refs.append(
                        (btn, tooltip) if tooltip is not None else btn,
                    )
                ),
                on_run=self._on_run,
                on_stop=self._on_stop,
            )

        # Initialize the shared namespaces, then tag the card, then
        # install the drag script. The drag script's install guard
        # makes the install a no-op on subsequent dialog rebuilds
        # (it just re-emits the rebind event).
        ui.run_javascript(_ensure_namespace_js())
        ui.run_javascript(
            f"""
            (function() {{
                // Scope the search to the most recently shown
                // Quasar dialog so we don't tag a sibling case's
                // card by accident.
                var dialogs = document.querySelectorAll('.q-dialog');
                var card = null;
                for (var i = dialogs.length - 1; i >= 0; i--) {{
                    card = dialogs[i].querySelector(
                        '.runtime-manager-page-card',
                    );
                    if (card) {{ break; }}
                }}
                if (!card) {{
                    var cards = document.querySelectorAll(
                        '.runtime-manager-page-card',
                    );
                    card = cards[cards.length - 1] || null;
                }}
                if (!card) {{ return; }}
                card.id = {self._card_id!r};
                card.classList.add('floating-runtime-manager-card');
            }})();
            """,
        )
        ui.run_javascript(_drag_script(self._card_id, self.case_slug))

    @property
    def is_open(self) -> bool:
        """Whether the dialog is currently visible.

        Tries ``self._dialog.value`` first (the canonical
        NiceGUI 3.x signal — confirmed in
        ``nicegui/elements/dialog.py:50-58``: ``open()`` sets
        ``value = True``, ``close()`` sets ``value = False``).
        Falls back to ``self._dialog.props.get('visible')``
        for any older NiceGUI that doesn't expose ``value``.
        """
        if self._dialog is None:
            return False
        value = getattr(self._dialog, 'value', None)
        if value is not None:
            return bool(value)
        return bool(self._dialog.props.get('visible', False))
