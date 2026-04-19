from __future__ import annotations

from datetime import datetime, timedelta
from typing import Iterable, List

from cardchase_ai.models.schemas import HitterGameLogRow, RollingHitterStats


DATE_FMT = "%Y-%m-%d"



def filter_last_n_days(rows: Iterable[HitterGameLogRow], days: int) -> List[HitterGameLogRow]:
    rows = list(rows)
    if not rows:
        return []
    latest = max(datetime.strptime(row.date, DATE_FMT) for row in rows if row.date)
    cutoff = latest - timedelta(days=days - 1)
    return [
        row
        for row in rows
        if row.date and datetime.strptime(row.date, DATE_FMT) >= cutoff
    ]



def summarize_hitter_window(rows: Iterable[HitterGameLogRow]) -> RollingHitterStats:
    rows = list(rows)
    if not rows:
        return RollingHitterStats()

    at_bats = sum(row.at_bats for row in rows)
    hits = sum(row.hits for row in rows)
    home_runs = sum(row.home_runs for row in rows)
    rbi = sum(row.rbi for row in rows)
    stolen_bases = sum(row.stolen_bases for row in rows)
    walks = sum(row.walks for row in rows)
    strikeouts = sum(row.strikeouts for row in rows)

    avg = hits / at_bats if at_bats else 0.0
    obp = (hits + walks) / (at_bats + walks) if (at_bats + walks) else 0.0
    singles = hits - home_runs
    total_bases_floor = singles + (4 * home_runs)
    slg = total_bases_floor / at_bats if at_bats else 0.0
    ops = obp + slg

    return RollingHitterStats(
        games=len(rows),
        at_bats=at_bats,
        hits=hits,
        home_runs=home_runs,
        rbi=rbi,
        stolen_bases=stolen_bases,
        walks=walks,
        strikeouts=strikeouts,
        avg=round(avg, 3),
        obp=round(obp, 3),
        slg=round(slg, 3),
        ops=round(ops, 3),
    )
