"""
RedTeam Operator Bot
====================
Kiçik qrup üçün (2-10 nəfər) hazırlanmış Discord botu.
Roadmap-a əsaslanan öyrənmə streaks, progress, CVE feed,
daily challenges, leaderboard və quiz sistemi.
"""

import discord
from discord.ext import commands, tasks
from discord import app_commands
import json
import os
import random
import asyncio
import aiohttp
from datetime import datetime, timedelta, timezone
from pathlib import Path

# ── CONFIG ──────────────────────────────────────────────
TOKEN = os.getenv("DISCORD_TOKEN", "")
DATA_FILE = "data.json"

# Kanal adları (server-inizdəkilərlə uyğunlaşdırın)
DAILY_CHANNEL   = "📊-progress-tracker"
FEED_CHANNEL    = "🔐-cve-feed"
CHALLENGE_CHAN  = "🏁-htb-writeups"

# Roadmap fazaları
PHASES = {
    1: {"name": "Foundation",          "weeks": "1-8",   "emoji": "🏗️"},
    2: {"name": "Active Directory",    "weeks": "9-20",  "emoji": "🏰"},
    3: {"name": "Post-Exploitation",   "weeks": "21-28", "emoji": "⚡"},
    4: {"name": "Advanced Exploit",    "weeks": "29-36", "emoji": "💣"},
    5: {"name": "Real-World Mastery",  "weeks": "37-52", "emoji": "🔥"},
}

# ── DATA ─────────────────────────────────────────────────
def load() -> dict:
    if not Path(DATA_FILE).exists():
        return {"users": {}, "challenges": [], "quiz_scores": {}}
    with open(DATA_FILE) as f:
        return json.load(f)

def save(data: dict):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def get_user(data: dict, uid: str) -> dict:
    if uid not in data["users"]:
        data["users"][uid] = {
            "name": "",
            "streak": 0,
            "longest_streak": 0,
            "last_checkin": None,
            "total_hours": 0,
            "machines": 0,
            "phase": 1,
            "week": 1,
            "xp": 0,
            "badges": [],
            "notes_count": 0,
        }
    return data["users"][uid]

# ── XP & BADGES ──────────────────────────────────────────
XP_TABLE = {
    "checkin":   50,
    "machine":  100,
    "writeup":  150,
    "quiz_win": 200,
    "streak_7": 500,
    "streak_30":2000,
}

BADGES = {
    "streak_7":    ("🔥", "7-Day Streak"),
    "streak_30":   ("💀", "30-Day Streak"),
    "machines_10": ("🖥️", "10 Machines Owned"),
    "machines_50": ("👑", "50 Machines Owned"),
    "phase_2":     ("🏰", "AD Phase Unlocked"),
    "phase_3":     ("⚡", "Post-Exploit Phase"),
    "phase_4":     ("💣", "Exploit Dev Phase"),
    "phase_5":     ("🔥", "Real-World Operator"),
    "quiz_master": ("🧠", "Quiz Master"),
}

def award_xp(u: dict, action: str) -> int:
    pts = XP_TABLE.get(action, 0)
    u["xp"] = u.get("xp", 0) + pts
    return pts

def check_badges(u: dict) -> list[str]:
    """Returns list of newly earned badge keys."""
    earned = []
    b = u.get("badges", [])
    if u["streak"] >= 7   and "streak_7"    not in b: b.append("streak_7");    earned.append("streak_7")
    if u["streak"] >= 30  and "streak_30"   not in b: b.append("streak_30");   earned.append("streak_30")
    if u["machines"] >= 10 and "machines_10" not in b: b.append("machines_10"); earned.append("machines_10")
    if u["machines"] >= 50 and "machines_50" not in b: b.append("machines_50"); earned.append("machines_50")
    if u["phase"] >= 2    and "phase_2"     not in b: b.append("phase_2");     earned.append("phase_2")
    if u["phase"] >= 3    and "phase_3"     not in b: b.append("phase_3");     earned.append("phase_3")
    if u["phase"] >= 4    and "phase_4"     not in b: b.append("phase_4");     earned.append("phase_4")
    if u["phase"] >= 5    and "phase_5"     not in b: b.append("phase_5");     earned.append("phase_5")
    u["badges"] = b
    return earned

def level_from_xp(xp: int) -> tuple[int, str]:
    thresholds = [
        (0,    "Script Kiddie"),
        (500,  "Noob Hacker"),
        (1500, "Pentester"),
        (3500, "Red Teamer"),
        (7000, "Senior Red Teamer"),
        (12000,"Threat Actor"),
        (20000,"APT Operator"),
    ]
    level = 1
    title = thresholds[0][1]
    for i, (req, name) in enumerate(thresholds):
        if xp >= req:
            level = i + 1
            title = name
    return level, title

# ── QUIZ DATA ─────────────────────────────────────────────
QUIZ_QUESTIONS = [
    {
        "q": "Kerberoasting hücumunda hansı ticket request edilir?",
        "choices": ["TGT", "TGS (Service Ticket)", "AS-REP", "PAC"],
        "answer": 1,
        "topic": "Kerberos",
    },
    {
        "q": "DCSync attack-ı yerinə yetirmək üçün hansı hüquq lazımdır?",
        "choices": ["GenericAll", "DS-Replication-Get-Changes-All", "WriteDacl", "AddMember"],
        "answer": 1,
        "topic": "Active Directory",
    },
    {
        "q": "LSASS prosesinin PID-ini tapmaq üçün hansı komanda istifadə olunur?",
        "choices": ["ps aux | grep lsass", "tasklist /FI \"IMAGENAME eq lsass.exe\"", "netstat -ano", "whoami /priv"],
        "answer": 1,
        "topic": "Credential Access",
    },
    {
        "q": "BloodHound hansı protokol vasitəsilə AD məlumatlarını toplayır?",
        "choices": ["SMB", "LDAP", "Kerberos", "RPC"],
        "answer": 1,
        "topic": "Enumeration",
    },
    {
        "q": "Pass-the-Hash hücumunda hansı hash istifadə olunur?",
        "choices": ["LM hash", "NT hash", "NTLM v2 hash", "SHA-256"],
        "answer": 1,
        "topic": "Lateral Movement",
    },
    {
        "q": "AMSI bypass üçün ən sadə patch hansı funksiyanı hədəf alır?",
        "choices": ["AmsiInitialize", "AmsiScanBuffer", "AmsiCloseSession", "AmsiOpenSession"],
        "answer": 1,
        "topic": "Evasion",
    },
    {
        "q": "Unconstrained delegation-da hansı atribut Active olmalıdır?",
        "choices": ["msDS-AllowedToDelegateTo", "TrustedForDelegation", "msDS-AllowedToActOnBehalfOfOtherIdentity", "userAccountControl"],
        "answer": 1,
        "topic": "Delegation",
    },
    {
        "q": "Golden Ticket yaratmaq üçün mütləq lazım olan hash nədir?",
        "choices": ["Administrator NTLM hash", "krbtgt NTLM hash", "Domain SID", "Machine account hash"],
        "answer": 1,
        "topic": "Kerberos",
    },
    {
        "q": "ROP (Return-Oriented Programming) hansı müdafiəni bypass edir?",
        "choices": ["ASLR", "DEP/NX", "Stack Canary", "PIE"],
        "answer": 1,
        "topic": "Binary Exploitation",
    },
    {
        "q": "AS-REP Roasting üçün hədəf user-də hansı parametr aktiv olmalıdır?",
        "choices": ["Password never expires", "Do not require Kerberos preauthentication", "Account is sensitive", "Password not required"],
        "answer": 1,
        "topic": "Kerberos",
    },
    {
        "q": "Chisel tool-u hansı protokol üzərindən tunnel qurur?",
        "choices": ["DNS", "ICMP", "HTTP/HTTPS", "SMB"],
        "answer": 2,
        "topic": "Pivoting",
    },
    {
        "q": "GTFOBins hansı məqsəd üçün istifadə olunur?",
        "choices": ["Password cracking", "SUID/sudo binary exploitation", "Network scanning", "Malware analysis"],
        "answer": 1,
        "topic": "Linux PrivEsc",
    },
    {
        "q": "mimikatz-da `sekurlsa::logonpasswords` nə edir?",
        "choices": ["SAM faylını dump edir", "LSASS-dan credential-ları oxuyur", "Kerberos ticket-lər list edir", "Registry-dən LSA secrets oxuyur"],
        "answer": 1,
        "topic": "Credential Access",
    },
    {
        "q": "ESC1 AD CS attack-ında nə exploit olunur?",
        "choices": ["CA key theft", "Enrollee Supplies Subject + Client Auth template", "NTLM relay to HTTP", "Template ACL misconfiguration"],
        "answer": 1,
        "topic": "AD CS",
    },
    {
        "q": "Process Hollowing-da hansı Windows API çağırışı prosesi suspend edir?",
        "choices": ["CreateProcess (SUSPENDED flag)", "NtSuspendProcess", "SuspendThread", "ZwCreateProcess"],
        "answer": 0,
        "topic": "Malware Dev",
    },
]

# ── DAILY CHALLENGES ──────────────────────────────────────
DAILY_CHALLENGES = [
    {"title": "SUID Enum", "desc": "GTFOBins-dən 5 SUID exploit tap və test et. Screenshot-la.", "xp": 100, "phase": 1},
    {"title": "BloodHound Path", "desc": "Home lab-da BloodHound run et, DA-ya ən qısa yolu tap.", "xp": 150, "phase": 2},
    {"title": "Kerberoast & Crack", "desc": "Ən azı 1 service account-u kerberoast edib hash-ı crack et.", "xp": 200, "phase": 2},
    {"title": "NTLM Relay Lab", "desc": "SMB signing-i disable et, Responder + ntlmrelayx-la relay yap.", "xp": 250, "phase": 2},
    {"title": "LSASS Dump", "desc": "3 fərqli metodla LSASS dump et (Mimikatz, ProcDump, comsvcs).", "xp": 150, "phase": 3},
    {"title": "Pivoting Chain", "desc": "Chisel ilə 2 network hop qur, daxili subnet-ə çat.", "xp": 200, "phase": 3},
    {"title": "Persistence + Cleanup", "desc": "5 fərqli persistence qur, reboot-da check et, sonra hamısını sil.", "xp": 200, "phase": 3},
    {"title": "CreateRemoteThread", "desc": "C-də CreateRemoteThread injector yaz, calc.exe inject et.", "xp": 300, "phase": 4},
    {"title": "AMSI Bypass", "desc": "PowerShell AMSI-ni 2 fərqli metodla bypass et.", "xp": 250, "phase": 4},
    {"title": "ROP Chain", "desc": "ROPgadget ilə ret2libc chain yaz, shell al.", "xp": 350, "phase": 4},
    {"title": "Scapy SYN Scan", "desc": "Python/Scapy ilə multi-threaded SYN scanner yaz.", "xp": 100, "phase": 1},
    {"title": "Golden Ticket", "desc": "Lab-da DCSync et, krbtgt hash al, Golden Ticket forge et.", "xp": 300, "phase": 2},
    {"title": "AD CS ESC1", "desc": "Vulnerable template yarat, Certify ilə exploit et.", "xp": 300, "phase": 2},
    {"title": "Sliver Beacon", "desc": "Sliver C2-də HTTP beacon gen et, post-exploit modul run et.", "xp": 200, "phase": 3},
    {"title": "Buffer Overflow 64", "desc": "pwntools ilə 64-bit BOF exploit yaz, shell al.", "xp": 350, "phase": 4},
]

# ── BOT SETUP ─────────────────────────────────────────────
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)
tree = bot.tree

# ── STREAK: CHECK-IN ──────────────────────────────────────
@tree.command(name="checkin", description="Günlük check-in - öyrəndiklərini qeyd et")
@app_commands.describe(
    hours="Bu gün neçə saat çalışdın?",
    topic="Nə öyrəndin? (məs: Kerberoasting, LSASS dump)",
    machines="Bu gün neçə machine root aldın? (default: 0)",
)
async def checkin(interaction: discord.Interaction, hours: float, topic: str, machines: int = 0):
    await interaction.response.defer()
    data = load()
    uid = str(interaction.user.id)
    u = get_user(data, uid)
    u["name"] = interaction.user.display_name

    now = datetime.now(timezone.utc).date()
    last = datetime.fromisoformat(u["last_checkin"]).date() if u["last_checkin"] else None

    streak_broken = False
    if last is None:
        u["streak"] = 1
    elif last == now:
        await interaction.followup.send("⚠️ Bu gün artıq check-in etmisən!", ephemeral=True)
        return
    elif last == now - timedelta(days=1):
        u["streak"] += 1
    else:
        streak_broken = u["streak"] > 1
        u["streak"] = 1

    if u["streak"] > u.get("longest_streak", 0):
        u["longest_streak"] = u["streak"]

    u["last_checkin"] = datetime.now(timezone.utc).isoformat()
    u["total_hours"] = round(u.get("total_hours", 0) + hours, 1)
    u["machines"] = u.get("machines", 0) + machines

    xp_earned = award_xp(u, "checkin")
    if machines:
        for _ in range(machines):
            xp_earned += award_xp(u, "machine")
    if u["streak"] == 7:
        xp_earned += award_xp(u, "streak_7")
    if u["streak"] == 30:
        xp_earned += award_xp(u, "streak_30")

    new_badges = check_badges(u)
    level, title = level_from_xp(u["xp"])
    save(data)

    # ── Embed ──
    color = discord.Color.green() if not streak_broken else discord.Color.orange()
    em = discord.Embed(
        title=f"{'🔥' * min(u['streak'], 5)} Check-in qeydə alındı!",
        color=color,
        timestamp=datetime.now(timezone.utc),
    )
    em.set_author(name=interaction.user.display_name, icon_url=interaction.user.display_avatar.url)
    em.add_field(name="📚 Mövzu", value=topic, inline=False)
    em.add_field(name="⏱️ Saat", value=f"{hours}h", inline=True)
    em.add_field(name="🖥️ Machine", value=str(machines), inline=True)
    em.add_field(name="🔥 Streak", value=f"{u['streak']} gün", inline=True)
    em.add_field(name="⚡ XP", value=f"+{xp_earned} → {u['xp']} total", inline=True)
    em.add_field(name="🎖️ Səviyyə", value=f"Lv.{level} {title}", inline=True)
    em.add_field(name="📊 Ümumi saat", value=f"{u['total_hours']}h", inline=True)

    if streak_broken:
        em.add_field(name="💔 Streak sıfırlandı", value="Dünən check-in etmədin. Yenidən başla!", inline=False)

    if new_badges:
        badge_str = " ".join(f"{BADGES[b][0]} **{BADGES[b][1]}**" for b in new_badges)
        em.add_field(name="🏆 Yeni badge!", value=badge_str, inline=False)

    if u["streak"] in (7, 14, 30, 60, 100):
        em.add_field(name="🌟 Milestone!", value=f"{u['streak']} günlük streak! Əla iş!", inline=False)

    await interaction.followup.send(embed=em)

# ── PROFILE ───────────────────────────────────────────────
@tree.command(name="profile", description="Profil və statistikanı göstər")
@app_commands.describe(member="Digər üzvün profili (boş buraxsanız öz profiliniz)")
async def profile(interaction: discord.Interaction, member: discord.Member = None):
    await interaction.response.defer()
    target = member or interaction.user
    data = load()
    u = get_user(data, str(target.id))

    level, title = level_from_xp(u.get("xp", 0))
    phase = u.get("phase", 1)
    phase_info = PHASES[phase]

    # XP progress to next level
    xp_thresholds = [0, 500, 1500, 3500, 7000, 12000, 20000, 99999]
    cur_xp = u.get("xp", 0)
    next_xp = next((t for t in xp_thresholds if t > cur_xp), 99999)
    prev_xp = xp_thresholds[min(level - 1, len(xp_thresholds)-1)]
    prog_pct = int((cur_xp - prev_xp) / max(next_xp - prev_xp, 1) * 20)
    bar = "█" * prog_pct + "░" * (20 - prog_pct)

    badges_str = " ".join(BADGES[b][0] for b in u.get("badges", [])) or "Hələ yoxdur"

    em = discord.Embed(
        title=f"👤 {target.display_name}",
        color=discord.Color.blurple(),
    )
    em.set_thumbnail(url=target.display_avatar.url)
    em.add_field(name="🎖️ Səviyyə", value=f"**Lv.{level}** — {title}", inline=True)
    em.add_field(name="⚡ XP", value=f"{cur_xp:,}", inline=True)
    em.add_field(name="📈 Progress", value=f"`{bar}` {cur_xp}/{next_xp}", inline=False)
    em.add_field(name=f"{phase_info['emoji']} Faza", value=f"Faza {phase}: {phase_info['name']} (Həftə {phase_info['weeks']})", inline=False)
    em.add_field(name="🔥 Streak", value=f"{u.get('streak', 0)} gün (Ən yüksək: {u.get('longest_streak', 0)})", inline=True)
    em.add_field(name="⏱️ Ümumi saat", value=f"{u.get('total_hours', 0)}h", inline=True)
    em.add_field(name="🖥️ Machines", value=str(u.get("machines", 0)), inline=True)
    em.add_field(name="🏆 Badges", value=badges_str, inline=False)

    save(data)
    await interaction.followup.send(embed=em)

# ── LEADERBOARD ───────────────────────────────────────────
@tree.command(name="leaderboard", description="Server leaderboard-unu göstər")
@app_commands.describe(sort_by="Sıralama növü: xp / streak / machines / hours")
@app_commands.choices(sort_by=[
    app_commands.Choice(name="XP",       value="xp"),
    app_commands.Choice(name="Streak",   value="streak"),
    app_commands.Choice(name="Machines", value="machines"),
    app_commands.Choice(name="Hours",    value="total_hours"),
])
async def leaderboard(interaction: discord.Interaction, sort_by: str = "xp"):
    data = load()
    users = data.get("users", {})
    if not users:
        await interaction.response.send_message("Hələ heç kim check-in etməyib!", ephemeral=True)
        return

    sorted_users = sorted(users.items(), key=lambda x: x[1].get(sort_by, 0), reverse=True)
    medals = ["🥇", "🥈", "🥉"]

    em = discord.Embed(
        title=f"🏆 Leaderboard — {sort_by.upper()}",
        color=discord.Color.gold(),
        timestamp=datetime.now(timezone.utc),
    )

    rows = []
    for i, (uid, u) in enumerate(sorted_users[:10]):
        medal = medals[i] if i < 3 else f"`{i+1}.`"
        name = u.get("name") or f"User#{uid[:4]}"
        val = u.get(sort_by, 0)
        level, title = level_from_xp(u.get("xp", 0))
        unit = {"xp": "XP", "streak": "gün", "machines": "machine", "total_hours": "saat"}.get(sort_by, "")
        rows.append(f"{medal} **{name}** — {val} {unit} *(Lv.{level} {title})*")

    em.description = "\n".join(rows) or "Boşdur"
    await interaction.response.send_message(embed=em)

# ── PROGRESS: SET PHASE/WEEK ──────────────────────────────
@tree.command(name="setprogress", description="Cari fazanı və həftəni yenilə")
@app_commands.describe(phase="Hansı fazadasın? (1-5)", week="Neçənci həftəsindəsən? (1-52)")
async def setprogress(interaction: discord.Interaction, phase: int, week: int):
    if not (1 <= phase <= 5) or not (1 <= week <= 52):
        await interaction.response.send_message("❌ Faza 1-5, həftə 1-52 arasında olmalıdır.", ephemeral=True)
        return
    data = load()
    u = get_user(data, str(interaction.user.id))
    u["phase"] = phase
    u["week"] = week
    new_badges = check_badges(u)
    save(data)
    pinfo = PHASES[phase]
    msg = f"✅ Faza **{phase}: {pinfo['name']}** | Həftə **{week}** olaraq qeyd edildi."
    if new_badges:
        msg += "\n🏆 " + " ".join(f"{BADGES[b][0]} {BADGES[b][1]}" for b in new_badges)
    await interaction.response.send_message(msg)

# ── QUIZ ──────────────────────────────────────────────────
active_quizzes: dict[int, dict] = {}  # channel_id → quiz state

@tree.command(name="quiz", description="Təsadüfi Red Team sualı ver — kim əvvəl cavab verir?")
async def quiz(interaction: discord.Interaction):
    cid = interaction.channel_id
    if cid in active_quizzes:
        await interaction.response.send_message("⚠️ Bu kanalda artıq aktiv quiz var!", ephemeral=True)
        return

    q = random.choice(QUIZ_QUESTIONS)
    active_quizzes[cid] = {"answer": q["answer"], "topic": q["topic"], "started_by": interaction.user.id}

    choices_text = "\n".join(
        f"{'🅐🅑🅒🅓'[i]} {c}" for i, c in enumerate(q["choices"])
    )
    em = discord.Embed(
        title=f"🧠 Quiz — {q['topic']}",
        description=f"**{q['q']}**\n\n{choices_text}\n\n*`!a` `!b` `!c` `!d` ilə cavabla — ilk düzgün cavab +200 XP!*",
        color=discord.Color.purple(),
    )
    em.set_footer(text="60 saniyə vaxtın var!")
    await interaction.response.send_message(embed=em)

    await asyncio.sleep(60)
    if cid in active_quizzes:
        del active_quizzes[cid]
        try:
            await interaction.followup.send(f"⏰ Vaxt bitdi! Düzgün cavab: **{q['choices'][q['answer']]}**")
        except Exception:
            pass

@bot.command(name="a")
async def ans_a(ctx): await _check_answer(ctx, 0)
@bot.command(name="b")
async def ans_b(ctx): await _check_answer(ctx, 1)
@bot.command(name="c")
async def ans_c(ctx): await _check_answer(ctx, 2)
@bot.command(name="d")
async def ans_d(ctx): await _check_answer(ctx, 3)

async def _check_answer(ctx: commands.Context, choice: int):
    cid = ctx.channel.id
    if cid not in active_quizzes:
        return
    quiz_state = active_quizzes[cid]
    if choice == quiz_state["answer"]:
        del active_quizzes[cid]
        data = load()
        u = get_user(data, str(ctx.author.id))
        u["name"] = ctx.author.display_name
        xp = award_xp(u, "quiz_win")

        # quiz master badge: 10 quiz wins tracked
        qs = data.setdefault("quiz_scores", {})
        qs[str(ctx.author.id)] = qs.get(str(ctx.author.id), 0) + 1
        if qs[str(ctx.author.id)] >= 10 and "quiz_master" not in u.get("badges", []):
            u.setdefault("badges", []).append("quiz_master")
        save(data)
        level, title = level_from_xp(u["xp"])
        await ctx.send(
            f"✅ **{ctx.author.display_name}** düzgün cavabladı! "
            f"+{xp} XP → {u['xp']} total *(Lv.{level} {title})*"
        )
    else:
        await ctx.message.add_reaction("❌")

# ── DAILY CHALLENGE ───────────────────────────────────────
@tree.command(name="challenge", description="Günün challenge-ini al (fazana uyğun)")
async def challenge(interaction: discord.Interaction):
    data = load()
    u = get_user(data, str(interaction.user.id))
    phase = u.get("phase", 1)

    # Filter to current or easier phases
    pool = [c for c in DAILY_CHALLENGES if c["phase"] <= phase]
    if not pool:
        pool = DAILY_CHALLENGES

    ch = random.choice(pool)
    em = discord.Embed(
        title=f"🎯 Günün Challenge-i: {ch['title']}",
        description=ch["desc"],
        color=discord.Color.dark_red(),
    )
    em.add_field(name="💎 XP Mükafatı", value=f"{ch['xp']} XP", inline=True)
    em.add_field(name="🗂️ Faza", value=str(ch["phase"]), inline=True)
    em.set_footer(text="Tamamladıqdan sonra /checkin edərək qeyd et!")
    await interaction.response.send_message(embed=em)

# ── CVE FEED ──────────────────────────────────────────────
@tasks.loop(hours=6)
async def cve_feed():
    await bot.wait_until_ready()
    channel = discord.utils.get(bot.get_all_channels(), name=FEED_CHANNEL)
    if not channel:
        return
    try:
        async with aiohttp.ClientSession() as session:
            url = "https://cve.circl.lu/api/last/5"
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as r:
                if r.status != 200:
                    return
                cves = await r.json()
        if not cves:
            return
        em = discord.Embed(
            title="🔴 Son CVE-lər",
            color=discord.Color.red(),
            timestamp=datetime.now(timezone.utc),
        )
        for cve in cves[:5]:
            cve_id   = cve.get("id", "N/A")
            summary  = (cve.get("summary", "N/A") or "N/A")[:200]
            cvss     = cve.get("cvss", "?")
            em.add_field(
                name=f"🔸 {cve_id} | CVSS: {cvss}",
                value=summary + ("…" if len(summary) == 200 else ""),
                inline=False,
            )
        em.set_footer(text="Mənbə: cve.circl.lu")
        await channel.send(embed=em)
    except Exception:
        pass

# ── DAILY REMINDER ────────────────────────────────────────
@tasks.loop(hours=24)
async def daily_reminder():
    await bot.wait_until_ready()
    now = datetime.now(timezone.utc)
    if now.hour != 7:
        return
    channel = discord.utils.get(bot.get_all_channels(), name=DAILY_CHANNEL)
    if not channel:
        return

    data = load()
    missed = []
    for uid, u in data.get("users", {}).items():
        last = datetime.fromisoformat(u["last_checkin"]).date() if u.get("last_checkin") else None
        if last and last < now.date() - timedelta(days=1):
            missed.append(u.get("name", f"User#{uid[:4]}"))

    ch = random.choice(DAILY_CHALLENGES)
    em = discord.Embed(
        title="☀️ Günün Başladı — Red Team Operator, Hazır Ol!",
        description=(
            f"**Günün challenge-i:** {ch['title']}\n"
            f"{ch['desc']}\n\n"
            f"💎 *{ch['xp']} XP* · `/checkin` ilə günü qeyd et!"
        ),
        color=discord.Color.orange(),
        timestamp=now,
    )
    if missed:
        em.add_field(name="⚠️ Streak Riski", value=", ".join(missed) + " — dünən check-in etmədi!", inline=False)
    em.set_footer(text='"Consistency over intensity." — Hər gün bir addım.')
    await channel.send(embed=em)

# ── STATS (SERVER-WIDE) ───────────────────────────────────
@tree.command(name="stats", description="Server-in ümumi statistikası")
async def stats(interaction: discord.Interaction):
    data = load()
    users = data.get("users", {})
    if not users:
        await interaction.response.send_message("Hələ heç kim check-in etməyib!", ephemeral=True)
        return

    total_hours   = sum(u.get("total_hours", 0) for u in users.values())
    total_machines= sum(u.get("machines", 0) for u in users.values())
    total_xp      = sum(u.get("xp", 0) for u in users.values())
    top_streak    = max((u.get("streak", 0) for u in users.values()), default=0)
    active_today  = sum(
        1 for u in users.values()
        if u.get("last_checkin") and
        datetime.fromisoformat(u["last_checkin"]).date() == datetime.now(timezone.utc).date()
    )

    em = discord.Embed(
        title="📊 Server Statistikası",
        color=discord.Color.blurple(),
        timestamp=datetime.now(timezone.utc),
    )
    em.add_field(name="👥 Üzvlər", value=str(len(users)), inline=True)
    em.add_field(name="✅ Bu gün aktiv", value=str(active_today), inline=True)
    em.add_field(name="⏱️ Ümumi saat", value=f"{total_hours:.1f}h", inline=True)
    em.add_field(name="🖥️ Ümumi machine", value=str(total_machines), inline=True)
    em.add_field(name="⚡ Ümumi XP", value=f"{total_xp:,}", inline=True)
    em.add_field(name="🔥 Ən uzun streak", value=f"{top_streak} gün", inline=True)
    await interaction.response.send_message(embed=em)

# ── ROADMAP ───────────────────────────────────────────────
@tree.command(name="roadmap", description="12 aylıq roadmap fazasını göstər")
@app_commands.describe(phase="Faza nömrəsi (1-5, boş buraxsanız cari fazanız)")
async def roadmap_cmd(interaction: discord.Interaction, phase: int = None):
    data = load()
    u = get_user(data, str(interaction.user.id))
    phase = phase or u.get("phase", 1)
    if not (1 <= phase <= 5):
        await interaction.response.send_message("❌ Faza 1-5 arasında olmalıdır.", ephemeral=True)
        return

    pinfo = PHASES[phase]
    descriptions = {
        1: "Linux mastery, Networking deep dive, Python for red team, C & binary exploitation basics. 30+ lab, 30+ Python tool.",
        2: "AD architecture, BloodHound, Kerberoasting, AS-REP Roasting, NTLM relay, Delegation attacks, ACL/GPO abuse, DCSync, Golden Ticket, AD CS (ESC1-8). RastaLabs + Offshore Pro Labs.",
        3: "Credential dumping (LSASS, SAM, DPAPI, browser), 15+ persistence technique, lateral movement (PsExec, WMI, DCOM, RDP, WinRM), pivoting (Chisel, ligolo-ng, SSH), C2 frameworks (Sliver, custom C2).",
        4: "Malware development (PE format, 10+ process injection, AMSI/ETW bypass, syscall direct), kernel/rootkit basics, advanced exploitation (heap, format string, ROP), CVE hunting.",
        5: "HTB Pro Labs (Dante, Offshore, Cybernetics, APTLabs), certifications (CRTP, CRTO, OSEP), portfolio (GitHub 15+ repos, 25+ blog), bug bounty, job applications.",
    }

    em = discord.Embed(
        title=f"{pinfo['emoji']} Faza {phase}: {pinfo['name']}",
        description=descriptions[phase],
        color=discord.Color.dark_green(),
    )
    em.add_field(name="📅 Həftələr", value=pinfo["weeks"], inline=True)
    em.add_field(name="📍 Sənin fazanız", value=f"Faza {u.get('phase', 1)}", inline=True)
    save(data)
    await interaction.response.send_message(embed=em)

# ── WRITEUP LOG ───────────────────────────────────────────
@tree.command(name="writeup", description="Machine/challenge writeup-unu qeyd et")
@app_commands.describe(
    machine="Machine/challenge adı",
    platform="Platforma: HTB / THM / CTF / VulnHub",
    difficulty="Çətinlik: Easy / Medium / Hard / Insane",
    notes="Qısa qeyd (öyrəndiklərin, istifadə olunan texnikalar)",
)
async def writeup(interaction: discord.Interaction, machine: str, platform: str, difficulty: str, notes: str):
    data = load()
    u = get_user(data, str(interaction.user.id))
    u["name"] = interaction.user.display_name
    xp = award_xp(u, "writeup")
    save(data)

    em = discord.Embed(
        title=f"📝 Writeup: {machine}",
        color=discord.Color.teal(),
        timestamp=datetime.now(timezone.utc),
    )
    em.set_author(name=interaction.user.display_name, icon_url=interaction.user.display_avatar.url)
    em.add_field(name="🖥️ Platform", value=platform, inline=True)
    em.add_field(name="⚡ Difficulty", value=difficulty, inline=True)
    em.add_field(name="🧠 Qeydlər", value=notes, inline=False)
    em.add_field(name="💎 XP", value=f"+{xp}", inline=True)
    em.set_footer(text="Writeup qeydə alındı!")
    await interaction.response.send_message(embed=em)

# ── HELP ──────────────────────────────────────────────────
@tree.command(name="rthelp", description="Bütün komandaların siyahısı")
async def rthelp(interaction: discord.Interaction):
    em = discord.Embed(
        title="🔐 RedTeam Bot — Komandalar",
        color=discord.Color.dark_blue(),
    )
    cmds = [
        ("/checkin",     "Günlük check-in (saat + mövzu + machine)"),
        ("/profile",     "Profil, XP, streak, badge-lər"),
        ("/leaderboard", "Sıralama (XP / streak / machine / saat)"),
        ("/setprogress", "Cari faza və həftəni yenilə"),
        ("/challenge",   "Günün challenge-ini al"),
        ("/quiz",        "Çoxseçimli Red Team sualı — !a !b !c !d ilə cavabla"),
        ("/writeup",     "Machine writeup qeyd et (+150 XP)"),
        ("/roadmap",     "12 aylıq roadmap fazasını göstər"),
        ("/stats",       "Server-in ümumi statistikası"),
        ("/rthelp",      "Bu yardım menyusu"),
    ]
    for name, desc in cmds:
        em.add_field(name=f"`{name}`", value=desc, inline=False)
    em.set_footer(text="CVE feed hər 6 saatda avtomatik, daily reminder hər gün 07:00 UTC.")
    await interaction.response.send_message(embed=em, ephemeral=True)

# ── STARTUP ───────────────────────────────────────────────
@bot.event
async def on_ready():
    await tree.sync()
    cve_feed.start()
    daily_reminder.start()
    await bot.change_presence(
        activity=discord.Activity(
            type=discord.ActivityType.watching,
            name="Red Team Operators grow 🔥"
        )
    )
    print(f"[+] {bot.user} hazırdır. {len(bot.guilds)} server.")

bot.run(TOKEN)
