"""Every setting this installation has, by section (spec §7).

**Each section arrived with its consumer.** Appearance came first (the theme, read by
`frontend/src/app/Shell.tsx`); Models and Privacy & data with 14.7.5.4, which made every model
call read its purpose's model. Building arrived with 14.7.5.5, declared `Designed` until the
consultant build (14.7.8) reads it; the read-only ones arrive in 14.7.5.6.
"""

from comeni_core.settings.declare import FROM_ENV, EnvItem, Setting, Where
from comeni_core.settings.reasons import Designed, ReadOnlyHere
from comeni_core.settings.sections import Catalogue, Section

THEME = Setting.choice(
    key="appearance.theme",
    label="Theme",
    help=(
        "Light or dark. Kept by this browser, so another browser or another person keeps "
        "their own. Match the system follows your operating system's setting."
    ),
    options=[("system", "Match the system"), ("light", "Light"), ("dark", "Dark")],
    default="system",
    where=Where.BROWSER,
)

APPEARANCE = Section(key="appearance", title="Appearance", order=1, settings=(THEME,))

CONSULTANT = "arrives with the consultant build (14.7.8)"

PACING = Setting.choice(
    key="building.pacing",
    label="Pacing",
    help=(
        "How the build walks you through its steps: together, step by step, or set up at once "
        "and stopping only where it needs you. Ask me every time asks at the start of each build."
    ),
    options=[
        ("together", "Go through it together"),
        ("stop_where_needed", "Set it up, stop only where you need me"),
        ("ask", "Ask me every time"),
    ],
    default="ask",
    env="COMENI_BUILD_PACING",
    unavailable=Designed(where=CONSULTANT),
)

TIER4_ANSWERS = Setting.choice(
    key="building.tier4",
    label="Choices no rule settles",
    help=(
        "What happens at a tier-4 choice, where no rule decides. In the consultant build it "
        "always stops for you; letting a model propose the answer, always flagged as a model's, "
        "is designed."
    ),
    options=[("stop", "Always stop for me"), ("model", "Let a model answer, flagged")],
    default="stop",
    env="COMENI_BUILD_TIER4",
    unavailable=Designed(where="letting a model answer comes after the consultant build"),
)

BUILDING = Section(key="building", title="Building", order=2, settings=(PACING, TIER4_ANSWERS))

CONNECTIONS = Setting.collection(
    key="models.connections",
    label="Connections",
    help=(
        "Where models are reached: a model server on this machine or your network, or a "
        "provider with a key. Add one, test it, then choose a model for each purpose below."
    ),
    fields=(
        Setting.text(
            key="connection.name", label="Name",
            help="What this connection is called here, e.g. Local Ollama.",
        ),
        Setting.choice(
            key="connection.server", label="Server",
            help="What answers at the endpoint. It decides how model ids are written.",
            options=[
                ("ollama", "Ollama"),
                ("openai_compatible", "Another OpenAI-compatible server (vLLM, LM Studio)"),
                ("hosted", "A hosted provider"),
            ],
            default="ollama",
        ),
        Setting.text(
            key="connection.endpoint", label="Endpoint",
            help="The server's address, e.g. http://ollama:11434. Empty for a hosted provider.",
        ),
        Setting.secret(
            key="connection.key", label="Key",
            help="The provider's API key. Stored sealed; shown only as its last four characters.",
        ),
    ),
    from_env=EnvItem(
        name=FROM_ENV,
        present_when="COMENI_AI_MODEL",
        fields={"endpoint": "COMENI_AI_BASE_URL", "key": "COMENI_AI_API_KEY"},
    ),
    actions=("test", "models"),
)


def _purpose(name: str, label: str, help: str) -> Setting:
    return Setting.model(
        key=f"models.{name}", label=label, help=help, of="models.connections",
        env=f"COMENI_AI_MODEL_{name.upper()}",
    )


DEFAULT_MODEL = Setting.model(
    key="models.default",
    label="Default model",
    help=(
        "The model every purpose uses unless it names its own. COMENI_AI_MODEL in .env sets "
        "it, through the From .env connection."
    ),
    of="models.connections",
    env="COMENI_AI_MODEL",
)
MODEL_WANT = _purpose(
    "want", "Understanding what you want",
    "Reads what you asked for and picks what it should produce. The call most worth a strong "
    "model.",
)
MODEL_TALK = _purpose(
    "talk", "Talking with you",
    "Phrases the questions the build asks you and reads your replies. A small model is enough.",
)
MODEL_TIER4 = _purpose(
    "tier4", "Choosing where the rules cannot",
    "Proposes an answer to a choice no rule settles (tier 4). Always shown to you as a model's.",
)
MODEL_READBACK = _purpose(
    "readback", "Reading the plan back",
    "Says back, in a sentence, what the pipeline will do, so you can check it was understood.",
)
MODEL_FORGE = _purpose(
    "forge", "Adapting tools",
    "Drafts a new tool's contract in the registry's workshop, for a person to review.",
)
PURPOSE_SETTINGS = (MODEL_WANT, MODEL_TALK, MODEL_TIER4, MODEL_READBACK, MODEL_FORGE)

WHERE_PURPOSES = Setting.readonly(
    key="privacy.where",
    label="Where each purpose goes",
    help=(
        "For each purpose, whether what it sends stays on this machine or your network, or "
        "goes to a provider. Worked out from the connection each purpose uses."
    ),
    unavailable=ReadOnlyHere(why="worked out from Settings → Models"),
)

MODELS = Section(
    key="models", title="Models", order=3,
    settings=(CONNECTIONS, DEFAULT_MODEL, *PURPOSE_SETTINGS),
)

RO = ReadOnlyHere(why="reported by the server; not changed here")

PROTECTION = Setting.choice(
    key="privacy.protection",
    label="Protection level",
    help=(
        "How much of your data a model may see. Level 0 lets a model read an uploaded sample. "
        "Open, guarded and sealed send less, down to nothing at all."
    ),
    options=[
        ("level_0", "Level 0: a model may read an uploaded sample"),
        ("open", "Open"),
        ("guarded", "Guarded"),
        ("sealed", "Sealed"),
    ],
    default="level_0",
    unavailable=Designed(
        where="level 0 arrives with samples (14.7.6); open, guarded and sealed are designed "
        "(issue 71)"
    ),
)


def _reported(key: str, label: str, help: str, why: ReadOnlyHere = RO) -> Setting:
    return Setting.readonly(key=key, label=label, help=help, unavailable=why)


REGISTRY_ROOT = _reported(
    "registry.root", "Registry",
    "The folder the tools and types are read from. Set as MENDEL_REGISTRY_ROOT in .env.",
)
REGISTRY_LAYERS = _reported(
    "registry.layers", "Layers",
    "Each layer stacked on the registry, in order. A later layer can replace an earlier "
    "one's tool.",
)
GITHUB_TOKEN = _reported(
    "registry.github", "GitHub token",
    "Lets the forge read nf-core's catalogue without GitHub's anonymous rate limit. Set or not.",
    ReadOnlyHere(why="a deploy secret: set it as COMENI_FORGE_GITHUB_TOKEN in .env"),
)
DOCKERHUB = _reported(
    "registry.dockerhub", "Docker Hub account",
    "Lets the forge read all of pegi3s's images, not only the first hundred. Set or not.",
    ReadOnlyHere(why="a deploy secret: set COMENI_FORGE_DOCKERHUB_USER and _TOKEN in .env"),
)
SOURCE_CHECK = _reported(
    "registry.source_check", "Nightly source check",
    "When the worker re-reads every source to see whether an upstream tool moved.",
)
VERSIONS = _reported(
    "system.versions", "Versions", "The version of each part of this installation."
)
DATABASE = _reported("system.database", "Database", "Whether Mendel's database answers.")
REDIS = _reported("system.redis", "Job queue", "Whether the queue that runs model jobs answers.")
MODEL_SERVER = _reported(
    "system.model", "Default model's server",
    "Whether anything answers at the default model's endpoint. A hosted provider is not probed.",
)

PRIVACY = Section(
    key="privacy", title="Privacy & data", order=4, settings=(PROTECTION, WHERE_PURPOSES)
)
REGISTRY = Section(
    key="registry", title="Registry & sources", order=6,
    settings=(REGISTRY_ROOT, REGISTRY_LAYERS, GITHUB_TOKEN, DOCKERHUB, SOURCE_CHECK),
)
SYSTEM = Section(
    key="system", title="System", order=7, settings=(VERSIONS, DATABASE, REDIS, MODEL_SERVER)
)

CATALOGUE = Catalogue(sections=(APPEARANCE, BUILDING, MODELS, PRIVACY, REGISTRY, SYSTEM))
