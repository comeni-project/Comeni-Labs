# The inspection protocol

One inspection, one process. The caller writes a request to stdin and reads one report from
stdout.

## The request

One line of JSON, then each file's bytes back to back, in the order the request lists them.

| field | what it holds |
|---|---|
| `format` | the format piece: `id`, `version`, `path` (its entry file, absolute), `decided` |
| `codec` | the codec piece, or `null` for bytes that need no opening |
| `measures` | the measure pieces, each with its `decided` thresholds |
| `files` | one `{name, length}` per file; `length` is how many bytes follow for it |
| `cap_bytes` | the most any one file may unpack to |

A file whose bytes stop before its `length` is a broken request.

## The report

One line of JSON, keys sorted, `null` fields left out.

| field | what it holds |
|---|---|
| `type_id` | the type the format confirmed, filled by the caller from the format's `reads` |
| `facts` | by measure id: `by` (the pieces, `fastq@1.0.0` then the measure), either `value` or `undetermined` (a reason), `evidence`, and `coverage` |
| `unreadable` | why nothing could be measured, when nothing could |

Every fact's `evidence` carries `rows`, how many rows of records it read, and, when they apply:
`shorter_file` (one file of a pair ended first), `capped` (the head ended at `cap_bytes`) and
`stopped` (the format stopped at a malformed record: `malformed record 3: …`).

Every fact's `coverage` says how much of the data it read: `all` only when every file in the
request is marked `whole` and was read to its end, and `head` otherwise: a file capped, cut short
(a whole gzip that ends early also carries `truncated: true` in its evidence), stopped at a
malformed record, or left with an unread tail because its pair ended first. A `value` must be a
boolean, an integer, a finite number or a string; anything else makes the inspection unreadable. A request's `files` entry carries
`whole: true` only when the caller knows the payload is the entire file; the browser sends the
first 4 MB, so an upload is a head unless its real size says otherwise.

## The pipeline runner

`measure_cli.py` runs the same pieces over whole files, with no cap, in a pipeline step on a plain
Python image (#465). It imports the standard library and this package's stdlib modules only
(`core`, `outcome`, `records`, `stream`), takes every piece on its command line
(`--format id@version=path`, `--codec`, `--measure`, `--decided id=JSON`, or `--parser` for a
tool's output), and writes one report in the shape above to stdout, with exit status 0. A codec's
`open` is handed a byte stream, never the whole file in memory.

## Exit codes

`0` with a report on stdout. Anything else, or nothing within the caller's time limit, is
`unreadable` on the caller's side: an inspection never fails a conversation.

## Another implementation

An implementation in any language is valid if `comeni_inspect.harness` reproduces every golden
report byte for byte against it.
