"""Template builder page: combine JSON templates into a trackable project checklist."""

from __future__ import annotations

import io
import json
import re
from datetime import date, timedelta
from pathlib import Path

import pandas as pd
import streamlit as st

import ui

DATA_DIR = Path(__file__).parent / "data"
SEVERITIES = ["High", "Medium", "Low"]
SIZES = ["Small", "Medium", "Large"]
# Default due date for each item, in days after the project start date.
DUE_OFFSETS = {"High": 7, "Medium": 21, "Low": 45}
COLUMNS = [
    "Done", "ID", "Template", "Section", "Item", "Severity",
    "Guidance", "Owner", "Due date", "Notes",
]
READ_ONLY_COLUMNS = ["ID", "Template", "Section", "Item", "Severity", "Guidance"]

# --------------------------------------------------------------------------- #
# Data
# --------------------------------------------------------------------------- #
@st.cache_data
def load_templates() -> dict[str, dict]:
    """Load every JSON template in data/, keyed by template name."""
    templates = {}
    for path in sorted(DATA_DIR.glob("*.json")):
        with path.open(encoding="utf-8") as f:
            template = json.load(f)
        templates[template["name"]] = template
    return templates


def count_items(template: dict) -> int:
    return sum(len(section["items"]) for section in template["sections"])


def build_checklist(
    templates: dict[str, dict],
    selected: list[str],
    size: str,
    severities: list[str],
    owner: str,
    start: date,
    custom_items: list[str],
) -> pd.DataFrame:
    """Flatten the selected templates into one checklist table."""
    max_size = SIZES.index(size)
    rows = []
    for name in selected:
        for section in templates[name]["sections"]:
            for item in section["items"]:
                if SIZES.index(item.get("min_size", "Small")) > max_size:
                    continue
                if item["severity"] not in severities:
                    continue
                rows.append({
                    "Done": False,
                    "ID": item["id"],
                    "Template": name,
                    "Section": section["name"],
                    "Item": item["text"],
                    "Severity": item["severity"],
                    "Guidance": item.get("guidance", ""),
                    "Owner": owner,
                    "Due date": start + timedelta(days=DUE_OFFSETS[item["severity"]]),
                    "Notes": "",
                })
    for i, text in enumerate(custom_items, start=1):
        rows.append({
            "Done": False,
            "ID": f"CUS-{i:02d}",
            "Template": "Custom",
            "Section": "Custom items",
            "Item": text,
            "Severity": "Medium",
            "Guidance": "",
            "Owner": owner,
            "Due date": start + timedelta(days=DUE_OFFSETS["Medium"]),
            "Notes": "",
        })
    return pd.DataFrame(rows, columns=COLUMNS)


# --------------------------------------------------------------------------- #
# Exports
# --------------------------------------------------------------------------- #
def slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-") or "checklist"


def to_excel(df: pd.DataFrame) -> bytes:
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Checklist")
        sheet = writer.sheets["Checklist"]
        for column_cells in sheet.columns:
            width = max(len(str(cell.value or "")) for cell in column_cells)
            sheet.column_dimensions[column_cells[0].column_letter].width = min(width + 2, 60)
        sheet.freeze_panes = "A2"
    return buffer.getvalue()


def to_markdown(df: pd.DataFrame, project: str) -> str:
    lines = [
        f"# {project}: Risk Checklist",
        "",
        f"_Generated {date.today():%d %B %Y}_",
        "",
        *ui.customization_markdown(),
    ]
    for (template, section), group in df.groupby(["Template", "Section"], sort=False):
        lines += ["", f"## {template} / {section}", ""]
        for row in group.to_dict("records"):
            box = "x" if row["Done"] else " "
            meta = [row["Severity"]]
            if row["Owner"]:
                meta.append(f"owner: {row['Owner']}")
            if pd.notna(row["Due date"]):
                meta.append(f"due: {row['Due date']}")
            lines.append(f"- [{box}] **{row['ID']}** {row['Item']} ({', '.join(meta)})")
            if row["Notes"]:
                lines.append(f"  - Notes: {row['Notes']}")
    return "\n".join(lines) + "\n"


# --------------------------------------------------------------------------- #
# Views
# --------------------------------------------------------------------------- #
def render_sidebar(templates: dict[str, dict]) -> None:
    with st.sidebar:
        st.header("Checklist settings")
        with st.form("settings", border=False):
            st.subheader("Project", divider="gray")
            project = st.text_input("Project name", value="New project")
            owner = st.text_input("Default owner", placeholder="e.g. Risk lead")
            start = st.date_input("Start date", value=date.today(), format="YYYY-MM-DD")

            st.subheader("Scope", divider="gray")
            selected = st.multiselect(
                "Risk templates",
                options=list(templates),
                default=list(templates)[:1],
                help="Combine as many templates as the project needs.",
            )
            size = st.select_slider(
                "Project size",
                options=SIZES,
                value="Medium",
                help="Larger projects include additional, more rigorous controls.",
            )
            severities = st.multiselect(
                "Severity levels", options=SEVERITIES, default=SEVERITIES
            )
            custom = st.text_area(
                "Custom items",
                placeholder="One item per line",
                help="Added to the checklist with Medium severity.",
            )
            submitted = st.form_submit_button(
                "Generate checklist", type="primary", width="stretch"
            )

        st.subheader("Display", divider="gray")
        st.toggle("Show guidance", value=True, key="show_guidance")

    if not submitted:
        return
    custom_items = [line.strip() for line in custom.splitlines() if line.strip()]
    if not selected and not custom_items:
        st.sidebar.warning("Select at least one template or add a custom item.")
        return
    checklist = build_checklist(
        templates, selected, size, severities, owner.strip(), start, custom_items
    )
    if checklist.empty:
        st.sidebar.warning("No items match these settings. Try widening the filters.")
        return
    st.session_state.checklist = checklist
    st.session_state.project = project.strip() or "Untitled project"
    # A new key resets the editor so edits from a previous checklist don't carry over.
    st.session_state.version = st.session_state.get("version", 0) + 1
    st.session_state.just_generated = True


def render_overview(templates: dict[str, dict]) -> None:
    st.info(
        "Choose templates and settings in the sidebar, then select **Generate checklist**.",
        icon=":material/arrow_back:",
    )
    st.subheader("Available templates")
    columns = st.columns(3)
    for i, template in enumerate(templates.values()):
        with columns[i % 3].container(border=True, height="stretch"):
            st.markdown(f"**{template['name']}**")
            st.write(template["description"])
            st.caption(
                f"{count_items(template)} items · {len(template['sections'])} sections"
            )


def render_checklist() -> None:
    base = st.session_state.checklist
    project = st.session_state.project

    if st.session_state.pop("just_generated", False):
        st.success(
            f"Checklist generated: {len(base)} items ready to track.",
            icon=":material/check_circle:",
        )
    st.subheader(project)
    metrics = st.container()
    ui.customization_note()

    tab_checklist, tab_summary, tab_export = st.tabs(
        [":material/checklist: Checklist", ":material/analytics: Summary",
         ":material/download: Export"]
    )

    with tab_checklist:
        column_order = [c for c in COLUMNS if st.session_state.show_guidance or c != "Guidance"]
        edited = st.data_editor(
            base,
            key=f"editor_{st.session_state.version}",
            hide_index=True,
            width="stretch",
            height=min(38 + 35 * len(base), 640),
            column_order=column_order,
            disabled=READ_ONLY_COLUMNS,
            column_config={
                "Done": st.column_config.CheckboxColumn("Done", width="small"),
                "ID": st.column_config.TextColumn("ID", width="small"),
                "Item": st.column_config.TextColumn("Item", width="large"),
                "Severity": st.column_config.TextColumn("Severity", width="small"),
                "Guidance": st.column_config.TextColumn("Guidance", width="large"),
                "Owner": st.column_config.TextColumn("Owner"),
                "Due date": st.column_config.DateColumn("Due date", format="YYYY-MM-DD"),
                "Notes": st.column_config.TextColumn("Notes", width="medium"),
            },
        )
        st.caption("Tick items as they are addressed and fill in owners, dates and notes.")

    total = len(edited)
    done = int(edited["Done"].sum())
    high = edited["Severity"].eq("High")
    open_high = int((high & ~edited["Done"]).sum())
    with metrics:
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Total items", total, border=True)
        c2.metric("Completed", f"{done} / {total}", border=True)
        c3.metric("Open high-severity", open_high, border=True)
        c4.metric("Progress", f"{done / total:.0%}", border=True)
        st.progress(done / total)

    with tab_summary:
        left, right = st.columns(2)
        with left:
            st.markdown("**Items by section and severity**")
            by_severity = (
                pd.crosstab(edited["Section"], edited["Severity"])
                .reindex(columns=SEVERITIES, fill_value=0)
                .reindex(edited["Section"].unique())
            )
            by_severity["Total"] = by_severity.sum(axis=1)
            st.dataframe(by_severity, width="stretch")
        with right:
            st.markdown("**Completion by section**")
            progress = (
                edited.groupby("Section", sort=False)["Done"]
                .agg(Items="count", Done="sum")
                .assign(Progress=lambda d: d["Done"] / d["Items"])
            )
            st.dataframe(
                progress,
                width="stretch",
                column_config={
                    "Progress": st.column_config.ProgressColumn(
                        "Progress", format="percent", min_value=0, max_value=1
                    )
                },
            )

    with tab_export:
        st.markdown("Download the checklist, including your edits.")
        slug = slugify(project)
        c1, c2, c3 = st.columns(3)
        c1.download_button(
            "Excel (.xlsx)",
            data=to_excel(edited),
            file_name=f"{slug}-risk-checklist.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            icon=":material/table_view:",
            width="stretch",
            on_click=ui.download_toast("Excel checklist"),
        )
        c2.download_button(
            "CSV (.csv)",
            data=edited.to_csv(index=False).encode("utf-8"),
            file_name=f"{slug}-risk-checklist.csv",
            mime="text/csv",
            icon=":material/description:",
            width="stretch",
            on_click=ui.download_toast("CSV checklist"),
        )
        c3.download_button(
            "Markdown (.md)",
            data=to_markdown(edited, project),
            file_name=f"{slug}-risk-checklist.md",
            mime="text/markdown",
            icon=":material/article:",
            width="stretch",
            on_click=ui.download_toast("Markdown checklist"),
        )


def render() -> None:
    templates = load_templates()

    st.title("Template builder")
    st.caption(
        "Combine curated templates into one project checklist, then track owners, "
        "due dates and progress and export it."
    )

    if not templates:
        st.error(f"No templates found in `{DATA_DIR}`. Add at least one JSON template.")
        st.stop()

    render_sidebar(templates)

    if "checklist" in st.session_state:
        render_checklist()
    else:
        render_overview(templates)
