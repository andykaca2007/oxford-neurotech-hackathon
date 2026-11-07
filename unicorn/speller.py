"""Speller with word prediction, for 4 or 12 tiles.

4 tiles:  three looks per letter (tiles 1-3 = letter ranges, then thirds, then letters);
          tile 4 = the predicted word (one look accepts and speaks it), SPACE, or BACK.
12 tiles: two looks per letter: level 0 shows nine letter triples (A-C ... Y-Z) plus the top
          two predicted words and SPACE; level 1 shows the three letters, BACK, and the
          predictions again. Letter about 2 looks, common word 1 look.

Prediction = most frequent English word with that prefix (wordfreq top 30 000, offline).

    python unicorn/speller.py          # spells "app" on both layouts and accepts the guess

State machine like phrase_tree.PhraseTree: select(tile, now) -> word or None, labels(), prompt().
"""
from __future__ import annotations

import time

try:
    from wordfreq import top_n_list
    _WORDS = top_n_list("en", 30000)
except Exception:  # wordfreq missing: a tiny fallback so the screen still runs
    _WORDS = ["the", "and", "you", "water", "please", "help", "apple", "nurse", "pain", "yes", "no", "toilet"]

LETTERS = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
GROUPS4 = [LETTERS[0:9], LETTERS[9:18], LETTERS[18:26]]
TRIPLES = [LETTERS[i:i + 3] for i in range(0, 26, 3)]   # 9 groups, last is "YZ"


def _split3(s: str) -> list[str]:
    n = len(s)
    a, b = (n + 2) // 3, (2 * n + 2) // 3
    return [s[:a], s[a:b], s[b:]]


def predict(prefix: str, k: int = 1) -> list[str]:
    """Most frequent words starting with prefix (case-insensitive), excluding the prefix itself."""
    p = prefix.lower()
    if not p:
        return []
    out = [w for w in _WORDS if w.startswith(p) and w != p]
    return [w.upper() for w in out[:k]]


def _rng(s: str) -> str:
    return s if len(s) <= 1 else f"{s[0]}-{s[-1]}"


class Speller:
    def __init__(self, n_tiles: int = 4, timeout_s: float = 12.0):
        if n_tiles not in (4, 12):
            raise ValueError("n_tiles must be 4 or 12")
        self.n = n_tiles
        self.text = ""
        self.word = ""
        self.level = 0
        self.choice = ""
        self.timeout_s = timeout_s
        self.last_t = -1e9
        self.said: str | None = None

    # ---- labels ----
    def labels(self) -> list[str]:
        if self.n == 4:
            return self._labels4()
        return self._labels12()

    def _labels4(self):
        if self.level == 0:
            opts = [_rng(g) for g in GROUPS4]
            pred = predict(self.word)
            smart = pred[0] if pred else "SPACE"
        elif self.level == 1:
            opts = [_rng(p) for p in _split3(self.choice)]
            smart = "BACK"
        else:
            opts = (list(self.choice) + ["", "", ""])[:3]
            smart = "BACK"
        return opts + [smart]

    def _labels12(self):
        pred = predict(self.word, 2) if self.word else []
        if self.level == 0:
            tiles = [_rng(t) for t in TRIPLES]                    # 9
            tiles += [pred[0] if len(pred) > 0 else "SPACE",
                      pred[1] if len(pred) > 1 else "",
                      "SPACE" if self.word else ""]
        else:
            tiles = (list(self.choice) + ["", "", ""])[:3] + ["BACK"]
            tiles += [pred[0] if len(pred) > 0 else "", pred[1] if len(pred) > 1 else ""]
            tiles += [""] * (12 - len(tiles))
        return tiles

    def prompt(self, *_args) -> str:
        pred = predict(self.word)
        hint = f"   guess: {pred[0]}" if pred else ""
        return f"{self.text} {self.word}_{hint}".strip()

    # ---- a look ----
    def select(self, tile: int, now: float) -> str | None:
        self.last_t = now
        self.said = None
        return self._select4(tile) if self.n == 4 else self._select12(tile)

    def _accept_pred(self, k: int = 0) -> str | None:
        pred = predict(self.word, 2)
        if self.word and len(pred) > k:
            return self._finish(pred[k])
        if self.word and k == 0:
            return self._finish(self.word)
        return None

    def _select4(self, tile):
        if self.level == 0:
            if tile == 3:
                return self._accept_pred(0)
            self.choice = GROUPS4[tile]
            self.level = 1
        elif self.level == 1:
            if tile == 3:
                self.level = 0
                return None
            self.choice = _split3(self.choice)[tile]
            if len(self.choice) == 1:
                self.word += self.choice
                self.level = 0
            else:
                self.level = 2
        else:
            if tile == 3:
                self.level = 1
                self.choice = next(g for g in GROUPS4 if self.choice[0] in g)
                return None
            parts = list(self.choice)
            if tile < len(parts):
                self.word += parts[tile]
            self.level = 0
        return None

    def _select12(self, tile):
        if self.level == 0:
            if tile < 9:
                self.choice = TRIPLES[tile]
                self.level = 1
                return None
            if tile == 9:
                return self._accept_pred(0) if self.word else None   # SPACE with nothing typed: ignore
            if tile == 10:
                return self._accept_pred(1)
            if tile == 11 and self.word:
                return self._finish(self.word)                        # SPACE: take the letters as typed
            return None
        # level 1
        if tile < 3:
            parts = list(self.choice)
            if tile < len(parts):
                self.word += parts[tile]
            self.level = 0
        elif tile == 3:
            self.level = 0
        elif tile in (4, 5):
            return self._accept_pred(tile - 4)
        return None

    def _finish(self, word: str) -> str:
        self.text = (self.text + " " + word).strip()
        self.word = ""
        self.level = 0
        self.said = word
        return word

    def tick(self, now: float) -> bool:
        if self.level and now - self.last_t > self.timeout_s:
            self.level = 0
            return True
        return False


if __name__ == "__main__":
    t = time.monotonic()
    sp = Speller(4)
    for tile in [0, 0, 0, 1, 2, 0, 1, 2, 0]:
        sp.select(tile, t)
    print("4 tiles after A,P,P:", sp.labels(), "->", sp.select(3, t))
    sp = Speller(12)
    for tile in [0, 0, 5, 0, 5, 0]:   # A-C > A ; P-R > P ; P-R > P
        sp.select(tile, t)
    print("12 tiles after A,P,P:", sp.labels()[9:11], "->", sp.select(9, t))
