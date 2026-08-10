import sys
import os
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from services.stages import derive_stage, next_etapa, add_delay, normalize_phone


def test_normalize_phone():
    assert normalize_phone("+54 9 11 3843-8602") == "+5491138438602"
    assert normalize_phone("5491138438602") == "+5491138438602"
    assert normalize_phone("") == ""


def test_derive_stage_paused():
    assert derive_stage("cualificado", "", 0, paused=True) == "Pausado por humano"


def test_derive_stage_wizard():
    assert derive_stage("wizard", "", 3) == "Wizard Q3"


def test_derive_stage_followup():
    assert derive_stage("cualificado", "6h2") == "Seguimiento 6h2"
    assert derive_stage("cualificado", "m3") == "Nurturing mensual m3"


def test_next_etapa_chain():
    nxt, delay = next_etapa("6h1")
    assert nxt == "6h2"
    nxt, delay = next_etapa("m6")
    assert nxt is None


def test_add_delay_hours():
    base = datetime(2026, 8, 4, 10, 0)
    assert add_delay(base, {"hours": 6}).hour == 16
