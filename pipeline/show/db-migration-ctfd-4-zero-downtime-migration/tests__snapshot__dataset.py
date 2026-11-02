"""Production snapshot of the CTFd database of a CTF platform that has hosted events since mid 2024 (teams mode).

~1.1M rows. Legacy data carries the quirks MIGRATION_SPEC.md describes: free-text countries from the 2024 import,
e-mail addresses that differ only by case or surrounding blanks, proxy chains / ports / junk in recorded IPs, untyped
pre-2.0 submissions, string ids and dangling ids in challenge requirements, flag data spelled several ways, and unlocks
whose hint or solution was deleted. The hidden variant raises the rate of every such case (same classes)."""
import datetime

from dbm_data import Json, Table

START = datetime.datetime(2024, 6, 1)
END = datetime.datetime(2026, 9, 30, 23, 59, 59)
CATEGORIES = ["web", "crypto", "pwn", "reversing", "forensics", "misc", "osint", "hardware", "blockchain", "cloud"]
DOMAINS = ["example.org", "mail.example.com", "uni.example.edu", "corp.example.net", "students.example.ac.uk",
           "proton.example.ch", "ctf.example.io"]
COUNTRY_CODES = ["US", "DE", "FR", "GB", "IN", "CN", "BR", "CA", "JP", "KR", "RU", "PL", "NL", "SE", "IT", "ES", "AU",
                 "SG", "IL", "VN", "UA", "TR", "MX", "AR", "CH", "AT", "NO", "FI", "DK", "BE", "PT", "CZ", "RO", "GR",
                 "AX", "CI", "RE", "ST"]
COUNTRY_NAMES = {"US": "United States", "DE": "Germany", "FR": "France", "GB": "United Kingdom", "IN": "India",
                 "CN": "China", "BR": "Brazil", "CA": "Canada", "JP": "Japan", "KR": "South Korea", "PL": "Poland",
                 "NL": "Netherlands", "SE": "Sweden", "IT": "Italy", "ES": "Spain", "AU": "Australia", "SG": "Singapore",
                 "AX": "Åland Islands", "CI": "Côte d’Ivoire", "RE": "Réunion", "ST": "São Tomé & Príncipe"}
ALIASES = ["USA", "U.S.A.", "United States of America", "UK", "Great Britain", "England", "Deutschland",
           "Republic of Korea", "Holland", "Brasil", "Россия"]
JUNK_COUNTRIES = ["Narnia", "Earth", "N/A", "none", "Internet", "??"]


def v6(r):
    """A compressed IPv6 address as browsers and proxies report them (fits the 46-character column)."""
    return r.choice([f"2001:db8:{r.int(0, 65535):x}::{r.int(1, 65535):x}", f"2a02:{r.int(0, 65535):x}:{r.int(0, 65535):x}::1",
                     f"fd00::{r.int(0, 65535):x}:{r.int(0, 65535):x}", f"2600:{r.int(0, 4095):x}:{r.int(0, 65535):x}:{r.int(0, 65535):x}::"])


def n(ctx, count):
    return ctx.n(count)


def generate(ctx):
    hid = ctx.hidden
    edge = 2.0 if hid else 1.0
    N_USERS, N_TEAMS, N_CHAL = n(ctx, 40000), n(ctx, 8000), n(ctx, 420)
    N_SUBS, N_TRACK, N_UNLOCK = n(ctx, 600000), n(ctx, 250000), n(ctx, 60000)

    # ---- config, brackets, modules, audiences, pages --------------------------------------------------------------
    cfg = [("ctf_name", "Lighthouse CTF"), ("user_mode", "teams"), ("setup", "1"), ("ctf_theme", "core"),
           ("challenge_visibility", "private"), ("score_visibility", "public"), ("account_visibility", "public"),
           ("registration_visibility", "public"), ("team_size", "6"), ("verify_emails", "1"), ("paused", "0"),
           ("start", "1717200000"), ("end", "1790812799"), ("version_latest", "3.8.0"), ("ctf_logo", None),
           ("mail_server", "smtp.example.org"), ("mail_port", "587"), ("mail_useauth", "1"), ("mail_tls", "1"),
           ("theme_header", ""), ("theme_footer", ""), ("ctf_description", "Year-round CTF for students"),
           ("social_shares", "1"), ("team_creation", "1"), ("name_changes", "0"), ("incorrect_submissions_per_min", "10"),
           ("max_attempts_behavior", "lockout"), ("max_attempts_timeout", "300")]
    yield Table("config", ["id", "key", "value"], [(i + 1, k, v) for i, (k, v) in enumerate(cfg)])
    yield Table("brackets", ["id", "name", "description", "type"],
                [(1, "Students", "Currently enrolled", "users"), (2, "Open", "Everyone else", "users"),
                 (3, "Academic teams", None, "teams"), (4, "Professional teams", None, "teams")])
    yield Table("modules", ["id", "name", "description"],
                [(i, f"{w.title()} track", f"Challenges of the {w} track") for i, w in enumerate(CATEGORIES[:6], 1)])
    yield Table("audiences", ["id", "name", "description", "type"],
                [(1, "Beta testers", None, "users"), (2, "University partners", None, "teams"),
                 (3, "Sponsors", "Sponsor-only training", "teams")])
    yield Table("pages", ["id", "title", "route", "content", "draft", "hidden", "auth_required", "format", "link_target"],
                [(i, f"Page {w}", f"page-{w}", f"# {w.title()}\n\n{ctx.row('pages', i).words(20, 60)}", False,
                  i % 5 == 0, i % 4 == 0, "markdown", None) for i, w in enumerate(["rules", "faq", "sponsors", "about",
                                                                                 "privacy", "contact", "prizes",
                                                                                 "schedule", "writeups", "archive",
                                                                                 "team", "code"], 1)])

    # ---- challenges -------------------------------------------------------------------------------------------------
    chal_rows, dyn_rows, chal_ids = [], [], list(range(1, N_CHAL + 1))
    values = {}
    for cid in chal_ids:
        r = ctx.row("challenges", cid)
        dyn = r.chance(0.25)
        value = r.choice([50, 100, 150, 200, 250, 300, 400, 500])
        values[cid] = value
        req = None
        x = r.random()
        cand = [c for c in (r.int(1, N_CHAL), r.int(1, N_CHAL), r.int(1, N_CHAL)) if c < cid][:r.int(1, 3)]
        if x < 0.25:
            req = {"prerequisites": cand}
        elif x < 0.30:
            req = {"prerequisites": cand, "anonymize": True}
        elif x < 0.32:
            req = {"anonymize": False, "prerequisites": []}
        elif x < 0.32 + 0.01 * edge:
            req = {"prerequisites": [str(c) for c in cand] + ([cand[0]] if cand else [])}  # string ids, a duplicate
        elif x < 0.33 + 0.02 * edge:
            req = {"prerequisites": cand + [cid]}  # self reference
        elif x < 0.34 + 0.03 * edge:
            req = {"prerequisites": cand + [N_CHAL + r.int(5, 400)]}  # a deleted challenge
        elif x < 0.345 + 0.035 * edge:
            req = {"prerequisites": str(cand[0]) if cand else "3"}  # not a list
        elif x < 0.35 + 0.04 * edge:
            req = {}
        elif x < 0.355 + 0.045 * edge:
            req = {"prerequisites": cand, "anonymize": "true"}  # a string, not the JSON true
        chal_rows.append((cid, f"{r.word().title()} {r.word()} {cid}", r.words(15, 60), r.choice([0, 0, 0, 5, 10, 25]),
                          value, r.choice(CATEGORIES), "dynamic" if dyn else "standard",
                          r.weighted([("visible", 90), ("hidden", 8), ("locked", 2)]), req,
                          f"nc chal.example.org {30000 + cid}" if r.chance(0.3) else None,
                          None, r.choice([None, None, "by the Lighthouse team", f"by {r.name()}"]),
                          r.weighted([("any", 85), ("all", 15)]), value if dyn else None, 50 if dyn else None,
                          15 if dyn else None, "logarithmic" if dyn else "static", cid,
                          r.int(1, 6) if r.chance(0.3) else None, None))
        if dyn:
            dyn_rows.append((cid, value, 50, 15))
    # json is stored as the application wrote it: serialize with the app's separators so text matches
    yield Table("challenges", ["id", "name", "description", "max_attempts", "value", "category", "type", "state",
                               "requirements", "connection_info", "next_id", "attribution", "logic", "initial",
                               "minimum", "decay", "function", "position", "module_id", "scheduled_at"], chal_rows)
    yield Table("dynamic_challenge", ["id", "initial", "minimum", "decay"], dyn_rows)

    flags, fid = [], 0
    for cid in chal_ids:
        r = ctx.row("flags", cid)
        for _ in range(r.weighted([(1, 70), (2, 25), (3, 5)])):
            fid += 1
            data = r.weighted([("case_insensitive", 30), ("", 48), (None, 15), ("CASE_INSENSITIVE", 2 * edge),
                               (" case_insensitive ", 1 * edge), ("regex", 2), ("Case_Insensitive", 1 * edge)])
            ftype = r.weighted([("static", 85), ("regex", 15)])
            flags.append((fid, cid, ftype, f"flag{{{r.hexstr(16)}}}" if ftype == "static" else r"flag\{[a-f0-9]{16}\}",
                          data))
    yield Table("flags", ["id", "challenge_id", "type", "content", "data"], flags)

    hints, hint_ids, hid_ = [], [], 0
    for cid in chal_ids:
        r = ctx.row("hints", cid)
        for _ in range(r.int(0, 4)):
            hid_ += 1 + (r.int(1, 3) if r.chance(0.06) else 0)  # gaps: deleted hints
            hint_ids.append(hid_)
            hints.append((hid_, "standard", cid, r.words(8, 30), r.choice([0, 0, 10, 25, 50]), None,
                          r.choice([None, "Hint", "Nudge", "Big hint"])))
    yield Table("hints", ["id", "type", "challenge_id", "content", "cost", "requirements", "title"], hints)

    tags, tid = [], 0
    for cid in chal_ids:
        r = ctx.row("tags", cid)
        for _ in range(r.int(0, 5)):
            tid += 1
            tags.append((tid, cid, r.word()))
    yield Table("tags", ["id", "challenge_id", "value"], tags)
    topics = [(i, f"{w}-{j}") for i, (w, j) in enumerate(((w, j) for w in CATEGORIES for j in range(12)), 1)]
    yield Table("topics", ["id", "value"], topics)
    ct, cti = [], 0
    for cid in chal_ids:
        r = ctx.row("challenge_topics", cid)
        for t in sorted({r.int(1, len(topics)) for _ in range(r.int(0, 3))}):
            cti += 1
            ct.append((cti, cid, t))
    yield Table("challenge_topics", ["id", "challenge_id", "topic_id"], ct)

    solutions, sol_ids, sid = [], [], 0
    for cid in chal_ids:
        r = ctx.row("solutions", cid)
        if r.chance(0.4):
            sid += 1 + (r.int(1, 2) if r.chance(0.08) else 0)  # gaps: deleted solutions
            sol_ids.append(sid)
            solutions.append((sid, cid, r.words(30, 90), r.weighted([("hidden", 40), ("visible", 50), ("solved", 10)])))
    yield Table("solutions", ["id", "challenge_id", "content", "state"], solutions)
    files, fi = [], 0
    for cid in chal_ids:
        r = ctx.row("files", cid)
        for _ in range(r.int(0, 2)):
            fi += 1
            files.append((fi, "challenge", f"{r.hexstr(32)}/{r.word()}.zip", cid, None, r.hexstr(40), None))
    yield Table("files", ["id", "type", "location", "challenge_id", "page_id", "sha1sum", "solution_id"], files)

    # ---- teams and users --------------------------------------------------------------------------------------------
    team_members = {t: [] for t in range(1, N_TEAMS + 1)}
    users, emails_seen, user_team, user_ips, used = [], [], {}, {}, set()
    for uid in range(1, N_USERS + 1):
        r = ctx.row("users", uid)
        admin = uid <= 5
        team = None if admin or r.chance(0.02) else r.int(1, N_TEAMS)
        if team:
            team_members[team].append(uid)
        user_team[uid] = team
        first, last = r.first_name(), r.last_name()
        email = f"{first.lower()}.{last.lower()}{uid}@{r.choice(DOMAINS)}"
        x = r.random()
        if emails_seen and x < 0.012 * edge:  # the same address as an earlier account, differently spelled
            base = emails_seen[r.int(0, len(emails_seen) - 1)]
            email = r.choice([base.upper(), base.title(), f" {base}", f"{base} ", base.replace("@", "@").capitalize()])
            if email == base:
                email = base.upper()
        elif x < 0.017 * edge:
            email = None
        if email is not None and email in used:
            email = None
        if email is not None:
            used.add(email)
            if email.strip().lower() == email:
                emails_seen.append(email)
        cx = r.random()
        if cx < 0.45:
            country = None
        elif cx < 0.50:
            country = ""
        elif cx < 0.86:
            country = r.choice(COUNTRY_CODES)
        elif cx < 0.90:
            country = r.choice(COUNTRY_CODES).lower()
        elif cx < 0.95:
            code = r.choice(list(COUNTRY_NAMES))
            name = COUNTRY_NAMES[code]
            country = r.choice([name, name.upper(), name.lower(), f" {name} "])[:32]
        elif cx < 0.95 + 0.03 * edge:
            country = r.choice(ALIASES)
        else:
            country = r.choice(JUNK_COUNTRIES)
        user_ips[uid] = [r.ipv4() for _ in range(r.int(1, 3))] + ([v6(r)] if r.chance(0.15) else [])
        created = r.timestamp(START, END - datetime.timedelta(days=30))
        users.append((uid, None, f"{first}{last}{uid}" if r.chance(0.7) else r.handle(uid),
                      f"$bcrypt-sha256$v=2,t=2b,r=12${r.hexstr(22)}${r.hexstr(31)}", email,
                      "admin" if admin else "user", None,
                      f"https://{first.lower()}{uid}.example.dev" if r.chance(0.2) else None,
                      r.choice(["Lighthouse University", "Ocean State College", "Team Rocket Labs", "Independent",
                                "Example Corp", "Polytechnic of the North"]) if r.chance(0.3) else None,
                      country, r.chance(0.01), r.chance(0.005), r.chance(0.8), team, created,
                      r.choice([None, None, "en", "de", "fr", "ja"]), r.choice([None, 1, 2]), False))
    yield Table("users", ["id", "oauth_id", "name", "password", "email", "type", "secret", "website", "affiliation",
                          "country", "hidden", "banned", "verified", "team_id", "created", "language", "bracket_id",
                          "change_password"], users)
    teams = []
    for t in range(1, N_TEAMS + 1):
        r = ctx.row("teams", t)
        members = team_members[t]
        teams.append((t, None, f"{r.word()}_{r.word()}_{t}", f"team{t}@{r.choice(DOMAINS)}" if r.chance(0.6) else None,
                      f"$bcrypt-sha256${r.hexstr(40)}", None,
                      f"https://team{t}.example.dev" if r.chance(0.1) else None,
                      r.choice([None, "Lighthouse University", "Example Corp"]),
                      r.choice(COUNTRY_CODES) if r.chance(0.4) else None, r.chance(0.01), r.chance(0.004),
                      r.timestamp(START, END - datetime.timedelta(days=60)), members[0] if members else None,
                      r.choice([None, 3, 4])))
    yield Table("teams", ["id", "oauth_id", "name", "email", "password", "secret", "website", "affiliation", "country",
                          "hidden", "banned", "created", "captain_id", "bracket_id"], teams)
    yield Table("audience_members", ["id", "audience_id", "user_id", "team_id"],
                [(i, 1 if i <= 120 else 2, i * 7 if i <= 120 else None, None if i <= 120 else (i - 120) * 13)
                 for i in range(1, 181)])
    yield Table("module_audience_access", ["id", "module_id", "audience_id"], [(1, 6, 1), (2, 5, 2), (3, 6, 3)])

    # ---- submissions and solves -------------------------------------------------------------------------------------
    players = [u for u in range(6, N_USERS + 1) if user_team[u]]
    solved = set()
    subs, solves = [], []
    span = (END - START).total_seconds()
    for sid_ in range(1, N_SUBS + 1):
        r = ctx.row("submissions", sid_)
        uid = players[r.skewed(0, len(players) - 1, 2.2)]
        team = user_team[uid]
        cid = chal_ids[r.skewed(0, len(chal_ids) - 1, 1.6)]
        when = START + datetime.timedelta(seconds=span * (sid_ - 1 + r.random()) / N_SUBS)
        if (team, cid) not in solved and r.chance(0.16):
            kind = "correct"
            solved.add((team, cid))
            solves.append((sid_, cid, uid, team))
        else:
            kind = r.weighted([("incorrect", 900), ("partial", 35), ("discard", 25), ("ratelimited", 36),
                               (None, 3 * edge), ("Incorrect", 1 * edge), ("incorrect ", 1 * edge),
                               (" INCORRECT", 0.5 * edge)])
        ips = user_ips[uid]
        y = r.random()
        if y < 0.88:
            ip = r.choice(ips)
        elif y < 0.92:
            ip = f"{r.choice(ips)}, {r.ipv4()}" + (f", 10.0.{r.int(0, 9)}.{r.int(1, 254)}" if r.chance(0.3) else "")
            if len(ip) > 46:
                ip = ip[:ip.rfind(",")]
        elif y < 0.94:
            ip = f"{r.ipv4()}:{r.int(1024, 65535)}"
        elif y < 0.945 + 0.005 * edge:
            ip = f"[{v6(r)}]:{r.int(1024, 65535)}"
        elif y < 0.95 + 0.01 * edge:
            ip = r.choice(["unknown", "-", "", "  "])
        elif y < 0.955 + 0.015 * edge:
            ip = None
        elif y < 0.958 + 0.018 * edge:
            ip = r.choice(["300.12.1.4", "10.0.0", "1.2.3.4.5", "fe80::1%eth0", "localhost"])
        elif y < 0.961 + 0.021 * edge:
            ip = f"  {r.choice(ips)}\t"
        else:
            ip = r.choice(ips)
        provided = (f"flag{{{r.hexstr(16)}}}" if kind == "correct" else
                    r.choice([f"flag{{{r.word()}_{r.word()}}}", r.word(), f"FLAG{{{r.hexstr(8)}}}", "", "' OR 1=1 --",
                              f"flag{{{r.hexstr(16)}}}", "ÿ" * r.int(1, 3) + "flag"]))
        subs.append((sid_, cid, uid, team, ip, provided, kind, when))
    yield Table("submissions", ["id", "challenge_id", "user_id", "team_id", "ip", "provided", "type", "date"], subs)
    yield Table("solves", ["id", "challenge_id", "user_id", "team_id"], solves)
    del subs

    awards = []
    for a in range(1, n(ctx, 15000) + 1):
        r = ctx.row("awards", a)
        uid = players[r.int(0, len(players) - 1)]
        awards.append((a, uid, user_team[uid], r.choice(["First blood", "Write-up", "Bug bounty", "Hint penalty"]),
                       r.words(3, 10), r.timestamp(START, END), r.choice([-50, -25, -10, 10, 25, 50, 100]),
                       r.choice(["bonus", "penalty", "writeup"]), None, None, "standard"))
    yield Table("awards", ["id", "user_id", "team_id", "name", "description", "date", "value", "category", "icon",
                           "requirements", "type"], awards)

    # ---- unlocks: hint and solution unlocks; some point at deleted hints/solutions ------------------------------------
    max_hint, max_sol = (hint_ids[-1] if hint_ids else 1), (sol_ids[-1] if sol_ids else 1)
    unlocks = []
    for u in range(1, N_UNLOCK + 1):
        r = ctx.row("unlocks", u)
        uid = players[r.skewed(0, len(players) - 1, 2.0)]
        if r.chance(0.9):
            utype = "hints"
            target = r.int(1, max_hint) if r.chance(0.05 * edge) else hint_ids[r.int(0, len(hint_ids) - 1)]
        else:
            utype = "solutions"
            target = r.int(1, max_sol + 3) if r.chance(0.06 * edge) else sol_ids[r.int(0, len(sol_ids) - 1)]
        unlocks.append((u, uid, user_team[uid], target, r.timestamp(START, END), utype, r.choice(user_ips[uid])))
    yield Table("unlocks", ["id", "user_id", "team_id", "target", "date", "type", "ip"], unlocks)

    track = []
    for t in range(1, N_TRACK + 1):
        r = ctx.row("tracking", t)
        uid = players[r.skewed(0, len(players) - 1, 1.8)]
        opened = r.chance(0.3)
        track.append((t, "challenges.open" if opened else None, r.choice(user_ips[uid]), uid,
                      START + datetime.timedelta(seconds=span * (t - 1 + r.random()) / N_TRACK),
                      r.int(1, N_CHAL) if opened else None))
    yield Table("tracking", ["id", "type", "ip", "user_id", "date", "target"], track)

    tokens = []
    for t in range(1, n(ctx, 5000) + 1):
        r = ctx.row("tokens", t)
        created = r.timestamp(START, END)
        tokens.append((t, "user", players[r.int(0, len(players) - 1)], created, created + datetime.timedelta(days=30),
                       f"ctfd_{r.hexstr(64)}", r.choice([None, "CI", "scoreboard bot", "writeup sync"])))
    yield Table("tokens", ["id", "type", "user_id", "created", "expiration", "value", "description"], tokens)
    notes = [(i, f"Announcement {i}", ctx.row("notifications", i).words(10, 40), START + datetime.timedelta(days=i * 3),
              None, None) for i in range(1, 201)]
    yield Table("notifications", ["id", "title", "content", "date", "user_id", "team_id"], notes)
    comments = []
    for c in range(1, n(ctx, 3000) + 1):
        r = ctx.row("comments", c)
        kind = r.choice(["challenge", "user", "team"])
        comments.append((c, kind, r.words(5, 30), r.timestamp(START, END), r.int(1, 5),
                         r.int(1, N_CHAL) if kind == "challenge" else None,
                         r.int(6, N_USERS) if kind == "user" else None, r.int(1, N_TEAMS) if kind == "team" else None,
                         None))
    yield Table("comments", ["id", "type", "content", "date", "author_id", "challenge_id", "user_id", "team_id",
                             "page_id"], comments)
    yield Table("fields", ["id", "name", "type", "field_type", "description", "required", "public", "editable"],
                [(1, "Student ID", "user", "text", None, False, False, True),
                 (2, "Discord", "user", "text", "Your handle", False, True, True),
                 (3, "T-shirt size", "user", "text", None, False, False, True),
                 (4, "University", "team", "text", None, False, True, False),
                 (5, "Coach e-mail", "team", "text", None, False, False, True),
                 (6, "Eligible for prizes", "user", "boolean", None, True, False, False)])
    entries = []
    for e in range(1, n(ctx, 40000) + 1):
        r = ctx.row("field_entries", e)
        fld = r.choice([1, 2, 3, 6])
        entries.append((e, "user", Json(r.chance(0.5) if fld == 6 else f"{r.word()}#{r.int(1000, 9999)}"), fld,
                        players[r.int(0, len(players) - 1)], None))
    yield Table("field_entries", ["id", "type", "value", "field_id", "user_id", "team_id"], entries)
    ratings, seen = [], set()
    for i in range(1, n(ctx, 15000) + 1):
        r = ctx.row("ratings", i)
        uid, cid = players[r.int(0, len(players) - 1)], r.int(1, N_CHAL)
        if (uid, cid) in seen:
            continue
        seen.add((uid, cid))
        ratings.append((len(ratings) + 1, uid, cid, r.choice([-1, 1, 1]), r.choice([None, r.words(3, 15)]),
                        r.timestamp(START, END)))
    yield Table("ratings", ["id", "user_id", "challenge_id", "value", "review", "date"], ratings)
