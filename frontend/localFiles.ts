import { execFile } from "node:child_process";
import { realpath, stat } from "node:fs/promises";
import { dirname, isAbsolute, join, relative, sep } from "node:path";
import { pathToFileURL } from "node:url";
import { promisify } from "node:util";
import type { Plugin } from "vite";

const execute = promisify(execFile);

/** Desktop integration belongs on the local host, outside the API containers. */
export function localFiles(root: string): Plugin {
  return { name: "local-output-files", configureServer(server) {
    server.middlewares.use("/api/local/reveal", async (request, response) => {
      const reply = (status: number, body: object) => {
        response.statusCode = status;
        response.setHeader("Content-Type", "application/json");
        response.end(JSON.stringify(body));
      };
      // This action opens a desktop window: accept only the local app's own browser origin.
      const hostname = new URL(`http://${request.headers.host ?? "invalid"}`).hostname;
      const expected = `http://${request.headers.host}`;
      if (!["127.0.0.1", "localhost", "[::1]"].includes(hostname)
        || request.headers.origin !== expected) {
        reply(403, { detail: "Open this action from the local Comeni app." }); return;
      }
      if (request.method !== "POST") { reply(405, { detail: "Use POST." }); return; }
      try {
        let body = "";
        for await (const chunk of request) {
          body += chunk;
          if (body.length > 8192) { reply(413, { detail: "Request too large." }); return; }
        }
        const { run, process: processName, name } = JSON.parse(body);
        if (typeof run !== "string" || !/^[a-f0-9]{32}$/.test(run)
          || typeof processName !== "string" || !/^[A-Za-z0-9_.-]+$/.test(processName)
          || processName === "." || processName === ".."
          || typeof name !== "string" || !name || isAbsolute(name) || name.includes("\\")
          || name.split("/").some((part: string) => part === ".." || part === ".")) {
          reply(400, { detail: "Choose a file from this run’s outputs." }); return;
        }
        const runRoot = await realpath(join(root, ".run/wiener/work", run));
        const file = join(runRoot, "results", processName, name);
        const resolved = await realpath(file);
        const inside = relative(runRoot, resolved);
        if (!inside || inside === ".." || inside.startsWith(`..${sep}`) || isAbsolute(inside)) {
          reply(403, { detail: "This file is outside the run’s working folder." }); return;
        }
        await stat(file);
        if (process.platform === "darwin") {
          await execute("open", ["-R", file], { timeout: 5000 });
          reply(200, { revealed: "file" }); return;
        }
        if (process.platform === "win32") {
          await execute("explorer.exe", [`/select,${file}`], { timeout: 5000 });
          reply(200, { revealed: "file" }); return;
        }
        try {
          await execute("gdbus", ["call", "--session", "--dest", "org.freedesktop.FileManager1",
            "--object-path", "/org/freedesktop/FileManager1", "--method", "org.freedesktop.FileManager1.ShowItems",
            `[${JSON.stringify(pathToFileURL(file).href)}]`, ""], { timeout: 5000 });
          reply(200, { revealed: "file" });
        } catch {
          await execute("xdg-open", [dirname(file)], { timeout: 5000 });
          reply(200, { revealed: "folder" });
        }
      } catch (error) {
        const code = (error as NodeJS.ErrnoException).code;
        reply(code === "ENOENT" ? 404 : 503, { detail: code === "ENOENT"
          ? "The local output file or file manager could not be found."
          : "The desktop file manager could not be opened. Use Copy path to locate the file." });
      }
    });
  } };
}
