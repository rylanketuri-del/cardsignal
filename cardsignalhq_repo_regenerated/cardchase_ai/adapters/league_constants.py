"""League-specific configuration constants — no adapter imports."""

MLB_SEARCH_TEMPLATES = {
    "broad": "{player} baseball card",
    "bowman_chrome": "{player} Bowman Chrome rookie",
    "auto": "{player} auto baseball card",
    "psa10": "{player} PSA 10 baseball card",
}

MLB_CARD_QUERY_LABELS = {
    "broad": "Base Cards",
    "bowman_chrome": "Bowman Chrome",
    "auto": "Autographs",
    "psa10": "PSA 10",
}

MLB_SUPPORTED_POSITIONS = ("Pitcher", "Catcher", "Infield", "Outfield")
MLB_SUPPORTED_METRICS = ("AVG", "HR", "OPS", "SB", "RBI", "R")

NFL_SEARCH_TEMPLATES = {
    "broad": "{player} football card",
    "prizm_rookie": "{player} Prizm rookie",
    "auto": "{player} auto football card",
    "psa10": "{player} PSA 10 football card",
}

NFL_CARD_QUERY_LABELS = {
    "broad": "Base Cards",
    "prizm_rookie": "Prizm Rookie",
    "auto": "Autographs",
    "psa10": "PSA 10",
}

NFL_SUPPORTED_POSITIONS = ("QB", "RB", "WR", "TE")
NFL_SUPPORTED_METRICS = ("PASS_YDS", "RUSH_YDS", "REC_YDS", "TD", "COMP_PCT")
