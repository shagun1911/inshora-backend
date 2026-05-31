"""Backfill broken blog image_url values (local /static paths) with Cloudinary URLs."""

from __future__ import annotations

import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv(Path(__file__).parent / ".env")

MONGODB_URI = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
client = MongoClient(MONGODB_URI)
db = client.inshora
blog_collection = db.blog_posts


def is_broken_image_url(url: str | None) -> bool:
    if not url:
        return True
    if url.startswith("/static/"):
        return True
    if "via.placeholder.com" in url:
        return True
    if url.startswith("http://127.0.0.1") or url.startswith("http://localhost"):
        return True
    return False


def backfill(*, dry_run: bool = False) -> int:
    import openai

    from blog_image import generate_blog_image_url

    openai.api_key = os.getenv("OPENAI_API_KEY")
    posts = list(blog_collection.find().sort("created_at", -1))
    updated = 0

    for post in posts:
        old_url = post.get("image_url")
        if not is_broken_image_url(old_url):
            print(f"OK  {post['_id']} — {post.get('title', '')[:60]}")
            continue

        topic = post.get("title") or "Texas insurance"
        print(f"FIX {post['_id']} — {topic[:60]}")
        print(f"    old: {old_url}")

        if dry_run:
            print("    (dry run — skipped upload)")
            continue

        new_url = generate_blog_image_url(topic)
        blog_collection.update_one({"_id": post["_id"]}, {"$set": {"image_url": new_url}})
        print(f"    new: {new_url}")
        updated += 1

    return updated


if __name__ == "__main__":
    dry_run = "--dry-run" in sys.argv
    count = backfill(dry_run=dry_run)
    print(f"\nUpdated {count} blog post(s).")
