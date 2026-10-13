"""The tool catalogue: one module per area, each exporting a ``TOOLS`` tuple of ``ToolSpec``.

Each area module is edited by the task that registers its tools, so those tasks touch disjoint
files. ``TOOLS`` is every area's tools; the registry orders them by name.
"""

from . import (
    approach,
    conclusion,
    configuration,
    evidence,
    housekeeping,
    model,
    orient,
    review,
    runs,
    study,
)

AREAS = (
    orient,
    study,
    approach,
    model,
    evidence,
    configuration,
    runs,
    conclusion,
    housekeeping,
    review,
)
TOOLS = tuple(tool for area in AREAS for tool in area.TOOLS)
