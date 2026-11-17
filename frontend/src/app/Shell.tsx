import { useEffect } from "react";
import { Outlet } from "react-router";

import { Rail } from "./rail/Rail";
import { RailProvider } from "./rail/RailContext";
import { painted, useTheme } from "./useTheme";

/** The frame every page sits in: the one rail (#511) beside the page. */
export function Shell() {
  const [theme] = useTheme();
  useEffect(() => {
    document.documentElement.dataset.theme = painted(theme);
  }, [theme]);

  return (
    <RailProvider>
      <div className="flex h-dvh bg-paper">
        <Rail />
        <main className="flex-1 min-w-0 h-dvh grid grid-rows-[minmax(0,1fr)] overflow-hidden">
          <Outlet />
        </main>
      </div>
    </RailProvider>
  );
}
