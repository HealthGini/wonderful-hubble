# Workspace Guidelines for GoodDeeds.space

## Automated Regression Prevention Rules

1. **Test-Driven Regression Enforcer**:
   - Every user feature or UI fix must be backed by an explicit assertion in `tests/test_regression_coverage.py`.
   - Before completing any task, `./run_tests.sh` must be executed and verified 100% OK (83+ tests passing).

2. **Attachment Opening Handler Integrity**:
   - `openAttachment(url, filename)` in `static/app.js` must be preserved and bound to `window.openAttachment`.
   - Attachment buttons in `renderFeedCard(item)` must invoke `openAttachment(window._attachmentCache[cacheKey], ...)` to support Base64 file Blob URLs.

3. **Feed Space Filter Structure**:
   - The `#feed-group-select` dropdown must feature `⭐ My Spaces (All Joined)` as default for authenticated users, with optgroups for `My Joined Spaces` and `Other Community Spaces`.

4. **Terminology Consistency**:
   - Consistently use "Spaces" and "Space" across user-facing HTML and JS.
   - Use "Kudos" and "Posts" (without "Hub").
   - Use "Looking for your Kudos or Posts?" in profile banners.

5. **Subagent Merge Integrity**:
   - When merging subagent implementations, always diff modified files against `head` to ensure no helper functions or custom renderers are overwritten.
