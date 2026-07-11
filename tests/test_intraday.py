"""Mode intraday : réglage du matin rejoué sans autotune + grille explicite."""

import json

from trading_os.webapp.insights import FALLBACK_NAME, PATCHES, VARIANTS, saved_state


def test_saved_state_replays_morning_choice(tmp_path):
    p = tmp_path / "state.json"
    p.write_text(json.dumps({"instruments": {"NQ": {
        "variant": "Sweep session + V-shape (retest + prise partielle)",
        "patch": {"entry_timing": "retest", "exit_mode": "scale"},
        "reason": "30 trades · WR 43%"}}}), encoding="utf-8")
    st = saved_state(["NQ"], path=str(p))
    assert st["NQ"]["patch"] == {"entry_timing": "retest", "exit_mode": "scale"}
    assert "figé en intraday" in st["NQ"]["reason"]


def test_saved_state_fallback_without_file(tmp_path):
    st = saved_state(["NQ"], path=str(tmp_path / "absent.json"))
    assert st["NQ"]["variant"] == FALLBACK_NAME and st["NQ"]["patch"] == {}


def test_variant_patches_are_explicit_and_distinct():
    # l'étiquette doit rester vraie quels que soient les défauts de config.yaml :
    # chaque variante fixe explicitement entry_timing ET exit_mode, sans doublon
    seen = set()
    for name, patch in VARIANTS:
        assert "entry_timing" in patch and "exit_mode" in patch, name
        key = tuple(sorted(patch.items()))
        assert key not in seen, f"variante dupliquée : {name}"
        seen.add(key)
    assert len(PATCHES) == len(VARIANTS)
