#!/usr/bin/env python3
"""Erzeugt bonding_test.kicad_pcb: einlagige Testplatine zum Einstellen eines Drahtbonders.

Aufruf:  python3 generate_pcb.py
Alle Maße in mm. Parameter unten anpassen und neu erzeugen.
"""
import os
import string
import pcbnew
from pcbnew import FromMM, VECTOR2I

# ---- Platine -------------------------------------------------------------
BOARD_W, BOARD_H = 200.0, 100.0          # Querformat

# ---- Pads (JLCPCB-Limits, 1-2 Lagen, 1 oz) -------------------------------
PAD_W = 0.10          # min. Leiterbahnbreite
PAD_GAP = 0.30        # Abstand benachbarter Pärchen (JLC-Minimum wäre 0.15)
PAD_LEN = 5.0
PAIR_GAP = 0.5        # Lücke zwischen den beiden Pads eines Pärchens (Bondstrecke)

# ---- Tabelle -------------------------------------------------------------
PAIRS_PER_BLOCK = 10  # Pärchen pro Tabellenzelle
COL_GAP = 1.0         # Lücke zwischen Zellen in x
ROW_GAP = 0.6         # Lücke zwischen Zellen in y (statt PAD_GAP)
MARGIN_L, MARGIN_R = 6.0, 3.0            # links Platz für Zeilenbuchstaben
MARGIN_T, MARGIN_B = 4.5, 4.5            # oben/unten Platz für Spaltennummern
ID_COLS, ID_ROWS = 3, 3   # unten rechts freigelassene Zellen für das Beschriftungsfeld
MASK_MARGIN = 0.1     # Lötstopp-Freistellung um jede Zelle

SILK_H, SILK_W, SILK_T = 1.0, 0.8, 0.15  # JLC: min. 1.0 mm hoch, 0.15 mm Strich

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "bonding_test.kicad_pcb")

# ---- abgeleitete Geometrie -----------------------------------------------
pitch = PAD_W + PAD_GAP
# Pads liegen waagerecht: Pärchen entlang x, Pärchen einer Zelle in y gestapelt
block_w = 2 * PAD_LEN + PAIR_GAP
block_pitch = block_w + COL_GAP
pair_h = (PAIRS_PER_BLOCK - 1) * pitch + PAD_W   # Höhe einer Zelle
row_pitch = pair_h + ROW_GAP

n_cols = int((BOARD_W - MARGIN_L - MARGIN_R + COL_GAP) // block_pitch)
n_rows = int((BOARD_H - MARGIN_T - MARGIN_B + ROW_GAP) // row_pitch)
grid_w = n_cols * block_pitch - COL_GAP
grid_h = n_rows * row_pitch - ROW_GAP
# Raster im verfügbaren Bereich zentrieren
x0 = MARGIN_L + (BOARD_W - MARGIN_L - MARGIN_R - grid_w) / 2
y0 = MARGIN_T + (BOARD_H - MARGIN_T - MARGIN_B - grid_h) / 2

board = pcbnew.NewBoard(OUT)
board.SetCopperLayerCount(2)  # KiCad-Minimum; B.Cu bleibt leer -> als 1-lagig bestellbar

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


# ---- Umriss --------------------------------------------------------------
edge = pcbnew.PCB_SHAPE(board)
edge.SetShape(pcbnew.SHAPE_T_RECT)
edge.SetStart(P(0, 0))
edge.SetEnd(P(BOARD_W, BOARD_H))
edge.SetLayer(pcbnew.Edge_Cuts)
edge.SetWidth(FromMM(0.1))
board.Add(edge)

# ---- Zellen --------------------------------------------------------------
rows = string.ascii_uppercase[:n_rows]
cu_only = pcbnew.LSET()
cu_only.AddLayer(pcbnew.F_Cu)

for r, letter in enumerate(rows):
    ry = y0 + r * row_pitch                       # Oberkante der Zeile
    for c in range(n_cols):
        if r >= n_rows - ID_ROWS and c >= n_cols - ID_COLS:
            continue                              # Platz für das ID-Feld
        bx = x0 + c * block_pitch                 # linke Kante der Zelle
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

        # eine durchgehende Lötstopp-Öffnung pro Zelle (keine Stege zwischen Pads)
        m = pcbnew.PCB_SHAPE(fp)
        m.SetShape(pcbnew.SHAPE_T_RECT)
        m.SetStart(P(bx - MASK_MARGIN, ry - MASK_MARGIN))
        m.SetEnd(P(bx + block_w + MASK_MARGIN, ry + pair_h + MASK_MARGIN))
        m.SetLayer(pcbnew.F_Mask)
        m.SetWidth(0)
        m.SetFilled(True)
        fp.Add(m)

    text(letter, MARGIN_L / 2, ry + pair_h / 2, h=1.5, w=1.2, t=0.2)

# ---- Spaltennummern oben und unten ---------------------------------------
for c in range(n_cols):
    cx = x0 + c * block_pitch + block_w / 2
    for y in (y0 - 1.6, y0 + grid_h + 1.6):
        text(str(c + 1), cx, y)

# ---- Beschriftungsfeld (PCB-ID, mit Edding) unten rechts ------------------
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
print(f"ID-Feld: {fx1 - fx0 - 0.3:.1f} x {fy1 - fy0 - 1.7:.1f} mm")

text(f"BOND TEST  pad {PAD_W:.2f} x {PAD_LEN:.1f}  gap {PAIR_GAP:.1f}  pitch {pitch:.2f} mm",
     BOARD_W / 2, BOARD_H - 1.2)

pcbnew.SaveBoard(OUT, board)
print(f"{n_rows} Zeilen x {n_cols} Zellen x {PAIRS_PER_BLOCK} "
      f"abzüglich {ID_ROWS}x{ID_COLS} Zellen fürs ID-Feld = "
      f"{(n_rows * n_cols - ID_ROWS * ID_COLS) * PAIRS_PER_BLOCK} Pad-Pärchen, Pitch {pitch:.2f} mm")
print(f"Raster: x {x0:.2f}..{x0 + grid_w:.2f}, y {y0:.2f}..{y0 + grid_h:.2f}")
