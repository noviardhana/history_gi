"""CSV loading, normalization, and basic integrity diagnostics."""
from __future__ import annotations

from pathlib import Path
import pandas as pd
from pipeline.config import GAMES

REQUIRED_COLUMNS = {"account", "banner_type", "datetime", "rarity", "item_name"}

def load_data(filepath: str | Path, game_key: str, *, strict: bool = True) -> pd.DataFrame:
    df = pd.read_csv(filepath)
    missing = REQUIRED_COLUMNS - set(df.columns)
    if missing:
        if strict: raise ValueError(f"Missing required columns: {', '.join(sorted(missing))}")
        return pd.DataFrame()
    df = df.copy()
    df["_source_row"] = range(len(df))
    df["account"] = df["account"].astype("string").str.strip()
    df["banner_type"] = df["banner_type"].astype("string").str.strip()
    df["datetime"] = pd.to_datetime(df["datetime"], errors="coerce")
    df["rarity"] = pd.to_numeric(df["rarity"], errors="coerce")
    df = df.dropna(subset=["account", "banner_type", "datetime", "rarity"])
    df = df[df.account.ne("") & df.banner_type.ne("")]
    df["rarity"] = df["rarity"].astype(int)
    for c in ("uid", "adventure_rank", "world_level", "pull_number", "pity", "pity4", "pity5"):
        if c not in df: df[c] = pd.NA
        else: df[c] = pd.to_numeric(df[c], errors="coerce")
    if df["pull_number"].notna().all():
        df = df.sort_values(["account", "pull_number", "_source_row"], kind="stable")
    else:
        df = df.sort_values(["account", "datetime", "_source_row"], kind="stable")
    df["seq"] = df.groupby("account", sort=False).cumcount()
    df["date"] = df.datetime.dt.date
    df["year_month"] = df.datetime.dt.to_period("M").astype(str)
    for n in (3,4,5): df[f"is_{n}star"] = df.rarity.eq(n)
    if "win_50_50" not in df: df["win_50_50"] = pd.NA
    cfg = GAMES[game_key]
    banner_order = [b for b in cfg.banner_order if b in df.banner_type.unique()]
    banner_order += [b for b in df.banner_type.unique() if b not in banner_order]
    df["banner_type"] = pd.Categorical(df.banner_type, categories=banner_order, ordered=True)
    return df.drop(columns="_source_row").reset_index(drop=True)

def validate_data(df: pd.DataFrame) -> dict:
    if df.empty: return {"rows": 0, "empty": True, "issues": ["Dataset is empty"]}
    issues=[]
    if df.datetime.isna().any(): issues.append("Invalid datetime values")
    if df.rarity.isna().any(): issues.append("Missing/invalid rarity")
    if not df.rarity.isin([3,4,5]).all(): issues.append("Unexpected rarity values")
    if df.duplicated().any(): issues.append("Exact duplicate rows detected")
    if df[["account","banner_type","datetime"]].isna().any().any(): issues.append("Missing key fields")
    return {"rows":int(len(df)),"accounts":int(df.account.nunique()),"issues":issues,"empty":False}
