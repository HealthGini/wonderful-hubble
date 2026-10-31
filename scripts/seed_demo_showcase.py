#!/usr/bin/env python3
"""
Idempotent Demo Showcase Data Generator for GoodDeeds.space.

Populates `gooddeeds.db` directly via SQLite (without triggering live external
email deliveries) with rich, realistic personas, Community Spaces, formatted
Kudos, upcoming Events (Nov–Dec 2026), Community Resources with downloadable
Base64 text guides (indexed for deep attachment search), curated Space resources,
Space Chat Board threads (including @mentions and Broadcasts), emoji reactions,
and threaded comments.

Safe to run multiple times without creating duplicate records:
  python3 scripts/seed_demo_showcase.py
"""

import base64
import json
import os
import secrets
import sqlite3
import sys

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from database import get_db, hash_password, init_db, extract_resource_text


def make_text_attachment_data_uri(filename: str, text_content: str) -> str:
    """Encodes a plain-text guide as a named Base64 Data URI compatible with openAttachment()."""
    b64 = base64.b64encode(text_content.encode("utf-8")).decode("ascii")
    return f"data:text/plain;name={filename};base64,{b64}"


def seed_showcase():
    init_db()
    conn = get_db()
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    pw_hash = hash_password("password123")

    # 1. Ensure 4 additional realistic community members exist (8 total personas)
    demo_users = [
        (
            "priya@gooddeeds.space",
            "Dr_Priya_Nair",
            "555-0105",
            "https://images.unsplash.com/photo-1559839734-2b71ea197ec2?auto=format&fit=crop&w=200&q=80",
            "Community clinic physician & preventive health volunteer (39). Organizing free blood-pressure screenings, prescription navigation clinics, and caregiver support.",
        ),
        (
            "samir@gooddeeds.space",
            "Samir_Patel",
            "555-0106",
            "https://images.unsplash.com/photo-1506794778202-cad84cf45f1d?auto=format&fit=crop&w=200&q=80",
            "Full-stack engineer & career coach (31). Running free weekend Python workshops, mock interviews, and resume clinics for first-generation students and career switchers.",
        ),
        (
            "rosa@gooddeeds.space",
            "Rosa_Delgado",
            "555-0107",
            "https://images.unsplash.com/photo-1580489944761-15a19d654956?auto=format&fit=crop&w=200&q=80",
            "Bilingual family safety & housing advocate (45). Connecting survivors and families with emergency shelter, pro-bono legal aid clinics, and trauma-informed peer support.",
        ),
        (
            "chloe@gooddeeds.space",
            "Chloe_Green",
            "555-0108",
            "https://images.unsplash.com/photo-1544005313-94ddf0286df2?auto=format&fit=crop&w=200&q=80",
            "Urban arborist & zero-waste coordinator (26). Leading Saturday tree-plantings, community orchard harvests, and neighborhood repair cafes.",
        ),
    ]

    for email_addr, uname, phone, avatar, bio in demo_users:
        cur.execute("SELECT id FROM users WHERE email = ? OR username = ?", (email_addr, uname))
        if not cur.fetchone():
            cur.execute(
                """
                INSERT INTO users (email, username, password_hash, phone, avatar_url, bio, is_site_admin, email_verified, unsubscribe_token)
                VALUES (?, ?, ?, ?, ?, ?, 0, 1, ?)
                """,
                (email_addr, uname, pw_hash, phone, avatar, bio, secrets.token_urlsafe(24)),
            )

    user_id_by_name = {
        r["username"]: r["id"]
        for r in cur.execute("SELECT id, username FROM users").fetchall()
    }

    # 2. Enrich existing Spaces (Lifewire, Medical Help, NAMI) & add 2 unjoined Spaces for Maya_Lin
    #    so `#feed-group-select` showcases both "My Joined Spaces" and "Other Community Spaces"!
    space_specs = [
        (
            "Lifewire",
            "Confidential survivor advocacy, safe housing navigation, legal aid referrals, and healing-centered support groups for families rebuilding safety and independence.",
            ["Wellbeing & Care", "Community & Action"],
            "https://images.unsplash.com/photo-1516589178581-6cd7833ae3b2?auto=format&fit=crop&w=200&q=80",
        ),
        (
            "Medical Help",
            "Community health navigation connecting neighbors with free preventive screenings, sliding-scale dental and vision clinics, prescription assistance, and caregiver peer support.",
            ["Wellbeing & Care", "Community & Action"],
            "https://images.unsplash.com/photo-1505751172876-fa1923c5c528?auto=format&fit=crop&w=200&q=80",
        ),
        (
            "NAMI",
            "Peer-led mental health education, family support circles, crisis de-escalation resources, and stigma-free community wellness workshops.",
            ["Wellbeing & Care", "Inspiring Stories"],
            "https://images.unsplash.com/photo-1527137342181-19aab11a8ee8?auto=format&fit=crop&w=200&q=80",
        ),
        (
            "🌿 Urban Gardens & Climate Action",
            "Neighbors growing fresh produce for local food banks, planting shade trees, composting, and hosting monthly Fix-It Repair Cafes.",
            ["Community & Action", "Inspiring Stories"],
            "https://images.unsplash.com/photo-1466692476868-aef1dfb1e735?auto=format&fit=crop&w=200&q=80",
        ),
        (
            "💼 Career Launchpad & Tech Mentorship",
            "Practitioners volunteering resume reviews, mock interviews, digital literacy classes, and coding mentorship for job seekers and students.",
            ["Skills & Learning", "Community & Action"],
            "https://images.unsplash.com/photo-1522071820081-009f0129c71c?auto=format&fit=crop&w=200&q=80",
        ),
    ]

    for s_name, s_desc, s_themes, s_icon in space_specs:
        row = cur.execute("SELECT id, description, icon_url FROM groups WHERE name = ?", (s_name,)).fetchone()
        if row:
            if not (row["description"] or "").strip() or len((row["description"] or "").strip()) < 30:
                cur.execute(
                    "UPDATE groups SET description = ?, themes = ?, icon_url = COALESCE(NULLIF(icon_url, ''), ?) WHERE id = ?",
                    (s_desc, json.dumps(s_themes), s_icon, row["id"]),
                )
        else:
            cur.execute(
                "INSERT INTO groups (name, description, themes, icon_url) VALUES (?, ?, ?, ?)",
                (s_name, s_desc, json.dumps(s_themes), s_icon),
            )

    group_id_by_name = {
        r["name"]: r["id"]
        for r in cur.execute("SELECT id, name FROM groups").fetchall()
    }

    def gid(partial_name: str) -> int:
        for full_name, g_id in group_id_by_name.items():
            if partial_name.lower() in full_name.lower():
                return g_id
        raise KeyError(f"Group matching {partial_name!r} not found")

    # 3. Add Space memberships (Note: Maya_Lin stays out of Urban Gardens & Career Launchpad
    #    so she can demo "Other Community Spaces" discovery & live Join Space!)
    memberships = [
        # Mental Health & Peer Listening
        (gid("Mental Health"), "Dr_Priya_Nair", 0),
        (gid("Mental Health"), "Rosa_Delgado", 0),
        # Education, Tutoring & Skill Share
        (gid("Education"), "Samir_Patel", 1),
        (gid("Education"), "Elena_Wellness", 0),
        # Community Action & Mutual Aid
        (gid("Mutual Aid"), "Rosa_Delgado", 0),
        (gid("Mutual Aid"), "Chloe_Green", 0),
        (gid("Mutual Aid"), "Dr_Priya_Nair", 0),
        # Lifewire
        (gid("Lifewire"), "Rosa_Delgado", 1),
        (gid("Lifewire"), "Elena_Wellness", 0),
        (gid("Lifewire"), "Dr_Priya_Nair", 0),
        # Medical Help
        (gid("Medical Help"), "Dr_Priya_Nair", 1),
        (gid("Medical Help"), "Elena_Wellness", 0),
        (gid("Medical Help"), "Arthur_74", 0),
        (gid("Medical Help"), "Marcus_Vance", 0),
        # NAMI
        (gid("NAMI"), "Elena_Wellness", 1),
        (gid("NAMI"), "Arthur_74", 0),
        (gid("NAMI"), "Rosa_Delgado", 0),
        (gid("NAMI"), "Samir_Patel", 0),
        # Urban Gardens & Climate Action (Other Community Space for Maya_Lin!)
        (gid("Urban Gardens"), "Chloe_Green", 1),
        (gid("Urban Gardens"), "Marcus_Vance", 0),
        (gid("Urban Gardens"), "Arthur_74", 0),
        (gid("Urban Gardens"), "Dr_Priya_Nair", 0),
        # Career Launchpad & Tech Mentorship (Other Community Space for Maya_Lin!)
        (gid("Career Launchpad"), "Samir_Patel", 1),
        (gid("Career Launchpad"), "Elena_Wellness", 0),
        (gid("Career Launchpad"), "Rosa_Delgado", 0),
        (gid("Career Launchpad"), "Marcus_Vance", 0),
    ]
    for g_id, uname, is_adm in memberships:
        uid = user_id_by_name[uname]
        cur.execute(
            "INSERT OR IGNORE INTO group_members (group_id, user_id, is_admin) VALUES (?, ?, ?)",
            (g_id, uid, is_adm),
        )

    # 4. Prepare downloadable Base64 guide attachments (indexed in extracted_text!)
    att_nami_breathing = make_text_attachment_data_uri(
        "NAMI_Box_Breathing_478_Protocol.txt",
        "NAMI PEER WELLNESS POCKET CARD — 4-7-8 VAGAL NERVE RESET & GROUNDING\n"
        "=====================================================================\n"
        "1. 4-7-8 Vagal Nerve Reset: Inhale quietly through the nose for 4 seconds,\n"
        "   hold gently for 7 seconds, and exhale audibly for 8 seconds.\n"
        "2. 5-4-3-2-1 Sensory Grounding: Name 5 things you see, 4 you can touch,\n"
        "   3 you hear, 2 you smell, and 1 positive intention for today.\n"
        "3. Immediate 24/7 Confidential Support: Call or text 988 (988 Suicide & Crisis Lifeline)\n"
        "   or text HOME to 741741.\n",
    )

    att_rx_directory = make_text_attachment_data_uri(
        "Sliding_Scale_Insulin_and_Rx_Directory.txt",
        "COMMUNITY MEDICAL HELP — SLIDING-SCALE CLINIC & PRESCRIPTION ASSISTANCE GUIDE\n"
        "=============================================================================\n"
        "• Harborview Free Saturday Pharmacy & Blood Pressure Screening: Saturdays 9 AM - 1 PM\n"
        "  (No insurance required; bilingual Spanish, Mandarin, and Hindi navigators on site).\n"
        "• NeedyMeds Copay Assistance & Emergency Insulin Voucher Hotline: (800) 503-6897.\n"
        "• Senior Mobile Dental & Vision Van: First Tuesday monthly at Oakwood Senior Center.\n",
    )

    att_lifewire_safety = make_text_attachment_data_uri(
        "Lifewire_Safety_Planning_Checklist.txt",
        "LIFEWIRE CONFIDENTIAL SAFETY PLANNING & EMERGENCY HOUSING CHECKLIST\n"
        "====================================================================\n"
        "• Codeword Go-Bag Checklist: Keep copies of IDs, birth certificates, lease papers,\n"
        "  essential medications, and spare keys with a trusted neighbor or advocate.\n"
        "• Confidential Court Advocacy & Pro-Bono Family Law Clinic: Walk-ins Thursdays 1-5 PM.\n"
        "• 24-Hour Bilingual Safe Shelter & Transitional Housing Helpline: 1-800-827-8840.\n",
    )

    att_star_worksheet = make_text_attachment_data_uri(
        "STAR_Behavioral_Interview_Worksheet.txt",
        "CAREER LAUNCHPAD — SITUATION TASK ACTION RESULT RUBRIC & RESUME CHECKLIST\n"
        "=========================================================================\n"
        "• Situation Task Action Result Rubric: Frame every project story around measurable\n"
        "  impact, collaboration, and lessons learned.\n"
        "• Free Laptop Loaner & Wi-Fi Hotspot Program available via Central Public Library.\n"
        "• Weekly Python, SQL & Data Literacy Study Hall: Wednesdays 6:30 PM on Zoom.\n",
    )

    att_winter_coat = make_text_attachment_data_uri(
        "Winter_Coat_and_Blanket_Dropoff_Locations.txt",
        "WINTER WARMTH MUTUAL AID — DROP-OFF BINS & DISTRIBUTION HOURS\n"
        "==============================================================\n"
        "• Oakwood Fire Station Bin #3 (Open daily 8 AM - 8 PM): Clean winter coats, waterproof\n"
        "  gloves, children's boots, and new thermal socks.\n"
        "• Central Library Lobby Bin #1: Sleeping bags and fleece blankets.\n"
        "• Direct Family Pickup: Sundays 11 AM - 3 PM at Oakwood Community Gym (no ID needed).\n",
    )

    # 5. SyntheticRich Kudos (with Markdown bold, italics, bullet lists, links, and blockquotes!)
    kudos_entries = [
        {
            "author": "Maya_Lin",
            "recipient": "Dr_Priya_Nair",
            "content": (
                "Huge gratitude to **Dr. Priya Nair** for staying two extra hours at our Saturday blood-pressure and diabetes screening clinic!\n"
                "- Helped **19 uninsured neighbors** navigate sliding-scale prescription refills\n"
                "- Translated discharge instructions clearly for elderly patients and caregivers\n"
                "> Compassionate healthcare access changes lives!"
            ),
            "groups": [gid("Medical Help"), gid("Mutual Aid")],
            "created_at": "2026-10-30 16:40:00",
            "reactions": [("Elena_Wellness", "❤️"), ("Marcus_Vance", "👏"), ("Arthur_74", "🌟"), ("Rosa_Delgado", "🤗")],
            "comments": [
                ("Dr_Priya_Nair", "Thank you Maya! Seeing our neighbors leave with affordable medications and peace of mind makes every Saturday worth it."),
                ("Arthur_74", "Dr. Nair took 20 minutes to explain my blood-pressure log—truly a gem in our community!"),
            ],
        },
        {
            "author": "Elena_Wellness",
            "recipient": "Rosa_Delgado",
            "content": (
                "Heartfelt Kudos to **Rosa Delgado** for coordinating emergency transitional housing and *bilingual trauma-informed peer support* for three families this week.\n"
                "- Connected parents with pro-bono legal aid and school enrollment stability\n"
                "- Prepared welcome grocery baskets with warm winter bedding\n"
                "> Thank you for making Lifewire a beacon of safety and dignity!"
            ),
            "groups": [gid("Lifewire"), gid("Mental Health")],
            "created_at": "2026-10-29 19:15:00",
            "reactions": [("Maya_Lin", "❤️"), ("Dr_Priya_Nair", "🌟"), ("Marcus_Vance", "👏"), ("Chloe_Green", "🤗")],
            "comments": [
                ("Rosa_Delgado", "It takes a whole village—thank you @Elena_Wellness and everyone who donated grocery cards!"),
            ],
        },
        {
            "author": "Arthur_74",
            "recipient": "Samir_Patel",
            "content": (
                "Standing ovation for **Samir Patel**! Not only did he mentor six first-generation college students through mock coding interviews, he also ran a *Senior Digital Fraud & Smartphone Safety* table at our center.\n"
                "- Helped 14 retirees set up password managers and passkeys\n"
                "- Shared his [Open Career Mentorship Repo](https://gooddeeds.space/#/groups) with everyone"
            ),
            "groups": [gid("Education"), gid("Career Launchpad")],
            "created_at": "2026-10-28 14:20:00",
            "reactions": [("Maya_Lin", "🎉"), ("Elena_Wellness", "👏"), ("Marcus_Vance", "👍"), ("Dr_Priya_Nair", "🌟")],
            "comments": [
                ("Samir_Patel", "Learning goes both ways, Arthur—your storytelling tips upgraded everyone's interview confidence!"),
            ],
        },
        {
            "author": "Marcus_Vance",
            "recipient": "Chloe_Green",
            "content": (
                "Big shoutout to **Chloe Green** for leading 32 volunteers in harvesting **480 lbs of fresh kale, tomatoes, and squash** from our neighborhood garden plots directly for the weekend food pantry!\n"
                "> Zero waste, fresh nutrition, and neighbors working shoulder to shoulder."
            ),
            "groups": [gid("Urban Gardens"), gid("Mutual Aid")],
            "created_at": "2026-10-27 17:50:00",
            "reactions": [("Maya_Lin", "🌟"), ("Arthur_74", "👏"), ("Rosa_Delgado", "❤️"), ("Dr_Priya_Nair", "🎉")],
            "comments": [
                ("Chloe_Green", "Next harvest day is November 8—bring gloves and reusable crates!"),
            ],
        },
        {
            "author": "Rosa_Delgado",
            "recipient": "Elena_Wellness",
            "content": (
                "Deep appreciation for **Elena Wellness** and our **NAMI** facilitators for hosting Tuesday evening caregiver burnout & grief-support circles.\n"
                "- Created a judgment-free room where caregivers can exhale and feel heard\n"
                "- Shared practical *box-breathing* routines we now practice daily"
            ),
            "groups": [gid("NAMI"), gid("Mental Health")],
            "created_at": "2026-10-26 20:05:00",
            "reactions": [("Maya_Lin", "❤️"), ("Arthur_74", "🤗"), ("Dr_Priya_Nair", "🌟")],
            "comments": [],
        },
        {
            "author": "Samir_Patel",
            "recipient": "Maya_Lin",
            "content": (
                "Massive Kudos to **Maya Lin** for pairing 12 high school girls with women engineers for our robotics & STEM scholarship clinic!\n"
                "- Reviewed 12 college financial-aid essays line by line\n"
                "- Donated 5 Raspberry Pi starter kits so students can keep building at home\n"
                "> Closing the opportunity gap one Saturday at a time!"
            ),
            "groups": [gid("Education"), gid("Career Launchpad")],
            "created_at": "2026-10-25 15:30:00",
            "reactions": [("Marcus_Vance", "🎉"), ("Elena_Wellness", "❤️"), ("Arthur_74", "🌟"), ("Chloe_Green", "👏"), ("Dr_Priya_Nair", "👍")],
            "comments": [
                ("Maya_Lin", "Watching their robot prototypes cross the finish line was the highlight of my month!"),
            ],
        },
        {
            "author": "Dr_Priya_Nair",
            "recipient": "Arthur_74",
            "content": (
                "Warmest Kudos to **Arthur** for organizing daily check-in phone buddies and hospital ride-shares for homebound seniors recovering from surgery!\n"
                "- Coordinated **24 volunteer rides** to physical therapy appointments\n"
                "- Made sure nobody in our senior pilot spent recovery week alone"
            ),
            "groups": [gid("Medical Help"), gid("Mutual Aid")],
            "created_at": "2026-10-24 11:10:00",
            "reactions": [("Maya_Lin", "❤️"), ("Elena_Wellness", "🤗"), ("Rosa_Delgado", "🌟"), ("Marcus_Vance", "👏")],
            "comments": [],
        },
    ]

    for kd in kudos_entries:
        a_id = user_id_by_name[kd["author"]]
        r_id = user_id_by_name[kd["recipient"]]
        exists = cur.execute(
            "SELECT id FROM feed_items WHERE item_type = 'KUDOS' AND author_id = ? AND recipient_id = ? AND substr(content, 1, 50) = ?",
            (a_id, r_id, kd["content"][:50]),
        ).fetchone()
        if exists:
            continue
        cur.execute(
            """
            INSERT INTO feed_items (item_type, author_id, recipient_id, title, content, post_subtype, created_at)
            VALUES ('KUDOS', ?, ?, NULL, ?, 'GENERAL', ?)
            """,
            (a_id, r_id, kd["content"], kd["created_at"]),
        )
        item_id = cur.lastrowid
        for g_id in kd["groups"]:
            cur.execute("INSERT OR IGNORE INTO item_groups (item_id, group_id) VALUES (?, ?)", (item_id, g_id))
        for r_uname, emoji in kd["reactions"]:
            cur.execute(
                "INSERT OR IGNORE INTO reactions (item_id, user_id, emoji) VALUES (?, ?, ?)",
                (item_id, user_id_by_name[r_uname], emoji),
            )
        for c_uname, c_text in kd["comments"]:
            cur.execute(
                "INSERT INTO comments (item_id, user_id, content) VALUES (?, ?, ?)",
                (item_id, user_id_by_name[c_uname], c_text),
            )

    # 6. Synthetic Multi-Format Posts (Events in Nov-Dec 2026, Resources with Base64 files, Stories)
    post_entries = [
        {
            "author": "Elena_Wellness",
            "title": "NAMI Family-to-Family Anxiety & Grounding Workshop + Printable Pocket Protocol",
            "content": (
                "Feeling overwhelmed by seasonal stress or supporting a loved one through panic episodes? Join our free **NAMI** peer-led workshop!\n"
                "- Practice calm de-escalation conversations and sensory grounding\n"
                "- Download our printable pocket protocol attached below for step-by-step breathing exercises\n"
                "> Open to all ages, caregivers, students, and neighbors—no registration fee."
            ),
            "theme": "Wellbeing & Care",
            "category": "Health & Wellness",
            "post_subtype": "EVENT,RESOURCE",
            "event_date": "2026-11-07",
            "event_time": "2:00 PM - 4:00 PM",
            "target_audience": "Adults, Youth (16+), Parents & Family Caregivers",
            "target_geography": "Bellevue, Seattle & Virtual Zoom",
            "contact_info": "Elena Wellness — elena@gooddeeds.space | (555) 010-3000",
            "attachments": [att_nami_breathing, "https://www.nami.org/support-education"],
            "groups": [gid("NAMI"), gid("Mental Health")],
            "created_at": "2026-10-31 09:30:00",
            "reactions": [("Maya_Lin", "❤️"), ("Rosa_Delgado", "🌟"), ("Arthur_74", "👏"), ("Dr_Priya_Nair", "🤗")],
            "comments": [
                ("Maya_Lin", "Just printed the pocket protocol card for my desk—thank you Elena!"),
                ("Samir_Patel", "Sharing this with our student mentorship cohort as finals season approaches."),
            ],
        },
        {
            "author": "Dr_Priya_Nair",
            "title": "Free Sliding-Scale Clinic, Prescription Navigation & Preventive Health Directory",
            "content": (
                "Navigating medical bills, prescription refills, or finding uninsured care shouldn't require a degree in healthcare administration. Our **Medical Help** volunteers compiled a verified local directory:\n"
                "- Free Saturday blood-pressure, A1C glucose, and flu/COVID clinics\n"
                "- Sliding-scale dental, vision, and prescription copay assistance programs\n"
                "- Multilingual patient navigators available every weekend"
            ),
            "theme": "Wellbeing & Care",
            "category": "Health & Wellness",
            "post_subtype": "RESOURCE",
            "event_date": None,
            "event_time": None,
            "target_audience": "Uninsured / Underinsured Neighbors, Seniors & Families",
            "target_geography": "King County, Greater Seattle & Eastside",
            "contact_info": "Dr. Priya Nair — priya@gooddeeds.space | (555) 010-5000",
            "attachments": [att_rx_directory, "https://findahealthcenter.hrsa.gov"],
            "groups": [gid("Medical Help")],
            "created_at": "2026-10-30 18:10:00",
            "reactions": [("Maya_Lin", "🌟"), ("Marcus_Vance", "❤️"), ("Arthur_74", "👍"), ("Rosa_Delgado", "👏")],
            "comments": [
                ("Rosa_Delgado", "This prescription voucher list already helped two Lifewire families this week!"),
            ],
        },
        {
            "author": "Rosa_Delgado",
            "title": "Lifewire Confidential Safety Planning, Emergency Housing & Pro-Bono Legal Aid Guide",
            "content": (
                "Everyone deserves a safe home and compassionate support without judgment. Our **Lifewire** advocacy team has published an updated resource packet covering:\n"
                "- Confidential 24/7 bilingual shelter & transitional housing intake\n"
                "- Thursday afternoon pro-bono family law & protection-order clinic\n"
                "- Practical safety planning checklist for neighbors supporting a friend in crisis"
            ),
            "theme": "Wellbeing & Care",
            "category": "Housing & Shelter",
            "post_subtype": "RESOURCE",
            "event_date": None,
            "event_time": None,
            "target_audience": "Survivors, Families Seeking Safe Housing & Community Allies",
            "target_geography": "Eastside, Bellevue, Redmond & King County",
            "contact_info": "Rosa Delgado — rosa@gooddeeds.space | 24/7 Helpline: 1-800-827-8840",
            "attachments": [att_lifewire_safety],
            "groups": [gid("Lifewire"), gid("Mutual Aid")],
            "created_at": "2026-10-30 11:25:00",
            "reactions": [("Elena_Wellness", "❤️"), ("Maya_Lin", "🤗"), ("Dr_Priya_Nair", "🌟"), ("Chloe_Green", "👏")],
            "comments": [],
        },
        {
            "author": "Marcus_Vance",
            "title": "Annual Winter Coat, Warm Blanket & Holiday Food Box Drive (Volunteers + Drop-Off Map)",
            "content": (
                "Temperatures are dropping fast! Join **Community Action & Mutual Aid** as we collect 500 winter coats, waterproof boots, and shelf-stable holiday meal kits for local families and unhoused neighbors.\n"
                "- **Sorting & Packing Shift:** Saturday, November 14 from 10:00 AM – 2:00 PM at Oakwood Community Gym\n"
                "- **Direct Family Pickup:** No ID or paperwork required—hot cider and kids' book corner included!\n"
                "- Check the attached drop-off bin directory for neighborhood collection spots"
            ),
            "theme": "Community & Action",
            "category": "Food & Mutual Aid",
            "post_subtype": "EVENT,RESOURCE",
            "event_date": "2026-11-14",
            "event_time": "10:00 AM - 2:00 PM",
            "target_audience": "All Ages, Families, Student Volunteers & Local Donors",
            "target_geography": "Oakwood District, Downtown & Metro Area",
            "contact_info": "Marcus Vance — marcus@gooddeeds.space | (555) 010-2000",
            "attachments": [att_winter_coat],
            "groups": [gid("Mutual Aid")],
            "created_at": "2026-10-29 14:45:00",
            "reactions": [("Maya_Lin", "❤️"), ("Chloe_Green", "🎉"), ("Arthur_74", "👏"), ("Dr_Priya_Nair", "🌟"), ("Samir_Patel", "👍")],
            "comments": [
                ("Chloe_Green", "Bringing 15 crates of winter squash and apples from the community orchard!"),
                ("Maya_Lin", "Just dropped off 8 kids' winter parkas at the Fire Station bin!"),
            ],
        },
        {
            "author": "Samir_Patel",
            "title": "Free Tech Resume Review, Mock Interview Clinic & Python Study Hall",
            "content": (
                "Laid off recently, returning to the workforce, or applying for your first internship? **Career Launchpad** mentors are hosting a hands-on career accelerator session!\n"
                "- **1-on-1 Resume & LinkedIn Tear-Downs** (25-minute slots with hiring managers)\n"
                "- **Mock Behavioral & Coding Interviews** using our structured worksheet attached below\n"
                "- Beginner-friendly Python & SQL automation track for non-technical career switchers"
            ),
            "theme": "Skills & Learning",
            "category": "Career & Job Skills",
            "post_subtype": "EVENT,RESOURCE",
            "event_date": "2026-11-18",
            "event_time": "6:00 PM - 8:30 PM",
            "target_audience": "Job Seekers, College Students, Career Switchers & Veterans",
            "target_geography": "Central Public Library Room 302 & Online (Zoom)",
            "contact_info": "Samir Patel — samir@gooddeeds.space | (555) 010-6000",
            "attachments": [att_star_worksheet],
            "groups": [gid("Career Launchpad"), gid("Education")],
            "created_at": "2026-10-28 17:00:00",
            "reactions": [("Maya_Lin", "🌟"), ("Arthur_74", "👏"), ("Rosa_Delgado", "❤️")],
            "comments": [
                ("Rosa_Delgado", "Sharing this with three moms in our transitional housing program who are re-entering accounting and admin roles!"),
            ],
        },
        {
            "author": "Dr_Priya_Nair",
            "title": "Community Blood Pressure, Diabetes A1C & Caregiver Wellness Fair",
            "content": (
                "Bring your parents, grandparents, and neighbors to our free walk-in **Medical Help** preventive health morning!\n"
                "- Free blood-pressure cuffs for seniors managing hypertension\n"
                "- Pharmacist 1-on-1 medication interaction checks (bring your pill bottles!)\n"
                "- Caregiver respite corner with warm tea and **NAMI** peer listeners"
            ),
            "theme": "Wellbeing & Care",
            "category": "Senior Support",
            "post_subtype": "EVENT",
            "event_date": "2026-11-21",
            "event_time": "9:30 AM - 1:00 PM",
            "target_audience": "Seniors, Adults & Family Caregivers",
            "target_geography": "Oakwood Senior Center (410 Maple Ave)",
            "contact_info": "Dr. Priya Nair — priya@gooddeeds.space",
            "attachments": [],
            "groups": [gid("Medical Help"), gid("NAMI")],
            "created_at": "2026-10-27 12:15:00",
            "reactions": [("Arthur_74", "❤️"), ("Elena_Wellness", "🌟"), ("Maya_Lin", "👏")],
            "comments": [],
        },
        {
            "author": "Chloe_Green",
            "title": "Saturday Repair Cafe & Community Tree-Planting Day: Fix Lamps, Bikes & Electronics Free!",
            "content": (
                "Don't toss that wobbly chair, flat bicycle tire, or broken toaster! Bring it to our **Urban Gardens & Climate Action** Repair Cafe while our tree crew plants 35 native shade trees along Cedar Creek.\n"
                "- Volunteer electricians, tailors, and bike mechanics fixing items for free\n"
                "- Free cedar mulch, winter cover-crop seeds, and kids' Pollinator Craft Table"
            ),
            "theme": "Community & Action",
            "category": "Environment & Sustainability",
            "post_subtype": "EVENT",
            "event_date": "2026-11-28",
            "event_time": "10:00 AM - 3:00 PM",
            "target_audience": "Neighbors of All Ages, DIYers & Families",
            "target_geography": "Cedar Creek Park Pavilion",
            "contact_info": "Chloe Green — chloe@gooddeeds.space | (555) 010-8000",
            "attachments": [],
            "groups": [gid("Urban Gardens"), gid("Mutual Aid")],
            "created_at": "2026-10-26 10:40:00",
            "reactions": [("Marcus_Vance", "🎉"), ("Arthur_74", "👍"), ("Maya_Lin", "🌟")],
            "comments": [
                ("Arthur_74", "Bringing my 1978 desk lamp and a thermos of hot cocoa for the tree crew!"),
            ],
        },
        {
            "author": "Arthur_74",
            "title": "What Happened When 15 Teenagers Became Tech & Memoir Pen-Pals at Our Senior Center",
            "content": (
                "Six months ago, half the tables in our senior center dining room sat quiet after lunch, while local high schoolers needed community service hours. We paired 15 teenagers with 15 retirees over tea:\n"
                "- The students taught tablet video-calling, transit apps, and scam-spotting\n"
                "- Our retirees shared wartime family recipes, woodworking, and career resilience\n"
                "- Last Friday, **all 30 showed up even though the program officially ended**—because they had become genuine friends.\n"
                "> Loneliness melts away the moment two generations realize how much they still have to teach each other."
            ),
            "theme": "Inspiring Stories",
            "category": "Senior Support",
            "post_subtype": "GENERAL",
            "event_date": None,
            "event_time": None,
            "target_audience": "Youth Volunteers, Seniors & Educators",
            "target_geography": "Community-Wide",
            "contact_info": "Arthur (Senior Center Pilot Lead) — arthur@gooddeeds.space",
            "attachments": [],
            "groups": [gid("Education"), gid("Mental Health")],
            "created_at": "2026-10-29 08:50:00",
            "reactions": [("Maya_Lin", "❤️"), ("Elena_Wellness", "🤗"), ("Dr_Priya_Nair", "🌟"), ("Rosa_Delgado", "❤️"), ("Samir_Patel", "👏"), ("Chloe_Green", "🎉")],
            "comments": [
                ("Elena_Wellness", "This gave me chills, Arthur! Intergenerational connection is one of the strongest protective factors for mental health."),
                ("Maya_Lin", "Three of my robotics students asked how they can join the December cohort!"),
            ],
        },
        {
            "author": "Maya_Lin",
            "title": "December Intergenerational STEM, Robotics & College Financial Aid Showcase",
            "content": (
                "Celebrate what our student builders and volunteer mentors created this fall, followed by a bilingual **FAFSA & Scholarship Application Help Desk** for high school seniors and parents!\n"
                "- Live student robotics & community-app demos (1:00 PM)\n"
                "- 1-on-1 financial aid & scholarship essay review tables (2:15 PM)"
            ),
            "theme": "Skills & Learning",
            "category": "Youth & Mentorship",
            "post_subtype": "EVENT",
            "event_date": "2026-12-05",
            "event_time": "1:00 PM - 4:00 PM",
            "target_audience": "Middle & High School Students, Parents & STEM Mentors",
            "target_geography": "Jefferson High Commons & Livestream",
            "contact_info": "Maya Lin — maya@gooddeeds.space",
            "attachments": [],
            "groups": [gid("Education"), gid("Career Launchpad")],
            "created_at": "2026-10-25 13:00:00",
            "reactions": [("Samir_Patel", "🎉"), ("Arthur_74", "🌟"), ("Marcus_Vance", "👏")],
            "comments": [],
        },
    ]

    for po in post_entries:
        a_id = user_id_by_name[po["author"]]
        exists = cur.execute(
            "SELECT id FROM feed_items WHERE item_type = 'POST' AND title = ?",
            (po["title"],),
        ).fetchone()
        if exists:
            continue
        res_url_str = json.dumps(po["attachments"]) if po["attachments"] else ""
        ext_txt = extract_resource_text(res_url_str)
        cur.execute(
            """
            INSERT INTO feed_items (
                item_type, author_id, recipient_id, title, content, theme, resource_url,
                post_subtype, event_date, event_time, target_audience, target_geography,
                contact_info, category, extracted_text, created_at
            ) VALUES ('POST', ?, NULL, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                a_id,
                po["title"],
                po["content"],
                po["theme"],
                res_url_str,
                po["post_subtype"],
                po["event_date"],
                po["event_time"],
                po["target_audience"],
                po["target_geography"],
                po["contact_info"],
                po["category"],
                ext_txt,
                po["created_at"],
            ),
        )
        item_id = cur.lastrowid
        for g_id in po["groups"]:
            cur.execute("INSERT OR IGNORE INTO item_groups (item_id, group_id) VALUES (?, ?)", (item_id, g_id))
        for r_uname, emoji in po["reactions"]:
            cur.execute(
                "INSERT OR IGNORE INTO reactions (item_id, user_id, emoji) VALUES (?, ?, ?)",
                (item_id, user_id_by_name[r_uname], emoji),
            )
        for c_uname, c_text in po["comments"]:
            cur.execute(
                "INSERT INTO comments (item_id, user_id, content) VALUES (?, ?, ?)",
                (item_id, user_id_by_name[c_uname], c_text),
            )

    # 7. Curated Space Resources (`group_resources`) across Spaces & Monthly Spotlight
    curated_resources = [
        (gid("Lifewire"), "Lifewire 24/7 Safe Housing & Court Advocacy Guide", att_lifewire_safety, "FILE", "Wellbeing & Care", "Rosa_Delgado"),
        (gid("Medical Help"), "Free Saturday Clinic & Prescription Assistance Directory", att_rx_directory, "FILE", "Wellbeing & Care", "Dr_Priya_Nair"),
        (gid("NAMI"), "NAMI 4-7-8 Vagal Nerve Reset & 988 Crisis Pocket Card", att_nami_breathing, "FILE", "Wellbeing & Care", "Elena_Wellness"),
        (gid("Career Launchpad"), "STAR Behavioral Interview & Tech Resume Rubric", att_star_worksheet, "FILE", "Skills & Learning", "Samir_Patel"),
        (gid("Urban Gardens"), "Community Orchard Harvest & Repair Cafe Volunteer Guide", "https://gooddeeds.space/#/groups", "URL", "Community & Action", "Chloe_Green"),
        (gid("Mutual Aid"), "Winter Coat & Warm Blanket Drop-Off Locations Map", att_winter_coat, "FILE", "Community & Action", "Marcus_Vance"),
    ]
    for g_id, r_title, r_url, r_type, r_theme, added_uname in curated_resources:
        exists = cur.execute(
            "SELECT id FROM group_resources WHERE group_id = ? AND title = ?",
            (g_id, r_title),
        ).fetchone()
        if not exists:
            cur.execute(
                """
                INSERT INTO group_resources (group_id, title, url, resource_type, theme, added_by, extracted_text)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (g_id, r_title, r_url, r_type, r_theme, user_id_by_name[added_uname], extract_resource_text(r_url)),
            )

    # 8. Rich Space Chat Board threads (including @mentions and Broadcast announcements)
    chat_threads = [
        (gid("NAMI"), "Elena_Wellness", "📢 Reminder everyone: Our November 7 Anxiety & Grounding Workshop is open to family caregivers too—feel free to invite a neighbor!", 1),
        (gid("NAMI"), "Arthur_74", "Thanks @Elena_Wellness! I shared the 4-7-8 pocket protocol with two gentlemen in our senior walking club today.", 0),
        (gid("Medical Help"), "Dr_Priya_Nair", "📢 Saturday's Harborview Blood Pressure & Prescription Navigation table now has Spanish and Hindi interpreters on site from 9 AM to 1 PM!", 1),
        (gid("Medical Help"), "Marcus_Vance", "Awesome news @Dr_Priya_Nair—we'll include flyers in this weekend's mutual aid grocery boxes.", 0),
        (gid("Lifewire"), "Rosa_Delgado", "Thank you @Maya_Lin and @Elena_Wellness for helping restock the transitional housing welcome kits with kids' school supplies!", 0),
        (gid("Career Launchpad"), "Samir_Patel", "📢 Mock interview sign-up sheet for November 18 is live! We still have 4 mentor slots open for resume reviews.", 1),
        (gid("Urban Gardens"), "Chloe_Green", "📢 Bring dull kitchen knives, lamps, or kids' bikes to the November 28 Repair Cafe at Cedar Creek Pavilion!", 1),
    ]
    for g_id, uname, msg_txt, is_bcast in chat_threads:
        uid = user_id_by_name[uname]
        exists = cur.execute(
            "SELECT id FROM group_messages WHERE group_id = ? AND user_id = ? AND message = ?",
            (g_id, uid, msg_txt),
        ).fetchone()
        if not exists:
            cur.execute(
                "INSERT INTO group_messages (group_id, user_id, message, is_broadcast) VALUES (?, ?, ?, ?)",
                (g_id, uid, msg_txt, is_bcast),
            )

    conn.commit()

    stats = {
        "users": cur.execute("SELECT COUNT(*) FROM users").fetchone()[0],
        "spaces": cur.execute("SELECT COUNT(*) FROM groups").fetchone()[0],
        "kudos": cur.execute("SELECT COUNT(*) FROM feed_items WHERE item_type = 'KUDOS'").fetchone()[0],
        "posts": cur.execute("SELECT COUNT(*) FROM feed_items WHERE item_type = 'POST'").fetchone()[0],
        "resources": cur.execute("SELECT COUNT(*) FROM group_resources").fetchone()[0],
        "chat_messages": cur.execute("SELECT COUNT(*) FROM group_messages").fetchone()[0],
        "reactions": cur.execute("SELECT COUNT(*) FROM reactions").fetchone()[0],
        "comments": cur.execute("SELECT COUNT(*) FROM comments").fetchone()[0],
    }
    conn.close()
    print("✅ Showcase demo dataset ready in gooddeeds.db:", json.dumps(stats, indent=2))


if __name__ == "__main__":
    seed_showcase()
