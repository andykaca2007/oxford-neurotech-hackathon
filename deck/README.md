# Presentation deck

A single web page: one slide per screen, every figure drawn live from real data (`data.json`) so it animates in.

    cd deck && python3 -m http.server 8790      # then open http://localhost:8790 and press F for fullscreen

Keys: right arrow or space = next, left = back, F = fullscreen. Click anywhere also advances.

Slides: 0 opening (raw vs cleaned trace, the load under arithmetic, three numbers), 1 video, 2 the six filters,
3 the spectrum, 4 how it works, 5 ROC, 6 training curve, 7 what comes next.

The video slide plays `deck/demo.mp4` if that file exists; otherwise drop the recording onto the slide or choose it
with the button. The file never leaves the laptop. Before pressing play, say "a real recording from a public dataset,
through our live system": nothing on screen says it.

`data.json` is written by the export cell at the top of this folder's history (see loadmonitor/figures_editorial.py
for the same computations); regenerate it if the model or recordings change.
