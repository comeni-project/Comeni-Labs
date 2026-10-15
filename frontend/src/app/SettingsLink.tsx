import { Navigate, useParams } from "react-router";

/** An old `/settings/<section>` link, sent to the overlay over the front door. */
export function SettingsLink() {
  const { section } = useParams();
  return <Navigate to={`/?settings=${section ?? ""}`} replace />;
}
