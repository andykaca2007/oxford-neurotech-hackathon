# Presentation deck

A single web page: one slide per screen, every figure drawn live from real data (`data.json`) so it animates in.

    cd deck && python3 -m http.server 8790      # then open http://localhost:8790 and press F for fullscreen

Keys: right arrow or space = next, left = back, F = fullscreen. Click anywhere also advances.

Slides (hash `#n` jumps straight to one): 0 title (Team Avengers; the raw and cleaned traces draw themselves),
1 the problem (a head whose load trace spikes against a flat "nothing" line, then the alpha and theta shifts measured
in 36 lab people), 2 the solution (headset, the six-filter chain, a dial that swings to the real peak of 89),
3 opening numbers (raw vs cleaned trace, the load under arithmetic, three numbers), 4 video, 5 the six filters,
6 the spectrum, 7 how it works, 8 ROC, 9 training curve, 10 limitations (contact picture of the dry cap, 36 held-out
AUROCs one bar each), 11 what comes next. Each slide carries a small top-right tag naming the judging criterion it answers.

The video slide plays `deck/demo.mp4` (the 8 Nov recording, converted from the phone's HEVC to H.264 so browsers
play it: `ffmpeg -i in.MOV -vf scale=-2:1080 -c:v libx264 -crf 22 -pix_fmt yuv420p -movflags +faststart -c:a aac
deck/demo.mp4`). Without that file, drop a recording onto the slide or choose it with the button; it never leaves
the laptop. Before pressing play, say "a real recording from a public dataset, through our live system": nothing
on screen says it.

`data.json` is written by the export cell at the top of this folder's history (see loadmonitor/figures_editorial.py
for the same computations); regenerate it if the model or recordings change.
