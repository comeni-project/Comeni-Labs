# iframe-worker

`shim.js` is the unmodified iframe-worker 1.0.3 shim from
https://unpkg.com/iframe-worker@1.0.3/shim, distributed under the adjacent MIT license.
Upstream: https://github.com/squidfunk/iframe-worker.

MkDocs Material uses this shim for search when opening the built site through `file://`.
Keep the script local so offline search does not depend on a warm browser cache.
