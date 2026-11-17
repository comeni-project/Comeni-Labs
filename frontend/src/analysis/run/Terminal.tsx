import { FitAddon } from "@xterm/addon-fit";
import { Terminal as XTerm, type ITheme } from "@xterm/xterm";
import "@xterm/xterm/css/xterm.css";
import { forwardRef, useEffect, useImperativeHandle, useRef, useState } from "react";

/** What a page can do with a terminal: type into it, run a line, and read its last lines. */
export type TerminalHandle = {
  insert: (text: string) => void;
  run: (text: string) => void;
  /** The last `lines` of what it shows, as text: for the assistant. */
  tail: (lines?: number) => string;
  focus: () => void;
  /** Draw a note in the terminal without sending it: what the assistant ran, and its output. */
  note: (text: string) => void;
};

/** The terminal's colours from the theme's tokens (#511): the app's surface and ink, and colour
 *  only for meaning — green done, orange errors, amber warnings, blue live. */
function themeOf(): ITheme {
  const css = getComputedStyle(document.documentElement);
  const v = (name: string) => css.getPropertyValue(name).trim();
  return {
    background: v("--surface"),
    foreground: v("--ink-2"),
    cursor: v("--now-mid"),
    cursorAccent: v("--surface"),
    selectionBackground: v("--now-soft"),
    black: v("--ink"), brightBlack: v("--ink-3"),
    red: v("--needs-you-ink"), brightRed: v("--needs-you"),
    green: v("--done-ink"), brightGreen: v("--done"),
    yellow: v("--measured-ink"), brightYellow: v("--measured"),
    blue: v("--now-ink"), brightBlue: v("--now"),
    magenta: v("--ai"), brightMagenta: v("--ai"),
    cyan: v("--now-ink"), brightCyan: v("--now"),
    white: v("--ink-3"), brightWhite: v("--ink"),
  };
}

/** A terminal on a run's WebSocket (`wiener-term`): the bytes it sends are drawn, and, when
 *  `interactive`, what is typed is sent back — a shell. The socket is opened on mount and closed on
 *  unmount; `key` a new one to start again. */
export const Terminal = forwardRef<TerminalHandle, {
  path: string;
  interactive?: boolean;
  label: string;
  onState?: (state: "connecting" | "open" | "closed") => void;
}>(function Terminal({ path, interactive = false, label, onState }, ref) {
  const box = useRef<HTMLDivElement>(null);
  const term = useRef<XTerm | null>(null);
  const socket = useRef<WebSocket | null>(null);
  const [, setOpen] = useState(false);

  useImperativeHandle(ref, () => ({
    insert: (text) => { socket.current?.send(JSON.stringify({ type: "input", data: text })); term.current?.focus(); },
    run: (text) => { socket.current?.send(JSON.stringify({ type: "input", data: `${text}\r` })); term.current?.focus(); },
    tail: (lines = 120) => {
      const buffer = term.current?.buffer.active;
      if (!buffer) return "";
      const out: string[] = [];
      for (let i = Math.max(0, buffer.length - lines); i < buffer.length; i += 1) {
        out.push(buffer.getLine(i)?.translateToString(true) ?? "");
      }
      return out.join("\n").replace(/\n+$/, "");
    },
    focus: () => term.current?.focus(),
    note: (text) => term.current?.write(`\r\n${text.replaceAll("\n", "\r\n")}\r\n`),
  }), []);

  useEffect(() => {
    if (!box.current) return;
    const xterm = new XTerm({
      theme: themeOf(), fontFamily: "'JetBrains Mono Variable', 'JetBrains Mono', ui-monospace, monospace",
      fontSize: 12.5, lineHeight: 1.35, cursorBlink: interactive, disableStdin: !interactive,
      convertEol: !interactive, scrollback: 20000, allowProposedApi: false,
    });
    const fit = new FitAddon();
    xterm.loadAddon(fit);
    xterm.open(box.current);
    term.current = xterm;
    const fitNow = () => { try { fit.fit(); } catch { /* not laid out yet */ } };
    fitNow();

    const url = new URL(path, window.location.href);
    url.protocol = url.protocol === "https:" ? "wss:" : "ws:";
    onState?.("connecting");
    const ws = new WebSocket(url.toString());
    ws.binaryType = "arraybuffer";
    socket.current = ws;
    const resize = () => {
      fitNow();
      if (interactive && ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({ type: "resize", cols: xterm.cols, rows: xterm.rows }));
      }
    };
    ws.onopen = () => { setOpen(true); onState?.("open"); resize(); };
    ws.onclose = () => { setOpen(false); onState?.("closed"); };
    ws.onmessage = (message) => {
      xterm.write(typeof message.data === "string" ? message.data : new Uint8Array(message.data as ArrayBuffer));
    };
    const typed = interactive ? xterm.onData((data) => ws.send(JSON.stringify({ type: "input", data }))) : null;
    const watch = new ResizeObserver(resize);
    watch.observe(box.current);
    // The theme follows the app's: re-read the tokens when it changes.
    const themed = new MutationObserver(() => { xterm.options.theme = themeOf(); });
    themed.observe(document.documentElement, { attributes: true, attributeFilter: ["data-theme", "class"] });
    return () => {
      typed?.dispose();
      watch.disconnect();
      themed.disconnect();
      ws.close();
      xterm.dispose();
      term.current = null;
      socket.current = null;
    };
  }, [path, interactive]); // eslint-disable-line react-hooks/exhaustive-deps

  return <div ref={box} role="region" aria-label={label} className="flex-1 min-h-0 px-3 py-2 overflow-hidden" />;
});
