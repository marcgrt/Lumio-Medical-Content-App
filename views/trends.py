"""Lumio — Trends tab: Themen-Radar + Story-Radar."""

from views.feed import _render_themen_radar, _render_story_radar

import streamlit as st


def render_trends(filters: dict):
    """Render the Trends tab with Themen-Radar and Story-Radar."""
    st.markdown('<div class="page-header">Trends</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="page-sub">Automatisch erkannte Themen-Cluster &amp; Redaktions-Pitches</div>',
        unsafe_allow_html=True,
    )

    # --- Themen-Radar 2.0 ---
    _render_themen_radar(filters)

    # --- Story-Radar ---
    _render_story_radar()
