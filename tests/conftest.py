"""Réglages communs aux tests : le code de src/ est importable sans installation."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))   # tests/rejeu.py
