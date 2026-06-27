"""
Database management for GoodDeeds.space.

This module handles SQLite database connections, schema initialization,
password hashing, and demo data seeding.
"""

import sqlite3
import hashlib
import json
import os

# Ensure DB is created next to this script by default unless DB_PATH is set
DEFAULT_DB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "gooddeeds.db")
DB_PATH = os.environ.get("DB_PATH", DEFAULT_DB)

def get_db():
    """
    Establishes a connection to the SQLite database.
    
    Sets the row factory to sqlite3.Row for dictionary-like access
    and enables foreign key support.
    
    Returns:
        sqlite3.Connection: The database connection object.
    """
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

def hash_password(password: str) -> str:
    """
    Hashes a plain text password using SHA-256.
    
    Args:
        password: The plain text password to hash.
        
    Returns:
        str: The hex digest of the hashed password.
    """
    return hashlib.sha256(password.encode("utf-8")).hexdigest()

def init_db():
    """
    Initializes the database schema.
    
    Creates all necessary tables if they do not exist.
    If the users table is empty after creation, it automatically
    triggers data seeding.
    """
    conn = get_db()
    cursor = conn.cursor()

    # 1. Users
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        email TEXT UNIQUE NOT NULL,
        username TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        phone TEXT,
        avatar_url TEXT,
        bio TEXT,
        is_site_admin INTEGER DEFAULT 0,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )
    """)
    try:
        cursor.execute("ALTER TABLE users ADD COLUMN is_site_admin INTEGER DEFAULT 0")
    except Exception:
        pass

    # 2. Sessions
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS sessions (
        token TEXT PRIMARY KEY,
        user_id INTEGER NOT NULL,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
    )
    """)

    # 3. Groups
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS groups (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT UNIQUE NOT NULL,
        description TEXT,
        themes TEXT,
        icon_url TEXT,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )
    """)

    # 4. Group Members
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS group_members (
        group_id INTEGER NOT NULL,
        user_id INTEGER NOT NULL,
        is_admin INTEGER DEFAULT 0,
        joined_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY (group_id, user_id),
        FOREIGN KEY (group_id) REFERENCES groups(id) ON DELETE CASCADE,
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
    )
    """)

    # 5. Group Resources
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS group_resources (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        group_id INTEGER NOT NULL,
        title TEXT NOT NULL,
        url TEXT NOT NULL,
        resource_type TEXT DEFAULT 'URL',
        theme TEXT DEFAULT 'Community Resources',
        added_by INTEGER,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (group_id) REFERENCES groups(id) ON DELETE CASCADE,
        FOREIGN KEY (added_by) REFERENCES users(id) ON DELETE SET NULL
    )
    """)

    # 6. Group Messages (Chat Board)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS group_messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        group_id INTEGER NOT NULL,
        user_id INTEGER NOT NULL,
        message TEXT NOT NULL,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (group_id) REFERENCES groups(id) ON DELETE CASCADE,
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
    )
    """)

    # 7. Unified Feed Items (Kudos & Posts)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS feed_items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        item_type TEXT NOT NULL, -- 'KUDOS' or 'POST'
        author_id INTEGER NOT NULL,
        recipient_id INTEGER, -- For KUDOS
        title TEXT, -- For POST
        content TEXT NOT NULL,
        theme TEXT, -- For POST
        resource_url TEXT, -- Link/PDF URL for POST
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (author_id) REFERENCES users(id) ON DELETE CASCADE,
        FOREIGN KEY (recipient_id) REFERENCES users(id) ON DELETE CASCADE
    )
    """)

    # 8. Item Groups (Tagging Kudos/Posts to Groups)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS item_groups (
        item_id INTEGER NOT NULL,
        group_id INTEGER NOT NULL,
        PRIMARY KEY (item_id, group_id),
        FOREIGN KEY (item_id) REFERENCES feed_items(id) ON DELETE CASCADE,
        FOREIGN KEY (group_id) REFERENCES groups(id) ON DELETE CASCADE
    )
    """)

    # 9. Reactions
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS reactions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        item_id INTEGER NOT NULL,
        user_id INTEGER NOT NULL,
        emoji TEXT NOT NULL,
        UNIQUE(item_id, user_id, emoji),
        FOREIGN KEY (item_id) REFERENCES feed_items(id) ON DELETE CASCADE,
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
    )
    """)

    # 10. Comments
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS comments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        item_id INTEGER NOT NULL,
        user_id INTEGER NOT NULL,
        content TEXT NOT NULL,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (item_id) REFERENCES feed_items(id) ON DELETE CASCADE,
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
    )
    """)

    # 11. Email Outbox (Simulated Email Log)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS email_outbox (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        recipient_email TEXT NOT NULL,
        subject TEXT NOT NULL,
        body TEXT NOT NULL,
        sent_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        status TEXT DEFAULT 'SENT'
    )
    """)

    # 12. Customer Service Inquiries
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS customer_service_inquiries (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        subject TEXT NOT NULL,
        message TEXT NOT NULL,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
    )
    """)

    # 13. Group Invitations
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS group_invitations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        group_id INTEGER NOT NULL,
        sender_id INTEGER NOT NULL,
        recipient_username TEXT NOT NULL,
        message TEXT,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        status TEXT DEFAULT 'PENDING',
        FOREIGN KEY (group_id) REFERENCES groups(id) ON DELETE CASCADE,
        FOREIGN KEY (sender_id) REFERENCES users(id) ON DELETE CASCADE
    )
    """)

    # Check if we need to seed demo data
    cursor.execute("SELECT COUNT(*) as count FROM users")
    if cursor.fetchone()["count"] == 0:
        seed_data(cursor)

    conn.commit()
    conn.close()

def seed_data(cursor):
    """
    Seeds the database with realistic demo data.
    
    Populates sample users, groups, memberships, resources, chat messages,
    feed items (posts/kudos), reactions, comments, and invitations.
    
    Args:
        cursor: sqlite3.Cursor object to execute inserts.
    """
    pw_hash = hash_password("password123")

    # Diverse Sample Users across age groups and backgrounds
    # Maya (user 1) is seeded as a site super admin (is_site_admin = 1)
    users = [
        ("maya@gooddeeds.space", "Maya_Lin", pw_hash, "555-0101", "https://images.unsplash.com/photo-1534528741775-53994a69daeb?auto=format&fit=crop&w=200&q=80", "Youth mentor & software engineer (28). Passionate about closing the STEM education gap and promoting community mental health wellness.", 1),
        ("marcus@gooddeeds.space", "Marcus_Vance", pw_hash, "555-0102", "https://images.unsplash.com/photo-1507003211169-0a1dd7228f2d?auto=format&fit=crop&w=200&q=80", "Neighborhood organizer and father of 3 (42). Organizing local weekend cleanups, community food pantries, and mutual aid networks.", 0),
        ("elena@gooddeeds.space", "Elena_Wellness", pw_hash, "555-0103", "https://images.unsplash.com/photo-1573496359142-b8d87734a5a2?auto=format&fit=crop&w=200&q=80", "Licensed mental health counselor (35). Hosting free weekly grounding circles and destigmatizing emotional support for all ages.", 0),
        ("arthur@gooddeeds.space", "Arthur_74", pw_hash, "", "https://images.unsplash.com/photo-1500648767791-00dcc994a43e?auto=format&fit=crop&w=200&q=80", "Retired history teacher (74) leading our senior center bootstrap pilot. Partnering with young volunteers for intergenerational friendship.", 0)
    ]
    cursor.executemany("INSERT INTO users (email, username, password_hash, phone, avatar_url, bio, is_site_admin) VALUES (?, ?, ?, ?, ?, ?, ?)", users)

    # Generic & Inclusive Sample Groups
    groups = [
        ("🌱 Mental Health & Peer Listening", "A safe, confidential space for emotional encouragement, stress reduction, and mental health wellness across all walks of life.", json.dumps(["Mental Health", "Community Resources"]), "https://images.unsplash.com/photo-1529156069898-49953e39b3ac?auto=format&fit=crop&w=200&q=80"),
        ("🎓 Education, Tutoring & Skill Share", "Connecting experienced professionals, students, and retirees for academic tutoring, career advice, and mutual skill exchange.", json.dumps(["Education", "Events"]), "https://images.unsplash.com/photo-1517486808906-6ca8b3f04846?auto=format&fit=crop&w=200&q=80"),
        ("🤝 Community Action & Mutual Aid", "Local mutual aid network organizing neighborhood cleanups, food pantries, senior center visits, and volunteer assistance.", json.dumps(["Community Services", "Inspiring Stories"]), "https://images.unsplash.com/photo-1593113598332-cd288d649433?auto=format&fit=crop&w=200&q=80")
    ]
    cursor.executemany("INSERT INTO groups (name, description, themes, icon_url) VALUES (?, ?, ?, ?)", groups)

    # Group Members (group_id, user_id, is_admin)
    members = [
        (1, 3, 1), # Elena admin of Group 1
        (1, 1, 0), # Maya member of Group 1
        (1, 2, 0), # Marcus member of Group 1
        (1, 4, 0), # Arthur member of Group 1
        (2, 1, 1), # Maya admin of Group 2
        (2, 4, 0), # Arthur member of Group 2
        (2, 2, 0), # Marcus member of Group 2
        (3, 2, 1), # Marcus admin of Group 3
        (3, 1, 0), # Maya member of Group 3
        (3, 3, 0), # Elena member of Group 3
        (3, 4, 0), # Arthur member of Group 3
    ]
    cursor.executemany("INSERT INTO group_members (group_id, user_id, is_admin) VALUES (?, ?, ?)", members)

    # Group Curated Resources
    resources = [
        (1, "Mental Health First Aid & Grounding Handbook", "https://example.com/grounding_guide.pdf", "PDF", "Mental Health", 3),
        (1, "Free Online Mindfulness & Audio Meditations", "https://example.com/mindfulness", "URL", "Mental Health", 3),
        (2, "Comprehensive Resume & Career Mentorship Guide", "https://example.com/resume_guide.pdf", "PDF", "Education", 1),
        (3, "Local Mutual Aid Network & Volunteer Map", "https://example.com/volunteer_map.pdf", "PDF", "Community Services", 2)
    ]
    cursor.executemany("INSERT INTO group_resources (group_id, title, url, resource_type, theme, added_by) VALUES (?, ?, ?, ?, ?, ?)", resources)

    # Group Chat Messages
    chat_msgs = [
        (1, 3, "Welcome everyone to our confidential listening space. Remember that asking for support is a courageous step toward becoming your best self."),
        (1, 1, "Thank you Elena! Your grounding audio guide helped me so much before my big presentation yesterday."),
        (2, 1, "Looking for a volunteer coding tutor for a motivated high school sophomore this Saturday!"),
        (2, 4, "I would love to help tutor in writing and history, Maya. Intergenerational learning is wonderful!"),
        (3, 2, "Reminder: Weekend neighborhood cleanup and food pantry restock starts tomorrow at 10 AM. All ages welcome!")
    ]
    cursor.executemany("INSERT INTO group_messages (group_id, user_id, message) VALUES (?, ?, ?)", chat_msgs)

    # Primary Feed Items (Kudos & Posts)
    items = [
        ("KUDOS", 1, 2, None, "Massive thank you to Marcus for organizing our neighborhood food pantry restock! Your dedication brings connection, positivity, and goodness to our block every single day.", None, None),
        ("POST", 3, None, "Promoting Goodness: Breaking the Cycle of Negativity", "Far too often we are inundated with news of division, stress, and hardship. It makes it easy to forget the intrinsic kindness inside every human being. By choosing to do one good deed today—whether listening to a friend, tutoring a student, or helping a neighbor—we ripple positivity outward. Let's promote goodness and help everyone become the best possible version of themselves.", "Mental Health", "https://example.com/kindness_guide.pdf"),
        ("KUDOS", 4, 3, None, "Heartfelt kudos to Elena for hosting free weekly mental health listening circles. Your empathy and practical grounding tips have helped people of all ages find peace and resilience!", None, None),
        ("POST", 1, None, "Free Online Tutoring & Mentorship Fair This Saturday", "Join us this Saturday at 2 PM for our intergenerational skill share! Whether you need academic tutoring, career advice, or want to volunteer your expertise across education and tech, there is a welcoming place for you.", "Events", "https://example.com/mentorship_fair.pdf"),
        ("POST", 2, None, "How Small Acts of Mutual Aid Transformed Our Neighborhood", "Last month, a few neighbors set up a shared tool library and community pantry. What started as a simple shelf has turned into daily collaboration between college students, busy parents, and retired neighbors. Promote goodness—one good deed at a time!", "Inspiring Stories", "")
    ]
    cursor.executemany("INSERT INTO feed_items (item_type, author_id, recipient_id, title, content, theme, resource_url) VALUES (?, ?, ?, ?, ?, ?, ?)", items)

    # Item Groups Tagging
    item_groups = [
        (1, 3), # Kudos 1 tagged to Group 3
        (2, 1), # Post 2 tagged to Group 1
        (3, 1), # Kudos 3 tagged to Group 1
        (4, 2), # Post 4 tagged to Group 2
        (5, 3)  # Post 5 tagged to Group 3
    ]
    cursor.executemany("INSERT INTO item_groups (item_id, group_id) VALUES (?, ?)", item_groups)

    # Reactions
    reactions = [
        (1, 3, "❤️"), (1, 4, "👏"), (1, 1, "🌟"),
        (2, 1, "❤️"), (2, 2, "❤️"), (2, 4, "🤗"), (2, 2, "🌟"),
        (3, 1, "👏"), (3, 2, "🎉"),
        (4, 3, "❤️"), (4, 4, "🌟"),
        (5, 1, "❤️"), (5, 3, "👏"), (5, 4, "🌟")
    ]
    cursor.executemany("INSERT INTO reactions (item_id, user_id, emoji) VALUES (?, ?, ?)", reactions)

    # Comments
    comments = [
        (1, 3, "Marcus truly embodies community leadership!"),
        (2, 1, "Beautiful reminder Elena. One good deed at a time really makes a difference."),
        (2, 4, "Wonderful wisdom. Glad to be part of this safe space."),
        (3, 2, "Elena's listening circles have been a blessing for my entire family."),
        (4, 4, "Count me in for Saturday! I will bring history books.")
    ]
    cursor.executemany("INSERT INTO comments (item_id, user_id, content) VALUES (?, ?, ?)", comments)

    # Email Outbox Seed
    emails = [
        ("marcus@gooddeeds.space", "🌟 You received new Kudos from Maya_Lin!", "Maya_Lin gave you public Kudos on gooddeeds.space:\n\n\"Massive thank you to Marcus for organizing our neighborhood food pantry restock!...\"\n\nView and celebrate your full Kudos here: /#/kudos/1"),
        ("elena@gooddeeds.space", "🌟 You received new Kudos from Arthur_74!", "Arthur_74 gave you public Kudos on gooddeeds.space:\n\n\"Heartfelt kudos to Elena for hosting free weekly mental health listening circles!...\"\n\nView and celebrate your full Kudos here: /#/kudos/3")
    ]
    cursor.executemany("INSERT INTO email_outbox (recipient_email, subject, body) VALUES (?, ?, ?)", emails)

    # Group Invitations Seed
    invites = [
        (1, 2, "Maya_Lin", "Join Marcus and our family in Mental Health & Peer Listening!"),
        (2, 3, "Maya_Lin", "Elena invited you to join Education, Tutoring & Skill Share!"),
        (3, 4, "Marcus_Vance", "Arthur invited you to join Community Action & Mutual Aid!")
    ]
    cursor.executemany("INSERT INTO group_invitations (group_id, sender_id, recipient_username, message) VALUES (?, ?, ?, ?)", invites)

if __name__ == "__main__":
    init_db()
    print(f"Database initialized successfully at {DB_PATH}.")
