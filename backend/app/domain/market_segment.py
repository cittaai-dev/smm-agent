from pydantic import BaseModel


class MarketSegment(BaseModel):
    """Explicit whitelist of where competitor discovery is allowed to look --
    never open-ended crawling (step5_trust_boundary.md Part D §5). Set up by
    a human (Team Lead) once per brand."""

    brand_id: str
    segment_name: str
    youtube_channel_keywords: list[str] = []
    news_sources: list[str] = []
    reddit_communities: list[str] = []
    website_urls: list[str] = []
    max_competitors_to_track: int = 10
