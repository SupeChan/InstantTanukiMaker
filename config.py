from dataclasses import dataclass
import pathlib
from PIL import Image, ImageSequence
from itertools import cycle
import os
import sys
import wx

SIZE_ANIME = (600, 600)
TRANSPARENT_COLOR_KEY = (255, 6, 4)

PROCESS_PER_MONITOR_DPI_AWARE = 2

BASE = "素体"
BACKPACK = "背負い物"
HAT = "帽子"
FACE = "表情"
BROWS = "眉"
EYES = "目"
MOUTH = "口"
EMOTION = "感情"
ETC = "その他"

FOLDER_IMAGE = pathlib.Path(sys.prefix + "/Image")
PATH_ICON = FOLDER_IMAGE / "Icon/Instant.ico"
FOLDER_MATERIAL = FOLDER_IMAGE / "Material"
FOLDER_BASE = FOLDER_MATERIAL / BASE
PATH_PNG_PREVIEW = FOLDER_MATERIAL / "preview.png"
PATH_GIF_PREVIEW = FOLDER_MATERIAL / "preview.gif"
PATH_PNG = FOLDER_MATERIAL / "preview.png"
SUFFIXES_IMAGE = ["png", "gif"]

ORDER_COMPOSITE_DEFAULT = [BACKPACK, BASE, HAT, FACE, BROWS, EYES, MOUTH, EMOTION, ETC]
LST_ORDER_PARTS = [BACKPACK, HAT, FACE, BROWS, EYES, MOUTH, EMOTION, ETC]

DIC_FOLDER_BASE = {folder.stem: folder for folder in FOLDER_BASE.iterdir()
                   if bool(list(folder.rglob("*.*")))}

LST_FOLDER_PARTS = [FOLDER_MATERIAL / parts for parts in LST_ORDER_PARTS]
DIC_DIC_PARTS = {
    folder_parts.stem: {path_image.stem: path_image for path_image in folder_parts.iterdir()}
    for folder_parts in LST_FOLDER_PARTS}

STYLE_CB = wx.CB_DROPDOWN | wx.CB_READONLY

DIC_TANUKI_OFFSET = {"ライスシャワー": (0, 50),
                     "ヒシアケボノ": (50, 0),
                     "マーベラスサンデー": (39, 0)}

ALIGNMENT_FLAT = [((0, 0), 0)]

LST_ALIGNMENT_HUT = [((362, 79), -20), ((340, 109), -20), ((289, 63), -9), ((283, 96), -14),
                     ((178, 108), 11), ((161, 67), 12), ((208, 73), 2), ((199, 106), 7)]

LST_ALIGNMENT_EYES = [((311, 187), -24), ((282, 234), -24), ((264, 184), -11),
                      ((239, 228), -16), ((198, 249), 8), ((189, 202), 10), ((216, 216), 4),
                      ((208, 248), 6)]

LST_ALIGNMENT_MOUTH = [((300, 213), -28), ((272, 259), -28), ((262, 210), -13),
                       ((232, 255), -24), ((207, 272), 4), ((196, 227), 6), ((220, 240), -3),
                       ((213, 272), 0)]

DIC_ALIGNMENT = {HAT: LST_ALIGNMENT_HUT,
                 EYES: LST_ALIGNMENT_EYES,
                 MOUTH: LST_ALIGNMENT_MOUTH}
