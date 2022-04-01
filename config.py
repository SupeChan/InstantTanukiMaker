from dataclasses import dataclass
import pathlib
from PIL import Image, ImageSequence
from itertools import cycle
import os

import ctypes
import win32api

import sys
import wx

PROCESS_PER_MONITOR_DPI_AWARE = 2
ctypes.windll.shcore.SetProcessDpiAwareness(PROCESS_PER_MONITOR_DPI_AWARE)
INFO_MONITOR_FULL = win32api.GetMonitorInfo(win32api.MonitorFromPoint((0, 0)))
AREA_WORKING = INFO_MONITOR_FULL.get("Work")
WIDTH_WORKING, HEIGHT_WORKING = AREA_WORKING[2], AREA_WORKING[3]

stem_user_folder = str(pathlib.Path(os.getenv("USERPROFILE")).stem)
CONTAINS_JAPANESE = not (stem_user_folder.isalnum() and stem_user_folder.isascii())

SIZE_THUMBNAIL = (100, 100)
DEFAULT_BASE_SIZE = (500, 500)

PROCESS_PER_MONITOR_DPI_AWARE = 2

BASE = "素体"
TRANSPARENT = "肌透過"
FACE = "表情"
BROWS = "眉"
EYES = "目"
MOUTH = "口"
EMOTION = "感情"
ETC = "その他"
COLLAGE = "加工用素材"

TYPES_IMAGE = [BASE, TRANSPARENT, FACE, BROWS, EYES, MOUTH]

FOLDER_IMAGE = pathlib.Path(sys.prefix + "/Image")
FOLDER_ICON = FOLDER_IMAGE / "Icon"
FOLDER_BTN = FOLDER_ICON / "Button"
PATH_ICON = FOLDER_IMAGE / "Icon/Instant.ico"
FOLDER_MATERIAL = FOLDER_IMAGE / "Material"
FOLDER_BASE = FOLDER_MATERIAL / BASE
PATH_PNG_PREVIEW = FOLDER_MATERIAL / "preview.png"
PATH_GIF_PREVIEW = FOLDER_MATERIAL / "preview.gif"
SUFFIXES_IMAGE = [".png", ".gif"]

ORDER_COMPOSITE_DEFAULT = [BASE, FACE, BROWS, EYES, MOUTH, EMOTION, ETC, COLLAGE]
LST_ORDER_PARTS = [FACE, BROWS, EYES, MOUTH, ETC, COLLAGE]
EXTERNAL = "外部画像"

DIC_FOLDER_BASE = {folder.stem: folder for folder in FOLDER_BASE.iterdir()
                   if bool(list(folder.rglob("*.*")))}

LST_FOLDER_PARTS = [FOLDER_MATERIAL / parts for parts in LST_ORDER_PARTS]
DIC_DIC_PARTS = {
    folder_parts.stem: {path_image.stem: path_image for path_image in folder_parts.iterdir()}
    for folder_parts in LST_FOLDER_PARTS}

DIC_TANUKI_OFFSET = {"イナリワン顔無し": [(-25, 0)],
                     "ライスシャワー顔無し": [(0, 25)],
                     "マーベラスサンデー顔無し": [(-11, 0)]}

FILTER_IMAGE_CONTOUR = "鉛筆風"
FILTER_IMAGE_DOT = "ドット風"
FILTER_IMAGE_FANCY = "ぼけぼけ"
FILTER_IMAGE_NONE = "フィルタ無し"

FILTER_COLOR_GAMING = "ゲーミング"
FILTER_COLOR_MONOCHROME = "モノクロ"
FILTER_COLOR_INVERT = "ネガポジ"
FILTER_COLOR_NONE = "フィルタ無し"

LST_FILTER_IMAGE = [FILTER_IMAGE_CONTOUR, FILTER_IMAGE_DOT, FILTER_IMAGE_FANCY, FILTER_IMAGE_NONE]
LST_FILTER_COLOR = [FILTER_COLOR_GAMING, FILTER_COLOR_MONOCHROME, FILTER_COLOR_INVERT,
                    FILTER_COLOR_NONE]

ALIGNMENT_NONE = "画像中央"
ALIGNMENT_HUT = "帽子"
ALIGNMENT_EYES = "目"
ALIGNMENT_EYE_LEFT = "左目"
ALIGNMENT_EYE_RIGHT = "右目"
ALIGNMENT_MOUSE = "口"
ALIGNMENT_HAND_LEFT = "左手"
ALIGNMENT_HAND_RIGHT = "右手"

LST_ALIGNMENT = [ALIGNMENT_HUT,
                 ALIGNMENT_EYES, ALIGNMENT_EYE_LEFT, ALIGNMENT_EYE_RIGHT,
                 ALIGNMENT_MOUSE,
                 ALIGNMENT_HAND_LEFT, ALIGNMENT_HAND_RIGHT,
                 ALIGNMENT_NONE]

ALIGNMENT_FLAT = [((0, 0), 0)]
OFFSET_FLAT = [(0, 0)]
ANGLE_FLAT = [0]
# LST_ALIGNMENT_HUT = [((362, 79), -20), ((340, 109), -20), ((289, 63), -9), ((283, 96), -14),
#                      ((178, 108), 11), ((161, 67), 12), ((208, 73), 2), ((199, 106), 7)]

LST_ALIGNMENT_HUT = [((102, -141), -27), ((75, -99), -25), ((33, -148), -8), ((23, -104), -19),
                     ((-51, -93), 7), ((-66, -134), 9), ((-30, -125), 3), ((-43, -94), 2)]

LST_ALIGNMENT_EYES = [((61, -70), -24), ((34, -24), -22), ((13, -76), -8),
                      ((-11, -30), -18), ((-53, -11), 10), ((-64, -54), 11), ((-36, -43), 3),
                      ((-45, -11), 7)]

LST_ALIGNMENT_EYE_LEFT = [((96, -48), -23), ((68, -3), -25), ((52, -64), -10), ((26, -12), -22),
                          ((-13, -8), 7), ((-26, -54), 8), ((1, -37), 2), ((-5, -7), 4)]

LST_ALIGNMENT_EYE_RIGHT = [((25, -82), -24), ((-3, -37), -28), ((-28, -79), -12), ((-50, -39), -23),
                           ((-92, 1), 3), ((-103, -43), 6), ((-75, -37), -2), ((-83, -1), 3)]

LST_ALIGNMENT_MOUTH = [((43, -36), -26), ((17, 12), -23), ((7, -37), -7),
                       ((-23, 7), -19), ((-47, 28), 12), ((-55, -16), 13), ((-32, -5), 3),
                       ((-38, 29), 9)]

LST_ALIGNMENT_HAND_LEFT = [((137, 47), -1), ((119, 115), -25), ((127, 52), -16), ((64, 110), -9),
                           ((-17, 85), 37), ((23, 9), 0), ((56, 78), -35), ((76, 65), -1)]

LST_ALIGNMENT_HAND_RIGHT = [((-85, 26), 18), ((-94, -13), -28), ((-93, 61), 29), ((-135, 0), -9),
                            ((-156, -11), 26), ((-128, 97), 65), ((-168, -3), -19),
                            ((-110, 94), 34)]

DIC_ALIGNMENT = {
    ALIGNMENT_HUT: LST_ALIGNMENT_HUT,
    ALIGNMENT_EYES: LST_ALIGNMENT_EYES,
    ALIGNMENT_EYE_LEFT: LST_ALIGNMENT_EYE_LEFT,
    ALIGNMENT_EYE_RIGHT: LST_ALIGNMENT_EYE_RIGHT,
    ALIGNMENT_MOUSE: LST_ALIGNMENT_MOUTH,
    ALIGNMENT_HAND_LEFT: LST_ALIGNMENT_HAND_LEFT,
    ALIGNMENT_HAND_RIGHT: LST_ALIGNMENT_HAND_RIGHT}

STYLE_SLIDER = wx.SL_VALUE_LABEL | wx.SL_TICKS

KEY_LEFT = 314
KEY_RIGHT = 316
KEY_UP = 315
KEY_DOWN = 317

# 無意味に連続して関数を呼び出し画像を更新しないためのディレイ
DELAY_UPDATE = 100
