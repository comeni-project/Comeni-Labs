import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

import "./main.css";
import { Shell } from "./app/Shell";
import { Queue } from "./forge/Queue";

const client = new QueryClient();

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <QueryClientProvider client={client}>
      <Shell>
        <Queue />
      </Shell>
    </QueryClientProvider>
  </StrictMode>,
);
