"""The casino games Otto can play with the gamble tool. Pure rules: no database, no money moves (sprocket/bank.py does those).

Each play(game, choice, rng) returns (multiplier, text): the stake comes back multiplied (0 = lost it, 1 = pushed / got it back, 2 = doubled...).
The house always has a small edge, like a real casino (roulette 2.7%, the others 2-8%), so over many bets he drifts down; `rtp` below checks it.
"""
import random

GAMES = {
    "slots": "three reels; no choice needed. Matching symbols pay, a pair of cherries pays a little.",
    "roulette": "choice: red, black, odd, even, low (1-18), high (19-36) pay double; or a number 0-36 pays 36 times.",
    "blackjack": "choice: the total you stand on (12-20, default 17). Beat the dealer without going over 21; blackjack pays 2.5 times.",
    "dice": "two dice. choice: over (8+) or under (6 or less) pay 2.3 times; seven pays 5 times.",
}

REELS = ("cherry", "lemon", "plum", "bell", "bar", "seven")
WEIGHTS = (8, 7, 6, 4, 2, 1)
TRIPLE = {"cherry": 7, "lemon": 9, "plum": 13, "bell": 26, "bar": 70, "seven": 250}
RED = {1, 3, 5, 7, 9, 12, 14, 16, 18, 19, 21, 23, 25, 27, 30, 32, 34, 36}


def slots(rng, choice=None):
    r = rng.choices(REELS, weights=WEIGHTS, k=3)
    txt = " | ".join(r)
    if r[0] == r[1] == r[2]:
        return TRIPLE[r[0]], f"{txt}: three " + ("cherries" if r[0] == "cherry" else r[0] + "s") + "!"
    if r.count("cherry") == 2:
        return 2, f"{txt}: a pair of cherries."
    return 0, f"{txt}: nothing."


def roulette(rng, choice=None):
    n = rng.randint(0, 36)
    colour = "green" if n == 0 else "red" if n in RED else "black"
    spin = f"The ball lands on {n} ({colour})."
    c = str(choice or "red").strip().lower()
    if c.isdigit() and 0 <= int(c) <= 36:
        return (36, spin + f" Your number {c} came up!") if int(c) == n else (0, spin + f" You bet on {c}.")
    wins = {"red": colour == "red", "black": colour == "black", "odd": n % 2 == 1, "even": n != 0 and n % 2 == 0, "low": 1 <= n <= 18, "high": 19 <= n <= 36}
    if c not in wins:
        c = "red"
    return (2, spin + f" You bet {c} and won.") if wins[c] else (0, spin + f" You bet {c} and lost.")


def _hand_value(cards):
    t, aces = sum(cards), cards.count(11)
    while t > 21 and aces:
        t -= 10
        aces -= 1
    return t


def blackjack(rng, choice=None):
    try:
        stand = max(12, min(20, int(str(choice).strip())))
    except (TypeError, ValueError):
        stand = 17
    deck = [min(r, 10) if r > 1 else 11 for r in range(1, 14)] * 4
    rng.shuffle(deck)
    you, dealer = [deck.pop(), deck.pop()], [deck.pop(), deck.pop()]
    if _hand_value(you) == 21:
        if _hand_value(dealer) == 21:
            return 1, f"You: {you} and the dealer: {dealer}. Both blackjack, you get your bet back."
        return 2.5, f"You: {you}. Blackjack!"
    while _hand_value(you) < stand:
        you.append(deck.pop())
    yv = _hand_value(you)
    if yv > 21:
        return 0, f"You stood on {stand} but drew to {you} = {yv}: bust."
    while _hand_value(dealer) < 17:
        dealer.append(deck.pop())
    dv = _hand_value(dealer)
    desc = f"You: {you} = {yv}. Dealer: {dealer} = {dv}."
    if dv > 21 or yv > dv:
        return 2, desc + " You win."
    if yv == dv:
        return 1, desc + " A push: bet back."
    return 0, desc + " The dealer wins."


def dice(rng, choice=None):
    a, b = rng.randint(1, 6), rng.randint(1, 6)
    t = a + b
    c = str(choice or "over").strip().lower()
    if c not in ("over", "under", "seven"):
        c = "over"
    desc = f"The dice show {a} and {b} = {t}."
    if c == "seven":
        return (5, desc + " Seven, as you called!") if t == 7 else (0, desc + " Not seven.")
    if (c == "over" and t >= 8) or (c == "under" and t <= 6):
        return 2.3, desc + f" You called {c}: win."
    return 0, desc + f" You called {c}: lose."


PLAY = {"slots": slots, "roulette": roulette, "blackjack": blackjack, "dice": dice}


def play(game, choice=None, rng=random):
    if game not in PLAY:
        raise ValueError("Games: " + ", ".join(GAMES))
    return PLAY[game](rng, choice)


def rtp(game, choice=None, n=200_000, seed=1):
    """Return-to-player over n plays (1.0 = fair; below 1 = house edge)."""
    rng = random.Random(seed)
    return sum(play(game, choice, rng)[0] for _ in range(n)) / n
