"""Brand lookup must not depend on filesystem case sensitivity."""

from agentcy_briefs.core import brands


def test_resolve_brand_is_case_insensitive(tmp_path, monkeypatch):
    brand_dir = tmp_path / "acme"
    brand_dir.mkdir()
    (brand_dir / "brand.yml").write_text("name: Acme\n")
    monkeypatch.setattr(brands, "get_brands_dir", lambda: tmp_path)

    assert brands.resolve_brand("Acme").samefile(brand_dir)
    assert brands.resolve_brand("acme").samefile(brand_dir)
    assert brands.resolve_brand("missing") is None
    assert brands.load_brand_config("ACME") == {"name": "Acme"}
