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
import secrets
import datetime
import sqlite3
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from urllib.parse import parse_qs, urlparse
import urllib.request
from database import get_db, hash_password, verify_password, get_user_stats, extract_resource_text, get_platform_stats
from email_templates import (
    DEFAULT_EMAIL_PREFS,
    parse_user_email_prefs,
    is_email_pref_enabled,
    get_public_base_url,
    build_unsubscribe_url,
    build_welcome_email,
    build_email_verification_email,
    build_password_reset_email,
    build_security_alert_email,
    build_site_invitation_email,
    build_space_invitation_email,
    build_invite_accepted_email,
    build_kudos_received_email,
    build_comment_notification_email,
    build_space_announcement_email,
    build_space_chat_email,
    build_weekly_digest_email,
    build_space_role_updated_email,
    build_space_member_removed_email,
    build_support_confirmation_email,
    build_support_admin_alert_email,
    build_content_report_admin_alert_email,
    build_moderation_action_email,
    get_all_template_previews,
)

from fido2.server import Fido2Server
from fido2.webauthn import (
    PublicKeyCredentialRpEntity,
    PublicKeyCredentialUserEntity,
    AttestedCredentialData,
    RegistrationResponse,
    AuthenticationResponse,
    AuthenticatorData
)
import pickle
import base64
import dataclasses
from enum import Enum

def base64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode('utf-8').rstrip('=')

def base64url_decode(s: str) -> bytes:
    s = str(s)
    s += '=' * (4 - len(s) % 4)
    return base64.urlsafe_b64decode(s)

def serializable_fido_dict(obj):
    if isinstance(obj, bytes):
        return base64url_encode(obj)
    elif isinstance(obj, Enum):
        return obj.value
    elif isinstance(obj, dict):
        return {k: serializable_fido_dict(v) for k, v in obj.items() if v is not None}
    elif isinstance(obj, (list, tuple)):
        return [serializable_fido_dict(x) for x in obj]
    return obj

def to_camel_case(snake_str):
    components = snake_str.split('_')
    return components[0] + ''.join(x.title() for x in components[1:])

def camel_case_keys(obj):
    if isinstance(obj, dict):
        new_dict = {}
        for k, v in obj.items():
            new_key = to_camel_case(k)
            new_dict[new_key] = camel_case_keys(v)
        return new_dict
    elif isinstance(obj, list):
        return [camel_case_keys(x) for x in obj]
    return obj

_user_rate_limit_timestamps = {}
_auth_rate_limit_timestamps = {}

def get_client_ip(headers):
    """Extracts client IP address from request headers with fallback to 127.0.0.1."""
    if hasattr(headers, "get"):
        xff = headers.get("X-Forwarded-For") or headers.get("x-forwarded-for")
        if xff:
            return str(xff).split(",")[0].strip()
        real_ip = headers.get("X-Real-IP") or headers.get("x-real-ip")
        if real_ip:
            return str(real_ip).strip()
    return "127.0.0.1"

def check_auth_rate_limit(action, identifier, max_requests=10, window_seconds=60.0):
    """
    Rate limits authentication endpoints (/api/auth/login, /api/auth/signup) by IP and identifier
    to prevent brute-force credential stuffing and automated signup spam.
    Returns (is_allowed: bool, error_message: str)
    """
    import time
    now = time.time()
    key = f"{action}:{identifier}"
    timestamps = _auth_rate_limit_timestamps.get(key, [])
    timestamps = [t for t in timestamps if now - t < window_seconds]
    if len(timestamps) >= max_requests:
        return False, "Too many authentication attempts. Please wait a minute and try again."
    timestamps.append(now)
    _auth_rate_limit_timestamps[key] = timestamps
    return True, None

BLOCKLISTED_KEYWORDS = [
    "buy cheap viagra",
    "crypto scam",
    "click here to win prize",
    "free bitcoin giveaway",
    "spam-bot-payload",
    "malicious-phishing-link"
]

def check_content_moderation(user, text_fields):
    """
    Verifies rate limits and checks text content against blocklisted spam/harmful keywords.
    Returns (is_allowed: bool, error_message: str)
    """
    if not user:
        return True, None
    import time
    now = time.time()
    uid = user["id"]
    timestamps = _user_rate_limit_timestamps.get(uid, [])
    timestamps = [t for t in timestamps if now - t < 60.0]
    if len(timestamps) >= 120:
        return False, "Rate limit exceeded. Please wait a moment before posting again."
    timestamps.append(now)
    _user_rate_limit_timestamps[uid] = timestamps

    full_text = " ".join([str(t or "") for t in text_fields]).lower()
    for keyword in BLOCKLISTED_KEYWORDS:
        if keyword in full_text:
            return False, f"Content blocked by automated safety filter (prohibited phrase: '{keyword}')."
    return True, None

def get_fido_server(headers):
    origin = headers.get("Origin") or headers.get("origin")
    if not origin:
        host = headers.get("Host") or headers.get("host") or "localhost:8080"
        scheme = "http" if "localhost" in host else "https"
        origin = f"{scheme}://{host}"
    
    parsed_origin = urlparse(origin)
    rp_id = parsed_origin.hostname or "localhost"
    rp = PublicKeyCredentialRpEntity(id=rp_id, name="GoodDeeds.space")
    return Fido2Server(rp)

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
        SELECT u.id, u.email, u.username, u.phone, u.avatar_url, u.bio, u.is_site_admin, u.is_banned, u.oauth_provider, u.oauth_id,
               COALESCE(u.email_verified, 0) as email_verified, u.email_prefs
        FROM sessions s
        JOIN users u ON s.user_id = u.id
        WHERE s.token = ?
    """, (token,))
    row = cursor.fetchone()
    conn.close()
    if row:
        if row["is_banned"] == 1:
            return None
        udict = dict(row)
        udict["email_prefs"] = parse_user_email_prefs(udict.get("email_prefs"))
        return udict
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

def create_in_app_notification(conn, user_id, actor_id, notif_type, target_id, message, link_hash):
    """Inserts a real-time in-app notification for the target user."""
    if not user_id or (actor_id and int(user_id) == int(actor_id)):
        return
    try:
        conn.execute("""
            INSERT INTO notifications (user_id, actor_id, notif_type, target_id, message, link_hash)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (user_id, actor_id, notif_type, target_id, message, link_hash))
        conn.commit()
    except Exception as e:
        print(f"⚠️ Failed to insert in-app notification: {e}")

def ensure_user_unsubscribe_token(conn, user_id: int) -> str:
    """Fetches or lazily creates an opaque unsubscribe token for a user."""
    if not user_id:
        return ""
    cur = conn.cursor()
    cur.execute("SELECT unsubscribe_token FROM users WHERE id = ?", (int(user_id),))
    row = cur.fetchone()
    if row and row["unsubscribe_token"]:
        return str(row["unsubscribe_token"])
    tok = secrets.token_urlsafe(24)
    try:
        cur.execute("UPDATE users SET unsubscribe_token = ? WHERE id = ?", (tok, int(user_id)))
    except Exception:
        return ""
    return tok


def issue_auth_email_token(conn, user_id: int, token_type: str, ttl_minutes: int = 60) -> str:
    """Issues a fresh single-use token in auth_email_tokens and invalidates older unused tokens of the same type."""
    cur = conn.cursor()
    cur.execute("DELETE FROM auth_email_tokens WHERE user_id = ? AND token_type = ? AND used = 0", (int(user_id), token_type))
    tok = secrets.token_urlsafe(32)
    expires_dt = datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None) + datetime.timedelta(minutes=ttl_minutes)
    expires_str = expires_dt.strftime("%Y-%m-%d %H:%M:%S")
    cur.execute(
        "INSERT INTO auth_email_tokens (token, user_id, token_type, expires_at, used) VALUES (?, ?, ?, ?, 0)",
        (tok, int(user_id), token_type, expires_str),
    )
    return tok


def send_real_or_simulated_email(
    recipient_email,
    subject,
    text_body,
    html_body=None,
    template_key="general",
    reply_to=None,
    unsubscribe_url=None,
):
    """
    Attempts real SMTP email delivery if SMTP_HOST environment variable is set.
    
    Always records the transmission (plain text + branded HTML + metadata) in the SQLite
    email_outbox table for verification and audit purposes (accessible via /api/outbox).
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
            if reply_to:
                msg["Reply-To"] = reply_to
            if unsubscribe_url:
                msg["List-Unsubscribe"] = f"<{unsubscribe_url}>"

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
        INSERT INTO email_outbox (recipient_email, subject, body, html_body, template_key, reply_to, status)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (recipient_email, subject, text_body, html_body, template_key or "general", reply_to, delivery_status))
    conn.commit()
    conn.close()
    return delivery_status == "SENT_LIVE_SMTP"


def dispatch_email_template(recipient_email: str, tpl: dict, reply_to: str = None, unsubscribe_url: str = None):
    """Dispatches a rendered template dictionary via send_real_or_simulated_email."""
    if not recipient_email or not tpl:
        return False
    return send_real_or_simulated_email(
        recipient_email=recipient_email,
        subject=tpl["subject"],
        text_body=tpl["text_body"],
        html_body=tpl.get("html_body"),
        template_key=tpl.get("template_key", "general"),
        reply_to=reply_to,
        unsubscribe_url=unsubscribe_url,
    )


def parse_bulk_email_addresses(raw_emails):
    """
    Parses a bulk email input (string with commas, semicolons, newlines, whitespace,
    or 'Display Name <email@domain.com>' entries, or a list of strings) into
    deduplicated valid email addresses and any invalid tokens.
    """
    if not raw_emails:
        return [], []
    if isinstance(raw_emails, (list, tuple)):
        chunks = []
        for item in raw_emails:
            if item is not None:
                chunks.extend(re.split(r"[,;\n\r]+", str(item)))
    else:
        chunks = re.split(r"[,;\n\r]+", str(raw_emails))

    email_regex = re.compile(r"^[^@\s<>]+@[^@\s<>]+\.[^@\s<>]+$")
    angle_regex = re.compile(r"<([^<>]+)>")
    valid_emails = []
    invalid_tokens = []
    seen_lower = set()

    for chunk in chunks:
        c = chunk.strip()
        if not c:
            continue
        angle_match = angle_regex.search(c)
        if angle_match:
            candidate = angle_match.group(1).strip()
            candidates = [candidate] if candidate else []
        else:
            # If whitespace-separated plain emails were pasted on one line without angle brackets
            sub_parts = [p.strip().strip("'\"()") for p in c.split() if p.strip()]
            if len(sub_parts) > 1 and all("@" in p for p in sub_parts):
                candidates = sub_parts
            else:
                candidates = [c.strip("'\"()")]

        for cand in candidates:
            if not cand:
                continue
            if email_regex.match(cand):
                low = cand.lower()
                if low not in seen_lower:
                    seen_lower.add(low)
                    valid_emails.append(cand)
            else:
                invalid_tokens.append(cand)

    return valid_emails, invalid_tokens

# ================== MODULE-LEVEL FEED HELPER FUNCTIONS ==================
CANONICAL_POST_SUBTYPES = ("GENERAL", "EVENT", "RESOURCE")

def parse_post_subtypes_list(raw_val, event_date="", resource_url="", apply_legacy_fallback=False):
    """
    Parses a single or comma-separated post_subtype string (or list) into a canonical ordered list
    of subtypes from ("GENERAL", "EVENT", "RESOURCE").
    """
    tokens = []
    if isinstance(raw_val, (list, tuple)):
        raw_parts = [str(x) for x in raw_val if x is not None]
    else:
        raw_parts = str(raw_val or "").split(",")

    for part in raw_parts:
        p = part.strip().upper()
        if p in ("COMMUNITY EVENT", "UPCOMING COMMUNITY EVENT", "EVENT"):
            tokens.append("EVENT")
        elif p in ("COMMUNITY RESOURCE", "RESOURCE"):
            tokens.append("RESOURCE")
        elif p in ("GENERAL POST", "GENERAL"):
            tokens.append("GENERAL")

    ordered = [s for s in CANONICAL_POST_SUBTYPES if s in tokens]
    if apply_legacy_fallback:
        if event_date and "EVENT" not in ordered:
            ordered.append("EVENT")
            ordered = [s for s in CANONICAL_POST_SUBTYPES if s in ordered]
        if not ordered:
            has_res = bool(resource_url and str(resource_url).strip() not in ("", "[]"))
            ordered = ["RESOURCE"] if (has_res and not event_date) else ["GENERAL"]
    elif not ordered:
        ordered = ["GENERAL"]
    return ordered


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
                SELECT c.id, c.content, c.created_at, u.username as author_name, u.avatar_url as author_avatar, c.user_id
                FROM comments c
                JOIN users u ON c.user_id = u.id
                WHERE c.item_id = ?
                ORDER BY c.created_at ASC
            """, (item_id,))
            item["comments"] = [dict(c) for c in cursor.fetchall()]

            if item.get("item_type") == "POST":
                item["post_subtypes"] = parse_post_subtypes_list(
                    item.get("post_subtype"),
                    event_date=item.get("event_date") or "",
                    resource_url=item.get("resource_url") or "",
                    apply_legacy_fallback=True
                )
            else:
                item["post_subtypes"] = []

            is_joined_tag = any(g["id"] in joined_group_ids for g in item["groups"])
            item["_score"] = (100 if is_joined_tag else 0) + item["total_reactions"]

            # Blended rank score balancing fresh/new feeds with most popular/liked items
            is_new_item = (item.get("id") or 0) > 5
            affinity_boost = 100 if (is_joined_tag or (user_id and is_new_item)) else 0
            recency_boost = 0.0
            if is_new_item:
                age_hours = 0.0
                try:
                    dt_str = str(item.get("created_at") or "").replace("Z", "").split(".")[0]
                    dt = datetime.strptime(dt_str, "%Y-%m-%d %H:%M:%S")
                    now_utc = datetime.now(timezone.utc).replace(tzinfo=None)
                    age_hours = max(0.0, (now_utc - dt).total_seconds() / 3600.0)
                except Exception:
                    age_hours = 0.0
                recency_boost = round(10.0 * max(0.1, 1.0 - (age_hours / 72.0)), 4) + ((item.get("id") or 0) * 0.01)

            popularity_boost = (item.get("total_reactions") or 0) * 2.0 + len(item.get("comments") or []) * 0.5
            item["_rank_score"] = (
                (affinity_boost + popularity_boost + recency_boost)
                if is_new_item
                else float(item["_score"])
            )
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
        enriched.sort(key=lambda x: (x.get("_rank_score") or 0.0, x.get("created_at") or "", x.get("id") or 0), reverse=True)
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

# ================== CONVERSATIONAL SEARCH (LOCAL NLU + OPTIONAL GEMINI RAG) ==================

CHAT_STOP_WORDS = {
    "a", "an", "the", "is", "are", "was", "were", "be", "been", "being",
    "do", "does", "did", "have", "has", "had", "can", "could", "would", "should", "will",
    "i", "me", "my", "we", "our", "you", "your", "it", "its", "they", "them", "their",
    "there", "here", "this", "that", "these", "those", "any", "some", "all",
    "find", "search", "show", "list", "tell", "give", "get", "see", "looking", "look",
    "need", "want", "know", "for", "about", "related", "to", "in", "on", "at", "of",
    "from", "with", "by", "or", "and", "as", "into", "around", "near",
    "what", "where", "when", "who", "which", "how", "why",
    "please", "thanks", "thank", "hi", "hello", "hey", "gooddeeds", "good", "deeds",
    "community", "platform", "website", "site", "available", "current", "recent", "latest",
    "join", "joined", "joining", "explore", "browse"
}

CHAT_FOLLOWUP_PRONOUNS = {"that", "those", "it", "them", "same", "above", "previous"}

CHAT_DOMAIN_SYNONYMS = {
    "mental": ["mental", "anxiety", "wellbeing", "wellness", "nami", "crisis", "counseling", "therapy"],
    "anxiety": ["anxiety", "mental", "crisis", "ssri", "nami", "wellness"],
    "health": ["health", "healthcare", "wellness", "medical", "apple health", "medicaid", "wellbeing"],
    "healthcare": ["healthcare", "health", "medical", "medicaid", "apple health", "coverage"],
    "medicaid": ["medicaid", "apple health", "healthcare", "insurance", "federal"],
    "legal": ["legal", "wills", "will", "clinic", "attorney", "lawyer", "financial"],
    "wills": ["wills", "will", "legal", "estate", "clinic"],
    "food": ["food", "pantry", "meal", "meals", "groceries", "hunger", "mutual aid"],
    "pantry": ["pantry", "food", "restock", "mutual aid"],
    "tutor": ["tutor", "tutoring", "mentorship", "mentor", "education", "student", "learning"],
    "tutoring": ["tutor", "tutoring", "mentorship", "education", "learning"],
    "mentorship": ["mentorship", "mentor", "tutoring", "youth", "education"],
    "emergency": ["emergency", "crisis", "urgent", "hotline", "numbers", "988", "911"],
    "crisis": ["crisis", "emergency", "mental", "anxiety", "hotline"],
    "immigrant": ["immigrant", "immigration", "coverage", "healthcare"],
    "tool": ["tool", "tools", "library", "repair", "gardening"],
    "tools": ["tool", "tools", "library", "repair", "gardening"],
}


def _stem_token(tok):
    if len(tok) > 5 and tok.endswith("ing"):
        return tok[:-3]
    if len(tok) > 4 and tok.endswith("ies"):
        return tok[:-3] + "y"
    if len(tok) > 4 and tok.endswith("es"):
        return tok[:-2]
    if len(tok) > 3 and tok.endswith("s") and not tok.endswith("ss"):
        return tok[:-1]
    return tok


def _extract_chat_query_signals(raw_message, history=None):
    text_lower = (raw_message or "").lower().strip()
    raw_words = re.findall(r"[a-z0-9_@.-]+", text_lower)

    intent_subtype = ""
    intent_item_type = ""
    wants_upcoming = False
    wants_spaces = False
    wants_contact = any(w in raw_words for w in ("contact", "reach", "email", "phone", "organizer", "coordinator"))

    event_triggers = {"event", "events", "upcoming", "calendar", "schedule", "scheduled", "happening", "meetup", "meetups", "gathering", "gatherings"}
    resource_triggers = {"resource", "resources", "guide", "guides", "directory", "directories", "material", "materials", "handbook"}
    kudos_triggers = {"kudos", "gratitude", "appreciation", "appreciated", "recognized", "shoutout", "shoutouts"}
    post_triggers = {"post", "posts", "story", "stories", "discussion", "discussions"}
    space_triggers = {"space", "spaces", "group", "groups"}

    if any(w in event_triggers for w in raw_words) or "this week" in text_lower or "this month" in text_lower or "next week" in text_lower:
        intent_subtype = "EVENT"
        intent_item_type = "POST"
        if any(w in raw_words for w in ("upcoming", "next", "future", "soon", "scheduled")) or "coming up" in text_lower:
            wants_upcoming = True
    elif any(w in resource_triggers for w in raw_words):
        intent_subtype = "RESOURCE"
        intent_item_type = "POST"
    elif any(w in kudos_triggers for w in raw_words):
        intent_item_type = "KUDOS"
    elif any(w in post_triggers for w in raw_words):
        intent_item_type = "POST"

    if any(w in space_triggers for w in raw_words):
        wants_spaces = True

    intent_strip_words = event_triggers | resource_triggers | kudos_triggers | post_triggers | space_triggers | {
        "contact", "contacts", "reach", "organizer", "organizers", "info", "information"
    }
    # Preserve "will" as a topical noun when user asks about "will clinic" or "free will"
    topical_tokens = []
    for idx, w in enumerate(raw_words):
        clean_w = w.lstrip("@")
        if not clean_w or len(clean_w) < 2:
            continue
        if clean_w == "will" and ("clinic" in raw_words or "free" in raw_words or "legal" in raw_words or "estate" in raw_words):
            topical_tokens.append("wills")
            continue
        if clean_w in CHAT_STOP_WORDS or clean_w in intent_strip_words:
            continue
        if clean_w not in topical_tokens:
            topical_tokens.append(clean_w)

    # Multi-turn follow-up carryover if user refers back ("that", "those", "what about ...")
    is_followup_ref = (
        any(w in CHAT_FOLLOWUP_PRONOUNS for w in raw_words)
        or text_lower.startswith("what about")
        or text_lower.startswith("how about")
        or (wants_contact and not topical_tokens)
    )
    if not topical_tokens and is_followup_ref and isinstance(history, list):
        for prev in reversed(history):
            if isinstance(prev, dict) and prev.get("role") == "user" and prev.get("content"):
                prev_signals = _extract_chat_query_signals(prev.get("content"), history=None)
                if prev_signals["topical_tokens"]:
                    topical_tokens = prev_signals["topical_tokens"]
                    break

    return {
        "topical_tokens": topical_tokens,
        "intent_subtype": intent_subtype,
        "intent_item_type": intent_item_type,
        "wants_upcoming": wants_upcoming,
        "wants_spaces": wants_spaces,
        "wants_contact": wants_contact,
    }


def _try_gemini_rag_answer(user_message, history, matched_items, matched_spaces):
    api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not api_key or os.environ.get("DISABLE_EXTERNAL_LLM", "").strip() == "1":
        return None

    context_lines = []
    for idx, it in enumerate(matched_items[:6], 1):
        if it.get("item_type") == "KUDOS":
            context_lines.append(
                f"{idx}. [KUDOS #{it['id']}] {it.get('recipient_name', 'Member')} received Kudos from {it.get('author_name', 'Member')}: "
                f"{(it.get('content') or '')[:300]}"
            )
        else:
            subtypes_str = ", ".join(it.get("post_subtypes") or [it.get("post_subtype") or "GENERAL"])
            spaces_str = ", ".join(g.get("name", "") for g in (it.get("groups") or [])) or "General Feed"
            ev_str = f" | Event Date: {it.get('event_date')} {it.get('event_time') or ''}".strip() if it.get("event_date") else ""
            contact_str = f" | Contact: {it.get('contact_info')}" if it.get("contact_info") else ""
            aud_str = f" | Audience: {it.get('target_audience')}" if it.get("target_audience") else ""
            geo_str = f" | Geography: {it.get('target_geography')}" if it.get("target_geography") else ""
            body_snip = re.sub(r"\s+", " ", (it.get("content") or ""))[:360]
            context_lines.append(
                f"{idx}. [POST #{it['id']} | Types: {subtypes_str} | Space: {spaces_str} | Category: {it.get('category') or it.get('theme') or 'General'}"
                f"{ev_str}{contact_str}{aud_str}{geo_str}] Title: {it.get('title') or 'Untitled'} — {body_snip}"
            )

    for sp in matched_spaces[:3]:
        context_lines.append(
            f"- [SPACE #{sp['id']}] {sp['name']} ({sp.get('theme') or 'Community'}): {(sp.get('description') or '')[:220]}"
        )

    grounded_blob = "\n".join(context_lines) if context_lines else "No matching community posts, events, resources, or spaces were found in GoodDeeds.space."
    sys_prompt = (
        "You are the friendly GoodDeeds.space Community Search Assistant. "
        "Answer the user's question concisely (2-4 short sentences or compact bullets) using ONLY the GoodDeeds.space records below. "
        "Use **bold** for post titles and Space names, include event dates or contact info when relevant, and never invent facts outside the provided records.\n\n"
        f"GOODDEEDS.SPACE RECORDS:\n{grounded_blob}"
    )

    contents = []
    if isinstance(history, list):
        for turn in history[-4:]:
            if not isinstance(turn, dict):
                continue
            role = "model" if turn.get("role") == "assistant" else "user"
            txt = str(turn.get("content") or "").strip()
            if txt:
                contents.append({"role": role, "parts": [{"text": txt[:600]}]})
    contents.append({"role": "user", "parts": [{"text": user_message[:600]}]})

    payload = {
        "system_instruction": {"parts": [{"text": sys_prompt}]},
        "contents": contents,
        "generationConfig": {"temperature": 0.2, "maxOutputTokens": 320}
    }
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={api_key}"
    try:
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        with urllib.request.urlopen(req, timeout=4.0) as resp:
            resp_data = json.loads(resp.read().decode("utf-8"))
        candidates = resp_data.get("candidates") or []
        if candidates:
            parts = (candidates[0].get("content") or {}).get("parts") or []
            text_out = "".join(p.get("text", "") for p in parts).strip()
            if text_out:
                return text_out
    except Exception:
        return None
    return None


def _compose_local_nlu_answer(user_message, signals, matched_items, matched_spaces, used_broader_fallback=False):
    tokens = signals["topical_tokens"]
    intent_subtype = signals["intent_subtype"]
    intent_item_type = signals["intent_item_type"]
    wants_contact = signals["wants_contact"]
    topic_label = " ".join(tokens)

    type_noun = "community items"
    if intent_item_type == "KUDOS":
        type_noun = "Kudos"
    elif intent_subtype == "EVENT":
        type_noun = "Community Events" if len(matched_items) != 1 else "Community Event"
    elif intent_subtype == "RESOURCE":
        type_noun = "Community Resources" if len(matched_items) != 1 else "Community Resource"
    elif intent_item_type == "POST":
        type_noun = "Posts" if len(matched_items) != 1 else "Post"
    elif len(matched_items) == 1:
        type_noun = "community item"

    if not matched_items and not matched_spaces:
        if topic_label:
            return (
                f"I couldn't find any posts, events, resources, or Spaces matching **\"{topic_label}\"** right now.\n"
                "- Try asking with broader keywords (for example, *\"mental health\"*, *\"upcoming events\"*, *\"free legal help\"*, or *\"recent Kudos\"*)."
            )
        return (
            "I couldn't find matching items for that request yet. Try asking about **upcoming events**, **community resources**, **Spaces**, or **recent Kudos**!"
        )

    lines = []
    if used_broader_fallback and intent_subtype and topic_label:
        subtype_friendly = "Community Events" if intent_subtype == "EVENT" else "Community Resources"
        lines.append(
            f"I didn't find {subtype_friendly} specifically tagged for **\"{topic_label}\"**, "
            f"but I found **{len(matched_items)} related community {'item' if len(matched_items) == 1 else 'items'}** that may help:"
        )
    elif matched_items:
        if topic_label:
            lines.append(f"I found **{len(matched_items)} {type_noun}** matching **\"{topic_label}\"**" + (f" (plus **{len(matched_spaces)} {'Space' if len(matched_spaces) == 1 else 'Spaces'}**):" if matched_spaces else ":"))
        else:
            lines.append(f"Here {'is' if len(matched_items) == 1 else 'are'} **{len(matched_items)} {type_noun}** from the community:")
    elif matched_spaces:
        lines.append(f"I found **{len(matched_spaces)} Community {'Space' if len(matched_spaces) == 1 else 'Spaces'}** matching your question:")

    for it in matched_items[:3]:
        if it.get("item_type") == "KUDOS":
            snip = re.sub(r"\s+", " ", (it.get("content") or "").strip())
            if len(snip) > 110:
                snip = snip[:107].rstrip() + "..."
            lines.append(f"- 🌟 **Kudos to {it.get('recipient_name', 'Member')}** (from *{it.get('author_name', 'Member')}*): \"{snip}\"")
        else:
            subtypes = it.get("post_subtypes") or ["GENERAL"]
            badge = "📅 Event" if "EVENT" in subtypes else ("📚 Resource" if "RESOURCE" in subtypes else "📝 Post")
            if "EVENT" in subtypes and "RESOURCE" in subtypes:
                badge = "📅 Event & 📚 Resource"
            elif "GENERAL" in subtypes and "RESOURCE" in subtypes:
                badge = "📝 Post & 📚 Resource"
            title = it.get("title") or "Community Post"
            meta_bits = [badge]
            if it.get("groups"):
                meta_bits.append("in **" + ", ".join(g["name"] for g in it["groups"][:2]) + "**")
            if it.get("event_date"):
                ev_txt = f"on {it['event_date']}" + (f" at {it['event_time']}" if it.get("event_time") else "")
                meta_bits.append(ev_txt)
            if it.get("contact_info") and (wants_contact or "EVENT" in subtypes or "RESOURCE" in subtypes):
                meta_bits.append(f"Contact: {it['contact_info']}")
            lines.append(f"- **{title}** ({' • '.join(meta_bits)})")

    if matched_spaces and (signals["wants_spaces"] or not matched_items):
        for sp in matched_spaces[:3]:
            lines.append(f"- 👥 **{sp['name']}** (*{sp.get('theme') or 'Community Space'}*) — {(sp.get('description') or '')[:120]}")

    return "\n".join(lines)


def run_conversational_search(raw_message, history=None, user=None, scope=""):
    signals = _extract_chat_query_signals(raw_message, history=history)
    tokens = signals["topical_tokens"]
    intent_subtype = signals["intent_subtype"]
    intent_item_type = signals["intent_item_type"]
    wants_upcoming = signals["wants_upcoming"]

    uid = user["id"] if user else None
    all_items = fetch_enriched_items("", [], uid, "smart")

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT g.id, g.name, g.description, g.themes, g.icon_url,
               (SELECT COUNT(*) FROM group_members gm WHERE gm.group_id = g.id) as member_count
        FROM groups g
        ORDER BY member_count DESC, g.name ASC
    """)
    all_spaces = []
    for r in cursor.fetchall():
        sp_dict = dict(r)
        try:
            parsed_themes = json.loads(sp_dict.get("themes") or "[]")
            if not isinstance(parsed_themes, list):
                parsed_themes = [str(parsed_themes)]
        except Exception:
            parsed_themes = []
        sp_dict["themes"] = parsed_themes
        sp_dict["theme"] = ", ".join(str(t) for t in parsed_themes if t) or "Community Space"
        all_spaces.append(sp_dict)

    joined_space_ids = set()
    if uid:
        cursor.execute("SELECT group_id FROM group_members WHERE user_id = ?", (uid,))
        joined_space_ids = {r["group_id"] for r in cursor.fetchall()}
    conn.close()

    today_str = datetime.date.today().isoformat()
    phrase_lower = " ".join(tokens).lower()

    scored_entries = []
    for item in all_items:
        title_l = (item.get("title") or "").lower()
        content_l = (item.get("content") or "").lower()
        cat_l = ((item.get("category") or "") + " " + (item.get("theme") or "")).lower()
        groups_l = " ".join((g.get("name") or "") for g in (item.get("groups") or [])).lower()
        meta_l = " ".join([
            item.get("target_audience") or "",
            item.get("target_geography") or "",
            item.get("contact_info") or "",
            item.get("author_name") or "",
            item.get("recipient_name") or "",
        ]).lower()
        ext_l = ((item.get("extracted_text") or "") + " " + (item.get("resource_url") or "")).lower()

        topical_score = 0
        if tokens:
            if len(tokens) > 1 and phrase_lower in title_l:
                topical_score += 25
            elif len(tokens) > 1 and phrase_lower in content_l:
                topical_score += 15

            for tok in tokens:
                stem = _stem_token(tok)
                primary_candidates = {tok, stem}
                matched_primary = False
                for cand in primary_candidates:
                    if not cand or len(cand) < 2:
                        continue
                    if cand in title_l:
                        topical_score += 14
                        matched_primary = True
                    if cand in groups_l:
                        topical_score += 12
                        matched_primary = True
                    if cand in cat_l:
                        topical_score += 10
                        matched_primary = True
                    if cand in meta_l:
                        topical_score += 9
                        matched_primary = True
                    if cand in content_l:
                        topical_score += 7
                        matched_primary = True
                    if cand in ext_l:
                        topical_score += 5
                        matched_primary = True

                if not matched_primary:
                    for syn in CHAT_DOMAIN_SYNONYMS.get(tok, CHAT_DOMAIN_SYNONYMS.get(stem, [])):
                        if syn in title_l or syn in groups_l or syn in cat_l:
                            topical_score += 6
                        elif syn in content_l or syn in meta_l or syn in ext_l:
                            topical_score += 3

        subtypes = item.get("post_subtypes") or []
        matches_type_strict = True
        if intent_item_type == "KUDOS":
            matches_type_strict = (item.get("item_type") == "KUDOS")
        elif intent_subtype == "EVENT":
            matches_type_strict = (item.get("item_type") == "POST" and ("EVENT" in subtypes or bool(item.get("event_date"))))
            if matches_type_strict and wants_upcoming and item.get("event_date"):
                ev_d = str(item.get("event_date")).split("T")[0]
                if ev_d < today_str:
                    matches_type_strict = False
        elif intent_subtype == "RESOURCE":
            matches_type_strict = (item.get("item_type") == "POST" and "RESOURCE" in subtypes)
        elif intent_item_type == "POST":
            matches_type_strict = (item.get("item_type") == "POST")

        if tokens and topical_score == 0:
            continue

        total_score = topical_score
        if matches_type_strict:
            total_score += 20
        if scope == "my_spaces" and joined_space_ids:
            item_gids = {g.get("id") for g in (item.get("groups") or [])}
            if item_gids & joined_space_ids:
                total_score += 4

        scored_entries.append((total_score, topical_score, matches_type_strict, item))

    strict_matches = [e for e in scored_entries if e[2]]
    used_broader_fallback = False

    if strict_matches:
        chosen = strict_matches
    elif tokens and scored_entries:
        chosen = scored_entries
        used_broader_fallback = True
    else:
        chosen = []

    if intent_subtype == "EVENT" and not used_broader_fallback:
        def _event_sort_key(entry):
            ev_date = str(entry[3].get("event_date") or "9999-99-99").split("T")[0]
            is_upcoming_flag = 0 if ev_date >= today_str else 1
            return (-entry[1], is_upcoming_flag, ev_date if is_upcoming_flag == 0 else "")
        chosen.sort(key=_event_sort_key)
    else:
        chosen.sort(key=lambda e: (-e[0], -int(e[3].get("id") or 0)))

    matched_items = [e[3] for e in chosen[:8]]

    # Score Community Spaces as well
    matched_spaces = []
    if signals["wants_spaces"] and not tokens:
        matched_spaces = all_spaces[:5]
    elif tokens:
        space_scored = []
        for sp in all_spaces:
            sp_blob = f"{sp.get('name') or ''} {sp.get('description') or ''} {sp.get('theme') or ''}".lower()
            s_score = 0
            for tok in tokens:
                stem = _stem_token(tok)
                if tok in (sp.get("name") or "").lower() or stem in (sp.get("name") or "").lower():
                    s_score += 15
                elif tok in sp_blob or stem in sp_blob:
                    s_score += 7
                else:
                    for syn in CHAT_DOMAIN_SYNONYMS.get(tok, CHAT_DOMAIN_SYNONYMS.get(stem, [])):
                        if syn in sp_blob:
                            s_score += 4
            if s_score > 0:
                space_scored.append((s_score, sp))
        space_scored.sort(key=lambda x: -x[0])
        matched_spaces = [x[1] for x in space_scored[:3]]
        if signals["wants_spaces"] and not matched_spaces:
            matched_spaces = all_spaces[:5]

    llm_answer = _try_gemini_rag_answer(raw_message, history, matched_items, matched_spaces)
    if llm_answer:
        answer = llm_answer
        engine = "gemini_rag"
    else:
        answer = _compose_local_nlu_answer(raw_message, signals, matched_items, matched_spaces, used_broader_fallback=used_broader_fallback)
        engine = "local_nlu"

    suggested_followups = []
    if intent_subtype != "EVENT":
        suggested_followups.append("What upcoming events are scheduled?")
    if intent_subtype != "RESOURCE":
        suggested_followups.append("Are there mental health or wellness resources?")
    if intent_item_type != "KUDOS":
        suggested_followups.append("Show recent community Kudos")
    if not signals["wants_spaces"]:
        suggested_followups.append("Which Community Spaces can I join?")

    return {
        "success": True,
        "engine": engine,
        "answer": answer,
        "matched_items": matched_items,
        "matched_item_ids": [it["id"] for it in matched_items],
        "matched_spaces": matched_spaces,
        "detected_intent": {
            "subtype": intent_subtype,
            "item_type": intent_item_type,
            "keywords": tokens,
            "upcoming_only": wants_upcoming,
        },
        "suggested_followups": suggested_followups[:3],
    }

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
    base_url = get_public_base_url(headers)

    # ================== HOST & CSRF / ORIGIN PROTECTION ==================
    if method in ("POST", "PUT", "DELETE"):
        host_hdr = (headers.get("Host") or headers.get("host") or "").strip() if hasattr(headers, "get") else ""
        if host_hdr:
            allowed_hosts_env = os.environ.get("ALLOWED_HOSTS", "localhost,127.0.0.1,gooddeeds.space,www.gooddeeds.space")
            allowed_hosts = [h.strip().lower() for h in allowed_hosts_env.split(",") if h.strip()]
            render_host = os.environ.get("RENDER_EXTERNAL_HOSTNAME", "").strip().lower()
            if render_host:
                allowed_hosts.append(render_host)
            host_only = host_hdr.split(":")[0].lower()
            trusted_suffixes = (".onrender.com", ".googlers.com", ".run.app", ".fly.dev", ".railway.app", ".herokuapp.com", ".vercel.app")
            is_trusted_suffix = any(host_only.endswith(sfx) for sfx in trusted_suffixes)
            if "*" not in allowed_hosts and host_only not in allowed_hosts and not is_trusted_suffix:
                return error_response("Bad Request: Invalid or untrusted Host header.", 400)

            origin_hdr = (headers.get("Origin") or headers.get("origin") or "").strip() if hasattr(headers, "get") else ""
            referer_hdr = (headers.get("Referer") or headers.get("referer") or "").strip() if hasattr(headers, "get") else ""
            if origin_hdr and origin_hdr != "null":
                origin_host = urlparse(origin_hdr).netloc
                if origin_host != host_hdr:
                    return error_response("Forbidden: CSRF Origin mismatch.", 403)
            elif referer_hdr:
                referer_host = urlparse(referer_hdr).netloc
                if referer_host != host_hdr:
                    return error_response("Forbidden: CSRF Referer mismatch.", 403)
            else:
                return error_response("Forbidden: CSRF check failed (missing Origin or Referer header).", 403)

    # ================== PLATFORM STATS ENDPOINTS ==================
    if path_only in ("/api/stats", "/api/landing_stats", "/stats", "/landing_stats") and method == "GET":
        stats = get_platform_stats()
        return json_response({"success": True, "stats": stats})

    # ================== AUTH ENDPOINTS ==================
    # 1. WebAuthn Registration Challenge
    if path_only == "/api/auth/webauthn/register/challenge" and method == "POST":
        if not user:
            return error_response("Login required", 401)
        
        conn = get_db()
        cursor = conn.cursor()
        
        # Cleanup expired challenges
        cursor.execute("DELETE FROM webauthn_challenges WHERE created_at < datetime('now', '-5 minutes')")
        
        # Fetch existing credentials to exclude them
        cursor.execute("SELECT public_key FROM passkeys WHERE user_id = ?", (user["id"],))
        exclude_credentials = []
        for r in cursor.fetchall():
            try:
                cred = AttestedCredentialData(r["public_key"])
                exclude_credentials.append(cred)
            except Exception:
                pass
        
        server = get_fido_server(headers)
        user_entity = PublicKeyCredentialUserEntity(
            id=str(user["id"]).encode("utf-8"),
            name=user["email"],
            display_name=user["username"]
        )
        
        try:
            options, state = server.register_begin(
                user_entity,
                credentials=exclude_credentials
            )
        except Exception as e:
            conn.close()
            return error_response(f"Failed to begin registration: {e}", 400)
        
        challenge_str = base64url_encode(options.public_key.challenge)
        state_bytes = pickle.dumps(state)
        
        try:
            cursor.execute("""
                INSERT INTO webauthn_challenges (challenge, user_id, state)
                VALUES (?, ?, ?)
            """, (challenge_str, user["id"], state_bytes))
            conn.commit()
        except Exception as e:
            conn.close()
            return error_response(f"Database error: {e}", 500)
            
        conn.close()
        
        options_dict = camel_case_keys(serializable_fido_dict(dataclasses.asdict(options)))
        return json_response(options_dict)

    # 2. WebAuthn Registration Verify
    if path_only == "/api/auth/webauthn/register/verify" and method == "POST":
        if not user:
            return error_response("Login required", 401)
        
        try:
            client_data_json = base64url_decode(body.get("response", {}).get("clientDataJSON", ""))
            client_data = json.loads(client_data_json.decode("utf-8"))
            challenge_str = client_data.get("challenge")
        except Exception:
            return error_response("Invalid clientDataJSON", 400)
            
        if not challenge_str:
            return error_response("Challenge missing from clientDataJSON", 400)
            
        conn = get_db()
        cursor = conn.cursor()
        
        # Look up challenge and verify not expired
        cursor.execute("""
            SELECT user_id, state FROM webauthn_challenges
            WHERE challenge = ? AND created_at >= datetime('now', '-5 minutes')
        """, (challenge_str,))
        row = cursor.fetchone()
        if not row:
            # Check if it exists but expired
            cursor.execute("SELECT user_id FROM webauthn_challenges WHERE challenge = ?", (challenge_str,))
            exists_expired = cursor.fetchone()
            if exists_expired:
                cursor.execute("DELETE FROM webauthn_challenges WHERE challenge = ?", (challenge_str,))
                conn.commit()
                conn.close()
                return error_response("Challenge expired.", 400)
            conn.close()
            return error_response("Registration challenge not found or expired.", 400)
            
        if row["user_id"] != user["id"]:
            conn.close()
            return error_response("User mismatch.", 400)
            
        state = pickle.loads(row["state"])
        server = get_fido_server(headers)
        
        try:
            reg_resp = RegistrationResponse.from_dict(body)
            auth_data = server.register_complete(state, reg_resp)
            cred_data = auth_data.credential_data
        except Exception as e:
            conn.close()
            return error_response(f"Verification failed: {str(e)}", 400)
            
        cred_id_str = base64url_encode(cred_data.credential_id)
        pub_key_bytes = bytes(cred_data)
        device_name = body.get("deviceName", "Unknown Device")
        if len(device_name) > 50:
            device_name = device_name[:50]
            
        try:
            cursor.execute("""
                INSERT INTO passkeys (credential_id, user_id, public_key, sign_count, device_name)
                VALUES (?, ?, ?, ?, ?)
            """, (cred_id_str, user["id"], pub_key_bytes, auth_data.counter, device_name))
            cursor.execute("DELETE FROM webauthn_challenges WHERE challenge = ?", (challenge_str,))
            conn.commit()
        except sqlite3.IntegrityError:
            conn.rollback()
            conn.close()
            return error_response("Credential already registered.", 400)
        except Exception as e:
            conn.rollback()
            conn.close()
            return error_response(f"Database error: {e}", 500)
            
        conn.close()
        dispatch_email_template(
            user["email"],
            build_security_alert_email(user["username"], f"New Passkey registered ({device_name})", base_url),
        )
        return json_response({"success": True})

    # 3. WebAuthn Login Challenge
    if path_only == "/api/auth/webauthn/login/challenge" and method == "POST":
        username_or_email = body.get("username") or body.get("email") or ""
        username_or_email = username_or_email.strip()
        
        conn = get_db()
        cursor = conn.cursor()
        
        # Cleanup expired challenges
        cursor.execute("DELETE FROM webauthn_challenges WHERE created_at < datetime('now', '-5 minutes')")
        
        credentials = []
        user_id = None
        
        if username_or_email:
            cursor.execute("""
                SELECT id FROM users
                WHERE LOWER(email) = LOWER(?) OR LOWER(username) = LOWER(?)
            """, (username_or_email, username_or_email))
            row = cursor.fetchone()
            if row:
                user_id = row["id"]
                cursor.execute("SELECT public_key FROM passkeys WHERE user_id = ?", (user_id,))
                for r in cursor.fetchall():
                    try:
                        credentials.append(AttestedCredentialData(r["public_key"]))
                    except Exception:
                        pass
            else:
                conn.close()
                return error_response("User not found", 404)
                
        server = get_fido_server(headers)
        try:
            options, state = server.authenticate_begin(credentials=credentials)
        except Exception as e:
            conn.close()
            return error_response(f"Failed to begin authentication: {e}", 400)
        
        challenge_str = base64url_encode(options.public_key.challenge)
        state_bytes = pickle.dumps(state)
        
        try:
            cursor.execute("""
                INSERT INTO webauthn_challenges (challenge, user_id, state)
                VALUES (?, ?, ?)
            """, (challenge_str, user_id, state_bytes))
            conn.commit()
        except Exception as e:
            conn.close()
            return error_response(f"Database error: {e}", 500)
            
        conn.close()
        
        options_dict = camel_case_keys(serializable_fido_dict(dataclasses.asdict(options)))
        return json_response(options_dict)

    # 4. WebAuthn Login Verify
    if path_only == "/api/auth/webauthn/login/verify" and method == "POST":
        try:
            client_data_json = base64url_decode(body.get("response", {}).get("clientDataJSON", ""))
            client_data = json.loads(client_data_json.decode("utf-8"))
            challenge_str = client_data.get("challenge")
        except Exception:
            return error_response("Invalid clientDataJSON", 400)
            
        if not challenge_str:
            return error_response("Challenge missing from clientDataJSON", 400)
            
        conn = get_db()
        cursor = conn.cursor()
        
        # Look up challenge and verify not expired
        cursor.execute("""
            SELECT user_id, state FROM webauthn_challenges
            WHERE challenge = ? AND created_at >= datetime('now', '-5 minutes')
        """, (challenge_str,))
        challenge_row = cursor.fetchone()
        if not challenge_row:
            # Check if expired
            cursor.execute("SELECT user_id FROM webauthn_challenges WHERE challenge = ?", (challenge_str,))
            exists_expired = cursor.fetchone()
            if exists_expired:
                cursor.execute("DELETE FROM webauthn_challenges WHERE challenge = ?", (challenge_str,))
                conn.commit()
                conn.close()
                return error_response("Challenge expired.", 400)
            conn.close()
            return error_response("Login challenge not found or expired.", 400)
            
        state = pickle.loads(challenge_row["state"])
        
        cred_id_b64 = body.get("id")
        if not cred_id_b64:
            conn.close()
            return error_response("Credential ID missing", 400)
            
        cursor.execute("""
            SELECT user_id, public_key, sign_count FROM passkeys
            WHERE credential_id = ?
        """, (cred_id_b64,))
        passkey_row = cursor.fetchone()
        if not passkey_row:
            conn.close()
            return error_response("Passkey not registered on this server.", 401)
            
        target_user_id = passkey_row["user_id"]
        stored_sign_count = passkey_row["sign_count"]
        
        if challenge_row["user_id"] is not None and challenge_row["user_id"] != target_user_id:
            conn.close()
            return error_response("User mismatch.", 400)
            
        cred = AttestedCredentialData(passkey_row["public_key"])
        server = get_fido_server(headers)
        
        try:
            assert_resp = AuthenticationResponse.from_dict(body)
            server.authenticate_complete(state, [cred], assert_resp)
            
            # Robust counter retrieval
            try:
                new_sign_count = assert_resp.response.authenticator_data.counter
            except Exception:
                auth_data_bytes = base64url_decode(body.get("response", {}).get("authenticatorData", ""))
                auth_data = AuthenticatorData(auth_data_bytes)
                new_sign_count = auth_data.counter
                
        except Exception as e:
            conn.close()
            return error_response(f"Verification failed: {str(e)}", 401)
            
        if new_sign_count > 0 and new_sign_count <= stored_sign_count:
            conn.close()
            return error_response("Signature counter verification failed (possible replay attack).", 401)
            
        try:
            cursor.execute("""
                UPDATE passkeys SET sign_count = ? WHERE credential_id = ?
            """, (new_sign_count, cred_id_b64))
            cursor.execute("DELETE FROM webauthn_challenges WHERE challenge = ?", (challenge_str,))
            
            token = str(uuid.uuid4())
            cursor.execute("INSERT INTO sessions (token, user_id) VALUES (?, ?)", (token, target_user_id))
            
            cursor.execute("""
                SELECT id, email, username, phone, avatar_url, bio, is_site_admin, oauth_provider, oauth_id,
                       COALESCE(email_verified, 0) as email_verified, email_prefs
                FROM users WHERE id = ?
            """, (target_user_id,))
            user_dict = dict(cursor.fetchone())
            user_dict["email_prefs"] = parse_user_email_prefs(user_dict.get("email_prefs"))
            
            conn.commit()
        except Exception as e:
            conn.rollback()
            conn.close()
            return error_response(f"Database error during login: {e}", 500)
            
        conn.close()
        return json_response({"token": token, "user": user_dict, "success": True})

    if path_only == "/api/auth/signup" and method == "POST":
        client_ip = get_client_ip(headers)
        is_allowed, err_msg = check_auth_rate_limit("signup", client_ip, max_requests=5, window_seconds=60.0)
        if not is_allowed:
            return error_response(err_msg, 429)

        email = body.get("email", "").strip()
        username = body.get("username", "").strip()
        password = body.get("password", "")
        phone = body.get("phone", "").strip()
        avatar_url = body.get("avatar_url", "").strip() or "https://images.unsplash.com/photo-1534528741775-53994a69daeb?auto=format&fit=crop&w=200&q=80"
        bio = body.get("bio", "").strip()

        full_signup_text = f"{email} {username} {bio}".lower()
        for keyword in BLOCKLISTED_KEYWORDS:
            if keyword in full_signup_text:
                return error_response(f"Registration blocked by automated safety filter (prohibited phrase: '{keyword}').", 400)

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
            ensure_user_unsubscribe_token(conn, user_id)
            verify_tok = issue_auth_email_token(conn, user_id, "VERIFY_EMAIL", ttl_minutes=24 * 60)
            token = str(uuid.uuid4())
            cursor.execute("INSERT INTO sessions (token, user_id) VALUES (?, ?)", (token, user_id))
            inviter_notifications = []
            try:
                cursor.execute("""
                    SELECT id, sender_id FROM site_invitations
                    WHERE LOWER(recipient_email) = LOWER(?) AND status = 'PENDING'
                """, (email,))
                pending_site_invites = cursor.fetchall()
                if pending_site_invites:
                    cursor.execute("""
                        UPDATE site_invitations SET status = 'ACCEPTED'
                        WHERE LOWER(recipient_email) = LOWER(?) AND status = 'PENDING'
                    """, (email,))
                    seen_senders = set()
                    for sinv in pending_site_invites:
                        sid = sinv["sender_id"]
                        if sid and sid not in seen_senders:
                            seen_senders.add(sid)
                            create_in_app_notification(
                                conn,
                                sid,
                                user_id,
                                "SITE_INVITE_ACCEPTED",
                                user_id,
                                f"🎉 @{username} ({email}) accepted your invitation and joined GoodDeeds.space!",
                                f"/#/user/{user_id}"
                            )
                            cursor.execute("SELECT id, username, email, email_prefs FROM users WHERE id = ?", (sid,))
                            inv_row = cursor.fetchone()
                            if inv_row and is_email_pref_enabled(inv_row["email_prefs"], "invites"):
                                inv_unsub = ensure_user_unsubscribe_token(conn, sid)
                                inviter_notifications.append((
                                    inv_row["email"],
                                    inv_row["username"],
                                    build_unsubscribe_url(base_url, inv_unsub, "invites"),
                                ))
            except Exception:
                pass
            conn.commit()
            cursor.execute("""
                SELECT id, email, username, phone, avatar_url, bio, is_site_admin, oauth_provider, oauth_id,
                       COALESCE(email_verified, 0) as email_verified, email_prefs
                FROM users WHERE id = ?
            """, (user_id,))
            new_user = dict(cursor.fetchone())
            new_user["email_prefs"] = parse_user_email_prefs(new_user.get("email_prefs"))
            conn.close()

            verify_url = f"{base_url}/#/verify-email?token={verify_tok}"
            dispatch_email_template(email, build_welcome_email(username, verify_url, base_url))
            for inv_email, inv_uname, inv_unsub_url in inviter_notifications:
                dispatch_email_template(
                    inv_email,
                    build_invite_accepted_email(inv_uname, username, user_id, inv_unsub_url, base_url),
                    unsubscribe_url=inv_unsub_url,
                )

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
        client_ip = get_client_ip(headers)
        login_key = f"{client_ip}:{email.lower()}" if email else client_ip
        is_allowed, err_msg = check_auth_rate_limit("login", login_key, max_requests=10, window_seconds=60.0)
        if not is_allowed:
            return error_response(err_msg, 429)

        if not email or not password:
            return error_response("Email and password are required.")
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, email, username, password_hash, phone, avatar_url, bio, is_site_admin, is_banned, oauth_provider, oauth_id,
                   COALESCE(email_verified, 0) as email_verified, email_prefs
            FROM users
            WHERE LOWER(email) = LOWER(?) OR LOWER(username) = LOWER(?)
        """, (email, email))
        row = cursor.fetchone()
        if not row or not verify_password(password, row["password_hash"]):
            conn.close()
            return error_response("Invalid email or password.", 401)
        if row["is_banned"] == 1:
            conn.close()
            return error_response("Account suspended by site administration.", 403)
        user_dict = dict(row)
        user_dict["email_prefs"] = parse_user_email_prefs(user_dict.get("email_prefs"))
        stored_pw_hash = user_dict.pop("password_hash", "")
        # Transparently upgrade legacy unsalted hashes to salted PBKDF2-HMAC-SHA256 on login
        if not str(stored_pw_hash).startswith("pbkdf2_sha256$"):
            new_salted_hash = hash_password(password)
            cursor.execute("UPDATE users SET password_hash = ? WHERE id = ?", (new_salted_hash, user_dict["id"]))
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
            is_new_google_user = False
            if existing_row:
                user_dict = dict(existing_row)
                new_avatar = user_dict.get("avatar_url") or ""
                if (not new_avatar or not str(new_avatar).strip()) and avatar_url:
                    new_avatar = avatar_url
                    cursor.execute("""
                        UPDATE users
                        SET oauth_provider = 'google', oauth_id = ?, avatar_url = ?, email_verified = 1
                        WHERE id = ?
                    """, (oauth_id, new_avatar, user_dict["id"]))
                else:
                    cursor.execute("""
                        UPDATE users
                        SET oauth_provider = 'google', oauth_id = ?, email_verified = 1
                        WHERE id = ?
                    """, (oauth_id, user_dict["id"]))
                conn.commit()
                cursor.execute("""
                    SELECT id, email, username, phone, avatar_url, bio, is_site_admin, oauth_provider, oauth_id,
                           COALESCE(email_verified, 0) as email_verified, email_prefs
                    FROM users WHERE id = ?
                """, (user_dict["id"],))
                user_dict = dict(cursor.fetchone())
                user_dict["email_prefs"] = parse_user_email_prefs(user_dict.get("email_prefs"))
            else:
                is_new_google_user = True
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
                    INSERT INTO users (email, username, password_hash, avatar_url, bio, oauth_provider, oauth_id, email_verified)
                    VALUES (?, ?, 'OAUTH_GOOGLE', ?, ?, 'google', ?, 1)
                """, (email, username, avatar_url, bio, oauth_id))
                user_id = cursor.lastrowid
                ensure_user_unsubscribe_token(conn, user_id)
                conn.commit()
                cursor.execute("""
                    SELECT id, email, username, phone, avatar_url, bio, is_site_admin, oauth_provider, oauth_id,
                           COALESCE(email_verified, 0) as email_verified, email_prefs
                    FROM users WHERE id = ?
                """, (user_id,))
                user_dict = dict(cursor.fetchone())
                user_dict["email_prefs"] = parse_user_email_prefs(user_dict.get("email_prefs"))

            token = str(uuid.uuid4())
            cursor.execute("INSERT INTO sessions (token, user_id) VALUES (?, ?)", (token, user_dict["id"]))
            conn.commit()
            conn.close()
            if is_new_google_user:
                dispatch_email_template(email, build_welcome_email(user_dict["username"], "", base_url))
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

    # ================== PASSWORD RESET, EMAIL VERIFICATION & PREFERENCES ==================
    if path_only == "/api/auth/forgot_password" and method == "POST":
        client_ip = get_client_ip(headers)
        is_allowed, err_msg = check_auth_rate_limit("forgot_pw", client_ip, max_requests=5, window_seconds=60.0)
        if not is_allowed:
            return error_response(err_msg, 429)

        email_in = str(body.get("email") or "").strip()
        if not email_in:
            return error_response("Please enter your account email address.", 400)

        conn = get_db()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id, username, email, is_banned FROM users WHERE LOWER(email) = LOWER(?)",
            (email_in,),
        )
        u_row = cursor.fetchone()
        reset_dispatch = None
        if u_row and u_row["is_banned"] != 1:
            tok = issue_auth_email_token(conn, u_row["id"], "PASSWORD_RESET", ttl_minutes=60)
            conn.commit()
            reset_url = f"{base_url}/#/reset-password?token={tok}"
            reset_dispatch = (u_row["email"], u_row["username"], reset_url)
        conn.close()

        if reset_dispatch:
            dispatch_email_template(
                reset_dispatch[0],
                build_password_reset_email(reset_dispatch[1], reset_dispatch[2], 60, base_url),
            )

        return json_response({
            "success": True,
            "message": "If an account exists for that email address, a password reset link has been sent.",
        })

    if path_only == "/api/auth/reset_password" and method == "POST":
        tok = str(body.get("token") or "").strip()
        new_password = str(body.get("new_password") or body.get("password") or "")
        if not tok:
            return error_response("Password reset token is required.", 400)
        if len(new_password) < 6:
            return error_response("New password must be at least 6 characters long.", 400)

        now_utc_str = datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None).strftime("%Y-%m-%d %H:%M:%S")
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT t.token, t.user_id, t.expires_at, t.used, u.username, u.email, u.is_banned
            FROM auth_email_tokens t
            JOIN users u ON t.user_id = u.id
            WHERE t.token = ? AND t.token_type = 'PASSWORD_RESET'
        """, (tok,))
        t_row = cursor.fetchone()
        if not t_row or t_row["used"] == 1 or str(t_row["expires_at"]) < now_utc_str:
            conn.close()
            return error_response("This password reset link is invalid or has expired. Please request a new one.", 400)
        if t_row["is_banned"] == 1:
            conn.close()
            return error_response("Account suspended by site administration.", 403)

        pw_hash = hash_password(new_password)
        cursor.execute("UPDATE users SET password_hash = ? WHERE id = ?", (pw_hash, t_row["user_id"]))
        cursor.execute("UPDATE auth_email_tokens SET used = 1 WHERE token = ?", (tok,))
        cursor.execute("DELETE FROM sessions WHERE user_id = ?", (t_row["user_id"],))
        conn.commit()
        conn.close()

        dispatch_email_template(
            t_row["email"],
            build_security_alert_email(t_row["username"], "Account password was reset", base_url),
        )
        return json_response({
            "success": True,
            "message": "Your password has been updated! You can now log in with your new password.",
        })

    if path_only == "/api/auth/send_verification" and method == "POST":
        if not user:
            return error_response("Login required", 401)
        if user.get("email_verified") == 1:
            return json_response({
                "success": True,
                "already_verified": True,
                "message": "Your email address is already verified.",
            })
        conn = get_db()
        tok = issue_auth_email_token(conn, user["id"], "VERIFY_EMAIL", ttl_minutes=24 * 60)
        conn.commit()
        conn.close()

        verify_url = f"{base_url}/#/verify-email?token={tok}"
        dispatch_email_template(
            user["email"],
            build_email_verification_email(user["username"], verify_url, base_url),
        )
        return json_response({
            "success": True,
            "message": f"Verification email sent to {user['email']}.",
        })

    if path_only == "/api/auth/verify_email" and method == "POST":
        tok = str(body.get("token") or "").strip()
        if not tok:
            return error_response("Verification token is required.", 400)
        now_utc_str = datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None).strftime("%Y-%m-%d %H:%M:%S")
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT t.token, t.user_id, t.expires_at, t.used, u.username, u.email
            FROM auth_email_tokens t
            JOIN users u ON t.user_id = u.id
            WHERE t.token = ? AND t.token_type = 'VERIFY_EMAIL'
        """, (tok,))
        t_row = cursor.fetchone()
        if not t_row or t_row["used"] == 1 or str(t_row["expires_at"]) < now_utc_str:
            conn.close()
            return error_response("This verification link is invalid or has expired.", 400)

        cursor.execute("UPDATE users SET email_verified = 1 WHERE id = ?", (t_row["user_id"],))
        cursor.execute("UPDATE auth_email_tokens SET used = 1 WHERE token = ?", (tok,))
        conn.commit()
        conn.close()
        return json_response({
            "success": True,
            "email": t_row["email"],
            "username": t_row["username"],
            "message": "Email verified successfully!",
        })

    if path_only == "/api/email/preferences" and method in ("GET", "PUT"):
        if not user:
            return error_response("Login required", 401)
        if method == "GET":
            return json_response({
                "success": True,
                "email_verified": user.get("email_verified", 0),
                "email_prefs": user.get("email_prefs", dict(DEFAULT_EMAIL_PREFS)),
            })
        raw_in = body.get("email_prefs") if isinstance(body.get("email_prefs"), dict) else body
        merged = dict(user.get("email_prefs") or DEFAULT_EMAIL_PREFS)
        for k in DEFAULT_EMAIL_PREFS:
            if k in raw_in:
                merged[k] = bool(raw_in[k])
        conn = get_db()
        conn.execute("UPDATE users SET email_prefs = ? WHERE id = ?", (json.dumps(merged), user["id"]))
        conn.commit()
        conn.close()
        return json_response({"success": True, "email_prefs": merged})

    if path_only == "/api/email/unsubscribe" and method == "POST":
        tok = str(body.get("token") or "").strip()
        category = str(body.get("category") or "all").strip().lower()
        if not tok:
            return error_response("Unsubscribe token is required.", 400)
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT id, username, email, email_prefs FROM users WHERE unsubscribe_token = ?", (tok,))
        u_row = cursor.fetchone()
        if not u_row:
            conn.close()
            return error_response("Invalid unsubscribe link.", 400)
        prefs = parse_user_email_prefs(u_row["email_prefs"])
        if category == "all":
            for k in DEFAULT_EMAIL_PREFS:
                prefs[k] = False
        elif category in DEFAULT_EMAIL_PREFS:
            prefs[category] = False
        else:
            for k in DEFAULT_EMAIL_PREFS:
                prefs[k] = False
            category = "all"
        cursor.execute("UPDATE users SET email_prefs = ? WHERE id = ?", (json.dumps(prefs), u_row["id"]))
        conn.commit()
        conn.close()
        return json_response({
            "success": True,
            "username": u_row["username"],
            "category": category,
            "email_prefs": prefs,
            "message": f"Unsubscribed from {'all optional community emails' if category == 'all' else category.replace('_', ' ') + ' emails'}.",
        })

    if path_only == "/api/email/send_digest" and method == "POST":
        if not user:
            return error_response("Login required", 401)
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT g.id, g.name
            FROM group_members gm
            JOIN groups g ON gm.group_id = g.id
            WHERE gm.user_id = ?
            ORDER BY g.name
        """, (user["id"],))
        joined_rows = cursor.fetchall()
        joined_ids = [r["id"] for r in joined_rows]
        joined_names = [r["name"] for r in joined_rows]

        if joined_ids:
            placeholders = ",".join("?" for _ in joined_ids)
            cursor.execute(f"""
                SELECT DISTINCT f.id, f.item_type, f.title, f.content, f.post_subtype, f.event_date, f.event_time,
                       u.username as author_name
                FROM feed_items f
                JOIN users u ON f.author_id = u.id
                LEFT JOIN item_groups ig ON f.id = ig.item_id
                WHERE ig.group_id IN ({placeholders}) OR ig.group_id IS NULL
                ORDER BY f.created_at DESC
                LIMIT 5
            """, joined_ids)
        else:
            cursor.execute("""
                SELECT f.id, f.item_type, f.title, f.content, f.post_subtype, f.event_date, f.event_time,
                       u.username as author_name
                FROM feed_items f
                JOIN users u ON f.author_id = u.id
                ORDER BY f.created_at DESC
                LIMIT 5
            """)
        feed_rows = cursor.fetchall()
        highlights = []
        for fr in feed_rows:
            if fr["item_type"] == "KUDOS":
                snip = (fr["content"] or "")[:90]
                highlights.append(f"🌟 Kudos by @{fr['author_name']}: \"{snip}\"")
            else:
                st = (fr["post_subtype"] or "").upper()
                prefix = "📅 Event" if "EVENT" in st else ("📚 Resource" if "RESOURCE" in st else "📝 Post")
                when = f" ({fr['event_date']})" if fr["event_date"] else ""
                highlights.append(f"{prefix}: {fr['title'] or (fr['content'] or '')[:70]}{when} — by @{fr['author_name']}")

        if joined_ids:
            placeholders_chat = ",".join("?" for _ in joined_ids)
            cursor.execute(f"""
                SELECT COUNT(*) as chat_cnt
                FROM group_messages
                WHERE group_id IN ({placeholders_chat})
                  AND created_at >= datetime('now', '-7 days')
            """, joined_ids)
            chat_cnt_row = cursor.fetchone()
            recent_chat_cnt = chat_cnt_row["chat_cnt"] if chat_cnt_row else 0
            if recent_chat_cnt > 0:
                highlights.append(f"💬 {recent_chat_cnt} active Chat Board message{'s' if recent_chat_cnt != 1 else ''} across your joined Spaces")

        unsub_tok = ensure_user_unsubscribe_token(conn, user["id"])
        conn.commit()
        conn.close()

        unsub_url = build_unsubscribe_url(base_url, unsub_tok, "digest")
        dispatch_email_template(
            user["email"],
            build_weekly_digest_email(user["username"], joined_names, highlights, unsub_url, base_url),
            unsubscribe_url=unsub_url,
        )
        return json_response({
            "success": True,
            "message": f"Weekly Community Digest sent to {user['email']}!",
        })

    if path_only == "/api/email/templates" and method == "GET":
        return json_response({
            "success": True,
            "templates": get_all_template_previews(base_url),
        })

    # ================== USER PROFILES & HISTORY ==================
    if path_only == "/api/users/profile" and method == "PUT":
        if not user:
            return error_response("Login required", 401)
        avatar_url = body.get("avatar_url", user["avatar_url"]).strip()
        bio = body.get("bio", user["bio"]).strip()
        password = body.get("password", "")
        raw_prefs_update = body.get("email_prefs")

        conn = get_db()
        cursor = conn.cursor()
        if password:
            pw_hash = hash_password(password)
            cursor.execute("UPDATE users SET avatar_url = ?, bio = ?, password_hash = ? WHERE id = ?", (avatar_url, bio, pw_hash, user["id"]))
        else:
            cursor.execute("UPDATE users SET avatar_url = ?, bio = ? WHERE id = ?", (avatar_url, bio, user["id"]))
        if isinstance(raw_prefs_update, dict):
            merged_prefs = dict(user.get("email_prefs") or DEFAULT_EMAIL_PREFS)
            for k in DEFAULT_EMAIL_PREFS:
                if k in raw_prefs_update:
                    merged_prefs[k] = bool(raw_prefs_update[k])
            cursor.execute("UPDATE users SET email_prefs = ? WHERE id = ?", (json.dumps(merged_prefs), user["id"]))
        conn.commit()
        cursor.execute("""
            SELECT id, email, username, phone, avatar_url, bio, is_site_admin, oauth_provider, oauth_id,
                   COALESCE(email_verified, 0) as email_verified, email_prefs
            FROM users WHERE id = ?
        """, (user["id"],))
        updated_user = dict(cursor.fetchone())
        updated_user["email_prefs"] = parse_user_email_prefs(updated_user.get("email_prefs"))
        conn.close()
        if password:
            dispatch_email_template(
                user["email"],
                build_security_alert_email(user["username"], "Account password updated", base_url),
            )
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
            cursor.execute("SELECT id, username, avatar_url, bio, is_site_admin, is_banned, created_at FROM users WHERE id = ?", (int(target_seg),))
        elif target_seg.lower() in ("profile", "me", "undefined", "null") and user:
            cursor.execute("SELECT id, username, avatar_url, bio, is_site_admin, is_banned, created_at FROM users WHERE id = ?", (user["id"],))
        elif target_seg.lower() in ("profile", "me", "undefined", "null"):
            cursor.execute("SELECT id, username, avatar_url, bio, is_site_admin, is_banned, created_at FROM users WHERE id = 1")
        else:
            cursor.execute("SELECT id, username, avatar_url, bio, is_site_admin, is_banned, created_at FROM users WHERE username = ? OR email = ?", (target_seg, target_seg))
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

    # ================== EDIT / UPDATE ITEM (KUDOS / POSTS / EVENTS) ==================
    if (path_only.startswith("/api/feed/") or path_only.startswith("/api/kudos/") or path_only.startswith("/api/posts/") or path_only.startswith("/api/post/")) and method in ("PUT", "PATCH"):
        item_id_str = path_only.split("/")[-1]
        try:
            item_id = int(item_id_str)
        except ValueError:
            return error_response("Invalid item ID")
        if not user:
            return error_response("Authentication required", 401)
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT id, author_id, recipient_id, item_type FROM feed_items WHERE id = ?", (item_id,))
        row = cursor.fetchone()
        if not row:
            conn.close()
            return error_response("Item not found", 404)
        is_owner = (row["author_id"] == user["id"]) or (row["recipient_id"] == user["id"])
        is_admin = (user.get("is_site_admin") == 1)
        if not (is_owner or is_admin):
            conn.close()
            return error_response("Forbidden: You do not have permission to edit this item", 403)

        title = body.get("title", "").strip()
        theme = body.get("theme", "").strip() or "Events"
        content = body.get("content", "").strip()
        raw_res_url = body.get("resource_url") or body.get("attachments") or ""
        if isinstance(raw_res_url, (list, dict)):
            resource_url = json.dumps(raw_res_url)
        else:
            resource_url = str(raw_res_url or "").strip()
        event_date = body.get("event_date", "").strip() or None
        event_time = str(body.get("event_time") if body.get("event_time") is not None else (body.get("time") or "")).strip() or None
        raw_put_subtype = body.get("post_subtypes") if body.get("post_subtypes") is not None else body.get("post_subtype", "")
        if raw_put_subtype:
            post_subtype = ",".join(parse_post_subtypes_list(raw_put_subtype))
        else:
            post_subtype = None
        target_audience = str(body.get("target_audience") or "").strip() or None
        target_geography = str(body.get("target_geography") or body.get("target_geographical_areas") or "").strip() or None
        contact_info = str(body.get("contact_info") or body.get("key_contact_info") or "").strip() or None
        category = str(body.get("category") or body.get("subject") or "").strip() or None
        extracted_text = extract_resource_text(resource_url)

        cursor.execute("""
            UPDATE feed_items
            SET title = COALESCE(NULLIF(?, ''), title),
                theme = COALESCE(NULLIF(?, ''), theme),
                content = COALESCE(NULLIF(?, ''), content),
                resource_url = ?,
                event_date = COALESCE(?, event_date),
                event_time = COALESCE(?, event_time),
                post_subtype = COALESCE(?, post_subtype),
                target_audience = COALESCE(?, target_audience),
                target_geography = COALESCE(?, target_geography),
                contact_info = COALESCE(?, contact_info),
                category = COALESCE(?, category),
                extracted_text = ?
            WHERE id = ?
        """, (title, theme, content, resource_url, event_date, event_time, post_subtype, target_audience, target_geography, contact_info, category, extracted_text, item_id))
        conn.commit()
        conn.close()

        enriched = fetch_enriched_items("WHERE f.id = ?", (item_id,), user["id"])
        item_obj = enriched[0] if enriched else {"id": item_id, "title": title}
        return json_response({"success": True, "message": "Post updated successfully", "item": item_obj, "post": item_obj})

    # ================== DELETE ITEM (KUDOS / POSTS / EVENTS) ==================
    if (path_only.startswith("/api/feed/") or path_only.startswith("/api/kudos/") or path_only.startswith("/api/posts/") or path_only.startswith("/api/post/")) and method == "DELETE":
        item_id_str = path_only.split("/")[-1]
        try:
            item_id = int(item_id_str)
        except ValueError:
            return error_response("Invalid item ID")
        if not user:
            return error_response("Authentication required", 401)
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT id, author_id, recipient_id, item_type FROM feed_items WHERE id = ?", (item_id,))
        row = cursor.fetchone()
        if not row:
            conn.close()
            return error_response("Item not found", 404)
        is_owner = (row["author_id"] == user["id"]) or (row["recipient_id"] == user["id"])
        is_admin = (user.get("is_site_admin") == 1)
        if not (is_owner or is_admin):
            conn.close()
            return error_response("Forbidden: You do not have permission to delete this post", 403)
        cursor.execute("DELETE FROM feed_items WHERE id = ?", (item_id,))
        conn.commit()
        conn.close()
        return json_response({"success": True, "message": "Post deleted successfully", "deleted_id": item_id})

    # ================== DELETE GROUP RESOURCE ==================
    if path_only.startswith("/api/groups/") and "/resources/" in path_only and method == "DELETE":
        if not user:
            return error_response("Login required", 401)
        parts = path_only.split("/")
        try:
            gid = int(parts[3])
            rid = int(parts[5])
        except (ValueError, IndexError):
            return error_response("Invalid group or resource ID")
        
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT id, added_by FROM group_resources WHERE id = ? AND group_id = ?", (rid, gid))
        r_row = cursor.fetchone()
        if not r_row:
            conn.close()
            return error_response("Resource not found", 404)
        
        cursor.execute("SELECT is_admin FROM group_members WHERE group_id = ? AND user_id = ?", (gid, user["id"]))
        m_row = cursor.fetchone()
        is_admin = (m_row and m_row["is_admin"] == 1) or (user.get("is_site_admin") == 1)
        is_owner = (r_row["added_by"] == user["id"])
        if not (is_owner or is_admin):
            conn.close()
            return error_response("Forbidden: You do not have permission to delete this resource", 403)

        cursor.execute("DELETE FROM group_resources WHERE id = ? AND group_id = ?", (rid, gid))
        conn.commit()
        conn.close()
        return json_response({"success": True, "message": "Resource deleted successfully", "deleted_id": rid})


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

        subtype_param = query.get("subtype", [""])[0].strip().upper()
        if subtype_param:
            if subtype_param == "EVENT":
                where_parts.append("(f.item_type = 'POST' AND ((',' || UPPER(COALESCE(f.post_subtype, '')) || ',') LIKE '%,EVENT,%' OR (f.event_date IS NOT NULL AND f.event_date != '')))")
            elif subtype_param == "RESOURCE":
                where_parts.append("(f.item_type = 'POST' AND ((',' || UPPER(COALESCE(f.post_subtype, '')) || ',') LIKE '%,RESOURCE,%' OR (TRIM(COALESCE(f.post_subtype, '')) = '' AND (f.event_date IS NULL OR f.event_date = '') AND (f.resource_url IS NOT NULL AND f.resource_url != '' AND f.resource_url != '[]'))))")
            elif subtype_param == "GENERAL":
                where_parts.append("(f.item_type = 'POST' AND ((',' || UPPER(COALESCE(f.post_subtype, '')) || ',') LIKE '%,GENERAL,%' OR (TRIM(COALESCE(f.post_subtype, '')) = '' AND (f.event_date IS NULL OR f.event_date = '') AND (f.resource_url IS NULL OR f.resource_url = '' OR f.resource_url = '[]'))))")
            else:
                where_parts.append("(',' || UPPER(COALESCE(f.post_subtype, '')) || ',') LIKE ?")
                params.append(f"%,{subtype_param},%")

        exclude_subtype = query.get("exclude_subtype", [""])[0].strip().upper()
        if exclude_subtype == "EVENT":
            where_parts.append("((',' || UPPER(COALESCE(f.post_subtype, '')) || ',') NOT LIKE '%,EVENT,%' AND (f.event_date IS NULL OR f.event_date = ''))")

        category_param = query.get("category", [""])[0].strip()
        if category_param:
            where_parts.append("LOWER(COALESCE(f.category, '')) = LOWER(?)")
            params.append(category_param)

        if theme:
            THEME_ALIASES = {
                "Inspiring Stories": ["Inspiring Stories", "Inspiring Story", "Inspiring Stories & Wisdom"],
                "Wellbeing & Care": ["Wellbeing & Care", "Mental Health", "Wellness", "Mindfulness", "Mental Health & Peer Listening"],
                "Skills & Learning": ["Skills & Learning", "Educational", "Education", "Education & Skill Building"],
                "Community & Action": ["Community & Action", "General", "General & Mutual Aid"]
            }
            if theme == "Events":
                where_parts.append("((',' || UPPER(COALESCE(f.post_subtype, '')) || ',') LIKE '%,EVENT,%' OR f.theme = 'Events' OR (f.event_date IS NOT NULL AND f.event_date != ''))")
            elif theme == "Resources":
                where_parts.append("((',' || UPPER(COALESCE(f.post_subtype, '')) || ',') LIKE '%,RESOURCE,%' OR f.theme = 'Resources' OR (TRIM(COALESCE(f.post_subtype, '')) = '' AND (f.event_date IS NULL OR f.event_date = '') AND (f.resource_url IS NOT NULL AND f.resource_url != '' AND f.resource_url != '[]')))")
            elif theme in THEME_ALIASES:
                aliases = THEME_ALIASES[theme]
                where_parts.append(f"f.theme IN ({','.join(['?']*len(aliases))})")
                params.extend(aliases)
            else:
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
            searchable_row_expr = (
                "(COALESCE(f.title, '') || ' ' || COALESCE(f.content, '') || ' ' || COALESCE(f.theme, '') || ' ' || "
                "COALESCE(f.category, '') || ' ' || "
                "COALESCE(f.extracted_text, '') || ' ' || COALESCE(f.resource_url, '') || ' ' || "
                "COALESCE(f.target_audience, '') || ' ' || COALESCE(f.target_geography, '') || ' ' || "
                "COALESCE(f.contact_info, '') || ' ' || COALESCE(f.post_subtype, '') || ' ' || "
                "COALESCE(f.event_date, '') || ' ' || COALESCE(f.event_time, '') || ' ' || "
                "COALESCE(u.username, '') || ' ' || COALESCE(ru.username, ''))"
            )
            if "author:" in search.lower():
                parts = search.split("author:", 1)
                prefix = parts[0].strip()
                author_tokens = parts[1].strip().split()
                if author_tokens:
                    author_name = author_tokens[0]
                    remaining = (prefix + " " + " ".join(author_tokens[1:])).strip()
                    where_parts.append("(u.username LIKE ? OR ru.username LIKE ?)")
                    params.extend([f"%{author_name}%", f"%{author_name}%"])
                    if remaining:
                        like_q = f"%{remaining}%"
                        where_parts.append(f"{searchable_row_expr} LIKE ?")
                        params.append(like_q)
                else:
                    if prefix:
                        like_q = f"%{prefix}%"
                        where_parts.append(f"{searchable_row_expr} LIKE ?")
                        params.append(like_q)
            else:
                clean_search = search.lstrip("@").strip()
                like_q = f"%{search}%"
                like_clean = f"%{clean_search}%"
                tokens = [t.lstrip("@").strip() for t in clean_search.split() if t.lstrip("@").strip()]
                if len(tokens) > 1:
                    token_clauses = " AND ".join([f"{searchable_row_expr} LIKE ?" for _ in tokens])
                    where_parts.append(f"({searchable_row_expr} LIKE ? OR ({token_clauses}))")
                    params.append(like_q)
                    params.extend([f"%{t}%" for t in tokens])
                else:
                    where_parts.append(
                        "(f.title LIKE ? OR f.content LIKE ? OR f.theme LIKE ? OR f.category LIKE ? OR f.extracted_text LIKE ? "
                        "OR f.resource_url LIKE ? OR f.target_audience LIKE ? OR f.target_geography LIKE ? "
                        "OR f.contact_info LIKE ? OR f.event_date LIKE ? OR f.event_time LIKE ? OR u.username LIKE ? OR ru.username LIKE ?)"
                    )
                    params.extend([like_q, like_q, like_q, like_q, like_q, like_q, like_q, like_q, like_q, like_q, like_q, like_clean, like_clean])

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

    # ================== CONVERSATIONAL CHAT SEARCH ==================
    if path_only == "/api/chat_search" and method == "POST":
        raw_msg = str(body.get("message") or body.get("query") or "").strip()
        if not raw_msg:
            return error_response("Please enter a question or search message.", 400)
        if len(raw_msg) > 1000:
            raw_msg = raw_msg[:1000]
        history = body.get("history") if isinstance(body.get("history"), list) else []
        scope = str(body.get("scope") or "").strip()
        result = run_conversational_search(raw_msg, history=history, user=user, scope=scope)
        return json_response(result)

    # ================== CREATE KUDOS ==================
    if path_only == "/api/kudos" and method == "POST":
        if not user:
            return error_response("Login required to give Kudos", 401)
        recipient_id = body.get("recipient_id")
        content = body.get("content", "").strip()
        group_ids = body.get("group_ids", [])

        if not recipient_id or not content:
            return error_response("Recipient and message are required.")

        ok, mod_err = check_content_moderation(user, [content])
        if not ok:
            return error_response(mod_err, 400)

        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT id, email, username, email_prefs FROM users WHERE id = ?", (recipient_id,))
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

        preview = content[:100] + ("..." if len(content) > 100 else "")
        create_in_app_notification(
            conn,
            recipient_id,
            user["id"],
            "KUDOS",
            kudos_id,
            f"🌟 @{user['username']} gave you Kudos: \"{preview[:50]}\"",
            f"/#/kudos/{kudos_id}"
        )

        send_kudos_email = is_email_pref_enabled(recip["email_prefs"], "kudos")
        recip_unsub_tok = ensure_user_unsubscribe_token(conn, recipient_id) if send_kudos_email else ""

        conn.commit()
        conn.close()

        if send_kudos_email:
            unsub_url = build_unsubscribe_url(base_url, recip_unsub_tok, "kudos")
            dispatch_email_template(
                recip["email"],
                build_kudos_received_email(recip["username"], user["username"], content, kudos_id, unsub_url, base_url),
                unsubscribe_url=unsub_url,
            )

        enriched = fetch_enriched_items("WHERE f.id = ?", (kudos_id,), user["id"])
        item_obj = enriched[0]
        return json_response({"item": item_obj, "kudos": item_obj, "success": True}, 201)

    # ================== CREATE POST ==================
    if path_only == "/api/posts" and method == "POST":
        if not user:
            return error_response("Login required to create posts", 401)
        title = body.get("title", "").strip()
        theme = (body.get("theme") or "").strip() or "General"
        content = body.get("content", "").strip()
        raw_res_url = body.get("resource_url") or body.get("attachments") or ""
        if isinstance(raw_res_url, (list, dict)):
            resource_url = json.dumps(raw_res_url)
        else:
            resource_url = str(raw_res_url or "").strip()
        group_ids = body.get("group_ids", [])
        raw_post_subtype = body.get("post_subtypes") if body.get("post_subtypes") is not None else body.get("post_subtype", "")
        subtypes_list = parse_post_subtypes_list(raw_post_subtype)
        post_subtype = ",".join(subtypes_list)
        event_date = body.get("event_date", "").strip()
        event_time = str(body.get("event_time") if body.get("event_time") is not None else (body.get("time") or "")).strip()
        if "EVENT" not in subtypes_list:
            event_date = ""
            event_time = ""

        target_audience = str(body.get("target_audience") or "").strip()
        target_geography = str(body.get("target_geography") or body.get("target_geographical_areas") or "").strip()
        contact_info = str(body.get("contact_info") or body.get("key_contact_info") or "").strip()
        category = str(body.get("category") or body.get("subject") or "").strip()

        VALID_THEMES = {"Inspiring Stories", "Wellbeing & Care", "Skills & Learning", "Community & Action", "Inspiring Story", "Mental Health", "Wellness", "Mindfulness", "Educational", "General", "Events", "Resources", "Education", "Community Resources", "Inspiring Stories & Wisdom", "Mental Health & Peer Listening", "Education & Skill Building", "General & Mutual Aid", "Upcoming Community Events", "General Community Resources"}

        if not title or not content:
            return error_response("Title and content are required.")

        ok, mod_err = check_content_moderation(user, [title, content, resource_url, target_audience, target_geography, contact_info, category, event_time])
        if not ok:
            return error_response(mod_err, 400)

        if theme not in VALID_THEMES:
            return error_response(f"Invalid theme: {theme}", 400)

        if "EVENT" in subtypes_list:
            if not event_date:
                return error_response("Event date is required for Community Events.", 400)
            today_str = datetime.date.today().isoformat()
            if event_date < today_str:
                return error_response("Event date cannot be in the past.", 400)

        conn = get_db()
        cursor = conn.cursor()
        extracted_text = extract_resource_text(resource_url)
        cursor.execute("""
            INSERT INTO feed_items (item_type, author_id, title, theme, content, resource_url, post_subtype, event_date, event_time, extracted_text, target_audience, target_geography, contact_info, category)
            VALUES ('POST', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (user["id"], title, theme, content, resource_url, post_subtype, event_date, event_time, extracted_text, target_audience, target_geography, contact_info, category))
        post_id = cursor.lastrowid

        for gid in group_ids:
            try:
                cursor.execute("INSERT OR IGNORE INTO item_groups (item_id, group_id) VALUES (?, ?)", (post_id, int(gid)))
            except Exception:
                pass

        space_announcement_dispatches = []
        clean_gids = []
        for g in (group_ids or []):
            try:
                clean_gids.append(int(g))
            except Exception:
                pass
        if clean_gids and ("EVENT" in subtypes_list or "RESOURCE" in subtypes_list or bool(body.get("notify_space_members"))):
            cursor.execute("SELECT id, name FROM groups WHERE id = ?", (clean_gids[0],))
            primary_space = cursor.fetchone()
            if primary_space:
                placeholders = ",".join("?" for _ in clean_gids)
                cursor.execute(f"""
                    SELECT DISTINCT u.id, u.username, u.email, u.email_prefs
                    FROM group_members gm
                    JOIN users u ON gm.user_id = u.id
                    WHERE gm.group_id IN ({placeholders})
                      AND u.id != ?
                      AND COALESCE(u.is_banned, 0) = 0
                """, (*clean_gids, user["id"]))
                subtype_label = (
                    "Community Event" if "EVENT" in subtypes_list
                    else ("Community Resource" if "RESOURCE" in subtypes_list else "Space Post")
                )
                for mrow in cursor.fetchall():
                    if is_email_pref_enabled(mrow["email_prefs"], "space_updates"):
                        m_tok = ensure_user_unsubscribe_token(conn, mrow["id"])
                        m_unsub = build_unsubscribe_url(base_url, m_tok, "space_updates")
                        space_announcement_dispatches.append((
                            mrow["email"],
                            build_space_announcement_email(
                                mrow["username"],
                                user["username"],
                                primary_space["id"],
                                primary_space["name"],
                                post_id,
                                title,
                                subtype_label,
                                event_date=event_date,
                                event_time=event_time,
                                summary_snippet=content,
                                unsubscribe_url=m_unsub,
                                base_url=base_url,
                            ),
                            m_unsub,
                        ))

        conn.commit()
        conn.close()

        for m_email, m_tpl, m_unsub in space_announcement_dispatches:
            dispatch_email_template(m_email, m_tpl, unsubscribe_url=m_unsub)

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

        ok, mod_err = check_content_moderation(user, [content])
        if not ok:
            return error_response(mod_err, 400)

        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("INSERT INTO comments (item_id, user_id, content) VALUES (?, ?, ?)", (item_id, user["id"], content))
        cid = cursor.lastrowid

        cursor.execute("""
            SELECT f.author_id, f.item_type, f.title,
                   u.username as author_username, u.email as author_email, u.email_prefs as author_prefs
            FROM feed_items f
            JOIN users u ON f.author_id = u.id
            WHERE f.id = ?
        """, (item_id,))
        parent_row = cursor.fetchone()
        comment_email_dispatch = None
        if parent_row and parent_row["author_id"] != user["id"]:
            link_prefix = "kudos" if parent_row["item_type"] == "KUDOS" else "post"
            snippet = content[:50] + ("..." if len(content) > 50 else "")
            create_in_app_notification(
                conn,
                parent_row["author_id"],
                user["id"],
                "COMMENT",
                item_id,
                f"💬 @{user['username']} commented: \"{snippet}\"",
                f"/#/{link_prefix}/{item_id}"
            )
            if parent_row["author_email"] and is_email_pref_enabled(parent_row["author_prefs"], "comments"):
                c_tok = ensure_user_unsubscribe_token(conn, parent_row["author_id"])
                c_unsub = build_unsubscribe_url(base_url, c_tok, "comments")
                comment_email_dispatch = (
                    parent_row["author_email"],
                    build_comment_notification_email(
                        parent_row["author_username"],
                        user["username"],
                        parent_row["item_type"],
                        parent_row["title"] or "",
                        content,
                        int(item_id),
                        unsubscribe_url=c_unsub,
                        base_url=base_url,
                    ),
                    c_unsub,
                )

        conn.commit()
        cursor.execute("""
            SELECT c.id, c.content, c.created_at, u.username as author_name, u.avatar_url as author_avatar, c.user_id
            FROM comments c
            JOIN users u ON c.user_id = u.id
            WHERE c.id = ?
        """, (cid,))
        new_c = dict(cursor.fetchone())
        conn.close()
        if comment_email_dispatch:
            dispatch_email_template(
                comment_email_dispatch[0],
                comment_email_dispatch[1],
                unsubscribe_url=comment_email_dispatch[2],
            )
        return json_response({"comment": new_c, "success": True}, 201)

    if path_only.startswith("/api/comments/") and method == "DELETE":
        if not user:
            return error_response("Login required to delete comment", 401)
        try:
            cid = int(path_only.split("/")[-1])
        except ValueError:
            return error_response("Invalid comment ID")
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT id, user_id, item_id FROM comments WHERE id = ?", (cid,))
        c_row = cursor.fetchone()
        if not c_row:
            conn.close()
            return error_response("Comment not found", 404)
        is_owner = (c_row["user_id"] == user["id"])
        is_admin = (user.get("is_site_admin") == 1)
        if not (is_owner or is_admin):
            # Check if post author or space admin
            cursor.execute("SELECT author_id FROM feed_items WHERE id = ?", (c_row["item_id"],))
            f_row = cursor.fetchone()
            if f_row and f_row["author_id"] == user["id"]:
                is_owner = True
            else:
                cursor.execute("""
                    SELECT gm.is_admin FROM item_groups ig
                    JOIN group_members gm ON ig.group_id = gm.group_id
                    WHERE ig.item_id = ? AND gm.user_id = ? AND gm.is_admin = 1
                """, (c_row["item_id"], user["id"]))
                if cursor.fetchone():
                    is_admin = True
        if not (is_owner or is_admin):
            conn.close()
            return error_response("Forbidden: You do not have permission to delete this comment", 403)
        cursor.execute("DELETE FROM comments WHERE id = ?", (cid,))
        conn.commit()
        conn.close()
        return json_response({"success": True, "deleted_id": cid})

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
            
            if theme_filter:
                THEME_ALIASES = {
                    "Inspiring Stories": ["Inspiring Stories", "Inspiring Story", "Inspiring Stories & Wisdom"],
                    "Wellbeing & Care": ["Wellbeing & Care", "Mental Health", "Wellness", "Mindfulness", "Mental Health & Peer Listening"],
                    "Skills & Learning": ["Skills & Learning", "Educational", "Education", "Education & Skill Building"],
                    "Community & Action": ["Community & Action", "General", "General & Mutual Aid"]
                }
                target_themes = set(THEME_ALIASES.get(theme_filter, [theme_filter]))
                if not any(t in g["themes"] for t in target_themes):
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
                ORDER BY m.created_at DESC, m.id DESC
            """, (gid,))
            rows = [dict(r) for r in cursor.fetchall()]
            conn.close()
            return json_response({"messages": rows, "chat_messages": rows, "chat": rows})

        elif subres in ("members", "roster"):
            cursor.execute("""
                SELECT u.id, u.username, u.avatar_url, u.bio, u.is_site_admin, gm.is_admin, gm.joined_at
                FROM group_members gm
                JOIN users u ON gm.user_id = u.id
                WHERE gm.group_id = ?
                ORDER BY gm.is_admin DESC, u.is_site_admin DESC, u.username ASC
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
            SELECT u.id, u.username, u.avatar_url, u.bio, u.is_site_admin, gm.is_admin, gm.joined_at
            FROM group_members gm
            JOIN users u ON gm.user_id = u.id
            WHERE gm.group_id = ?
            ORDER BY gm.is_admin DESC, u.is_site_admin DESC, u.username ASC
        """, (gid,))
        roster = [dict(r) for r in cursor.fetchall()]
        g_data["roster"] = roster

        cursor.execute("""
            DELETE FROM group_invitations
            WHERE group_id = ? AND status = 'PENDING'
              AND EXISTS (
                SELECT 1 FROM group_members gm
                JOIN users u ON gm.user_id = u.id
                WHERE gm.group_id = group_invitations.group_id
                  AND (LOWER(u.username) = LOWER(group_invitations.recipient_username)
                       OR LOWER(u.email) = LOWER(group_invitations.recipient_username))
              )
        """, (gid,))
        conn.commit()

        cursor.execute("""
            SELECT gi.id, gi.group_id, gi.sender_id, gi.recipient_username, gi.message, gi.status, gi.created_at,
                   u.username as sender_name, u.avatar_url as sender_avatar,
                   ru.id as recipient_id, ru.avatar_url as recipient_avatar
            FROM group_invitations gi
            JOIN users u ON gi.sender_id = u.id
            LEFT JOIN users ru ON LOWER(ru.username) = LOWER(gi.recipient_username)
            WHERE gi.group_id = ?
              AND NOT (gi.status = 'PENDING' AND ru.id IS NOT NULL AND EXISTS (
                  SELECT 1 FROM group_members gm WHERE gm.group_id = gi.group_id AND gm.user_id = ru.id
              ))
            ORDER BY gi.created_at DESC
        """, (gid,))
        g_data["invitations"] = [dict(r) for r in cursor.fetchall()]

        uid = user["id"] if user else None
        g_data["is_joined"] = any(m["id"] == uid for m in roster)
        g_data["is_admin"] = bool((user and user.get("is_site_admin") == 1) or any(m["id"] == uid and m["is_admin"] == 1 for m in roster))

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
            ORDER BY m.created_at DESC, m.id DESC
        """, (gid,))
        g_data["chat_messages"] = [dict(r) for r in cursor.fetchall()]

        conn.close()
        return json_response({"group": g_data})

    # UPDATE GROUP / SPACE DETAILS (Space Admin or Site Admin)
    if path_only.startswith("/api/groups/") and len(path_only.split("/")) == 4 and method in ("PUT", "PATCH"):
        if not user:
            return error_response("Login required to edit space", 401)
        parts = path_only.split("/")
        gid_str = parts[3]
        try:
            gid = int(gid_str)
        except ValueError:
            return error_response("Invalid group ID", 400)

        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM groups WHERE id = ?", (gid,))
        g_row = cursor.fetchone()
        if not g_row:
            conn.close()
            return error_response("Space not found", 404)

        is_super_admin = (user.get("is_site_admin") == 1)
        is_group_admin = False
        if not is_super_admin:
            cursor.execute("SELECT is_admin FROM group_members WHERE group_id = ? AND user_id = ?", (gid, user["id"]))
            admin_row = cursor.fetchone()
            if admin_row and admin_row["is_admin"] == 1:
                is_group_admin = True

        if not (is_super_admin or is_group_admin):
            conn.close()
            return error_response("Only Space Admins or Site Admins can edit space details.", 403)

        existing = dict(g_row)
        raw_name = body.get("name")
        new_name = str(raw_name).strip() if raw_name is not None else existing["name"]
        if not new_name:
            conn.close()
            return error_response("Space name is required.", 400)

        raw_desc = body.get("description")
        new_desc = str(raw_desc).strip() if raw_desc is not None else (existing.get("description") or "")

        raw_icon = body.get("icon_url")
        if raw_icon is not None:
            new_icon = str(raw_icon).strip() or existing.get("icon_url") or "https://images.unsplash.com/photo-1529156069898-49953e39b3ac?auto=format&fit=crop&w=200&q=80"
        else:
            new_icon = existing.get("icon_url") or "https://images.unsplash.com/photo-1529156069898-49953e39b3ac?auto=format&fit=crop&w=200&q=80"

        raw_themes = body.get("themes")
        raw_single_theme = body.get("theme")
        if raw_themes is not None:
            if isinstance(raw_themes, list):
                themes_list = [str(t).strip() for t in raw_themes if str(t).strip()]
            elif isinstance(raw_themes, str):
                try:
                    parsed = json.loads(raw_themes)
                    themes_list = [str(t).strip() for t in parsed if str(t).strip()] if isinstance(parsed, list) else [raw_themes.strip()]
                except Exception:
                    themes_list = [t.strip() for t in raw_themes.split(",") if t.strip()]
            else:
                themes_list = []
            new_themes_str = json.dumps(themes_list)
        elif raw_single_theme is not None and str(raw_single_theme).strip():
            new_themes_str = json.dumps([str(raw_single_theme).strip()])
        else:
            new_themes_str = existing.get("themes") or "[]"

        ok_mod, mod_err = check_content_moderation(user, [new_name, new_desc])
        if not ok_mod:
            conn.close()
            return error_response(mod_err, 400)

        try:
            cursor.execute(
                "UPDATE groups SET name = ?, description = ?, themes = ?, icon_url = ? WHERE id = ?",
                (new_name, new_desc, new_themes_str, new_icon, gid)
            )
            conn.commit()
        except sqlite3.IntegrityError:
            conn.close()
            return error_response("A space with this name already exists.", 400)
        except Exception as e:
            conn.close()
            return error_response(f"Could not update space: {str(e)}", 400)

        cursor.execute("SELECT * FROM groups WHERE id = ?", (gid,))
        updated_row = dict(cursor.fetchone())
        try:
            updated_row["themes"] = json.loads(updated_row["themes"]) if updated_row.get("themes") else []
        except Exception:
            updated_row["themes"] = []
        conn.close()
        return json_response({"success": True, "group": updated_row})

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

        if target_uid == user["id"]:
            conn.close()
            return error_response("You cannot promote or demote yourself.", 400)

        cursor.execute("SELECT id, username, email, is_site_admin FROM users WHERE id = ?", (target_uid,))
        target_user_row = cursor.fetchone()
        if not target_user_row:
            conn.close()
            return error_response("Target user not found.", 404)

        cursor.execute("SELECT name FROM groups WHERE id = ?", (gid,))
        g_name_row = cursor.fetchone()
        g_name_str = g_name_row["name"] if g_name_row else f"Space #{gid}"

        cursor.execute("SELECT * FROM group_members WHERE group_id = ? AND user_id = ?", (gid, target_uid))
        member_row = cursor.fetchone()
        if member_row:
            cursor.execute("UPDATE group_members SET is_admin = ? WHERE group_id = ? AND user_id = ?", (is_admin_val, gid, target_uid))
        else:
            cursor.execute("INSERT INTO group_members (group_id, user_id, is_admin) VALUES (?, ?, ?)", (gid, target_uid, is_admin_val))

        conn.commit()
        conn.close()
        if target_user_row["email"]:
            dispatch_email_template(
                target_user_row["email"],
                build_space_role_updated_email(
                    target_user_row["username"],
                    gid,
                    g_name_str,
                    is_admin_val == 1,
                    user["username"],
                    base_url,
                ),
            )
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
            cursor.execute("SELECT 1 FROM group_bans WHERE group_id = ? AND user_id = ?", (gid, user["id"]))
            if cursor.fetchone():
                conn.close()
                return error_response("You have been banned from joining this space.", 403)
            join_is_admin = 1 if user.get("is_site_admin") == 1 else 0
            cursor.execute("INSERT OR IGNORE INTO group_members (group_id, user_id, is_admin) VALUES (?, ?, ?)", (gid, user["id"], join_is_admin))
            cursor.execute("""
                DELETE FROM group_invitations
                WHERE group_id = ? AND status = 'PENDING'
                  AND (LOWER(recipient_username) = LOWER(?) OR LOWER(recipient_username) = LOWER(?))
            """, (gid, user["username"], user["email"]))
        else:
            cursor.execute("DELETE FROM group_members WHERE group_id = ? AND user_id = ?", (gid, user["id"]))
        conn.commit()
        conn.close()
        return json_response({"success": True, "action": action})

    # KICK / BAN MEMBER FROM SPACE
    if path_only.startswith("/api/groups/") and path_only.endswith("/members/kick") and method == "POST":
        if not user:
            return error_response("Login required", 401)
        parts = path_only.split("/")
        try:
            gid = int(parts[3])
            target_uid = int(body.get("user_id") or body.get("target_user_id"))
        except (ValueError, TypeError):
            return error_response("Valid group_id and user_id are required.")
        ban_flag = bool(body.get("ban", False))
        reason = str(body.get("reason", "")).strip() or "Removed by space administrator"

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
            return error_response("Forbidden: Requires Space Admin or Site Admin status.", 403)

        cursor.execute("SELECT name FROM groups WHERE id = ?", (gid,))
        g_row_kick = cursor.fetchone()
        kick_space_name = g_row_kick["name"] if g_row_kick else f"Space #{gid}"
        cursor.execute("SELECT username, email FROM users WHERE id = ?", (target_uid,))
        kick_target_user = cursor.fetchone()

        cursor.execute("DELETE FROM group_members WHERE group_id = ? AND user_id = ?", (gid, target_uid))
        if ban_flag:
            cursor.execute("""
                INSERT OR REPLACE INTO group_bans (group_id, user_id, banned_by, reason)
                VALUES (?, ?, ?, ?)
            """, (gid, target_uid, user["id"], reason))
        conn.commit()
        conn.close()
        if kick_target_user and kick_target_user["email"]:
            dispatch_email_template(
                kick_target_user["email"],
                build_space_member_removed_email(
                    kick_target_user["username"],
                    kick_space_name,
                    ban_flag,
                    reason,
                    base_url,
                ),
            )
        return json_response({"success": True, "group_id": gid, "user_id": target_uid, "banned": ban_flag})

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

        emails_input = body.get("emails") if body.get("emails") is not None else body.get("email", "")
        if isinstance(emails_input, (list, tuple)):
            emails_raw = ", ".join([str(e).strip() for e in emails_input if str(e).strip()])
        else:
            emails_raw = str(emails_input or "").strip()
        message = str(body.get("message", "") or "").strip()
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

        raw_recipients = [e.strip() for e in re.split(r"[,;\n\r]+", emails_raw) if e.strip()]
        valid_recipients = []
        email_list = []
        already_members = []

        for rec in raw_recipients:
            cursor.execute("SELECT id, username, email, email_prefs FROM users WHERE LOWER(username) = LOWER(?) OR LOWER(email) = LOWER(?) OR id = ?", (rec, rec, int(rec) if rec.isdigit() else -1))
            urow = cursor.fetchone()
            if urow:
                cursor.execute("SELECT 1 FROM group_members WHERE group_id = ? AND user_id = ?", (gid, urow["id"]))
                if cursor.fetchone():
                    already_members.append(urow["username"])
                    continue
                valid_recipients.append((rec, urow))
                email_list.append(urow["email"])
            else:
                valid_recipients.append((rec, None))
                if "@" in rec:
                    email_list.append(rec)
                else:
                    email_list.append(f"{rec.lower().replace(' ', '_')}@gooddeeds.space")

        if not valid_recipients:
            conn.close()
            if already_members:
                return error_response(f"{', '.join(already_members)} is already a member of this space.", 400)
            return error_response("Please enter valid recipient email addresses or usernames")

        space_invite_dispatches = []
        for (raw_rec, target_urow), target_email in zip(valid_recipients, email_list):
            cursor.execute("""
                DELETE FROM group_invitations
                WHERE group_id = ? AND status = 'PENDING'
                  AND LOWER(recipient_username) = LOWER(?)
            """, (gid, raw_rec))
            cursor.execute("INSERT INTO group_invitations (group_id, sender_id, recipient_username, message, status) VALUES (?, ?, ?, ?, 'PENDING')", (gid, user["id"], raw_rec, message or "Come join our uplifting space!"))
            if target_urow:
                create_in_app_notification(
                    conn,
                    target_urow["id"],
                    user["id"],
                    "INVITATION",
                    gid,
                    f"👥 @{user['username']} invited you to join Space: \"{group_name}\"",
                    f"/#/group/{gid}"
                )
                if is_email_pref_enabled(target_urow["email_prefs"], "invites"):
                    inv_tok = ensure_user_unsubscribe_token(conn, target_urow["id"])
                    inv_unsub = build_unsubscribe_url(base_url, inv_tok, "invites")
                    space_invite_dispatches.append((target_email, True, inv_unsub))
            else:
                space_invite_dispatches.append((target_email, False, ""))
        conn.commit()
        conn.close()

        for rec_email, is_existing_u, inv_unsub in space_invite_dispatches:
            dispatch_email_template(
                rec_email,
                build_space_invitation_email(
                    user["username"],
                    user["email"],
                    gid,
                    group_name,
                    message,
                    is_existing_user=is_existing_u,
                    unsubscribe_url=inv_unsub,
                    base_url=base_url,
                ),
                unsubscribe_url=inv_unsub or None,
            )

        return json_response({"success": True, "message": f"Invitation sent to {len(email_list)} recipient(s)!"})

    # INVITE OTHERS TO JOIN THE WEBSITE (SINGLE OR BULK EMAILS)
    if path_only in ("/api/invitations/site", "/api/invite") and method == "POST":
        if not user:
            return error_response("Login required to send invitations", 401)

        raw_emails_input = body.get("emails") if body.get("emails") is not None else body.get("email", "")
        message = str(body.get("message", "") or "").strip()

        ok_mod, mod_err = check_content_moderation(user, [message])
        if not ok_mod:
            return error_response(mod_err, 400)

        valid_emails, invalid_tokens = parse_bulk_email_addresses(raw_emails_input)
        if not valid_emails:
            if invalid_tokens:
                return error_response(f"Invalid email format: {', '.join(invalid_tokens[:5])}. Please enter valid email addresses.", 400)
            return error_response("At least one valid recipient email address is required.", 400)

        conn = get_db()
        cursor = conn.cursor()

        invited_emails = []
        already_registered = []

        for email_addr in valid_emails:
            cursor.execute("SELECT id, username, email FROM users WHERE LOWER(email) = LOWER(?)", (email_addr,))
            urow = cursor.fetchone()
            if urow:
                already_registered.append(urow["email"])
                continue
            invited_emails.append(email_addr)

        if not invited_emails:
            conn.close()
            return error_response(
                f"{', '.join(already_registered)} {'are' if len(already_registered) > 1 else 'is'} already registered on GoodDeeds.space.",
                400
            )

        note_text = message or "Join me on GoodDeeds.space to recognize everyday kindness with public Kudos and share local community resources & events!"
        site_invite_tpl = build_site_invitation_email(user["username"], user["email"], note_text, base_url)

        for rec_email in invited_emails:
            cursor.execute("""
                DELETE FROM site_invitations
                WHERE sender_id = ? AND LOWER(recipient_email) = LOWER(?) AND status = 'PENDING'
            """, (user["id"], rec_email))
            cursor.execute("""
                INSERT INTO site_invitations (sender_id, sender_name, recipient_email, message, status)
                VALUES (?, ?, ?, ?, 'PENDING')
            """, (user["id"], user["username"], rec_email, note_text))

        conn.commit()
        conn.close()

        for rec_email in invited_emails:
            dispatch_email_template(rec_email, site_invite_tpl)

        msg_parts = [f"Sent {len(invited_emails)} invitation email(s) to join GoodDeeds.space!"]
        if already_registered:
            msg_parts.append(f"Skipped {len(already_registered)} already-registered address(es).")
        if invalid_tokens:
            msg_parts.append(f"Ignored {len(invalid_tokens)} invalid entry(ies).")

        return json_response({
            "success": True,
            "count": len(invited_emails),
            "sent_count": len(invited_emails),
            "invited_emails": invited_emails,
            "already_registered": already_registered,
            "invalid_emails": invalid_tokens,
            "invalid_entries": invalid_tokens,
            "message": " ".join(msg_parts)
        })

    # GET SENT WEBSITE INVITATIONS FOR CURRENT USER
    if path_only in ("/api/invitations/site", "/api/invite") and method == "GET":
        if not user:
            return json_response({"invitations": [], "success": True})
        conn = get_db()
        cursor = conn.cursor()
        # Sync any pending invitations whose recipient email is now a registered user
        cursor.execute("""
            UPDATE site_invitations
            SET status = 'ACCEPTED'
            WHERE status = 'PENDING'
              AND EXISTS (SELECT 1 FROM users u WHERE LOWER(u.email) = LOWER(site_invitations.recipient_email))
        """)
        conn.commit()
        cursor.execute("""
            SELECT si.id, si.sender_id, si.sender_name, si.recipient_email, si.message, si.status, si.created_at,
                   u.id as registered_user_id, u.username as registered_username, u.avatar_url as registered_avatar
            FROM site_invitations si
            LEFT JOIN users u ON LOWER(u.email) = LOWER(si.recipient_email)
            WHERE si.sender_id = ?
            ORDER BY si.created_at DESC, si.id DESC
        """, (user["id"],))
        rows = [dict(r) for r in cursor.fetchall()]
        conn.close()
        return json_response({"invitations": rows, "success": True})

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
            cursor.execute("""
                DELETE FROM group_invitations
                WHERE group_id = ? AND status = 'PENDING' AND id != ?
                  AND (LOWER(recipient_username) = LOWER(?) OR LOWER(recipient_username) = LOWER(?))
            """, (gid, invite_id, user["username"], user["email"]))
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
            etime = (body.get("event_time") or "").strip() or None
            if desc and url:
                resources_list = [{"description": desc, "url": url, "resource_type": rtype, "theme": rtheme, "event_date": edate, "event_time": etime}]

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
            etime = (item.get("event_time") or "").strip() or None
            if desc and url:
                extracted_text = extract_resource_text(url)
                cursor.execute("INSERT INTO group_resources (group_id, title, url, resource_type, theme, event_date, event_time, added_by, extracted_text) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                               (gid, desc, url, rtype, rtheme, edate, etime, user["id"], extracted_text))
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

        broadcast_email = bool(body.get("broadcast_email") or body.get("notify_members"))

        ok, mod_err = check_content_moderation(user, [msg])
        if not ok:
            return error_response(mod_err, 400)

        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT id, name FROM groups WHERE id = ?", (gid,))
        g_chat_row = cursor.fetchone()
        if not g_chat_row:
            conn.close()
            return error_response("Space not found", 404)
        space_name = g_chat_row["name"]

        if broadcast_email:
            if user.get("is_site_admin") != 1:
                cursor.execute("SELECT 1 FROM group_members WHERE group_id = ? AND user_id = ?", (gid, user["id"]))
                if not cursor.fetchone():
                    conn.close()
                    return error_response("Join this Space first to broadcast emails to Space members.", 403)
            ok_bcast, bcast_err = check_auth_rate_limit(
                "chat_broadcast", f"{user['id']}:{gid}", max_requests=3, window_seconds=300.0
            )
            if not ok_bcast:
                conn.close()
                return error_response("Broadcast email limit reached for this Space (max 3 per 5 minutes). Uncheck broadcast to keep chatting!", 429)

        cursor.execute(
            "INSERT INTO group_messages (group_id, user_id, message, is_broadcast) VALUES (?, ?, ?, ?)",
            (gid, user["id"], msg, 1 if broadcast_email else 0),
        )
        mid = cursor.lastrowid

        # Hybrid Space Chat Email & In-App Notification Routing:
        #   1) Direct @username mentions -> immediate 'space_chat_mention' email
        #   2) Member broadcast toggle   -> immediate 'space_chat_broadcast' email to Space members
        #   3) Opt-in passive activity   -> 'space_chat_activity' email (max 1 per 6h per Space)
        chat_email_dispatches = []
        notified_uids = set()
        short_snip = msg[:60] + ("..." if len(msg) > 60 else "")

        mention_tokens = list({
            m_uname.lower()
            for m_uname in re.findall(r"(?<![A-Za-z0-9_])@([A-Za-z0-9_]{2,40})", msg)
        })
        if mention_tokens:
            m_placeholders = ",".join("?" for _ in mention_tokens)
            cursor.execute(f"""
                SELECT id, username, email, email_prefs
                FROM users
                WHERE LOWER(username) IN ({m_placeholders})
                  AND id != ?
                  AND COALESCE(is_banned, 0) = 0
            """, (*mention_tokens, user["id"]))
            for m_user in cursor.fetchall():
                notified_uids.add(m_user["id"])
                create_in_app_notification(
                    conn,
                    m_user["id"],
                    user["id"],
                    "CHAT_MENTION",
                    gid,
                    f"💬 @{user['username']} mentioned you in {space_name}: \"{short_snip}\"",
                    f"/#/group/{gid}",
                )
                if m_user["email"] and is_email_pref_enabled(m_user["email_prefs"], "chat_mentions"):
                    u_tok = ensure_user_unsubscribe_token(conn, m_user["id"])
                    u_unsub = build_unsubscribe_url(base_url, u_tok, "chat_mentions")
                    chat_email_dispatches.append((
                        m_user["email"],
                        build_space_chat_email(
                            m_user["username"],
                            user["username"],
                            gid,
                            space_name,
                            msg,
                            mode="mention",
                            unsubscribe_url=u_unsub,
                            base_url=base_url,
                        ),
                        u_unsub,
                    ))

        cursor.execute("""
            SELECT DISTINCT u.id, u.username, u.email, u.email_prefs
            FROM group_members gm
            JOIN users u ON gm.user_id = u.id
            WHERE gm.group_id = ?
              AND u.id != ?
              AND COALESCE(u.is_banned, 0) = 0
        """, (gid, user["id"]))
        space_members = cursor.fetchall()

        if broadcast_email:
            for sm in space_members:
                if sm["id"] in notified_uids:
                    continue
                notified_uids.add(sm["id"])
                create_in_app_notification(
                    conn,
                    sm["id"],
                    user["id"],
                    "CHAT_BROADCAST",
                    gid,
                    f"📢 @{user['username']} in {space_name}: \"{short_snip}\"",
                    f"/#/group/{gid}",
                )
                if sm["email"] and is_email_pref_enabled(sm["email_prefs"], "chat_mentions"):
                    u_tok = ensure_user_unsubscribe_token(conn, sm["id"])
                    u_unsub = build_unsubscribe_url(base_url, u_tok, "chat_mentions")
                    chat_email_dispatches.append((
                        sm["email"],
                        build_space_chat_email(
                            sm["username"],
                            user["username"],
                            gid,
                            space_name,
                            msg,
                            mode="broadcast",
                            unsubscribe_url=u_unsub,
                            base_url=base_url,
                        ),
                        u_unsub,
                    ))
        else:
            activity_subj = f"💬 New chat conversation in \"{space_name}\""
            for sm in space_members:
                if sm["id"] in notified_uids:
                    continue
                if sm["email"] and is_email_pref_enabled(sm["email_prefs"], "chat_activity"):
                    cursor.execute("""
                        SELECT 1 FROM email_outbox
                        WHERE recipient_email = ?
                          AND template_key = 'space_chat_activity'
                          AND subject = ?
                          AND sent_at >= datetime('now', '-6 hours')
                        LIMIT 1
                    """, (sm["email"], activity_subj))
                    if not cursor.fetchone():
                        u_tok = ensure_user_unsubscribe_token(conn, sm["id"])
                        u_unsub = build_unsubscribe_url(base_url, u_tok, "chat_activity")
                        chat_email_dispatches.append((
                            sm["email"],
                            build_space_chat_email(
                                sm["username"],
                                user["username"],
                                gid,
                                space_name,
                                msg,
                                mode="activity",
                                unsubscribe_url=u_unsub,
                                base_url=base_url,
                            ),
                            u_unsub,
                        ))

        conn.commit()

        cursor.execute("""
            SELECT m.*, u.username as author_name, u.avatar_url as author_avatar
            FROM group_messages m
            JOIN users u ON m.user_id = u.id
            WHERE m.id = ?
        """, (mid,))
        new_m = dict(cursor.fetchone())
        conn.close()

        for rec_email, chat_tpl, chat_unsub in chat_email_dispatches:
            dispatch_email_template(rec_email, chat_tpl, unsubscribe_url=chat_unsub)

        return json_response({
            "message": new_m,
            "emailed_count": len(chat_email_dispatches),
            "broadcast": broadcast_email,
            "success": True,
        }, 201)

    # DELETE GROUP CHAT MESSAGE
    if path_only.startswith("/api/groups/") and "/chat/" in path_only and method == "DELETE":
        if not user:
            return error_response("Login required", 401)
        parts = path_only.split("/")
        try:
            gid = int(parts[3])
            mid = int(parts[5])
        except (ValueError, IndexError):
            return error_response("Invalid group or message ID")
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT id, user_id FROM group_messages WHERE id = ? AND group_id = ?", (mid, gid))
        m_row = cursor.fetchone()
        if not m_row:
            conn.close()
            return error_response("Message not found", 404)
        is_owner = (m_row["user_id"] == user["id"])
        is_super_admin = (user.get("is_site_admin") == 1)
        is_group_admin = False
        if not is_super_admin:
            cursor.execute("SELECT is_admin FROM group_members WHERE group_id = ? AND user_id = ?", (gid, user["id"]))
            gm_row = cursor.fetchone()
            if gm_row and gm_row["is_admin"] == 1:
                is_group_admin = True
        if not (is_owner or is_super_admin or is_group_admin):
            conn.close()
            return error_response("Forbidden: You do not have permission to delete this chat message.", 403)
        cursor.execute("DELETE FROM group_messages WHERE id = ? AND group_id = ?", (mid, gid))
        conn.commit()
        conn.close()
        return json_response({"success": True, "deleted_id": mid})

    # ================== IN-APP NOTIFICATIONS (POLLING & REALTIME) ==================
    if path_only == "/api/notifications" and method == "GET":
        if not user:
            return error_response("Login required", 401)
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT n.id, n.notif_type, n.target_id, n.message, n.link_hash, n.is_read, n.created_at,
                   u.username as actor_name, u.avatar_url as actor_avatar
            FROM notifications n
            LEFT JOIN users u ON n.actor_id = u.id
            WHERE n.user_id = ?
            ORDER BY n.created_at DESC
            LIMIT 25
        """, (user["id"],))
        notifs = [dict(r) for r in cursor.fetchall()]
        cursor.execute("SELECT COUNT(*) FROM notifications WHERE user_id = ? AND is_read = 0", (user["id"],))
        unread_count = cursor.fetchone()[0]
        conn.close()
        return json_response({"success": True, "notifications": notifs, "unread_count": unread_count})

    if path_only == "/api/notifications/read" and method == "POST":
        if not user:
            return error_response("Login required", 401)
        notif_id = body.get("id")
        conn = get_db()
        cursor = conn.cursor()
        if notif_id:
            cursor.execute("UPDATE notifications SET is_read = 1 WHERE id = ? AND user_id = ?", (notif_id, user["id"]))
        else:
            cursor.execute("UPDATE notifications SET is_read = 1 WHERE user_id = ?", (user["id"],))
        conn.commit()
        conn.close()
        return json_response({"success": True})

    # ================== SITE ADMIN USER BAN / SUSPEND ==================
    if path_only.startswith("/api/admin/users/") and path_only.endswith("/ban") and method == "POST":
        if not user or user.get("is_site_admin") != 1:
            return error_response("Forbidden: Requires Site Admin status.", 403)
        parts = path_only.split("/")
        try:
            target_uid = int(parts[4])
        except (ValueError, IndexError):
            return error_response("Invalid target user ID")
        is_banned_val = 1 if (body.get("is_banned") in (1, True, "1", "true") or body.get("ban") in (1, True, "1", "true")) else 0
        purge_content = bool(body.get("purge_content", False))

        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT username, email FROM users WHERE id = ?", (target_uid,))
        ban_u_row = cursor.fetchone()
        cursor.execute("UPDATE users SET is_banned = ? WHERE id = ?", (is_banned_val, target_uid))
        if is_banned_val == 1:
            cursor.execute("DELETE FROM sessions WHERE user_id = ?", (target_uid,))
            if purge_content:
                cursor.execute("DELETE FROM feed_items WHERE author_id = ?", (target_uid,))
                cursor.execute("DELETE FROM comments WHERE user_id = ?", (target_uid,))
                cursor.execute("DELETE FROM group_messages WHERE user_id = ?", (target_uid,))
        conn.commit()
        conn.close()
        if ban_u_row and ban_u_row["email"]:
            dispatch_email_template(
                ban_u_row["email"],
                build_moderation_action_email(
                    ban_u_row["username"],
                    "ACCOUNT_SUSPENDED" if is_banned_val == 1 else "ACCOUNT_RESTORED",
                    "ACCOUNT",
                    base_url=base_url,
                ),
            )
        return json_response({"success": True, "user_id": target_uid, "is_banned": is_banned_val, "purged": purge_content})

    # ================== CONTENT REPORTING & MODERATION QUEUE ==================
    if path_only == "/api/reports" and method == "POST":
        if not user:
            return error_response("Login required to submit reports", 401)
        target_type = str(body.get("target_type", "")).strip().upper()
        try:
            target_id = int(body.get("target_id"))
        except (ValueError, TypeError):
            return error_response("Valid target_type and target_id are required.")
        reason = str(body.get("reason", "")).strip()
        notes = str(body.get("notes", "")).strip()
        if not target_type or not reason:
            return error_response("Report reason is required.")

        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO content_reports (target_type, target_id, reporter_id, reason, notes)
            VALUES (?, ?, ?, ?, ?)
        """, (target_type, target_id, user["id"], reason, notes))
        rid = cursor.lastrowid

        rep_snippet = ""
        rep_author_name = ""
        if target_type in ("POST", "KUDOS"):
            cursor.execute("SELECT f.title, f.content, u.username FROM feed_items f LEFT JOIN users u ON f.author_id = u.id WHERE f.id = ?", (target_id,))
            r_item = cursor.fetchone()
            if r_item:
                rep_snippet = f"{r_item['title'] or ''} - {r_item['content']}".strip(" -")
                rep_author_name = r_item["username"] or ""
        elif target_type == "COMMENT":
            cursor.execute("SELECT c.content, u.username FROM comments c LEFT JOIN users u ON c.user_id = u.id WHERE c.id = ?", (target_id,))
            r_item = cursor.fetchone()
            if r_item:
                rep_snippet = r_item["content"]
                rep_author_name = r_item["username"] or ""
        elif target_type == "CHAT":
            cursor.execute("SELECT m.message, u.username FROM group_messages m LEFT JOIN users u ON m.user_id = u.id WHERE m.id = ?", (target_id,))
            r_item = cursor.fetchone()
            if r_item:
                rep_snippet = r_item["message"]
                rep_author_name = r_item["username"] or ""

        conn.commit()
        conn.close()

        support_alert_recipient = os.environ.get("SUPPORT_ALERT_EMAIL", "support@gooddeeds.space")
        dispatch_email_template(
            support_alert_recipient,
            build_content_report_admin_alert_email(
                reporter_username=user["username"],
                target_type=target_type,
                target_id=target_id,
                target_author_name=rep_author_name,
                reason=reason,
                notes=notes,
                content_snippet=rep_snippet,
                report_id=rid,
                base_url=base_url,
            ),
        )
        return json_response({"success": True, "report_id": rid}, 201)

    if path_only == "/api/admin/reports" and method == "GET":
        if not user or user.get("is_site_admin") != 1:
            return error_response("Forbidden: Requires Site Admin status.", 403)
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT r.*, u.username as reporter_name
            FROM content_reports r
            LEFT JOIN users u ON r.reporter_id = u.id
            ORDER BY r.status = 'PENDING' DESC, r.created_at DESC
        """)
        reports = []
        for r in cursor.fetchall():
            rep = dict(r)
            ttype = rep["target_type"]
            tid = rep["target_id"]
            snippet = ""
            author_id = None
            author_name = ""
            if ttype in ("POST", "KUDOS"):
                cursor.execute("SELECT f.title, f.content, f.author_id, u.username FROM feed_items f LEFT JOIN users u ON f.author_id = u.id WHERE f.id = ?", (tid,))
                row = cursor.fetchone()
                if row:
                    snippet = f"{row['title'] or ''} - {row['content']}".strip(" -")
                    author_id = row["author_id"]
                    author_name = row["username"] or ""
            elif ttype == "COMMENT":
                cursor.execute("SELECT c.content, c.user_id, u.username FROM comments c LEFT JOIN users u ON c.user_id = u.id WHERE c.id = ?", (tid,))
                row = cursor.fetchone()
                if row:
                    snippet = row["content"]
                    author_id = row["user_id"]
                    author_name = row["username"] or ""
            elif ttype == "CHAT":
                cursor.execute("SELECT m.message, m.user_id, u.username FROM group_messages m LEFT JOIN users u ON m.user_id = u.id WHERE m.id = ?", (tid,))
                row = cursor.fetchone()
                if row:
                    snippet = row["message"]
                    author_id = row["user_id"]
                    author_name = row["username"] or ""
            rep["content_snippet"] = snippet or "[Deleted or unavailable]"
            rep["target_author_id"] = author_id
            rep["target_author_name"] = author_name
            reports.append(rep)
        conn.close()
        return json_response({"reports": reports})

    if path_only.startswith("/api/admin/reports/") and path_only.endswith("/resolve") and method == "POST":
        if not user or user.get("is_site_admin") != 1:
            return error_response("Forbidden: Requires Site Admin status.", 403)
        parts = path_only.split("/")
        try:
            rid = int(parts[4])
        except (ValueError, IndexError):
            return error_response("Invalid report ID")
        action = str(body.get("action", "DISMISS")).strip().upper() # 'DISMISS', 'DELETE_CONTENT', 'BAN_AUTHOR'

        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM content_reports WHERE id = ?", (rid,))
        rep = cursor.fetchone()
        if not rep:
            conn.close()
            return error_response("Report not found", 404)

        ttype = rep["target_type"]
        tid = rep["target_id"]
        target_author_id = None
        target_author_info = None

        if action in ("DELETE_CONTENT", "BAN_AUTHOR"):
            if ttype in ("POST", "KUDOS"):
                cursor.execute("SELECT author_id FROM feed_items WHERE id = ?", (tid,))
                row = cursor.fetchone()
                if row: target_author_id = row["author_id"]
                cursor.execute("DELETE FROM feed_items WHERE id = ?", (tid,))
            elif ttype == "COMMENT":
                cursor.execute("SELECT user_id FROM comments WHERE id = ?", (tid,))
                row = cursor.fetchone()
                if row: target_author_id = row["user_id"]
                cursor.execute("DELETE FROM comments WHERE id = ?", (tid,))
            elif ttype == "CHAT":
                cursor.execute("SELECT user_id FROM group_messages WHERE id = ?", (tid,))
                row = cursor.fetchone()
                if row: target_author_id = row["user_id"]
                cursor.execute("DELETE FROM group_messages WHERE id = ?", (tid,))

            if target_author_id:
                cursor.execute("SELECT username, email FROM users WHERE id = ?", (target_author_id,))
                au_row = cursor.fetchone()
                if au_row and au_row["email"]:
                    target_author_info = (au_row["email"], au_row["username"])

            if action == "BAN_AUTHOR" and target_author_id:
                cursor.execute("UPDATE users SET is_banned = 1 WHERE id = ?", (target_author_id,))
                cursor.execute("DELETE FROM sessions WHERE user_id = ?", (target_author_id,))

        new_status = "DISMISSED" if action == "DISMISS" else "RESOLVED"
        cursor.execute("UPDATE content_reports SET status = ? WHERE id = ?", (new_status, rid))
        conn.commit()
        conn.close()
        if target_author_info:
            dispatch_email_template(
                target_author_info[0],
                build_moderation_action_email(
                    target_author_info[1],
                    "ACCOUNT_SUSPENDED" if action == "BAN_AUTHOR" else "CONTENT_REMOVED",
                    ttype,
                    reason=rep["reason"] or "",
                    base_url=base_url,
                ),
            )
        return json_response({"success": True, "report_id": rid, "status": new_status, "action": action})

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
        inquiry_id = cursor.lastrowid
        submitted_at = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        conn.commit()
        conn.close()

        support_alert_recipient = os.environ.get("SUPPORT_ALERT_EMAIL", "support@gooddeeds.space")
        dispatch_email_template(
            user["email"],
            build_support_confirmation_email(user["username"], inquiry_id, subject, message, base_url),
        )
        dispatch_email_template(
            support_alert_recipient,
            build_support_admin_alert_email(user["username"], user["email"], inquiry_id, subject, message, submitted_at, base_url),
            reply_to=user["email"],
        )

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
        allowed = {"server.py", "database.py", "handlers.py", "email_templates.py", "run.sh", "static/index.html", "static/app.js", "static/style.css"}
        if fname not in allowed:
            return error_response("Source file restricted or not found.", 404)
        base_dir = os.path.dirname(os.path.abspath(__file__))
        full_p = os.path.join(base_dir, fname)
        with open(full_p, "r", encoding="utf-8") as f:
            content = f.read()
        return json_response({"file": fname, "content": content})

    return error_response("API endpoint not found", 404)
