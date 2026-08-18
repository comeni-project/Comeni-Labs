import { isRouteErrorResponse, useRouteError } from "react-router";

/** One boundary for the whole tree.
 *
 * It shows what actually broke rather than a friendly nothing: a curator who hits an error
 * needs the string to send on, and the API's refusals are coded precisely so they can be
 * looked up with `forge explain`.
 */
export function ErrorBoundary() {
  const error = useRouteError();
  const message = isRouteErrorResponse(error)
    ? `${error.status} ${error.statusText}`
    : error instanceof Error
      ? error.message
      : String(error);

  return (
    <div className="p-6 max-w-[600px]">
      <h1 className="font-display text-title mb-4">Something broke</h1>
      <pre className="font-data text-body text-fault whitespace-pre-wrap">{message}</pre>
    </div>
  );
}
