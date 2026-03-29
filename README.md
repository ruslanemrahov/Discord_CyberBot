# 🔐 RedTeam Operator Discord Bot

Red Team qrupunuz üçün hazırlanmış Discord botu.  
Öyrənmə streaks, XP/levels, CVE feed, daily challenge, quiz sistemi.

---

## ⚡ Quraşdırma

### 1. Discord Bot yaradın

1. https://discord.com/developers/applications → **New Application**
2. Sol menyudan **Bot** → **Add Bot**
3. **TOKEN** kopyalayın → `bot.py` faylında `TOKEN = "..."` yerinə yazın
4. **Privileged Gateway Intents** bölməsindən:
   - ✅ SERVER MEMBERS INTENT
   - ✅ MESSAGE CONTENT INTENT
5. **OAuth2 → URL Generator**:
   - Scopes: `bot` + `applications.commands`
   - Bot Permissions: `Send Messages`, `Embed Links`, `Read Message History`, `Add Reactions`
6. Yaradılan linki brauzerdə açın → serverinizə əlavə edin

### 2. Botun özünü run edin

```bash
# Python 3.10+ lazımdır
pip install -r requirements.txt

# TOKEN-i environment variable olaraq verin:
export DISCORD_TOKEN="your_token_here"
python bot.py
```

Və ya birbaşa `bot.py` faylında:
```python
TOKEN = "your_token_here"
```

---

## 🛠️ Discord Server Kanalları

Bot bu adlarda kanallar axtarır (dəyişdirmək üçün `bot.py`-in yuxarısına bax):

| Kanal adı              | Məqsəd                    |
|------------------------|---------------------------|
| `📊-progress-tracker`  | Daily reminder mesajları  |
| `🔐-cve-feed`          | Avtomatik CVE xəbərləri   |
| `🏁-htb-writeups`      | Writeup kanalı (manual)   |

---

## 📋 Slash Komandalar

| Komanda        | Açıqlama                                         |
|----------------|--------------------------------------------------|
| `/checkin`     | Günlük check-in — saat + mövzu + machine count  |
| `/profile`     | XP, streak, badge, level, faza statistikası     |
| `/leaderboard` | XP / streak / machine / saat üzrə sıralama      |
| `/setprogress` | Cari roadmap fazasını və həftəsini yenilə        |
| `/challenge`   | Fazana uyğun günlük challenge al                 |
| `/quiz`        | Çoxseçimli sual → `!a` `!b` `!c` `!d` cavabla  |
| `/writeup`     | Machine/CTF writeup qeyd et (+150 XP)           |
| `/roadmap`     | 12 aylıq roadmap fazasını izah et               |
| `/stats`       | Server-in ümumi statistikası                    |
| `/rthelp`      | Komandaların siyahısı                           |

---

## 🏆 XP Sistemi

| Hərəkət         | XP    |
|-----------------|-------|
| Daily check-in  | +50   |
| Hər machine     | +100  |
| Writeup          | +150  |
| Quiz qazan      | +200  |
| 7 günlük streak | +500  |
| 30 günlük streak| +2000 |

### Səviyyələr

| Lv | Başlıq            | Tələb olunan XP |
|----|-------------------|-----------------|
| 1  | Script Kiddie     | 0               |
| 2  | Noob Hacker       | 500             |
| 3  | Pentester         | 1,500           |
| 4  | Red Teamer        | 3,500           |
| 5  | Senior Red Teamer | 7,000           |
| 6  | Threat Actor      | 12,000          |
| 7  | APT Operator      | 20,000          |

---

## 🔴 Avtomatik Xüsusiyyətlər

- **CVE Feed** — hər 6 saatda `#cve-feed` kanalına son 5 CVE
- **Daily Reminder** — hər gün 07:00 UTC-də günün challenge-i + streak riski olan üzvlər

---

## 📁 Fayllar

```
redteam_bot/
├── bot.py          ← Əsas bot
├── requirements.txt
├── data.json       ← Avtomatik yaradılır (bütün user məlumatları)
└── README.md
```

---

## 🔧 Fərdiləşdirmə

`bot.py`-in yuxarısındakı sabitlər:

```python
DAILY_CHANNEL  = "📊-progress-tracker"   # reminder kanalı
FEED_CHANNEL   = "🔐-cve-feed"           # CVE feed kanalı
CHALLENGE_CHAN = "🏁-htb-writeups"        # writeup kanalı
```

Quiz sualları və daily challenge-lər — `QUIZ_QUESTIONS` və `DAILY_CHALLENGES` listlərini genişləndirə bilərsən.

---

## ☁️ 24/7 Hosting (Pulsuz)

**Railway.app** (ən asan):
1. https://railway.app → GitHub-dan repo import et
2. Environment variable: `DISCORD_TOKEN = your_token`
3. Deploy → bot 24/7 işləyir

**Alternativlər:** Render.com, Fly.io, VPS (DigitalOcean $5/ay)
