from app.engine._reference import load_crops, load_rules, validate_reference


def test_reference_tables_are_consistent():
    assert validate_reference() == []


def test_every_crop_pair_has_a_rule():
    crops, rules = load_crops(), load_rules()
    assert len(rules) == len(crops) ** 2


def test_same_crop_back_to_back_is_excluded():
    for c, rule in ((c, load_rules()[(c, c)]) for c in load_crops()):
        assert rule["allowed"] is False


def test_legume_after_heavy_feeder_scores_highest():
    r = load_rules()
    assert r[("wheat", "berseem_clover")]["soil_score"] == 1.0
    assert r[("wheat", "maize")]["soil_score"] < r[("wheat", "berseem_clover")]["soil_score"]


def test_every_crop_has_source_and_reliability():
    for name, c in load_crops().items():
        assert c["source"] and c["reliability"], name
