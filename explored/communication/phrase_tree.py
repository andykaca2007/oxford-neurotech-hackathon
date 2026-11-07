"""Fixed 16-phrase tree: two looks per phrase.

Look 1 opens a group (four tiles = four groups). Look 2 picks a phrase inside that group
(the same four tiles now show four phrases). The phrase goes to the carer, and the tree
goes back to the four groups.

    python explored/communication/phrase_tree.py          # prints the tree and which two tiles say each phrase

Why a fixed tree and not a runtime LLM (see EXPERT_PANEL_2026-11-07.md): every phrase is
known in advance, so we can test every path, and the decoder's accuracy is the only thing
that decides what gets said.

Safety rules built in:
  - After the first look, the user has `timeout_s` seconds to make the second. If no second
    look comes, the tree goes back to the groups. So one stray pick (noise, a glance, alpha
    during rest) only opens a group; saying a phrase needs two picks in a row.
  - Nothing is said until the second look, so a wrong group costs time, not a wrong message.

Tile order matters: tile i always flickers at the same frequency (ssvep_stim.py TILES:
7.5, 8.57, 10, 12 Hz), so group i and phrase i always sit on that tile. The 10 Hz tile
overlaps the eyes-closed alpha rhythm (8 to 12 Hz); check the rest-run false picks per
tile before deciding which phrases sit there.

Edit TREE freely: it must stay 4 groups x 4 phrases, and every phrase must be unique.
"""
from __future__ import annotations

# (group label shown on the tile, [the 4 phrases in that group, in tile order])
TREE = [
    ("NEED", ["Water, please", "Something to eat", "Toilet, please", "Move me, please"]),
    ("BODY", ["I am in pain", "I am too hot", "I am too cold", "I am tired"]),
    ("PEOPLE", ["Call the nurse", "Call my family", "Please stay", "I want to be alone"]),
    ("ANSWER", ["Yes", "No", "I don't know", "Ask me later"]),
]

N_TILES = 4


def check_tree(tree) -> None:
    """Raise ValueError unless the tree is 4 groups of 4 unique phrases."""
    if len(tree) != N_TILES:
        raise ValueError(f"need {N_TILES} groups, got {len(tree)}")
    seen = set()
    for label, phrases in tree:
        if len(phrases) != N_TILES:
            raise ValueError(f"group {label!r} needs {N_TILES} phrases, got {len(phrases)}")
        for p in phrases:
            if p in seen:
                raise ValueError(f"phrase {p!r} appears twice; the log could not tell them apart")
            seen.add(p)


class PhraseTree:
    """State machine for two-look selection.

    Feed it the decoder's picks with select(tile, now) and call tick(now) regularly.
    Times are in seconds from any monotonic clock (time.monotonic() in the stim).
    """

    def __init__(self, tree=TREE, timeout_s: float = 8.0):
        check_tree(tree)
        self.tree = tree
        self.timeout_s = timeout_s
        self.group: int | None = None   # None = showing the four groups (the root)
        self.opened_t = 0.0             # when the current group was opened

    # -- what the screen shows ------------------------------------------------
    def labels(self) -> list[str]:
        """The four tile labels right now."""
        if self.group is None:
            return [label for label, _ in self.tree]
        return list(self.tree[self.group][1])

    def prompt(self, now: float) -> str:
        """One line telling the user what the next look does."""
        if self.group is None:
            return "Look at a group"
        left = max(0.0, self.timeout_s - (now - self.opened_t))
        return f"{self.tree[self.group][0]}: look at a phrase (back to groups in {left:.0f} s)"

    # -- input ----------------------------------------------------------------
    def select(self, tile: int, now: float) -> str | None:
        """Apply one decoder pick. Returns the phrase if this pick completed one, else None."""
        if not 0 <= tile < N_TILES:
            raise ValueError(f"tile must be 0..{N_TILES - 1}, got {tile}")
        self.tick(now)                  # a late second look counts as a new first look
        if self.group is None:
            self.group = tile
            self.opened_t = now
            return None
        phrase = self.tree[self.group][1][tile]
        self.group = None
        return phrase

    def tick(self, now: float) -> bool:
        """Go back to the groups if the second look is overdue. True if it just timed out."""
        if self.group is not None and now - self.opened_t > self.timeout_s:
            self.group = None
            return True
        return False

    def reset(self) -> None:
        self.group = None

    # -- helpers for replay and logging ---------------------------------------
    def path(self, phrase: str) -> tuple[int, int]:
        """The two tiles (group tile, phrase tile) that say `phrase`."""
        for g, (_, phrases) in enumerate(self.tree):
            if phrase in phrases:
                return g, phrases.index(phrase)
        raise KeyError(f"{phrase!r} is not in the tree")

    def group_of(self, phrase: str) -> int:
        return self.path(phrase)[0]

    def all_phrases(self) -> list[str]:
        return [p for _, phrases in self.tree for p in phrases]


if __name__ == "__main__":
    t = PhraseTree()
    names = ["tile 0 (7.5 Hz)", "tile 1 (8.57 Hz)", "tile 2 (10 Hz)", "tile 3 (12 Hz)"]
    for g, (label, phrases) in enumerate(TREE):
        print(f"{names[g]}: {label}")
        for p, phrase in enumerate(phrases):
            print(f"    then {names[p]}: {phrase}")
