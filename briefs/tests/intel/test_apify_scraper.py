from __future__ import annotations

from types import SimpleNamespace

import agentcy_briefs.intel.scrapers.apify as apify

# Shaped like johnvc/linkedin-posts-api dataset items: one row per post, plus
# the error and free-tier notice rows the Actor can add to the same dataset.
LINKEDIN_POSTS_ITEMS = [
    {
        "result_type": "post",
        "postId": "7381234567890123456",
        "postUrl": "https://www.linkedin.com/posts/example-founder_activity-7381234567890123456",
        "postType": "post",
        "datePosted": "2026-10-20T14:05:00.000Z",
        "text": "Our brand kit is live.",
        "hashtags": ["#branding"],
        "authorName": "Example Founder",
        "authorUrl": "https://www.linkedin.com/in/example-founder",
        "authorType": "Person",
        "numLikes": 128,
        "numComments": 14,
        "numShares": 6,
        "fromCache": False,
        "fetched_at": "2026-10-23T09:00:00.000000+00:00",
    },
    {
        "result_type": "post",
        "postId": "7379876543210987654",
        "postUrl": "https://www.linkedin.com/posts/example-founder_activity-7379876543210987654",
        "postType": "post",
        "datePosted": "2026-10-14T08:30:00.000Z",
        "text": "Notes from the workshop.",
        "numLikes": 41,
        "numComments": 3,
        "fromCache": True,
        "fetched_at": "2026-10-22T18:00:00.000000+00:00",
    },
    {
        "result_type": "error",
        "sourceUrl": "https://www.linkedin.com/in/example-founder",
        "error_message": "No post returned for this source.",
        "error_type": "CollectionError",
        "fetched_at": "2026-10-23T09:00:01.000000+00:00",
    },
    {
        "free_tier_notice": True,
        "message": "Free monthly allowance reached for this Actor.",
    },
]


def test_scrape_linkedin_maps_linkedin_posts_api_rows(monkeypatch) -> None:
    captured: dict[str, object] = {}

    class FakeActor:
        def call(self, *, run_input):
            captured["run_input"] = run_input
            return {"defaultDatasetId": "dataset-1"}

    class FakeClient:
        def actor(self, actor_id):
            captured["actor_id"] = actor_id
            return FakeActor()

        def dataset(self, dataset_id):
            captured["dataset_id"] = dataset_id
            return SimpleNamespace(iterate_items=lambda: iter(LINKEDIN_POSTS_ITEMS))

    monkeypatch.setattr(apify, "get_apify_client", FakeClient)

    posts = apify.scrape_posts("linkedin", "example-founder", limit=10)

    assert captured["actor_id"] == "johnvc/linkedin-posts-api"
    assert captured["run_input"] == {
        "profileUrls": ["https://www.linkedin.com/in/example-founder/"],
        "maxPostsPerProfile": 10,
    }
    assert captured["dataset_id"] == "dataset-1"
    assert posts == [
        {
            "platform": "linkedin",
            "id": "7381234567890123456",
            "text": "Our brand kit is live.",
            "created_at": "2026-10-20T14:05:00.000Z",
            "likes": 128,
            "comments": 14,
            "reposts": 6,
            "url": "https://www.linkedin.com/posts/example-founder_activity-7381234567890123456",
        },
        {
            "platform": "linkedin",
            "id": "7379876543210987654",
            "text": "Notes from the workshop.",
            "created_at": "2026-10-14T08:30:00.000Z",
            "likes": 41,
            "comments": 3,
            "reposts": 0,
            "url": "https://www.linkedin.com/posts/example-founder_activity-7379876543210987654",
        },
    ]
