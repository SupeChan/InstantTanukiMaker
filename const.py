import ctypes
import win32api
import sys
import pathlib
from dataclasses import dataclass, fields
import wx
from wx.lib.newevent import NewEvent
from PIL import Image
import numpy as np

VERSION = "3.0.0"

# DPI表示とモニタ情報
PROCESS_PER_MONITOR_DPI_AWARE = 2
ctypes.windll.shcore.SetProcessDpiAwareness(PROCESS_PER_MONITOR_DPI_AWARE)
INFO_MONITOR_FULL = win32api.GetMonitorInfo(win32api.MonitorFromPoint((0, 0)))
AREA_WORKING = INFO_MONITOR_FULL.get("Work")
WIDTH_WORKING, HEIGHT_WORKING = AREA_WORKING[2], AREA_WORKING[3]
WIDTH_DEFAULT = 2560
RATE_DISPLAY = WIDTH_WORKING / WIDTH_DEFAULT

# 画像サイズ
DEFAULT_SIZE = (500, 500)
MAX_SIZE = (1500, 1500)
MIN_SIZE = (100, 100)
DEFAULT_WIDTH, DEFAULT_HEIGHT = DEFAULT_SIZE
MAX_WIDTH, MAX_HEIGHT = MAX_SIZE
MIN_WIDTH, MIN_HEIGHT = MIN_SIZE

ICON_SIZE = (80, 80)
THUMB_SIZE = (64, 64)
THUMB_MINI_SIZE = (63, 63)

# プロパティパネル色
COLOR_FILE = (200, 230, 200)
COLOR_PARTS = (200, 200, 250)
COLOR_NONE = (200, 200, 200)

# フレーム数表示
DISPLAY_FONT_SINGLE_SIZE = 20
DISPLAY_FONT_DOUBLE_SIZE = 14
DISPLAY_BBOX = (19, 53, 67, 84)

# イベント通知
EVENT_UPDATE, EVT_UPDATE = NewEvent()
EVENT_APPEND, EVT_APPEND = NewEvent()
EVENT_SELECT, EVT_SELECT = NewEvent()
EVENT_LAYOUT, EVT_LAYOUT = NewEvent()
EVENT_INFO, EVT_INFO = NewEvent()
EVENT_START_PROGRESS, EVT_START_PROGRESS = NewEvent()
EVENT_END_PROGRESS, EVT_END_PROGRESS = NewEvent()
EVENT_PLAY, EVT_PLAY = NewEvent()


# ImageManager
@dataclass
class ImageType:
    BASE: str = "素体"
    TRANSPARENT: str = "素体透過"
    COSTUME: str = "きぐるみ"
    FACE: str = "表情"
    BROWS: str = "眉"
    EYES: str = "目"
    MOUTH: str = "口"
    ACCESSORY: str = "アクセサリ"
    COLLAGE: str = "パーツ"
    FREE: str = "フリー"
    ETC: str = "その他"


TYPES_IMAGE = [field.default for field in fields(ImageType)]
TYPES_REPLACE = [ImageType.BASE, ImageType.COSTUME,
                 ImageType.FACE, ImageType.BROWS, ImageType.EYES, ImageType.MOUTH]

KEYWORD_TRANSPARENT = "【透過】"
KEYWORDS_SEPARATE = ["[腕と手]", "[ばらばら]"]

TYPES_BASE = [ImageType.BASE, ImageType.TRANSPARENT, ImageType.COLLAGE]
DIC_BASE_OFFSET = {"イナリワン": np.array((-25, 0)),
                   "ライスシャワー": np.array((0, 25)),
                   "マーベラスサンデー": np.array((-11, 0))}

OFFSET_FLAT = np.array([0, 0])


@dataclass
class BlendMode:
    MULTIPLY: str = "乗算"
    SCREEN: str = "スクリーン"
    OVERLAY: str = "オーバーレイ"
    ALPHA: str = "アルファ"
    NONE: str = "なし"


MODES_BLEND = [field.default for field in fields(BlendMode)]


@dataclass
class ImageFilter:
    LINE: str = "鉛筆風"
    COLORING: str = "塗り絵"
    DOT: str = "ドット"
    MOCHI: str = "もちもち"
    NONE: str = "なし"


FILTERS_IMAGE = [field.default for field in fields(ImageFilter)]


@dataclass
class ColorFilter:
    MONO: str = "モノクロ"
    ASH: str = "灰"
    GAMING: str = "ゲーミング"
    NONE: str = "なし"


FILTERS_COLOR = [field.default for field in fields(ColorFilter)]


@dataclass
class SaveMode:
    GIF: str = "GIF"
    PNG_SEQUENCE: str = "連番PNG"
    PNG_ANIME: str = "APNG"


MODES_SAVE = [field.default for field in fields(SaveMode)]
THRESHOLD_CONVERT_SINGLE = 0.25

# フォルダパス
FOLDER_DATA = pathlib.Path(sys.prefix + "/Data")
FOLDER_IMAGE = FOLDER_DATA / "Image"
FOLDER_ICON = FOLDER_IMAGE / "Icon"
FOLDER_WIDGET = FOLDER_ICON / "Widget"
FOLDER_BUTTON = FOLDER_ICON / "Folder"
FOLDER_BACKGROUND = FOLDER_ICON / "Background"
FOLDER_MATERIAL = FOLDER_IMAGE / "Material"
FOLDER_BASE = FOLDER_MATERIAL / ImageType.BASE

FOLDER_APPEND = pathlib.Path.cwd() / "あぺんど"
FOLDER_APPEND_BUTTON = FOLDER_APPEND / "フォルダアイコン"

# ウィジェットアイコン
PATH_ICON = FOLDER_WIDGET / "Instant.ico"
PATH_FOCUS_ON = FOLDER_WIDGET / "focus_on.png"
PATH_FOCUS_OFF = FOLDER_WIDGET / "focus_off.png"
PATH_DISPLAY_NUM = FOLDER_WIDGET / "display_number.png"
PATH_MARK_ON = FOLDER_WIDGET / "mark_on.png"
PATH_MARK_OFF = FOLDER_WIDGET / "mark_off.png"
PATH_PAUSE = FOLDER_WIDGET / "pause.png"
PATH_PLAYING = FOLDER_WIDGET / "playing.gif"
PATH_MACHAN = FOLDER_WIDGET / "umaaji.png"
PATH_BTN_IMPORT = FOLDER_WIDGET / "import.png"

# サムネイルアイコン
PATH_BG_FOLDER = FOLDER_BACKGROUND / "フォルダ背景.png"
PATH_BG_ANIMATION = FOLDER_BACKGROUND / "アニメーション背景.png"
PATH_BG_PHOTO = FOLDER_BACKGROUND / "静止画背景.png"
PATH_BG_FILE = FOLDER_BACKGROUND / "ファイル背景.png"
PATH_BG_PARTS = FOLDER_BACKGROUND / "パーツ背景.png"

PATH_BG_UNSELECTED = FOLDER_BACKGROUND / "未選択.png"
PATH_BUTTON_UNKNOWN = FOLDER_BUTTON / "Unknown.png"

BG_FOLDER = Image.open(PATH_BG_FOLDER).convert("RGBA")
BG_ANIMATION = Image.open(PATH_BG_ANIMATION).convert("RGBA")
BG_PHOTO = Image.open(PATH_BG_PHOTO).convert("RGBA")
BG_FILE = Image.open(PATH_BG_FILE).convert("RGBA")
BG_PARTS = Image.open(PATH_BG_PARTS).convert("RGBA")
BG_UNSELECTED = Image.open(PATH_BG_UNSELECTED).convert("RGBA")
BMP_UNSELECTED = wx.Bitmap.FromBufferRGBA(*BG_UNSELECTED.size, BG_UNSELECTED.tobytes())

BMP_MACHAN = Image.open(PATH_MACHAN).convert("RGBA")
BMP_MACHAN = wx.Bitmap.FromBufferRGBA(*BMP_MACHAN.size, BMP_MACHAN.tobytes())

# 加工画像パス
PATH_GIF_PREVIEW = FOLDER_MATERIAL / "preview.gif"
PATH_MASK_COSTUME = FOLDER_MATERIAL / "mask_costume.gif"
PATH_MASK_FACE = FOLDER_MATERIAL / "mask_face.png"

# フォント
PATH_FONT_GENEI = FOLDER_DATA / "Font/GenEiNuGothic-EB_v1.1/GenEiNuGothic-EB.ttf"
FACE_FONT_GENEI = "源暎Nuゴシック EB"
wx.Font.AddPrivateFont(str(PATH_FONT_GENEI))

# 取り込める拡張子
SUFFIXES_IMAGE = [".jpg", ".jpeg", ".png", ".gif",
                  ".JPG", ".JPEG", ".PNG", ".GIF"]
