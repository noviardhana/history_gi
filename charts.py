"""Reusable chart helpers."""
from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.graph_objects as go

TEXT_PRIMARY = "#eef3f9"

def apply_layout(fig, title, xaxis_title=None, yaxis_title=None, height=380, legend=False, yaxis_range=None, **extra):
    fig.update_layout(title=title, xaxis_title=xaxis_title, yaxis_title=yaxis_title, height=height, showlegend=legend, **extra)
    if yaxis_range is not None: fig.update_yaxes(range=yaxis_range)
    return fig

def _monthly_star_chart(pv: pd.DataFrame, cfg, star: int):
    fig = go.Figure()
    for banner in pv.columns:
        fig.add_trace(go.Bar(x=pv.index, y=pv[banner], name=banner, marker_color=cfg.banner_colors.get(banner, "#999999")))
    total = pv.sum(axis=1)
    fig.add_trace(go.Scatter(x=total.index, y=total.values, mode="text", text=[f"{int(v)}" if v else "" for v in total.values],
                             textposition="top center", textfont=dict(color=TEXT_PRIMARY, size=11),
                             showlegend=False, hoverinfo="skip", cliponaxis=False))
    apply_layout(fig, f"{star}★ Obtained per Month", "Month", f"{star}★ obtained", height=340,
                 barmode="stack", hovermode="x unified", legend=True)
    fig.update_yaxes(range=[0, max(int(total.max()), 1) * 1.25])
    fig.update_layout(legend_itemclick=False, legend_itemdoubleclick=False)
    return fig

def _kde(vals, grid):
    """Gaussian KDE (Silverman-style bandwidth) on `grid`; None when it cannot be estimated."""
    x = np.asarray(vals, dtype=float)
    if len(x) < 3 or x.std(ddof=1) == 0:
        return None
    sd = x.std(ddof=1)
    iqr = np.subtract(*np.percentile(x, [75, 25]))
    bw = 0.9 * (min(sd, iqr / 1.34) if iqr > 0 else sd) * len(x) ** (-1 / 5)
    z = (grid[:, None] - x[None, :]) / bw
    return np.exp(-0.5 * z ** 2).sum(axis=1) / (len(x) * bw * np.sqrt(2 * np.pi))
