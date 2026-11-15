from datetime import datetime

from app.services import nasa_power


def test_power_history_includes_vulnerability_series(monkeypatch):
    request_params = {}

    class Response:
        def raise_for_status(self):
            pass

        def json(self):
            return {
                "properties": {
                    "parameter": {
                        "T2M": {"20260101": 20.0, "20260102": 21.0},
                        "T2M_MAX": {"20260101": 28.0, "20260102": 29.0},
                        "T2M_MIN": {"20260101": 12.0, "20260102": 13.0},
                        "PRECTOTCORR": {"20260101": 0.0, "20260102": 1.5},
                        "ALLSKY_SFC_SW_DWN": {"20260101": 18.0, "20260102": 19.0},
                        "GWETROOT": {"20260101": 0.24, "20260102": 0.31},
                        "GWETTOP": {"20260101": 0.2, "20260102": 0.25},
                    }
                }
            }

    cache_keys = []
    monkeypatch.setattr(nasa_power, "get_cached", lambda key: None)
    monkeypatch.setattr(
        nasa_power,
        "set_cached",
        lambda key, _value: cache_keys.append(key),
    )
    def fake_get(_url, **kwargs):
        request_params.update(kwargs["params"])
        return Response()

    monkeypatch.setattr(nasa_power.requests, "get", fake_get)

    result = nasa_power.get_power_summary(30.2142, -92.3746, history_days=365)

    assert result["series"] == {
        "dates": ["2026-01-01", "2026-01-02"],
        "temp_c": [20.0, 21.0],
        "temp_max_c": [28.0, 29.0],
        "temp_min_c": [12.0, 13.0],
        "precip_mm": [0.0, 1.5],
        "soil_moisture": [0.24, 0.31],
    }
    assert cache_keys == ["power_vulnerability_v1:30.21:-92.37:365"]
    assert request_params["parameters"].split(",") == [
        "T2M",
        "T2M_MAX",
        "T2M_MIN",
        "PRECTOTCORR",
        "ALLSKY_SFC_SW_DWN",
        "GWETROOT",
        "GWETTOP",
    ]
    assert (
        datetime.strptime(request_params["end"], "%Y%m%d")
        - datetime.strptime(request_params["start"], "%Y%m%d")
    ).days == 364


def test_missing_daily_measurements_remain_unavailable(monkeypatch):
    class Response:
        def raise_for_status(self):
            pass

        def json(self):
            return {
                "properties": {
                    "parameter": {
                        "T2M": {"20260101": 20.0},
                        "T2M_MAX": {"20260101": -999},
                        "T2M_MIN": {"20260101": None},
                        "PRECTOTCORR": {"20260101": 0.0},
                        "ALLSKY_SFC_SW_DWN": {"20260101": 18.0},
                        "GWETROOT": {"20260101": -999},
                        "GWETTOP": {"20260101": 0.2},
                    }
                }
            }

    monkeypatch.setattr(nasa_power, "get_cached", lambda _key: None)
    monkeypatch.setattr(nasa_power, "set_cached", lambda *_args: None)
    monkeypatch.setattr(nasa_power.requests, "get", lambda *_args, **_kwargs: Response())

    result = nasa_power.get_power_summary(30.2142, -92.3746)

    assert result["series"]["temp_max_c"] == [None]
    assert result["series"]["temp_min_c"] == [None]
    assert result["series"]["soil_moisture"] == [None]


def test_nasa_fallback_does_not_fabricate_daily_observations(monkeypatch):
    monkeypatch.setattr(nasa_power, "get_cached", lambda _key: None)
    monkeypatch.setattr(
        nasa_power.requests,
        "get",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(TimeoutError("offline")),
    )

    result = nasa_power.get_power_summary(30.2142, -92.3746)

    assert result["_fallback"] is True
    assert result["series"] == {
        "dates": [],
        "temp_c": [],
        "temp_max_c": [],
        "temp_min_c": [],
        "precip_mm": [],
        "soil_moisture": [],
    }
