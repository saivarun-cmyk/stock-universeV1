from pathlib import Path
import yaml

CONFIG_DIR = Path(__file__).resolve().parents[1] / "config"

# One config file per market -- kept fully separate on disk so India and USA
# symbols are never accidentally combined.
CONFIG_FILES = {
    "India": CONFIG_DIR / "universe_india.yaml",
    "USA": CONFIG_DIR / "universe_usa.yaml",
}


def _load(market="India"):
    path = CONFIG_FILES.get(market, CONFIG_FILES["India"])
    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def stocks(market="India"):
    items = list(_load(market).get("stocks", []))
    for item in items:
        item.setdefault("type", "stock")
        item["market"] = market
    return items


def indexes(market="India"):
    items = list(_load(market).get("indexes", []))
    for item in items:
        item["type"] = "index"
        item["market"] = market
    return items


def all_items(market="India"):
    return stocks(market) + indexes(market)
