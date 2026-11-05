# Risk Checklist Generator

A Streamlit app that builds risk and control checklists from curated templates. It has two pages:

- **Domain checklist** (default): pick a risk domain and, optionally, a framework, and the app generates a structured control checklist with framework references and example audit evidence.
- **Template builder**: combine project risk templates, then track and export the checklist.

## Features

### Domain checklist

- **Sidebar inputs**: risk domain (IT Technology Risk, AI Governance & Risk, Data Validation & Quality, Cybersecurity Controls, Healthcare IT Risk, Custom), optional framework (NIST CSF, ISO 27001, SOC 2, HIPAA, Custom), optional company size and context, and the number of checklist items (10 to 50).
- **Curated templates**: each domain has 50 controls in 9 or 10 categories, held as JSON in `data/domains/`. The categories are the familiar GRC groupings (Governance, Access Control, Data Protection, Change Management, Third-Party Risk, Monitoring & Logging, Business Continuity) plus domain-specific ones such as *AI-Specific Risks* (fairness, hallucination, prompt injection, excessive agency), *Reconciliation & Completeness* or *Medical Device Security*. **Custom** uses a generic, domain-neutral template.
- **Control attributes**: every control states the risk it addresses, its priority, its type (Directive, Preventive, Detective or Corrective, and whether it is manual, automated or IT-dependent manual), its frequency, and a suggested owner role. It also gives a test procedure and two or three pieces of example evidence, worded like an audit request list (system-generated populations, sample sizes, named tool exports). Each control is referenced to NIST CSF 2.0, ISO/IEC 27001:2022, SOC 2 and HIPAA where a direct mapping exists, plus domain sources (COBIT, NIST AI RMF, EU AI Act, OWASP LLM Top 10, BCBS 239, CIS Controls, HICP and others).
- **Prioritisation**: when fewer than 50 items are requested, every category stays represented. The remaining slots go to the highest-priority controls, with a boost for controls that map to the chosen framework or mention terms from your context.
- **Output**: expandable categories, each control showing all of the attributes above, with **Download as Markdown** and **Download as CSV**. The CSV has one row per control with every attribute as a column, plus empty Status, Owner and Notes columns for tracking. With a Custom framework it includes an empty reference column for you to map.

### Template builder

- **Template library**: five starter templates (Project Delivery, IT Security, Data Privacy, Third-Party & Vendor, Business Continuity), stored as JSON in `data/`.
- **Tailoring**: combine templates, scale the checklist by project size, filter by severity and add your own items.
- **Tracking**: tick items off, assign owners, set due dates and add notes directly in the table. Default due dates are set from the start date by severity (High: 7 days, Medium: 21, Low: 45).
- **Summary**: item counts by section and severity, plus completion progress per section.
- **Export**: download the checklist, including your edits, as Excel, CSV or Markdown.

## Getting started

Requires Python 3.10 or later.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

The app opens at <http://localhost:8501>.

## Project structure

```
risk-checklist-generator/
├── app.py                  # Entry point and page navigation
├── domain_checklist.py     # Domain checklist page
├── template_builder.py     # Template builder page
├── ui.py                   # Shared UI copy (customisation note, download toasts)
├── data/                   # Template builder templates (one JSON file per template)
│   ├── domains/            # Domain checklist templates (one JSON file per domain)
│   ├── business_continuity.json
│   ├── data_privacy.json
│   ├── it_security.json
│   ├── project_delivery.json
│   └── vendor_risk.json
├── .streamlit/config.toml  # Theme and client settings
├── requirements.txt
└── README.md
```

## Adding a template builder template

Create a new `.json` file in `data/`. It is picked up automatically the next time the app starts (or after clearing the cache from the app menu).

```json
{
  "name": "Template name",
  "description": "One-line summary shown on the overview page.",
  "sections": [
    {
      "name": "Section name",
      "items": [
        {
          "id": "ABC-01",
          "text": "The control or check to perform",
          "severity": "High",
          "min_size": "Small",
          "guidance": "Optional tip on how to address the item."
        }
      ]
    }
  ]
}
```

| Field      | Values                        | Notes                                                       |
|------------|-------------------------------|-------------------------------------------------------------|
| `severity` | `High`, `Medium`, `Low`       | Drives the severity filter and default due date.            |
| `min_size` | `Small`, `Medium`, `Large`    | Smallest project size the item applies to. Defaults to `Small`. |
| `guidance` | Any text                      | Optional.                                                   |

Template names must be unique; item IDs should be unique within the app.

## Editing a domain template

Domain templates live in `data/domains/` and are listed in `DOMAINS` in `domain_checklist.py`. Each control has this shape:

```json
{
  "id": "CYB-AC-01",
  "control": "Phishing-resistant MFA (FIDO2 or certificate-based) is enforced for remote access, email, cloud consoles and all privileged access.",
  "risk": "Credential phishing and MFA fatigue attacks lead to account takeover.",
  "priority": "High",
  "type": "Preventive · Automated",
  "frequency": "Continuous",
  "owner": "IAM Team",
  "test": "Inspect IdP authentication policies and exclusions, and compare the MFA method report to in-scope users.",
  "evidence": ["Conditional access or authentication policy export with exclusions", "MFA method registration report by user"],
  "refs": {"NIST CSF": "PR.AA-03", "ISO 27001": "A.8.5", "SOC 2": "CC6.1", "HIPAA": "§164.312(d)"},
  "other": "CIS Control 6.3-6.5"
}
```

Each category has a short `code` (e.g. `AC`), a `name` and an `objective`, and control IDs follow `<DOMAIN>-<CODE>-<NN>`.

| Field | Values |
|-------|--------|
| `priority` | `High`, `Medium`, `Low` |
| `type` | `Directive`, `Preventive`, `Detective` or `Corrective`, then ` · `, then `Manual`, `Automated` or `IT-dependent manual` |
| `frequency` | `Continuous`, `Per event`, `Daily`, `Weekly`, `Monthly`, `Quarterly`, `Semi-annual`, `Annual` |
| `refs` | Keys from `NIST CSF`, `ISO 27001`, `SOC 2`, `HIPAA`. Leave a framework out when there is no direct mapping. |

Keep 50 controls and at most 10 categories per domain, so every slider value can be met with each category represented. Avoid semicolons in evidence text, because the CSV export joins evidence items with `; `. Template edits are picked up on the next run without restarting the app.

Framework references are a starting point for mapping, not an authoritative crosswalk. Review them against the current framework text before relying on them for an audit.
