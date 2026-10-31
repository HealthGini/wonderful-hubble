"""
Branded Transactional & Community Email Templates for GoodDeeds.space.

Provides responsive HTML + plain-text email builders across all platform scenarios:
1. Account, Authentication & Security (Welcome, Email Verification, Password Reset, Security Alert)
2. Invitations & Viral Growth (Platform Invite, Space Invite, Invite Accepted)
3. Community Recognition & Activity (Kudos Received, Comment Received, Space Announcement, Weekly Digest)
4. Space Governance (Space Admin Role Updated, Space Member Removed/Banned)
5. Trust, Safety & Support (Support Confirmation, Support Admin Alert, Content Report Alert, Moderation Action)
6. LLC Supporter & Organization Tiers (Supporter Contribution Receipt, Organization Subscription Onboarding)
"""

import html as html_lib
import json
import os
from urllib.parse import urlencode


DEFAULT_EMAIL_PREFS = {
    "kudos": True,
    "comments": True,
    "invites": True,
    "space_updates": True,
    "chat_mentions": True,
    "chat_activity": False,
    "digest": True,
}


def parse_user_email_prefs(raw_prefs) -> dict:
    """Returns normalized email notification preferences merged over defaults."""
    prefs = dict(DEFAULT_EMAIL_PREFS)
    if not raw_prefs:
        return prefs
    data = raw_prefs
    if isinstance(raw_prefs, str):
        try:
            data = json.loads(raw_prefs)
        except Exception:
            data = {}
    if isinstance(data, dict):
        for k in DEFAULT_EMAIL_PREFS:
            if k in data:
                prefs[k] = bool(data[k])
    return prefs


def is_email_pref_enabled(raw_prefs, category_key: str) -> bool:
    """Checks whether a non-transactional email category is enabled for the user."""
    if not category_key or category_key == "transactional":
        return True
    prefs = parse_user_email_prefs(raw_prefs)
    return bool(prefs.get(category_key, DEFAULT_EMAIL_PREFS.get(category_key, True)))


def get_public_base_url(headers=None) -> str:
    """
    Resolves the canonical public base URL for clickable links inside emails.
    Priority:
      1. PUBLIC_BASE_URL environment variable (e.g. 'https://gooddeeds.space')
      2. Origin or X-Forwarded-Proto + Host request headers
      3. 'http://localhost:8080' local development fallback
    """
    env_url = (os.environ.get("PUBLIC_BASE_URL") or "").strip().rstrip("/")
    if env_url:
        return env_url
    if headers and hasattr(headers, "get"):
        origin = (headers.get("Origin") or headers.get("origin") or "").strip().rstrip("/")
        if origin.startswith("http://") or origin.startswith("https://"):
            return origin
        host = (headers.get("Host") or headers.get("host") or "").strip()
        if host:
            proto = (headers.get("X-Forwarded-Proto") or headers.get("x-forwarded-proto") or "").strip().lower()
            if proto not in ("http", "https"):
                proto = "http" if ("localhost" in host or host.startswith("127.")) else "https"
            return f"{proto}://{host}".rstrip("/")
    return "http://localhost:8080"


def build_unsubscribe_url(base_url: str, unsubscribe_token: str, category: str = "all") -> str:
    """Builds a 1-click unsubscribe URL that works without requiring login."""
    if not unsubscribe_token:
        return ""
    clean_base = (base_url or "http://localhost:8080").rstrip("/")
    qs = urlencode({"token": unsubscribe_token, "category": category or "all"})
    return f"{clean_base}/#/unsubscribe?{qs}"


def _esc(val) -> str:
    return html_lib.escape(str(val or ""))


def render_branded_email(
    *,
    badge_text: str,
    accent_theme: str = "amber",
    heading: str,
    greeting: str,
    intro_paragraphs: list,
    quote_block: str = "",
    quote_caption: str = "",
    bullet_items: list = None,
    cta_label: str = "",
    cta_url: str = "",
    secondary_note: str = "",
    base_url: str = "http://localhost:8080",
    unsubscribe_url: str = "",
    category_label: str = "",
) -> str:
    """
    Renders a responsive, email-client-safe HTML message using inline styles and table layout.
    """
    palettes = {
        "amber": {
            "banner_bg": "#fffbeb",
            "banner_border": "#fde68a",
            "badge_bg": "#fef3c7",
            "badge_text": "#92400e",
            "cta_bg": "#d97706",
            "quote_bg": "#fffbeb",
            "quote_border": "#f59e0b",
        },
        "indigo": {
            "banner_bg": "#eef2ff",
            "banner_border": "#c7d2fe",
            "badge_bg": "#e0e7ff",
            "badge_text": "#3730a3",
            "cta_bg": "#4f46e5",
            "quote_bg": "#f5f7ff",
            "quote_border": "#6366f1",
        },
        "teal": {
            "banner_bg": "#f0fdfa",
            "banner_border": "#99f6e4",
            "badge_bg": "#ccfbf1",
            "badge_text": "#115e59",
            "cta_bg": "#0f766e",
            "quote_bg": "#f0fdfa",
            "quote_border": "#14b8a6",
        },
        "rose": {
            "banner_bg": "#fff1f2",
            "banner_border": "#fecdd3",
            "badge_bg": "#ffe4e6",
            "badge_text": "#9f1239",
            "cta_bg": "#be123c",
            "quote_bg": "#fff1f2",
            "quote_border": "#f43f5e",
        },
        "slate": {
            "banner_bg": "#f8fafc",
            "banner_border": "#cbd5e1",
            "badge_bg": "#e2e8f0",
            "badge_text": "#1e293b",
            "cta_bg": "#1e293b",
            "quote_bg": "#f8fafc",
            "quote_border": "#64748b",
        },
    }
    pal = palettes.get(accent_theme, palettes["amber"])
    clean_base = (base_url or "http://localhost:8080").rstrip("/")

    paragraphs_html = "".join(
        f'<p style="margin:0 0 14px 0;font-size:15px;line-height:1.65;color:#334155;">{_esc(p)}</p>'
        for p in (intro_paragraphs or [])
        if p
    )

    quote_html = ""
    if quote_block:
        cap_html = (
            f'<div style="margin-top:8px;font-size:12px;font-weight:700;color:#64748b;">{_esc(quote_caption)}</div>'
            if quote_caption
            else ""
        )
        quote_html = f"""
        <div style="margin:18px 0;padding:16px 18px;background-color:{pal['quote_bg']};border-left:4px solid {pal['quote_border']};border-radius:12px;">
          <div style="font-size:15px;line-height:1.6;color:#1e293b;font-weight:600;white-space:pre-line;">{_esc(quote_block)}</div>
          {cap_html}
        </div>
        """

    bullets_html = ""
    if bullet_items:
        li_rows = "".join(
            f'<li style="margin:0 0 8px 0;font-size:14px;line-height:1.55;color:#334155;">{_esc(item)}</li>'
            for item in bullet_items
            if item
        )
        bullets_html = f'<ul style="margin:14px 0 18px 0;padding-left:20px;">{li_rows}</ul>'

    cta_html = ""
    if cta_label and cta_url:
        safe_url = _esc(cta_url)
        cta_html = f"""
        <div style="margin:24px 0 18px 0;text-align:center;">
          <a href="{safe_url}" style="display:inline-block;padding:13px 26px;background-color:{pal['cta_bg']};color:#ffffff;text-decoration:none;font-weight:800;font-size:15px;border-radius:999px;">{_esc(cta_label)}</a>
          <div style="margin-top:10px;font-size:12px;color:#64748b;word-break:break-all;">
            Or open link directly: <a href="{safe_url}" style="color:#4f46e5;text-decoration:underline;">{safe_url}</a>
          </div>
        </div>
        """

    secondary_html = (
        f'<p style="margin:14px 0 0 0;font-size:13px;line-height:1.55;color:#64748b;">{_esc(secondary_note)}</p>'
        if secondary_note
        else ""
    )

    prefs_footer_html = ""
    if unsubscribe_url:
        safe_unsub = _esc(unsubscribe_url)
        safe_prefs = _esc(f"{clean_base}/#/profile")
        cat_note = f" ({_esc(category_label)})" if category_label else ""
        prefs_footer_html = f"""
        <div style="margin-top:10px;font-size:12px;color:#64748b;">
          <a href="{safe_prefs}" style="color:#475569;text-decoration:underline;">Manage Email Preferences</a>
          &nbsp;&bull;&nbsp;
          <a href="{safe_unsub}" style="color:#475569;text-decoration:underline;">Unsubscribe{cat_note}</a>
        </div>
        """
    else:
        prefs_footer_html = """
        <div style="margin-top:8px;font-size:11px;color:#94a3b8;">
          This is an essential account, governance, or support service notification for your GoodDeeds.space account.
        </div>
        """

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{_esc(heading)}</title>
</head>
<body style="margin:0;padding:0;background-color:#faf9f6;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif;color:#1c1917;">
  <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="background-color:#faf9f6;padding:28px 14px;">
    <tr>
      <td align="center">
        <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="max-width:600px;background-color:#ffffff;border:1px solid #e7e5e4;border-radius:22px;overflow:hidden;">
          <tr>
            <td style="padding:20px 28px;background-color:{pal['banner_bg']};border-bottom:1px solid {pal['banner_border']};">
              <table role="presentation" width="100%" cellspacing="0" cellpadding="0">
                <tr>
                  <td>
                    <a href="{_esc(clean_base)}/#/" style="text-decoration:none;font-size:19px;font-weight:900;color:#0f766e;letter-spacing:-0.02em;">
                      ☀️ GoodDeeds<span style="color:#b45309;">.space</span>
                    </a>
                  </td>
                  <td align="right">
                    <span style="display:inline-block;padding:4px 11px;border-radius:999px;background-color:{pal['badge_bg']};color:{pal['badge_text']};font-size:11px;font-weight:800;letter-spacing:0.04em;text-transform:uppercase;">
                      {_esc(badge_text)}
                    </span>
                  </td>
                </tr>
              </table>
            </td>
          </tr>
          <tr>
            <td style="padding:28px;">
              <h1 style="margin:0 0 14px 0;font-size:22px;line-height:1.3;font-weight:800;color:#292524;">{_esc(heading)}</h1>
              <p style="margin:0 0 14px 0;font-size:15px;font-weight:700;color:#1e293b;">{_esc(greeting)}</p>
              {paragraphs_html}
              {quote_html}
              {bullets_html}
              {cta_html}
              {secondary_html}
            </td>
          </tr>
          <tr>
            <td style="padding:18px 28px;background-color:#fafaf9;border-top:1px solid #f1f5f9;text-align:center;">
              <div style="font-size:12px;font-weight:700;color:#57534e;">
                Become the best version of yourself — one good deed at a time.
              </div>
              <div style="margin-top:4px;font-size:12px;color:#78716c;">
                <a href="{_esc(clean_base)}/#/" style="color:#0f766e;text-decoration:none;font-weight:700;">GoodDeeds.space</a>
                &nbsp;&bull;&nbsp; Free &amp; Open Community Spaces
              </div>
              {prefs_footer_html}
            </td>
          </tr>
        </table>
      </td>
    </tr>
  </table>
</body>
</html>"""


# ==============================================================================
# 1. ACCOUNT, AUTHENTICATION & SECURITY TEMPLATES
# ==============================================================================

def build_welcome_email(username: str, verify_url: str = "", base_url: str = "http://localhost:8080") -> dict:
    clean_base = (base_url or "http://localhost:8080").rstrip("/")
    cta_url = verify_url or f"{clean_base}/#/feed"
    cta_label = "Verify Email & Explore GoodDeeds.space ↗" if verify_url else "Explore GoodDeeds.space ↗"
    subject = f"☀️ Welcome to GoodDeeds.space, {username}!"
    bullets = [
        "🔍 Search Community Events, Resources, Posts & Kudos — or ask questions in plain English with Ask in Chat.",
        "👥 Join open Community Spaces for mental wellness, education, food & mutual aid, and neighborhood action.",
        "🌟 Give Public Kudos to recognize everyday kindness and uplift neighbors.",
    ]
    verify_line = (
        f"\nPlease confirm your email address with one click:\n{verify_url}\n"
        if verify_url
        else ""
    )
    text_body = (
        f"Hello {username},\n\n"
        f"Welcome to GoodDeeds.space! We're thrilled to have you in our community.\n"
        f"{verify_line}\n"
        f"Here are three ways to get started today:\n"
        f"  • {bullets[0]}\n"
        f"  • {bullets[1]}\n"
        f"  • {bullets[2]}\n\n"
        f"Visit the community feed:\n{clean_base}/#/feed\n\n"
        f"Become the best version of yourself — one good deed at a time.\n"
        f"— The GoodDeeds.space Team"
    )
    html_body = render_branded_email(
        badge_text="Welcome",
        accent_theme="amber",
        heading="Welcome to GoodDeeds.space!",
        greeting=f"Hello {username},",
        intro_paragraphs=[
            "We're glad you're here! GoodDeeds.space is a welcoming community platform built to celebrate intrinsic kindness, share helpful local resources & events, and collaborate across open Spaces.",
            "Please confirm your email address below and jump right into the community:" if verify_url else "Here are a few ways to jump right into the community:",
        ],
        bullet_items=bullets,
        cta_label=cta_label,
        cta_url=cta_url,
        base_url=clean_base,
    )
    return {
        "template_key": "welcome",
        "category": "transactional",
        "subject": subject,
        "text_body": text_body,
        "html_body": html_body,
    }


def build_email_verification_email(username: str, verify_url: str, base_url: str = "http://localhost:8080") -> dict:
    clean_base = (base_url or "http://localhost:8080").rstrip("/")
    subject = "✅ Verify your email address for GoodDeeds.space"
    text_body = (
        f"Hello {username},\n\n"
        f"Please verify your email address for your GoodDeeds.space account by clicking the link below:\n\n"
        f"{verify_url}\n\n"
        f"This link expires in 24 hours. If you did not create a GoodDeeds.space account, you can safely ignore this message."
    )
    html_body = render_branded_email(
        badge_text="Email Verification",
        accent_theme="teal",
        heading="Confirm Your Email Address",
        greeting=f"Hello {username},",
        intro_paragraphs=[
            "Click the button below to confirm your email address and keep your GoodDeeds.space account verified.",
        ],
        cta_label="Verify My Email Address ✓",
        cta_url=verify_url,
        secondary_note="This verification link expires in 24 hours. If you didn't request this, you can safely ignore this email.",
        base_url=clean_base,
    )
    return {
        "template_key": "email_verification",
        "category": "transactional",
        "subject": subject,
        "text_body": text_body,
        "html_body": html_body,
    }


def build_password_reset_email(username: str, reset_url: str, expires_minutes: int = 60, base_url: str = "http://localhost:8080") -> dict:
    clean_base = (base_url or "http://localhost:8080").rstrip("/")
    subject = "🔑 Reset your GoodDeeds.space password"
    text_body = (
        f"Hello {username},\n\n"
        f"We received a request to reset the password for your GoodDeeds.space account.\n\n"
        f"Click the link below to choose a new password (valid for {expires_minutes} minutes):\n"
        f"{reset_url}\n\n"
        f"If you did not request a password reset, no changes have been made to your account and you can safely ignore this email."
    )
    html_body = render_branded_email(
        badge_text="Password Reset",
        accent_theme="indigo",
        heading="Reset Your Password",
        greeting=f"Hello {username},",
        intro_paragraphs=[
            "We received a request to reset the password for your GoodDeeds.space account.",
            f"Use the secure single-use button below within the next {expires_minutes} minutes to set a new password:",
        ],
        cta_label="Choose a New Password →",
        cta_url=reset_url,
        secondary_note="Didn't request this? Your current password remains unchanged — you can safely ignore this message.",
        base_url=clean_base,
    )
    return {
        "template_key": "password_reset",
        "category": "transactional",
        "subject": subject,
        "text_body": text_body,
        "html_body": html_body,
    }


def build_security_alert_email(username: str, event_label: str, base_url: str = "http://localhost:8080") -> dict:
    clean_base = (base_url or "http://localhost:8080").rstrip("/")
    subject = f"🛡️ Security Notice: {event_label} on GoodDeeds.space"
    support_url = f"{clean_base}/#/feed"
    text_body = (
        f"Hello {username},\n\n"
        f"This is an automated security confirmation that the following change occurred on your GoodDeeds.space account:\n\n"
        f"  • {event_label}\n\n"
        f"If you made this change, no further action is needed. If you do not recognize this activity, please reset your password immediately or contact Customer Service at {support_url}."
    )
    html_body = render_branded_email(
        badge_text="Security Alert",
        accent_theme="slate",
        heading=f"Account Security Update: {event_label}",
        greeting=f"Hello {username},",
        intro_paragraphs=[
            "We're letting you know about an authentication or security update on your GoodDeeds.space account:",
        ],
        quote_block=event_label,
        cta_label="Review My Account →",
        cta_url=f"{clean_base}/#/profile",
        secondary_note="If you made this change, you're all set. If you don't recognize this activity, please reset your password right away and reach out via Customer Service.",
        base_url=clean_base,
    )
    return {
        "template_key": "security_alert",
        "category": "transactional",
        "subject": subject,
        "text_body": text_body,
        "html_body": html_body,
    }


# ==============================================================================
# 2. INVITATIONS & VIRAL GROWTH TEMPLATES
# ==============================================================================

def build_site_invitation_email(sender_username: str, sender_email: str, note_text: str, base_url: str = "http://localhost:8080") -> dict:
    clean_base = (base_url or "http://localhost:8080").rstrip("/")
    join_url = f"{clean_base}/#/"
    note = note_text or "Join me on GoodDeeds.space to recognize everyday kindness with public Kudos and share local community resources & events!"
    subject = f"☀️ {sender_username} invited you to join GoodDeeds.space!"
    text_body = (
        f"Hello!\n\n"
        f"{sender_username} ({sender_email}) has invited you to join GoodDeeds.space — "
        f"a community platform built to celebrate everyday kindness with public Kudos and share helpful community events and resources.\n\n"
        f"Personal Note from {sender_username}:\n"
        f"\"{note}\"\n\n"
        f"Join free today:\n"
        f"{join_url}\n\n"
        f"Become the best version of yourself — one good deed at a time."
    )
    html_body = render_branded_email(
        badge_text="Community Invite",
        accent_theme="amber",
        heading=f"{sender_username} invited you to GoodDeeds.space!",
        greeting="Hello!",
        intro_paragraphs=[
            f"{sender_username} ({sender_email}) invited you to join GoodDeeds.space — a welcoming social platform to celebrate intrinsic kindness with public Kudos and discover local community events, mutual aid, and resources.",
        ],
        quote_block=f"\"{note}\"",
        quote_caption=f"— Personal note from @{sender_username}",
        cta_label="Join GoodDeeds.space Free ↗",
        cta_url=join_url,
        base_url=clean_base,
    )
    return {
        "template_key": "site_invitation",
        "category": "transactional",
        "subject": subject,
        "text_body": text_body,
        "html_body": html_body,
    }


def build_space_invitation_email(
    sender_username: str,
    sender_email: str,
    group_id: int,
    group_name: str,
    note_text: str,
    is_existing_user: bool = False,
    unsubscribe_url: str = "",
    base_url: str = "http://localhost:8080",
) -> dict:
    clean_base = (base_url or "http://localhost:8080").rstrip("/")
    space_url = f"{clean_base}/#/group/{group_id}"
    note = note_text or "Join us in promoting goodness and building meaningful community connections!"
    # Preserve 'invited to join' substring for test compatibility
    subject = f"💌 You've been invited to join \"{group_name}\" on GoodDeeds.space!"
    action_hint = (
        "Log in to accept your invitation and collaborate with Space members:"
        if is_existing_user
        else "Create your free account or log in to join this Space today:"
    )
    text_body = (
        f"Hello!\n\n"
        f"{sender_username} ({sender_email}) has invited you to join the community Space \"{group_name}\" on GoodDeeds.space.\n\n"
        f"Personal Note:\n"
        f"\"{note}\"\n\n"
        f"{action_hint}\n"
        f"{space_url}\n\n"
        f"Promote goodness — one good deed at a time."
    )
    html_body = render_branded_email(
        badge_text="Space Invitation",
        accent_theme="teal",
        heading=f"Join the \"{group_name}\" Space",
        greeting="Hello!",
        intro_paragraphs=[
            f"{sender_username} ({sender_email}) invited you to collaborate inside the \"{group_name}\" Space on GoodDeeds.space.",
            action_hint,
        ],
        quote_block=f"\"{note}\"",
        quote_caption=f"— Invited by @{sender_username}",
        cta_label=f"Open \"{group_name}\" Space ↗",
        cta_url=space_url,
        base_url=clean_base,
        unsubscribe_url=unsubscribe_url,
        category_label="Invitations",
    )
    return {
        "template_key": "space_invitation",
        "category": "invites",
        "subject": subject,
        "text_body": text_body,
        "html_body": html_body,
    }


def build_invite_accepted_email(
    inviter_username: str,
    new_username: str,
    new_user_id: int,
    unsubscribe_url: str = "",
    base_url: str = "http://localhost:8080",
) -> dict:
    clean_base = (base_url or "http://localhost:8080").rstrip("/")
    profile_url = f"{clean_base}/#/user/{new_user_id}"
    subject = f"🎉 @{new_username} accepted your invitation to GoodDeeds.space!"
    text_body = (
        f"Hello {inviter_username},\n\n"
        f"Great news — @{new_username} just accepted your invitation and joined GoodDeeds.space!\n\n"
        f"Visit their profile or welcome them with their first public Kudos:\n"
        f"{profile_url}\n\n"
        f"Thank you for helping our caring community grow!"
    )
    html_body = render_branded_email(
        badge_text="Invite Accepted",
        accent_theme="amber",
        heading=f"@{new_username} joined GoodDeeds.space!",
        greeting=f"Hello {inviter_username},",
        intro_paragraphs=[
            f"Wonderful news — @{new_username} accepted your invitation and created their GoodDeeds.space account!",
            "Say hello or send them a warm welcome Kudos to kick off their journey.",
        ],
        cta_label=f"View @{new_username}'s Profile ↗",
        cta_url=profile_url,
        base_url=clean_base,
        unsubscribe_url=unsubscribe_url,
        category_label="Invitations",
    )
    return {
        "template_key": "invite_accepted",
        "category": "invites",
        "subject": subject,
        "text_body": text_body,
        "html_body": html_body,
    }


# ==============================================================================
# 3. COMMUNITY RECOGNITION, ACTIVITY & DIGEST TEMPLATES
# ==============================================================================

def build_kudos_received_email(
    recipient_username: str,
    sender_username: str,
    content: str,
    kudos_id: int,
    unsubscribe_url: str = "",
    base_url: str = "http://localhost:8080",
) -> dict:
    clean_base = (base_url or "http://localhost:8080").rstrip("/")
    kudos_url = f"{clean_base}/#/kudos/{kudos_id}"
    preview = content[:240] + ("..." if len(content) > 240 else "")
    # Preserve 'You received new Kudos' in subject and content preview in body
    subject = f"🌟 You received new Kudos from {sender_username}!"
    text_body = (
        f"Hello {recipient_username},\n\n"
        f"{sender_username} gave you public Kudos on GoodDeeds.space:\n\n"
        f"\"{preview}\"\n\n"
        f"View, react, or reply to your Kudos here:\n"
        f"{kudos_url}"
    )
    html_body = render_branded_email(
        badge_text="Public Kudos",
        accent_theme="amber",
        heading=f"@{sender_username} celebrated you with Public Kudos!",
        greeting=f"Hello {recipient_username},",
        intro_paragraphs=[
            f"Your kindness made a difference! @{sender_username} just shared public appreciation for you on GoodDeeds.space:",
        ],
        quote_block=f"\"{preview}\"",
        quote_caption=f"— Public Kudos from @{sender_username}",
        cta_label="View & Celebrate Your Kudos 🌟",
        cta_url=kudos_url,
        base_url=clean_base,
        unsubscribe_url=unsubscribe_url,
        category_label="Kudos Notifications",
    )
    return {
        "template_key": "kudos_received",
        "category": "kudos",
        "subject": subject,
        "text_body": text_body,
        "html_body": html_body,
    }


def build_comment_notification_email(
    recipient_username: str,
    commenter_username: str,
    item_type: str,
    item_title: str,
    comment_text: str,
    item_id: int,
    unsubscribe_url: str = "",
    base_url: str = "http://localhost:8080",
) -> dict:
    clean_base = (base_url or "http://localhost:8080").rstrip("/")
    is_kudos = str(item_type or "").upper() == "KUDOS"
    route_seg = "kudos" if is_kudos else "post"
    item_url = f"{clean_base}/#/{route_seg}/{item_id}"
    label = "Kudos" if is_kudos else (f"Post \"{item_title}\"" if item_title else "Post")
    snippet = comment_text[:240] + ("..." if len(comment_text) > 240 else "")
    subject = f"💬 @{commenter_username} commented on your {'Kudos' if is_kudos else 'Post'}"
    text_body = (
        f"Hello {recipient_username},\n\n"
        f"@{commenter_username} left a comment on your {label} on GoodDeeds.space:\n\n"
        f"\"{snippet}\"\n\n"
        f"View the conversation and reply here:\n"
        f"{item_url}"
    )
    html_body = render_branded_email(
        badge_text="New Comment",
        accent_theme="indigo",
        heading=f"New reply from @{commenter_username}",
        greeting=f"Hello {recipient_username},",
        intro_paragraphs=[
            f"@{commenter_username} commented on your {label}:",
        ],
        quote_block=f"\"{snippet}\"",
        quote_caption=f"— @{commenter_username}",
        cta_label="View Comment & Reply →",
        cta_url=item_url,
        base_url=clean_base,
        unsubscribe_url=unsubscribe_url,
        category_label="Comment Notifications",
    )
    return {
        "template_key": "comment_received",
        "category": "comments",
        "subject": subject,
        "text_body": text_body,
        "html_body": html_body,
    }


def build_space_announcement_email(
    recipient_username: str,
    author_username: str,
    space_id: int,
    space_name: str,
    post_id: int,
    post_title: str,
    post_subtype_label: str,
    event_date: str = "",
    event_time: str = "",
    summary_snippet: str = "",
    unsubscribe_url: str = "",
    base_url: str = "http://localhost:8080",
) -> dict:
    clean_base = (base_url or "http://localhost:8080").rstrip("/")
    post_url = f"{clean_base}/#/post/{post_id}"
    when_line = f"📅 Scheduled: {event_date}" + (f" at {event_time}" if event_time else "") if event_date else ""
    snippet = (summary_snippet or "")[:220] + ("..." if len(summary_snippet or "") > 220 else "")
    subject = f"📢 New {post_subtype_label} in {space_name}: {post_title}"
    text_body = (
        f"Hello {recipient_username},\n\n"
        f"@{author_username} shared a new {post_subtype_label} in your joined Space \"{space_name}\":\n\n"
        f"{post_title}\n"
        f"{when_line + chr(10) if when_line else ''}"
        f"{snippet}\n\n"
        f"Open details in {space_name}:\n{post_url}"
    )
    bullets = [when_line] if when_line else None
    html_body = render_branded_email(
        badge_text=space_name[:26],
        accent_theme="indigo",
        heading=f"New {post_subtype_label}: {post_title}",
        greeting=f"Hello {recipient_username},",
        intro_paragraphs=[
            f"@{author_username} posted a new {post_subtype_label} in \"{space_name}\":",
        ],
        quote_block=snippet,
        quote_caption=f"Posted in 👥 {space_name}",
        bullet_items=bullets,
        cta_label="View Full Post ↗",
        cta_url=post_url,
        base_url=clean_base,
        unsubscribe_url=unsubscribe_url,
        category_label="Space Updates",
    )
    return {
        "template_key": "space_announcement",
        "category": "space_updates",
        "subject": subject,
        "text_body": text_body,
        "html_body": html_body,
    }


def build_space_chat_email(
    recipient_username: str,
    sender_username: str,
    space_id: int,
    space_name: str,
    message_text: str,
    mode: str = "mention",
    unsubscribe_url: str = "",
    base_url: str = "http://localhost:8080",
) -> dict:
    """
    Renders Space Chat Board email notifications for the hybrid chat model:
      - mode='mention'   -> Direct @username mention (category='chat_mentions')
      - mode='broadcast' -> Space member checked '📢 Also email Space members' (category='chat_mentions')
      - mode='activity'  -> Opt-in passive chat ping with 6h cooldown (category='chat_activity')
    """
    clean_base = (base_url or "http://localhost:8080").rstrip("/")
    chat_url = f"{clean_base}/#/group/{space_id}"
    snippet = (message_text or "")[:280] + ("..." if len(message_text or "") > 280 else "")
    norm_mode = (mode or "mention").lower()

    if norm_mode == "broadcast":
        t_key = "space_chat_broadcast"
        cat = "chat_mentions"
        cat_label = "Chat @Mentions & Broadcasts"
        badge = "Space Chat Broadcast"
        theme = "teal"
        subject = f"📢 Chat Broadcast in \"{space_name}\" from @{sender_username}"
        heading = f"Broadcast in \"{space_name}\" Chat Board"
        intro = [
            f"@{sender_username} shared a broadcast message with members of \"{space_name}\" on GoodDeeds.space:",
        ]
        cta_label = f"Open \"{space_name}\" Chat Board ↗"
        sec_note = ""
    elif norm_mode == "activity":
        t_key = "space_chat_activity"
        cat = "chat_activity"
        cat_label = "All Space Chat Activity"
        badge = "Space Chat Activity"
        theme = "indigo"
        subject = f"💬 New chat conversation in \"{space_name}\""
        heading = f"New Chat Activity in \"{space_name}\""
        intro = [
            f"@{sender_username} posted a new message on the \"{space_name}\" Chat Board:",
        ]
        cta_label = "Join the Conversation ↗"
        sec_note = "To keep your inbox calm, passive Chat Board alerts are sent at most once every 6 hours per Space."
    else:
        t_key = "space_chat_mention"
        cat = "chat_mentions"
        cat_label = "Chat @Mentions & Broadcasts"
        badge = "Chat @Mention"
        theme = "indigo"
        subject = f"💬 @{sender_username} mentioned you in \"{space_name}\" Chat Board"
        heading = f"@{sender_username} mentioned you in \"{space_name}\""
        intro = [
            f"@{sender_username} tagged you on the \"{space_name}\" Space Chat Board:",
        ]
        cta_label = f"Reply in \"{space_name}\" Chat Board →"
        sec_note = ""

    text_body = (
        f"Hello {recipient_username},\n\n"
        f"{intro[0]}\n\n"
        f"\"{snippet}\"\n\n"
        f"Open the Space Chat Board:\n{chat_url}"
        + (f"\n\n({sec_note})" if sec_note else "")
    )
    html_body = render_branded_email(
        badge_text=badge,
        accent_theme=theme,
        heading=heading,
        greeting=f"Hello {recipient_username},",
        intro_paragraphs=intro,
        quote_block=f"\"{snippet}\"",
        quote_caption=f"— @{sender_username} in 👥 {space_name}",
        cta_label=cta_label,
        cta_url=chat_url,
        secondary_note=sec_note,
        base_url=clean_base,
        unsubscribe_url=unsubscribe_url,
        category_label=cat_label,
    )
    return {
        "template_key": t_key,
        "category": cat,
        "subject": subject,
        "text_body": text_body,
        "html_body": html_body,
    }


def build_weekly_digest_email(
    username: str,
    joined_space_names: list,
    highlight_lines: list,
    unsubscribe_url: str = "",
    base_url: str = "http://localhost:8080",
) -> dict:
    clean_base = (base_url or "http://localhost:8080").rstrip("/")
    feed_url = f"{clean_base}/#/feed"
    spaces_str = ", ".join(joined_space_names[:4]) if joined_space_names else "All Open Community Spaces"
    items = highlight_lines or ["🌟 Explore this week's new Kudos, Community Events, and Mutual Aid Resources on GoodDeeds.space!"]
    subject = f"☀️ Your Weekly GoodDeeds.space Community Digest"
    bullets_txt = "\n".join(f"  • {line}" for line in items[:6])
    text_body = (
        f"Hello {username},\n\n"
        f"Here is your weekly snapshot of kindness, upcoming events, and resources from {spaces_str}:\n\n"
        f"{bullets_txt}\n\n"
        f"Explore all updates or search in chat:\n{feed_url}"
    )
    html_body = render_branded_email(
        badge_text="Weekly Digest",
        accent_theme="amber",
        heading="Your Weekly Community Highlights",
        greeting=f"Hello {username},",
        intro_paragraphs=[
            f"Here's what neighbors and Space members shared recently across {spaces_str}:",
        ],
        bullet_items=items[:6],
        cta_label="Open My Community Feed ↗",
        cta_url=feed_url,
        base_url=clean_base,
        unsubscribe_url=unsubscribe_url,
        category_label="Weekly Digest",
    )
    return {
        "template_key": "weekly_digest",
        "category": "digest",
        "subject": subject,
        "text_body": text_body,
        "html_body": html_body,
    }


# ==============================================================================
# 4. SPACE GOVERNANCE & ADMINISTRATION TEMPLATES
# ==============================================================================

def build_space_role_updated_email(
    username: str,
    group_id: int,
    group_name: str,
    is_promoted: bool,
    actor_username: str,
    base_url: str = "http://localhost:8080",
) -> dict:
    clean_base = (base_url or "http://localhost:8080").rstrip("/")
    space_url = f"{clean_base}/#/group/{group_id}"
    if is_promoted:
        subject = f"🛡️ You are now a Space Admin for \"{group_name}\""
        intro = [
            f"@{actor_username} promoted you to Space Admin for \"{group_name}\" on GoodDeeds.space.",
            "As a Space Admin, you can now:",
        ]
        bullets = [
            "Edit Space description, categories, and community details.",
            "Curate verified Community Resources and schedule Space Events.",
            "Invite members in bulk and help keep Space conversations welcoming.",
        ]
    else:
        subject = f"ℹ️ Space Admin role updated for \"{group_name}\""
        intro = [
            f"@{actor_username} updated your role in \"{group_name}\" from Space Admin to Space Member.",
            "You remain a full member of the Space and can continue sharing Posts, Events, Resources, and Kudos.",
        ]
        bullets = None

    text_body = (
        f"Hello {username},\n\n"
        + "\n".join(intro)
        + ("\n" + "\n".join(f"  • {b}" for b in bullets) if bullets else "")
        + f"\n\nVisit \"{group_name}\":\n{space_url}"
    )
    html_body = render_branded_email(
        badge_text="Space Governance",
        accent_theme="teal" if is_promoted else "slate",
        heading=subject.replace("🛡️ ", "").replace("ℹ️ ", ""),
        greeting=f"Hello {username},",
        intro_paragraphs=intro,
        bullet_items=bullets,
        cta_label=f"Open \"{group_name}\" ↗",
        cta_url=space_url,
        base_url=clean_base,
    )
    return {
        "template_key": "space_role_updated",
        "category": "transactional",
        "subject": subject,
        "text_body": text_body,
        "html_body": html_body,
    }


def build_space_member_removed_email(
    username: str,
    group_name: str,
    is_banned: bool,
    reason: str = "",
    base_url: str = "http://localhost:8080",
) -> dict:
    clean_base = (base_url or "http://localhost:8080").rstrip("/")
    action_word = "removed and restricted from re-joining" if is_banned else "removed from"
    clean_reason = reason or "Space moderation decision"
    subject = f"Notice regarding your membership in \"{group_name}\""
    text_body = (
        f"Hello {username},\n\n"
        f"A Space Administrator has {action_word} the Space \"{group_name}\" on GoodDeeds.space.\n\n"
        f"Reason noted: {clean_reason}\n\n"
        f"If you believe this action was taken in error, you may reach out to Customer Service after signing in at {clean_base}/#/feed."
    )
    html_body = render_branded_email(
        badge_text="Space Notice",
        accent_theme="slate",
        heading=f"Update on \"{group_name}\" Membership",
        greeting=f"Hello {username},",
        intro_paragraphs=[
            f"A Space Administrator has {action_word} the Community Space \"{group_name}\".",
        ],
        quote_block=f"Reason: {clean_reason}",
        cta_label="Browse Other Open Spaces →",
        cta_url=f"{clean_base}/#/groups",
        secondary_note="Questions? Contact our volunteer support team anytime via the Customer Service link in the site footer.",
        base_url=clean_base,
    )
    return {
        "template_key": "space_member_removed",
        "category": "transactional",
        "subject": subject,
        "text_body": text_body,
        "html_body": html_body,
    }


# ==============================================================================
# 5. TRUST, SAFETY, FLAGGING & CUSTOMER SUPPORT TEMPLATES
# ==============================================================================

def build_support_confirmation_email(
    username: str,
    inquiry_id: int,
    subject_line: str,
    message: str,
    base_url: str = "http://localhost:8080",
) -> dict:
    clean_base = (base_url or "http://localhost:8080").rstrip("/")
    ref_code = f"#GD-{int(inquiry_id):04d}" if inquiry_id else "#GD-NEW"
    subject = f"Confirmation ({ref_code}): We received your inquiry '{subject_line}'"
    text_body = (
        f"Hello {username},\n\n"
        f"Thank you for contacting GoodDeeds.space Customer Service ({ref_code}). We have received your inquiry:\n\n"
        f"Subject: {subject_line}\n"
        f"\"{message}\"\n\n"
        f"Our support team will review your message and follow up at this email address shortly."
    )
    html_body = render_branded_email(
        badge_text=f"Support {ref_code}",
        accent_theme="amber",
        heading="We Received Your Support Request",
        greeting=f"Hello {username},",
        intro_paragraphs=[
            f"Thank you for reaching out to GoodDeeds.space! Your request has been logged under reference {ref_code}, and a member of our support team will reply to this email address shortly.",
        ],
        quote_block=message,
        quote_caption=f"Subject: {subject_line}",
        cta_label="Return to GoodDeeds.space ↗",
        cta_url=f"{clean_base}/#/feed",
        base_url=clean_base,
    )
    return {
        "template_key": "support_confirmation",
        "category": "transactional",
        "subject": subject,
        "text_body": text_body,
        "html_body": html_body,
    }


def build_support_admin_alert_email(
    username: str,
    user_email: str,
    inquiry_id: int,
    subject_line: str,
    message: str,
    submitted_at: str,
    base_url: str = "http://localhost:8080",
) -> dict:
    clean_base = (base_url or "http://localhost:8080").rstrip("/")
    ref_code = f"#GD-{int(inquiry_id):04d}" if inquiry_id else "#GD-NEW"
    subject = f"🚨 Support Alert ({ref_code}) from {username}: {subject_line}"
    text_body = (
        f"Reference: {ref_code}\n"
        f"User: {username} ({user_email})\n"
        f"Inquiry Subject: {subject_line}\n\n"
        f"Message:\n{message}\n\n"
        f"Submitted at: {submitted_at}\n"
        f"Tip: Hit 'Reply' to respond directly to {user_email}."
    )
    html_body = render_branded_email(
        badge_text=f"Ops Ticket {ref_code}",
        accent_theme="rose",
        heading=f"New Support Inquiry: {subject_line}",
        greeting="Hello Support Team,",
        intro_paragraphs=[
            f"Member @{username} ({user_email}) submitted a Customer Service request at {submitted_at}.",
            "You can reply directly to this email to respond to the user.",
        ],
        quote_block=message,
        quote_caption=f"From @{username} <{user_email}> • {ref_code}",
        cta_label="Open GoodDeeds.space ↗",
        cta_url=f"{clean_base}/#/feed",
        base_url=clean_base,
    )
    return {
        "template_key": "support_admin_alert",
        "category": "transactional",
        "subject": subject,
        "text_body": text_body,
        "html_body": html_body,
    }


def build_content_report_admin_alert_email(
    reporter_username: str,
    target_type: str,
    target_id: int,
    target_author_name: str,
    reason: str,
    notes: str,
    content_snippet: str,
    report_id: int,
    base_url: str = "http://localhost:8080",
) -> dict:
    clean_base = (base_url or "http://localhost:8080").rstrip("/")
    mod_url = f"{clean_base}/#/moderation"
    snippet = (content_snippet or "[No preview available]")[:260]
    subject = f"🚩 Moderation Report #{report_id}: {target_type} #{target_id} ({reason})"
    text_body = (
        f"A community member flagged content for review on GoodDeeds.space:\n\n"
        f"  • Report ID: #{report_id}\n"
        f"  • Flagged Item: {target_type} #{target_id} (by @{target_author_name or 'unknown'})\n"
        f"  • Reported By: @{reporter_username}\n"
        f"  • Reason: {reason}\n"
        + (f"  • Reporter Notes: {notes}\n" if notes else "")
        + f"\nContent Excerpt:\n\"{snippet}\"\n\n"
        f"Review & resolve in the Moderation Queue:\n{mod_url}"
    )
    bullets = [
        f"Report #{report_id} • Target: {target_type} #{target_id} (authored by @{target_author_name or 'unknown'})",
        f"Reported by: @{reporter_username}",
        f"Reason: {reason}" + (f" — {notes}" if notes else ""),
    ]
    html_body = render_branded_email(
        badge_text="Moderation Queue",
        accent_theme="rose",
        heading=f"Content Flagged: {target_type} #{target_id}",
        greeting="Hello Site Moderators,",
        intro_paragraphs=[
            "A member submitted a content safety report requiring review in the Moderation Queue:",
        ],
        bullet_items=bullets,
        quote_block=snippet,
        quote_caption="Excerpt of reported content",
        cta_label="Open Moderation Queue 🛡️",
        cta_url=mod_url,
        base_url=clean_base,
    )
    return {
        "template_key": "content_report_alert",
        "category": "transactional",
        "subject": subject,
        "text_body": text_body,
        "html_body": html_body,
    }


def build_moderation_action_email(
    username: str,
    action_type: str,
    target_type: str = "ACCOUNT",
    reason: str = "",
    base_url: str = "http://localhost:8080",
) -> dict:
    """
    action_type: 'CONTENT_REMOVED' | 'ACCOUNT_SUSPENDED' | 'ACCOUNT_RESTORED'
    """
    clean_base = (base_url or "http://localhost:8080").rstrip("/")
    act = (action_type or "").upper()
    if act == "ACCOUNT_RESTORED":
        subject = "✅ Your GoodDeeds.space account has been restored"
        heading = "Your Account Has Been Restored"
        accent = "teal"
        paragraphs = [
            "Good news — a Site Administrator has restored your GoodDeeds.space account.",
            "You may sign back in anytime and continue participating in Community Spaces in accordance with our Community Standards.",
        ]
        cta_label = "Sign In to GoodDeeds.space ↗"
        cta_url = f"{clean_base}/#/"
    elif act == "ACCOUNT_SUSPENDED":
        subject = "⚠️ Important Notice: Your GoodDeeds.space account has been suspended"
        heading = "Account Suspension Notice"
        accent = "rose"
        paragraphs = [
            "Following a Trust & Safety review under our Terms of Service and Community Standards, your GoodDeeds.space account has been suspended and active sessions have been signed out.",
            "If you believe this action was taken in error, please reply to this email or contact support@gooddeeds.space with your username to request an appeal review.",
        ]
        cta_label = ""
        cta_url = ""
    else:
        subject = f"ℹ️ Moderation Notice: Your {target_type.title()} was removed"
        heading = f"Your {target_type.title()} Was Removed"
        accent = "slate"
        paragraphs = [
            f"Following a community report review, a moderator removed your {target_type.lower()} because it did not align with GoodDeeds.space Community Standards.",
            "Please review our Community Standards to help keep GoodDeeds.space safe, constructive, and welcoming for everyone.",
        ]
        cta_label = "View GoodDeeds.space ↗"
        cta_url = f"{clean_base}/#/"

    quote_txt = f"Moderation note: {reason}" if reason else ""
    text_body = (
        f"Hello {username},\n\n"
        + "\n\n".join(paragraphs)
        + (f"\n\n{quote_txt}" if quote_txt else "")
    )
    html_body = render_branded_email(
        badge_text="Trust & Safety",
        accent_theme=accent,
        heading=heading,
        greeting=f"Hello {username},",
        intro_paragraphs=paragraphs,
        quote_block=quote_txt,
        cta_label=cta_label,
        cta_url=cta_url,
        base_url=clean_base,
    )
    return {
        "template_key": "moderation_action",
        "category": "transactional",
        "subject": subject,
        "text_body": text_body,
        "html_body": html_body,
    }


# ==============================================================================
# 6. LLC SUPPORTER & ORGANIZATION SUBSCRIPTION TEMPLATES (PHASE 2 READY)
# ==============================================================================

def build_supporter_receipt_email(
    supporter_name: str,
    amount_str: str,
    transaction_id: str,
    date_str: str,
    base_url: str = "http://localhost:8080",
) -> dict:
    clean_base = (base_url or "http://localhost:8080").rstrip("/")
    subject = f"💛 Thank you for supporting GoodDeeds.space! (Receipt {transaction_id})"
    disclosure = (
        "Disclosure: GoodDeeds.space is operated as a limited liability company (LLC). "
        "Voluntary supporter contributions help fund free open community infrastructure and are not tax-deductible as charitable contributions."
    )
    text_body = (
        f"Hello {supporter_name},\n\n"
        f"Thank you for your generous contribution of {amount_str} to help keep GoodDeeds.space free and open for communities!\n\n"
        f"Receipt Summary:\n"
        f"  • Amount: {amount_str}\n"
        f"  • Transaction ID: {transaction_id}\n"
        f"  • Date: {date_str}\n\n"
        f"{disclosure}\n\n"
        f"With gratitude,\nGoodDeeds.space"
    )
    html_body = render_branded_email(
        badge_text="Supporter Receipt",
        accent_theme="amber",
        heading="Thank You for Supporting GoodDeeds.space!",
        greeting=f"Hello {supporter_name},",
        intro_paragraphs=[
            f"Your contribution of {amount_str} directly supports hosting, search infrastructure, and free Community Spaces for neighbors and local nonprofits.",
        ],
        bullet_items=[
            f"Amount Paid: {amount_str}",
            f"Receipt / Transaction ID: {transaction_id}",
            f"Date: {date_str}",
        ],
        cta_label="Visit GoodDeeds.space ↗",
        cta_url=f"{clean_base}/#/",
        secondary_note=disclosure,
        base_url=clean_base,
    )
    return {
        "template_key": "supporter_receipt",
        "category": "transactional",
        "subject": subject,
        "text_body": text_body,
        "html_body": html_body,
    }


def build_org_subscription_onboarding_email(
    org_name: str,
    plan_name: str,
    admin_username: str,
    storage_quota_gb: int,
    base_url: str = "http://localhost:8080",
) -> dict:
    clean_base = (base_url or "http://localhost:8080").rstrip("/")
    subject = f"🚀 Welcome \"{org_name}\" to GoodDeeds.space {plan_name}!"
    bullets = [
        f"Expanded Space attachment & document storage ({storage_quota_gb} GB pooled allocation).",
        "Priority onboarding & dedicated support via support@gooddeeds.space.",
        "Bulk member & partner-agency email invitations plus full PDF/document search indexing.",
    ]
    text_body = (
        f"Hello {admin_username},\n\n"
        f"\"{org_name}\" is now active on the GoodDeeds.space {plan_name} plan!\n\n"
        f"Included capabilities:\n"
        + "\n".join(f"  • {b}" for b in bullets)
        + f"\n\nManage your Spaces anytime:\n{clean_base}/#/groups"
    )
    html_body = render_branded_email(
        badge_text=plan_name[:26],
        accent_theme="indigo",
        heading=f"{org_name} Is Live on {plan_name}!",
        greeting=f"Hello {admin_username},",
        intro_paragraphs=[
            f"Thank you for partnering with GoodDeeds.space! Your organization's {plan_name} subscription is active.",
        ],
        bullet_items=bullets,
        cta_label="Manage Organization Spaces ↗",
        cta_url=f"{clean_base}/#/groups",
        base_url=clean_base,
    )
    return {
        "template_key": "org_onboarding",
        "category": "transactional",
        "subject": subject,
        "text_body": text_body,
        "html_body": html_body,
    }


def get_all_template_previews(base_url: str = "http://localhost:8080") -> list:
    """Returns rendered sample previews of all 16+ GoodDeeds.space email templates for inspection."""
    clean_base = (base_url or "http://localhost:8080").rstrip("/")
    sample_unsub = build_unsubscribe_url(clean_base, "sample-preview-token", "all")
    samples = [
        ("1. Account & Security", "Welcome & Onboarding", build_welcome_email("Alex_Kindness", f"{clean_base}/#/verify-email?token=sample-verify-token", clean_base)),
        ("1. Account & Security", "Email Address Verification", build_email_verification_email("Alex_Kindness", f"{clean_base}/#/verify-email?token=sample-verify-token", clean_base)),
        ("1. Account & Security", "Forgot Password / Reset Link", build_password_reset_email("Alex_Kindness", f"{clean_base}/#/reset-password?token=sample-reset-token", 60, clean_base)),
        ("1. Account & Security", "Security Alert (Password / Passkey)", build_security_alert_email("Alex_Kindness", "New Passkey registered on Chrome (macOS)", clean_base)),
        ("2. Invitations & Growth", "Platform Invitation (Invite Friends)", build_site_invitation_email("Maya_Lin", "maya@gooddeeds.space", "Come check out the local wellness and mutual aid Spaces!", clean_base)),
        ("2. Invitations & Growth", "Community Space Invitation", build_space_invitation_email("Marcus_Oak", "marcus@gooddeeds.space", 2, "Youth STEM & Mentorship", "Would love your help mentoring Saturday robotics!", False, sample_unsub, clean_base)),
        ("2. Invitations & Growth", "Invite Accepted (to Inviter)", build_invite_accepted_email("Maya_Lin", "Alex_Kindness", 5, sample_unsub, clean_base)),
        ("3. Community Activity", "New Public Kudos Received", build_kudos_received_email("Arthur_74", "Maya_Lin", "Massive thank you for organizing the neighborhood tool library and helping three families this weekend!", 1, sample_unsub, clean_base)),
        ("3. Community Activity", "New Comment on Your Post / Kudos", build_comment_notification_email("Maya_Lin", "Elena_Wellness", "POST", "Weekend Community Pantry Restock", "Count me in! I can bring two crates of fresh produce at 9 AM.", 5, sample_unsub, clean_base)),
        ("3. Community Activity", "Space Event / Resource Announcement", build_space_announcement_email("Arthur_74", "Maya_Lin", 1, "NAMI", 6, "Peer Listening & Anxiety Support Workshop", "Community Event", "2026-11-15", "2:00 PM", "Open peer-led workshop sharing practical sleep and grounding strategies.", sample_unsub, clean_base)),
        ("3. Community Activity", "Space Chat Direct @Mention", build_space_chat_email("Elena_Wellness", "Maya_Lin", 1, "NAMI", "Hey @Elena_Wellness, can we share the peer-listening handout before Saturday's circle?", "mention", sample_unsub, clean_base)),
        ("3. Community Activity", "Space Chat Member Broadcast", build_space_chat_email("Arthur_74", "Marcus_Oak", 2, "Youth STEM & Mentorship", "Heads up everyone: Saturday robotics workshop is moving indoors to Library Room B due to rain!", "broadcast", sample_unsub, clean_base)),
        ("3. Community Activity", "Space Chat Opt-In Activity (6h Cooldown)", build_space_chat_email("Maya_Lin", "Elena_Wellness", 1, "NAMI", "Good morning neighbors! Just shared coffee & grounding notes in the chat.", "activity", sample_unsub, clean_base)),
        ("3. Community Activity", "Weekly Joined Spaces Digest", build_weekly_digest_email("Maya_Lin", ["NAMI", "Neighborhood Mutual Aid"], ["🌟 4 new Kudos celebrated across your Spaces", "📅 Community Event: Saturday Food Pantry Restock (Nov 14 • 10:00 AM)", "📚 New Resource: Free Legal & Estate Planning Clinic Guide"], sample_unsub, clean_base)),
        ("4. Space Governance", "Promoted to Space Admin", build_space_role_updated_email("Elena_Wellness", 1, "NAMI", True, "Maya_Lin", clean_base)),
        ("4. Space Governance", "Removed from Space Notice", build_space_member_removed_email("Sample_User", "Neighborhood Mutual Aid", False, "Repeated off-topic commercial promotions", clean_base)),
        ("5. Trust, Safety & Support", "Support Inquiry Confirmation (to User)", build_support_confirmation_email("Maya_Lin", 12, "Setting up a multi-chapter nonprofit Space", "Hi team, can multiple regional chapters share resources across Spaces?", clean_base)),
        ("5. Trust, Safety & Support", "Support Ticket Alert (to Support Team)", build_support_admin_alert_email("Maya_Lin", "maya@gooddeeds.space", 12, "Setting up a multi-chapter nonprofit Space", "Hi team, can multiple regional chapters share resources across Spaces?", "2026-10-31 07:30:00", clean_base)),
        ("5. Trust, Safety & Support", "Flagged Content Alert (to Moderators)", build_content_report_admin_alert_email("Elena_Wellness", "POST", 42, "Spam_Account", "Spam or misleading link", "Contains commercial solicitation link", "Click here for guaranteed crypto returns...", 7, clean_base)),
        ("5. Trust, Safety & Support", "Moderation Action / Suspension Notice", build_moderation_action_email("Sample_User", "CONTENT_REMOVED", "POST", "Unsolicited commercial promotion violates Community Standards.", clean_base)),
        ("6. LLC & Organization Tiers", "Supporter Contribution Receipt", build_supporter_receipt_email("Arthur Pendelton", "$25.00 USD", "GD-SUP-20261031-0091", "October 31, 2026", clean_base)),
        ("6. LLC & Organization Tiers", "Organization / Coalition Onboarding", build_org_subscription_onboarding_email("Bay Area Mutual Aid Coalition (4 Agencies)", "Coalition Network Plan", "Maya_Lin", 250, clean_base)),
    ]
    out = []
    for group_name, label, tpl in samples:
        out.append({
            "section": group_name,
            "title": label,
            "template_key": tpl["template_key"],
            "category": tpl["category"],
            "subject": tpl["subject"],
            "text_body": tpl["text_body"],
            "html_body": tpl["html_body"],
        })
    return out
