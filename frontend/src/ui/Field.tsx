/** The ground every artboard sits on — **not wallpaper, and not decoration.**
 *
 * ═══ WHY THIS EXISTS AT ALL ═══════════════════════════════════════════════════════════════
 *
 * It was deferred through Plan 4 as "the three-layer arc field — decorative ambience", and that
 * was wrong. `body { background: var(--paper) }` and nothing else is a flat black rectangle;
 * every `.dc.html` artboard opens with an arc field, a scan texture and a vignette, and their
 * absence is the single biggest reason the built pages did not look like the drawings.
 *
 * The name for what it does is **depth without ornament**. The panels are flat, square and
 * unshadowed by design; without something behind them they read as a list of grey boxes on
 * black. The field is what makes a panel sit *in* a page rather than *on* one.
 *
 * ═══ THREE LAYERS, EACH DOING ONE THING ══════════════════════════════════════════════════
 *
 * 1. **The arcs** — concentric circles from an origin far off the bottom of the frame, in
 *    `--link` with a second `--pea` family. `.breathe` swells them over 46s and `.slowA`
 *    rotates over 680s: both are far below the threshold at which anything appears to move,
 *    which is the point. It is a texture that is never caught moving.
 * 2. **The scan** — 1px lines every 3px at 1% white. A CRT reference, and the reason the
 *    background is not a perfectly clean gradient. It is what keeps the ground from looking
 *    like a print.
 * 3. **The vignette** — a radial that darkens toward the edges, so a page's own margins hold
 *    the eye in the middle without a border.
 *
 * ═══ WHAT IT MUST NOT DO ═════════════════════════════════════════════════════════════════
 *
 * `pointer-events: none` on every layer and `aria-hidden` on the svg. It is behind the whole
 * application, so a layer that swallowed a click would break every control on every screen.
 *
 * **`prefers-reduced-motion` stops it**, in `main.css` alongside the five movements. Two slow
 * animations that never stop are exactly what that media query is for.
 */
export function Field({ origin = "bottom" }: { origin?: "bottom" | "corner" }) {
  return (
    <div aria-hidden className="fixed inset-0 pointer-events-none overflow-hidden -z-10">
      {/* **760 tall, which is the artboard's frame — not 900.** The arcs are struck from an
          origin at y=900, *below* the frame, and a 900-tall viewBox put that origin on the
          bottom edge and pushed every ring out of view: what showed was one faint sweep
          instead of four concentric arcs. The origin is meant to be off-canvas. */}
      <svg className="absolute inset-0 w-full h-full" viewBox="0 0 1400 760"
           preserveAspectRatio="xMidYMid slice">
        <defs>
          <radialGradient id="field-pool" cx="46%" cy="34%" r="58%">
            <stop offset="0%" stopColor="var(--link)" stopOpacity=".055" />
            <stop offset="100%" stopColor="var(--link)" stopOpacity="0" />
          </radialGradient>
        </defs>
        {/* **The pool belongs to the corner variant only.** `_field.html` has it; the front
            door's `OverviewFirst` does not — its bloom IS the light source, and a second wash
            on top of it flattens the arcs into grey fog. Drawing both is exactly what that
            looked like. */}
        {origin === "corner" && <rect width="1400" height="760" fill="url(#field-pool)" />}

        {/* **The origin moves with the page, and the arcs do not change.** The front door
            centres its bloom below the prompt (`OverviewFirst`); every other board throws it
            from the lower-left corner (`_field.html`). One component, two origins — rather
            than two components that drift apart. */}
        <g className="field-breathe" fill="none">
          {origin === "bottom" ? (
            <g className="field-spin" style={{ transformOrigin: "700px 900px" }}
               stroke="var(--link)" strokeWidth="1">
              <circle cx="700" cy="900" r="470" opacity=".10" />
              <circle cx="700" cy="900" r="660" opacity=".07" />
              <circle cx="700" cy="900" r="880" opacity=".048" />
              <circle cx="700" cy="900" r="1140" opacity=".032" />
              <path d="M700 900 L-140 120" strokeWidth=".75" opacity=".05" />
              <path d="M700 900 L1540 120" strokeWidth=".75" opacity=".05" />
            </g>
          ) : (
            <g className="field-spin" style={{ transformOrigin: "60px 700px" }}
               stroke="var(--link)" strokeWidth="1">
              <circle cx="60" cy="700" r="380" opacity=".085" />
              <circle cx="60" cy="700" r="530" opacity=".062" />
              <circle cx="60" cy="700" r="700" opacity=".044" />
              <circle cx="60" cy="700" r="900" opacity=".030" />
            </g>
          )}

          {/* The second family, in `--pea`. Two hues at these opacities do not read as two
              colours — they read as depth, which is the whole trick. */}
          <g stroke="var(--pea)" fill="none">
            {origin === "bottom" ? (
              <circle cx="700" cy="900" r="780" opacity=".035" strokeWidth="1" />
            ) : (
              <>
                <circle cx="1180" cy="-60" r="410" opacity=".055" strokeWidth="1" />
                <circle cx="1180" cy="-60" r="590" opacity=".038" strokeWidth="1" />
                <circle cx="1180" cy="-60" r="800" opacity=".026" strokeWidth="1" />
              </>
            )}
          </g>

          {/* **Chords are the corner field's, not the bloom's.** `_field.html` crosses its arcs
              with three long lines so they stop reading as a target; `OverviewFirst` has none —
              its two rays come off the origin instead, and adding chords on top of them made
              the front door busier than the drawing. */}
          {origin === "corner" && (
            <g stroke="var(--link)" strokeWidth=".75" fill="none">
              <path d="M-80 96 L1480 402" opacity=".045" />
              <path d="M-80 520 L1480 176" opacity=".034" />
              <path d="M180 -60 L1080 820" opacity=".026" />
            </g>
          )}
        </g>
      </svg>

      {/* The rule grid sits under the scan, and only on the boards that carry a table — the
          front door's bloom has no grid behind it. */}
      {origin === "corner" && <div className="absolute inset-0 field-rule" />}
      <div className="absolute inset-0 field-scan" />
      <div className="absolute inset-0 field-vignette" />
    </div>
  );
}
