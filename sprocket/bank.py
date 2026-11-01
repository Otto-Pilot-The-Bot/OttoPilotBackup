"""Otto's money: a small double-entry ledger in USD, kept in whole cents.

Accounts (plain strings):
    mint          where play money comes from. Only the HUMAN can move money out of it (grants). May go negative.
    otto:wallet   cash Otto carries.
    otto:bank     his account at the bank.

Rules that keep it honest (and make it safe to swap for real money later):
- Integer cents only, never floats.  One currency (USD), stored on every row.
- Append-only: database triggers refuse UPDATE and DELETE on the ledger. To undo something, post a reversing entry.
- Every entry has an idempotency key, so a retried request can never be applied twice.
- Real accounts cannot go below zero; only `mint` can.
- Otto's tools only ever move money between his OWN two accounts (deposit / withdraw). Money entering or leaving the system
  (grants, and in future real top-ups or cash-outs) is human-only and goes through `grant` / a Provider.

Real money later: the ledger is the source of truth, a Provider is the thing that talks to the outside world.
PlayMoneyProvider (the default) just mints. A real provider would implement the same three methods, create a PENDING request that
the human approves, and only then post to the ledger. RealMoneyProvider below is a switched-off stub: config.BANK_REAL_ENABLED
is False and nothing in the project turns it on.
"""
import re
import time
from decimal import Decimal, InvalidOperation

from . import config

CURRENCY = "USD"
MINT, WALLET, ACCOUNT = "mint", "otto:wallet", "otto:bank"
ACCOUNTS = (MINT, WALLET, ACCOUNT)

SCHEMA = """
CREATE TABLE IF NOT EXISTS bank_ledger(id INTEGER PRIMARY KEY, ts REAL, tick INT, kind TEXT, src TEXT NOT NULL, dst TEXT NOT NULL,
  cents INTEGER NOT NULL CHECK(cents > 0), currency TEXT NOT NULL DEFAULT 'USD', memo TEXT, actor TEXT, idem TEXT UNIQUE, provider TEXT);
CREATE TRIGGER IF NOT EXISTS bank_ledger_no_update BEFORE UPDATE ON bank_ledger BEGIN SELECT RAISE(ABORT, 'ledger is append-only'); END;
CREATE TRIGGER IF NOT EXISTS bank_ledger_no_delete BEFORE DELETE ON bank_ledger BEGIN SELECT RAISE(ABORT, 'ledger is append-only'); END;
"""


class BankError(ValueError):
    """A refused transaction. The message is safe to show to Otto or to the human."""


# ---------------------------------------------------------------- amounts
def parse_amount(v):
    """'12', 12, '$12.50', '1,200.5' -> cents. Refuses negatives, zero, more than 2 decimals, junk, and absurdly big numbers."""
    if isinstance(v, bool) or v is None:
        raise BankError("Say how much, for example 5 or 12.50.")
    s = str(v).strip().replace("$", "").replace(",", "").replace("usd", "").replace("USD", "").strip()
    if not re.fullmatch(r"\d+(\.\d+)?", s):
        raise BankError("That is not an amount of money. Use a plain positive number like 5 or 12.50.")
    try:
        d = Decimal(s)
    except InvalidOperation:
        raise BankError("That is not an amount of money.")
    if d != d.quantize(Decimal("0.01")):
        raise BankError("Money only goes down to cents (two decimals).")
    cents = int(d * 100)
    if cents <= 0:
        raise BankError("The amount must be more than zero.")
    if cents > config.BANK_MAX_TXN_CENTS:
        raise BankError(f"That is more than one transaction may move (limit {fmt(config.BANK_MAX_TXN_CENTS)}).")
    return cents


def fmt(cents):
    sign = "-" if cents < 0 else ""
    c = abs(int(cents))
    return f"{sign}${c // 100:,}.{c % 100:02d}"


# ---------------------------------------------------------------- ledger
def setup(db):
    db.c.executescript(SCHEMA)
    db.c.commit()


def balance(db, acct):
    r = db.one("SELECT COALESCE(SUM(CASE WHEN dst=? THEN cents ELSE 0 END),0) - COALESCE(SUM(CASE WHEN src=? THEN cents ELSE 0 END),0) b FROM bank_ledger", acct, acct)
    return int(r["b"])


def balances(db):
    return {"wallet": balance(db, WALLET), "account": balance(db, ACCOUNT), "currency": CURRENCY}


def post(db, src, dst, cents, kind, memo="", actor="system", idem=None, tick=0, provider="play"):
    """The only writer. Atomic: checks funds and inserts in one transaction. Returns the new row id (or the existing one for a repeated idem key)."""
    if src not in ACCOUNTS or dst not in ACCOUNTS or src == dst:
        raise BankError("Unknown account.")
    if not isinstance(cents, int) or cents <= 0:
        raise BankError("The amount must be a positive number of cents.")
    if idem:
        old = db.one("SELECT id FROM bank_ledger WHERE idem=?", idem)
        if old:
            return old["id"]
    c = db.c
    try:
        c.execute("BEGIN IMMEDIATE")
        if src != MINT:
            have = c.execute("SELECT COALESCE(SUM(CASE WHEN dst=? THEN cents ELSE 0 END),0) - COALESCE(SUM(CASE WHEN src=? THEN cents ELSE 0 END),0) FROM bank_ledger", (src, src)).fetchone()[0]
            if have < cents:
                c.execute("ROLLBACK")
                raise BankError(f"Not enough money: there is {fmt(have)} and that needs {fmt(cents)}.")
        cur = c.execute("INSERT INTO bank_ledger(ts,tick,kind,src,dst,cents,currency,memo,actor,idem,provider) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                        (time.time(), tick, kind, src, dst, cents, CURRENCY, (memo or "")[:200], actor, idem, provider))
        c.execute("COMMIT")
        return cur.lastrowid
    except BankError:
        raise
    except Exception:
        try:
            c.execute("ROLLBACK")
        except Exception:
            pass
        raise


def recent(db, n=30):
    return db.q("SELECT id,ts,tick,kind,src,dst,cents,memo,actor FROM bank_ledger ORDER BY id DESC LIMIT ?", n)


def audit(db):
    """Money is only moved, never made out of thin air: everything in Otto's accounts must equal what the mint paid out."""
    mint = balance(db, MINT)
    return {"ok": mint + balance(db, WALLET) + balance(db, ACCOUNT) == 0, "mint": mint, **balances(db)}


# ---------------------------------------------------------------- Otto's side (his own two accounts only)
def deposit(db, cents, tick=0, idem=None):
    post(db, WALLET, ACCOUNT, cents, "deposit", "Otto deposited cash", actor="otto", tick=tick, idem=idem)
    return balances(db)


def withdraw(db, cents, tick=0, idem=None):
    post(db, ACCOUNT, WALLET, cents, "withdraw", "Otto withdrew cash", actor="otto", tick=tick, idem=idem)
    return balances(db)


# ---------------------------------------------------------------- the human's side
def grant(db, cents, memo="Gift from your human", tick=0, to=WALLET):
    """Human only (called from the page's WebSocket handler, never from a model tool)."""
    if to not in (WALLET, ACCOUNT):
        raise BankError("Unknown account.")
    post(db, MINT, to, cents, "grant", memo, actor="human", tick=tick)
    return balances(db)


def take_back(db, cents, memo="Taken back by your human", tick=0):
    """Human only: the opposite of a grant. Takes from the wallet first, then the account."""
    w = balance(db, WALLET)
    from_w = min(w, cents)
    if from_w + balance(db, ACCOUNT) < cents:
        raise BankError("He does not have that much.")
    if from_w:
        post(db, WALLET, MINT, from_w, "take_back", memo, actor="human", tick=tick)
    if cents - from_w:
        post(db, ACCOUNT, MINT, cents - from_w, "take_back", memo, actor="human", tick=tick)
    return balances(db)


def ensure_start(db):
    """Give Otto his starting cash once."""
    if db.get("bank_started"):
        return
    if config.BANK_START_CENTS > 0:
        post(db, MINT, WALLET, config.BANK_START_CENTS, "grant", "Starting cash", actor="system", idem="start")
    db.put("bank_started", True)


# ---------------------------------------------------------------- providers (for later; nothing here touches the outside world)
class Provider:
    name = "base"

    def top_up(self, db, cents, memo=""):
        raise NotImplementedError

    def cash_out(self, db, cents, memo=""):
        raise NotImplementedError

    def status(self):
        return {"provider": self.name, "real_money": False}


class PlayMoneyProvider(Provider):
    name = "play"

    def top_up(self, db, cents, memo=""):
        return grant(db, cents, memo or "Play money top-up")

    def cash_out(self, db, cents, memo=""):
        raise BankError("Play money cannot be cashed out.")


class RealMoneyProvider(Provider):
    """Placeholder for a real payment service. Deliberately does nothing. To use it later: implement top_up/cash_out against the
    service, make each one create a PENDING request that the human approves in the Bank panel, post to the ledger only after
    approval, and set config.BANK_REAL_ENABLED. Keep Otto's tools limited to deposit/withdraw between his own accounts."""
    name = "real"

    def top_up(self, db, cents, memo=""):
        raise BankError("Real money is switched off.")

    def cash_out(self, db, cents, memo=""):
        raise BankError("Real money is switched off.")


def provider():
    return RealMoneyProvider() if (config.BANK_PROVIDER == "real" and config.BANK_REAL_ENABLED) else PlayMoneyProvider()
