"""Domain checklist page: generate a control checklist from curated domain templates."""

from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path

import pandas as pd
import streamlit as st

import ui

DOMAIN_DIR = Path(__file__).parent / "data" / "domains"

# Sidebar option -> template file in data/domains/. "Custom" uses the generic template.
DOMAINS = {
    "IT Technology Risk": "it_technology_risk.json",
    "AI Governance & Risk": "ai_governance.json",
    "Data Validation & Quality": "data_quality.json",
    "Cybersecurity Controls": "cybersecurity_controls.json",
    "Healthcare IT Risk": "healthcare_it.json",
    "Custom": "generic.json",
}
# Frameworks the templates are mapped to (keys match each control's "refs").
FRAMEWORKS = {
    "NIST CSF": "NIST Cybersecurity Framework 2.0",
    "ISO 27001": "ISO/IEC 27001:2022",
    "SOC 2": "SOC 2 Trust Services Criteria",
    "HIPAA": "HIPAA (45 CFR Part 164)",
}
FRAMEWORK_OPTIONS = ["None", *FRAMEWORKS, "Custom"]
PRIORITY_WEIGHT = {"High": 3, "Medium": 2, "Low": 1}
PRIORITY_COLOR = {"High": "red", "Medium": "orange", "Low": "gray"}
# Ranking bonuses on top of the priority weight.
FRAMEWORK_BONUS = 1.5
CONTEXT_BONUS = 0.75  # per matching context term, at most two terms
STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "based", "by", "company", "for", "from",
    "has", "have", "in", "into", "is", "its", "large", "medium", "mid", "of", "on",
    "or", "our", "people", "size", "sized", "small", "staff", "that", "the", "their",
    "this", "to", "use", "uses", "using", "we", "with", "employees", "around", "about",
}


# --------------------------------------------------------------------------- #
# Data
# --------------------------------------------------------------------------- #
@st.cache_data
def _read_domain(filename: str, mtime: float) -> dict:
    with (DOMAIN_DIR / filename).open(encoding="utf-8") as f:
        return json.load(f)


def load_domain(filename: str) -> dict:
    """Load a domain template, re-reading it whenever the file changes on disk."""
    return _read_domain(filename, (DOMAIN_DIR / filename).stat().st_mtime)


def context_terms(context: str) -> list[str]:
    """Keywords from the free-text context, lightly stemmed (vendors -> vendor)."""
    terms = set()
    for word in re.findall(r"[a-z0-9][a-z0-9&+-]*", context.lower()):
        if len(word) < 3 or word in STOPWORDS or word.isdigit():
            continue
        terms.add(word[:-1] if len(word) > 4 and word.endswith("s") else word)
    return sorted(terms)


def select_controls(template: dict, count: int, framework: str | None, context: str) -> tuple[list[dict], list[str]]:
    """Pick `count` controls, keeping every category represented.

    Controls are ranked by priority, then boosted when they map to the selected
    framework or mention terms from the context. Each category's best control is
    taken first, the rest are filled by rank, and template order is restored.
    """
    terms = context_terms(context)
    scored = []
    for c, category in enumerate(template["categories"]):
        for i, item in enumerate(category["items"]):
            text = " ".join([
                item["control"], item["risk"], item["test"], item["owner"],
                *item["evidence"], item.get("other", ""),
            ]).lower()
            hits = [t for t in terms if re.search(rf"\b{re.escape(t)}", text)]
            score = PRIORITY_WEIGHT[item["priority"]]
            score += FRAMEWORK_BONUS if framework in item["refs"] else 0
            score += CONTEXT_BONUS * min(len(hits), 2)
            scored.append({"score": score, "pos": (c, i), "hits": hits})
    ranked = sorted(scored, key=lambda s: (-s["score"], s["pos"]))

    chosen: dict[tuple[int, int], dict] = {}
    if count >= len(template["categories"]):
        for c in range(len(template["categories"])):
            best = next(s for s in ranked if s["pos"][0] == c)
            chosen[best["pos"]] = best
    for s in ranked:
        if len(chosen) >= count:
            break
        chosen.setdefault(s["pos"], s)

    categories = []
    for c, category in enumerate(template["categories"]):
        items = [category["items"][i] for (cc, i) in sorted(chosen) if cc == c]
        if items:
            categories.append({**category, "items": items})
    matched = sorted({t for s in chosen.values() for t in s["hits"]})
    return categories, matched


def framework_columns(result: dict) -> dict[str, callable]:
    """Framework reference columns for the export, depending on the selection."""
    fw = result["framework"]
    if fw in FRAMEWORKS:
        return {f"{fw} reference": lambda item: item["refs"].get(fw, "")}
    if fw == "Custom":
        return {f"{result['framework_label']} reference": lambda item: ""}
    return {name: (lambda item, n=name: item["refs"].get(n, "")) for name in FRAMEWORKS}


def to_dataframe(result: dict) -> pd.DataFrame:
    columns = framework_columns(result)
    rows = []
    for category in result["categories"]:
        for item in category["items"]:
            row = {
                "Category": category["name"],
                "ID": item["id"],
                "Control": item["control"],
                "Risk addressed": item["risk"],
                "Priority": item["priority"],
                "Control type": item["type"],
                "Frequency": item["frequency"],
                "Suggested owner": item["owner"],
            }
            row.update({name: get(item) for name, get in columns.items()})
            row.update({
                "Test procedure": item["test"],
                "Example evidence": "; ".join(item["evidence"]),
                "Other references": item.get("other", ""),
                "Status": "Not started",
                "Owner": "",
                "Notes": "",
            })
            rows.append(row)
    return pd.DataFrame(rows)


# --------------------------------------------------------------------------- #
# Exports
# --------------------------------------------------------------------------- #
def slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-") or "checklist"


def item_refs(item: dict, result: dict) -> list[str]:
    fw = result["framework"]
    if fw in FRAMEWORKS:
        ref = item["refs"].get(fw)
        return [f"{fw} {ref}"] if ref else [f"{fw}: no direct mapping"]
    if fw == "Custom":
        return []
    return [f"{name} {ref}" for name, ref in item["refs"].items()]


def to_markdown(result: dict) -> str:
    total = sum(len(c["items"]) for c in result["categories"])
    lines = [
        f"# {result['domain']}: Risk Control Checklist",
        "",
        f"- **Generated:** {result['generated']:%d %B %Y}",
        f"- **Framework:** {result['framework_label'] or 'None selected'}",
    ]
    if result["context"]:
        lines.append(f"- **Context:** {result['context']}")
    lines += [
        f"- **Scope:** {total} controls across {len(result['categories'])} categories",
        f"- **Template sources:** {result['references']}",
        "",
        *ui.customization_markdown(),
    ]
    for n, category in enumerate(result["categories"], start=1):
        lines += ["", f"## {n}. {category['name']}", "", f"_{category['objective']}_", ""]
        for item in category["items"]:
            meta = [
                f"Priority: {item['priority']}",
                f"Type: {item['type']}",
                f"Frequency: {item['frequency']}",
                f"Suggested owner: {item['owner']}",
            ]
            lines.append(f"- [ ] **{item['id']}** {item['control']}")
            lines.append(f"  - **Risk addressed:** {item['risk']}")
            lines.append(f"  - {' | '.join(meta)}")
            refs = item_refs(item, result)
            if refs:
                lines.append(f"  - Framework: {' | '.join(refs)}")
            lines.append(f"  - **How to test:** {item['test']}")
            lines.append("  - **Example evidence:**")
            lines += [f"    - {e}" for e in item["evidence"]]
            if item.get("other"):
                lines.append(f"  - Other references: {item['other']}")
    return "\n".join(lines) + "\n"


# --------------------------------------------------------------------------- #
# Views
# --------------------------------------------------------------------------- #
def md(text: str) -> str:
    """Escape characters Streamlit markdown would treat as LaTeX."""
    return text.replace("$", r"\$")


def render_sidebar() -> dict:
    with st.sidebar:
        st.header("Checklist settings")
        st.subheader("Scope", divider="gray")
        domain = st.selectbox(
            "Risk domain",
            list(DOMAINS),
            key="dc_domain",
            help="Each domain has its own curated control template. Custom uses a generic template.",
        )
        custom_domain = ""
        if domain == "Custom":
            custom_domain = st.text_input(
                "Custom domain name",
                placeholder="e.g. Payments operations",
                key="dc_custom_domain",
                help="Used as the checklist title. Controls come from a generic risk and control template.",
            )
        framework = st.selectbox(
            "Framework (optional)",
            FRAMEWORK_OPTIONS,
            key="dc_framework",
            help="Shows the matching control reference for each item and favours controls that map to it.",
        )
        custom_framework = ""
        if framework == "Custom":
            custom_framework = st.text_input(
                "Framework name",
                placeholder="e.g. PCI DSS 4.0, NIST SP 800-53",
                key="dc_custom_framework",
                help="Adds an empty reference column to the exports for you to map controls.",
            )
        st.subheader("Tailoring", divider="gray")
        context = st.text_area(
            "Company size / context (optional)",
            placeholder="e.g. 400-person SaaS company on AWS, processing customer PII, using third-party AI vendors",
            key="dc_context",
            help="Shown on the checklist. Controls that mention your context terms are favoured when trimming.",
        )
        count = st.slider(
            "Number of checklist items",
            10, 50, 25,
            key="dc_count",
            help="Every category keeps at least one control; higher-priority controls fill the rest.",
        )
        st.caption("Templates are curated starting points. Tailor the output to your organisation.")
    return {
        "domain": domain,
        "custom_domain": custom_domain.strip(),
        "framework": framework,
        "custom_framework": custom_framework.strip(),
        "context": context.strip(),
        "count": count,
    }


def build_result(settings: dict) -> dict:
    template = load_domain(DOMAINS[settings["domain"]])
    fw = settings["framework"]
    framework = None if fw == "None" else fw
    if fw == "Custom":
        label = settings["custom_framework"] or "Custom framework"
    else:
        label = FRAMEWORKS.get(fw)
    categories, matched = select_controls(template, settings["count"], framework, settings["context"])
    if settings["domain"] == "Custom":
        domain = settings["custom_domain"] or "Custom risk domain"
    else:
        domain = settings["domain"]
    return {
        "settings": settings,
        "domain": domain,
        "references": template["references"],
        "framework": framework,
        "framework_label": label,
        "context": settings["context"],
        "categories": categories,
        "matched_terms": matched,
        "generated": datetime.now(),
    }


def render_template_card(settings: dict) -> None:
    template = load_domain(DOMAINS[settings["domain"]])
    total = sum(len(c["items"]) for c in template["categories"])
    with st.container(border=True):
        st.caption("SELECTED TEMPLATE")
        st.markdown(f"**{template['name']}**")
        st.write(template["description"])
        st.caption(
            f"{total} curated controls in {len(template['categories'])} categories: "
            + ", ".join(c["name"] for c in template["categories"])
        )
        st.caption(f"Sources: {template['references']}")


def render_item(item: dict, result: dict) -> None:
    fw = result["framework"]
    badges = [f":{PRIORITY_COLOR[item['priority']]}-badge[{item['priority']} priority]"]
    if fw in FRAMEWORKS:
        ref = item["refs"].get(fw)
        badges.append(f":blue-badge[{fw} {ref}]" if ref else f":gray-badge[No direct {fw} mapping]")
    badges += [f":gray-badge[{item['type']}]", f":gray-badge[{item['frequency']}]"]
    with st.container(border=True):
        st.markdown(f"**{item['id']}** &nbsp; " + " ".join(badges))
        st.markdown(md(item["control"]))
        st.markdown(f":gray[**Risk addressed:** {md(item['risk'])}]")
        left, right = st.columns(2, gap="medium")
        evidence = "\n".join(f"- {md(e)}" for e in item["evidence"])
        left.markdown(f"**Example evidence**\n\n{evidence}")
        right.markdown(f"**How to test**\n\n{md(item['test'])}")
        notes = [f"Suggested owner: {item['owner']}"]
        if fw is None and item["refs"]:
            notes.append(" · ".join(f"{n} {r}" for n, r in item["refs"].items()))
        if item.get("other"):
            notes.append(f"Also: {item['other']}")
        st.caption(md("  \n".join(notes)))


def render_result(result: dict, settings: dict) -> None:
    categories = result["categories"]
    items = [i for c in categories for i in c["items"]]
    if result["settings"] != settings:
        st.info(
            "The inputs have changed since this checklist was generated. "
            "Select **Generate checklist** to refresh it.",
            icon=":material/sync:",
        )

    st.subheader(f"{result['domain']}: risk control checklist")
    meta = [f"Generated {result['generated']:%d %b %Y, %H:%M}"]
    if result["framework_label"]:
        meta.append(f"Framework: {result['framework_label']}")
    if result["context"]:
        meta.append(f"Context: {result['context']}")
    st.caption(md(" · ".join(meta)))

    fw = result["framework"]
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Controls", len(items), border=True)
    c2.metric("Categories", len(categories), border=True)
    c3.metric("High priority", sum(i["priority"] == "High" for i in items), border=True)
    if fw in FRAMEWORKS:
        mapped = sum(fw in i["refs"] for i in items)
        c4.metric(
            "Coverage", f"{mapped / len(items):.0%}", border=True,
            help=f"Share of these controls with a direct {fw} reference.",
        )
    else:
        c4.metric("Evidence items", sum(len(i["evidence"]) for i in items), border=True)

    if fw == "Custom":
        st.caption(
            f"No built-in mapping exists for {md(result['framework_label'])}, so the exports "
            "include an empty reference column for you to complete."
        )
    if result["matched_terms"]:
        st.caption("Context terms that matched controls: " + ", ".join(result["matched_terms"]))

    ui.customization_note()

    slug = f"{slugify(result['domain'])}-checklist-{result['generated']:%Y%m%d}"
    with st.container(horizontal=True):
        st.download_button(
            "Download as Markdown",
            data=to_markdown(result),
            file_name=f"{slug}.md",
            mime="text/markdown",
            icon=":material/article:",
            on_click=ui.download_toast("Markdown checklist"),
        )
        st.download_button(
            "Download as CSV",
            data=to_dataframe(result).to_csv(index=False).encode("utf-8-sig"),
            file_name=f"{slug}.csv",
            mime="text/csv",
            icon=":material/table_view:",
            on_click=ui.download_toast("CSV checklist"),
        )

    expand_all = st.toggle("Expand all categories", key="dc_expand_all")
    for n, category in enumerate(categories, start=1):
        high = sum(i["priority"] == "High" for i in category["items"])
        k = len(category["items"])
        label = f"{n}. {category['name']} · {k} control{'s' if k != 1 else ''}"
        if high:
            label += f" · {high} high"
        with st.expander(label, expanded=expand_all or n == 1):
            st.caption(md(category["objective"]))
            for item in category["items"]:
                render_item(item, result)


def render() -> None:
    st.title("Domain risk checklist")
    st.caption(
        "Generate a control checklist for a risk domain, with framework references, "
        "test steps and example audit evidence for each control."
    )
    settings = render_sidebar()
    render_template_card(settings)

    generated = st.button("Generate checklist", type="primary", icon=":material/auto_awesome:")
    if generated:
        st.session_state.dc_result = build_result(settings)

    result = st.session_state.get("dc_result")
    if result is None:
        st.info(
            "Choose a risk domain and options in the sidebar, then select **Generate checklist**.",
            icon=":material/arrow_back:",
        )
        return
    if generated:
        n = sum(len(c["items"]) for c in result["categories"])
        k = len(result["categories"])
        fw = f", mapped to {result['framework_label']}" if result["framework"] in FRAMEWORKS else ""
        st.success(
            f"Checklist generated: {n} controls across {k} categories{fw}.",
            icon=":material/check_circle:",
        )
    render_result(result, settings)
