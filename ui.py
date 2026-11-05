"""Shared UI copy and helpers used by both pages."""

from __future__ import annotations

import streamlit as st

CUSTOMIZE_TITLE = "Starting template: tailor before use"
CUSTOMIZE_BODY = (
    "This checklist is a starting point, not a finished assessment. Review each control "
    "against your environment, risk appetite and policies: remove what doesn't apply, add "
    "what's missing, assign owners and set testing frequencies. Framework references are "
    "indicative, so confirm them against the current standard before relying on them for "
    "audit or compliance."
)


def customization_note() -> None:
    """Persistent callout reminding users the output is a template to customise."""
    st.info(f"**{CUSTOMIZE_TITLE}**  \n{CUSTOMIZE_BODY}", icon=":material/edit_note:")


def customization_markdown() -> list[str]:
    """The same note as a Markdown blockquote for exported files."""
    return [f"> **{CUSTOMIZE_TITLE}.** {CUSTOMIZE_BODY}"]


def download_toast(label: str):
    """Return an on_click callback that confirms a download with a toast."""

    def _toast() -> None:
        st.toast(f"{label} downloaded", icon=":material/download_done:")

    return _toast
