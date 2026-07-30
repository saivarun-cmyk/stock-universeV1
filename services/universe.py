from pathlib import Path
import yaml

CONFIG_FILE = Path(__file__).resolve().parents[1] / "config" / "universe.yaml"


def _load():
    with CONFIG_FILE.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def stocks():
    items = list(_load().get("stocks", []))
    for item in items:
        item.setdefault("type", "stock")
    return items


def indexes():
    items = list(_load().get("indexes", []))
    for item in items:
        item["type"] = "index"
    return items


def all_items():
    return stocks() + indexes()
