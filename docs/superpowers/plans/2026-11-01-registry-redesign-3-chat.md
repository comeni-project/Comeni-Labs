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

- [ ] `useForgeEvents`: stream while the AI works, polling if it drops.
- [ ] One message shape with sender and time; progress ladder with tokens (#420, #430).
- [ ] What each reply changed, including nothing, from the commands it sent (#423).
- [ ] Proposals in words, decided in place.
- [ ] Resizable, pinned column; a sheet at phone width (#425).
- [ ] Side-by-side comparison with the Chat states, Review and Phone boards.
