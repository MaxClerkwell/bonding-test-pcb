#!/usr/bin/env python3
# SPDX-License-Identifier: CC-BY-4.0
# Copyright (c) 2026 Stephan Bökelmann
"""Generates bonding_test.kicad_pcb: single-layer test board for setting up a wire bonder.

Created by Stephan Bökelmann while working as a research associate at
Ruhr University Bochum, Institute for Experimental Physics I (EP1),
Hadrons and Nuclei group.

Usage:  python3 generate_pcb.py   (needs the `qrencode` command line tool)
All dimensions in mm. Adjust the parameters below and regenerate.
"""
import os
import string
import subprocess
import pcbnew
from pcbnew import FromMM, VECTOR2I

# ---- Release info (printed on the back side) ------------------------------
VERSION = "v1.1.0"
DOI = "10.5281/zenodo.24319171"

# ---- Board ---------------------------------------------------------------
BOARD_W, BOARD_H = 200.0, 100.0          # landscape

# ---- Pads (JLCPCB limits, 1-2 layers, 1 oz) ------------------------------
PAD_W = 0.10          # min. trace width
PAD_GAP = 0.30        # spacing between neighbouring pairs (JLC minimum would be 0.15)
PAD_LEN = 5.0
PAIR_GAP = 0.5        # gap between the two pads of a pair (bond span)

# ---- Table ---------------------------------------------------------------
PAIRS_PER_BLOCK = 10  # pairs per table cell
COL_GAP = 1.0         # gap between cells in x
ROW_GAP = 0.6         # gap between cells in y (instead of PAD_GAP)
MARGIN_L, MARGIN_R = 6.0, 3.0            # room for row letters on the left
MARGIN_T, MARGIN_B = 4.5, 4.5            # room for column numbers top/bottom
ID_COLS, ID_ROWS = 3, 3   # cells left out bottom right for the label field
MASK_MARGIN = 0.1     # solder mask clearance around each cell

SILK_H, SILK_W, SILK_T = 1.0, 0.8, 0.15  # JLC: min. 1.0 mm height, 0.15 mm stroke

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "bonding_test.kicad_pcb")

# ---- derived geometry ---------------------------------------------------
pitch = PAD_W + PAD_GAP
# pads are horizontal: a pair runs along x, the pairs of a cell are stacked in y
block_w = 2 * PAD_LEN + PAIR_GAP
block_pitch = block_w + COL_GAP
pair_h = (PAIRS_PER_BLOCK - 1) * pitch + PAD_W   # height of one cell
row_pitch = pair_h + ROW_GAP

n_cols = int((BOARD_W - MARGIN_L - MARGIN_R + COL_GAP) // block_pitch)
n_rows = int((BOARD_H - MARGIN_T - MARGIN_B + ROW_GAP) // row_pitch)
grid_w = n_cols * block_pitch - COL_GAP
grid_h = n_rows * row_pitch - ROW_GAP
# centre the grid in the available area
x0 = MARGIN_L + (BOARD_W - MARGIN_L - MARGIN_R - grid_w) / 2
y0 = MARGIN_T + (BOARD_H - MARGIN_T - MARGIN_B - grid_h) / 2

board = pcbnew.NewBoard(OUT)
board.SetCopperLayerCount(2)  # KiCad minimum; B.Cu stays empty -> can be ordered as 1-layer

ds = board.GetDesignSettings()
ds.m_TrackMinWidth = FromMM(0.10)
ds.m_MinClearance = FromMM(0.10)
ds.m_CopperEdgeClearance = FromMM(0.2)
ds.m_SolderMaskExpansion = 0
ds.m_SolderMaskMinWidth = 0
nc = ds.m_NetSettings.GetDefaultNetclass()
nc.SetClearance(FromMM(0.10))
nc.SetTrackWidth(FromMM(0.10))


def P(x, y):
    return VECTOR2I(FromMM(x), FromMM(y))


def text(s, x, y, layer=pcbnew.F_SilkS, h=SILK_H, w=SILK_W, t=SILK_T):
    tx = pcbnew.PCB_TEXT(board)
    tx.SetText(s)
    tx.SetLayer(layer)
    tx.SetPosition(P(x, y))
    tx.SetTextSize(VECTOR2I(FromMM(w), FromMM(h)))
    tx.SetTextThickness(FromMM(t))
    tx.SetHorizJustify(pcbnew.GR_TEXT_H_ALIGN_CENTER)
    tx.SetVertJustify(pcbnew.GR_TEXT_V_ALIGN_CENTER)
    board.Add(tx)


# ---- Outline -------------------------------------------------------------
edge = pcbnew.PCB_SHAPE(board)
edge.SetShape(pcbnew.SHAPE_T_RECT)
edge.SetStart(P(0, 0))
edge.SetEnd(P(BOARD_W, BOARD_H))
edge.SetLayer(pcbnew.Edge_Cuts)
edge.SetWidth(FromMM(0.1))
board.Add(edge)

# ---- Cells ---------------------------------------------------------------
rows = string.ascii_uppercase[:n_rows]
cu_only = pcbnew.LSET()
cu_only.AddLayer(pcbnew.F_Cu)

for r, letter in enumerate(rows):
    ry = y0 + r * row_pitch                       # top edge of the row
    for c in range(n_cols):
        if r >= n_rows - ID_ROWS and c >= n_cols - ID_COLS:
            continue                              # room for the ID field
        bx = x0 + c * block_pitch                 # left edge of the cell
        cx, cy = bx + block_w / 2, ry + pair_h / 2

        fp = pcbnew.FOOTPRINT(board)
        fp.SetFPID(pcbnew.LIB_ID("", f"BondCell_{PAIRS_PER_BLOCK}x2"))
        fp.SetReference(f"{letter}{c + 1}")
        fp.SetValue("BondCell")
        fp.Reference().SetVisible(False)
        fp.Value().SetVisible(False)
        fp.Reference().SetLayer(pcbnew.F_Fab)
        fp.Value().SetLayer(pcbnew.F_Fab)
        fp.SetAttributes(pcbnew.FP_SMD | pcbnew.FP_EXCLUDE_FROM_BOM
                         | pcbnew.FP_EXCLUDE_FROM_POS_FILES | pcbnew.FP_BOARD_ONLY)
        fp.SetPosition(P(cx, cy))
        board.Add(fp)

        for i in range(PAIRS_PER_BLOCK):
            py = ry + PAD_W / 2 + i * pitch
            for half, px in (("a", bx + PAD_LEN / 2),
                             ("b", bx + PAD_LEN + PAIR_GAP + PAD_LEN / 2)):
                pad = pcbnew.PAD(fp)
                pad.SetNumber(f"{i + 1}{half}")
                pad.SetAttribute(pcbnew.PAD_ATTRIB_SMD)
                pad.SetShape(pcbnew.F_Cu, pcbnew.PAD_SHAPE_RECT)
                pad.SetSize(pcbnew.F_Cu, VECTOR2I(FromMM(PAD_LEN), FromMM(PAD_W)))
                pad.SetLayerSet(cu_only)
                pad.SetPosition(P(px, py))
                fp.Add(pad)

        # one continuous solder mask opening per cell (no webs between pads)
        m = pcbnew.PCB_SHAPE(fp)
        m.SetShape(pcbnew.SHAPE_T_RECT)
        m.SetStart(P(bx - MASK_MARGIN, ry - MASK_MARGIN))
        m.SetEnd(P(bx + block_w + MASK_MARGIN, ry + pair_h + MASK_MARGIN))
        m.SetLayer(pcbnew.F_Mask)
        m.SetWidth(0)
        m.SetFilled(True)
        fp.Add(m)

    text(letter, MARGIN_L / 2, ry + pair_h / 2, h=1.5, w=1.2, t=0.2)

# ---- Column numbers top and bottom ---------------------------------------
for c in range(n_cols):
    cx = x0 + c * block_pitch + block_w / 2
    for y in (y0 - 1.6, y0 + grid_h + 1.6):
        text(str(c + 1), cx, y)

# ---- Label field (PCB ID, for a marker pen) bottom right -----------------
fx0 = x0 + (n_cols - ID_COLS) * block_pitch
fy0 = y0 + (n_rows - ID_ROWS) * row_pitch
fx1, fy1 = x0 + grid_w, y0 + grid_h
text("PCB ID", (fx0 + fx1) / 2, fy0 + 0.7)
field = pcbnew.PCB_SHAPE(board)
field.SetShape(pcbnew.SHAPE_T_RECT)
field.SetStart(P(fx0 + 0.3, fy0 + 1.7))
field.SetEnd(P(fx1, fy1))
field.SetLayer(pcbnew.F_SilkS)
field.SetWidth(0)
field.SetFilled(True)
board.Add(field)
print(f"ID field: {fx1 - fx0 - 0.3:.1f} x {fy1 - fy0 - 1.7:.1f} mm")

text(f"BOND TEST  pad {PAD_W:.2f} x {PAD_LEN:.1f}  gap {PAIR_GAP:.1f}  pitch {pitch:.2f} mm",
     BOARD_W / 2, BOARD_H - 1.2)

# ---- Back side: release info, DOI, QR code, parameter log -----------------
# Coordinates below are given as seen from the back (u runs left to right),
# i.e. u = BOARD_W - x, and all text is mirrored.
B = pcbnew.B_SilkS


def btext(s, u, y, h=1.2, t=0.15, just="left"):
    tx = pcbnew.PCB_TEXT(board)
    tx.SetText(s)
    tx.SetLayer(B)
    tx.SetPosition(P(BOARD_W - u, y))
    tx.SetTextSize(VECTOR2I(FromMM(h * 0.85), FromMM(h)))
    tx.SetTextThickness(FromMM(t))
    tx.SetMirrored(True)
    tx.SetHorizJustify({"left": pcbnew.GR_TEXT_H_ALIGN_LEFT,
                        "center": pcbnew.GR_TEXT_H_ALIGN_CENTER}[just])
    tx.SetVertJustify(pcbnew.GR_TEXT_V_ALIGN_CENTER)
    board.Add(tx)


def bline(u1, y1, u2, y2, w=0.15):
    ln = pcbnew.PCB_SHAPE(board)
    ln.SetShape(pcbnew.SHAPE_T_SEGMENT)
    ln.SetStart(P(BOARD_W - u1, y1))
    ln.SetEnd(P(BOARD_W - u2, y2))
    ln.SetLayer(B)
    ln.SetWidth(FromMM(w))
    board.Add(ln)


def brect(u1, y1, u2, y2):
    rc = pcbnew.PCB_SHAPE(board)
    rc.SetShape(pcbnew.SHAPE_T_RECT)
    rc.SetStart(P(BOARD_W - u1, y1))
    rc.SetEnd(P(BOARD_W - u2, y2))
    rc.SetLayer(B)
    rc.SetWidth(0)
    rc.SetFilled(True)
    board.Add(rc)


# -- info block (left) --
btext("bonding-test-pcb", 3, 6.5, h=3.0, t=0.4)
btext(VERSION, 3, 12.0, h=2.0, t=0.3)
for k, line in enumerate([
        "Test board for setting up a wire bonder",
        "",
        "Stephan Bökelmann",
        "Ruhr University Bochum",
        "Institute for Experimental Physics I (EP1)",
        "Hadrons and Nuclei group",
        "",
        "License: CC BY 4.0",
        f"Pad {PAD_LEN:.1f} x {PAD_W:.2f} mm, gap {PAIR_GAP:.1f} mm, pitch {pitch:.2f} mm",
        "Fab: FR4, 1 oz Cu, ENIG"]):
    if line:
        btext(line, 3, 17.0 + k * 2.3)

# -- QR code with the DOI link; silkscreen is white, so the *light* modules
#    (including the quiet zone) are printed and the dark ones stay bare mask --
QR_MODULE, QR_U, QR_Y = 0.6, 3.0, 42.0
qr = subprocess.run(["qrencode", "-t", "ASCII", "-m", "4", "-l", "M", f"https://doi.org/{DOI}"],
                    check=True, capture_output=True, text=True).stdout.splitlines()
for j, row in enumerate(qr):
    mods = [row[i] == "#" for i in range(0, len(row), 2)]
    i = 0
    while i < len(mods):                      # merge horizontal runs of light modules
        if mods[i]:
            i += 1
            continue
        k = i
        while k < len(mods) and not mods[k]:
            k += 1
        brect(QR_U + i * QR_MODULE, QR_Y + j * QR_MODULE,
              QR_U + k * QR_MODULE, QR_Y + (j + 1) * QR_MODULE)
        i = k
qr_size = len(qr) * QR_MODULE
btext("DOI", QR_U + qr_size + 2, QR_Y + 3, h=2.0, t=0.3)
btext(DOI, QR_U + qr_size + 2, QR_Y + 7.5, h=1.5, t=0.2)
btext("https://doi.org/", QR_U + qr_size + 2, QR_Y + 12)
btext(DOI, QR_U + qr_size + 2, QR_Y + 14.3)

# -- fields to fill in by hand --
for k, label in enumerate(["Date", "Operator", "Bonder", "Wire", "Tool"]):
    y = 72.0 + k * 5.0
    btext(label + ":", 3, y, h=1.5, t=0.2)
    bline(16, y + 1.2, 70, y + 1.2)
btext("JLCJLCJLCJLC", 3, 96.5, h=1.0)         # JLCPCB prints its order number here

# -- parameter log: one line per table row of the front side --
T_U0, T_Y0, T_RH = 76.0, 3.8, 4.2
cols = [("Row", 10), ("US power", 22), ("Time", 22), ("Force", 22), ("Notes", 45)]
t_u1 = T_U0 + sum(w for _, w in cols)
t_y1 = T_Y0 + (n_rows + 1) * T_RH
for k in range(n_rows + 2):
    bline(T_U0, T_Y0 + k * T_RH, t_u1, T_Y0 + k * T_RH, w=0.3 if k in (0, 1, n_rows + 1) else 0.15)
u = T_U0
for name, w in cols:
    bline(u, T_Y0, u, t_y1, w=0.3 if u == T_U0 else 0.15)
    btext(name, u + w / 2, T_Y0 + T_RH / 2, h=1.5, t=0.2, just="center")
    u += w
bline(t_u1, T_Y0, t_u1, t_y1, w=0.3)
for r, letter in enumerate(rows):
    btext(letter, T_U0 + cols[0][1] / 2, T_Y0 + (r + 1.5) * T_RH, h=2.0, t=0.3, just="center")

pcbnew.SaveBoard(OUT, board)
print(f"{n_rows} rows x {n_cols} cells x {PAIRS_PER_BLOCK} "
      f"minus {ID_ROWS}x{ID_COLS} cells for the ID field = "
      f"{(n_rows * n_cols - ID_ROWS * ID_COLS) * PAIRS_PER_BLOCK} pad pairs, pitch {pitch:.2f} mm")
print(f"Grid: x {x0:.2f}..{x0 + grid_w:.2f}, y {y0:.2f}..{y0 + grid_h:.2f}")
