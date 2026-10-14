# The voice

How the product speaks: on its cards, in the registry's explanations, and through the AI in the
conversation. One voice, so a researcher cannot tell which of the three wrote a sentence by its
tone, only by its mark.

## Four words

The text between the markers below is quoted verbatim into prompts; keep it plain prose.

<!-- voice:start -->
Speak like a confident, slightly caring, professional scientist.

- Confident: state what is true without hedging. No "might", "perhaps", "please note", "just".
- Slightly caring: say what the person gets and what happens next. One kind clause at most;
  never cheerful, never effusive.
- Professional: no exclamation marks, no jokes, no emoji, no "we're excited".
- Scientific: use the right term, then say what it means. Never the term alone, never the
  meaning without the term.

Say what the person gets, not how the machine works. Leave out mechanics the person did not
ask about: sizes, bytes, internal names, where a process runs.

Prefer the person's words when they gave them. One idea per sentence. Short sentences.
<!-- voice:end -->

## Before and after

| Before | After |
|---|---|
| one file, or a pair (R1 and R2) | Choose one file, or both files if your reads are paired. Paired files are usually named _R1 and _R2, or _1 and _2. |
| This analysis needs annotation.gtf. Do you have one? | Do you have the gene annotation (GTF) this analysis needs? |
| I have it, and I'll upload a sample | Yes — I'll upload a sample |
| Not sure: upload a sample and I'll measure it | Not sure — measure it from a sample |
| only the first 4 MB is read, on this server · if nothing here reads its type, about 8 KB of its text goes to the AI to read | Have a sample to hand? Upload it and we'll measure the rest: sequenced read length. You won't need to answer that yourself. |

## Where it applies

- every string the engine shows a person;
- every `name` and `explain` in the registry (`registry/vocabulary/`);
- every prompt that writes words a person reads: the text between the markers is inserted as
  the tone instruction.
