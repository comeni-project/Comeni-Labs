# Registry redesign, slice 3: chat and progress

**Spec:** [slice 3 and D3](../specs/2026-10-31-registry-redesign-design.md). **Issues:** #420, #423,
#425, #430. **Branch:** `registry-redesign-3-chat`. **Size:** M to L.

## Server

- [x] Forge calls record their tokens (#420).
- [x] `forge_step`: each step, attempt, refusal and call total, in order.
- [x] `draft_piece` and `answer_message` write them.
- [x] Refusals are sentences, with the detail kept apart; a refused draft is resolved once its piece
      has items (#430).
- [x] `GET .../events` reads the record, `GET .../events/stream` pushes what is new.

## Page

- [x] `useForgeSteps` (the table is `forge_step`, so the hook takes its name): stream while the AI works, polling if it drops.
- [x] One message shape with sender and time; progress ladder with tokens (#420, #430).
- [x] What each reply changed, including nothing, from the commands it sent (#423).
- [x] Proposals in words, decided in place.
- [x] Resizable, pinned column; a sheet at phone width (#425).
- [x] Side-by-side comparison with the Chat states, Review and Phone boards.

Deviations, found side by side with the boards:

- The tool diagram moved into the left column beside the chat, as the Review board has it; slice 1 had
  it full width, which pushed the composer below the fold.
- The boards' "The reviewer reads it" step waits for the reviewer, slice 4.
- Proposals say Accept, Change, Decline as Chat states does; item rows keep Approve and Reject until
  their own pages are rebuilt, in slice 6. Change only points the chat at the item: slice 5 adds the form.
- Checked with fixture states through a local proxy, because no model was running: working, refused
  and proposal at 1440 and 390, dark, and refused at 1440, light. The stream route answered on the real
  stack with nothing working. A real draft has not yet been watched live; the walk does that.
