import { Link, NavLink, Outlet, useLocation } from "react-router";

import { Field } from "../ui/Field";


/** The frame: identity, then two workspaces, then the sections of the one you are in.
 *
 * **The wordmark is the whole identity and it goes home.** It said `Forge · Comeni Labs` on
 * every screen, which was true while `/` redirected into the forge and every destination was a
 * forge screen. 3B made `/` a real page and 3C adds a half that is not the forge either, so a
 * wordmark naming one workspace was claiming the product is that workspace. Naming the site is
 * the fix that stays true as halves are added.
 *
 * **`Builder` became a link in Plan 3C phase 3**, and `Soon` went with it — nothing is disabled
 * here any more. It was `aria-disabled` for the whole of 3A, 3B and 3D on the rule that a link
 * going nowhere silently is worse than one that admits it; six of those were what made slice 1
 * look finished when nothing on the screen did anything. The rule stands and `Soon` is deleted
 * rather than kept for a future occupant, because a component with no caller is a component that
 * rots.
 *
 * **`?` opens the glossary, from anywhere.** Eight words appear on these screens without ever
 * being defined — contract, role, type, measurement, drift, hole, band, proposal — and the
 * verdict on 2026-08-19 was that the person who co-designed the system could not read its own
 * interface. It lives in the shell rather than on a page so it is reachable from the screen you
 * are confused by rather than from a screen you have to go and find.
 *
 * **The forge left this nav on 2026-08-30 — hidden, not removed.** Operator's decision, Plan 4
 * phase 0. `Forge`, `Queue` and `Tools` were three of the five tabs here; every one of their
 * routes still resolves and `frontend/src/forge/` is untouched. The reason is not that the
 * screens are bad: the forge is carried as needing testing and general rework, nothing in 3E,
 * Wiener or this plan touches it, and a link into a surface nobody is maintaining teaches a
 * person that the product has a half that does not work. It is reachable by URL, which is what
 * the operator and three journal entries actually use.
 *
 * **`router.test.tsx` holds both halves** — that the frame offers no way in, and that every
 * forge URL still mounts — because *hidden* rots into *broken* the first time somebody deletes
 * a route nobody can see any more.
 *
 * **This is not the `Registry` section.** `ov-blocked` on the redesign canvas asks for
 * `Builder / Runs / Registry` with the forge inside Registry, and that is right — but Registry
 * does not exist, and inventing a section to hold one hidden thing is worse than a nav with two
 * tabs. Raise it when Registry has a second occupant.
 *
 * **There is no Registry box.** It was a text input in the nav that took a type id from memory
 * and opened a panel — the operator's verdict was *ugly, unintuitive and useless*, and the
 * design argument behind it does not survive contact: `forge-review.md` §3 wanted the registry
 * consulted *mid-decision*, and the way you consult a type mid-decision is by clicking the type
 * you are looking at, not by retyping it into a box in the corner. The panel went with the box
 * rather than staying reachable by nothing. When it returns it should hang off a type id.
 */
/** 12.5px, `--ink-3`, no box — the artboards' shell has no pills in it.
 *
 * It shipped as a `--pea` inset shadow on a rounded, padded chip at `--ink-2`. Every part of
 * that was invented: the artboard marks the section you are in with **`--ink` and a 1px
 * `--link` underline**, 3px clear of the baseline, and leaves the others as flat text. A pill
 * reads as a button — as something to press rather than as where you already are. */
const nav = "pb-[3px] text-[12.5px] no-underline transition-colors border-b border-transparent";
const here = "text-ink border-b-[var(--link)]";

function Tab({ to, children }: { to: string; children: string }) {
  return (
    <NavLink
      to={to}
      className={({ isActive }) =>
        `${nav} ${isActive ? here : "text-ink-3 hover:text-ink"}`
      }
    >
      {children}
    </NavLink>
  );
}

export function Shell() {
  // **One field for the whole application, and the route picks where it is thrown from.**
  // The front door's arcs bloom from below the prompt (`OverviewFirst`); every other board
  // throws them from the lower-left corner (`_field.html`). Two mounted fields stacked their
  // gradients into a grey wash, which is exactly what the first attempt looked like.
  const bloom = useLocation().pathname === "/";

  return (
    <div className="grid grid-rows-[auto_1fr] h-dvh">
      {/* **`auto`, not a 54px track.** The bar was a fixed row and the text sat 10px from its
          top and 23px from its bottom — visibly high, because a fixed height and the row's own
          padding were two answers to the same question and the track won. The artboards have
          no bar at all: the shell is a line of text with the page's 28px above it and 20px
          below, ruled off. Let the content set the height and nothing is left to disagree. */}
      {/* **Behind everything, and it is the page's ground rather than a decoration.** Every
          artboard opens on an arc field, a scan texture and a vignette; the app had none of
          them and drew a flat black rectangle, which is most of why the built screens did not
          look like the drawings they came from. */}
      <Field origin={bloom ? "bottom" : "corner"} />

      {/* **Transparent, not `bg-surface`.** The artboards' shell is a hairline bottom border
          over the field — a filled bar cuts the ground off at the top of the page and makes
          the header read as a separate product from everything under it. */}
      {/* **Baseline-aligned, 28px apart, and the wordmark is one word.** The artboards set
          `Comeni` at 14px/700/-.02em and the sections at 12.5px, all sitting on one baseline.
          It shipped as `● Comeni Labs` in the display face beside three pill buttons — four
          differences from the drawing, in the one row that is on every screen.

          **The right-hand side is empty on purpose.** The artboard puts a `⌘K` command hint and
          a laboratory name there. Neither exists: the hint is door 1 again plus a jump palette
          nothing implements, and the laboratory name is a fact this half of the product does not
          hold. Drawing either would be inventing a control or inventing a fact. */}
      {/* **`py-3.5`, not the artboard's 28/20.** The drawing has no bar — its 28px is the
          PAGE's top padding, and lifting that into a persistent header made 68px of chrome
          above every screen. The page keeps its 28px; the bar is a bar, and a compact one.
          `gap-7` at 28px is the artboard's own spacing between the wordmark and the sections. */}
      <nav className="gutter flex items-baseline gap-7 py-3.5 border-b border-line">
        <Link
          to="/"
          aria-label="Comeni — home"
          /* **Same box metrics as a Tab.** The tabs carry a 3px pad and a 1px underline, so a
             wordmark without them made the flex line 4px taller at the bottom than the top —
             14px above the text and 19px below, which is what "not centred" was. */
          className="pb-[3px] border-b border-transparent text-[14px] font-bold
                     tracking-[-.02em] text-ink no-underline"
        >
          Comeni
        </Link>

        <Tab to="/build">Builder</Tab>
        <Tab to="/runs">Runs</Tab>
      </nav>
      <Outlet />
    </div>
  );
}
