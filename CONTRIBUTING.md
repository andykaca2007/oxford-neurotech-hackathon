# How we work in this repo (hackathon rules, kept short)

- `main` is always runnable. Nobody commits to `main` directly.
- One branch per change, named `yourname/what-it-does`, e.g. `paing/speak-flag`.
- Open a pull request as soon as the branch exists, even if it is not finished. Title = what
  changes, body = how you tested it (fake, replay, or live headset). Draft PRs are fine.
- One teammate reviews, then "Squash and merge". Delete the branch after merging.
- Before you push: `python -m pytest tests` passes, and `python explored/ssvep/ssvep_decode.py --fake --seconds 20` still prints scores.
- Never commit: `.venv/`, `data/nakanishi2015/`, `models/`, `recordings/`, raw CSVs, videos.
  `.gitignore` already covers them; if git shows one of these as untracked, stop and ask.
- Pull `main` before starting a branch: `git checkout main && git pull`.
- Commit messages say what and why in one line, present tense: "Add --speak so a phrase is
  spoken aloud when no wristband is present".
- Code freeze: Sunday 13:00. After that only README and slides change.
