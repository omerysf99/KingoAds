import aiosqlite
import json
from typing import Optional, List, Dict


class Database:
    def __init__(self, db_path: str):
        self.db_path = db_path

    async def init(self):
        async with aiosqlite.connect(self.db_path) as db:
            await db.executescript("""
                PRAGMA journal_mode=WAL;

                CREATE TABLE IF NOT EXISTS users (
                    user_id     INTEGER PRIMARY KEY,
                    username    TEXT,
                    full_name   TEXT,
                    ref_by      INTEGER,
                    balance_try REAL    DEFAULT 0,
                    earned_try  REAL    DEFAULT 0,
                    joined_at   TEXT    DEFAULT CURRENT_TIMESTAMP,
                    is_banned   INTEGER DEFAULT 0
                );

                CREATE TABLE IF NOT EXISTS channels (
                    channel_id   INTEGER PRIMARY KEY,
                    owner_id     INTEGER NOT NULL,
                    username     TEXT,
                    title        TEXT,
                    member_count INTEGER DEFAULT 0,
                    category     TEXT    DEFAULT 'Genel',
                    is_approved  INTEGER DEFAULT 0,
                    is_active    INTEGER DEFAULT 1,
                    added_at     TEXT    DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (owner_id) REFERENCES users(user_id)
                );

                CREATE TABLE IF NOT EXISTS ads (
                    ad_id             INTEGER PRIMARY KEY AUTOINCREMENT,
                    advertiser_id     INTEGER NOT NULL,
                    title             TEXT,
                    content           TEXT,
                    photo_file_id     TEXT,
                    button_text       TEXT,
                    button_url        TEXT,
                    budget_try        REAL,
                    spent_try         REAL    DEFAULT 0,
                    target_views      INTEGER,
                    actual_views      INTEGER DEFAULT 0,
                    status            TEXT    DEFAULT 'pending',
                    publish_mode      TEXT    DEFAULT 'auto',
                    selected_channels TEXT    DEFAULT '[]',
                    category          TEXT    DEFAULT 'Genel',
                    created_at        TEXT    DEFAULT CURRENT_TIMESTAMP,
                    approved_at       TEXT,
                    finished_at       TEXT,
                    FOREIGN KEY (advertiser_id) REFERENCES users(user_id)
                );

                CREATE TABLE IF NOT EXISTS ad_sends (
                    send_id      INTEGER PRIMARY KEY AUTOINCREMENT,
                    ad_id        INTEGER NOT NULL,
                    channel_id   INTEGER NOT NULL,
                    message_id   INTEGER,
                    views_count  INTEGER DEFAULT 0,
                    earned_try   REAL    DEFAULT 0,
                    sent_at      TEXT    DEFAULT CURRENT_TIMESTAMP,
                    updated_at   TEXT    DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (ad_id)      REFERENCES ads(ad_id),
                    FOREIGN KEY (channel_id) REFERENCES channels(channel_id)
                );

                CREATE TABLE IF NOT EXISTS payments (
                    payment_id   INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id      INTEGER NOT NULL,
                    ad_id        INTEGER,
                    amount_try   REAL,
                    amount_crypto REAL,
                    crypto_type  TEXT,
                    wallet       TEXT,
                    tx_hash      TEXT,
                    status       TEXT DEFAULT 'pending',
                    created_at   TEXT DEFAULT CURRENT_TIMESTAMP,
                    confirmed_at TEXT,
                    FOREIGN KEY (user_id) REFERENCES users(user_id)
                );

                CREATE TABLE IF NOT EXISTS withdrawals (
                    wd_id         INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id       INTEGER NOT NULL,
                    amount_try    REAL,
                    amount_crypto REAL,
                    crypto_type   TEXT,
                    wallet        TEXT,
                    status        TEXT DEFAULT 'pending',
                    created_at    TEXT DEFAULT CURRENT_TIMESTAMP,
                    processed_at  TEXT,
                    FOREIGN KEY (user_id) REFERENCES users(user_id)
                );

                CREATE TABLE IF NOT EXISTS referrals (
                    ref_id       INTEGER PRIMARY KEY AUTOINCREMENT,
                    referrer_id  INTEGER NOT NULL,
                    referred_id  INTEGER NOT NULL UNIQUE,
                    earned_try   REAL DEFAULT 0,
                    created_at   TEXT DEFAULT CURRENT_TIMESTAMP
                );
            """)
            await db.commit()

    # ═══════════════════════════════════════════════════════════
    #  USERS
    # ═══════════════════════════════════════════════════════════
    async def get_user(self, user_id: int) -> Optional[Dict]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("SELECT * FROM users WHERE user_id=?", (user_id,)) as c:
                row = await c.fetchone()
                return dict(row) if row else None

    async def upsert_user(self, user_id: int, username: str, full_name: str, ref_by: int = None):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "INSERT OR IGNORE INTO users (user_id, username, full_name, ref_by) VALUES (?,?,?,?)",
                (user_id, username or "", full_name, ref_by)
            )
            await db.execute(
                "UPDATE users SET username=?, full_name=? WHERE user_id=?",
                (username or "", full_name, user_id)
            )
            await db.commit()
        if ref_by and ref_by != user_id:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute(
                    "INSERT OR IGNORE INTO referrals (referrer_id, referred_id) VALUES (?,?)",
                    (ref_by, user_id)
                )
                await db.commit()

    async def update_balance(self, user_id: int, delta: float):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "UPDATE users SET balance_try=balance_try+?, earned_try=earned_try+MAX(0,?) WHERE user_id=?",
                (delta, delta, user_id)
            )
            await db.commit()

    async def get_stats(self) -> Dict:
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute("SELECT COUNT(*) FROM users") as c:
                users = (await c.fetchone())[0]
            async with db.execute("SELECT COUNT(*) FROM channels WHERE is_approved=1") as c:
                channels = (await c.fetchone())[0]
            async with db.execute("SELECT COUNT(*) FROM ads WHERE status='active'") as c:
                active_ads = (await c.fetchone())[0]
            async with db.execute("SELECT COUNT(*) FROM ads WHERE status='pending'") as c:
                pending_ads = (await c.fetchone())[0]
            async with db.execute("SELECT COALESCE(SUM(spent_try),0) FROM ads") as c:
                revenue = (await c.fetchone())[0]
        return dict(users=users, channels=channels, active_ads=active_ads,
                    pending_ads=pending_ads, revenue=revenue)

    async def get_all_user_ids(self) -> List[int]:
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute("SELECT user_id FROM users WHERE is_banned=0") as c:
                return [r[0] for r in await c.fetchall()]

    # ═══════════════════════════════════════════════════════════
    #  CHANNELS
    # ═══════════════════════════════════════════════════════════
    async def add_channel(self, channel_id: int, owner_id: int, username: str,
                          title: str, member_count: int, category: str = "Genel"):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """INSERT OR REPLACE INTO channels
                   (channel_id, owner_id, username, title, member_count, category)
                   VALUES (?,?,?,?,?,?)""",
                (channel_id, owner_id, username, title, member_count, category)
            )
            await db.commit()

    async def get_channel(self, channel_id: int) -> Optional[Dict]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("SELECT * FROM channels WHERE channel_id=?", (channel_id,)) as c:
                row = await c.fetchone()
                return dict(row) if row else None

    async def get_approved_channels(self) -> List[Dict]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT * FROM channels WHERE is_approved=1 AND is_active=1 ORDER BY member_count DESC"
            ) as c:
                return [dict(r) for r in await c.fetchall()]

    async def get_pending_channels(self) -> List[Dict]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                """SELECT c.*, u.full_name as owner_name, u.username as owner_username
                   FROM channels c JOIN users u ON c.owner_id=u.user_id
                   WHERE c.is_approved=0 ORDER BY c.added_at DESC"""
            ) as c:
                return [dict(r) for r in await c.fetchall()]

    async def get_owner_channels(self, owner_id: int) -> List[Dict]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT * FROM channels WHERE owner_id=? ORDER BY added_at DESC", (owner_id,)
            ) as c:
                return [dict(r) for r in await c.fetchall()]

    async def approve_channel(self, channel_id: int):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("UPDATE channels SET is_approved=1 WHERE channel_id=?", (channel_id,))
            await db.commit()

    async def reject_channel(self, channel_id: int):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("UPDATE channels SET is_active=0 WHERE channel_id=?", (channel_id,))
            await db.commit()

    async def update_channel_members(self, channel_id: int, count: int):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("UPDATE channels SET member_count=? WHERE channel_id=?", (count, channel_id))
            await db.commit()

    # ═══════════════════════════════════════════════════════════
    #  ADS
    # ═══════════════════════════════════════════════════════════
    async def create_ad(self, data: dict) -> int:
        async with aiosqlite.connect(self.db_path) as db:
            cur = await db.execute(
                """INSERT INTO ads
                   (advertiser_id, title, content, photo_file_id, button_text, button_url,
                    budget_try, target_views, publish_mode, selected_channels, category)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                (data["advertiser_id"], data["title"], data["content"],
                 data.get("photo_file_id"), data.get("button_text"), data.get("button_url"),
                 data["budget_try"], data["target_views"],
                 data.get("publish_mode", "auto"),
                 json.dumps(data.get("selected_channels", [])),
                 data.get("category", "Genel"))
            )
            await db.commit()
            return cur.lastrowid

    async def get_ad(self, ad_id: int) -> Optional[Dict]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("SELECT * FROM ads WHERE ad_id=?", (ad_id,)) as c:
                row = await c.fetchone()
                if row:
                    d = dict(row)
                    d["selected_channels"] = json.loads(d["selected_channels"] or "[]")
                    return d
                return None

    async def get_pending_ads(self) -> List[Dict]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                """SELECT a.*, u.full_name as adv_name, u.username as adv_username
                   FROM ads a JOIN users u ON a.advertiser_id=u.user_id
                   WHERE a.status='pending' ORDER BY a.created_at ASC"""
            ) as c:
                rows = [dict(r) for r in await c.fetchall()]
                for r in rows:
                    r["selected_channels"] = json.loads(r["selected_channels"] or "[]")
                return rows

    async def get_active_ads(self) -> List[Dict]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("SELECT * FROM ads WHERE status='active'") as c:
                rows = [dict(r) for r in await c.fetchall()]
                for r in rows:
                    r["selected_channels"] = json.loads(r["selected_channels"] or "[]")
                return rows

    async def get_user_ads(self, user_id: int) -> List[Dict]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT * FROM ads WHERE advertiser_id=? ORDER BY created_at DESC", (user_id,)
            ) as c:
                rows = [dict(r) for r in await c.fetchall()]
                for r in rows:
                    r["selected_channels"] = json.loads(r["selected_channels"] or "[]")
                return rows

    async def approve_ad(self, ad_id: int):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "UPDATE ads SET status='active', approved_at=CURRENT_TIMESTAMP WHERE ad_id=?",
                (ad_id,)
            )
            await db.commit()

    async def reject_ad(self, ad_id: int):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("UPDATE ads SET status='rejected' WHERE ad_id=?", (ad_id,))
            await db.commit()

    async def finish_ad(self, ad_id: int):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "UPDATE ads SET status='finished', finished_at=CURRENT_TIMESTAMP WHERE ad_id=?",
                (ad_id,)
            )
            await db.commit()

    async def add_ad_views(self, ad_id: int, views: int, spent: float) -> bool:
        """Returns True if ad is now finished"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "UPDATE ads SET actual_views=actual_views+?, spent_try=spent_try+? WHERE ad_id=?",
                (views, spent, ad_id)
            )
            await db.commit()
            async with db.execute(
                "SELECT actual_views, target_views FROM ads WHERE ad_id=?", (ad_id,)
            ) as c:
                row = await c.fetchone()
                if row and row[0] >= row[1]:
                    await db.execute(
                        "UPDATE ads SET status='finished', finished_at=CURRENT_TIMESTAMP WHERE ad_id=?",
                        (ad_id,)
                    )
                    await db.commit()
                    return True
        return False

    # ═══════════════════════════════════════════════════════════
    #  AD SENDS
    # ═══════════════════════════════════════════════════════════
    async def log_ad_send(self, ad_id: int, channel_id: int, message_id: int) -> int:
        async with aiosqlite.connect(self.db_path) as db:
            cur = await db.execute(
                "INSERT INTO ad_sends (ad_id, channel_id, message_id) VALUES (?,?,?)",
                (ad_id, channel_id, message_id)
            )
            await db.commit()
            return cur.lastrowid

    async def get_active_sends(self) -> List[Dict]:
        """Aktif reklamların gönderim kayıtları"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                """SELECT s.*, a.budget_try, a.target_views, a.actual_views, a.spent_try,
                          a.status as ad_status, c.owner_id
                   FROM ad_sends s
                   JOIN ads a ON s.ad_id=a.ad_id
                   JOIN channels c ON s.channel_id=c.channel_id
                   WHERE a.status='active'"""
            ) as c:
                return [dict(r) for r in await c.fetchall()]

    async def update_send_views(self, send_id: int, views: int, earned: float):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "UPDATE ad_sends SET views_count=?, earned_try=?, updated_at=CURRENT_TIMESTAMP WHERE send_id=?",
                (views, earned, send_id)
            )
            await db.commit()

    async def channel_send_exists(self, ad_id: int, channel_id: int) -> bool:
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(
                "SELECT 1 FROM ad_sends WHERE ad_id=? AND channel_id=?", (ad_id, channel_id)
            ) as c:
                return bool(await c.fetchone())

    async def get_channel_total_earnings(self, channel_id: int) -> float:
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(
                "SELECT COALESCE(SUM(earned_try),0) FROM ad_sends WHERE channel_id=?", (channel_id,)
            ) as c:
                return (await c.fetchone())[0]

    # ═══════════════════════════════════════════════════════════
    #  PAYMENTS
    # ═══════════════════════════════════════════════════════════
    async def create_payment(self, user_id: int, ad_id: int, amount_try: float,
                             amount_crypto: float, crypto_type: str, wallet: str) -> int:
        async with aiosqlite.connect(self.db_path) as db:
            cur = await db.execute(
                """INSERT INTO payments
                   (user_id, ad_id, amount_try, amount_crypto, crypto_type, wallet)
                   VALUES (?,?,?,?,?,?)""",
                (user_id, ad_id, amount_try, amount_crypto, crypto_type, wallet)
            )
            await db.commit()
            return cur.lastrowid

    async def get_payment(self, payment_id: int) -> Optional[Dict]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT p.*, u.full_name, u.username FROM payments p JOIN users u ON p.user_id=u.user_id WHERE p.payment_id=?",
                (payment_id,)
            ) as c:
                row = await c.fetchone()
                return dict(row) if row else None

    async def get_pending_payments(self) -> List[Dict]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                """SELECT p.*, u.full_name, u.username
                   FROM payments p JOIN users u ON p.user_id=u.user_id
                   WHERE p.status='pending' ORDER BY p.created_at ASC"""
            ) as c:
                return [dict(r) for r in await c.fetchall()]

    async def confirm_payment(self, payment_id: int, tx_hash: str = ""):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "UPDATE payments SET status='confirmed', tx_hash=?, confirmed_at=CURRENT_TIMESTAMP WHERE payment_id=?",
                (tx_hash, payment_id)
            )
            await db.commit()

    async def reject_payment(self, payment_id: int):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("UPDATE payments SET status='rejected' WHERE payment_id=?", (payment_id,))
            await db.commit()

    # ═══════════════════════════════════════════════════════════
    #  WITHDRAWALS
    # ═══════════════════════════════════════════════════════════
    async def create_withdrawal(self, user_id: int, amount_try: float,
                                amount_crypto: float, crypto_type: str, wallet: str) -> int:
        async with aiosqlite.connect(self.db_path) as db:
            cur = await db.execute(
                "INSERT INTO withdrawals (user_id, amount_try, amount_crypto, crypto_type, wallet) VALUES (?,?,?,?,?)",
                (user_id, amount_try, amount_crypto, crypto_type, wallet)
            )
            await db.commit()
            return cur.lastrowid

    async def get_pending_withdrawals(self) -> List[Dict]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                """SELECT w.*, u.full_name, u.username
                   FROM withdrawals w JOIN users u ON w.user_id=u.user_id
                   WHERE w.status='pending' ORDER BY w.created_at ASC"""
            ) as c:
                return [dict(r) for r in await c.fetchall()]

    async def process_withdrawal(self, wd_id: int):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "UPDATE withdrawals SET status='processed', processed_at=CURRENT_TIMESTAMP WHERE wd_id=?",
                (wd_id,)
            )
            await db.commit()

    # ═══════════════════════════════════════════════════════════
    #  REFERRALS
    # ═══════════════════════════════════════════════════════════
    async def add_referral_earning(self, referrer_id: int, referred_id: int, amount: float):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "UPDATE referrals SET earned_try=earned_try+? WHERE referrer_id=? AND referred_id=?",
                (amount, referrer_id, referred_id)
            )
            await db.commit()

    async def get_referral_stats(self, user_id: int) -> Dict:
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(
                "SELECT COUNT(*), COALESCE(SUM(earned_try),0) FROM referrals WHERE referrer_id=?",
                (user_id,)
            ) as c:
                row = await c.fetchone()
                return {"count": row[0], "total_earned": row[1]}

    async def get_referrer(self, user_id: int) -> Optional[int]:
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute("SELECT ref_by FROM users WHERE user_id=?", (user_id,)) as c:
                row = await c.fetchone()
                return row[0] if row else None
