import wx
from wx.lib.scrolledpanel import ScrolledPanel

import numpy as np
from PIL import Image, ImageDraw

import threading
from natsort import os_sorted

import const
from config import CONFIG
import wxlib
import widgets
import editor


class ImageSelectDialog(wx.Dialog):
    def __init__(self, parent, caption, id_replace=None):
        super().__init__(parent, -1, caption)
        self.path_image = None
        self.frames = None
        self.id_replace = id_replace

        self.panel = wx.Panel(self)
        self.panel_target = wx.Panel(self.panel)
        self.panel_append = widgets.ImageAppendPanel(self.panel, "画像選択", CONFIG.dir_dialog, True)
        self.sizer = wx.BoxSizer(wx.VERTICAL)
        self.setting_widgets()
        self.set_position()

    def setting_widgets(self):
        self.Bind(const.EVT_APPEND, self.on_append)

        if self.id_replace:
            color = const.COLOR_FILE if CONFIG.manager.is_file(
                self.id_replace) else const.COLOR_PARTS
            self.panel_append.SetBackgroundColour(color)

        if self.id_replace:
            image = CONFIG.manager.get_image(self.id_replace)
            panel_bmp = widgets.BitmapPanel(self.panel_target, bmp=image.get_bmp_icon())
            st_label = wx.StaticText(self.panel_target, -1, image.label)

            sizer_target = wx.BoxSizer()
            sizer_target.Add(wx.StaticText(self.panel_target, -1, "交換対象:"), 0, wx.ALIGN_CENTER)
            sizer_target.Add(panel_bmp)
            sizer_target.Add(st_label, 0, wx.ALIGN_CENTER)
            self.panel_target.SetSizer(sizer_target)

        self.sizer.Add(self.panel_target)
        self.sizer.Add(self.panel_append)
        self.panel.SetSizer(self.sizer)
        self.sizer.Fit(self)

    def set_position(self):
        left, top = self.GetParent().Position
        width, height = self.GetParent().Size
        right = left + width

        width_dial, height_dial = self.GetSize()
        self.SetPosition((np.clip(right - width_dial, 0, const.WIDTH_WORKING - width_dial),
                          np.clip(top, 0, const.HEIGHT_WORKING - height_dial)))

    def get_select_image(self):
        return self.path_image, self.frames, self.id_replace

    def on_append(self, event):
        self.path_image = event.path_image
        self.frames = event.frames
        CONFIG.dir_dialog = self.path_image.parent
        self.EndModal(wx.ID_OK)


class SelectionColorPanel(ScrolledPanel):
    def __init__(self, parent):
        super().__init__(parent)
        self.lst_icon = []
        self.colors_target = []
        self.sizer = wx.BoxSizer()
        self.SetSizer(self.sizer)
        self.SetupScrolling(scroll_x=True, scroll_y=False)
        width, height = const.ICON_SIZE
        self.SetMinSize((width + 10, height + 10))
        self.SetBackgroundColour((255, 255, 255))

    def append_color(self, color):
        color_hsv = editor.convert_rgb2hsv_full(color)
        if color_hsv not in set(self.colors_target):
            self.colors_target.append(color_hsv)
            self.add_icon(color)

    def add_icon(self, color):
        im = Image.new("RGBA", const.ICON_SIZE, color)
        right, bottom = im.size
        ImageDraw.Draw(im).rectangle((0, 0, right - 1, bottom - 1), outline=(0, 0, 0), width=1)
        bmp = wx.Bitmap.FromBufferRGBA(*im.size, im.tobytes())
        icon = widgets.BitmapPanel(self, bmp=bmp)
        icon.sbmp.Bind(wx.EVT_LEFT_DOWN, self.on_remove)
        self.sizer.Add(icon, 0, wx.ALL, 5)
        self.lst_icon.append(icon.sbmp)
        self.Layout()
        self.SetupScrolling(scroll_y=False)

    def on_remove(self, event):
        icon = event.GetEventObject()
        ix = self.lst_icon.index(icon)
        self.lst_icon.remove(icon)
        self.colors_target.pop(ix)
        icon.GetParent().Destroy()
        self.Layout()
        self.SetupScrolling(scroll_y=False)


class SelectColorDialog(wx.Dialog):
    def __init__(self, parent, path_image, frames):
        style = wx.DEFAULT_DIALOG_STYLE | wx.OK | wx.CANCEL
        super().__init__(parent, -1, "透過色指定ダイアログ", style=style)
        self.parent = parent

        self.im_target = (editor.open_image(path_image).convert("RGBA") if not frames else
                          frames[0].convert("RGBA"))

        if self.im_target.width < const.DEFAULT_WIDTH or self.im_target.height < const.DEFAULT_HEIGHT:
            width = const.DEFAULT_WIDTH if self.im_target.width < const.DEFAULT_WIDTH else self.im_target.width
            height = const.DEFAULT_HEIGHT if self.im_target.height < const.DEFAULT_HEIGHT else self.im_target.height
            size = (width, height)
            im_campus = Image.new("RGBA", size, (0, 0, 0, 0))
            offset = np.array(size) // 2 - np.array(self.im_target.size) // 2
            im_campus.paste(self.im_target, tuple(offset))
            self.im_target = im_campus

        self.chess_board = editor.create_chess_board(self.im_target.size,True)
        campus_edit = Image.alpha_composite(self.chess_board.convert("RGBA"), self.im_target)
        self.bmp_edit = wx.Bitmap.FromBufferRGBA(*campus_edit.size, campus_edit.tobytes())

        self.panel = ScrolledPanel(self)
        caption = ("色を利用して輪郭の内側を透過します。\n"
                   "画像をクリックして色を選択、選択解除は一覧のアイコンをクリック")
        self.st_caption = wx.StaticText(self.panel, -1, caption)
        self.panel_urara = widgets.BitmapPanel(self.panel)
        self.panel_digital = widgets.BitmapPanel(self.panel)
        self.panel_viewer = widgets.BitmapPanel(self.panel, bmp=self.bmp_edit)
        self.panel_selection = SelectionColorPanel(self.panel)
        self.check_face = wx.CheckBox(self.panel, -1, "顔だけ透過")
        self.btn_ok = wx.Button(self.panel, wx.ID_OK, "OK")
        self.btn_cancel = wx.Button(self.panel, wx.ID_CANCEL, "Cancel")
        self.sizer = wx.BoxSizer(wx.VERTICAL)
        self.setting_widgets()
        self.set_position()

    def setting_widgets(self):
        self.panel.SetupScrolling()
        self.panel_viewer.sbmp.Bind(wx.EVT_LEFT_DOWN, self.on_click)
        self.btn_ok.Disable()

        sizer_header = wx.BoxSizer()
        sizer_header.Add(self.panel_urara)
        sizer_header.Add(self.panel_digital)

        sizer_bottom = wx.BoxSizer()
        sizer_btn = wx.BoxSizer(wx.VERTICAL)

        sizer_btn.Add(self.check_face, 0, wx.ALL, 5)
        sizer_btn.Add(self.btn_ok, 1, wx.GROW | wx.ALL, 5)
        sizer_btn.Add(self.btn_cancel, 1, wx.GROW | wx.ALL, 5)

        sizer_bottom.Add(wx.StaticText(self.panel, -1, "選択色一覧"), 0, wx.ALIGN_CENTER_VERTICAL)
        sizer_bottom.Add(self.panel_selection, 1, wx.GROW)
        sizer_bottom.Add(sizer_btn, 0, wx.GROW)

        self.sizer.Add(self.st_caption, 0, wx.ALL, 10)
        self.sizer.Add(sizer_header, 0, wx.ALL, 10)
        self.sizer.Add(self.panel_viewer, 0, wx.ALIGN_CENTER_HORIZONTAL | wx.LEFT | wx.RIGHT, 10)
        self.sizer.Add(sizer_bottom, 0, wx.GROW | wx.ALL, 10)
        self.panel.SetSizer(self.sizer)
        self.sizer.Fit(self)

    def set_position(self):
        left, top = self.parent.GetTopLevelParent().GetPosition()
        width, height = self.parent.GetTopLevelParent().GetSize()
        right = left + width

        width_dial, height_dial = self.GetSize()
        self.SetPosition((np.clip(right - width_dial, 0, const.WIDTH_WORKING - width_dial),
                          np.clip(top, 0, const.HEIGHT_WORKING - height_dial)))

    def on_click(self, event):
        x, y = event.GetPosition()
        width, height = self.im_target.size
        if not (0 <= x < width and 0 <= y < height):
            return

        pixel = self.im_target.getpixel((x, y))
        color, alpha = pixel[:-1], pixel[-1]
        if not alpha:
            return

        self.panel_selection.append_color(color)
        self.on_layout(None)
        self.btn_ok.Enable()

    def on_layout(self, event):
        self.sizer.Layout()
        self.panel.FitInside()

    def get_colors_target(self):
        colors_target = self.panel_selection.colors_target
        face_only = self.check_face.GetValue()
        return colors_target, face_only

class ClipperSelectDialog(wx.Dialog):
    def __init__(self, parent, id_image):
        super().__init__(parent, -1, "クリッパー設定ダイアログ")
        self.panel = wx.Panel(self)
        self.id_image = id_image
        image_target = CONFIG.manager.get_image(id_image)
        bmp = image_target.get_bmp_icon()
        self.st_label = wx.StaticText(self.panel, -1, image_target.label)
        self.icon_target = widgets.BitmapPanel(self.panel, bmp)

        self.is_file = CONFIG.manager.is_file(id_image)
        self.lst_image = (CONFIG.manager.get_order_file_display() if self.is_file else
                          CONFIG.manager.get_order_parts_display(id_image))
        self.lst_image.remove(image_target)
        self.lst_unclipper = []
        self.lst_clipper = []
        self.imagelist, self.order_il = self.create_imagelist()

        self.lc_unclipper = wx.ListCtrl(self.panel, -1, style=wx.LC_SMALL_ICON)
        self.lc_clipper = wx.ListCtrl(self.panel, -1, style=wx.LC_SMALL_ICON)

        self.btn_ok = wx.Button(self.panel, wx.ID_OK, "OK")

        self.sizer = wx.BoxSizer(wx.VERTICAL)
        self.setting_widgets()
        self.SetSize((800, 700))
        self.set_position()
        self.update_display()

    def setting_widgets(self):
        color_bg = const.COLOR_FILE if self.is_file else const.COLOR_PARTS
        self.panel.SetBackgroundColour(color_bg)

        self.lc_unclipper.SetImageList(self.imagelist, wx.IMAGE_LIST_SMALL)
        self.lc_clipper.SetImageList(self.imagelist, wx.IMAGE_LIST_SMALL)

        self.lc_unclipper.Bind(wx.EVT_LEFT_DOWN, self.on_click)
        self.lc_unclipper.Bind(wx.EVT_LEFT_DCLICK, self.on_click)
        self.lc_clipper.Bind(wx.EVT_LEFT_DOWN, self.on_click)
        self.lc_clipper.Bind(wx.EVT_LEFT_DCLICK, self.on_click)

        sizer_top = wx.BoxSizer()
        sizer_top.Add(self.icon_target, 0, wx.ALL, 10)
        sizer_top.Add(self.st_label, 0, wx.ALIGN_CENTER_VERTICAL)

        sizer_mid = wx.BoxSizer()
        sizer_unclipper = wx.BoxSizer(wx.VERTICAL)
        sizer_clipper = wx.BoxSizer(wx.VERTICAL)

        sizer_unclipper.Add(wx.StaticText(self.panel, -1, "画像一覧", style=wx.ALIGN_CENTER), 0,
                            wx.GROW)
        sizer_unclipper.Add(self.lc_unclipper, 1, wx.GROW)

        sizer_clipper.Add(wx.StaticText(self.panel, -1, "クリッパー", style=wx.ALIGN_CENTER), 0, wx.GROW)
        sizer_clipper.Add(self.lc_clipper, 1, wx.GROW)

        sizer_mid.Add(sizer_unclipper, 1, wx.GROW)
        sizer_mid.Add(wx.StaticText(self.panel, -1, "⇔"), 0, wx.ALIGN_CENTER_VERTICAL)
        sizer_mid.Add(sizer_clipper, 1, wx.GROW)

        sizer_btn = wx.BoxSizer(wx.VERTICAL)
        sizer_btn.Add(self.btn_ok, 0, wx.ALIGN_RIGHT)

        self.sizer.Add(sizer_top, 0, wx.ALL, 10)
        self.sizer.Add(sizer_mid, 1, wx.GROW | wx.ALL, 10)
        self.sizer.Add(sizer_btn, 0, wx.GROW | wx.ALL, 10)
        self.panel.SetSizer(self.sizer)
        self.sizer.Fit(self)

    def set_position(self):
        left, top = self.GetParent().Position
        width, height = self.GetParent().Size
        right = left + width

        width_dial, height_dial = self.GetSize()
        self.SetPosition((np.clip(right - width_dial, 0, const.WIDTH_WORKING - width_dial),
                          np.clip(top, 0, const.HEIGHT_WORKING - height_dial)))

    def update_display(self):
        self.lc_unclipper.ClearAll()
        self.lc_clipper.ClearAll()

        self.lst_clipper = CONFIG.manager.get_image(self.id_image).clippers_id.copy()
        lst_id = [image.id_file if self.is_file else image.id_parts for image in self.lst_image]
        self.lst_unclipper = sorted(set(lst_id) - set(self.lst_clipper), key=lst_id.index)

        self.lst_clipper = [CONFIG.manager.get_image(id_clipper) for id_clipper in self.lst_clipper]
        self.lst_unclipper = [CONFIG.manager.get_image(id_image) for id_image in self.lst_unclipper]

        for ix, image in enumerate(self.lst_unclipper):
            label = image.label + "　" * (15 - len(image.label))
            item = self.lc_unclipper.InsertItem(ix, label, self.order_il.index(image.id_file))

        for ix, clipper in enumerate(self.lst_clipper):
            label = clipper.label + "　" * (15 - len(clipper.label))
            item = self.lc_clipper.InsertItem(ix, label, self.order_il.index(clipper.id_file))

    def create_imagelist(self):
        imagelist = wx.ImageList(*const.ICON_SIZE)
        order_il = []
        for image in self.lst_image:
            imagelist.Add(image.get_bmp_icon())
            order_il.append(image.id_file)

        return imagelist, order_il

    def on_click(self, event):
        lc = event.GetEventObject()
        ix_selected, flag = lc.HitTest(event.GetPosition())
        if ix_selected < 0:
            event.Skip()
            return

        if lc == self.lc_unclipper:
            clipper = self.lst_unclipper[ix_selected]
            id_clipper = clipper.id_file if self.is_file else clipper.id_parts
            CONFIG.manager.add_clipper(self.id_image, id_clipper)

        else:
            clipper = self.lst_clipper[ix_selected]
            id_clipper = clipper.id_file if self.is_file else clipper.id_parts
            CONFIG.manager.remove_clipper(self.id_image, id_clipper)

        wxlib.post_update(self.GetParent(), preview=True)
        self.update_display()


class AnimationConverterDialog(wx.Dialog):
    def __init__(self, parent):
        super().__init__(parent, -1, "アニメーションコンバータ")
        self.parent = parent
        self.panel = wx.Panel(self)
        self.note = wx.Notebook(self.panel)
        self.panel_connect = wx.Panel(self.note)
        self.panel_separate = wx.Panel(self.note)

        self.note.InsertPage(0, self.panel_connect, "結合")
        self.note.InsertPage(1, self.panel_separate, "分解")

        cap_connect = "選択したフォルダ内のPNGを名前順に結合してアニメーション画像を作成します。"
        self.st_connect = wx.StaticText(self.panel_connect, -1, cap_connect)
        self.spin_duration = wx.SpinCtrl(self.panel_connect, -1, min=20, max=1000)
        self.combo_connect = wx.ComboBox(self.panel_connect, -1,
                                         style=wx.CB_DROPDOWN | wx.CB_READONLY)
        self.btn_connect = wx.Button(self.panel_connect, -1, "フォルダ選択")

        cap_separate = "選択したアニメーション画像をフレーム毎に分解します。\n加えて画像の輪郭毎に分割することもできます。"
        self.st_separate = wx.StaticText(self.panel_separate, -1, cap_separate)
        self.check_parts = wx.CheckBox(self.panel_separate, -1, "輪郭毎に分割")
        self.check_trim = wx.CheckBox(self.panel_separate, -1, "余白をトリミング")
        self.text_omit = wx.StaticText(self.panel_separate, -1, "最低検出サイズ")
        self.spin_omit = wx.SpinCtrl(self.panel_separate, -1, min=0, max=1000)
        self.btn_separate = wx.Button(self.panel_separate, -1, "画像選択")

        self.sizer = wx.BoxSizer(wx.VERTICAL)
        self.setting_widgets()

    def setting_widgets(self):
        self.combo_connect.Append([const.SaveMode.GIF, const.SaveMode.PNG_ANIME])
        self.combo_connect.SetValue(const.SaveMode.GIF)
        self.spin_duration.SetValue(100)
        self.btn_connect.Bind(wx.EVT_BUTTON, self.on_connect)

        self.spin_omit.SetValue(10)

        self.check_trim.Disable()
        self.text_omit.Disable()
        self.spin_omit.Disable()
        self.check_parts.Bind(wx.EVT_CHECKBOX, self.on_check)
        self.btn_separate.Bind(wx.EVT_BUTTON, self.on_separate)

        sizer_connect = wx.BoxSizer(wx.VERTICAL)
        sizer_duration = wx.BoxSizer()
        sizer_duration.Add(wx.StaticText(self.panel_connect, -1, "表示間隔(ms)"), 0,
                           wx.ALIGN_CENTER_VERTICAL)
        sizer_duration.Add(self.spin_duration)

        sizer_btn = wx.BoxSizer()
        sizer_btn.Add(self.combo_connect)
        sizer_btn.Add(self.btn_connect)

        sizer_connect.Add(self.st_connect, 1, wx.ALL, 10)
        sizer_connect.Add(sizer_duration, 0, wx.ALL, 5)
        sizer_connect.Add(sizer_btn, 0, wx.ALL, 5)
        self.panel_connect.SetSizer(sizer_connect)

        sizer_separate = wx.BoxSizer(wx.VERTICAL)

        sizer_check = wx.BoxSizer()
        sizer_check.Add(self.check_parts, 0, wx.ALIGN_CENTER_VERTICAL)
        sizer_check.Add(self.check_trim, 0, wx.ALIGN_CENTER_VERTICAL)
        sizer_check.Add(self.text_omit, 0, wx.ALIGN_CENTER_VERTICAL)
        sizer_check.Add(self.spin_omit, 0)

        sizer_separate.Add(self.st_separate, 1, wx.ALL, 10)
        sizer_separate.Add(sizer_check, 0, wx.ALL, 5)
        sizer_separate.Add(self.btn_separate, 0, wx.ALL, 5)

        self.panel_separate.SetSizer(sizer_separate)

        self.sizer.Add(self.note, 1, wx.GROW)
        self.panel.SetSizer(self.sizer)
        self.sizer.Fit(self)
        self.Centre()

    def on_connect(self, event):
        message = "結合したい画像が入ったフォルダを選択"
        folder_target = wxlib.select_folder(self, message)
        if not folder_target:
            return

        lst_path = [path_png for path_png in folder_target.glob("*.png")]
        if not lst_path:
            wxlib.show_message(self, "フォルダ内に画像が見つかりません！", "画像未発見エラー", wx.ICON_EXCLAMATION)
            return

        lst_path = os_sorted(lst_path)
        frames = []
        for path_png in lst_path:
            frame = editor.open_image(path_png)
            if not frame:
                message = f"{path_png.name}が開けません！"
                caption = "ファイルアクセスエラー"
                wxlib.show_message(self, message, caption, wx.ICON_ERROR)
                return

            frames.append(frame.convert("RGBA"))

        mode_save = self.combo_connect.GetValue()
        suffix = ".gif" if mode_save == const.SaveMode.GIF else ".png"
        name_file = f"{folder_target.stem}{suffix}"
        wildcard = f"*{suffix}"
        message = "画像の保存先"
        path_save = wxlib.save_file(self, message, wildcard, name_file)
        if not path_save:
            return

        duration = self.spin_duration.GetValue()
        wxlib.post_start_progress(self.parent, "しばらくお待ちください…", "アニメーション画像作成中")
        thread_connect = threading.Thread(target=self.connect_animation,
                                          args=(frames, path_save, duration))
        thread_connect.start()

    def connect_animation(self, frames, path_save, duration):
        with wxlib.progress_context(self.parent, "アニメーション画像の作成に失敗しました…", "作成失敗"):
            if path_save.suffix == ".gif":
                editor.save_gif(path_save, frames, duration)
            else:
                editor.save_apng(path_save, frames, duration)

            caption = "作成完了" if frames else "フォルダ内画像なし"
            message = "アニメーション画像の作成が完了しました！" if frames else "フォルダ内に画像がありません！"
            style = wx.ICON_INFORMATION if frames else wx.ICON_EXCLAMATION
            wxlib.post_end_progress(self.parent, message, caption, style,
                                    path_open=path_save.parent)

    def on_check(self, event):
        enable = self.check_parts.GetValue()
        self.check_trim.Enable(enable)
        self.text_omit.Enable(enable)
        self.spin_omit.Enable(enable)

    def on_separate(self, event):
        message = "分解したい画像を選択"
        wildcard = ";".join([f"*{suffix}" for suffix in [".gif", ".png"]])
        path_image = wxlib.select_file(self, message, wildcard)
        if not path_image:
            return

        frames = editor.get_frames(path_image)
        if not frames:
            message = f"{path_image.name}が開けません！"
            caption = "ファイルアクセスエラー"
            wxlib.show_message(self, message, caption, wx.ICON_ERROR)
            return

        folder_save = wxlib.save_file(self, "分割画像保存", "保存先フォルダ|", path_image.stem)

        sep_parts = self.check_parts.GetValue()
        trim = self.check_trim.GetValue()
        area_omit = self.spin_omit.GetValue()
        wxlib.post_start_progress(self.parent, "しばらくお待ちください…", "画像分割中")
        thread_separate = threading.Thread(target=self.separate_animation,
                                           args=(folder_save, frames, sep_parts, trim, area_omit))
        thread_separate.start()

    def separate_animation(self, folder_save, frames, sep_parts, trim, are_omit):
        with wxlib.progress_context(self.parent, "画像の分割に失敗しました…", "分割失敗"):
            if sep_parts:
                editor.save_png_sequence_contour(folder_save, frames, trim, are_omit)
            else:
                editor.save_png_sequence(folder_save, frames)

            message = "画像の分割が完了しました！"
            caption = "分割完了"
            wxlib.post_end_progress(self.parent, message, caption, path_open=folder_save)
