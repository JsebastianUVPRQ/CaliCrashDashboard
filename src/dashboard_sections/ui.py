"""Shared UI helpers for dashboard sections."""

from html import escape

import streamlit as st


def render_nav_bar(chips: list[tuple[str, str]]) -> None:
    """Rendered sticky anchor navigation (label, anchor) chips."""
    chips_html = "".join(
        f'<a class="nav-chip" href="#{escape(anchor)}">{escape(label)}</a>'
        for label, anchor in chips
    )
    st.markdown(
        f'<nav class="nav-bar" id="nav">{chips_html}</nav>',
        unsafe_allow_html=True,
    )


def render_section_header(
    anchor: str,
    kicker: str,
    title: str,
    caption: str = "",
) -> None:
    """Section title block: kicker chip, title and optional explanatory caption."""
    caption_html = (
        f'<p class="section-caption">{escape(caption)}</p>' if caption else ""
    )
    st.markdown(
        f"""
        <a id="{escape(anchor)}"></a>
        <div class="section-head">
            <p class="kicker">{escape(kicker)}</p>
            <h2 class="section-title">{escape(title)}</h2>
            {caption_html}
        </div>
        """,
        unsafe_allow_html=True,
    )

def render_source_note(text: str = "Fuente: Secretaría de Movilidad de Cali · datos.cali.gov.co") -> None:
    st.markdown(
        f'<p class="source-note">{escape(text)}</p>',
        unsafe_allow_html=True,
    )


def render_caveat(text: str) -> None:
    st.markdown(
        f'<div class="caveat-note">{escape(text)}</div>',
        unsafe_allow_html=True,
    )


def render_empty_state(title: str, actions: list[str]) -> None:
    """Friendly empty-state card with suggested actions."""
    items = "".join(f"<li>{escape(action)}</li>" for action in actions)
    st.markdown(
        f"""
        <div class="empty-state">
            <div class="empty-state-badge">Info</div>
            <div>
                <strong>{escape(title)}</strong>
                <p>Esto no necesariamente indica un error de la aplicación.</p>
                <ul>{items}</ul>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_insight_band(insights: list[tuple[str, str]]) -> None:
    """Executive insight cards: ``(kicker, sentence)`` pairs."""
    cards = "".join(
        (
            '<div class="insight-item">'
            f"<small>{escape(label)}</small>"
            f"{escape(text)}"
            "</div>"
        )
        for label, text in insights
    )
    if not cards:
        return
    st.markdown(
        f'<div class="insight-strip">{cards}</div>',
        unsafe_allow_html=True,
    )


def render_kpi_cards(cards: list[tuple[str, str, str, str]]) -> None:
    """KPI strip: (label, value, caption, css variant). Variant: ``""``,
    ``"kpi-risk"`` or ``"kpi-well"``."""
    cards_html = "".join(
        (
            '<article class="kpi-card {variant}">'
            f"<span>{escape(label)}</span>"
            f"<strong>{escape(value)}</strong>"
            f"<small>{escape(caption)}</small>"
            "</article>"
        ).format(variant=variant)
        for label, value, caption, variant in cards
    )
    st.markdown(
        f'<section class="kpi-strip">{cards_html}</section>',
        unsafe_allow_html=True,
    )