def _result(home, away):
    if home > away: return "H"
    if away > home: return "A"
    return "D"

def calculate_points(real_home: int, real_away: int, pred_home: int, pred_away: int) -> int:
    if real_home == pred_home and real_away == pred_away:
        return 3
    if _result(real_home, real_away) == _result(pred_home, pred_away):
        return 1
    return 0

def calculate_special_points(
    real_champion: str, real_runner_up: str, real_top_scorer: str,
    pred_champion: str, pred_runner_up: str, pred_top_scorer: str
) -> tuple[int, int, int]:
    pts_c = 5 if real_champion == pred_champion else 0
    pts_r = 3 if real_runner_up == pred_runner_up else 0
    pts_t = 2 if real_top_scorer and real_top_scorer.lower() == (pred_top_scorer or "").lower() else 0
    return pts_c, pts_r, pts_t
