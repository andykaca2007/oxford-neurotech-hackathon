"""What is physically in each of the 8 stream slots of the Core-8 cap.

Layout A (Sat 7 Nov, decided 22:50): the three back electrodes were moved onto positions the
public training data has, so the load model can use all eight.
    slot: 1   2   3   4   5   6    7    8
    was:  Fz  C3  Cz  C4  Pz  PO7  POz  PO8
    now:  Fz  C3  Cz  C4  Pz  P3   O1   P4      (PO7 -> P3, POz -> O1, PO8 -> P4)
Every script that names channels imports MONTAGE from here. If an electrode is moved again,
change it here only.
"""
MONTAGE = ["Fz", "C3", "Cz", "C4", "Pz", "P3", "O1", "P4"]
ORIGINAL = ["Fz", "C3", "Cz", "C4", "Pz", "PO7", "POz", "PO8"]
