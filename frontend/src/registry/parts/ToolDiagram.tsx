import type { Pin, ToolShape } from "./toolShape";

function PinButton({ pin, focus, onPick }: { pin: Pin; focus?: string | null; onPick: (key: string) => void }) {
  return (
    <div className="pin">
      <button type="button" className="pin-box" data-decided={pin.type !== null}
              aria-pressed={focus === pin.key} onClick={() => onPick(pin.key)}>
        <span className="flex justify-between gap-2 font-data text-[13px]">
          <span className="truncate">{pin.name}</span>
          {pin.type !== null && <span aria-hidden="true" className="text-done-ink">✓</span>}
        </span>
        <span className="block truncate font-data text-[12px] text-ink-2">{pin.type ?? "not decided"}</span>
      </button>
    </div>
  );
}

/** The tool drawn: a block with its inputs on the left and outputs on the right, filling in as
 *  a person decides. Picking a pin goes to the item that decides it. */
export function ToolDiagram({ name, shape, focus, onPick }: {
  name: string;
  shape: ToolShape;
  focus?: string | null;
  onPick: (key: string) => void;
}) {
  return (
    <div className="tool" role="group" aria-label={`The tool so far: ${name}`}>
      <div className="tool-side">
        {shape.inputs.map((pin) => <PinButton key={pin.key} pin={pin} focus={focus} onPick={onPick} />)}
      </div>
      <button type="button" className="tool-block" aria-pressed={focus === "questions:role"}
              onClick={() => onPick("questions:role")}>
        <span className="font-data font-medium text-[15px]">{name}</span>
        <span className="text-[12px] text-ink-3">{shape.job ?? "job not decided"}</span>
      </button>
      <div className="tool-side tool-right">
        {shape.outputs.map((pin) => <PinButton key={pin.key} pin={pin} focus={focus} onPick={onPick} />)}
      </div>
    </div>
  );
}
