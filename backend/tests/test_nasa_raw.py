"""NASA raw-image proxy: parameter building, validation and normalisation (no network)."""
import pytest

from jezero.nasa_raw import Query, UpstreamError, build_params, normalize, normalize_page, safe_url

SAMPLE = {
    "images": [
        {   # shape documented from the public feed
            "extended": {"mastAz": "307.733", "mastEl": "-20.2427", "sclk": "668555815.086",
                         "dimension": "(1648,1200)"},
            "sol": 18, "attitude": "(0.81,-0.01,0.01,0.58)",
            "image_files": {
                "medium": "https://mars.nasa.gov/mars2020-raw-images/pub/ods/surface/sol/00018/x_800.jpg",
                "small": "https://mars.nasa.gov/mars2020-raw-images/pub/ods/surface/sol/00018/x_320.jpg",
                "full_res": "https://mars.nasa.gov/mars2020-raw-images/pub/ods/surface/sol/00018/x.png",
                "large": "https://mars.nasa.gov/mars2020-raw-images/pub/ods/surface/sol/00018/x_1200.jpg"},
            "imageid": "SI0_0018_0668555815_008ECM_N0030578SRLC08001_0000LUJ",
            "camera": {"instrument": "SHERLOC_WATSON", "filter_name": "UNK"},
            "caption": "", "sample_type": "Full", "date_taken_mars": "Sol-00018M17:13:24.434",
            "credit": "NASA/JPL-Caltech", "date_taken_utc": "2021-03-09T09:58:39.213",
            "link": "https://mars.nasa.gov/mars2020/multimedia/raw-images/SI0_0018",
            "drive": "578", "title": "Mars Perseverance Sol 18: WATSON Camera", "site": 3,
            "date_received": "2021-03-09T18:26:55Z",
        },
        {"imageid": "BAD", "image_files": {"small": "https://evil.example.com/x.jpg"}, "camera": {}},
        {"imageid": "THUMB", "sample_type": "Thumbnail", "camera": {"instrument": "NAVCAM_LEFT"},
         "image_files": {"small": "http://mars.nasa.gov/t.jpg"}},
    ],
    "total_results": 123,
}


def test_build_params():
    p = build_params(Query(page=2, per_page=10, sol_min=400, sol_max=700, camera="navcam").validate())
    assert p["feed"] == "raw_images" and p["category"] == "mars2020" and p["feedtype"] == "json"
    assert p["condition_2"] == "400:sol:gte" and p["condition_3"] == "700:sol:lte"
    assert p["search"] == "NAVCAM_LEFT|NAVCAM_RIGHT"
    assert p["num"] == "10" and p["page"] == "2" and p["order"] == "sol desc"


@pytest.mark.parametrize("kw", [dict(per_page=0), dict(per_page=51), dict(sol_min=10, sol_max=5),
                                dict(camera="nope"), dict(order="sideways"), dict(sol_min=-1)])
def test_query_validation(kw):
    with pytest.raises(ValueError):
        Query(**kw).validate()


def test_safe_url():
    assert safe_url("https://mars.nasa.gov/a.jpg") == "https://mars.nasa.gov/a.jpg"
    assert safe_url("http://mars.nasa.gov/a.jpg") == "https://mars.nasa.gov/a.jpg"
    assert safe_url("https://evil.example.com/a.jpg") is None
    assert safe_url("https://nasa.gov.evil.com/a.jpg") is None
    assert safe_url("javascript:alert(1)") is None
    assert safe_url(None) is None


def test_normalize_item():
    n = normalize(SAMPLE["images"][0])
    assert n["sol"] == 18 and n["drive"] == 578 and n["site"] == 3
    assert n["camera_group"] == "sherloc" and n["mast_az_deg"] == pytest.approx(307.733)
    assert n["thumb"].endswith("_320.jpg") and n["full_res"].endswith(".png")
    assert normalize(SAMPLE["images"][1]) is None   # non-NASA URL rejected


def test_normalize_page_filters_thumbnails_and_reports_total():
    page = normalize_page(SAMPLE, Query(full_frame_only=True))
    assert [i["id"] for i in page["images"]] == ["SI0_0018_0668555815_008ECM_N0030578SRLC08001_0000LUJ"]
    assert page["total"] == 123
    with pytest.raises(UpstreamError):
        normalize_page({"oops": True}, Query())
