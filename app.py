"""Risk Checklist Generator: entry point and page navigation."""

import streamlit as st

import domain_checklist
import template_builder

st.set_page_config(
    page_title="Risk Checklist Generator",
    page_icon=":material/checklist:",
    layout="wide",
)

page = st.navigation(
    [
        st.Page(
            domain_checklist.render,
            title="Domain checklist",
            icon=":material/fact_check:",
            url_path="domain-checklist",
            default=True,
        ),
        st.Page(
            template_builder.render,
            title="Template builder",
            icon=":material/construction:",
            url_path="template-builder",
        ),
    ],
    position="top",
)
page.run()
