# GoodDeeds.space

GoodDeeds.space is a community-focused web application designed to promote goodness, build meaningful connections, and facilitate mutual aid. With a warm, accessible, and senior-friendly design philosophy, it connects volunteers, organizers, and neighbors to support each other.

## System Overview & Mission

The core mission of GoodDeeds.space is to encourage small acts of kindness that ripple outward to transform neighborhoods. The platform is designed to be accessible to all age groups, particularly seniors, featuring:
*   **Warm Aesthetics**: Inviting and easy-to-read interface.
*   **Intergenerational Connection**: Facilitating mentorship and support between youth and seniors.
*   **Low Barrier to Entry**: Simple workflows for posting help requests, sharing inspiring stories, and giving thanks (Kudos).

### Core Capabilities
- **Unified Social Feed**: A merged stream of Kudos (appreciation) and Posts (information/stories) sorted using a "smart sort" algorithm that prioritizes items from groups the user has joined and items with high engagement.
- **Group Spaces**: Dedicated sub-communities where members can chat, share curated resources, and invite others.
- **Gamified Spotlight**: A monthly "Hall of Fame" recognizing top kudos recipients, most liked post authors, and highly saved resources.
- **Simulated & Real Communications**: Integrated email notifications for kudos and invitations, with a built-in outbox viewer for testing.

---

## Architecture & Directory Structure

The application is built entirely on the Python 3.13 standard library (no external dependencies) and uses SQLite for data persistence.

```
├── database.py         # Database schema, initialization, and demo data seeding
├── handlers.py         # Core API request handlers, auth, and business logic
├── server.py           # Threaded HTTP server routing API and serving static files
├── run.sh              # Shell script to start the server
├── run_tests.sh        # Shell script to run the test suite
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
    ├── test_groups.py  # Group management, chat, and resources tests
    ├── test_invitations.py # Group invitations flow tests
    ├── test_spotlight.py # Spotlight and rotation tests
    └── test_suite.py   # Test suite runner and discoverer
```

### Component Roles
*   **`server.py`**: Listens on a specified port (default 8080). Routes requests starting with `/api/` to `handlers.handle_api_request` and serves static files from the `static/` directory for other requests.
*   **`database.py`**: Manages the SQLite database (`gooddeeds.db`). Defines the schema (13 tables) and populates realistic demo data on the first run.
*   **`handlers.py`**: Parses incoming HTTP requests, performs authentication checks, executes database queries, handles simulated/real email delivery, and returns JSON responses.
*   **`static/`**: A pure HTML5/CSS3/Vanilla JS single-page application (SPA).

---

## Startup Guide

### Prerequisites
*   Python 3.13 (or compatible Python 3 version using standard library)

### Database Initialization
The database initializes automatically when you start the server for the first time. If you wish to initialize or reset it manually, run:
```bash
python3 database.py
```
This will create `gooddeeds.db` and seed it with sample users, groups, posts, reactions, comments, and invitations.

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
| `SMTP_FROM_NAME` | Sender display name | `GoodDeeds Community` |

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
Authenticates a user and returns a session token. Supports login via email or username.
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

#### `POST /api/auth/logout`
Termates the current session. Requires authentication.
*   **Response (200 OK)**: `{"success": true}`

#### `GET /api/auth/me`
Retrieves details of the currently authenticated user. Requires authentication.
*   **Response (200 OK)**: `{"user": { ... }}`

---

### Feed & Interaction Endpoints

#### `GET /api/feed`
Retrieves a list of posts and kudos.
*   **Query Parameters**:
    *   `sort`: `smart` (default, weights by group membership and reactions) or `recent`.
    *   `theme`: Filter by specific theme (e.g., "Mental Health").
    *   `group_id`: Filter items tagged to a specific group.
    *   `search`: Search text in title, content, or theme.
    *   `filter_type`: Filter by type (`KUDOS` or `POST`).
*   **Response (200 OK)**:
    ```json
    {
      "feed": [
        {
          "id": 1,
          "item_type": "POST",
          "author_name": "Maya_Lin",
          "title": "Title",
          "content": "Content",
          "reactions": {"❤️": 3},
          "total_reactions": 3,
          "comments": [...],
          "_score": 103
        }
      ]
    }
    ```

#### `POST /api/kudos`
Creates a new Kudos thanking another user. Requires authentication.
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
Creates a new community post. Requires authentication.
*   **Payload**:
    ```json
    {
      "title": "Community Garden",
      "theme": "Community Services",
      "content": "Let's start a garden!",
      "resource_url": "https://example.com/garden_plan.pdf",
      "group_ids": [3]
    }
    ```
*   **Response (201 Created)**: `{"item": { ... }, "success": true}`

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

#### `POST /api/comments`
Adds a comment to a feed item. Requires authentication.
*   **Payload**:
    ```json
    {
      "item_id": 1,
      "content": "Great idea!"
    }
    ```
*   **Response (201 Created)**: `{"comment": { ... }, "success": true}`

---

### Group Endpoints

#### `GET /api/groups`
Retrieves all groups, optionally filtered by search query or theme.
*   **Query Parameters**: `search`, `theme`, `joined` (true/false)
*   **Response (200 OK)**: `{"groups": [...]}`

#### `POST /api/groups`
Creates a new group. The creator is automatically added as group admin. Requires authentication.
*   **Payload**:
    ```json
    {
      "name": "New Group",
      "description": "Group Description",
      "themes": ["Theme1"],
      "icon_url": ""
    }
    ```
*   **Response (201 Created)**: `{"id": 4, "success": true}`

#### `GET /api/groups/<id>`
Retrieves detailed metadata for a group, including roster, resources, chat messages, and invitations.
*   **Response (200 OK)**: `{"group": { ... }}`

#### `POST /api/groups/<id>/join` & `POST /api/groups/<id>/leave`
Joins or leaves a group. Requires authentication.
*   **Response (200 OK)**: `{"success": true, "action": "join|leave"}`

#### `POST /api/groups/<id>/resources`
Adds curated resources to a group. **Only group admins can perform this action.** Requires authentication.
*   **Payload**:
    ```json
    {
      "resources": [
        {
          "title": "Resource Title",
          "url": "https://example.com/file.pdf",
          "resource_type": "PDF",
          "theme": "Education"
        }
      ]
    }
    ```
*   **Response (201 Created)**: `{"success": true, "count": 1}`

#### `POST /api/groups/<id>/chat`
Posts a message to the group's chat board. Requires authentication.
*   **Payload**: `{"message": "Hello group!"}`
*   **Response (201 Created)**: `{"message": { ... }, "success": true}`

---

### Group Invitations

#### `POST /api/groups/<id>/invite`
Invites users to join a group. Sends an email (real or simulated) to recipients. Requires authentication.
*   **Payload**:
    ```json
    {
      "emails": "user1@example.com, Username2",
      "message": "Please join our group!"
    }
    ```
*   **Response (200 OK)**: `{"success": true, "message": "Invitation sent to 2 recipient(s)!"}`

#### `GET /api/invitations/pending`
Retrieves pending group invitations for the currently authenticated user.
*   **Response (200 OK)**: `{"invitations": [], "success": true}`

#### `POST /api/invitations/respond`
Accepts or declines a pending group invitation. Requires authentication.
*   **Payload**:
    ```json
    {
      "invite_id": 1,
      "action": "accept|reject"
    }
    ```
*   **Response (200 OK)**: `{"success": true, "message": "..."}`

---

### Gamification & Spotlight

#### `GET /api/spotlight`
Retrieves the Monthly Hall of Fame spotlight data, showing top kudos recipients, top post creators, and valuable resources.
*   **Query Parameters**:
    *   `month`: The month string (e.g., "June 2026", "May 2026"). Different months rotate the champions utilizing offset logic.
*   **Response (200 OK)**:
    ```json
    {
      "month": "June 2026",
      "top_kudos_champions": [...],
      "top_post_creators": [...],
      "valuable_resources": { ... }
    }
    ```

---

## Simulated Audit Logs & Support

### Simulated Outbox (`/#/outbox`)
Since SMTP servers might not be configured in local development, all emails sent by the system (kudos notifications, group invitations, support confirmations) are logged to the `email_outbox` table.
*   **API**: `GET /api/outbox`
*   **UI Access**: Navigate to `/#/outbox` in the application to view the simulated outgoing mail log. This is useful for verifying invitations and notifications without live SMTP setup.

### Customer Support Portal
Users can submit inquiries which log to `customer_service_inquiries`.
*   **Submit API**: `POST /api/support`
*   **View API (Admin)**: `GET /api/support`
*   On submission, a confirmation email is sent to the user, and an alert email is sent to `roht_kgupta@yahoo.com` (both visible in the Simulated Outbox).

---

## Running the Testing Suite

The testing suite verifies all API endpoints and database behaviors using isolated temporary databases.

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
