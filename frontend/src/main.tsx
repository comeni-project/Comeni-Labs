import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

import "./main.css";
import { Shell } from "./app/Shell";

const client = new QueryClient();

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <QueryClientProvider client={client}>
      <Shell>
        {/* the queue lands in Task 7 */}
        <div />
      </Shell>
    </QueryClientProvider>
  </StrictMode>,
);
