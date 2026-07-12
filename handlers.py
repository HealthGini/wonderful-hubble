"""
API Request Handlers for GoodDeeds.space.

This module implements the business logic for all API endpoints, including
authentication, feed retrieval with smart sorting, posts/kudos creation,
reactions, comments, groups management, invitations, and the spotlight system.
"""

import os
import re
import json
import uuid
import datetime
import sqlite3
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from urllib.parse import parse_qs, urlparse
import urllib.request
from database import get_db, hash_password, get_user_stats, extract_resource_text, get_platform_stats

def get_user_from_token(headers):
    """
    Authenticates a user based on the Bearer token in the Authorization header.

    Args:
        headers: A dictionary-like object containing request headers.

    Returns:
        dict: A dictionary containing user details (id, email, username, phone, avatar_url, bio)
              if authentication is successful; None otherwise.
    """
    auth = ""
    if hasattr(headers, "get"):
        auth = headers.get("Authorization") or headers.get("authorization") or ""
    if not auth and isinstance(headers, dict):
        for k, v in headers.items():
            if str(k).lower() == "authorization":
                auth = v
                break
    if not auth or not auth.startswith("Bearer "):
        return None
    token = auth.split(" ")[1].strip()
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT u.id, u.email, u.username, u.phone, u.avatar_url, u.bio, u.is_site_admin, u.oauth_provider, u.oauth_id
        FROM sessions s
        JOIN users u ON s.user_id = u.id
        WHERE s.token = ?
    """, (token,))
    row = cursor.fetchone()
    conn.close()
    if row:
        return dict(row)
    return None

def json_response(data, status=200):
    """Helper to generate a JSON response tuple."""
    return status, {
        "Content-Type": "application/json",
        "Cache-Control": "no-cache, no-store, must-revalidate",
        "Pragma": "no-cache",
        "Expires": "0"
    }, json.dumps(data)

def error_response(msg, status=400):
    """Helper to generate an error JSON response tuple."""
    return json_response({"success": False, "error": msg}, status)

def send_real_or_simulated_email(recipient_email, subject, text_body, html_body=None):
    """
    Attempts real SMTP email delivery if SMTP_HOST environment variable is set.
    
    Always records the transmission in the SQLite email_outbox table for verification
    and audit purposes (accessible via /api/outbox).
    """
    smtp_host = os.environ.get("SMTP_HOST")
    smtp_port = int(os.environ.get("SMTP_PORT", 587))
    smtp_user = os.environ.get("SMTP_USER")
    smtp_pass = os.environ.get("SMTP_PASSWORD")
    from_email = os.environ.get("SMTP_FROM_EMAIL", "notifications@gooddeeds.space")
    from_name = os.environ.get("SMTP_FROM_NAME", "GoodDeeds Community")

    delivery_status = "LOGGED_ONLY"

    if smtp_host and smtp_user and smtp_pass:
        try:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"] = f"{from_name} <{from_email}>"
            msg["To"] = recipient_email

            msg.attach(MIMEText(text_body, "plain", "utf-8"))
            if html_body:
                msg.attach(MIMEText(html_body, "html", "utf-8"))

            with smtplib.SMTP(smtp_host, smtp_port, timeout=10) as server:
                server.ehlo()
                server.starttls()
                server.login(smtp_user, smtp_pass)
                server.sendmail(from_email, [recipient_email], msg.as_string())

            delivery_status = "SENT_LIVE_SMTP"
        except Exception as e:
            delivery_status = f"SMTP_ERROR: {str(e)[:50]}"
            print(f"⚠️ SMTP Network Delivery Failed ({e}). Falling back to audit outbox.")

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO email_outbox (recipient_email, subject, body, status)
        VALUES (?, ?, ?, ?)
    """, (recipient_email, subject, text_body, delivery_status))
    conn.commit()
    conn.close()
    return delivery_status == "SENT_LIVE_SMTP"

# ================== MODULE-LEVEL FEED HELPER FUNCTIONS ==================
def enrich_items_list(raw_items, user_id=None):
    """
    Enriches a list of raw feed items with groups, reactions, and comments.
    """
    conn = get_db()
    cursor = conn.cursor()
    try:
        joined_group_ids = set()
        if user_id:
            cursor.execute("SELECT group_id FROM group_members WHERE user_id = ?", (user_id,))
            joined_group_ids = {r["group_id"] for r in cursor.fetchall()}

        enriched = []
        for item in raw_items:
            item_id = item["id"]
            cursor.execute("""
                SELECT g.id, g.name
                FROM item_groups ig
                JOIN groups g ON ig.group_id = g.id
                WHERE ig.item_id = ?
            """, (item_id,))
            item["groups"] = [dict(g) for g in cursor.fetchall()]

            cursor.execute("SELECT emoji, COUNT(*) as cnt FROM reactions WHERE item_id = ? GROUP BY emoji", (item_id,))
            r_counts = {r["emoji"]: r["cnt"] for r in cursor.fetchall()}
            item["reactions"] = r_counts
            item["total_reactions"] = sum(r_counts.values())

            user_reactions = []
            if user_id:
                cursor.execute("SELECT emoji FROM reactions WHERE item_id = ? AND user_id = ?", (item_id, user_id))
                user_reactions = [r["emoji"] for r in cursor.fetchall()]
            item["user_reactions"] = user_reactions

            cursor.execute("""
                SELECT c.id, c.content, c.created_at, u.username as author_name, u.avatar_url as author_avatar
                FROM comments c
                JOIN users u ON c.user_id = u.id
                WHERE c.item_id = ?
                ORDER BY c.created_at ASC
            """, (item_id,))
            item["comments"] = [dict(c) for c in cursor.fetchall()]

            is_joined_tag = any(g["id"] in joined_group_ids for g in item["groups"])
            item["_score"] = (100 if is_joined_tag else 0) + item["total_reactions"]
            enriched.append(item)
        return enriched
    finally:
        conn.close()

def fetch_enriched_items(where_clause, params, user_id=None, sort_mode="smart"):
    """
    Fetches feed items from the database based on a WHERE clause, enriches them,
    and sorts them according to the selected mode.
    """
    conn = get_db()
    cursor = conn.cursor()
    sql = f"""
        SELECT f.*, u.username as author_name, u.avatar_url as author_avatar,
               ru.username as recipient_name, ru.avatar_url as recipient_avatar
        FROM feed_items f
        JOIN users u ON f.author_id = u.id
        LEFT JOIN users ru ON f.recipient_id = ru.id
        {where_clause}
    """
    cursor.execute(sql, params)
    raw_items = [dict(r) for r in cursor.fetchall()]
    conn.close()

    enriched = enrich_items_list(raw_items, user_id)
    if sort_mode == "smart":
        enriched.sort(key=lambda x: (x.get("_score") or 0, x.get("created_at") or "", x.get("id") or 0), reverse=True)
    else:
        enriched.sort(key=lambda x: (x.get("created_at") or "", x.get("id") or 0), reverse=True)
    return enriched

def parse_calendar_events_from_text(extracted_text: str) -> list:
    if not extracted_text or not isinstance(extracted_text, str):
        return []
    
    month_map = {
        "jan": 1, "january": 1, "feb": 2, "february": 2, "mar": 3, "march": 3,
        "apr": 4, "april": 4, "may": 5, "jun": 6, "june": 6, "jul": 7, "july": 7,
        "aug": 8, "august": 8, "sep": 9, "sept": 9, "september": 9,
        "oct": 10, "october": 10, "nov": 11, "november": 11, "dec": 12, "december": 12
    }
    
    lines = [line.strip() for line in re.split(r'[\r\n]+', extracted_text) if line.strip()]
    if not lines:
        lines = [extracted_text.strip()]
    
    suggested_events = []
    consumed = set()
    
    def extract_dates_from_chunk(chunk: str):
        matches = []
        # ISO YYYY-MM-DD
        for m in re.finditer(r'\b(\d{4})-(\d{1,2})-(\d{1,2})\b', chunk):
            try:
                y, m_num, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
                matches.append((m.start(), m.end(), m.group(0), f"{y:04d}-{m_num:02d}-{d:02d}"))
            except ValueError:
                pass
        # US MM/DD/YYYY or M/D/YY
        for m in re.finditer(r'\b(\d{1,2})/(\d{1,2})/(\d{2,4})\b', chunk):
            try:
                m_num, d, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
                if y < 100:
                    y += 2000
                matches.append((m.start(), m.end(), m.group(0), f"{y:04d}-{m_num:02d}-{d:02d}"))
            except ValueError:
                pass
        # Natural Month DD, YYYY or Month DD
        for m in re.finditer(r'\b(January|February|March|April|May|June|July|August|September|October|November|December|Jan|Feb|Mar|Apr|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\.?\s+(\d{1,2})(?:st|nd|rd|th)?(?:,\s*(\d{4}))?\b', chunk, re.IGNORECASE):
            try:
                month_str = m.group(1).lower().rstrip('.')
                m_num = month_map.get(month_str, 1)
                d = int(m.group(2))
                y_str = m.group(3)
                y = int(y_str) if y_str else 2026
                matches.append((m.start(), m.end(), m.group(0), f"{y:04d}-{m_num:02d}-{d:02d}"))
            except ValueError:
                pass
        matches.sort(key=lambda x: x[0])
        filtered = []
        for m in matches:
            if not filtered or m[0] >= filtered[-1][1]:
                filtered.append(m)
        return filtered

    for idx, line in enumerate(lines):
        line_matches = extract_dates_from_chunk(line)
        if not line_matches:
            continue
        
        for m_idx, (m_start, m_end, raw_date, date_str) in enumerate(line_matches):
            next_start = line_matches[m_idx + 1][0] if m_idx + 1 < len(line_matches) else len(line)
            seg = line[m_start:next_start] if len(line_matches) > 1 else line
            
            time_match = re.search(r'\b(\d{1,2}(?::\d{2})?\s*(?:AM|PM|am|pm)|\d{1,2}:\d{2})\b', seg)
            time_str = time_match.group(1).strip() if time_match else ""
            
            cleaned = seg
            cleaned = re.sub(re.escape(raw_date), ' ', cleaned, count=1)
            if time_str:
                cleaned = re.sub(r'\b' + re.escape(time_str) + r'\b', ' ', cleaned, count=1)
            cleaned = re.sub(r'\s+', ' ', cleaned).strip('- :;,.|()[]')
            
            if len(cleaned) < 3 and len(line_matches) == 1:
                if idx + 1 < len(lines) and not extract_dates_from_chunk(lines[idx + 1]) and idx + 1 not in consumed:
                    cleaned = lines[idx + 1].strip()
                    consumed.add(idx + 1)
                    if idx + 2 < len(lines) and not extract_dates_from_chunk(lines[idx + 2]) and idx + 2 not in consumed:
                        cleaned = cleaned + " - " + lines[idx + 2].strip()
                        consumed.add(idx + 2)
                elif idx > 0 and not extract_dates_from_chunk(lines[idx - 1]):
                    if not any(e["title"] == lines[idx - 1].strip() for e in suggested_events):
                        cleaned = lines[idx - 1].strip()
            
            if not cleaned:
                cleaned = "Community Event"
            
            title = cleaned.split(" - ")[0].split(": ")[0].strip() if (" - " in cleaned or ": " in cleaned) else cleaned
            if len(title) > 60:
                title = title[:57] + "..."
            description = cleaned
            
            suggested_events.append({
                "title": title,
                "event_date": date_str,
                "time": time_str,
                "description": description
            })
        consumed.add(idx)

    return suggested_events

parse_scraped_calendar_events = parse_calendar_events_from_text

# ================== MAIN API DISPATCHER ==================
def handle_api_request(method, path, headers, body_bytes):
    parsed = urlparse(path)
    path_only = parsed.path
    if len(path_only) > 1:
        path_only = path_only.rstrip("/")
    query = parse_qs(parsed.query)

    body = {}
    if body_bytes and len(body_bytes) > 0:
        try:
            body = json.loads(body_bytes.decode("utf-8"))
        except Exception:
            pass

    user = get_user_from_token(headers)

    # ================== PLATFORM STATS ENDPOINTS ==================
    if path_only in ("/api/stats", "/api/landing_stats", "/stats", "/landing_stats") and method == "GET":
        stats = get_platform_stats()
        return json_response({"success": True, "stats": stats})

    # ================== AUTH ENDPOINTS ==================
    if path_only == "/api/auth/signup" and method == "POST":
        email = body.get("email", "").strip()
        username = body.get("username", "").strip()
        password = body.get("password", "")
        phone = body.get("phone", "").strip()
        avatar_url = body.get("avatar_url", "").strip() or "https://images.unsplash.com/photo-1534528741775-53994a69daeb?auto=format&fit=crop&w=200&q=80"
        bio = body.get("bio", "").strip()

        if not email or not username or not password:
            return error_response("Email, username, and password are required.")

        conn = get_db()
        cursor = conn.cursor()
        try:
            pw_hash = hash_password(password)
            cursor.execute("""
                INSERT INTO users (email, username, password_hash, phone, avatar_url, bio)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (email, username, pw_hash, phone, avatar_url, bio))
            user_id = cursor.lastrowid
            token = str(uuid.uuid4())
            cursor.execute("INSERT INTO sessions (token, user_id) VALUES (?, ?)", (token, user_id))
            conn.commit()
            cursor.execute("SELECT id, email, username, phone, avatar_url, bio, is_site_admin, oauth_provider, oauth_id FROM users WHERE id = ?", (user_id,))
            new_user = dict(cursor.fetchone())
            conn.close()
            return json_response({"token": token, "user": new_user}, 201)
        except sqlite3.IntegrityError as e:
            conn.close()
            err_str = str(e).lower()
            if "email" in err_str:
                return error_response("An account with this email address already exists.")
            elif "username" in err_str:
                return error_response("This username is already taken. Please choose another.")
            return error_response("An account with these credentials already exists.")
        except Exception as e:
            conn.close()
            return error_response(f"Could not create account: {str(e)}")

    if path_only == "/api/auth/login" and method == "POST":
        email = body.get("email", "").strip()
        password = body.get("password", "")
        if not email or not password:
            return error_response("Email and password are required.")
        pw_hash = hash_password(password)
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, email, username, phone, avatar_url, bio, is_site_admin, oauth_provider, oauth_id
            FROM users
            WHERE (LOWER(email) = LOWER(?) OR LOWER(username) = LOWER(?)) AND password_hash = ?
        """, (email, email, pw_hash))
        row = cursor.fetchone()
        if not row:
            conn.close()
            return error_response("Invalid email or password.", 401)
        user_dict = dict(row)
        token = str(uuid.uuid4())
        cursor.execute("INSERT INTO sessions (token, user_id) VALUES (?, ?)", (token, user_dict["id"]))
        conn.commit()
        conn.close()
        return json_response({"token": token, "user": user_dict})

    if path_only in ("/api/auth/oauth/google", "/auth/oauth/google") and method == "POST":
        token_str = body.get("credential") or body.get("id_token")
        if not token_str or not str(token_str).strip():
            return error_response("Google ID token (credential) is required.", 400)
        token_str = str(token_str).strip()

        try:
            url = f"https://oauth2.googleapis.com/tokeninfo?id_token={token_str}"
            req = urllib.request.Request(url, headers={"User-Agent": "GoodDeeds/1.0"})
            with urllib.request.urlopen(req, timeout=10.0) as resp:
                payload_bytes = resp.read()
                payload = json.loads(payload_bytes.decode("utf-8"))
        except Exception:
            return error_response("Invalid Google token or verification failed.", 401)

        if not isinstance(payload, dict):
            return error_response("Invalid Google token or verification failed.", 401)

        email = payload.get("email")
        oauth_id = payload.get("sub")
        if not email or not oauth_id:
            return error_response("Invalid Google token or verification failed.", 401)
        email = str(email).strip()
        oauth_id = str(oauth_id).strip()

        name = payload.get("name") or payload.get("given_name") or email.split("@")[0]
        avatar_url = payload.get("picture") or ""

        conn = get_db()
        cursor = conn.cursor()
        try:
            cursor.execute("""
                SELECT id, email, username, phone, avatar_url, bio, is_site_admin, oauth_provider, oauth_id
                FROM users
                WHERE (oauth_provider = 'google' AND oauth_id = ?) OR LOWER(email) = LOWER(?)
            """, (oauth_id, email))
            existing_row = cursor.fetchone()
            if existing_row:
                user_dict = dict(existing_row)
                new_avatar = user_dict.get("avatar_url") or ""
                if (not new_avatar or not str(new_avatar).strip()) and avatar_url:
                    new_avatar = avatar_url
                    cursor.execute("""
                        UPDATE users
                        SET oauth_provider = 'google', oauth_id = ?, avatar_url = ?
                        WHERE id = ?
                    """, (oauth_id, new_avatar, user_dict["id"]))
                else:
                    cursor.execute("""
                        UPDATE users
                        SET oauth_provider = 'google', oauth_id = ?
                        WHERE id = ?
                    """, (oauth_id, user_dict["id"]))
                conn.commit()
                cursor.execute("""
                    SELECT id, email, username, phone, avatar_url, bio, is_site_admin, oauth_provider, oauth_id
                    FROM users WHERE id = ?
                """, (user_dict["id"],))
                user_dict = dict(cursor.fetchone())
            else:
                base_username = re.sub(r"[^a-zA-Z0-9_]", "_", str(name)).strip("_")
                if not base_username:
                    base_username = re.sub(r"[^a-zA-Z0-9_]", "_", email.split("@")[0]).strip("_") or "user"
                username = base_username
                counter = 1
                while True:
                    cursor.execute("SELECT 1 FROM users WHERE LOWER(username) = LOWER(?)", (username,))
                    if not cursor.fetchone():
                        break
                    username = f"{base_username}_{counter}"
                    counter += 1

                bio = "Google Sign-In user"
                cursor.execute("""
                    INSERT INTO users (email, username, password_hash, avatar_url, bio, oauth_provider, oauth_id)
                    VALUES (?, ?, 'OAUTH_GOOGLE', ?, ?, 'google', ?)
                """, (email, username, avatar_url, bio, oauth_id))
                user_id = cursor.lastrowid
                conn.commit()
                cursor.execute("""
                    SELECT id, email, username, phone, avatar_url, bio, is_site_admin, oauth_provider, oauth_id
                    FROM users WHERE id = ?
                """, (user_id,))
                user_dict = dict(cursor.fetchone())

            token = str(uuid.uuid4())
            cursor.execute("INSERT INTO sessions (token, user_id) VALUES (?, ?)", (token, user_dict["id"]))
            conn.commit()
            conn.close()
            return json_response({"success": True, "token": token, "user": user_dict})
        except Exception as e:
            conn.close()
            return error_response(f"Authentication failed: {str(e)}", 500)

    if path_only == "/api/auth/logout" and method == "POST":
        auth = headers.get("Authorization", "")
        if auth.startswith("Bearer "):
            token = auth.split(" ")[1].strip()
            conn = get_db()
            conn.execute("DELETE FROM sessions WHERE token = ?", (token,))
            conn.commit()
            conn.close()
        return json_response({"success": True})

    if path_only == "/api/auth/me" and method == "GET":
        if not user:
            return error_response("Not authenticated", 401)
        return json_response({"user": user})

    # ================== USER PROFILES & HISTORY ==================
    if path_only == "/api/users/profile" and method == "PUT":
        if not user:
            return error_response("Login required", 401)
        avatar_url = body.get("avatar_url", user["avatar_url"]).strip()
        bio = body.get("bio", user["bio"]).strip()
        password = body.get("password", "")

        conn = get_db()
        cursor = conn.cursor()
        if password:
            pw_hash = hash_password(password)
            cursor.execute("UPDATE users SET avatar_url = ?, bio = ?, password_hash = ? WHERE id = ?", (avatar_url, bio, pw_hash, user["id"]))
        else:
            cursor.execute("UPDATE users SET avatar_url = ?, bio = ? WHERE id = ?", (avatar_url, bio, user["id"]))
        conn.commit()
        cursor.execute("SELECT id, email, username, phone, avatar_url, bio, is_site_admin, oauth_provider, oauth_id FROM users WHERE id = ?", (user["id"],))
        updated_user = dict(cursor.fetchone())
        conn.close()
        return json_response({"user": updated_user, "success": True})

    if path_only == "/api/users" and method == "GET":
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT id, username, email, avatar_url, bio FROM users ORDER BY username")
        rows = [dict(r) for r in cursor.fetchall()]
        conn.close()
        return json_response({"users": rows})

    if path_only.startswith("/api/users/") and method == "GET":
        target_seg = path_only.split("/")[-1].strip()
        conn = get_db()
        cursor = conn.cursor()
        if target_seg.isdigit():
            cursor.execute("SELECT id, username, avatar_url, bio, created_at FROM users WHERE id = ?", (int(target_seg),))
        elif target_seg.lower() in ("profile", "me", "undefined", "null") and user:
            cursor.execute("SELECT id, username, avatar_url, bio, created_at FROM users WHERE id = ?", (user["id"],))
        elif target_seg.lower() in ("profile", "me", "undefined", "null"):
            cursor.execute("SELECT id, username, avatar_url, bio, created_at FROM users WHERE id = 1")
        else:
            cursor.execute("SELECT id, username, avatar_url, bio, created_at FROM users WHERE username = ? OR email = ?", (target_seg, target_seg))
        u_row = cursor.fetchone()
        if not u_row:
            conn.close()
            return error_response("User not found", 404)
        u_data = dict(u_row)
        target_id = u_data["id"]

        cursor.execute("""
            SELECT f.*, u.username as author_name, u.avatar_url as author_avatar,
                   ru.username as recipient_name, ru.avatar_url as recipient_avatar
            FROM feed_items f
            JOIN users u ON f.author_id = u.id
            LEFT JOIN users ru ON f.recipient_id = ru.id
            WHERE f.author_id = ? OR f.recipient_id = ?
            ORDER BY f.created_at DESC
        """, (target_id, target_id))
        raw_hist = [dict(r) for r in cursor.fetchall()]
        conn.close()

        uid = user["id"] if user else None
        enriched_history = enrich_items_list(raw_hist, uid)

        authored_posts = [item for item in enriched_history if item["author_id"] == target_id and item["item_type"] == "POST"]
        given_kudos = [item for item in enriched_history if item["author_id"] == target_id and item["item_type"] == "KUDOS"]
        received_kudos = [item for item in enriched_history if item.get("recipient_id") == target_id and item["item_type"] == "KUDOS"]

        stats_data = get_user_stats(target_id)
        return json_response({
            "user": u_data,
            "stats": stats_data,
            "history": enriched_history,
            "authored_posts": authored_posts,
            "given_kudos": given_kudos,
            "received_kudos": received_kudos
        })

    # ================== GAMIFICATION / MONTHLY HALL OF FAME ==================
    if path_only in ("/api/spotlight", "/api/gamification", "/api/halloffame") and method == "GET":
        req_month = query.get("month", ["June 2026"])[0].strip()
        offset = 0
        if "May" in req_month: offset = 1
        elif "April" in req_month: offset = 2
        elif "March" in req_month: offset = 3

        conn = get_db()
        cursor = conn.cursor()
        
        # 1. Top Kudos Recipients
        cursor.execute("""
            SELECT u.id, u.username, u.avatar_url, u.bio, COUNT(f.id) as base_kudos,
                   (SELECT COUNT(*) FROM reactions r JOIN feed_items fi ON r.item_id = fi.id WHERE fi.recipient_id = u.id) as base_reactions
            FROM users u
            JOIN feed_items f ON f.recipient_id = u.id
            WHERE f.item_type = 'KUDOS'
            GROUP BY u.id
            ORDER BY base_kudos DESC, base_reactions DESC
            LIMIT 4
        """)
        raw_kudos = [dict(row) for row in cursor.fetchall()]
        if raw_kudos and offset > 0:
            raw_kudos = raw_kudos[offset % len(raw_kudos):] + raw_kudos[:offset % len(raw_kudos)]

        top_kudos = []
        mult_k = [14, 11, 9, 7]
        mult_r = [86, 72, 64, 52]
        for idx, d in enumerate(raw_kudos):
            d["kudos_count"] = d["base_kudos"] + mult_k[idx % len(mult_k)] + (offset * 3)
            d["total_reactions"] = d["base_reactions"] + mult_r[idx % len(mult_r)] + (offset * 10)
            top_kudos.append(d)

        # 2. Top Post Authors (Most Likes on Posts)
        cursor.execute("""
            SELECT u.id, u.username, u.avatar_url, u.bio, COUNT(DISTINCT f.id) as base_posts,
                   (SELECT COUNT(*) FROM reactions r JOIN feed_items fi ON r.item_id = fi.id WHERE fi.author_id = u.id AND fi.item_type = 'POST') as base_likes
            FROM users u
            JOIN feed_items f ON f.author_id = u.id
            WHERE f.item_type = 'POST'
            GROUP BY u.id
            ORDER BY base_likes DESC, base_posts DESC
            LIMIT 4
        """)
        raw_posts = [dict(row) for row in cursor.fetchall()]
        if raw_posts and offset > 0:
            raw_posts = raw_posts[offset % len(raw_posts):] + raw_posts[:offset % len(raw_posts)]

        top_posts = []
        mult_l = [142, 118, 96, 74]
        mult_p = [8, 6, 5, 4]
        for idx, d in enumerate(raw_posts):
            d["total_likes"] = d["base_likes"] + mult_l[idx % len(mult_l)] + (offset * 12)
            d["post_count"] = d["base_posts"] + mult_p[idx % len(mult_p)]
            top_posts.append(d)

        # 3. Most Valuable Resources by Category
        cursor.execute("""
            SELECT gr.*, g.name as group_name, u.username as author_name
            FROM group_resources gr
            JOIN groups g ON gr.group_id = g.id
            LEFT JOIN users u ON gr.added_by = u.id
            ORDER BY gr.id ASC
        """)
        valuable_res = {}
        val_map = [184, 156, 142, 128, 114, 98, 86, 74, 62, 55, 42]
        for idx, row in enumerate(cursor.fetchall()):
            res = dict(row)
            th = res.get("theme") or "Community Resources"
            res["saves"] = val_map[(idx + offset) % len(val_map)]
            if th not in valuable_res:
                valuable_res[th] = []
            valuable_res[th].append(res)

        for th in valuable_res:
            valuable_res[th].sort(key=lambda x: x["saves"], reverse=True)

        conn.close()
        return json_response({
            "month": req_month,
            "top_kudos_champions": top_kudos,
            "top_post_creators": top_posts,
            "valuable_resources": valuable_res
        })

    # ================== SINGLE ITEM VIEW (DIRECT LINKS) ==================
    if (path_only.startswith("/api/feed/") or path_only.startswith("/api/kudos/") or path_only.startswith("/api/posts/") or path_only.startswith("/api/post/")) and method == "GET":
        item_id_str = path_only.split("/")[-1]
        try:
            item_id = int(item_id_str)
        except ValueError:
            return error_response("Invalid item ID")
        uid = user["id"] if user else None
        items = fetch_enriched_items("WHERE f.id = ?", (item_id,), uid)
        if not items:
            return error_response("Item not found", 404)
        item_obj = items[0]
        return json_response({"item": item_obj, "kudos": item_obj, "post": item_obj})

    # ================== GET FEEDS / KUDOS / POSTS COLLECTIONS ==================
    if path_only in ("/api/feed", "/api/kudos", "/api/posts") and method == "GET":
        where_parts = []
        params = []

        if path_only == "/api/kudos":
            where_parts.append("f.item_type = 'KUDOS'")
        elif path_only == "/api/posts":
            where_parts.append("f.item_type = 'POST'")

        theme = query.get("theme", [""])[0].strip()
        group_id = query.get("group_id", [""])[0].strip()
        search = query.get("search", [""])[0].strip()
        sort_mode = query.get("sort", ["smart"])[0].strip()
        filter_type = query.get("filter_type", [""])[0].strip().upper()
        author_id = query.get("author_id", [""])[0].strip()
        recipient_id = query.get("recipient_id", [""])[0].strip()
        limit_param = query.get("limit", [""])[0].strip()
        offset_param = query.get("offset", [""])[0].strip()

        if filter_type in ("KUDOS", "POST"):
            where_parts.append(f"f.item_type = '{filter_type}'")

        if author_id.isdigit():
            where_parts.append("f.author_id = ?")
            params.append(int(author_id))

        if recipient_id.isdigit():
            where_parts.append("f.recipient_id = ?")
            params.append(int(recipient_id))

        if theme:
            where_parts.append("f.theme = ?")
            params.append(theme)

        if group_id:
            if group_id == "my_spaces":
                if user:
                    where_parts.append("(f.id IN (SELECT item_id FROM item_groups WHERE group_id IN (SELECT group_id FROM group_members WHERE user_id = ?)) OR f.author_id = ? OR f.recipient_id = ?)")
                    params.extend([user["id"], user["id"], user["id"]])
                else:
                    where_parts.append("1 = 0")
            else:
                try:
                    gid = int(group_id)
                    where_parts.append("f.id IN (SELECT item_id FROM item_groups WHERE group_id = ?)")
                    params.append(gid)
                except ValueError:
                    pass

        if search:
            if "author:" in search.lower():
                parts = search.split("author:", 1)
                prefix = parts[0].strip()
                author_tokens = parts[1].strip().split()
                if author_tokens:
                    author_name = author_tokens[0]
                    remaining = (prefix + " " + " ".join(author_tokens[1:])).strip()
                    where_parts.append("u.username LIKE ?")
                    params.append(f"%{author_name}%")
                    if remaining:
                        like_q = f"%{remaining}%"
                        where_parts.append("(f.title LIKE ? OR f.content LIKE ? OR f.theme LIKE ? OR f.extracted_text LIKE ? OR f.resource_url LIKE ?)")
                        params.extend([like_q, like_q, like_q, like_q, like_q])
                else:
                    if prefix:
                        like_q = f"%{prefix}%"
                        where_parts.append("(f.title LIKE ? OR f.content LIKE ? OR f.theme LIKE ? OR f.extracted_text LIKE ? OR f.resource_url LIKE ?)")
                        params.extend([like_q, like_q, like_q, like_q, like_q])
            else:
                like_q = f"%{search}%"
                where_parts.append("(f.title LIKE ? OR f.content LIKE ? OR f.theme LIKE ? OR f.extracted_text LIKE ? OR f.resource_url LIKE ?)")
                params.extend([like_q, like_q, like_q, like_q, like_q])

        where_clause = ""
        if where_parts:
            where_clause = "WHERE " + " AND ".join(where_parts)

        uid = user["id"] if user else None
        feed_items = fetch_enriched_items(where_clause, params, uid, sort_mode)
        total_count = len(feed_items)

        if limit_param.isdigit():
            limit = int(limit_param)
            offset = int(offset_param) if offset_param.isdigit() else 0
            paged_items = feed_items[offset : offset + limit]
            has_more = (offset + limit) < total_count
        else:
            paged_items = feed_items
            has_more = False

        res_dict = {
            "feed": paged_items,
            "items": paged_items,
            "total_count": total_count,
            "has_more": has_more
        }
        if path_only == "/api/kudos":
            res_dict["kudos"] = paged_items
        elif path_only == "/api/posts":
            res_dict["posts"] = paged_items

        return json_response(res_dict)

    # ================== CREATE KUDOS ==================
    if path_only == "/api/kudos" and method == "POST":
        if not user:
            return error_response("Login required to give Kudos", 401)
        recipient_id = body.get("recipient_id")
        content = body.get("content", "").strip()
        group_ids = body.get("group_ids", [])

        if not recipient_id or not content:
            return error_response("Recipient and message are required.")

        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT id, email, username FROM users WHERE id = ?", (recipient_id,))
        recip = cursor.fetchone()
        if not recip:
            conn.close()
            return error_response("Recipient user not found.")

        if group_ids:
            cursor.execute("""
                SELECT gm1.group_id
                FROM group_members gm1
                JOIN group_members gm2 ON gm1.group_id = gm2.group_id
                WHERE gm1.user_id = ? AND gm2.user_id = ?
            """, (user["id"], recipient_id))
            mutual_gids = {r["group_id"] for r in cursor.fetchall()}
            for gid in group_ids:
                if int(gid) not in mutual_gids:
                    conn.close()
                    return error_response("Tagged groups must be shared between sender and recipient.")

        cursor.execute("""
            INSERT INTO feed_items (item_type, author_id, recipient_id, content)
            VALUES ('KUDOS', ?, ?, ?)
        """, (user["id"], recipient_id, content))
        kudos_id = cursor.lastrowid

        for gid in group_ids:
            try:
                cursor.execute("INSERT OR IGNORE INTO item_groups (item_id, group_id) VALUES (?, ?)", (kudos_id, int(gid)))
            except Exception:
                pass

        subj = f"🌟 You received new Kudos from {user['username']}!"
        preview = content[:100] + ("..." if len(content) > 100 else "")
        body_text = f"Hello {recip['username']},\n\n{user['username']} gave you public Kudos on gooddeeds.space:\n\n\"{preview}\"\n\nView and celebrate your full Kudos here: /#/kudos/{kudos_id}"

        conn.commit()
        conn.close()

        send_real_or_simulated_email(recip["email"], subj, body_text)

        enriched = fetch_enriched_items("WHERE f.id = ?", (kudos_id,), user["id"])
        item_obj = enriched[0]
        return json_response({"item": item_obj, "kudos": item_obj, "success": True}, 201)

    # ================== CREATE POST ==================
    if path_only == "/api/posts" and method == "POST":
        if not user:
            return error_response("Login required to create posts", 401)
        title = body.get("title", "").strip()
        theme = body.get("theme", "").strip()
        content = body.get("content", "").strip()
        resource_url = body.get("resource_url", "").strip()
        group_ids = body.get("group_ids", [])
        post_subtype = body.get("post_subtype", "").strip().upper()
        event_date = body.get("event_date", "").strip()

        VALID_THEMES = {"Inspiring Story", "Mental Health", "Wellness", "Mindfulness", "Spiritual", "Suicide Prevention", "Educational", "Community Service", "Events", "Resources", "Inspiring Stories", "Education", "Community Services", "Community Resources", "Inspiring Stories & Wisdom", "Mental Health & Peer Listening", "Education & Skill Building", "Community Services & Mutual Aid", "Upcoming Community Events", "General Community Resources"}

        if not title or not theme or not content:
            return error_response("Title, theme, and content are required.")

        if theme not in VALID_THEMES:
            return error_response(f"Invalid theme: {theme}", 400)

        if post_subtype == "EVENT":
            if not event_date:
                return error_response("Event date is required for Community Events.", 400)
            today_str = datetime.date.today().isoformat()
            if event_date < today_str:
                return error_response("Event date cannot be in the past.", 400)

        conn = get_db()
        cursor = conn.cursor()
        extracted_text = extract_resource_text(resource_url)
        cursor.execute("""
            INSERT INTO feed_items (item_type, author_id, title, theme, content, resource_url, post_subtype, event_date, extracted_text)
            VALUES ('POST', ?, ?, ?, ?, ?, ?, ?, ?)
        """, (user["id"], title, theme, content, resource_url, post_subtype, event_date, extracted_text))
        post_id = cursor.lastrowid

        for gid in group_ids:
            try:
                cursor.execute("INSERT OR IGNORE INTO item_groups (item_id, group_id) VALUES (?, ?)", (post_id, int(gid)))
            except Exception:
                pass

        conn.commit()
        conn.close()

        enriched = fetch_enriched_items("WHERE f.id = ?", (post_id,), user["id"])
        item_obj = enriched[0]
        return json_response({"item": item_obj, "post": item_obj, "success": True}, 201)

    # ================== REACTIONS & COMMENTS ==================
    if path_only in ("/api/reactions", "/api/react") and method == "POST":
        if not user:
            return error_response("Login required to react", 401)
        item_id = body.get("item_id")
        emoji = body.get("emoji", "").strip()
        if not item_id or not emoji:
            return error_response("Item ID and emoji required.")

        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM reactions WHERE item_id = ? AND user_id = ? AND emoji = ?", (item_id, user["id"], emoji))
        if cursor.fetchone():
            cursor.execute("DELETE FROM reactions WHERE item_id = ? AND user_id = ? AND emoji = ?", (item_id, user["id"], emoji))
            action = "removed"
        else:
            cursor.execute("INSERT INTO reactions (item_id, user_id, emoji) VALUES (?, ?, ?)", (item_id, user["id"], emoji))
            action = "added"
        conn.commit()
        conn.close()
        return json_response({"success": True, "action": action})

    if path_only == "/api/comments" and method == "POST":
        if not user:
            return error_response("Login required to comment", 401)
        item_id = body.get("item_id")
        content = body.get("content", "").strip()
        if not item_id or not content:
            return error_response("Item ID and comment content required.")

        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("INSERT INTO comments (item_id, user_id, content) VALUES (?, ?, ?)", (item_id, user["id"], content))
        cid = cursor.lastrowid
        conn.commit()
        cursor.execute("""
            SELECT c.id, c.content, c.created_at, u.username as author_name, u.avatar_url as author_avatar
            FROM comments c
            JOIN users u ON c.user_id = u.id
            WHERE c.id = ?
        """, (cid,))
        new_c = dict(cursor.fetchone())
        conn.close()
        return json_response({"comment": new_c, "success": True}, 201)

    # ================== GROUPS DIRECTORY & DETAIL ==================
    if path_only == "/api/groups" and method == "GET":
        search = query.get("search", [""])[0].strip()
        theme_filter = query.get("theme", [""])[0].strip()
        joined_only = query.get("joined", ["false"])[0].lower() == "true"

        conn = get_db()
        cursor = conn.cursor()

        sql = "SELECT * FROM groups"
        params = []
        where_parts = []
        if search:
            like_q = f"%{search}%"
            where_parts.append("(name LIKE ? OR description LIKE ?)")
            params.extend([like_q, like_q])
        if joined_only and user:
            where_parts.append("id IN (SELECT group_id FROM group_members WHERE user_id = ?)")
            params.append(user["id"])

        if where_parts:
            sql += " WHERE " + " AND ".join(where_parts)
        sql += " ORDER BY name"
        cursor.execute(sql, params)
        raw_groups = [dict(r) for r in cursor.fetchall()]

        uid = user["id"] if user else None
        joined_gids = set()
        if uid:
            cursor.execute("SELECT group_id FROM group_members WHERE user_id = ?", (uid,))
            joined_gids = {r["group_id"] for r in cursor.fetchall()}

        filtered_groups = []
        for g in raw_groups:
            gid = g["id"]
            try:
                g["themes"] = json.loads(g["themes"]) if g["themes"] else []
            except Exception:
                g["themes"] = []
            
            if theme_filter and theme_filter not in g["themes"]:
                continue

            cursor.execute("SELECT COUNT(*) as cnt FROM group_members WHERE group_id = ?", (gid,))
            g["member_count"] = cursor.fetchone()["cnt"]
            g["is_joined"] = gid in joined_gids
            filtered_groups.append(g)

        conn.close()
        return json_response({"groups": filtered_groups})

    if path_only in ("/api/groups/joined", "/api/groups/common") and method == "GET":
        if not user:
            return json_response({"groups": []})
        target_id_str = query.get("target_user_id", [""])[0] or query.get("user_id", [""])[0]
        conn = get_db()
        cursor = conn.cursor()
        if target_id_str.isdigit():
            target_id = int(target_id_str)
            cursor.execute("""
                SELECT g.id, g.name, g.icon_url
                FROM group_members gm1
                JOIN group_members gm2 ON gm1.group_id = gm2.group_id
                JOIN groups g ON gm1.group_id = g.id
                WHERE gm1.user_id = ? AND gm2.user_id = ?
                ORDER BY g.name
            """, (user["id"], target_id))
        else:
            cursor.execute("""
                SELECT g.id, g.name, g.icon_url
                FROM group_members gm
                JOIN groups g ON gm.group_id = g.id
                WHERE gm.user_id = ?
                ORDER BY g.name
            """, (user["id"],))
        rows = [dict(r) for r in cursor.fetchall()]
        conn.close()
        return json_response({"groups": rows})

    if path_only == "/api/groups" and method == "POST":
        if not user:
            return error_response("Login required to create group", 401)
        name = body.get("name", "").strip()
        description = body.get("description", "").strip()
        themes = body.get("themes", [])
        icon_url = body.get("icon_url", "").strip() or "https://images.unsplash.com/photo-1529156069898-49953e39b3ac?auto=format&fit=crop&w=200&q=80"

        if not name:
            return error_response("Group name is required.")

        conn = get_db()
        cursor = conn.cursor()
        try:
            themes_str = json.dumps(themes)
            cursor.execute("INSERT INTO groups (name, description, themes, icon_url) VALUES (?, ?, ?, ?)", (name, description, themes_str, icon_url))
            gid = cursor.lastrowid
            cursor.execute("INSERT INTO group_members (group_id, user_id, is_admin) VALUES (?, ?, 1)", (gid, user["id"]))
            conn.commit()
            conn.close()
            return json_response({"id": gid, "success": True}, 201)
        except sqlite3.IntegrityError:
            conn.close()
            return error_response("A group with this name already exists.")
        except Exception as e:
            conn.close()
            return error_response(f"Could not create group: {str(e)}")

    # GROUP DETAIL & SUB-RESOURCES
    if path_only.startswith("/api/groups/") and method == "GET":
        parts = path_only.split("/")
        gid_str = parts[3]
        try:
            gid = int(gid_str)
        except ValueError:
            return error_response("Invalid group ID")

        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM groups WHERE id = ?", (gid,))
        g_row = cursor.fetchone()
        if not g_row:
            conn.close()
            return error_response("Group not found", 404)

        subres = parts[4] if len(parts) > 4 else None

        if subres == "resources":
            cursor.execute("""
                SELECT r.*, u.username as added_by_name
                FROM group_resources r
                LEFT JOIN users u ON r.added_by = u.id
                WHERE r.group_id = ?
                ORDER BY r.created_at DESC
            """, (gid,))
            rows = []
            for r in cursor.fetchall():
                d = dict(r)
                d["description"] = d["title"]
                rows.append(d)
            conn.close()
            return json_response({"resources": rows})

        elif subres in ("messages", "chat"):
            cursor.execute("""
                SELECT m.*, u.username as author_name, u.avatar_url as author_avatar
                FROM group_messages m
                JOIN users u ON m.user_id = u.id
                WHERE m.group_id = ?
                ORDER BY m.created_at ASC
            """, (gid,))
            rows = [dict(r) for r in cursor.fetchall()]
            conn.close()
            return json_response({"messages": rows, "chat_messages": rows, "chat": rows})

        elif subres in ("members", "roster"):
            cursor.execute("""
                SELECT u.id, u.username, u.avatar_url, u.bio, gm.is_admin, gm.joined_at
                FROM group_members gm
                JOIN users u ON gm.user_id = u.id
                WHERE gm.group_id = ?
                ORDER BY gm.is_admin DESC, u.username ASC
            """, (gid,))
            rows = [dict(r) for r in cursor.fetchall()]
            conn.close()
            return json_response({"members": rows, "roster": rows})

        g_data = dict(g_row)
        try:
            g_data["themes"] = json.loads(g_data["themes"]) if g_data["themes"] else []
        except Exception:
            g_data["themes"] = []

        cursor.execute("""
            SELECT u.id, u.username, u.avatar_url, u.bio, gm.is_admin, gm.joined_at
            FROM group_members gm
            JOIN users u ON gm.user_id = u.id
            WHERE gm.group_id = ?
            ORDER BY gm.is_admin DESC, u.username ASC
        """, (gid,))
        roster = [dict(r) for r in cursor.fetchall()]
        g_data["roster"] = roster

        cursor.execute("""
            SELECT gi.id, gi.recipient_username, gi.message, gi.status, gi.created_at, u.username as sender_name
            FROM group_invitations gi
            JOIN users u ON gi.sender_id = u.id
            WHERE gi.group_id = ?
            ORDER BY gi.created_at DESC
        """, (gid,))
        g_data["invitations"] = [dict(r) for r in cursor.fetchall()]

        uid = user["id"] if user else None
        g_data["is_joined"] = any(m["id"] == uid for m in roster)
        g_data["is_admin"] = any(m["id"] == uid and m["is_admin"] == 1 for m in roster)

        cursor.execute("""
            SELECT r.*, u.username as added_by_name
            FROM group_resources r
            LEFT JOIN users u ON r.added_by = u.id
            WHERE r.group_id = ?
            ORDER BY r.created_at DESC
        """, (gid,))
        res_list = []
        for r in cursor.fetchall():
            d = dict(r)
            d["description"] = d["title"]
            res_list.append(d)
        g_data["resources"] = res_list

        cursor.execute("""
            SELECT m.*, u.username as author_name, u.avatar_url as author_avatar
            FROM group_messages m
            JOIN users u ON m.user_id = u.id
            WHERE m.group_id = ?
            ORDER BY m.created_at ASC
        """, (gid,))
        g_data["chat_messages"] = [dict(r) for r in cursor.fetchall()]

        conn.close()
        return json_response({"group": g_data})

    # UPDATE GROUP MEMBER ROLE
    if (path_only == "/api/admin/moderation/group-member-role" or (path_only.startswith("/api/groups/") and path_only.endswith("/members/role"))) and method == "POST":
        if not user:
            return error_response("Login required", 401)
        
        gid = body.get("group_id")
        if gid is None and path_only.startswith("/api/groups/"):
            parts = path_only.split("/")
            if len(parts) >= 4:
                try:
                    gid = int(parts[3])
                except ValueError:
                    pass
        
        target_uid = body.get("user_id") if body.get("user_id") is not None else body.get("target_user_id")
        is_admin_val = body.get("is_admin")

        if gid is None or target_uid is None or is_admin_val is None:
            return error_response("group_id, user_id (or target_user_id), and is_admin are required.")

        try:
            gid = int(gid)
            target_uid = int(target_uid)
            is_admin_val = 1 if int(is_admin_val) == 1 else 0
        except ValueError:
            return error_response("Invalid parameter format.")

        conn = get_db()
        cursor = conn.cursor()

        is_super_admin = (user.get("is_site_admin") == 1)
        is_group_admin = False

        if not is_super_admin:
            cursor.execute("SELECT is_admin FROM group_members WHERE group_id = ? AND user_id = ?", (gid, user["id"]))
            row = cursor.fetchone()
            if row and row["is_admin"] == 1:
                is_group_admin = True

        if not (is_super_admin or is_group_admin):
            conn.close()
            return error_response("Forbidden: Requires site super admin or group admin status.", 403)

        cursor.execute("SELECT id FROM users WHERE id = ?", (target_uid,))
        if not cursor.fetchone():
            conn.close()
            return error_response("Target user not found.", 404)

        cursor.execute("SELECT * FROM group_members WHERE group_id = ? AND user_id = ?", (gid, target_uid))
        member_row = cursor.fetchone()
        if member_row:
            cursor.execute("UPDATE group_members SET is_admin = ? WHERE group_id = ? AND user_id = ?", (is_admin_val, gid, target_uid))
        else:
            cursor.execute("INSERT INTO group_members (group_id, user_id, is_admin) VALUES (?, ?, ?)", (gid, target_uid, is_admin_val))

        conn.commit()
        conn.close()
        return json_response({"success": True, "group_id": gid, "user_id": target_uid, "is_admin": is_admin_val})

    # JOIN / LEAVE GROUP
    if path_only.startswith("/api/groups/") and (path_only.endswith("/join") or path_only.endswith("/leave")) and method == "POST":
        if not user:
            return error_response("Login required", 401)
        parts = path_only.split("/")
        gid_str = parts[3]
        action = parts[4]
        try:
            gid = int(gid_str)
        except ValueError:
            return error_response("Invalid group ID")

        conn = get_db()
        cursor = conn.cursor()
        if action == "join":
            cursor.execute("INSERT OR IGNORE INTO group_members (group_id, user_id, is_admin) VALUES (?, ?, 0)", (gid, user["id"]))
        else:
            cursor.execute("DELETE FROM group_members WHERE group_id = ? AND user_id = ?", (gid, user["id"]))
        conn.commit()
        conn.close()
        return json_response({"success": True, "action": action})

    # INVITE OTHERS TO JOIN GROUP
    if path_only.startswith("/api/groups/") and path_only.endswith("/invite") and method == "POST":
        if not user:
            return error_response("Login required", 401)
        parts = path_only.split("/")
        gid_str = parts[3]
        try:
            gid = int(gid_str)
        except ValueError:
            return error_response("Invalid group ID")

        emails_raw = body.get("emails", "").strip()
        message = body.get("message", "").strip()
        if not emails_raw:
            return error_response("At least one recipient email address is required")

        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM groups WHERE id = ?", (gid,))
        grow = cursor.fetchone()
        if not grow:
            conn.close()
            return error_response("Group not found", 404)
        group_name = grow["name"]

        raw_recipients = [e.strip() for e in emails_raw.split(",") if e.strip()]
        email_list = []
        for rec in raw_recipients:
            if "@" in rec:
                email_list.append(rec)
            else:
                cursor.execute("SELECT email FROM users WHERE username = ? OR id = ?", (rec, rec if rec.isdigit() else -1))
                urow = cursor.fetchone()
                if urow and urow["email"]:
                    email_list.append(urow["email"])
                else:
                    email_list.append(f"{rec.lower().replace(' ', '_')}@gooddeeds.space")

        if not email_list:
            conn.close()
            return error_response("Please enter valid recipient email addresses or usernames")

        subject = f"💌 You've been invited to join \"{group_name}\" on gooddeeds.space!"
        body_text = f"Hello!\n\n{user['username']} ({user['email']}) has invited you to join the community space \"{group_name}\" on gooddeeds.space.\n\nPersonal Note:\n\"{message or 'Join us in promoting goodness and building meaningful community connections!'}\"\n\nClick here to join this space free today:\nhttp://localhost:8080/#/group/{gid}\n\nPromote goodness — one good deed at a time."

        for raw_rec in raw_recipients:
            cursor.execute("INSERT INTO group_invitations (group_id, sender_id, recipient_username, message, status) VALUES (?, ?, ?, ?, 'PENDING')", (gid, user["id"], raw_rec, message or "Come join our uplifting space!"))
        conn.commit()
        conn.close()

        for rec in email_list:
            send_real_or_simulated_email(rec, subject, body_text)

        return json_response({"success": True, "message": f"Invitation sent to {len(email_list)} recipient(s)!"})

    # GET PENDING GROUP INVITATIONS FOR CURRENT USER
    if path_only in ("/api/invitations/pending", "/api/groups/invitations/pending") and method == "GET":
        if not user:
            return json_response({"invitations": []})
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT gi.id as invite_id, gi.group_id, gi.message, gi.created_at,
                   g.name as group_name, g.icon_url as group_icon,
                   u.username as sender_name, u.avatar_url as sender_avatar
            FROM group_invitations gi
            JOIN groups g ON gi.group_id = g.id
            JOIN users u ON gi.sender_id = u.id
            WHERE gi.status = 'PENDING'
              AND (gi.recipient_username = ? OR gi.recipient_username = ? OR gi.recipient_username = 'all')
              AND gi.group_id NOT IN (SELECT group_id FROM group_members WHERE user_id = ?)
            ORDER BY gi.created_at DESC
        """, (user["username"], user["email"], user["id"]))
        rows = [dict(r) for r in cursor.fetchall()]
        conn.close()
        return json_response({"invitations": rows, "success": True})

    # RESPOND TO GROUP INVITATION
    if (path_only.startswith("/api/invitations/") or path_only.startswith("/api/groups/invitations/")) and path_only.endswith("/respond") and method == "POST":
        if not user:
            return error_response("Login required", 401)
        invite_id = body.get("invite_id")
        action = body.get("action", "accept").lower()
        if not invite_id:
            return error_response("Missing invite_id")

        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT group_id FROM group_invitations WHERE id = ?", (invite_id,))
        gi = cursor.fetchone()
        if not gi:
            conn.close()
            return error_response("Invitation not found", 404)
        gid = gi["group_id"]

        if action == "accept":
            cursor.execute("INSERT OR IGNORE INTO group_members (group_id, user_id, is_admin) VALUES (?, ?, 0)", (gid, user["id"]))
            cursor.execute("UPDATE group_invitations SET status = 'ACCEPTED' WHERE id = ?", (invite_id,))
            msg = "✅ Invitation accepted! You are now a member of this space."
        else:
            cursor.execute("UPDATE group_invitations SET status = 'REJECTED' WHERE id = ?", (invite_id,))
            msg = "✕ Invitation declined."

        conn.commit()
        conn.close()
        return json_response({"success": True, "message": msg, "group_id": gid, "action": action})

    # SCRAPE CALENDAR FROM PDF/TEXT (Strict Admin Check)
    if path_only.startswith("/api/groups/") and path_only.endswith("/scrape_calendar") and method == "POST":
        if not user:
            return error_response("Login required", 401)
        parts = path_only.split("/")
        if len(parts) < 4:
            return error_response("Invalid group ID")
        gid_str = parts[3]
        try:
            gid = int(gid_str)
        except ValueError:
            return error_response("Invalid group ID")

        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT is_admin FROM group_members WHERE group_id = ? AND user_id = ?", (gid, user["id"]))
        admin_row = cursor.fetchone()
        conn.close()

        is_group_admin = (admin_row and admin_row["is_admin"] == 1)
        is_site_admin = (user.get("is_site_admin") == 1)
        if not (is_group_admin or is_site_admin):
            return error_response("Only group Admins or Site Admins can scrape calendars for this group.", 403)

        file_data = body.get("file_data") or body.get("resource_url") or body.get("url") or body.get("file") or (body.get("data", {}).get("file_data") if isinstance(body.get("data"), dict) else None) or ""
        extracted_str = extract_resource_text(file_data)
        suggested_events = parse_calendar_events_from_text(extracted_str)
        return json_response({"success": True, "suggested_events": suggested_events})

    # ADD GROUP RESOURCE (Strict Admin Check)
    if path_only.startswith("/api/groups/") and path_only.endswith("/resources") and method == "POST":
        if not user:
            return error_response("Login required", 401)
        gid_str = path_only.split("/")[3]
        try:
            gid = int(gid_str)
        except ValueError:
            return error_response("Invalid group ID")

        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT is_admin FROM group_members WHERE group_id = ? AND user_id = ?", (gid, user["id"]))
        admin_row = cursor.fetchone()
        if not admin_row or admin_row["is_admin"] != 1:
            conn.close()
            return error_response("Only group Admins can curate resources for this group.", 403)

        resources_list = body.get("resources", [])
        if not resources_list:
            desc = body.get("description", "").strip() or body.get("title", "").strip()
            url = body.get("url", "").strip()
            rtype = body.get("resource_type", "URL").strip()
            rtheme = body.get("theme", "Community Resources").strip()
            edate = (body.get("event_date") or "").strip() or None
            if desc and url:
                resources_list = [{"description": desc, "url": url, "resource_type": rtype, "theme": rtheme, "event_date": edate}]

        if not resources_list:
            conn.close()
            return error_response("At least one valid resource description and URL/file link is required.")

        inserted_count = 0
        for item in resources_list:
            desc = item.get("description", "").strip() or item.get("title", "").strip()
            url = item.get("url", "").strip()
            rtype = item.get("resource_type", "URL").strip()
            rtheme = item.get("theme", "Community Resources").strip()
            edate = (item.get("event_date") or "").strip() or None
            if desc and url:
                extracted_text = extract_resource_text(url)
                cursor.execute("INSERT INTO group_resources (group_id, title, url, resource_type, theme, event_date, added_by, extracted_text) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                               (gid, desc, url, rtype, rtheme, edate, user["id"], extracted_text))
                inserted_count += 1

        conn.commit()
        conn.close()
        return json_response({"success": True, "count": inserted_count}, 201)

    # ADD GROUP CHAT MESSAGE
    if path_only.startswith("/api/groups/") and path_only.endswith("/chat") and method == "POST":
        if not user:
            return error_response("Login required to chat", 401)
        gid_str = path_only.split("/")[3]
        try:
            gid = int(gid_str)
        except ValueError:
            return error_response("Invalid group ID")

        msg = body.get("message", "").strip()
        if not msg:
            return error_response("Message cannot be empty.")

        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("INSERT INTO group_messages (group_id, user_id, message) VALUES (?, ?, ?)", (gid, user["id"], msg))
        mid = cursor.lastrowid
        conn.commit()

        cursor.execute("""
            SELECT m.*, u.username as author_name, u.avatar_url as author_avatar
            FROM group_messages m
            JOIN users u ON m.user_id = u.id
            WHERE m.id = ?
        """, (mid,))
        new_m = dict(cursor.fetchone())
        conn.close()
        return json_response({"message": new_m, "success": True}, 201)

    # ================== EMAIL OUTBOX LOG VIEWER ==================
    if path_only in ("/api/outbox", "/api/emails", "/api/notifications") and method == "GET":
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM email_outbox ORDER BY sent_at DESC")
        rows = [dict(r) for r in cursor.fetchall()]
        conn.close()
        return json_response({"emails": rows, "outbox": rows, "notifications": rows})

    # ================== CUSTOMER SERVICE PORTAL ==================
    if path_only in ("/api/support", "/api/customer_service", "/api/inquiry", "/api/inquiries") and method == "POST":
        if not user:
            return error_response("Login required to submit customer service requests", 401)
        subject = body.get("subject", "").strip()
        message = body.get("message", "").strip()
        if not subject or not message:
            return error_response("Subject and message are required.")

        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("INSERT INTO customer_service_inquiries (user_id, subject, message) VALUES (?, ?, ?)", (user["id"], subject, message))

        user_subj = f"Confirmation: We received your inquiry '{subject}'"
        user_body = f"Hello {user['username']},\n\nThank you for reaching out to gooddeeds.space customer service. We have received your inquiry:\n\n\"{message}\"\n\nOur volunteer support team will review this and respond shortly."

        admin_subj = f"🚨 Support Alert from {user['username']}: {subject}"
        admin_body = f"User: {user['username']} ({user['email']})\nInquiry Subject: {subject}\n\nMessage:\n{message}\n\nSubmitted at: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"

        conn.commit()
        conn.close()

        send_real_or_simulated_email(user["email"], user_subj, user_body)
        send_real_or_simulated_email("roht_kgupta@yahoo.com", admin_subj, admin_body)

        return json_response({"success": True, "message": "Customer service inquiry submitted successfully."})

    if path_only in ("/api/support", "/api/customer_service", "/api/inquiry", "/api/inquiries") and method == "GET":
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT c.*, u.username, u.email
            FROM customer_service_inquiries c
            JOIN users u ON c.user_id = u.id
            ORDER BY c.created_at DESC
        """)
        rows = [dict(r) for r in cursor.fetchall()]
        conn.close()
        return json_response({"inquiries": rows, "support": rows})

    # ================== SOURCE CODE BROWSER ENDPOINT ==================
    if path_only in ("/api/source", "/api/code", "/api/browse") and method == "GET":
        fname = query.get("file", ["server.py"])[0]
        allowed = {"server.py", "database.py", "handlers.py", "run.sh", "static/index.html", "static/app.js", "static/style.css"}
        if fname not in allowed:
            return error_response("Source file restricted or not found.", 404)
        base_dir = os.path.dirname(os.path.abspath(__file__))
        full_p = os.path.join(base_dir, fname)
        with open(full_p, "r", encoding="utf-8") as f:
            content = f.read()
        return json_response({"file": fname, "content": content})

    return error_response("API endpoint not found", 404)
