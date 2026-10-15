"""Generate the documentation stage badge from extra.stage in the MkDocs configuration."""

import json

STAGE_CSS = "assets/stage.css"


def stage_css(stage: str) -> str:
    """Return a CSS string token, keeping a stage label on one line."""
    if not isinstance(stage, str) or not stage.strip():
        raise ValueError("extra.stage must be a nonempty product-stage label")
    label = json.dumps(" ".join(stage.split()), ensure_ascii=False)
    return f":root {{ --comeni-stage: {label}; }}\n"


def on_config(config):
    stage_css(config["extra"].get("stage"))
    if STAGE_CSS not in config["extra_css"]:
        config["extra_css"].append(STAGE_CSS)
    return config


def on_files(files, config):
    from mkdocs.structure.files import File

    files.append(File.generated(config, STAGE_CSS, content=stage_css(config["extra"]["stage"])))
    return files
