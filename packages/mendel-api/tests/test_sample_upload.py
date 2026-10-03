"""Reading an upload's heads off the stream, when the stream itself goes wrong (issue 226)."""

import asyncio

import pytest
from mendel_api.services import sample_upload
from starlette.requests import ClientDisconnect

BOUNDARY = "b0undary"
START = (
    f"--{BOUNDARY}\r\nContent-Disposition: form-data; name=\"files\"; filename=\"a.fq\"\r\n\r\n"
    "@r\nA\n"
).encode()


class _Request:
    headers = {"content-type": f"multipart/form-data; boundary={BOUNDARY}"}

    def __init__(self, then):
        self.then = then

    async def stream(self):
        yield START
        await self.then()


def _read(then):
    return asyncio.run(sample_upload.read_heads(_Request(then), head=1024))


def test_a_client_that_goes_away_mid_body_is_a_refusal_not_a_crash():
    async def gone():
        raise ClientDisconnect()

    with pytest.raises(sample_upload.BadUpload, match="stopped"):
        _read(gone)


def test_a_body_that_stops_arriving_is_given_up_on(monkeypatch):
    monkeypatch.setattr(sample_upload, "READ_TIMEOUT_S", 0.05)

    async def stalls():
        await asyncio.sleep(5)

    with pytest.raises(sample_upload.BadUpload, match="stopped arriving"):
        _read(stalls)
