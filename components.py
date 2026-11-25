"""Reusable HTML/UI helpers for the dashboard."""
import streamlit as st

def block_label(text: str):
    st.markdown(
        f'<div class="block-label"><span class="block-label-text">{text}</span>'
        f'<span class="block-label-line"></span></div>',
        unsafe_allow_html=True,
    )

def chart_note(text: str):
    st.markdown(f'<div class="chart-note">{text}</div>', unsafe_allow_html=True)

def badge(text: str, color: str) -> str:
    return (f'<span class="gx-badge" style="background:{color}26; color:{color}; '
            f'border:1px solid {color}55;">{text}</span>')

def kpi_card(label: str, value: str, sub: str = "", color: str = "#f2a641", value_size: str = "1.6em") -> str:
    return (f'<div class="kpi-card"><div class="kpi-label">{label}</div>'
            f'<div class="kpi-value" style="color:{color}; font-size:{value_size};">{value}</div>'
            f'<div class="kpi-sub">{sub}</div></div>')
