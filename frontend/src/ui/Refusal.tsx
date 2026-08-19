const CODE = /^([A-Z]{2}\d{4}):/;

/** A refusal, as the API sent it.
 *
 * The code is kept and the way to expand it is offered, because `forge explain <code>` is the
 * long form and a friendlier sentence would hide the one string that says what to do.
 */
export function Refusal({ message }: { message: string }) {
  const code = CODE.exec(message)?.[1];
  return (
    <div className="border-l-2 border-fault pl-4 py-1">
      <p className="text-body text-ink">{message}</p>
      {code && (
        <p className="text-secondary text-ink-3 mt-1">
          <span className="font-data">forge explain {code}</span> for the long form
        </p>
      )}
    </div>
  );
}
