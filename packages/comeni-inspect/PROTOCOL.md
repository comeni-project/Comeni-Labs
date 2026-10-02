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
| `facts` | by measure id: `by` (the pieces, `fastq@1.0.0` then the measure), and either `value` or `undetermined` (a reason), with `evidence` |
| `unreadable` | why nothing could be measured, when nothing could |

## Exit codes

`0` with a report on stdout. Anything else, or nothing within the caller's time limit, is
`unreadable` on the caller's side: an inspection never fails a conversation.

## Another implementation

An implementation in any language is valid if `comeni_inspect.harness` reproduces every golden
report byte for byte against it.
