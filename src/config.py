from pathlib import Path

import yaml
from dotenv import load_dotenv

import os
import sys

# CODE: where the program and its bundled defaults live. ROOT: where the user's data lives (videos, db, music, keys).
CODE = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent))
ROOT = Path(os.environ["SF_HOME"]) if os.getenv("SF_HOME") else CODE
load_dotenv(ROOT / ".env")


def load(path=None) -> dict:
    with open(path or ROOT / "config.yaml", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    cfg["_root"] = ROOT
    return cfg


def resolve(cfg: dict, rel: str) -> Path:
    p = Path(rel)
    return p if p.is_absolute() else cfg["_root"] / p
