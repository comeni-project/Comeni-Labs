"""Every setting this installation has, by section (spec §7).

**One section to start**, Appearance, because it is the one whose consumer exists today: the
theme toggle in `frontend/src/app/Shell.tsx`. Each later part adds the section it builds —
Models in 14.7.5.4, Building in 14.7.5.5, the read-only ones in 14.7.5.6.
"""

from comeni_core.settings.declare import Setting, Where
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

CATALOGUE = Catalogue(sections=(APPEARANCE,))
