"""Saved pipeline models, dependency fingerprints, and generated-file evidence.

pipeline.py defines and validates the artifact. materialise.py builds it from
a resolved plan and registry declarations. Digest, lockfile, and emitted-file
records track its inputs and outputs; gates.py names validation levels.

Import from the individual modules. The package initializer has no re-exports.
"""
