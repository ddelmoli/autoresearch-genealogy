#!/usr/bin/env python3
"""Pins new_records_scan.fetch_since (added 14 OCT 2026).

WHAT IS BEING DEFENDED.
  The scan used ONE feed page of 8 posts. The feed's search query also matches the
  blog's non-collection weekly posts, so 8 posts reached back about three weeks,
  against a baseline 13 weeks old. The scan printed a clean "no new post" while a
  post naming a new collection for a watched county sat in the unread gap.

  1. It pages back until a post at or before the baseline date has been read.
  2. When the feed ends (or the page cap hits) first, `reached` is False, so the
     caller reports an INCOMPLETE window instead of a zero.
  3. With no baseline (first run), one exhausted feed counts as complete.
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import new_records_scan as nrs  # noqa: E402


def make_feed(dates):
    """dates newest-first; returns a fetch(start) serving PAGE-sized slices."""
    posts = [{"published": {"$t": d + "T12:00:00Z"}, "title": {"$t": "Added and Updated Ancestry"},
              "id": {"$t": "post-" + d}, "content": {"$t": ""}} for d in dates]

    def fetch(start):
        return {"feed": {"entry": posts[start - 1:start - 1 + nrs.PAGE]}}
    return fetch


def weekly(n, newest_day=300):
    import datetime
    base = datetime.date(2026, 1, 1)
    return [(base + datetime.timedelta(days=newest_day - 3 * i)).isoformat() for i in range(n)]


class FetchSince(unittest.TestCase):
    def test_pages_back_to_the_baseline(self):
        dates = weekly(60)            # ~6 months of posts at 3 a week
        base = dates[40]              # baseline sits on the second page
        raw, reached = nrs.fetch_since(base, fetch=make_feed(dates))
        self.assertTrue(reached)
        self.assertGreater(len(raw), nrs.PAGE)
        self.assertLessEqual(min(e["published"]["$t"] for e in raw)[:10], base)

    def test_feed_ends_before_the_baseline_is_incomplete(self):
        dates = weekly(30)
        raw, reached = nrs.fetch_since("2020-01-01", fetch=make_feed(dates))
        self.assertFalse(reached)
        self.assertEqual(len(raw), 30)

    def test_first_run_without_baseline(self):
        raw, reached = nrs.fetch_since(None, fetch=make_feed(weekly(10)))
        self.assertTrue(reached)
        self.assertEqual(len(raw), 10)


if __name__ == "__main__":
    unittest.main()
