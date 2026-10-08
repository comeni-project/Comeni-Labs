"""Outbound payload schemas and their declared boundaries.

Payloads are grouped by purpose. boundaries.py maps each named boundary to
its payload model and pipeline or forge flow. These models describe data;
callers implement transport and enforce access policy.

Import from the individual modules. The package initializer has no re-exports.
"""
