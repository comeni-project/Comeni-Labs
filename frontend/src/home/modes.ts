/** Build and Spawn, as a person is offered them — `LivingOpen`'s two cards.
 *
 * **One choice, two policies over one engine.** Shared by the first-run prompt and the manual
 * builder's *Assistant* tab, because the same verb behind two sets of words is two descriptions
 * that can drift.
 */
export const MODES = [
  { mode: "build", title: "Build step by step", short: "You choose at each real decision.",
    long: "Every step is shown with the reason it is there, and the alternatives that would also fit." },
  { mode: "spawn", title: "Spawn the whole thing", short: "It makes the safe choices and stops where it cannot.",
    long: "Same engine, same pipeline. It only stops where a person genuinely has to answer." },
] as const;
