# GoodDeeds.space — Community Gratitude & Spaces Platform

GoodDeeds.space is a full-stack community platform designed around celebrating acts of kindness (**Kudos**), sharing community **Posts**, organizing **Events & Resources**, and collaborating inside topic-based **Spaces**.

## 📊 Verification & Test Status
- **128/128** Automated Unit & Integration Tests Passing 100% OK (`./run_tests.sh`).
- Zero external framework bloat: Pure Python standard-library HTTP server + SQLite backend with a responsive Tailwind CSS Single-Page Application (SPA).

---

## 🏗️ Architecture Overview

- **Backend (`server.py`, `handlers.py`, `database.py`)**:
  - Multi-threaded HTTP server with RESTful JSON API routes (`/api/*`).
  - SQLite persistence (`gooddeeds.db`) with automated schema migration and demo seed data.
  - Multi-modal authentication: **WebAuthn Passkeys** (`fido2`), **Google OAuth 2.0**, and **Email/Password** sessions.
  - Real-time/Simulated SMTP email notifications (`email_outbox` audit log).
- **Frontend SPA (`static/index.html`, `static/app.js`, `static/style.css`)**:
  - Client-side hash router (`/#/feed`, `/#/groups`, `/#/group/<id>`, `/#/profile`, `/#/moderation`).
  - Interactive Spaces with **Posts & Kudos**, **Resources & Events Calendar**, **Chat Board**, and **Members List**.
  - Support for multi-link & Base64 file attachments with client-side Blob preview (`window.openAttachment`).

---

## 📈 Google Analytics (GA4) Integration & Accessing Metrics

GoodDeeds.space integrates **Google Analytics 4 (`gtag.js`)** in [`static/index.html`](static/index.html) and tracks both Single-Page Application (SPA) route transitions (`trackAnalyticsPageView`) and custom user actions (`trackAnalyticsEvent`, such as `give_kudos`) in [`static/app.js`](static/app.js).

### 1. View Live Reports in the Google Analytics Dashboard
1. **Create a GA4 Property & Get Your Measurement ID**:
   - Visit [analytics.google.com](https://analytics.google.com/) → **Admin (⚙️)** → **Create Property** → **Web**.
   - Copy your **Measurement ID** (format: `G-XXXXXXXXXX`).
2. **Configure Your Measurement ID**:
   - Open [`static/index.html`](static/index.html) and replace `G-GOODDEEDS` (lines 8 and 13) with your real `G-XXXXXXXXXX` ID.
3. **Access Realtime & Historical Metrics**:
   - In Google Analytics, open **Reports** → **Realtime overview** to monitor active users, virtual pageviews (`/#/feed`, `/#/groups`, `/#/profile`, `/#/moderation`), and custom events (`give_kudos`).

### 2. Inspect Analytics Events Locally in Browser DevTools
Even without a live GA4 property connected, every pageview and custom event is pushed into `window.dataLayer`:
1. Open the site in Chrome and launch **DevTools** (`F12` → **Console**).
2. Run:
   ```javascript
   window.dataLayer
   ```
3. Expand the array entries to inspect the exact `page_view` and `give_kudos` payloads emitted as you navigate.

---

## 🛡️ Moderation & Safety Features

GoodDeeds.space includes a three-tiered moderation and safety system to protect community integrity:

### 1. Direct Admin & Moderator Controls
- **User Account Suspension & Ban (`POST /api/admin/users/<id>/ban`)**:
  - Site Admins can click **🚫 Suspend User** on any user's profile page (or **✅ Restore User** for suspended accounts).
  - Immediately invalidates active session tokens (`DELETE FROM sessions WHERE user_id = ?`), blocks future logins (`403 Account suspended by site administration`), and optionally purges all authored posts, comments, and chat messages.
- **Space Member Removal & Space Bans (`POST /api/groups/<gid>/members/kick`)**:
  - Space Admins and Site Admins can **Kick** or **Ban from Space** any member from a Space's **Members List** (`roster` tab).
  - Banned users are recorded in `group_bans` and prevented from re-joining (`POST /api/groups/<gid>/join` returns `403`).
- **Granular Content Deletion**:
  - Authors, Space Admins, and Site Admins can delete individual comments (`DELETE /api/comments/<cid>`) and Space Chat Board messages (`DELETE /api/groups/<gid>/chat/<mid>`).

### 2. Community Content Reporting & Admin Queue
- **1-Click Community Reporting (`#modal-report-content` & `POST /api/reports`)**:
  - Users can click **🚩 Report** on any post, kudos, comment, or chat message to flag violations (*Spam / Bot Activity*, *Harassment / Abuse*, *Off-topic / Misleading*, *Inappropriate Content*).
- **Site Admin Moderation Queue (`/#/moderation` & `GET /api/admin/reports`)**:
  - Accessible via the **🛡️ Moderation Queue** link (`#nav-moderation-link`) in the Site Admin profile dropdown.
  - Displays reported content with context previews and 1-click resolution actions (`POST /api/admin/reports/<rid>/resolve`):
    - **✅ Dismiss Report**: Closes the report without altering content.
    - **🗑️ Delete Content**: Removes the reported post, comment, or chat message.
    - **🚫 Delete & Ban Author**: Deletes the reported content, suspends the author's account, purges their content, and resolves the report.

### 3. Automated Safety Guardrails
- **Server-Side Keyword Filter & Rate Limiter (`check_content_moderation`)**:
  - Automatically enforced across `POST /api/kudos`, `POST /api/posts`, `POST /api/comments`, and `POST /api/groups/<gid>/chat`.
  - Immediately blocks known spam/malicious phrases (`400 Bad Request`) and enforces per-user rate limits against automated floods.

---

## 🚀 Running Locally & Testing

### Start the Server
```bash
python3 server.py
```
The server listens on `http://0.0.0.0:8080`.

### Run the Automated Test Suite
```bash
./run_tests.sh
```
Executes all 128 unit, API integration, and UI regression tests across `tests/`.


