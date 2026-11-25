"""Pure dataframe filtering helpers used by dashboard UI."""
from __future__ import annotations

import pandas as pd


def filter_accounts(df: pd.DataFrame, account: str | None = None) -> pd.DataFrame:
    """Filter to one account; None/All labels retain every account."""
    if account is None or str(account).strip().lower() in {"all", "all accounts", "total"}:
        return df.copy()
    return df.loc[df["account"].astype(str).eq(str(account))].copy()


def filter_banners(df: pd.DataFrame, banners: list[str] | tuple[str, ...] | None = None) -> pd.DataFrame:
    """Filter banner types; None means all banners, [] means no banners."""
    if banners is None:
        return df.copy()
    selected = {str(b) for b in banners}
    return df.loc[df["banner_type"].astype(str).isin(selected)].copy()


def filter_dates(df: pd.DataFrame, date_range=None) -> pd.DataFrame:
    """Inclusive date filter. None means retain full history."""
    if date_range is None:
        return df.copy()
    if len(date_range) != 2:
        raise ValueError("date_range must contain (start_date, end_date)")
    start, end = date_range
    if start > end:
        raise ValueError("date_range start must be <= end")
    dates = pd.to_datetime(df["datetime"], errors="coerce").dt.date
    return df.loc[dates.ge(start) & dates.le(end)].copy()


def apply_filters(
    df: pd.DataFrame, account: str | None = None,
    banners: list[str] | tuple[str, ...] | None = None, date_range=None,
) -> pd.DataFrame:
    """Apply account, banner, and inclusive date filters without mutating input."""
    result = filter_accounts(df, account)
    result = filter_banners(result, banners)
    return filter_dates(result, date_range)
