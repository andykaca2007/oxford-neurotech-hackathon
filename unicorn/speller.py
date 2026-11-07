"""Four-tile speller with word prediction.

Three looks spell one letter: tiles 1 to 3 hold letter groups, then sub-groups, then letters.
Tile 4 is always the "smart" tile: the most likely word for the letters typed so far (one look
accepts it and speaks the word), or SPACE when nothing is typed, or BACK one level up inside a
letter. Prediction = most frequent English word with that prefix (wordfreq top 30 000, offline).

    python unicorn/speller.py          # types "app" and shows what each tile offers at every step

State machine like phrase_tree.PhraseTree: feed select(tile, now), poll labels(), prompt().
"""
from __future__ import annotations

import time

try:
    from wordfreq import top_n_list
    _WORDS = top_n_list("en", 30000)
except Exception:  # wordfreq missing: a tiny fallback so the screen still runs
    _WORDS = ["the", "and", "you", "water", "please", "help", "apple", "nurse", "pain", "yes", "no", "toilet"]

LETTERS = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
# level 1: 3 groups of 9/9/8 letters; level 2: each group splits in 3; level 3: single letters
GROUPS = [LETTERS[0:9], LETTERS[9:18], LETTERS[18:26]]


def _split3(s: str) -> list[str]:
    n = len(s)
    a, b = (n + 2) // 3, (2 * n + 2) // 3
    return [s[:a], s[a:b], s[b:]]


def predict(prefix: str, k: int = 1) -> list[str]:
    """Most frequent words starting with prefix (case-insensitive), longest-first on ties."""
    p = prefix.lower()
    if not p:
        return []
    out = [w for w in _WORDS if w.startswith(p) and w != p]
    return [w.upper() for w in out[:k]]


class Speller:
    def __init__(self, timeout_s: float = 12.0):
        self.text = ""          # finished words, spaces between
        self.word = ""          # letters of the current word
        self.level = 0          # 0 = groups, 1 = sub-groups, 2 = letters
        self.choice: str = ""   # letters still in play at this level
        self.timeout_s = timeout_s
        self.last_t = -1e9
        self.said: str | None = None

    # ---- what the four tiles show ----
    def labels(self) -> list[str]:
        if self.level == 0:
            opts = [f"{g[0]}-{g[-1]}" for g in GROUPS]
            smart = (predict(self.word) or ["SPACE" if self.word else "SPACE"])[0] if self.word else "SPACE"
        elif self.level == 1:
            parts = _split3(self.choice)
            opts = [f"{p[0]}-{p[-1]}" if len(p) > 1 else p for p in parts]
            smart = "BACK"
        else:
            parts = list(self.choice) + ["", "", ""]
            opts = parts[:3]
            smart = "BACK"
        return opts + [smart]

    def prompt(self) -> str:
        pred = predict(self.word)
        hint = f"   guess: {pred[0]}" if pred else ""
        return f"{self.text} {self.word}_{hint}".strip()

    # ---- a look ----
    def select(self, tile: int, now: float) -> str | None:
        """Returns a word to speak when one is completed, else None."""
        self.last_t = now
        self.said = None
        if self.level == 0:
            if tile == 3:
                if self.word:
                    pred = predict(self.word)
                    word = pred[0] if pred else self.word
                    return self._finish(word)
                return None  # SPACE with nothing typed: ignore
            self.choice = GROUPS[tile]
            self.level = 1
        elif self.level == 1:
            if tile == 3:
                self.level = 0
                return None
            parts = _split3(self.choice)
            self.choice = parts[tile]
            self.level = 2 if len(self.choice) > 1 else 0
            if len(self.choice) == 1:
                self.word += self.choice
                self.level = 0
        else:
            if tile == 3:
                self.level = 1
                self.choice = next(g for g in GROUPS if self.choice[0] in g)
                return None
            parts = list(self.choice)
            if tile < len(parts):
                self.word += parts[tile]
            self.level = 0
        return None

    def _finish(self, word: str) -> str:
        self.text = (self.text + " " + word).strip()
        self.word = ""
        self.level = 0
        self.said = word
        return word

    def tick(self, now: float) -> bool:
        """Back to the top level if a letter was left half-chosen too long."""
        if self.level and now - self.last_t > self.timeout_s:
            self.level = 0
            return True
        return False


if __name__ == "__main__":
    sp = Speller()
    t = time.monotonic()
    print("tiles:", sp.labels())
    for tile in [0, 0, 0,   1, 2, 0,   1, 2, 0]:   # A, P, P  (A-I > A-C > A ; J-R > P-R > P ; again)
        said = sp.select(tile, t)
        print(f"look tile {tile} -> {sp.prompt()!r}   tiles now: {sp.labels()}")
    said = sp.select(3, t)
    print("accept smart tile ->", said, "| text:", sp.text)
