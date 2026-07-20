"""App/ui — small UI primitives that complement (not replace) the existing
NiceGUI components.

Modules
-------
- :mod:`app.ui.loading` — full-panel spinner overlay with blurred
  gradient backdrop.
- :mod:`app.ui.section_loader` — deferred section mount pattern.
- :mod:`app.ui.bridge_store` — server-side dispatcher that batches
  every live value into a single ``ui.run_javascript`` per tick.
- :mod:`app.ui.button_feedback` — instant client-side click feedback.

All primitives are additive: nothing in this package replaces
existing components, and the rest of the app imports only when it
wants the new behavior.
"""
