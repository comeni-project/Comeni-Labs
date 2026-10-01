"""A secret typed into the settings menu never leaves through the API (spec §8, §9).

**Every response the settings routes can give is searched for the plaintext**, after the secret
is stored through the real Fernet codec. The leak this refuses is a serializer that dumps the
resolved value: one line, and the most likely way a key would reach a browser.
"""

from comeni_core.settings import Catalogue, Installation, Section, Setting
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient
from mendel_api.main import create_app
from mendel_api.services.installation import installation
from mendel_api.services.settings_codec import FernetCodec

PLAIN = "sk-guard-0123456789"
HELP = "The key a provider asks for. Stored sealed, and shown only as its last four."
KEY = Setting.secret(key="models.key", label="Key", help=HELP)
CATALOGUE = Catalogue(sections=(Section(key="models", title="Models", order=1, settings=(KEY,)),))


class MemoryStore:
    def __init__(self):
        self.rows = {}

    def values(self):
        return dict(self.rows)

    def put(self, key, value, by):
        self.rows[key] = value


def _client(store):
    codec = FernetCodec(Fernet.generate_key().decode())
    app = create_app()
    app.dependency_overrides[installation] = lambda: Installation(CATALOGUE, store, {}, codec)
    return TestClient(app)


def test_no_settings_response_and_no_stored_row_holds_the_plaintext():
    store = MemoryStore()
    client = _client(store)
    answers = [
        client.put("/api/settings/models.key", json={"value": PLAIN}),
        client.get("/api/settings"),
        client.put("/api/settings/models.key", json={"value": PLAIN + "x"}),
    ]
    assert answers, "nothing was asked — this guard is measuring nothing"
    for answer in answers:
        assert answer.status_code == 200, answer.text
        assert PLAIN not in answer.text, f"{answer.request.method} leaked the secret"
    assert all(PLAIN not in str(value) for value in store.rows.values()), "stored unsealed"
