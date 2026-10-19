---
title: Visual identity
description: Why the screens look the way they do — one meaning per colour, the faces, the type roles and motion.
---

# Visual identity

Comeni Labs and Comeni Code share one identity, because the two products hand people to each
other and should not feel like two brands. They share the identity, not code: Labs keeps its own
copy of the values in `frontend/src/tokens.css`, and no component names a colour, face or curve of
its own. `frontend/src/tokens.test.ts` checks the rules on this page.

## One meaning per colour

A colour on screen always says the same thing, and a value nobody needs to think about spends no
colour at all.

| Meaning | Token | Used for |
|---|---|---|
| Settled | none (the neutral inks and lines) | values a rule or a convention decided |
| Measured | `--measured` (amber) | values read from your files; a model's answer still awaiting review |
| Needs you | `--needs-you` (red) | an open value, or something that went wrong |
| Selected / now | `--now` (blue) | what is selected, running or on offer, inputs, and links |
| Valid / done | `--done` (teal-green) | a valid pipeline, finished stages |
| The main button | `--action` | the one primary action on a screen, raised by a 3px edge |

Each meaning has three shades. The plain token marks a dot, a bar or a border; `-soft` is the
tinted ground behind a chip or a selected row; `-ink` is the shade text wears. Text never wears
the plain mark colour, and every text colour reaches a 4.5:1 contrast against the grounds it is
drawn on, in both themes. A colour is never the only signal: a status also carries an icon and
words, so it reads in print, in greyscale and for a reader who does not see the hue.

## Light first, dark kept

The light palette is the default. Under *Match the system* (Settings → Appearance) the dark
palette applies when the operating system asks for dark; *Light* and *Dark* override the system.
Both palettes set the same tokens, so nothing exists in one theme only.

## Faces and type roles

The interface is set in **Lexend**; data (identifiers, types, paths, numbers in tables) in
**Geist Mono**. Both are bundled with the application rather than fetched, so an installation
with no internet access renders the same page ([invariant 13](invariants.md)).

Text sizes come from a closed set of roles, so a new size is a design decision rather than a
guess: hero 32 px, title 22, heading 16, lede 15, body 14, secondary 13, label 12, brand 17.
Labels are Lexend at 12 px in `--ink-3`; they are not uppercase.

## Shapes

Three radii: 8 px for fields and small controls, 10 px for buttons and canvas nodes, 14 px for
panels; chips are fully round and chart marks keep a 2 px corner. Panels are opaque surfaces with
a hairline border. Graphs you edit are drawn with right-angled wires.

## Motion

One easing curve (`--ease`) for every transition. Five movements and nothing else moves:
*settle* (rows and cards arriving), *grow-x* (bars drawing on first paint), *flow* (something is
happening right now), *blink* (the live cursor) and *lift* (hover on what can be clicked).
Nothing that encodes a quantity moves, and numbers never tween. The page body never scrolls
sideways; a wide table scrolls inside its own `.tbl` container.
