/** What `mendel build` writes, quoted rather than described.
 *
 * **The hero is the artifact, and the artifact is the argument.** The product claim is *nothing
 * was guessed silently*, and the shortest proof of it is fourteen lines of the file: a module
 * chosen at tier 3 that cites the paper behind the rule, and — immediately below it — a setting
 * that exits at tier 4 and says in the file that nobody judged it. A slogan claiming
 * transparency is a slogan. A generated file admitting *please review* is the product.
 *
 * **It is quoted, not fetched.** Every line comes from
 * `notes/audits/fixtures/pipeline-v1/pipeline.yml` — a real build of the RNA-seq spine — and is
 * static. That is what keeps it on the right side of the discipline the whole page rests on
 * (spec §1: this page counts and links, it never renders an item). An excerpt of the *format*
 * is documentation; a row from the registry's current contents would make this the Overview
 * page that was cut. `renders the same excerpt whatever the API says` holds the difference.
 *
 * The rails are the same colours the tiers carry everywhere else — amber for data-profiled,
 * coral for ambiguous — so a visitor has read the tier language once before ever opening a
 * pipeline. `Standing` draws the same idea as stroke weight at the other end of the page.
 */
type Tier = 3 | 4;

const TIER: Record<Tier, { rail: string; ink: string; name: string }> = {
  3: {
    rail: "border-l-[var(--measured)]",
    ink: "text-[var(--measured)]",
    name: "data-profiled",
  },
  4: {
    rail: "border-l-[var(--undecided)]",
    ink: "text-[var(--undecided)]",
    name: "ambiguous",
  },
};

/** One line: how far in, the key, and what it says. */
function L({ at = 0, k, v }: { at?: number; k?: string; v?: string }) {
  return (
    <div style={{ paddingLeft: at * 10 }} className="whitespace-pre">
      {k && <span className="text-ink-3">{k}</span>}
      {v && <span className="text-ink-2">{v}</span>}
      {!k && !v && " "}
    </div>
  );
}

function Block({ tier, children }: { tier: Tier; children: React.ReactNode }) {
  return (
    <div className={`border-l-2 ${TIER[tier].rail} pl-4 py-2`}>{children}</div>
  );
}

/** `tier:` in its own colour, with the name the four-tier ladder gives it.
 *
 * **Where it sits is not a layout choice.** `tier` is the first key under `why:` in the real
 * file, and moving it to the bottom of the block because a badge anchors better there would
 * make this a mock-up of a `pipeline.yml` rather than a quote of one. The name beside it —
 * *data-profiled*, *ambiguous* — is the ladder's own word, added because a bare `3` teaches
 * nobody anything on first read.
 */
function TierLine({ at, tier }: { at: number; tier: Tier }) {
  const t = TIER[tier];
  return (
    <div
      style={{ paddingLeft: at * 10 }}
      className="flex items-baseline gap-2 whitespace-pre"
    >
      <span className="text-ink-3">tier: </span>
      <b className={`${t.ink} font-semibold`}>{tier}</b>
      <span className={`${t.ink} opacity-80 font-ui text-label uppercase tracking-[.1em]`}>
        {t.name}
      </span>
    </div>
  );
}

export function Artifact() {
  return (
    <figure
      data-testid="artifact"
      className="m-0 rounded-r border border-line bg-surface overflow-hidden
                 shadow-[0_1px_2px_var(--shadow)]"
    >
      <figcaption
        className="flex items-baseline justify-between gap-4 px-4 py-2
                   border-b border-line bg-surface-2"
      >
        <span className="font-data text-secondary text-ink-2">pipeline.yml</span>
        <span className="font-ui text-label uppercase tracking-[.13em] text-ink-3">
          excerpt · every value carries a why
        </span>
      </figcaption>

      <div className="font-data text-secondary leading-[1.7] py-2 overflow-x-auto">
        <Block tier={3}>
          <L k="- id: " v="star_align" />
          <L at={1} k="module:" />
          <L at={2} k="contract_id: " v="nf-core/star/align@1.11.0" />
          <L at={2} k="digest: " v="sha256:6591741c355858d7…" />
          <L at={1} k="why:" />
          <TierLine at={2} tier={3} />
          <L at={2} v="reason: rule producer_of:alignment.bam" />
          <L at={3} v="matched {read_length: '>= 70'} —" />
          <L at={3} v="Dobin et al. 2013, doi:10.1093/…" />
        </Block>

        <Block tier={4}>
          <L at={1} k="settings:" />
          <L at={1} k="- name: " v="seq_platform" />
          <L at={2} k="why:" />
          <TierLine at={3} tier={4} />
          <L at={3} v="reason: no rule covered 'seq_platform';" />
          <L at={3} v="selected the first of 1 candidates" />
          <L at={3} v="without judgement — please review" />
        </Block>
      </div>
    </figure>
  );
}
