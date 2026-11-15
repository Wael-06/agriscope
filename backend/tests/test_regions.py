from app.api.regions import get_regions


def test_regions_include_egypt_usa_and_china_model_sites():
    regions = get_regions()
    countries = {region["country"] for region in regions}
    country_regions = {
        region["country"]: region
        for region in regions
        if region["country"] in {"USA", "CHINA"}
    }

    assert {"EGYPT", "USA", "CHINA"} <= countries
    assert len(regions) == 29
    assert all(region.get("default_crop") for region in regions)
    assert all(region["lat"] and region["lon"] for region in regions)
    assert set(country_regions["USA"]["supported_crops"]) == {
        "wheat", "maize", "rice", "tomato", "cotton", "sugarcane", "date_palm"
    }
    assert set(country_regions["CHINA"]["supported_crops"]) == {
        "wheat", "maize", "rice", "tomato", "cotton", "sugarcane"
    }
    assert set(country_regions["USA"]["suitability_crops"]) == {"maize", "cotton"}
    assert set(country_regions["CHINA"]["suitability_crops"]) == {
        "wheat", "maize", "rice"
    }
