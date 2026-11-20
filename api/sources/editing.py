"""Edits on the server: the snapshot of a module, with the stored edits replayed by `core`.

Light Mode stores edits in SQLite; here an edit is the plain dict of
`edits.py` plus the module it is stored under (`package`). The edited LinkML schema is the truth: graphs, roots,
usage and the LinkML download all read it. How edits replay, which module
owns an edit and the empty canvas are described in `core.py`; this module
finds the snapshots and keeps the legacy extraction path working.
"""
from __future__ import annotations

from collections.abc import Collection, Mapping, Sequence
from typing import Any

from ..light_mode.schema_source import SchemaProfile, schema_profile_for_package
from . import core
from . import edits as edit_ops
from . import graph
from .extraction import build_graph as extracted_graph
from .extraction import extraction_mode, get_usage_for_section
from .extraction import list_sections as extracted_sections
from .legacy import UnknownRoot
from .snapshots import get_snapshot, snapshot_yaml

SCRATCH_SUFFIX = core.SCRATCH_SUFFIX
Edited = core.Edited
is_scratch = core.is_scratch
snapshot_commit = core.snapshot_commit
with_stored = core.with_stored

EditError = edit_ops.EditError


class EditsUnavailable(RuntimeError):
    """The profile is on the legacy extraction path, which has no LinkML schema to edit."""


def rules_summary(profile: SchemaProfile) -> dict[str, Any]:
    return edit_ops.rules_summary(profile.edit_rules)


def editable(profile: SchemaProfile) -> bool:
    return extraction_mode(profile) == "linkml"


def _require_editable(profile: SchemaProfile) -> None:
    if not editable(profile):
        raise EditsUnavailable(
            f"Editing {profile.label} needs the LinkML extraction; SCHEMA_STUDIO_EXTRACTION selects legacy for it."
        )


def _snapshot(profile: SchemaProfile, package: str) -> dict[str, Any]:
    return get_snapshot(profile, core.snapshot_scope(profile, package))


def edited(
    package: str,
    stored: Sequence[Mapping[str, Any]] = (),
    *,
    base_namespace: str | None = None,
) -> Edited:
    """The module's snapshot (the whole profile's for the empty canvas) with the profile's edits replayed.

    Conflicts are the module's own; edits stored under other modules that do
    not apply here are left out without a report.
    """
    profile = schema_profile_for_package(package, base_namespace)
    _require_editable(profile)
    return core.edited(profile, _snapshot(profile, package), package, stored)


def _unsupported(stored: Sequence[Mapping[str, Any]], profile: SchemaProfile, package: str) -> list[dict[str, Any]]:
    detail = f"edits need the LinkML extraction, which SCHEMA_STUDIO_EXTRACTION turns off for {profile.label}"
    return [{"edit": edit, "reason": "unsupported", "detail": detail, "applied": False}
            for edit in stored if edit.get("package") in (None, package)]


def build_graph(
    package: str,
    stored: Sequence[Mapping[str, Any]] = (),
    *,
    root: str | None = None,
    include_quantities: bool = True,
    include_subsections: bool = True,
    include_inheritance: bool = True,
    allow_cross_module: bool = True,
    base_namespace: str | None = None,
    empty: bool = False,
    expand: Collection[str] = (),
) -> dict[str, Any]:
    """The module's graph from its edited schema, with `applied_edits` and `edit_conflicts` when there are any.

    `empty` starts the graph only from classes the edits added to the module.
    """
    profile = schema_profile_for_package(package, base_namespace)
    flags = {
        "root": root or None,
        "include_quantities": include_quantities,
        "include_subsections": include_subsections,
        "include_inheritance": include_inheritance,
        "allow_cross_module": allow_cross_module,
        "base_namespace": base_namespace,
    }
    if not editable(profile):
        if empty:
            result: dict[str, Any] = {"package": package, "root": root, "nodes": [], "edges": []}
        else:
            result = extracted_graph(package, **flags, expand=expand)
        conflicts: list[dict[str, Any]] = _unsupported(stored, profile, package)
        applied: list[Mapping[str, Any]] = []
    else:
        state = edited(package, stored, base_namespace=base_namespace)
        try:
            return core.build_graph(state, package, empty=empty, expand=expand, **{**flags, "root": root})
        except graph.RootNotFound as exc:
            raise UnknownRoot(f"ValueError: {exc}") from exc
    if applied:
        result["applied_edits"] = list(applied)
    if conflicts:
        result["edit_conflicts"] = conflicts
    return result


def list_sections(package: str, stored: Sequence[Mapping[str, Any]] = ()) -> list[str]:
    """The roots a module offers, edits included."""
    profile = schema_profile_for_package(package)
    if not editable(profile) or (not stored and not is_scratch(package)):
        return extracted_sections(package)
    state = edited(package, stored)
    return core.section_names(state, package)


def usage_for_section(section_id: str, package: str | None, stored: Sequence[Mapping[str, Any]] = ()) -> tuple:
    """Usage info of a section; a class an edit renamed keeps the usage of its source class."""
    if package and stored:
        profile = schema_profile_for_package(package)
        if editable(profile):
            source_id = core.usage_source(edited(package, stored), section_id)
            if source_id is None:
                return ()
            section_id = source_id
    return get_usage_for_section(section_id, package)


def prepare(
    package: str,
    stored: Sequence[Mapping[str, Any]],
    requests: Sequence[Mapping[str, Any]],
    *,
    base_namespace: str | None = None,
) -> list[dict[str, Any]]:
    """New edits (`op`, `target`, `payload`), checked in order on top of the stored ones; raises `EditError`.

    All of them apply or none: an error in one leaves nothing to store. Each
    edit gets the module it is to be stored under (`package`).
    """
    state = edited(package, stored, base_namespace=base_namespace)
    return core.prepare(state, package, requests)


def root_after(
    package: str,
    stored: Sequence[Mapping[str, Any]],
    prepared: Sequence[Mapping[str, Any]],
    root: str | None,
    *,
    base_namespace: str | None = None,
) -> str | None:
    """The root a graph can use once new edits apply: renamed with its class, or none when the class is gone."""
    if not root:
        return root
    state = edited(package, stored, base_namespace=base_namespace)
    return core.root_after(state, package, prepared, root)


def linkml_yaml(package: str, stored: Sequence[Mapping[str, Any]] = ()) -> str:
    """The module's LinkML schema as YAML, with the stored edits replayed onto it.

    Without edits, or on the legacy extraction path (which has nothing to
    edit), it is the snapshot's schema as converted.
    """
    profile = schema_profile_for_package(package)
    if not stored or not editable(profile):
        return snapshot_yaml(_snapshot(profile, package))
    return core.edited_yaml(edited(package, stored))


__all__ = [
    "Edited", "EditError", "EditsUnavailable", "SCRATCH_SUFFIX", "build_graph", "edited", "editable",
    "is_scratch", "linkml_yaml", "list_sections", "prepare", "root_after", "rules_summary", "snapshot_commit",
    "usage_for_section", "with_stored",
]
