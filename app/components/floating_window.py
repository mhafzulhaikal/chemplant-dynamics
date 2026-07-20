# app/components/floating_window.py

"""Generic draggable / resizable / minimizable dialog helper.

This module is the single source of truth for the floating-card
behaviour that the Runtime Manager dialog (and now the Faceplate
dialog) share. The exact pointer-event drag, multi-edge resize,
and minimize-toggling logic that used to live inline in
:mod:`app.components.floating_runtime_manager` has been lifted
out into :class:`DraggableCard` so any ``ui.dialog`` whose body
exposes a known card class + header class can be turned into a
floating, draggable, resizable, minimizable panel without
duplicating the JavaScript.

Why Pointer Events (not HTML5 Drag-and-Drop)?
----------------------------------------------
HTML5 DnD targets *data transfer*, not arbitrary element
repositioning; ``dragend`` reports ``clientX=0`` in WebKit/Gecko
so persistence is broken, and it has no native touch support.
Pointer Events with :func:`setPointerCapture` unify mouse/touch/pen
and survive the cursor leaving the window mid-drag. When capture
is lost (iframe, cross-origin widget, OS palm rejection), we fall
back to document-level pointer listeners that still receive
clientX/clientY.

Why not ``q-card-drag``?
------------------------
Quasar does not ship one — verified against the venv's Quasar
build. There is no built-in draggable card primitive in either
Quasar or NiceGUI.

Persistence scope
-----------------
Drag position and size are persisted to ``sessionStorage``
(per tab) and to an in-memory JS namespace (per page session).
They are *not* persisted across full page reloads in a fresh
tab — that would require a server round-trip we don't currently
need. Position + size survive every close/open cycle and every
tab switch within the same browser tab.

Usage
-----

The body builder is responsible for emitting a card with the
configured ``card_class`` and a drag-handle element with
``header_class``. Typical pattern::

    floating = DraggableCard(
        case_slug='sthr',
        card_class='faceplate-dialog-card',
        header_class='faceplate-dialog-header',
    )

    def body(card):
        with ui.card().classes('faceplate-root faceplate-dialog-card'):
            with ui.row().classes('faceplate-header faceplate-dialog-header'):
                # minimize button
                btn = ui.button(icon='horizontal_rule')
                tooltip = ui.tooltip('Minimize')
                card.register_minimize_button(btn, tooltip)
                # ...rest of body

    floating.build(body)
    floating.open()

The first consumer is
:class:`app.components.faceplate_dialog.FaceplateDialog` (the
new faceplate ``ui.dialog``).

Note: the legacy
:class:`app.components.floating_runtime_manager.FloatingRuntimeManager`
is *not* (yet) a consumer — its inline drag / resize / minimize
JS is heavily tuned (see the comments in
``floating_runtime_manager.py``) and a straight swap would
require updating the runtime manager's CSS to use the new
``<card-class>-minimized`` naming convention. That refactor
is a follow-up; the helper is built so it can be dropped in
without changing its public API.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from nicegui import ui

# JS SCRIPT FACTORIES
# Each script is a string of JavaScript that the Python side
# dispatches to the client via ``ui.run_javascript``. They are
# parameterised by the per-instance ``case_slug`` and ``card_id``
# so two different ``DraggableCard`` instances (e.g. the runtime
# manager and the faceplate) can coexist on the same page
# without clobbering each other's state.
# The scripts use the namespace prefix ``__draggableCard``
# (vs the legacy ``__floatingRuntimeManager``) for the *new*
# instances; the runtime manager will keep its existing JS
# verbatim so we don't touch behaviour while we extract the
# helper. Future consumers will use the new helper.


def _namespace_prefix(case_slug: str) -> str:
    """Return the per-case JS namespace prefix used everywhere."""
    return f'__draggableCard_{_safe_js_ident(case_slug)}'


def _safe_js_ident(slug: str) -> str:
    """Make a string safe to embed in a JS identifier.

    Strips characters that would break ``window.__draggableCard_<slug>``
    and falls back to ``'default'`` if the result is empty.
    """
    out = ''.join(ch if (ch.isalnum() or ch == '_') else '_' for ch in str(slug))
    return out or 'default'


def _ensure_namespace_js(case_slug: str) -> str:
    """Return JS that initializes the shared client-side namespaces.

    Both the drag script and the re-apply script need these maps to
    exist before they run. Calling this script is idempotent — running
    it multiple times is a no-op after the first.
    """
    nsp = _namespace_prefix(case_slug)
    return f"""
    window.{nsp}Ctl = window.{nsp}Ctl || {{}};
    window.{nsp}Positions = window.{nsp}Positions || {{}};
    window.{nsp}Sizes = window.{nsp}Sizes || {{}};
    window.{nsp}CardId = window.{nsp}CardId || {{}};
    """


def _drag_script(
    card_id: str,
    case_slug: str,
    *,
    card_class: str,
    header_class: str,
    position_storage_key: str,
    size_storage_key: str | None,
    min_width: int,
    min_height: int,
    install_resize_handles: bool,
) -> str:
    """Return the JS that binds drag + (optional) resize to ``card_id``.

    Targets the ``.<header_class>`` row of the card (the card chrome
    the body renderer already emits — so we don't need a new DOM
    element just to act as a drag handle). The script is
    self-contained: it skips drags that started on interactive
    children (buttons, inputs, selects, q-field, role=button) so
    the user can still click the close button, status label, and
    any other control inside the header.

    The controller for the active drag listeners is stored at
    ``window.<nsp>Ctl[caseSlug]``, keyed by case slug. Storing it
    off-DOM (not on the card element) is what makes teardown
    survive Quasar destroying and recreating the card on
    close/open.

    The script registers a persistent document-level listener for
    the ``<nsp>Rebind:<case>`` CustomEvent so the re-apply script
    can request a full rebind when needed (controller aborted,
    card replaced, etc.).
    """
    nsp = _namespace_prefix(case_slug)
    return f"""
    (function() {{
        var cardId = {card_id!r};
        var caseSlug = {case_slug!r};
        var cardClass = {card_class!r};
        var headerClass = {header_class!r};
        var positionKey = {position_storage_key!r};
        var sizeKey = {size_storage_key!r};
        var minW = {int(min_width)};
        var minH = {int(min_height)};
        var installResize = {str(bool(install_resize_handles)).lower()};

        window.{nsp}Ctl = window.{nsp}Ctl || {{}};
        window.{nsp}Positions = window.{nsp}Positions || {{}};
        window.{nsp}Sizes = window.{nsp}Sizes || {{}};
        window.{nsp}CardId = window.{nsp}CardId || {{}};

        // Idempotent install — re-running this script (e.g. on
        // hot-reload) must not stack rebind listeners.
        var installFlag = '{nsp}Installed';
        if (window[installFlag]) {{
            window.{nsp}CardId[caseSlug] = cardId;
            document.dispatchEvent(new CustomEvent(
                '{nsp}Rebind:' + caseSlug,
            ));
            return;
        }}
        window[installFlag] = true;
        window.{nsp}CardId[caseSlug] = cardId;

        // Seed the position namespace from sessionStorage if the
        // JS map does not already know about this case.
        if (!window.{nsp}Positions[caseSlug]) {{
            var stored = null;
            try {{
                var raw = window.sessionStorage.getItem(positionKey);
                if (raw) {{ stored = JSON.parse(raw); }}
            }} catch (_) {{ stored = null; }}
            if (stored && typeof stored.left === 'number'
                && typeof stored.top === 'number') {{
                window.{nsp}Positions[caseSlug] = stored;
            }}
        }}

        function persist(left, top) {{
            var rounded = {{ left: Math.round(left),
                             top: Math.round(top) }};
            window.{nsp}Positions[caseSlug] = rounded;
            try {{
                window.sessionStorage.setItem(
                    positionKey, JSON.stringify(rounded),
                );
            }} catch (_) {{ /* private mode etc. */ }}
        }}

        function getCard() {{
            var liveCardId = (
                window.{nsp}CardId || {{}}
            )[caseSlug] || cardId;
            // Always walk the live Quasar dialogs first. The card
            // is always in the slot (the dialog is hidden, not
            // destroyed, between close and reopen — confirmed in
            // the NiceGUI source at dialog.py:14-29 and dialog.js).
            // We do NOT filter on ``inner.offsetParent`` because
            // Quasar's show-transition can leave the inner briefly
            // with ``offsetParent === null`` for a few frames,
            // which would make the walk miss the card and either
            // return null (and retry for ~5 s) or pick a sibling
            // dialog's card by mistake. The id/class
            // re-assertion below is idempotent.
            var dialogs = document.querySelectorAll('.q-dialog');
            for (var i = dialogs.length - 1; i >= 0; i--) {{
                var c = dialogs[i].querySelector('.' + cardClass);
                if (c) {{
                    if (!c.id) {{ c.id = liveCardId; }}
                    return c;
                }}
            }}
            // Fallback: id-based lookup, but only if the result
            // is actually attached to the live document. A
            // detached node is never what we want.
            var byId = document.getElementById(liveCardId);
            if (byId && document.body.contains(byId)) {{ return byId; }}
            return null;
        }}

        function applyPosition(card) {{
            if (!card) {{ return null; }}
            // The body CSS does its own centering. We just clear
            // any inline ``left``/``top``/``transform`` from a
            // prior drag so the flex layout re-centers the card
            // on the next open. No JS math — race-free with
            // Quasar's show-transition.
            card.style.left = '';
            card.style.top = '';
            card.style.transform = '';
            card.style.visibility = 'visible';
            return {{ left: 0, top: 0 }};
        }}

        function bind(card, attempts) {{
            if (!card) {{ return; }}
            attempts = attempts || 0;
            var header = card.querySelector('.' + headerClass);
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
            var existing = window.{nsp}Ctl[caseSlug];
            if (existing && existing.controller) {{
                try {{ existing.controller.abort(); }} catch (_) {{}}
            }}
            document.body.style.userSelect = '';

            var controller = new AbortController();
            var signal = controller.signal;
            var dragState = null;

            header.style.cursor = 'grab';
            header.style.userSelect = 'none';
            header.style.touchAction = 'none';

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
                        '.' + headerClass,
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
                    + '[contenteditable]',
                );
            }}

            // Live-card reference. The DOM ``card`` (and its
            // ``header``) that we bound on may be replaced by
            // Quasar between open/close cycles — when that
            // happens, the card element is detached from the
            // document and writing ``.style.left`` to it is a
            // silent no-op. We solve this by re-querying the
            // live card on every pointer event from a class
            // selector stored in the closure, so a Quasar swap
            // mid-drag is self-healing.
            function liveCard() {{
                return getCard() || card;
            }}
            function liveHeader(lc) {{
                var c = lc || liveCard();
                return (c && c.querySelector('.' + headerClass))
                    || header;
            }}

            function onPointerDown(e) {{
                if (e.button !== 0 && e.pointerType === 'mouse') {{
                    return;
                }}
                if (shouldSkipDrag(e.target)) {{ return; }}
                if (dragState) {{
                    try {{
                        header.releasePointerCapture(dragState.pointerId);
                    }} catch (_) {{}}
                    dragState = null;
                    document.body.style.userSelect = '';
                }}
                var lc = liveCard();
                var lh = liveHeader(lc);
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
                var lc = liveCard();
                if (!lc) {{ return; }}
                var maxLeft = Math.max(
                    0,
                    document.documentElement.clientWidth - 40,
                );
                var maxTop = Math.max(
                    0,
                    document.documentElement.clientHeight - 40,
                );
                var newLeft = Math.max(
                    0,
                    Math.min(maxLeft, dragState.origLeft + dx),
                );
                var newTop = Math.max(
                    0,
                    Math.min(maxTop, dragState.origTop + dy),
                );
                lc.style.left = newLeft + 'px';
                lc.style.top = newTop + 'px';
            }}

            function endDrag(e) {{
                if (!dragState) {{ return; }}
                if (e && e.pointerId !== undefined
                    && e.pointerId !== dragState.pointerId) {{
                    return;
                }}
                try {{
                    (dragState.boundHeader || header).releasePointerCapture(
                        dragState.pointerId,
                    );
                }} catch (_) {{}}
                var lc = liveCard();
                var lh = liveHeader(lc);
                if (lh && lh.style) {{ lh.style.cursor = 'grab'; }}
                document.body.style.userSelect = '';
                if (lc) {{
                    var rect = lc.getBoundingClientRect();
                    persist(rect.left, rect.top);
                }}
                dragState = null;
            }}

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
            header.addEventListener(
                'pointerleave',
                function(e) {{
                    if (
                        dragState
                        && dragState.pointerId === e.pointerId
                    ) {{
                        try {{
                            (dragState.boundHeader || header)
                                .releasePointerCapture(
                                    dragState.pointerId,
                                );
                        }} catch (_) {{}}
                    }}
                }},
                {{ signal }},
            );

            document.addEventListener(
                'pointermove', onPointerMove, {{ signal }},
            );
            document.addEventListener('pointerup', endDrag, {{ signal }});
            document.addEventListener('pointercancel', endDrag, {{ signal }});

            function defensiveEnd() {{ endDrag(); }}
            window.addEventListener('blur', defensiveEnd, {{ signal }});
            document.addEventListener(
                'visibilitychange',
                function() {{
                    if (document.hidden) {{ defensiveEnd(); }}
                }},
                {{ signal }},
            );

            var resizeTimer = null;
            function onResize() {{
                if (resizeTimer) {{ return; }}
                resizeTimer = setTimeout(function() {{
                    resizeTimer = null;
                    var rc = liveCard();
                    if (!rc) {{ return; }}
                    var rect = rc.getBoundingClientRect();
                    var maxLeft = Math.max(
                        0,
                        document.documentElement.clientWidth - 40,
                    );
                    var maxTop = Math.max(
                        0,
                        document.documentElement.clientHeight - 40,
                    );
                    var newLeft = Math.max(
                        0,
                        Math.min(maxLeft, rect.left),
                    );
                    var newTop = Math.max(
                        0,
                        Math.min(maxTop, rect.top),
                    );
                    rc.style.left = newLeft + 'px';
                    rc.style.top = newTop + 'px';
                    persist(newLeft, newTop);
                }}, 120);
            }}
            window.addEventListener('resize', onResize, {{ signal }});

            requestAnimationFrame(function() {{
                requestAnimationFrame(function() {{
                    applyPosition(liveCard() || card);
                }});
            }});

            window.{nsp}Ctl[caseSlug] = {{
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

        document.addEventListener(
            '{nsp}Rebind:' + caseSlug,
            function(e) {{
                var card = (e && e.detail && e.detail.card) || getCard();
                if (card) {{ bind(card); }}
            }},
        );

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

        if (installResize && sizeKey) {{
            var SIDES = ['n', 'e', 's', 'w', 'ne', 'se', 'sw', 'nw'];

            function persistSize(width, height) {{
                var rounded = {{
                    width: Math.round(width),
                    height: Math.round(height),
                }};
                window.{nsp}Sizes[caseSlug] = rounded;
                try {{
                    window.sessionStorage.setItem(
                        sizeKey, JSON.stringify(rounded),
                    );
                }} catch (_) {{ /* private mode etc. */ }}
            }}

            function seedSizeFromStorage(card) {{
                var stored = null;
                try {{
                    var raw = window.sessionStorage.getItem(sizeKey);
                    if (raw) {{ stored = JSON.parse(raw); }}
                }} catch (_) {{ stored = null; }}
                if (!stored
                    || typeof stored.width !== 'number'
                    || typeof stored.height !== 'number') {{
                    return;
                }}
                try {{
                    var widthVar = '--' + cardClass + '-width';
                    var heightVar = '--' + cardClass + '-height';
                    card.style.setProperty(
                        widthVar, stored.width + 'px',
                    );
                    card.style.setProperty(
                        heightVar, stored.height + 'px',
                    );
                }} catch (_) {{ /* card detached etc. */ }}
            }}

            function clampSize(width, height) {{
                var maxW = Math.max(
                    minW,
                    document.documentElement.clientWidth - 16,
                );
                var maxH = Math.max(
                    minH,
                    document.documentElement.clientHeight - 16,
                );
                return {{
                    width: Math.max(minW, Math.min(maxW, width)),
                    height: Math.max(minH, Math.min(maxH, height)),
                }};
            }}

            function mountResizeHandles(card) {{
                if (!card) {{ return; }}
                // Guard against double-mount by looking at the live DOM
                // instead of a JS property.  Vue/Quasar may recreate the
                // card's children on dialog open/close, which removes
                // foreign appended handles.  Re-querying the DOM makes
                // the mount idempotent even after a Vue patch.
                if (card.querySelector('.' + cardClass + '-resize-handle')) {{
                    seedSizeFromStorage(card);
                    return;
                }}
                seedSizeFromStorage(card);
                SIDES.forEach(function(side) {{
                    var h = document.createElement('div');
                    h.className = cardClass + '-resize-handle '
                        + cardClass + '-resize-handle-' + side;
                    h.dataset.side = side;
                    card.appendChild(h);
                    bindOneHandle(card, h, side);
                }});
            }}

            function bindOneHandle(card, handle, side) {{
                var dragInfo = null;
                handle.addEventListener('pointerdown', function(e) {{
                    if (e.button !== 0 && e.pointerType === 'mouse') {{
                        return;
                    }}
                    if (card.classList.contains(cardClass + '-minimized')) {{
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
                    if (side.indexOf('w') !== -1) {{
                        newLeft = dragInfo.startLeft
                            + (dragInfo.startW - clamped.width);
                    }}
                    if (side.indexOf('n') !== -1) {{
                        newTop = dragInfo.startTop
                            + (dragInfo.startH - clamped.height);
                    }}
                    var widthVar = '--' + cardClass + '-width';
                    var heightVar = '--' + cardClass + '-height';
                    card.style.setProperty(
                        widthVar, clamped.width + 'px',
                    );
                    card.style.setProperty(
                        heightVar, clamped.height + 'px',
                    );
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
            document.addEventListener(
                '{nsp}Rebind:' + caseSlug,
                function() {{
                    tryMountHandles(0);
                }},
            );
        }}
    }})();
    """


def _reapply_script(card_id: str, case_slug: str, card_class: str) -> str:
    """Return JS that ensures drag is bound and position re-applied.

    Called on every ``open()``. If the card was *not* replaced and a
    live controller exists, this just re-applies the saved position. If
    the card was replaced or the controller was aborted, this dispatches
    the rebind CustomEvent — the drag script's persistent document
    listener picks it up and re-binds onto the live card.
    """
    nsp = _namespace_prefix(case_slug)
    return f"""
    (function() {{
        var cardId = {card_id!r};
        var caseSlug = {case_slug!r};
        var cardClass = {card_class!r};
        window.{nsp}Ctl = window.{nsp}Ctl || {{}};
        window.{nsp}CardId = window.{nsp}CardId || {{}};
        window.{nsp}CardId[caseSlug] = cardId;

        function getCard() {{
            var dialogs = document.querySelectorAll('.q-dialog');
            for (var i = dialogs.length - 1; i >= 0; i--) {{
                var c = dialogs[i].querySelector('.' + cardClass);
                if (c) {{
                    if (!c.id) {{ c.id = cardId; }}
                    return c;
                }}
            }}
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
            var ctl = window.{nsp}Ctl[caseSlug];
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
                    try {{ ctl.rebind(liveCard); }} catch (_) {{}}
                }} else {{
                    document.dispatchEvent(new CustomEvent(
                        '{nsp}Rebind:' + caseSlug,
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
            try {{ liveCard.style.visibility = 'visible'; }} catch (_) {{}}
        }}

        requestAnimationFrame(function() {{
            requestAnimationFrame(function() {{ tick(0); }});
        }});
    }})();
    """


def _abort_script() -> str:
    """Return JS that clears any stuck global drag state on close.

    We deliberately do NOT abort the JS drag controller on close. The
    reapply script's positive-proof check on the next ``open()`` will
    rebind the controller against the live card only if it has actually
    become stale. Aborting here was the source of the "first open works,
    second open shows only the backdrop" symptom documented in
    :mod:`app.components.floating_runtime_manager`. This script is kept
    for parity with the legacy helper, but only clears user-select and
    cursor state.
    """
    return """
    (function() {
        document.body.style.userSelect = '';
    })();
    """


def _tag_card_script(card_id: str, card_class: str) -> str:
    """Return JS that tags the most recently opened Quasar dialog's card.

    The drag script's ``getCard()`` walk looks for the card by class,
    but several other pieces (reapply script, manual position reset on
    open) need the DOM ``id`` to be set. This script finds the card and
    stamps the id if it isn't already set. Idempotent.
    """
    return f"""
    (function() {{
        var cardId = {card_id!r};
        var cardClass = {card_class!r};
        var dialogs = document.querySelectorAll('.q-dialog');
        var card = null;
        for (var i = dialogs.length - 1; i >= 0; i--) {{
            card = dialogs[i].querySelector('.' + cardClass);
            if (card) {{ break; }}
        }}
        if (!card) {{
            var cards = document.querySelectorAll('.' + cardClass);
            card = cards[cards.length - 1] || null;
        }}
        if (!card) {{ return; }}
        if (!card.id) {{ card.id = cardId; }}
    }})();
    """


# PYTHON HELPER

# A registered minimize button is one of:
#   - a bare ``ui.button`` (legacy)
#   - a ``(ui.button, ui.tooltip)`` tuple (preferred)
MinimizeButtonRef = Any | tuple[Any, Any | None]


class DraggableCard:
    """Generic draggable / resizable / minimizable dialog helper.

    A thin Python wrapper around a ``ui.dialog`` that adds:

    * Pointer-event-based drag (re-uses the
      ``__draggableCard_<case>`` JS namespace and
      ``sessionStorage``-backed position persistence).
    * Optional 8-direction resize via JS-mounted handles
      (``install_resize_handles=True``).
    * Minimize toggle with idempotent classList toggle and
      per-button icon/tooltip sync (matches the
      :class:`FloatingRuntimeManager` behaviour).
    * Drawer-aware centering via a CSS custom property
      (``drawer_offset_var``) that the host page can set on
      the card.

    Subclassing is **not** required. Instead, build a
    ``ui.dialog`` inside :meth:`build`, emit the body via the
    supplied ``body_builder(card)`` callable, and call
    :meth:`open` / :meth:`close` to control visibility.

    The body builder is given a reference to ``self`` so it
    can call :meth:`register_minimize_button` after creating
    each minimize button.
    """

    _next_card_id = 0

    def __init__(
        self,
        *,
        case_slug: str,
        card_class: str,
        header_class: str,
        install_resize_handles: bool = True,
        min_width: int = 360,
        min_height: int = 220,
        position_storage_key: str | None = None,
        size_storage_key: str | None = None,
        drawer_offset_var: str = '--dc-drawer-offset',
    ) -> None:
        self.case_slug = str(case_slug)
        self._card_class = str(card_class)
        self._header_class = str(header_class)
        self._install_resize = bool(install_resize_handles)
        self._min_width = int(min_width)
        self._min_height = int(min_height)
        self._position_storage_key = (
            str(position_storage_key) if position_storage_key else f'floatingCard:{self.case_slug}'
        )
        self._size_storage_key = (
            str(size_storage_key)
            if size_storage_key
            else (f'floatingCardSize:{self.case_slug}' if install_resize_handles else None)
        )
        self._drawer_offset_var = str(drawer_offset_var)

        self._card_id: str = self._make_card_id()
        self._dialog: ui.dialog | None = None
        self._minimized: bool = False
        # Mirrors FloatingRuntimeManager's bookkeeping. The list
        # lets ``toggle_minimize()`` keep each registered
        # button's icon/tooltip in sync with the server-side
        # state. Each entry is a bare button or a
        # ``(button, tooltip)`` tuple.
        self._minimize_button_refs: list[MinimizeButtonRef] = []

    # ── ID factory ──

    @classmethod
    def _make_card_id(cls) -> str:
        cls._next_card_id += 1
        return f'draggable-card-{cls._next_card_id}'

    # ── Build ──

    def build(self, body_builder: Callable[[DraggableCard], None]) -> DraggableCard:
        """Build the dialog, run the body builder, install scripts.

        Idempotent within an instance: a second call after the
        first is a no-op (the dialog already exists).

        ``body_builder`` is called with ``self`` so it can wire
        up minimize buttons via
        :meth:`register_minimize_button` as it creates them.
        """
        if self._dialog is not None:
            return self
        self._dialog = ui.dialog().props('persistent no-focus-trap model-value=false')
        with self._dialog:
            body_builder(self)

        # Initialize the shared namespaces, then tag the card,
        # then install the drag script. The drag script's
        # install guard makes the install a no-op on subsequent
        # dialog rebuilds (it just re-emits the rebind event).
        ui.run_javascript(_ensure_namespace_js(self.case_slug))
        ui.run_javascript(
            _tag_card_script(self._card_id, self._card_class),
        )
        ui.run_javascript(
            _drag_script(
                self._card_id,
                self.case_slug,
                card_class=self._card_class,
                header_class=self._header_class,
                position_storage_key=self._position_storage_key,
                size_storage_key=self._size_storage_key,
                min_width=self._min_width,
                min_height=self._min_height,
                install_resize_handles=self._install_resize,
            ),
        )
        return self

    # ── Public API ──

    def open(self) -> None:
        """Mount the dialog (if not already mounted) and show it.

        We deliberately do NOT run any DOM-mutating JS before
        ``self._dialog.open()``. Letting Quasar run its show-transition
        cleanly, then handing control to the reapply script, is race-
        free.
        """
        if self._dialog is None:
            # No-op if build() was never called. The subclass
            # usually drives build() in its own __init__ /
            # eager-build path.
            return
        self._dialog.open()
        ui.run_javascript(_ensure_namespace_js(self.case_slug))
        # Force-center the card on every open. We run this
        # immediately (no rAF) so the user does not see the
        # card flash at its prior position before the
        # reapply script's double-rAF fires. The reapply
        # script's later ``applyPosition`` call (via
        # ``ctl.reapply``) is still the source of truth —
        # this is just a synchronous, immediate force-center
        # that clears any inline ``left``/``top``/``transform``
        # from a prior drag.
        ui.run_javascript(f"""
            (function() {{
                var card = document.getElementById({self._card_id!r});
                if (!card) {{ return; }}
                card.style.left = '';
                card.style.top = '';
                card.style.transform = '';
                card.style.setProperty(
                    {self._drawer_offset_var!r}, '0px',
                );
                card.style.visibility = 'visible';
            }})();
            """)
        ui.run_javascript(
            _reapply_script(self._card_id, self.case_slug, self._card_class),
        )
        if self._minimized:
            # Re-showing after a previous minimize — restore
            # the full body so the user can interact with the
            # form.
            ui.run_javascript(f"""
                (function() {{
                    var cardId = {self._card_id!r};
                    var cardClass = {self._card_class!r};
                    var card = document.getElementById(cardId);
                    if (!card) {{
                        var dialogs = document.querySelectorAll('.q-dialog');
                        for (var i = dialogs.length - 1; i >= 0; i--) {{
                            var c = dialogs[i].querySelector('.' + cardClass);
                            if (c) {{ card = c; break; }}
                        }}
                    }}
                    if (!card) {{
                        var cards = document.querySelectorAll('.' + cardClass);
                        card = cards[cards.length - 1] || null;
                    }}
                    if (card) {{
                        card.classList.remove(
                            cardClass + '-minimized',
                        );
                    }}
                }})();
                """)
            self._minimized = False
            # Bring every minimize button back to its "Minimize"
            # affordance so the icon/tooltip mirror the freshly
            # restored body. Done unconditionally so the
            # buttons are also coherent on the very first open.
            self._sync_minimize_buttons()

    def close(self) -> None:
        """Hide the dialog.

        We deliberately do NOT abort the JS drag controller on
        close. Aborting it on every close turned out to be the
        source of the "first open works, second open shows
        only the backdrop" symptom — aborting the controller
        before Quasar's show-transition completed forced the
        reapply script into the rebind path, whose double-rAF
        fired faster than Quasar's ~200-400 ms show-transition.
        Quasar's transition handler then re-applied its own
        ``visibility: hidden`` to the slot children,
        overwriting the ``applyPosition`` flip and leaving
        the card invisible.

        Leaving the controller alive is safe: the dialog is
        hidden, so no pointer events reach the card. The
        reapply script's positive-proof check on the next
        ``open()`` will rebind the controller against the live
        card only if it has actually become stale.
        """
        if self._dialog is not None:
            self._dialog.close()
            # Belt-and-braces: clear any stuck global drag
            # state. The drag script may have set
            # ``body.userSelect='none'`` during a prior drag
            # that wasn't cleanly ended.
            ui.run_javascript('(function() {{ document.body.style.userSelect = ""; }})();')

    def toggle(self) -> None:
        """Open the dialog if hidden, close it if visible."""
        if self._dialog is None:
            self.open()
            return
        if self.is_open:
            self.close()
        else:
            self.open()

    # ── Minimize ──

    def toggle_minimize(self) -> None:
        """Toggle the card's minimized (header-only) state.

        Target state is computed BEFORE the Python attribute is flipped,
        then handed to JavaScript as an explicit boolean. Using
        ``card.classList.toggle('<card>-minimized', target)`` with an
        explicit boolean makes the JS path idempotent and self-healing.
        """
        if self._dialog is None:
            return
        target = not self._minimized
        target_js = 'true' if target else 'false'
        ui.run_javascript(f"""
            (function() {{
                var cardId = {self._card_id!r};
                var cardClass = {self._card_class!r};
                var card = document.getElementById(cardId);
                if (!card) {{
                    var dialogs = document.querySelectorAll('.q-dialog');
                    for (var i = dialogs.length - 1; i >= 0; i--) {{
                        var c = dialogs[i].querySelector('.' + cardClass);
                        if (c) {{ card = c; break; }}
                    }}
                }}
                if (!card) {{
                    var cards = document.querySelectorAll('.' + cardClass);
                    card = cards[cards.length - 1] || null;
                }}
                if (!card) {{ return; }}
                if (!card.id) {{ card.id = cardId; }}
                var t = {target_js};
                if (t) {{
                    card.classList.add(cardClass + '-minimized');
                }} else {{
                    card.classList.remove(cardClass + '-minimized');
                }}
            }})();
            """)
        self._minimized = target
        self._sync_minimize_buttons()

    def _sync_minimize_buttons(self) -> None:
        """Update every registered minimize button to mirror state.

        Mirrors the runtime manager's sync pattern: each
        button gets a fresh ``icon`` and ``aria-label`` so the
        user always sees an unambiguous affordance.

        * ``horizontal_rule`` + "Minimize" when expanded.
        * ``crop_square`` + "Restore" when collapsed.
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

    def register_minimize_button(
        self,
        btn: Any,
        tooltip: Any | None = None,
    ) -> None:
        """Register a minimize / restore button for state sync.

        ``btn`` is the ``ui.button`` (its ``icon`` and ``aria-label``
        props are mutated by :meth:`_sync_minimize_buttons` to mirror
        the current state). ``tooltip`` is an optional ``ui.tooltip``
        whose ``.text`` is updated in lockstep — preferred over
        ``btn.tooltip(...)`` because the latter is additive and would
        stack tooltips on every call.
        """
        if tooltip is not None:
            self._minimize_button_refs.append((btn, tooltip))
        else:
            self._minimize_button_refs.append(btn)

    # ── Introspection ──

    @property
    def card_id(self) -> str:
        """The DOM id assigned to this card (for testing)."""
        return self._card_id

    @property
    def card_class(self) -> str:
        """The CSS class used by the drag/reapply JS to find the card."""
        return self._card_class

    @property
    def is_minimized(self) -> bool:
        return self._minimized

    @property
    def is_open(self) -> bool:
        """Whether the dialog is currently visible.

        Tries ``self._dialog.value`` first (the canonical
        NiceGUI 3.x signal — ``open()`` sets ``value = True``,
        ``close()`` sets ``value = False``). Falls back to
        ``self._dialog.props.get('visible')`` for any older
        NiceGUI that doesn't expose ``value``.
        """
        if self._dialog is None:
            return False
        value = getattr(self._dialog, 'value', None)
        if value is not None:
            return bool(value)
        return bool(self._dialog.props.get('visible', False))


__all__ = [
    'DraggableCard',
    'MinimizeButtonRef',
]
