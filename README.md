# GoodDeeds.space

GoodDeeds.space is a community-focused web application designed to promote goodness, build meaningful connections, and facilitate mutual aid. With a warm, accessible, and senior-friendly design philosophy, it connects volunteers, organizers, and neighbors to support each other.

## 📊 Verification & Test Status
- **132/132** Automated Unit & Integration Tests Passing 100% OK (`./run_tests.sh`).
- Zero external framework bloat: Pure Python standard-library HTTP server + SQLite backend with a responsive Tailwind CSS Single-Page Application (SPA).

---

## System Overview & Mission

The core mission of GoodDeeds.space is to encourage small acts of kindness that ripple outward to transform neighborhoods. The platform is designed to be accessible to all age groups, particularly seniors, featuring:
*   **Warm Aesthetics**: Inviting and easy-to-read interface.
*   **Intergenerational Connection**: Facilitating mentorship and support between youth and seniors.
*   **Low Barrier to Entry**: Simple workflows for posting help requests, sharing inspiring stories, and giving thanks (Kudos).

### Core Capabilities
- **Unified Social Feed**: A merged stream of Kudos (appreciation) and Posts (information/stories) sorted using a "smart sort" algorithm that prioritizes items from Spaces the user has joined and items with high engagement.
- **Spaces**: Dedicated sub-communities where members can chat on the **Chat Board**, share curated resources & events, and invite others.
- **Real-Time In-App Notifications**: Bell dropdown with live unread badges, 15-second background polling, and instant toast alerts for new Kudos, Comments, and Space Invitations.
- **Multi-Modal Authentication**: Support for WebAuthn Passkeys (`fido2`), Google OAuth 2.0, and standard Email/Username + Password sessions.
- **Three-Tiered Moderation & Safety System**: Direct Admin Controls, Community Content Reporting & Admin Moderation Queue (`/#/moderation`), and Automated Server-Side Safety Guardrails.
- **Google Analytics (GA4)**: Integrated SPA pageview and custom event tracking (`gtag.js` + `window.dataLayer`).
- **Simulated & Real Communications**: Integrated email notifications for kudos and invitations, with a built-in outbox viewer for testing.

---

## Architecture & Directory Structure

The application is built on the Python 3.13 standard library and uses SQLite for data persistence.

```
├── database.py         # Database schema, initialization, and demo data seeding
├── handlers.py         # Core API request handlers, auth, moderation, and business logic
├── server.py           # Threaded HTTP server routing API and serving static files
├── run.sh              # Shell script to start the server
├── run_tests.sh        # Shell script to run the automated test suite (132 tests)
├── static/             # Frontend assets
│   ├── index.html      # Single Page Application (SPA) entry point
│   ├── app.js          # Frontend application logic (vanilla JS)
│   └── style.css       # Custom styles
└── tests/              # Unit and integration test suite
    ├── base_test.py    # Base test case class with helpers
    ├── test_database.py# Database initialization and seeding tests
    ├── test_auth.py    # Authentication flow tests
    ├── test_feed.py    # Feed sorting, filtering, and search tests
    ├── test_posts.py   # Posts/Kudos creation, comments, and reactions tests
    ├── test_groups.py  # Space management, chat, and resources tests
    ├── test_invitations.py # Space invitations flow tests
    ├── test_spotlight.py # Spotlight and rotation tests
    ├── test_regression_coverage.py # Comprehensive regression & moderation tests
    └── test_suite.py   # Test suite runner and discoverer
```

### Component Roles
*   **`server.py`**: Listens on a specified port (default 8080). Routes requests starting with `/api/` to `handlers.handle_api_request` and serves static files from the `static/` directory for other requests.
*   **`database.py`**: Manages the SQLite database (`gooddeeds.db`). Defines the schema (15+ tables including `group_bans` and `content_reports`) and populates realistic demo data on the first run.
*   **`handlers.py`**: Parses incoming HTTP requests, performs authentication checks, executes database queries, enforces automated safety guardrails (`check_content_moderation`), handles simulated/real email delivery, and returns JSON responses.
*   **`static/`**: A pure HTML5/CSS3/Vanilla JS single-page application (SPA).

---

## Startup Guide

### Prerequisites
*   Python 3.13 (or compatible Python 3 version)

### Database Initialization
The database initializes automatically when you start the server for the first time. If you wish to initialize or reset it manually, run:
```bash
python3 database.py
```
This will create `gooddeeds.db` and seed it with sample users, Spaces, posts, reactions, comments, and invitations.

### Configuration (Environment Variables)
You can configure the server using the following environment variables:

| Variable | Description | Default |
| :--- | :--- | :--- |
| `PORT` | Port number the HTTP server listens on | `8080` |
| `DB_PATH` | Path to the SQLite database file | `gooddeeds.db` (next to script) |
| `SMTP_HOST` | Hostname of the live SMTP server (optional) | *None* |
| `SMTP_PORT` | Port of the live SMTP server | `587` |
| `SMTP_USER` | SMTP username for authentication | *None* |
| `SMTP_PASSWORD`| SMTP password for authentication | *None* |
| `SMTP_FROM_EMAIL`| Sender email address | `notifications@gooddeeds.space`|
| `SMTP_FROM_NAME`| Sender display name | `GoodDeeds Community` |

### Running the Server
Start the server by executing:
```bash
python3 server.py
```
Or use the helper script:
```bash
./run.sh
```
Once running, open your browser and navigate to `http://localhost:8080` to access the application.

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

### 4. CSRF & XSS Protection on State-Changing Endpoints
- **Cross-Site Request Forgery (CSRF) Defense**:
  - **Explicit Bearer Token Auth**: API endpoints authenticate via an explicit `Authorization: Bearer <token>` HTTP header (stored in `localStorage`, never ambient cookies). Because browsers never attach custom `Authorization` headers to cross-site `<form>` submissions or cross-origin requests without preflight, endpoints are inherently immune to cookie-based CSRF.
  - **Server-Side Origin Validation**: In addition, `handle_api_request` in [`handlers.py`](handlers.py) enforces strict `Origin` / `Host` header matching on all state-changing requests (`POST`, `PUT`, `DELETE`). Cross-origin requests with a mismatched `Origin` are immediately rejected with `403 Forbidden: CSRF Origin mismatch.`
- **Cross-Site Scripting (XSS) Sanitization**:
  - All user-generated text fields (post titles/content, comments, chat messages, usernames, report notes) are sanitized via `escapeHtml(...)` in [`static/app.js`](static/app.js) before DOM insertion.

---

## REST API Reference

All API requests and responses are in JSON format. Authenticated requests require the `Authorization: Bearer <token>` header.

### Authentication Endpoints

#### `POST /api/auth/signup`
Creates a new user account.
*   **Payload**:
    ```json
    {
      "email": "user@example.com",
      "username": "NewUser",
      "password": "securepassword",
      "phone": "555-0199",
      "avatar_url": "https://example.com/avatar.png",
      "bio": "Hello community!"
    }
    ```
*   **Response (201 Created)**:
    ```json
    {
      "token": "uuid-session-token",
      "user": { "id": 5, "email": "user@example.com", "username": "NewUser", ... }
    }
    ```

#### `POST /api/auth/login`
Authenticates a user and returns a session token. Supports login via email or username. Returns `403` if the account is suspended by site administration.
*   **Payload**:
    ```json
    {
      "email": "NewUser",
      "password": "securepassword"
    }
    ```
*   **Response (200 OK)**:
    ```json
    {
      "token": "uuid-session-token",
      "user": { ... }
    }
    ```

#### `POST /api/auth/oauth/google`
Authenticates or signs up a user via Google OAuth ID token credential.

#### `POST /api/auth/webauthn/register/challenge` & `POST /api/auth/webauthn/register/verify`
Registers a WebAuthn Passkey device for passwordless login.

#### `POST /api/auth/webauthn/login/challenge` & `POST /api/auth/webauthn/login/verify`
Authenticates a user using an existing WebAuthn Passkey.

#### `POST /api/auth/logout`
Terminates the current session. Requires authentication.
*   **Response (200 OK)**: `{"success": true}`

#### `GET /api/auth/me`
Retrieves details of the currently authenticated user. Requires authentication.
*   **Response (200 OK)**: `{"user": { ... }}`

---

### Feed & Interaction Endpoints

#### `GET /api/feed`
Retrieves a list of posts and kudos.
*   **Query Parameters**:
    *   `sort`: `smart` (default, weights by Space membership and reactions) or `recent`.
    *   `theme`: Filter by specific theme (e.g., "Mental Health").
    *   `subtype`: Filter by post subtype (`EVENT` or `RESOURCE`).
    *   `group_id`: Filter items tagged to a specific Space (`my_spaces` or Space ID).
    *   `search`: Search text in title, content, extracted PDF text, or username.
    *   `filter_type`: Filter by type (`KUDOS` or `POST`).

#### `POST /api/kudos`
Creates a new Kudos thanking another user. Checked against automated safety guardrails. Requires authentication.
*   **Payload**:
    ```json
    {
      "recipient_id": 2,
      "content": "Thank you for the help!",
      "group_ids": [1, 3]
    }
    ```
*   **Response (201 Created)**: `{"item": { ... }, "success": true}`

#### `POST /api/posts`
Creates a new community post, event, or resource. Checked against automated safety guardrails. Requires authentication.
*   **Payload**:
    ```json
    {
      "title": "Community Garden",
      "theme": "Community Services",
      "content": "Let's start a garden!",
      "resource_url": "https://example.com/garden_plan.pdf",
      "post_subtype": "EVENT",
      "event_date": "2026-10-15",
      "group_ids": [3]
    }
    ```
*   **Response (201 Created)**: `{"item": { ... }, "success": true}`

#### `PUT /api/posts/<id>` & `DELETE /api/posts/<id>`
Updates or deletes an existing post/event. Allowed for the post author or site admin.

#### `POST /api/reactions`
Toggles an emoji reaction on a feed item. Requires authentication.
*   **Payload**:
    ```json
    {
      "item_id": 1,
      "emoji": "❤️"
    }
    ```
*   **Response (200 OK)**: `{"success": true, "action": "added|removed"}`

#### `POST /api/comments` & `DELETE /api/comments/<id>`
Adds or deletes a comment on a feed item. Deletion is permitted for the comment author, Space admin, or site admin.

---

### Space Endpoints

#### `GET /api/groups`
Retrieves all Spaces, optionally filtered by search query or theme.
*   **Query Parameters**: `search`, `theme`, `joined` (true/false)
*   **Response (200 OK)**: `{"groups": [...]}`

#### `POST /api/groups`
Creates a new Space. The creator is automatically added as Space admin. Requires authentication.

#### `GET /api/groups/<id>`
Retrieves detailed metadata for a Space, including roster, resources, Chat Board messages, and invitations.

#### `POST /api/groups/<id>/join` & `POST /api/groups/<id>/leave`
Joins or leaves a Space. Returns `403` if the user has been banned from the Space.

#### `POST /api/groups/<id>/members/kick`
Kicks or bans a member from a Space (`{"user_id": 3, "ban": true, "reason": "..."}`). Requires Space Admin or Site Admin privileges.

#### `POST /api/groups/<id>/resources`
Adds curated resources to a Space. Requires Space Admin privileges.

#### `POST /api/groups/<id>/chat` & `DELETE /api/groups/<id>/chat/<mid>`
Posts or deletes a message on the Space's Chat Board.

---

### Space Invitations

#### `POST /api/groups/<id>/invite`
Invites users to join a Space. Sends an email (real or simulated) to recipients. Requires authentication.

#### `GET /api/invitations/pending`
Retrieves pending Space invitations for the currently authenticated user.

#### `POST /api/invitations/respond`
Accepts or declines a pending Space invitation.

---

### Real-Time In-App Notifications Endpoints

#### `GET /api/notifications`
Retrieves the authenticated user's recent in-app notifications (Kudos received, Comments on posts, Space Invitations) along with `unread_count`. Polled every 15 seconds by the frontend navbar dropdown.

#### `POST /api/notifications/read`
Marks all notifications (`{}`) or a specific notification (`{"id": 12}`) as read (`is_read = 1`).

---

### Moderation & Admin Endpoints

#### `POST /api/admin/users/<id>/ban`
Suspends (`ban: true`) or restores (`ban: false`) a user account across the platform, optionally purging all their authored content (`purge_content: true`). Requires Site Admin status.

#### `POST /api/reports`
Submits a community report on a post, kudos, comment, or chat message (`target_type`, `target_id`, `reason`, `notes`).

#### `GET /api/admin/reports` & `POST /api/admin/reports/<id>/resolve`
Lists open community content reports and resolves them via `dismiss`, `delete_content`, or `ban_author`. Requires Site Admin status.

---

## Simulated Audit Logs & Support

### Simulated Outbox (`/#/outbox`)
Since SMTP servers might not be configured in local development, all emails sent by the system (kudos notifications, Space invitations, support confirmations) are logged to the `email_outbox` table.
*   **API**: `GET /api/outbox`
*   **UI Access**: Navigate to `/#/outbox` in the application to view the simulated outgoing mail log. This is useful for verifying invitations and notifications without live SMTP setup.

### Customer Support Portal
Users can submit inquiries which log to `customer_service_inquiries`.
*   **Submit API**: `POST /api/support`
*   **View API (Admin)**: `GET /api/support`
*   On submission, a confirmation email is sent to the user, and an alert email is sent to `roht_kgupta@yahoo.com` (both visible in the Simulated Outbox).

---

## Running the Testing Suite

The testing suite verifies all 128 unit, API integration, and UI regression tests using isolated temporary databases.

### Running with the Helper Script
Ensure the script is executable, then run it:
```bash
chmod +x run_tests.sh
./run_tests.sh
```

### Running manually with python
You can run the test suite runner directly:
```bash
python3 tests/test_suite.py
```

Or run via unittest discovery:
```bash
python3 -m unittest discover -s tests -p "test_*.py" -v
```

---

## Going Live & Production Deployment

This guide outlines the steps required to transition GoodDeeds.space from a local development environment to a production-ready, high-concurrency cloud deployment.

### Interim Step: SQLite WAL Mode & ASGI (FastAPI) Blueprint

Before transitioning to a managed MySQL cluster, two intermediate architectural steps ensure high performance and maintainability as routes grow:

#### 1. SQLite Write-Ahead Logging (WAL) & Lock Contention Prevention
To prevent `sqlite3.OperationalError: database is locked` under concurrent multi-threaded HTTP requests, [`database.py`](database.py) (`get_db()`) explicitly configures every SQLite connection with:
```python
conn = sqlite3.connect(DB_PATH, timeout=30.0)
conn.execute("PRAGMA foreign_keys = ON")
conn.execute("PRAGMA journal_mode = WAL")
conn.execute("PRAGMA synchronous = NORMAL")
conn.execute("PRAGMA busy_timeout = 5000")
```
- **`WAL` mode** allows concurrent reads while a write transaction is in progress.
- **`busy_timeout = 5000`** instructs SQLite to queue concurrent writers for up to 5 seconds instead of failing immediately.

#### 2. Migrating the Routing Layer to FastAPI / ASGI
As the API surface grows, migrating the custom `http.server` routing loop in `server.py` / `handlers.py` to **FastAPI** provides asynchronous I/O, automatic **Pydantic** request validation, and interactive **OpenAPI (`/docs`)** documentation:
```python
# Example FastAPI ASGI wrapper over modular handlers
from fastapi import FastAPI, Request, HTTPException
from fastapi.staticfiles import StaticFiles
import uvicorn

app = FastAPI(title="GoodDeeds.space API", version="2.0.0")
app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/api/feed")
async def get_feed(sort: str = "smart", theme: str = None, group_id: str = None):
    # Delegate to enriched feed query logic
    ...
```

---

### 1. Migrating from SQLite to MySQL

For production environments, migrating from SQLite to a robust relational database like MySQL is essential to support high concurrency, better performance, and scalability.

#### Database Drivers & Code Changes
To connect to MySQL, you will need a Python MySQL driver. Recommended options:
*   `mysql-connector-python`: Official Oracle driver.
*   `PyMySQL`: A pure-Python MySQL client.

Since the application uses standard Python database API (DB-API) compatibility, changes in `database.py` and `handlers.py` will involve replacing `sqlite3` imports and connections with the chosen MySQL driver.

Example using `mysql-connector-python`:
```python
import mysql.connector
import os

def get_db_connection():
    return mysql.connector.connect(
        host=os.environ.get('DB_HOST', 'localhost'),
        user=os.environ.get('DB_USER'),
        password=os.environ.get('DB_PASSWORD'),
        database=os.environ.get('DB_NAME', 'gooddeeds'),
        port=int(os.environ.get('DB_PORT', 3306))
    )
```

#### Schema Datatype Differences
When migrating the schema from SQLite to MySQL, note the following differences:

| Feature | SQLite | MySQL |
| :--- | :--- | :--- |
| **Auto-Increment** | `INTEGER PRIMARY KEY AUTOINCREMENT` | `INT AUTO_INCREMENT PRIMARY KEY` |
| **Default Timestamp** | `DATETIME DEFAULT CURRENT_TIMESTAMP` | `TIMESTAMP DEFAULT CURRENT_TIMESTAMP` |
| **Foreign Keys** | Enabled via `PRAGMA foreign_keys = ON;` | Supported natively (ensure InnoDB engine is used) |
| **Boolean** | Represented as `INTEGER` (0 or 1) | `TINYINT(1)` or `BOOLEAN` |
| **Strings/Text** | Dynamic length `TEXT` | Requires defined limits for indexed columns. Use `VARCHAR(255)` for keys/emails, `TEXT` for content. |

#### MySQL Production Schema (DDL)

Execute the following DDL script on your MySQL instance to initialize the database:

```sql
CREATE TABLE users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    email VARCHAR(255) UNIQUE NOT NULL,
    username VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    phone VARCHAR(50),
    avatar_url VARCHAR(512),
    bio TEXT,
    is_site_admin TINYINT DEFAULT 0,
    is_banned TINYINT DEFAULT 0,
    oauth_provider VARCHAR(50),
    oauth_id VARCHAR(255),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE sessions (
    token VARCHAR(255) PRIMARY KEY,
    user_id INT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE groups (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(255) UNIQUE NOT NULL,
    description TEXT,
    themes TEXT, -- Stores JSON array as string (MySQL JSON type can also be used)
    icon_url VARCHAR(512),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE group_members (
    group_id INT NOT NULL,
    user_id INT NOT NULL,
    is_admin TINYINT DEFAULT 0,
    joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (group_id, user_id),
    FOREIGN KEY (group_id) REFERENCES groups(id) ON DELETE CASCADE,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE group_bans (
    group_id INT NOT NULL,
    user_id INT NOT NULL,
    banned_by INT,
    reason TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (group_id, user_id),
    FOREIGN KEY (group_id) REFERENCES groups(id) ON DELETE CASCADE,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE group_resources (
    id INT AUTO_INCREMENT PRIMARY KEY,
    group_id INT NOT NULL,
    title VARCHAR(255) NOT NULL,
    url VARCHAR(512) NOT NULL,
    resource_type VARCHAR(50) DEFAULT 'URL',
    theme VARCHAR(100) DEFAULT 'Community Resources',
    added_by INT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (group_id) REFERENCES groups(id) ON DELETE CASCADE,
    FOREIGN KEY (added_by) REFERENCES users(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE group_messages (
    id INT AUTO_INCREMENT PRIMARY KEY,
    group_id INT NOT NULL,
    user_id INT NOT NULL,
    message TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (group_id) REFERENCES groups(id) ON DELETE CASCADE,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE feed_items (
    id INT AUTO_INCREMENT PRIMARY KEY,
    item_type VARCHAR(50) NOT NULL, -- 'KUDOS' or 'POST'
    author_id INT NOT NULL,
    recipient_id INT, -- For KUDOS
    title VARCHAR(255), -- For POST
    content TEXT NOT NULL,
    theme VARCHAR(100), -- For POST
    resource_url VARCHAR(512), -- Link/PDF URL for POST
    post_subtype VARCHAR(50),
    event_date VARCHAR(50),
    extracted_text TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (author_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (recipient_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE item_groups (
    item_id INT NOT NULL,
    group_id INT NOT NULL,
    PRIMARY KEY (item_id, group_id),
    FOREIGN KEY (item_id) REFERENCES feed_items(id) ON DELETE CASCADE,
    FOREIGN KEY (group_id) REFERENCES groups(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE reactions (
    id INT AUTO_INCREMENT PRIMARY KEY,
    item_id INT NOT NULL,
    user_id INT NOT NULL,
    emoji VARCHAR(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_bin NOT NULL,
    UNIQUE KEY unique_reaction (item_id, user_id, emoji),
    FOREIGN KEY (item_id) REFERENCES feed_items(id) ON DELETE CASCADE,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE comments (
    id INT AUTO_INCREMENT PRIMARY KEY,
    item_id INT NOT NULL,
    user_id INT NOT NULL,
    content TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (item_id) REFERENCES feed_items(id) ON DELETE CASCADE,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE content_reports (
    id INT AUTO_INCREMENT PRIMARY KEY,
    target_type VARCHAR(50) NOT NULL,
    target_id INT NOT NULL,
    reporter_id INT NOT NULL,
    reason VARCHAR(255) NOT NULL,
    notes TEXT,
    status VARCHAR(50) DEFAULT 'OPEN',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (reporter_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE email_outbox (
    id INT AUTO_INCREMENT PRIMARY KEY,
    recipient_email VARCHAR(255) NOT NULL,
    subject VARCHAR(255) NOT NULL,
    body TEXT NOT NULL,
    sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    status VARCHAR(50) DEFAULT 'SENT'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE customer_service_inquiries (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    subject VARCHAR(255) NOT NULL,
    message TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE group_invitations (
    id INT AUTO_INCREMENT PRIMARY KEY,
    group_id INT NOT NULL,
    sender_id INT NOT NULL,
    recipient_username VARCHAR(255) NOT NULL,
    message TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    status VARCHAR(50) DEFAULT 'PENDING',
    FOREIGN KEY (group_id) REFERENCES groups(id) ON DELETE CASCADE,
    FOREIGN KEY (sender_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

#### Connection Pooling
In high-concurrency environments, opening and closing a database connection for every request is expensive. Implement connection pooling to reuse connections.

Example using `mysql.connector.pooling`:

```python
import os
import mysql.connector.pooling

# Read MySQL configuration from environment variables
db_config = {
    "host": os.environ.get("DB_HOST", "localhost"),
    "user": os.environ.get("DB_USER", "gooddeeds_user"),
    "password": os.environ.get("DB_PASSWORD", "secure_password"),
    "database": os.environ.get("DB_NAME", "gooddeeds"),
    "port": int(os.environ.get("DB_PORT", 3306))
}

# Initialize connection pool
connection_pool = mysql.connector.pooling.MySQLConnectionPool(
    pool_name="gooddeeds_pool",
    pool_size=10,  # Adjust based on expected concurrency and server limits
    pool_reset_session=True,
    **db_config
)

def get_db():
    """Retrieves a connection from the pool."""
    return connection_pool.get_connection()
```

#### Data Migration Script

Use the following Python script to migrate your existing development data from `gooddeeds.db` to your MySQL instance. Run this script *after* creating the MySQL schema.

```python
import sqlite3
import mysql.connector
import os

# Source SQLite Configuration
SQLITE_DB = os.environ.get("DB_PATH", "gooddeeds.db")

# Target MySQL Configuration
MYSQL_CONFIG = {
    "host": os.environ.get("DB_HOST", "localhost"),
    "user": os.environ.get("DB_USER", "gooddeeds_user"),
    "password": os.environ.get("DB_PASSWORD", "secure_password"),
    "database": os.environ.get("DB_NAME", "gooddeeds"),
    "port": int(os.environ.get("DB_PORT", 3306))
}

def migrate():
    sqlite_conn = sqlite3.connect(SQLITE_DB)
    sqlite_conn.row_factory = sqlite3.Row
    sqlite_cursor = sqlite_conn.cursor()

    mysql_conn = mysql.connector.connect(**MYSQL_CONFIG)
    mysql_cursor = mysql_conn.cursor()

    # Tables in order of migration to respect foreign key constraints
    tables = [
        "users", "groups", "sessions", "group_members", "group_bans", "group_resources",
        "group_messages", "feed_items", "item_groups", "reactions", "comments",
        "content_reports", "email_outbox", "customer_service_inquiries", "group_invitations"
    ]

    print("Starting migration...")

    # Temporarily disable foreign keys in MySQL to avoid ordering issues during bulk load
    mysql_cursor.execute("SET FOREIGN_KEY_CHECKS = 0;")

    for table in tables:
        print(f"Migrating table: {table}...")
        
        # Fetch all rows from SQLite
        sqlite_cursor.execute(f"SELECT * FROM {table}")
        rows = sqlite_cursor.fetchall()
        
        if not rows:
            print(f"  No data in {table}, skipping.")
            continue

        columns = rows[0].keys()
        
        # Prepare MySQL Insert statement
        placeholders = ", ".join(["%s"] * len(columns))
        col_names = ", ".join(columns)
        insert_sql = f"INSERT INTO {table} ({col_names}) VALUES ({placeholders})"

        # Convert row data to tuple list
        data_to_insert = [tuple(row) for row in rows]

        # Execute bulk insert
        mysql_cursor.executemany(insert_sql, data_to_insert)
        print(f"  Successfully migrated {len(rows)} rows.")

    mysql_conn.commit()
    
    # Re-enable foreign key checks
    mysql_cursor.execute("SET FOREIGN_KEY_CHECKS = 1;")
    
    sqlite_conn.close()
    mysql_conn.close()
    print("Migration completed successfully!")

if __name__ == "__main__":
    migrate()
```

---

### 2. Production Email Integration Setup

In production, relying on simulated outboxes is insufficient. You must configure a reliable SMTP delivery mechanism or use dedicated transactional email APIs.

#### SMTP Configuration

Configure the application to connect to your production SMTP server (e.g., Mailgun, SendGrid, Amazon SES) using the following environment variables:

```bash
export SMTP_HOST="smtp.sendgrid.net"
export SMTP_PORT=587
export SMTP_USER="apikey"
export SMTP_PASSWORD="your_sendgrid_api_key"
export SMTP_FROM_EMAIL="notifications@gooddeeds.space"
export SMTP_FROM_NAME="GoodDeeds Community"
```

#### Domain Verification (DNS Records)

To ensure notifications aren't marked as spam, configure the following DNS records for your sending domain (e.g., `gooddeeds.space`):

*   **SPF (Sender Policy Framework)**: Authorizes specific mail servers to send emails on behalf of your domain.
    *   *Example TXT Record*:
        *   **Host**: `@`
        *   **Value**: `v=spf1 include:sendgrid.net ~all` (Replace `sendgrid.net` with your provider's SPF include).
*   **DKIM (DomainKeys Identified Mail)**: Adds a cryptographic signature to emails, verifying they were sent by the domain owner.
    *   Your email provider will supply a unique TXT record name (selector) and value (public key) to add to your DNS.
*   **DMARC (Domain-based Message Authentication, Reporting, and Conformance)**: Instructs receiving servers how to handle emails that fail SPF/DKIM checks.
    *   *Example TXT Record*:
        *   **Host**: `_dmarc`
        *   **Value**: `v=DMARC1; p=quarantine; pct=100; rua=mailto:dmarc-reports@gooddeeds.space`

#### Transitioning to Transactional Email APIs

If email volume exceeds standard SMTP relay limits, transition from Python's standard `smtplib` to a dedicated API SDK.

**Example: Transitioning to AWS SES (using `boto3`)**

1.  Install the AWS SDK: `pip install boto3`.
2.  Refactor email sending logic to use the SDK instead of SMTP:

```python
import os
import boto3
from botocore.exceptions import ClientError

def send_email_via_ses(recipient, subject, text_body, html_body=None):
    """
    Sends an email using AWS SES.
    Reads sender email and AWS region from environment variables.
    """
    sender = os.environ.get("SMTP_FROM_EMAIL", "notifications@gooddeeds.space")
    sender_name = os.environ.get("SMTP_FROM_NAME", "GoodDeeds Community")
    aws_region = os.environ.get("AWS_REGION", "us-east-1")

    client = boto3.client('ses', region_name=aws_region)
    
    destination = {'ToAddresses': [recipient]}
    message = {
        'Subject': {'Data': subject, 'Charset': 'UTF-8'},
        'Body': {
            'Text': {'Data': text_body, 'Charset': 'UTF-8'}
        }
    }
    if html_body:
        message['Body']['Html'] = {'Data': html_body, 'Charset': 'UTF-8'}
        
    try:
        response = client.send_email(
            Source=f"{sender_name} <{sender}>",
            Destination=destination,
            Message=message
        )
        return True
    except ClientError as e:
        print(f"SES Error: {e.response['Error']['Message']}")
        return False
```

---

### 3. Cloud Deployment Guides

#### AWS (Amazon Web Services)

##### Backend Deployment (Elastic Beanstalk or EC2)

*   **Option A: Elastic Beanstalk (Recommended for ease of use)**:
    1.  Create a `requirements.txt` listing any external dependencies (e.g., `mysql-connector-python`).
    2.  Create a `Procfile` in the root directory to specify the startup command:
        ```text
        web: python3 server.py
        ```
    3.  Zip the application contents (excluding database files and virtual environments).
    4.  Create a new Elastic Beanstalk Application, choose the **Python** platform, upload the ZIP, and configure the environment variables under Configuration -> Software.
*   **Option B: EC2 (Virtual Machine)**:
    1.  Launch an Ubuntu EC2 instance.
    2.  Install Python 3 and git.
    3.  Clone the repository and set up environment variables in `/etc/environment` or via a `.env` file.
    4.  Configure `systemd` to run the application as a background service. Create `/etc/systemd/system/gooddeeds.service`:
        ```ini
        [Unit]
        Description=GoodDeeds Backend Service
        After=network.target

        [Service]
        User=ubuntu
        WorkingDirectory=/home/ubuntu/gooddeeds
        ExecStart=/usr/bin/python3 server.py
        Restart=always
        EnvironmentFile=/home/ubuntu/gooddeeds/.env

        [Install]
        WantedBy=multi-user.target
        ```
    5.  Enable and start the service:
        ```bash
        sudo systemctl enable gooddeeds
        sudo systemctl start gooddeeds
        ```

##### AWS RDS MySQL Setup
1.  Navigate to RDS Dashboard -> Create Database.
2.  Choose **MySQL**, select the Free Tier templates (if applicable), and configure DB instance identifier, master username, and password.
3.  Ensure "Public Access" is set to **No**.
4.  Place it in the same VPC as your EC2/Beanstalk instances.

##### Security Group Configuration
Configure Security Groups to isolate the database:
1.  **Web Security Group** (Attached to EC2/Beanstalk):
    *   **Inbound**: Allow Port 80 (HTTP) and Port 443 (HTTPS) from source `0.0.0.0/0`.
2.  **Database Security Group** (Attached to RDS):
    *   **Inbound**: Allow Port 3306 (MySQL) *only* from the Web Security Group ID.

##### Load Balancing & SSL (ACM)
1.  Request a public SSL certificate in **AWS Certificate Manager** (ACM) for your domain.
2.  Create an **Application Load Balancer** (ALB).
3.  Add listeners:
    *   Port 80 (Configure to redirect to Port 443).
    *   Port 443 (Forward to Target Group containing your backend instances, with ACM SSL certificate attached).

---

#### GCP (Google Cloud Platform)

##### Containerization & Cloud Run
Cloud Run is the recommended serverless option for deploying containerized applications.

1.  Create a `Dockerfile` in the root of the project:
    ```dockerfile
    FROM python:3.13-slim
    WORKDIR /app
    RUN pip install --no-cache-dir mysql-connector-python
    COPY . .
    EXPOSE 8080
    ENV PORT=8080
    CMD ["python", "server.py"]
    ```
2.  Build and push the image to **Artifact Registry**:
    ```bash
    gcloud builds submit --tag gcr.io/your-project-id/gooddeeds-backend
    ```
3.  Deploy to **Cloud Run**:
    ```bash
    gcloud run deploy gooddeeds-backend \
        --image gcr.io/your-project-id/gooddeeds-backend \
        --platform managed \
        --allow-unauthenticated \
        --port 8080
    ```

##### Google Cloud SQL (MySQL) Setup
1.  Go to Cloud SQL Instances -> Create Instance -> Choose **MySQL**.
2.  Configure Instance ID, root password, and database version (MySQL 8.0 recommended).
3.  Under **Connections**, disable Public IP and enable **Private IP** (requires configuring a VPC network) for maximum security.

##### Secure Connections (Cloud SQL Auth Proxy)
If using Cloud Run, connect securely using the Cloud SQL connection name.
1.  In Cloud Run configuration, add a **Cloud SQL Connection** pointing to your database instance.
2.  Use the Unix socket path provided by Cloud Run to connect:
    ```python
    # Connection configuration for Cloud Run to Cloud SQL MySQL
    db_config = {
        "unix_socket": "/cloudsql/your-project-id:region:instance-name",
        "user": "gooddeeds_user",
        "password": "secure_password",
        "database": "gooddeeds"
    }
    conn = mysql.connector.connect(**db_config)
    ```

##### Load Balancing & Google-managed SSL
1.  Set up an **HTTPS External Load Balancer**.
2.  Configure the backend service pointing to the Cloud Run Network Endpoint Group (NEG).
3.  Configure the frontend map to use a **Google-managed certificate**. Provide your domain name, and GCP will provision and renew the SSL certificate automatically.
