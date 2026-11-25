"""Textual interpretation helpers for dashboard sections and charts."""
import html

import streamlit as st

SECTION_MEANINGS = {
    "Total Pulls & Account Progress": "Summarizes pull volume and rarity composition to compare account activity.",
    "5★ Pity Distribution": "Shows how many pulls were needed to obtain each 5★ item.",
    "Hazard Rate": "Estimates the chance of obtaining a 5★ at each pity level, provided one has not appeared yet.",
    "4★ Pity Distribution": "Shows the number of pulls required to obtain each 4★ item.",
    "5★ Pity Timeline": "Tracks the pity count for each 5★ result over time; colors distinguish rate-up outcomes.",
    "5★ Actual vs Expected": "Compares the actual number of 5★ results with the estimate based on the banner consolidated rate.",
    "Rolling Pulls per 5★": "Tracks the moving average pity across recent 5★ results to show changes in efficiency.",
    "50-50 Win/Lose": "Compares wins, losses, guarantees, and the rate-up win rate.",
    "Banner Performance": "Compares pull volume, 5★ acquisition efficiency, and rate-up success across banners.",
    "Luck Score": "Combines pity efficiency (60%) and rate-up success (40%); a score of 50 is neutral.",
    "Pull History": "Lists obtained 5★ and 4★ items, with banner and item-type filters.",
}


def section_meaning(title: str, fallback: str = "") -> str:
    if title in SECTION_MEANINGS:
        return SECTION_MEANINGS[title]
    if title.endswith(" Timeline") and title.split(" ", 1)[0] in {"Wish", "Warp"}:
        return "Shows monthly pull activity and each banner’s contribution."
    if title.startswith("Top Character &"):
        return "Summarizes the most frequently obtained 4★–5★ characters and weapons / Light Cones."
    if title.startswith("Latest 5★"):
        return "Shows the latest 5★ results for each banner, sorted newest first."
    return fallback


def section_header(title: str, subtitle: str = ""):
    meaning = section_meaning(title, subtitle)
    sub = f'<span class="gx-section-subtitle">What it shows: {html.escape(meaning)}</span>' if meaning else ""
    st.markdown(
        f'<div class="gx-section"><span class="gx-section-title">{html.escape(title)}</span>{sub}</div>',
        unsafe_allow_html=True,
    )



CHART_MEANINGS = {
    "total_pull": "The share of 3★, 4★, and 5★ results in each account’s pulls; compares rarity mix rather than raw volume.",
    "timeline": "Monthly pulls by banner; stacked bars show each banner’s contribution.",
    "timeline_5star": "The number of 5★ items obtained each month, broken down by banner.",
    "timeline_4star": "The number of 4★ items obtained each month, broken down by banner.",
    "pity_cdf": "The cumulative share of 5★ results obtained by each pity level; a faster-rising curve means results tend to arrive sooner.",
    "pity_timeline": "Each point represents one 5★ result; the X-axis shows the date and the Y-axis shows the pity count when it was obtained.",
    "exp_cum": "Compares cumulative actual 5★ results with the estimate based on the configured official rates.",
    "exp_gap": "Actual minus expected; a positive value means more 5★ results than expected by that date.",
    "rolling": "Dots show the pity count for each 5★; the line shows the moving average across the latest N results.",
    "wl_stack": "Rate-up outcome breakdown: Win, Lose, and Guaranteed for each banner and rarity.",
    "wl_rate": "Win rate is calculated from Win/Lose outcomes only; the marker shows the official 5★ rate-up chance.",
    "luck": "Compares pity efficiency, rate-up success, and Luck Score by account; 50 is the neutral point.",
    "banner_total": "Total pulls recorded for each banner; shows how activity is distributed.",
    "banner_eff": "Average pulls required to obtain one 5★; lower values indicate greater efficiency.",
    "banner_wr": "The 5★ rate-up win percentage among Win/Lose outcomes; the marker is the banner’s official baseline.",
}

def chart_meaning(name: str) -> str:
    if name in CHART_MEANINGS: return CHART_MEANINGS[name]
    if name.startswith("pity4_"): return "Distribution of pulls required to obtain a 4★ on this banner; the dashed line marks the average."
    if name.startswith("pity_"): return "Distribution of pulls required to obtain a 5★ on this banner; the dashed line marks the average and hard pity."
    if name.startswith("hazard_"): return "Observed chance of obtaining a 5★ in each pity bucket; faded bars indicate smaller at-risk samples."
    if name.startswith("top_"): return "Most frequently obtained items; bar length shows the number obtained and color indicates rarity."
    return "This chart summarizes data matching the account, banner, and date filters above."
