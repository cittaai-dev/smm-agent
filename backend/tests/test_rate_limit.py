import uuid

from app.infra.rate_limit import DataSourceRateLimiter


def test_rate_limit_blocks_after_threshold():
    limiter = DataSourceRateLimiter()
    brand_id = f"brand-{uuid.uuid4().hex[:8]}"

    assert limiter.check(brand_id, "youtube", limit_per_hour=2) is True
    assert limiter.check(brand_id, "youtube", limit_per_hour=2) is True
    assert limiter.check(brand_id, "youtube", limit_per_hour=2) is False


def test_rate_limit_is_scoped_per_brand_and_source():
    limiter = DataSourceRateLimiter()
    brand_a = f"brand-{uuid.uuid4().hex[:8]}"
    brand_b = f"brand-{uuid.uuid4().hex[:8]}"

    assert limiter.check(brand_a, "youtube", limit_per_hour=1) is True
    assert limiter.check(brand_a, "youtube", limit_per_hour=1) is False
    # A different brand's budget is untouched by brand_a exhausting its own.
    assert limiter.check(brand_b, "youtube", limit_per_hour=1) is True
    # A different source for the same brand has its own budget too.
    assert limiter.check(brand_a, "newsapi", limit_per_hour=1) is True
