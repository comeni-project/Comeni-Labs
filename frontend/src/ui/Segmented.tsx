/** Two or more views of one thing (Graph | Timeline, By pipeline | By run): pressed buttons in
 *  the shared `.seg` well. */
export function Segmented<const T extends string>({ options, value, onChange, label }: {
  options: { id: T; label: string }[];
  value: T;
  onChange: (id: T) => void;
  label: string;
}) {
  return (
    <div role="group" aria-label={label} className="seg">
      {options.map((option) => (
        <button key={option.id} type="button" className="seg-item" aria-pressed={option.id === value}
                onClick={() => onChange(option.id)}>
          {option.label}
        </button>
      ))}
    </div>
  );
}
