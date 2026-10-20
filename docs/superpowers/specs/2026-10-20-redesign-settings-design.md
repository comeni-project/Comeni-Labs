# Redesign 7 — settings

**Issue:** #381 (parent #370). **Status:** implemented on `redesign-settings` (stacked on part 6),
2026-10-20, without a question round at the operator's request. **Scope split (operator,
2026-10-20):** the overlay's redraw is this part; the **registry release setting** (follow the
newest or pin one) is the forge's (#360), which brings its backend.

## What was found

The overlay already took the part 1 tokens and part 2's shell: server-declared sections, the
groups *This browser / This installation / Reported*, rounded controls. The board's *GitHub
token shown as set or not, never typed* already holds: `registry.github` is a reported setting
whose value is `token_state()` (`set` / `not set`) and whose control is read-only.

## What changes

The overlay's own words were set in the data font as lowercase labels: the subtitle, *esc*, the
`.env` note and the section counts. They become sentences in the interface face (*This
installation · every change is saved as you make it*, an *Esc* key cap, *A value in `.env`
always wins.*), and a section's *N set* count is emphasised in the selected colour.

## Testing

`Preferences.test.tsx`: the subtitle and the `.env` sentence. Browser: the real catalogue's
menu, generated from `comeni_core.settings.catalogue.CATALOGUE` with an in-memory store, served
by the DevTools script; 1440 and 390, light and dark.
