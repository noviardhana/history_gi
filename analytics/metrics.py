"""Reusable statistical metrics (no UI dependencies)."""
import numpy as np
import pandas as pd
from pipeline.luck import compute_luck

def current_pity(history: pd.DataFrame, banner: str, star: int=5):
    if star not in (4,5): raise ValueError("star must be 4 or 5")
    if history.empty: return None
    if history.account.nunique()>1:
        return {a: current_pity(history[history.account.eq(a)],banner,star) for a in history.account.dropna().unique()}
    b=history[history.banner_type.astype(str).eq(str(banner))].sort_values(["datetime","seq"],kind="stable")
    if b.empty:return None
    events=np.flatnonzero(b[f"is_{star}star"].fillna(False).to_numpy())
    return int(len(b)-events[-1]-1) if len(events) else int(len(b))

def rateup_stats(df,cfg):
    d=df[(df.rarity.eq(5)) & df.win_50_50.isin(["Win","Lose"])]
    wins=int(d.win_50_50.eq("Win").sum()); losses=int(d.win_50_50.eq("Lose").sum())
    ex=pd.to_numeric(d.banner_type.astype(object).map(cfg.rateup_chance),errors="coerce")
    return wins,losses,(float(ex.mean()) if ex.notna().any() else None)

def overall_luck(df,cfg):
    if df.empty:return None
    d=df.copy();d.banner_type=d.banner_type.astype(object);d.account="All"
    val=compute_luck(d,cfg).iloc[0].get("luck_score")
    return None if pd.isna(val) else float(val)

def build_summary_stats(df,cfg):
    total=len(df);five=df[df.is_5star].sort_values(["datetime","seq"],kind="stable");n5=len(five)
    wins,losses,expected=rateup_stats(df,cfg)
    avg_pity=pd.to_numeric(five.get("pity"),errors="coerce").mean() if n5 and "pity" in five else None
    return {"total":int(total),"n5":int(n5),"n4":int(df.is_4star.sum()),"rate_5":n5/total*100 if total else 0,
      "per_5":total/n5 if n5 else None,"avg_pity_5":avg_pity,"wins":wins,"losses":losses,
      "win_rate":wins/(wins+losses)*100 if wins+losses else None,"expected":expected,"luck":overall_luck(df,cfg),"last5":five.iloc[-1] if n5 else None}

def account_metrics(df,cfg):
    rows=[]
    for account,subset in df.groupby("account",sort=False):
        s=build_summary_stats(subset,cfg);s["account"]=account;rows.append(s)
    return pd.DataFrame(rows)
