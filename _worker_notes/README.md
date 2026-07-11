# Interactive Space Calendar & PDF Scraping Documentation

## What Works
- **Interactive Space Calendar Layout & Widget (`#group-calendar-widget`)**: Responsive right sidebar (`lg:col-span-1`) in space details (`#view-group-detail`) displaying a 7-column weekday and day cells grid (`#calendar-days-grid`), month/year header (`#calendar-month-header`), and navigation buttons (`< Prev`, `Next >`).
- **Admin Action Bar (`#calendar-admin-action-bar` / `#admin-calendar-actions`)**: Automatically visible to space admins and site admins (`is_admin == 1` or `is_site_admin == 1`). Provides `+ Add Event` button and `📄 Upload PDF Calendar` button.
- **Quick Event Creation (`#modal-add-event`)**: Allows creating space events with title, event date, optional time, description, and optional attachment. Submits via `POST /api/posts` (`item_type: "POST"`, `post_subtype: "EVENT"`, `event_date`, `group_ids: [activeGroupData.id]`).
- **PDF Calendar Scraping (`POST /api/groups/<gid>/scrape_calendar`)**: Extracts text lines/tokens from base64 PDF or resource URIs via `extract_resource_text()`. Parses dates (ISO, US, and Natural formats) and surrounding text (title, time, description) via `parse_calendar_events_from_text` / `parse_scraped_calendar_events`.
- **Scraped Events Preview & Import (`#modal-scrape-preview`)**: Displays scraped suggested events (`#scrape-preview-list`) with checkboxes (`scraped-event-checkbox`) and editable fields so admins can review and batch import selected events directly into the space calendar (`confirmImportScrapedEvents()`).
- **Day Events Modal (`#modal-calendar-day`)**: Displays all events and resources scheduled on a clicked date (`showCalendarDayEvents(dateStr)`). Attachment buttons strictly comply with Rule 2 (`_attachmentCache` + `openAttachment(...)` + `formatAttachmentLabel(url, 0, 1)`).

## What Doesn't Work / Limitations
- None. All automated regression and integration tests pass cleanly (`Ran 92 tests in ~1.3s. OK`).

## How to Run Tests
From the workspace root directory, execute:
```bash
./run_tests.sh
```
All 92+ tests run cleanly with `OK`.
