from app.crawl_plan import build_crawl_plan


def test_full_dataset_crawl_uses_all_targets_and_all_cities() -> None:
    plan = build_crawl_plan({}, [])

    assert plan.target_types == ["category", "brand", "keyword"]
    assert plan.target_slugs_by_type is None
    assert plan.cities == "all"
    assert plan.city_slugs is None
    assert plan.is_scoped is False


def test_selected_target_without_city_still_covers_every_city() -> None:
    plan = build_crawl_plan({"category": ["restaurants"]}, [])

    assert plan.target_types == ["category"]
    assert plan.target_slugs_by_type == {"category": ["restaurants"]}
    assert plan.cities == "all"
    assert plan.city_slugs is None
    assert plan.is_scoped is True


def test_selected_cities_scope_all_targets_to_those_cities() -> None:
    plan = build_crawl_plan({}, ["cairo", "giza"])

    assert plan.target_types == ["category", "brand", "keyword"]
    assert plan.target_slugs_by_type is None
    assert plan.cities == "none"
    assert plan.city_slugs == ["cairo", "giza"]
    assert plan.is_scoped is True
