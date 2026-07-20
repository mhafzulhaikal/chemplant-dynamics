# app/assets.py

"""Static-asset bundling helpers.

Collects CSS files from the local ``static/css/`` tree and returns them as
a single concatenated string. This is used by
:func:`app.layouts.shell.setup_page_shell` to inline all styles in
the page ``<head>`` instead of relying on
``<link rel="stylesheet" href="/static/css/...">`` tags.

Why inline?
-----------
In NiceGUI's ``on_air`` mode the app is exposed via the ``on-air.nicegui.io``
relay. Browser requests for ``/static/css/...`` are forwarded through the
relay to the local ASGI app, and in practice they are frequently 404'd or
cross-origin-blocked — leaving the page unstyled. Inlining the CSS
removes the round-trip entirely and works identically in local and
on_air mode.

Load order
----------
CSS files are resolved by **following @import chains** starting from
``app.css`` (the entry point), exactly as a browser would. This ensures
``tokens.css`` (which defines all CSS custom properties) is inlined first,
before any file that references those variables. A plain alphabetical
``rglob`` would place ``tokens.css`` last and break every variable reference.

``@import`` handling
--------------------
Each ``@import`` is replaced in-place with the full content of the imported
file (recursively).  The ``@import`` line itself is stripped from the output.
Any files not reachable via imports from ``app.css`` are appended at the end.
"""

from __future__ import annotations

import re
from pathlib import Path

# Separator comment injected between inlined files for readability.
_SEP = '\n\n/* ===== {rel} ===== */\n'

# Matches @import url("foo.css"), @import url('foo.css'), @import "foo.css"
# with optional version queries like ?v=3
_IMPORT_RE = re.compile(
    r"""@import\s+(?:url\(\s*['"]?([^'"\)\s;]+)['"]?\s*\)|'([^']+)'|"([^"]+)")\s*;"""
)


def _collect(path: Path, css_root: Path, seen: set[Path]) -> str:
    """Return the fully-inlined CSS for ``path``.

    Recursively resolves ``@import`` statements in source order,
    replacing each with the inlined content of the imported file.
    Already-seen files are skipped (returns empty string) to prevent
    duplicates.
    """
    try:
        real = path.resolve()
    except OSError:
        return ''

    if real in seen:
        return ''
    seen.add(real)

    try:
        source = path.read_text(encoding='utf-8-sig')  # strips BOM if present
    except OSError:
        return ''

    try:
        path.relative_to(css_root).as_posix()
    except ValueError:
        pass

    # Replace each @import with the inlined content of the imported file.
    def _replace(m: re.Match) -> str:  # type: ignore[type-arg]
        raw = m.group(1) or m.group(2) or m.group(3)
        raw = raw.split('?')[0]  # strip ?v=3 query strings
        imp_path = (path.parent / raw).resolve()
        try:
            imp_rel = imp_path.relative_to(css_root).as_posix()
        except ValueError:
            imp_rel = imp_path.name
        inlined = _collect(imp_path, css_root, seen)
        if inlined:
            return _SEP.format(rel=imp_rel) + inlined
        return ''

    result = _IMPORT_RE.sub(_replace, source).strip()
    return result


def collect_css(static_dir: Path) -> str:
    """Bundle every CSS file under ``<static_dir>/css/`` into one string.

    Starts from ``app.css`` and follows ``@import`` chains to guarantee
    the correct cascade order (tokens → base → components → …).  Files
    not reachable from ``app.css`` are appended alphabetically at the
    end.

    :param static_dir: path to the project's ``app/static`` directory.
    :return: concatenated CSS ready to embed in a ``<style>`` tag. Empty
        string if the ``css/`` directory is missing.
    """
    css_root = Path(static_dir) / 'css'
    if not css_root.is_dir():
        return ''

    seen: set[Path] = set()
    chunks: list[str] = []

    # Primary pass: entry-point-driven, respects @import order.
    entry = css_root / 'app.css'
    if entry.is_file():
        content = _collect(entry, css_root, seen)
        if content:
            chunks.append(_SEP.format(rel='app.css'))
            chunks.append(content)

    # Secondary pass: files not reachable from app.css.
    for path in sorted(p for p in css_root.rglob('*.css') if p.is_file()):
        if path.resolve() not in seen:
            rel = path.relative_to(css_root).as_posix()
            try:
                source = _IMPORT_RE.sub('', path.read_text(encoding='utf-8-sig')).strip()
            except OSError:
                continue
            if source:
                chunks.append(_SEP.format(rel=rel))
                chunks.append(source)

    return ''.join(chunks)


__all__ = ['collect_css']
