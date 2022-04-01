import sys

import wx
from wx.adv import AnimationCtrl
from wx.lib.newevent import NewEvent
from wx.lib.scrolledpanel import ScrolledPanel
from wx.lib.agw.floatspin import FloatSpin, EVT_FLOATSPIN
import ctypes
import threading
import numpy as np
import win32gui, win32con

from config import *
from compositor import CompositeImage
import extra

EVENT_UPDATE, EVT_UPDATE = NewEvent()
EVENT_APPEND, EVT_APPEND = NewEvent()


class ThumbnailPanel(ScrolledPanel):
    def __init__(self, parent, dest, path_folder):
        super().__init__(parent, size=(620, 320))
        self.parent = parent
        self.dest = dest
        self.path_folder = path_folder
        self.sizer = wx.BoxSizer(wx.VERTICAL)
        self.setting_widgets()
        self.show_dir(path_folder)

    def setting_widgets(self):
        self.SetupScrolling(scroll_x=False)
        self.SetBackgroundColour("#FFFFFF")
        self.Bind(wx.EVT_MOUSEWHEEL, self.on_scroll)

    def on_scroll(self, event):
        pos_delta = 1 if 0 > event.GetWheelRotation() else -1
        orientation = event.GetWheelAxis()
        pos_cur = self.GetScrollPos(orientation)
        scrollrange = (self.GetScrollRange(orientation)
                       - np.clip(self.GetScrollThumb(orientation), 1, None))
        pos_next = pos_cur + pos_delta
        within_scroll_range = 0 <= pos_next <= scrollrange

        if within_scroll_range:
            event.Skip()
        else:
            self.Parent.Parent.GetEventHandler().ProcessEvent(event)

    def create_thumbnail(self, path_image):
        image = Image.open(path_image).convert("RGBA")
        bbox = image.getbbox()
        image = image.crop(bbox)
        image.thumbnail(SIZE_THUMBNAIL, Image.LANCZOS)
        image_campus = Image.new("RGBA", SIZE_THUMBNAIL, (255, 255, 255, 0))

        offset = [(dim_thumb - dim) // 2 for dim_thumb, dim in zip(SIZE_THUMBNAIL, image.size)]
        image_campus.paste(image, offset)
        bmp = wx.Bitmap.FromBufferRGBA(*SIZE_THUMBNAIL, image_campus.tobytes())

        return bmp

    def show_dir(self, path_folder):
        lst_path_image = [path_image for path_image in path_folder.iterdir()]
        lst_path_image = lst_path_image + [None] * (5 - (len(lst_path_image) % 5))
        nd_path_image = np.array(lst_path_image).reshape([-1, 5])

        for row in nd_path_image:
            sizer_row = wx.BoxSizer()
            for path_image in row:
                if not path_image:
                    break

                if path_image.is_dir():
                    path_btn = FOLDER_BTN / f"{path_image.name}.png"
                    if not path_btn.exists():
                        continue
                else:
                    path_btn = path_image

                bmp_thumb = self.create_thumbnail(path_btn)
                bbtn = wx.BitmapButton(self, -1, bmp_thumb)
                text = wx.StaticText(self, -1, path_image.stem,
                                     style=wx.ALIGN_CENTER | wx.ST_ELLIPSIZE_END,
                                     size=(10, 26))

                bbtn.Bind(wx.EVT_BUTTON, self.on_btn(path_image))
                sizer_item = wx.BoxSizer(wx.VERTICAL)
                sizer_item.Add(bbtn, 0)
                sizer_item.Add(text, 0, wx.GROW)
                sizer_row.Add(sizer_item, 0, wx.ALL, 5)

            self.sizer.Add(sizer_row, 0, wx.GROW)

        self.SetSizer(self.sizer)
        self.sizer.Fit(self)

    def on_btn(self, path_image):
        def inner(event):
            if path_image.is_dir():
                self.parent.on_select(path_image)(None)
            else:
                wx.PostEvent(self.dest, EVENT_APPEND(path_image=path_image, frames=None))
                if self.path_folder.parent == FOLDER_MATERIAL / BASE:
                    path_transparent = (FOLDER_MATERIAL / TRANSPARENT /
                                        path_image.name.replace("顔無し", "肌透過"))
                    if path_transparent.exists():
                        wx.PostEvent(self.dest,
                                     EVENT_APPEND(path_image=path_transparent, frames=None))

        return inner


class ImageAppendPanel(wx.Panel):
    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent
        self.frame_main = self.parent.GetParent()
        self.panel_thumb = ThumbnailPanel(self, self.frame_main, FOLDER_MATERIAL / BASE)
        sbox_append = wx.StaticBox(self, -1, "画像追加")
        self.sbsizer_append = wx.StaticBoxSizer(sbox_append, wx.VERTICAL)
        self.sizer_thumb = wx.BoxSizer(wx.VERTICAL)
        self.setting_widgets()

    def setting_widgets(self):
        sizer_btn = wx.BoxSizer()
        sizer_import = wx.BoxSizer(wx.VERTICAL)
        for parts in ORDER_COMPOSITE_DEFAULT:
            bmp = wx.Bitmap(str(FOLDER_BTN / f"{parts}.png"))
            btn = wx.BitmapButton(self, -1, bmp)
            folder_parts = FOLDER_MATERIAL / parts
            btn.Bind(wx.EVT_BUTTON, self.on_select(folder_parts))
            sizer_btn.Add(btn, 0, wx.ALL, 5)

        bmp_import = wx.Bitmap(str(FOLDER_BTN / "import.png"))
        btn_import = wx.BitmapButton(self, -1, bmp_import)
        btn_import.Bind(wx.EVT_BUTTON, self.on_import)
        sizer_import.Add(btn_import, 0, wx.ALIGN_RIGHT)
        sizer_btn.Add(sizer_import, 1, wx.GROW | wx.ALL, 5)

        self.sizer_thumb.Add(self.panel_thumb, 1, wx.GROW)
        self.sbsizer_append.Add(sizer_btn, 0, wx.GROW | wx.ALL, 10)
        self.sbsizer_append.Add(self.sizer_thumb, 1, wx.GROW | wx.ALL, 10)
        self.SetSizer(self.sbsizer_append)

    def on_select(self, path_folder):
        def inner(event):
            self.panel_thumb.Destroy()
            self.panel_thumb = ThumbnailPanel(self, self.frame_main, path_folder)
            self.sizer_thumb.Add(self.panel_thumb, 1, wx.GROW)
            self.sbsizer_append.Layout()

        return inner

    def on_import(self, event):
        with wx.FileDialog(self.parent.GetParent(), "取り込みたい画像を選択してください。", "外部画像取込",
                           wildcard="*.png;*.gif") as dial:
            result = dial.ShowModal()
            if not result == wx.ID_OK:
                return

            path_image = pathlib.Path(dial.GetPath())
            wx.PostEvent(self.frame_main, EVENT_APPEND(path_image=path_image, frames=None))


class PreviewPanel(wx.Panel):
    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent
        self.timer_duration = wx.Timer()
        self.sizer = wx.BoxSizer()
        self.sbmp_preview = wx.StaticBitmap(self, -1)
        self.bmp_preview = wx.Bitmap()
        self.ctrl_preview = AnimationCtrl(self, -1)
        self.setting_widgets()

    def setting_widgets(self):
        self.SetMinSize(DEFAULT_BASE_SIZE)
        self.sbmp_preview.SetBackgroundStyle(wx.BG_STYLE_CUSTOM)
        self.sbmp_preview.Bind(wx.EVT_PAINT, self.on_paint)
        self.sbmp_preview.Bind(wx.EVT_MOUSE_EVENTS, self.on_mouse)
        self.ctrl_preview.Bind(wx.EVT_MOUSE_EVENTS, self.on_mouse)

        self.sizer.Add(self.ctrl_preview, 1, wx.GROW)
        self.SetSizer(self.sizer)

    def load_frame(self, image):
        bmp = wx.Bitmap.FromBufferRGBA(*image.size, image.tobytes())
        self.bmp_preview = bmp

    def show_frame(self):
        self.sbmp_preview.SetBitmap(self.bmp_preview)
        self.ctrl_preview.Hide()
        self.sbmp_preview.Show()
        self.ctrl_preview.Stop()
        self.SetMinSize(self.sbmp_preview.GetSize())

    def show_animation(self):
        self.ctrl_preview.LoadFile(str(PATH_GIF_PREVIEW))
        self.sbmp_preview.Hide()
        self.ctrl_preview.Show()
        self.ctrl_preview.Play()

    def on_mouse(self, event):
        wx.PostEvent(self, event)

    def on_play(self):
        if self.ctrl_preview.IsPlaying():
            self.show_frame()
        else:
            self.show_animation()

    def is_playing(self):
        return self.ctrl_preview.IsPlaying()

    def change_frame(self, bmp: wx.Bitmap):
        self.sbmp_preview.SetBitmap(bmp)

    def on_paint(self, event):
        if self.bmp_preview and self.sbmp_preview:
            dc = wx.AutoBufferedPaintDC(self.sbmp_preview)
            dc.Clear()
            dc.DrawBitmap(self.bmp_preview, 0, 0)


class ExtraMenuBar(wx.MenuBar):
    def __init__(self):
        super().__init__()
        menu_config, menu_extra = wx.Menu(), wx.Menu()
        menu_change_size = menu_config.Append(-1, "サイズ変更")
        menu_transparent = menu_extra.Append(-1, "肌透過画像追加", "肌と思しき部分を透過して画像一覧に追加します。")
        self.Bind(wx.EVT_MENU, self.on_transparent, menu_transparent)

        menu_separate = menu_extra.Append(-1, "アニメーション画像分割", "選択したアニメーション画像をフレームごとに分割します。")
        menu_connect = menu_extra.Append(-1, "GIF作成", "フォルダ内のPNGを名前順に結合してGIF画像を作成します。")
        # self.Append(menu_config, "設定")
        self.Append(menu_extra, "おまけ機能")

        self.Bind(wx.EVT_MENU, self.on_change_size, menu_change_size)

        self.Bind(wx.EVT_MENU, self.on_separate, menu_separate)
        self.Bind(wx.EVT_MENU, self.on_connect, menu_connect)

    def on_change_size(self, event):
        print("on_change")

    def on_transparent(self, event):
        extra.create_transparent(self.Parent, EVENT_APPEND)

    def on_separate(self, event):
        extra.separate_animation()

    def on_connect(self, event):
        extra.connect_frames(self.Parent.spin_duration.GetValue())


class MainFrame(wx.Frame):
    def __init__(self):
        super().__init__(None, -1, "たぬこら")
        self.image_composite = CompositeImage()

        self.panel = ScrolledPanel(self)

        # プレビュー
        self.spin_frame = wx.SpinCtrl(self.panel, -1, value="1", min=1, max=1,
                                      style=wx.TE_PROCESS_ENTER | wx.SP_HORIZONTAL | wx.SP_WRAP)
        self.text_frame = wx.StaticText(self.panel, -1, "/1", style=wx.ALIGN_LEFT)
        self.slider_h = wx.Slider(self.panel, -1, value=0, minValue=-250, maxValue=250,
                                  style=STYLE_SLIDER)
        self.slider_v = wx.Slider(self.panel, -1, value=0, minValue=-300, maxValue=300,
                                  style=STYLE_SLIDER | wx.SL_VERTICAL)
        self.text_offset = wx.StaticText(self.panel, -1, "X：0 , Y：0", style=wx.ALIGN_LEFT)
        self.panel_preview = PreviewPanel(self.panel)

        # プロパティ
        self.text_image_selected = wx.StaticText(self.panel, -1, "未選択", style=wx.ALIGN_LEFT)
        self.spin_angle = wx.SpinCtrl(self.panel, -1, value="0", min=-360, max=360,
                                      style=wx.TE_PROCESS_ENTER)
        self.spin_zoom = wx.SpinCtrlDouble(self.panel, -1, value="1.0", min=0.1, max=3.0,
                                           inc=0.01, style=wx.TE_PROCESS_ENTER)
        for child in self.spin_zoom.GetChildren():
            if type(child) is wx.TextCtrl:
                self.tc_zoom = child

        # パーツオプション
        self.check_alias = wx.CheckBox(self.panel, -1, "アンチエイリアス")
        self.check_flip = wx.CheckBox(self.panel, -1, "左右反転")
        self.check_alignment = wx.CheckBox(self.panel, -1, "位置合わせ")
        self.combo_alignment = wx.ComboBox(self.panel, -1, style=wx.CB_DROPDOWN | wx.CB_READONLY)
        self.check_color = wx.CheckBox(self.panel, -1, "色乗算")
        self.ctrl_color = wx.ColourPickerCtrl(self.panel, -1)

        # 画像追加
        self.panel_append = ImageAppendPanel(self.panel)

        # 画像一覧
        self.btn_remove = wx.Button(self.panel, -1, "削除")
        self.btn_clear = wx.Button(self.panel, -1, "ALLクリア")
        self.rlc_image = wx.RearrangeList(self.panel, -1)
        self.btn_up = wx.Button(self.panel, -1, "画面奥")
        self.btn_down = wx.Button(self.panel, -1, "画面手前")

        # 画像全体
        self.check_size_specified = wx.CheckBox(self.panel, -1, "")
        self.spin_width = FloatSpin(self.panel, -1, max_val=1000, min_val=500, increment=50,
                                    style=wx.TE_PROCESS_ENTER)
        self.spin_height = FloatSpin(self.panel, -1, max_val=1000, min_val=500, increment=50,
                                     style=wx.TE_PROCESS_ENTER)
        # self.check_frames_specified = wx.CheckBox(self.panel, -1, "")
        # self.spin_frames_specified = wx.SpinCtrl(self.panel, -1, max=16, min=1,
        #                                          style=wx.TE_PROCESS_ENTER)
        self.spin_duration = wx.SpinCtrl(self.panel, -1, value="100", min=20, max=1000,
                                         style=wx.TE_PROCESS_ENTER)
        self.combo_filter_image = wx.ComboBox(self.panel, -1, style=wx.CB_DROPDOWN | wx.CB_READONLY)
        self.combo_filter_color = wx.ComboBox(self.panel, -1, style=wx.CB_DROPDOWN | wx.CB_READONLY)
        self.btn_play = wx.Button(self.panel, -1, "再生")
        self.btn_save = wx.Button(self.panel, -1, "保存")

        self.lst_ctrl_property = [self.slider_v, self.slider_h, self.spin_angle, self.spin_zoom,
                                  self.check_alias, self.check_flip,
                                  self.check_alignment, self.combo_alignment,
                                  self.check_color, self.ctrl_color]

        self.sizer_main = wx.BoxSizer()
        self.setting_widgets()
        self.delay_update = wx.CallLater(DELAY_UPDATE, self.update_composite)
        self.thread_update = None
        self.panel_preview.SetFocus()
        self.update_composite()
        self.Centre()

    def setting_widgets(self):
        self.SetIcon(wx.Icon(str(PATH_ICON)))
        self.SetMenuBar(ExtraMenuBar())
        self.CreateStatusBar()

        self.panel.SetupScrolling(scrollToTop=False, scrollIntoView=False)
        self.panel.SetDoubleBuffered(True)
        self.ctrl_color.Disable()
        self.ctrl_color.SetColour((255, 0, 0))
        [ctrl.Disable() for ctrl in self.lst_ctrl_property]
        self.combo_alignment.Append(LST_ALIGNMENT)
        self.combo_alignment.SetValue(ALIGNMENT_NONE)

        self.slider_h.SetTickFreq(50)
        self.slider_v.SetTickFreq(50)

        self.spin_width.Disable()
        self.spin_height.Disable()
        self.spin_width.SetDigits(0)
        self.spin_height.SetDigits(0)
        # self.spin_frames_specified.Disable()
        self.combo_filter_image.Append(LST_FILTER_IMAGE)
        self.combo_filter_color.Append(LST_FILTER_COLOR)

        # バインド
        self.btn_remove.Bind(wx.EVT_BUTTON, self.on_remove(False))
        self.btn_clear.Bind(wx.EVT_BUTTON, self.on_remove(True))
        self.rlc_image.Bind(wx.EVT_MOUSEWHEEL, self.on_scroll)
        self.rlc_image.Bind(wx.EVT_CHECKLISTBOX, self.on_check_image)
        self.rlc_image.Bind(wx.EVT_LISTBOX, self.on_select_image)
        self.btn_up.Bind(wx.EVT_BUTTON, self.on_move(True))
        self.btn_down.Bind(wx.EVT_BUTTON, self.on_move(False))

        self.panel_preview.Bind(wx.EVT_MOUSE_EVENTS, self.on_mouse)

        self.check_alias.Bind(wx.EVT_CHECKBOX, self.on_change_parts_properties)
        self.check_flip.Bind(wx.EVT_CHECKBOX, self.on_change_parts_properties)

        self.check_alignment.Bind(wx.EVT_CHECKBOX, self.on_alignment)
        self.combo_alignment.Bind(wx.EVT_COMBOBOX, self.on_alignment)

        self.check_color.Bind(wx.EVT_CHECKBOX, self.on_check_color)
        self.ctrl_color.Bind(wx.EVT_COLOURPICKER_CURRENT_CHANGED, self.on_change_color)

        self.slider_h.Bind(wx.EVT_SLIDER, self.on_change_parts_properties)
        self.slider_v.Bind(wx.EVT_SLIDER, self.on_change_parts_properties)

        self.spin_frame.Bind(wx.EVT_SPINCTRL, self.on_change_parts_properties)
        self.spin_frame.Bind(wx.EVT_TEXT_ENTER, self.on_change_parts_properties)
        self.spin_angle.Bind(wx.EVT_SPINCTRL, self.on_change_parts_properties)
        self.spin_angle.Bind(wx.EVT_TEXT_ENTER, self.on_change_parts_properties)
        self.spin_zoom.Bind(wx.EVT_SPINCTRLDOUBLE, self.on_change_parts_properties)
        self.spin_zoom.Bind(wx.EVT_TEXT_ENTER, self.on_change_parts_properties)

        self.check_size_specified.Bind(wx.EVT_CHECKBOX, self.on_check_size)

        self.spin_width.Bind(wx.EVT_TEXT_ENTER, self.on_change_composite_properties)
        self.spin_width.Bind(EVT_FLOATSPIN, self.on_change_composite_properties)
        self.spin_height.Bind(wx.EVT_TEXT_ENTER, self.on_change_composite_properties)
        self.spin_height.Bind(EVT_FLOATSPIN, self.on_change_composite_properties)
        # self.check_frames_specified.Bind(wx.EVT_CHECKBOX, self.on_check_frames)
        # self.spin_frames_specified.Bind(wx.EVT_TEXT_ENTER, self.on_change_composite_properties)
        # self.spin_frames_specified.Bind(wx.EVT_SPINCTRL, self.on_change_composite_properties)
        self.spin_duration.Bind(wx.EVT_TEXT_ENTER, self.on_change_composite_properties)
        self.spin_duration.Bind(wx.EVT_SPINCTRL, self.on_change_composite_properties)
        self.combo_filter_image.Bind(wx.EVT_COMBOBOX, self.on_change_composite_properties)
        self.combo_filter_color.Bind(wx.EVT_COMBOBOX, self.on_change_composite_properties)

        self.Bind(EVT_APPEND, self.on_append)
        self.Bind(wx.EVT_ACTIVATE, self.on_deactivate)

        # オフセット操作のためにキー入力をインターセプト
        widgets_key_intercept = [self.rlc_image, self.panel_append,
                                 self.slider_h, self.slider_v, self.panel_preview,
                                 self.combo_filter_image, self.combo_filter_color, self.btn_play,
                                 self.btn_save]

        for widget in widgets_key_intercept:
            widget.Bind(wx.EVT_CHAR_HOOK, self.on_keyboard)

        # ホイールスクロールの邪魔になるウィジェット
        widgets_scroll_avoid = [self.slider_v, self.slider_h,
                                self.combo_alignment,
                                self.spin_width, self.spin_height,
                                self.combo_filter_image, self.combo_filter_color]

        for widget in widgets_scroll_avoid:
            widget.Bind(wx.EVT_MOUSEWHEEL, lambda e: self.panel.GetEventHandler().ProcessEvent(e))
            for child in widget.Children:
                child.Bind(wx.EVT_MOUSEWHEEL,
                           lambda e: self.panel.GetEventHandler().ProcessEvent(e))

        self.btn_play.Bind(wx.EVT_BUTTON, self.on_play)
        self.btn_save.Bind(wx.EVT_BUTTON, self.on_save)

        self.Bind(EVT_UPDATE, self.on_update_composite)
        self.Bind(wx.EVT_CLOSE, self.on_close)

        # プレビュー
        fxsizer_preview = wx.FlexGridSizer(rows=2, cols=2, gap=(0, 0))
        gbsizer_status = wx.GridBagSizer()

        gbsizer_status.Add(wx.StaticText(self.panel, -1, "フレーム", style=wx.ALIGN_CENTER), (0, 0),
                           (1, 2), wx.GROW)
        gbsizer_status.Add(self.spin_frame, (1, 0), (1, 1), wx.GROW)
        gbsizer_status.Add(self.text_frame, (1, 1), (1, 1), wx.GROW | wx.ALIGN_CENTER_VERTICAL)

        fxsizer_preview.AddGrowableCol(1)
        fxsizer_preview.AddGrowableRow(1)
        fxsizer_preview.Add(gbsizer_status, 1, wx.ALIGN_RIGHT | wx.ALIGN_BOTTOM)
        fxsizer_preview.Add(self.slider_h, 1, wx.GROW | wx.ALIGN_BOTTOM)
        fxsizer_preview.Add(self.slider_v, 1, wx.GROW | wx.ALIGN_RIGHT)
        fxsizer_preview.Add(self.panel_preview, 1, wx.GROW)

        # プロパティ
        # パーツオプション
        sbox_parts = wx.StaticBox(self.panel, -1, "パーツプロパティ")
        sbsizer_parts = wx.StaticBoxSizer(sbox_parts, wx.VERTICAL)
        sizer_selected = wx.BoxSizer()
        sizer_parts = wx.BoxSizer()
        fxsizer_alignment = wx.FlexGridSizer(rows=3, cols=2, gap=(15, 5))
        fxsizer_option = wx.FlexGridSizer(rows=6, cols=2, gap=(5, 5))

        sizer_selected.Add(wx.StaticText(self.panel, -1, "選択中画像：", style=wx.ALIGN_LEFT),
                           0, wx.ALL, 5)
        sizer_selected.Add(self.text_image_selected, -1, wx.ALL | 5)

        fxsizer_alignment.Add(wx.StaticText(self.panel, -1, "オフセット", style=wx.ALIGN_LEFT), 0,
                              wx.GROW)
        fxsizer_alignment.Add(self.text_offset,
                              0,
                              wx.GROW)
        fxsizer_alignment.Add(wx.StaticText(self.panel, -1, "回転", style=wx.ALIGN_LEFT), 0, wx.GROW)
        fxsizer_alignment.Add(self.spin_angle, 0, wx.GROW)
        fxsizer_alignment.Add(wx.StaticText(self.panel, -1, "拡大率", style=wx.ALIGN_LEFT), 0,
                              wx.GROW)
        fxsizer_alignment.Add(self.spin_zoom, 0, wx.GROW)

        fxsizer_option.Add(self.check_alias, 0, wx.GROW)
        fxsizer_option.Add(self.check_flip, 0, wx.GROW)
        fxsizer_option.Add(self.check_alignment, 0, wx.GROW)
        fxsizer_option.Add(self.combo_alignment, 0, wx.GROW)
        fxsizer_option.Add(self.check_color, 0, wx.GROW)
        fxsizer_option.Add(self.ctrl_color, 0, wx.GROW)

        sizer_parts.Add(fxsizer_alignment, 0, wx.ALL, 10)
        sizer_parts.Add(wx.StaticText(self.panel, -1, ""), wx.LEFT | wx.Right, 20)
        sizer_parts.Add(fxsizer_option, 0, wx.ALL, 10)

        sbsizer_parts.Add(sizer_selected, 0, wx.GROW)
        sbsizer_parts.Add(sizer_parts, 1, wx.GROW)

        # 合成画像全体
        sbox_composite = wx.StaticBox(self.panel, -1, "合成プロパティ")
        sbsizer_composite = wx.StaticBoxSizer(sbox_composite, wx.VERTICAL)
        sizer_param = wx.BoxSizer()
        sizer_filter = wx.BoxSizer(wx.VERTICAL)

        fxsizer_size = wx.FlexGridSizer(rows=3, cols=4, gap=(0, 0))
        fxsizer_size.Add(wx.StaticText(self.panel, -1, "", style=wx.ALIGN_CENTER), 0, wx.GROW)
        fxsizer_size.Add(wx.StaticText(self.panel, -1, "幅", style=wx.ALIGN_CENTER), 0, wx.GROW)
        fxsizer_size.Add(wx.StaticText(self.panel, -1, "", style=wx.ALIGN_CENTER), 0, wx.GROW)
        fxsizer_size.Add(wx.StaticText(self.panel, -1, "高さ", style=wx.ALIGN_CENTER), 0, wx.GROW)
        fxsizer_size.Add(self.check_size_specified, 0, wx.GROW)
        fxsizer_size.Add(self.spin_width, 0, wx.GROW)
        font = wx.Font(12, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL)
        text_x = wx.StaticText(self.panel, -1, "×", style=wx.ALIGN_CENTER)
        text_x.SetFont(font)
        fxsizer_size.Add(text_x, 0, wx.ALIGN_CENTER_VERTICAL | wx.GROW)
        fxsizer_size.Add(self.spin_height, 0, wx.GROW)

        # fxsizer_frames = wx.FlexGridSizer(rows=2, cols=2, gap=(0, 0))
        # fxsizer_frames.Add(wx.StaticText(self.panel, -1, "", style=wx.ALIGN_CENTER), 0, wx.GROW)
        # fxsizer_frames.Add(wx.StaticText(self.panel, -1, "総フレーム数", style=wx.ALIGN_CENTER), 0,
        #                    wx.ALIGN_CENTER_VERTICAL)
        # fxsizer_frames.Add(self.check_frames_specified, 0, wx.GROW)
        # fxsizer_frames.Add(self.spin_frames_specified, 0, wx.GROW)

        sizer_duration = wx.BoxSizer(wx.VERTICAL)
        sizer_duration.Add(wx.StaticText(self.panel, -1, "表示間隔"), 0)
        sizer_duration.Add(self.spin_duration, 0)

        sizer_param.Add(fxsizer_size, 0, wx.GROW | wx.RIGHT, 30)
        # sizer_param.Add(fxsizer_frames, 0, wx.GROW | wx.LEFT | wx.RIGHT, 30)
        sizer_param.Add(sizer_duration, 0, wx.GROW)

        fxsizer_filter = wx.FlexGridSizer(rows=2, cols=2, gap=(5, 5))
        fxsizer_filter.Add(wx.StaticText(self.panel, -1, "画像フィルタ", style=wx.ALIGN_CENTER), 1,
                           wx.GROW)
        fxsizer_filter.Add(wx.StaticText(self.panel, -1, "色フィルタ", style=wx.ALIGN_CENTER), 1,
                           wx.GROW)

        fxsizer_filter.Add(self.combo_filter_image, 1, wx.GROW)
        fxsizer_filter.Add(self.combo_filter_color, 1, wx.GROW)

        sizer_btn_composite = wx.BoxSizer()
        sizer_btn_composite.Add(self.btn_save, 1, wx.GROW)
        sizer_btn_composite.Add(wx.StaticText(self.panel, -1, ""), 1, wx.GROW)
        sizer_btn_composite.Add(self.btn_play, 1, wx.GROW)

        sizer_filter.Add(sizer_param, 0, wx.GROW | wx.ALL, 10)
        sizer_filter.Add(fxsizer_filter, 0, wx.GROW | wx.ALL, 10)
        sizer_filter.Add(sizer_btn_composite, 1, wx.GROW | wx.ALL, 10)

        sbsizer_composite.Add(sizer_filter, 0, wx.GROW)

        sizer_property = wx.BoxSizer(wx.VERTICAL)
        sizer_property.Add(sbsizer_parts, 0, wx.GROW)
        sizer_property.Add(sbsizer_composite, 0, wx.GROW)

        # 画像一覧
        sbox_imagelist = wx.StaticBox(self.panel, -1, "画像一覧")
        sbsizer_imagelist = wx.StaticBoxSizer(sbox_imagelist, wx.VERTICAL)
        sizer_rlc = wx.BoxSizer()
        sizer_btn_imagelist = wx.BoxSizer(wx.VERTICAL)

        sizer_btn_imagelist.Add(self.btn_up, 0, wx.ALL, 5)
        sizer_btn_imagelist.Add(self.btn_down, 0, wx.ALL, 5)
        sizer_btn_imagelist.Add(wx.StaticText(self.panel, -1, ""), 0, wx.ALL, 5)
        sizer_btn_imagelist.Add(self.btn_remove, 0, wx.ALL, 5)
        sizer_btn_imagelist.Add(self.btn_clear, 0, wx.ALL, 5)

        sizer_rlc.Add(self.rlc_image, 1, wx.GROW | wx.ALL, 5)
        sizer_rlc.Add(sizer_btn_imagelist, 0, wx.ALIGN_CENTER_VERTICAL | wx.ALL, 5)
        sbsizer_imagelist.Add(sizer_rlc, 1, wx.GROW | wx.ALL, 5)

        fxsizer_main = wx.FlexGridSizer(rows=2, cols=2, gap=(5, 5))
        fxsizer_main.Add(fxsizer_preview, 0, wx.GROW)
        fxsizer_main.Add(self.panel_append, 0, wx.GROW)
        fxsizer_main.Add(sizer_property, 0, wx.GROW)
        fxsizer_main.Add(sbsizer_imagelist, 0, wx.GROW)
        self.sizer_main.Add(fxsizer_main, 0, wx.GROW | wx.ALL, 10)
        self.panel.SetSizer(self.sizer_main)
        self.fit_contains_scrollbar()

    def on_keyboard(self, event):
        if not self.is_selected_image():
            return

        keycode = event.GetKeyCode()
        if keycode in [wx.WXK_UP, wx.WXK_DOWN]:
            delta = -1 if keycode == wx.WXK_UP else 1
            self.slider_v.SetValue(self.slider_v.GetValue() + delta)
        elif keycode in [wx.WXK_LEFT, wx.WXK_RIGHT]:
            delta = -1 if keycode == wx.WXK_LEFT else 1
            self.slider_h.SetValue(self.slider_h.GetValue() + delta)
        else:
            return

        self.on_change_parts_properties(None)

    def on_check_size(self, event):
        is_checked = self.check_size_specified.GetValue()
        self.spin_width.Enable(is_checked)
        self.spin_height.Enable(is_checked)
        self.on_change_composite_properties(None)

    # def on_check_frames(self, event):
    #     is_checked = self.check_size_specified.GetValue()
    #     self.spin_frames_specified.Enable(is_checked)
    #     self.on_change_composite_properties(None)

    def on_change_composite_properties(self, event):
        size_specify = ([int(self.spin_width.GetValue()), int(self.spin_height.GetValue())]
                        if self.check_size_specified.GetValue() else None)

        # count_frames_specify = (self.spin_frames_specified.GetValue()
        #                         if self.check_frames_specified.GetValue() else None)

        count_frames_specify = None

        filter_image = self.combo_filter_image.GetValue()
        filter_color = self.combo_filter_color.GetValue()
        duration = self.spin_duration.GetValue()
        self.image_composite.set_params(size_specify, count_frames_specify, filter_image,
                                        filter_color, duration)
        self.start_delay_update()

    def on_change_parts_properties(self, event):
        if self.is_selected_image():
            ix_selected = self.rlc_image.GetSelection()
            id_image = self.rlc_image.GetClientData(ix_selected)
            ix_frame = self.spin_frame.GetValue() - 1
            offset = (self.slider_h.GetValue(), self.slider_v.GetValue())
            angle, zoom = self.spin_angle.GetValue(), float(self.tc_zoom.GetValue())
            anti_alias = self.check_alias.GetValue()
            is_flip = self.check_flip.GetValue()

            alignment = (self.combo_alignment.GetValue()
                         if self.check_alignment.GetValue() else None)

            color_multiply = (self.ctrl_color.GetColour()[:-1]
                              if self.check_color.GetValue() else None)

            x, y = offset
            self.text_offset.SetLabel(f"X：{x} , Y：{y}")
            self.image_composite.set_properties(id_image, ix_frame, offset, angle, zoom, anti_alias,
                                                is_flip, alignment, color_multiply)

        self.start_delay_update()

    def on_mouse(self, event):
        event.GetEventObject().SetFocus()
        type_event = event.GetEventType()

        if type_event in [wx.wxEVT_LEFT_DOWN, wx.wxEVT_LEFT_DCLICK, wx.wxEVT_RIGHT_DOWN,
                          wx.wxEVT_RIGHT_DCLICK]:
            angle_delta = 1 if type_event in [wx.wxEVT_RIGHT_DOWN, wx.wxEVT_RIGHT_DCLICK] else -1
            num_frame = self.spin_frame.GetValue() + angle_delta
            count_frames = self.spin_frame.GetMax()
            num_frame = 1 if num_frame > count_frames else num_frame
            num_frame = count_frames if num_frame <= 0 else num_frame
            self.spin_frame.SetValue(num_frame)
            self.set_properties()
            self.start_delay_update()

        elif type_event == wx.wxEVT_MOUSEWHEEL and self.is_selected_image():
            rotation = event.GetWheelRotation()
            rotation = rotation / abs(rotation)
            self.spin_angle.SetValue(int(self.spin_angle.GetValue() + rotation))
            self.on_change_parts_properties(None)

    def on_alignment(self, event):
        is_checked = self.check_alignment.GetValue()
        self.combo_alignment.Enable(is_checked)
        self.on_change_parts_properties(None)

    def on_check_color(self, event):
        is_checked = self.check_color.GetValue()
        self.ctrl_color.Enable(is_checked)
        self.on_change_parts_properties(None)

    def on_change_color(self, event):
        color_changed = event.GetColour()[:-1]
        self.ctrl_color.SetColour(color_changed)
        self.on_change_parts_properties(None)

    def on_deactivate(self, event):
        if event.GetActive():
            return

        hwnd_dial = win32gui.FindWindow(None, "色の設定")
        if not hwnd_dial:
            return

        pos = self.Position[0] + self.Size[0] // 2, self.Position[1]
        xl, yl, xr, yr = win32gui.GetWindowRect(hwnd_dial)
        width, height = xr - xl, yr - yl
        try:
            win32gui.SetWindowPos(hwnd_dial, win32con.HWND_TOP, *pos, width, height,
                                  win32con.SWP_SHOWWINDOW)
        except Exception:
            pass

    # GetScrollThumbが0しか返さないのでスマートではない実装に
    def on_scroll(self, event):
        obj = event.GetEventObject()
        pos_delta = 1 if 0 > event.GetWheelRotation() else -1
        orientation = event.GetWheelAxis()
        pos_cur = obj.GetScrollPos(orientation)
        obj.SetScrollPos(orientation, pos_cur + pos_delta)
        pos_next = obj.GetScrollPos(orientation)
        within_scroll_range = (pos_cur != pos_next)
        if within_scroll_range:
            event.Skip()
        else:
            self.panel.GetEventHandler().ProcessEvent(event)

    def on_append(self, event):
        path_image, frames = event.path_image, event.frames
        id_image, count_frames, is_animated = self.image_composite.append(path_image, frames)
        label_animated = "【アニメ】" if is_animated else "【静止画】"
        name_display = path_image.stem + label_animated

        lst_id = [self.rlc_image.GetClientData(ix) for ix in range(self.rlc_image.GetCount())]

        if id_image in lst_id:
            ix_append = lst_id.index(id_image)
            self.rlc_image.SetString(ix_append, name_display)
        else:
            ix_append = self.rlc_image.Append(name_display, id_image)

        self.spin_frame.SetMax(count_frames)
        self.text_frame.SetLabel(f"/{count_frames}")
        self.rlc_image.Check(ix_append, True)
        self.rlc_image.Select(ix_append)
        self.on_select_image(None)
        self.update_composite()

    def on_remove(self, is_all):
        def inner(event):
            if is_all:
                with wx.MessageDialog(self, "画像一覧をすべてクリアしますか？", "ALLクリア",
                                      style=wx.OK | wx.CANCEL | wx.ICON_EXCLAMATION) as dial:
                    result = dial.ShowModal()
                    if result == wx.ID_OK:
                        self.image_composite.clear()
                        self.rlc_image.Clear()
                        self.spin_frame.SetMax(1)
                        self.text_frame.SetLabel(f"/1")
                        self.switch_ctrl_property()
                        self.update_composite()
                return

            ix_selected = self.rlc_image.GetSelection()
            if ix_selected < 0:
                return

            id_image = self.rlc_image.GetClientData(ix_selected)
            count_frames = self.image_composite.remove(id_image)

            self.spin_frame.SetMax(count_frames)
            self.text_frame.SetLabel(f"/{count_frames}")
            self.rlc_image.Delete(ix_selected)
            self.switch_ctrl_property()
            self.update_composite()

        return inner

    def on_select_image(self, event):
        self.switch_ctrl_property()
        self.set_properties()

    def on_check_image(self, event):
        lst_checked = self.rlc_image.GetCheckedItems()
        ids_visible = [self.rlc_image.GetClientData(ix) for ix in lst_checked]
        self.image_composite.set_visible(ids_visible)
        self.start_delay_update()

    def on_move(self, is_up):
        def inner(event):
            is_moved = self.rlc_image.MoveCurrentUp() if is_up else self.rlc_image.MoveCurrentDown()
            if is_moved:
                lst_id_sorted = [self.rlc_image.GetClientData(ix) for ix in
                                 range(self.rlc_image.Count)]
                self.image_composite.sort(lst_id_sorted)
                self.update_composite()

        return inner

    def on_play(self, event):
        if not self.image_composite.has_composite_image():
            with wx.MessageDialog(self, "表示する画像がありません。", "画像非表示",
                                  style=wx.ICON_ERROR) as dial:
                dial.ShowModal()

            return

        if self.delay_update.IsRunning():
            self.delay_update.Stop()

        if not self.panel_preview.is_playing():
            self.image_composite.save_gif()

        label_play = "再生" if self.panel_preview.is_playing() else "停止"
        self.panel_preview.on_play()
        self.btn_play.SetLabel(label_play)
        self.fit_contains_scrollbar()

    def on_save(self, event):
        if not self.image_composite.has_composite_image():
            with wx.MessageDialog(self, "表示する画像がありません。", "画像非表示",
                                  style=wx.ICON_ERROR) as dial:
                dial.ShowModal()

            return

        name_save = "合成たぬき.gif"
        with wx.FileDialog(self, "名前を付けて保存", wildcard="*.gif",
                           defaultFile=name_save,
                           style=wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT) as dial:
            result = dial.ShowModal()
            if not result == wx.ID_OK:
                return

            path_save = pathlib.Path(dial.GetPath())

        self.image_composite.save_gif(path_save, False)
        with wx.MessageDialog(self, "たぬき画像を保存しました。", "保存完了", style=wx.ICON_INFORMATION) as dial:
            dial.ShowModal()

    def switch_ctrl_property(self):
        label = self.rlc_image.GetStringSelection() if self.is_selected_image() else "未選択"
        self.text_image_selected.SetLabel(label)
        for ctrl in self.lst_ctrl_property:
            ctrl.Enable(self.is_selected_image())

    def set_properties(self):
        if not self.is_selected_image():
            return

        ix_frame = self.spin_frame.GetValue() - 1
        ix_selected = self.rlc_image.GetSelection()
        id_image = self.rlc_image.GetClientData(ix_selected)
        properties = self.image_composite.get_properties(id_image)
        offset_x, offset_y = properties.get("offset")[ix_frame]
        angle = properties.get("angle")[ix_frame]
        zoom = properties.get("zoom")
        anti_alias = properties.get("anti_alias")
        is_flip = properties.get("is_flip")
        alignment = properties.get("alignment")
        color_multiply = properties.get("color_multiply")

        self.slider_h.SetValue(offset_x)
        self.slider_v.SetValue(offset_y)
        self.text_offset.SetLabel(f"X：{offset_x} , Y：{offset_y}")
        self.spin_angle.SetValue(angle)
        self.tc_zoom.SetValue(str(zoom))
        self.check_alias.SetValue(anti_alias)
        self.check_flip.SetValue(is_flip)

        self.check_alignment.SetValue(bool(alignment))
        self.combo_alignment.Enable(bool(alignment))
        if alignment:
            self.combo_alignment.SetValue(alignment)

        self.check_color.SetValue(bool(color_multiply))
        self.ctrl_color.Enable(bool(color_multiply))
        if color_multiply:
            self.ctrl_color.SetColour(wx.Colour(color_multiply))

    def is_selected_image(self):
        return self.rlc_image.GetSelection() >= 0

    def start_delay_update(self):
        if self.delay_update.IsRunning():
            self.delay_update.Restart(DELAY_UPDATE)
        else:
            self.delay_update.Start(DELAY_UPDATE)

    def update_composite(self):
        self.thread_update = threading.Thread(target=self.composite_frame, daemon=True)
        self.thread_update.start()

    def composite_frame(self):
        ix = self.spin_frame.GetValue()
        frame_composite = self.image_composite.composite_frame(ix - 1)
        wx.PostEvent(self, EVENT_UPDATE(image=frame_composite))

    def on_update_composite(self, event):
        image = event.image
        width, height = image.size
        self.slider_h.SetMax(width // 2)
        self.slider_h.SetMin(-width // 2)
        self.slider_v.SetMax(height // 2)
        self.slider_v.SetMin(-height // 2)
        self.spin_width.SetValue(width)
        self.spin_height.SetValue(height)
        self.panel_preview.load_frame(image)
        self.panel_preview.show_frame()
        self.btn_play.SetLabel("再生")
        self.fit_contains_scrollbar()

    def fit_contains_scrollbar(self):
        self.panel.SetupScrolling(scrollToTop=False, scrollIntoView=False)
        width_sc, height_sc = (wx.SystemSettings.GetMetric(wx.SYS_VSCROLL_X),
                               wx.SystemSettings.GetMetric(wx.SYS_HSCROLL_Y))
        width, height = self.sizer_main.ComputeFittingWindowSize(self)
        size_contains = (np.clip(width + width_sc, None, WIDTH_WORKING),
                         np.clip(height + height_sc, None, HEIGHT_WORKING))

        size_current = self.GetSize()
        if not size_current == size_contains:
            width_cur, height_cur = size_current
            width_con, height_con = size_contains
            is_growth = width_cur < width_con or height_cur < height_con
            self.SetSize(size_contains)
            if is_growth:
                self.Centre()

    def on_close(self, event):
        with wx.MessageDialog(self, "終了してよろしいですか？", "終了確認",
                              style=wx.OK | wx.CANCEL | wx.ICON_INFORMATION) as dial:
            if dial.ShowModal() == wx.ID_OK:
                self.Destroy()


if __name__ == '__main__':
    ctypes.windll.shcore.SetProcessDpiAwareness(PROCESS_PER_MONITOR_DPI_AWARE)
    app = wx.App()

    name_instance = f"{app.GetAppName()}-{wx.GetUserId()}"
    instance = wx.SingleInstanceChecker(name_instance)
    if instance.IsAnotherRunning():
        wx.Exit()

    MainFrame().Show()
    app.MainLoop()
