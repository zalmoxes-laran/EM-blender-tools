"""Thin shared UI helpers used across EM-Tools panels.

Keeps the visual language of checklist-style panels (Proxy Box,
Surface Areas, and similar) consistent: same icons for met/unmet
requirements, same indentation for hints, same disabled styling for
"you can't act until the previous step is done" rows.

Usage::

    from .ui_helpers import draw_requirement_row

    box = draw_requirement_row(
        layout, number=1, label="Anchor Document",
        ok=bool(settings.document_node_id),
        hint="Pick a document from the catalog or from the selected mesh.",
    )
    # add fields inside ``box`` as needed
    box.prop(settings, "document_node_name", text="")

Every consumer should funnel through this helper so the checklist UX
stays uniform even when new panels appear.
"""

from __future__ import annotations

from typing import Optional


def draw_requirement_row(
    layout,
    number: int,
    label: str,
    ok: bool,
    *,
    hint: Optional[str] = None,
    hint_icon: str = 'INFO',
    ok_icon: str = 'CHECKMARK',
    unmet_icon: str = 'X',
    inactive: bool = False,
):
    """Draw a checklist requirement row inside a boxed container.

    Args:
        layout:       parent Blender ``UILayout``.
        number:       step number printed as ``"N. label"``.
        label:        user-visible requirement name.
        ok:           whether the requirement is satisfied.
        hint:         optional one-liner shown dimmed below the row
                      when the requirement is *not* met. Skip when
                      ``None``.
        hint_icon:    icon for the hint row (default ``INFO``).
        ok_icon:      icon shown to the left of the label when met.
        unmet_icon:   icon shown to the left of the label when
                      unmet. When ``inactive`` is ``True`` the icon is
                      forced to ``BLANK1`` so the row reads as
                      "waiting for earlier steps" rather than "wrong".
        inactive:     caller signals that this step can't be evaluated
                      yet because an earlier step is still unmet.
                      The row is rendered dimmed with a blank icon.

    Returns:
        the boxed ``UILayout`` container so the caller can drop
        widgets (props, operators) directly inside it without
        re-boxing. Returned even when unmet/inactive so the layout
        tree stays deterministic.
    """
    box = layout.box()
    row = box.row()
    if inactive:
        row.enabled = False
        status_icon = 'BLANK1'
    else:
        status_icon = ok_icon if ok else unmet_icon
    row.label(text=f"{number}. {label}", icon=status_icon)
    if hint and not ok and not inactive:
        hint_row = box.row()
        hint_row.enabled = False
        hint_row.label(text=hint, icon=hint_icon)
    return box
