import wx
from wx.adv import AnimationCtrl
from wx.grid import Grid, GridCellNumberEditor
from wx.lib.agw.floatspin import FloatSpin, EVT_FLOATSPIN
from wx.lib.scrolledpanel import ScrolledPanel
from wx.lib.agw.customtreectrl import (CustomTreeCtrl, TREE_ITEMTYPE_CHECK,
                                       TR_HAS_VARIABLE_ROW_HEIGHT,
                                       TR_DEFAULT_STYLE, TR_ELLIPSIZE_LONG_ITEMS,
                                       TR_TOOLTIP_ON_LONG_ITEMS,
                                       EVT_TREE_ITEM_CHECKED)
from wx.lib.statbmp import GenStaticBitmap

import numpy as np
import threading

import const
from config import CONFIG
import editor
import menus
import wxlib


# アイコン表示
class BitmapPanel(wx.Panel):
    def __init__(self, parent, bmp=None, path_file=None):
        super().__init__(parent)
        self.bmp = bmp if bmp else wx.Bitmap(1, 1)
        self.sbmp = GenStaticBitmap(self, -1, self.bmp)

        self.sbmp.SetBackgroundStyle(wx.BG_STYLE_CUSTOM)
        self.sbmp.Bind(wx.EVT_PAINT, self.on_paint)

        self.sizer = wx.BoxSizer()
        self.sizer.Add(self.sbmp)
        self.SetSizer(self.sizer)
        self.SetDoubleBuffered(True)

        if bmp:
            self.set_bmp(bmp)
        elif path_file:
            self.load_file(path_file)

    def set_bmp(self, bmp):
        self.bmp = bmp
        self.sbmp.SetBitmap(bmp)
        self.SetMinSize(self.sbmp.GetSize())

    def load_file(self, path_file):
        im = editor.open_image(path_file).convert("RGBA")
        bmp = wx.Bitmap.FromBufferRGBA(*im.size, im.tobytes())
        self.set_bmp(bmp)

    def on_paint(self, event):
        if self.bmp and self.sbmp:
            dc = wx.BufferedPaintDC(self.sbmp)
            dc.Clear()
            dc.DrawBitmap(self.bmp, 0, 0)


# フォーカスの有無＝キー受付の可否
class FocusDisplayPanel(BitmapPanel):
    def __init__(self, parent):
        super().__init__(parent)
        im_focus_on = editor.open_image(const.PATH_FOCUS_ON).convert("RGBA")
        im_focus_off = editor.open_image(const.PATH_FOCUS_OFF).convert("RGBA")
        self.bmp_focus_on = wx.Bitmap.FromBufferRGBA(*im_focus_on.size, im_focus_on.tobytes())
        self.bmp_focus_off = wx.Bitmap.FromBufferRGBA(*im_focus_off.size, im_focus_off.tobytes())
        self.sbmp.SetToolTip("キー受付")
        self.set_bmp(self.bmp_focus_off)
        self.sbmp.Bind(wx.EVT_LEFT_DOWN, self.on_click)

    def on_click(self, event):
        self.GetParent().GetParent().sbmp_preview.SetFocus()

    def set_focus(self, is_focused):
        bmp = self.bmp_focus_on if is_focused else self.bmp_focus_off
        self.set_bmp(bmp)


# フレーム番号表示
class FrameNumberDisplayPanel(BitmapPanel):
    def __init__(self, parent):
        super().__init__(parent)
        self.im_display = editor.open_image(const.PATH_DISPLAY_NUM).convert("RGBA")
        self.sbmp.SetToolTip("現在フレーム")
        self.sbmp.Bind(wx.EVT_LEFT_DOWN, self.on_click)
        self.sbmp.Bind(wx.EVT_LEFT_DCLICK, self.on_click)
        self.sbmp.Bind(wx.EVT_RIGHT_DOWN, self.on_click)
        self.sbmp.Bind(wx.EVT_RIGHT_DCLICK, self.on_click)
        self.draw_number()

    def update_display(self):
        self.draw_number()

    def draw_number(self):
        ix_frame = CONFIG.manager.ix_frame + 1
        num_frame = CONFIG.manager.number_frames
        text_display = f"{ix_frame}/{num_frame}"
        size_font = (const.DISPLAY_FONT_DOUBLE_SIZE if num_frame >= 10 else
                     const.DISPLAY_FONT_SINGLE_SIZE)
        im_draw = editor.draw_text(self.im_display, text_display, size_font,
                                   const.PATH_FONT_GENEI, (0, 0, 0), const.DISPLAY_BBOX)
        bmp_draw = wx.Bitmap.FromBufferRGBA(*im_draw.size, im_draw.tobytes())
        self.set_bmp(bmp_draw)

    def on_click(self, event):
        if not (event.LeftIsDown() or event.RightIsDown()):
            return

        ix_delta = 1 if event.RightIsDown() else -1
        CONFIG.manager.shift_ix_frame(ix_delta)
        wxlib.post_update(self.GetTopLevelParent(), True, True, True)


# マーカーのオンオフ表示
class SelectionMarkerStatusPanel(BitmapPanel):
    def __init__(self, parent):
        super().__init__(parent)
        im_mark_on = editor.open_image(const.PATH_MARK_ON).convert("RGBA")
        im_mark_off = editor.open_image(const.PATH_MARK_OFF).convert("RGBA")
        self.bmp_mark_on = wx.Bitmap.FromBufferRGBA(*im_mark_on.size, im_mark_on.tobytes())
        self.bmp_mark_off = wx.Bitmap.FromBufferRGBA(*im_mark_off.size, im_mark_off.tobytes())
        self.sbmp.Bind(wx.EVT_LEFT_DOWN, self.on_left)
        self.sbmp.Bind(wx.EVT_LEFT_DCLICK, self.on_left)
        self.sbmp.SetToolTip("マーカー表示")
        self.set_bmp(self.bmp_mark_off)

    def update_display(self):
        marked = CONFIG.manager.marked_selection
        bmp = self.bmp_mark_on if marked else self.bmp_mark_off
        tooltip = "マーカー非表示" if marked else "マーカー表示"
        self.sbmp.SetToolTip(tooltip)
        self.set_bmp(bmp)

    def on_left(self, event):
        if CONFIG.manager.can_marking():
            CONFIG.manager.switch_marking()
            wxlib.post_update(self.GetTopLevelParent(), preview=True)


# アニメーション再生・停止
class PlayingStatusPanel(wx.Panel):
    def __init__(self, parent):
        super().__init__(parent)
        self.is_playing = False

        self.panel_pause = BitmapPanel(self, path_file=const.PATH_PAUSE)
        self.ctrl_playing = AnimationCtrl(self)
        self.sizer = wx.BoxSizer()
        self.setting_widgets()

    def setting_widgets(self):
        self.panel_pause.sbmp.SetToolTip("再生")
        self.ctrl_playing.SetToolTip("停止")
        self.ctrl_playing.LoadFile(str(const.PATH_PLAYING))
        self.ctrl_playing.Hide()

        self.panel_pause.sbmp.Bind(wx.EVT_LEFT_DOWN, self.on_play)
        self.ctrl_playing.Bind(wx.EVT_LEFT_DOWN, self.on_pause)

        self.sizer.Add(self.panel_pause)
        self.sizer.Add(self.ctrl_playing)
        self.SetSizer(self.sizer)

    def on_play(self, event):
        if not CONFIG.manager.can_save():
            message = "画像が表示されていません！"
            caption = "画像未表示"
            style = wx.ICON_EXCLAMATION
            wxlib.post_info(self.GetTopLevelParent(), message=message, caption=caption, style=style)
            return

        wxlib.post_play(self.GetTopLevelParent())

    def on_pause(self, event):
        wxlib.post_update(self.GetTopLevelParent(), preview=True)

    def play(self):
        self.panel_pause.Hide()
        self.ctrl_playing.Show()
        self.ctrl_playing.Play()

    def pause(self):
        self.ctrl_playing.Hide()
        self.panel_pause.Show()
        self.ctrl_playing.Stop()


# ヘッダ
class HeaderPanel(wx.Panel):
    def __init__(self, parent):
        super().__init__(parent)
        self.panel_focus = FocusDisplayPanel(self)
        self.panel_display_num = FrameNumberDisplayPanel(self)
        self.panel_marker = SelectionMarkerStatusPanel(self)
        self.panel_playing = PlayingStatusPanel(self)
        self.setting_widgets()

    def setting_widgets(self):
        sizer = wx.BoxSizer()
        sizer.Add(self.panel_focus, 0, wx.LEFT | wx.RIGHT, 5)
        sizer.Add(self.panel_display_num, 0, wx.LEFT | wx.RIGHT, 5)
        sizer.Add(self.panel_marker, 0, wx.LEFT | wx.RIGHT, 5)
        sizer.Add(self.panel_playing, 0, wx.LEFT | wx.RIGHT, 5)
        self.SetSizer(sizer)

    def update_display(self):
        self.panel_display_num.update_display()
        self.panel_marker.update_display()
        self.panel_playing.pause()

    def play(self):
        self.panel_playing.play()

    def set_focus(self, is_focused):
        self.panel_focus.set_focus(is_focused)


# プレビュー表示
class PreviewPanel(wx.Panel):
    DELAY_UPDATE = 10
    DIC_DIRECTION = {wx.WXK_UP: np.array((0, -1)), ord("W"): np.array((0, -1)),
                     wx.WXK_DOWN: np.array((0, 1)), ord("S"): np.array((0, 1)),
                     wx.WXK_LEFT: np.array((-1, 0)), ord("A"): np.array((-1, 0)),
                     wx.WXK_RIGHT: np.array((1, 0)), ord("D"): np.array((1, 0))}

    def __init__(self, parent):
        super().__init__(parent)
        self.panel_header = HeaderPanel(self)
        self.panel_preview = wx.Panel(self, -1, style=wx.FULL_REPAINT_ON_RESIZE)
        self.parent = parent
        self.sizer = wx.BoxSizer(wx.VERTICAL)
        self.bmp_preview = wx.Bitmap()
        self.sbmp_preview = GenStaticBitmap(self.panel_preview, -1, self.bmp_preview)
        self.anime_preview = AnimationCtrl(self.panel_preview, -1)
        self.setting_widgets()

        self.pos_start = (0, 0)
        self.is_dragging = False
        self.thread_loading = None
        self.delay_update = wx.CallLater(self.DELAY_UPDATE, self.start_loading)
        self.is_loading = False

    def setting_widgets(self):
        self.panel_preview.SetMinSize(const.DEFAULT_SIZE)

        self.sbmp_preview.SetBackgroundStyle(wx.BG_STYLE_CUSTOM)
        self.sbmp_preview.Bind(wx.EVT_PAINT, self.on_paint)
        self.sbmp_preview.Bind(wx.EVT_LEFT_DOWN, self.on_left)
        self.sbmp_preview.Bind(wx.EVT_LEFT_DCLICK, self.on_left)
        self.sbmp_preview.Bind(wx.EVT_RIGHT_DOWN, self.on_right)
        self.sbmp_preview.Bind(wx.EVT_MOTION, self.on_motion)
        self.sbmp_preview.Bind(wx.EVT_LEFT_UP, self.on_up)
        self.sbmp_preview.Bind(wx.EVT_ENTER_WINDOW, self.on_enter)
        self.sbmp_preview.Bind(wx.EVT_SET_FOCUS, self.on_focus)
        self.sbmp_preview.Bind(wx.EVT_KILL_FOCUS, self.on_focus)
        self.sbmp_preview.Bind(wx.EVT_CHAR_HOOK, self.on_press)
        self.sbmp_preview.Bind(wx.EVT_MOUSEWHEEL, self.on_wheel)

        sizer_view = wx.BoxSizer()
        sizer_view.Add(self.anime_preview, 1, wx.GROW)
        self.panel_preview.SetSizer(sizer_view)
        self.sizer.Add(self.panel_header, 0, wx.ALIGN_CENTER)
        self.sizer.Add(self.panel_preview, 0, wx.ALIGN_CENTER)
        self.SetSizer(self.sizer)

    def update_display(self):
        self.delay_update.Start(self.DELAY_UPDATE)
        self.panel_header.update_display()

    def start_loading(self):
        self.thread_loading = threading.Thread(target=self.load_frame, daemon=True)
        self.thread_loading.start()

    def load_frame(self):
        image_preview = CONFIG.manager.get_preview()
        self.bmp_preview = wx.Bitmap.FromBufferRGBA(*image_preview.size, image_preview.tobytes())
        self.panel_preview.SetMinSize(image_preview.size)
        self.show_frame()

    def show_frame(self):
        self.sbmp_preview.SetBitmap(self.bmp_preview)
        self.sbmp_preview.Show()
        self.anime_preview.Stop()
        wxlib.post_layout(self.GetTopLevelParent())

    def show_animation(self):
        self.anime_preview.LoadFile(str(const.PATH_GIF_PREVIEW))
        self.sbmp_preview.Hide()
        self.anime_preview.Play()
        self.panel_header.play()

    def on_left(self, event):
        pos = np.array(event.GetPosition())
        is_collide = CONFIG.manager.select_by_pos(pos, event.ControlDown())
        if is_collide:
            self.is_dragging = True
            self.pos_start = pos

        wxlib.post_update(self.GetTopLevelParent(), preview=True, prop=True)

    def on_right(self, event):
        pos = np.array(event.GetPosition())
        id_image = CONFIG.manager.get_image_by_pos(pos)
        if id_image:
            CONFIG.manager.select(None, id_image, False)
            wxlib.post_update(self.GetTopLevelParent(), prop=True)
            menu = menus.ComponentMenu(self.GetTopLevelParent(), id_image)
            self.GetTopLevelParent().PopupMenu(menu)

    def on_motion(self, event):
        self.sbmp_preview.SetFocus()
        if not self.is_dragging:
            return

        pos_cur = np.array(event.GetPosition())
        offset = pos_cur - self.pos_start
        self.pos_start = pos_cur
        CONFIG.manager.add_offset(offset)
        wxlib.post_update(self.GetTopLevelParent(), preview=True, prop=True)

    def on_up(self, event):
        self.is_dragging = False

    def on_enter(self, event):
        if self.is_dragging:
            if not event.LeftIsDown():
                self.is_dragging = False
        else:
            self.sbmp_preview.SetFocus()

    def on_press(self, event):
        key = event.GetKeyCode()

        # フレームをシフト
        if key == wx.WXK_TAB:
            ix_delta = -1 if event.ShiftDown() else 1
            CONFIG.manager.shift_ix_frame(ix_delta)
            wxlib.post_update(self.GetTopLevelParent(), True, True, True)
            return

        # マーカーのオンオフ
        elif key == wx.WXK_ESCAPE:
            CONFIG.manager.switch_marking()
            wxlib.post_update(self.GetTopLevelParent(), True, True, True)
            return

        # offsetの移動
        if not CONFIG.manager.is_selected():
            return

        direction = self.DIC_DIRECTION.get(key, None)
        if direction is None:
            return

        direction = direction * 5 if event.ControlDown() else direction
        CONFIG.manager.add_offset(direction)
        wxlib.post_update(self.GetTopLevelParent(), preview=True, prop=True)

    def on_wheel(self, event):
        if not CONFIG.manager.is_selected():
            return

        orientation = event.GetWheelAxis()
        if orientation != wx.MOUSE_WHEEL_VERTICAL:
            return

        rate_angle = 10 if event.ControlDown() else 1
        angle_delta = -1 if 0 > event.GetWheelRotation() else 1
        CONFIG.manager.add_angle(angle_delta * rate_angle)
        wxlib.post_update(self.GetTopLevelParent(), preview=True, prop=True)

    def play_animation(self):
        if self.anime_preview.IsPlaying():
            self.show_frame()
        else:
            self.show_animation()

    def change_frame(self, bmp: wx.Bitmap):
        self.sbmp_preview.SetBitmap(bmp)

    def on_paint(self, event):
        if self.bmp_preview and self.sbmp_preview:
            wx.BufferedPaintDC(self.sbmp_preview, self.bmp_preview)

    def on_focus(self, event):
        is_focused = event.GetEventType() == wx.wxEVT_SET_FOCUS
        self.panel_header.set_focus(is_focused)


# 選択中画像表示
class SelectionViewerPanel(ScrolledPanel):
    def __init__(self, parent):
        super().__init__(parent)
        self.lst_icon = []
        self.lst_id = [None]
        self.text_selected = wx.StaticText(self, -1, "未選択")
        self.sizer = wx.BoxSizer()
        self.sizer_icon = wx.BoxSizer()
        self.create_icon(const.BMP_UNSELECTED)

        self.sizer.Add(self.sizer_icon, 0)
        self.sizer.Add(self.text_selected, 0, wx.LEFT | wx.ALIGN_CENTER_VERTICAL, 10)
        self.SetSizer(self.sizer)

    def update_display(self):
        lst_id_selection = CONFIG.manager.get_selections_id()
        # 選択中画像のラベル表示
        count_selection = len(lst_id_selection)
        if count_selection == 0:
            self.text_selected.Show()
            self.text_selected.SetLabelText("未選択")
            lst_id_selection.append(None)

        elif count_selection == 1:
            label = CONFIG.manager.get_image(lst_id_selection[0]).label
            self.text_selected.Show()
            self.text_selected.SetLabelText(label)
        else:
            self.text_selected.Hide()

        if set(self.lst_id) == set(lst_id_selection):
            return

        # 既にあるアイコンにbitmapを設定
        for icon, id_exist, id_selection in zip(self.lst_icon, self.lst_id, lst_id_selection):
            if id_exist == id_selection:
                continue

            if id_selection is None:
                icon.set_bmp(const.BMP_UNSELECTED)
                continue

            selection = CONFIG.manager.get_image(id_selection)
            icon.set_bmp(selection.get_bmp_icon())

        num_selection = len(lst_id_selection)
        num_exists = len(self.lst_id)
        # アイコンを追加
        if num_selection > num_exists:
            images_selection = CONFIG.manager.get_images_selection()
            for im in images_selection[num_exists:]:
                bmp = im.get_bmp_icon()
                self.create_icon(bmp)

        # アイコンを削除
        elif num_selection < num_exists:
            for panel in self.lst_icon[num_selection:]:
                panel.Destroy()

            self.lst_icon = self.lst_icon[:num_selection]

        self.lst_id = lst_id_selection

        self.Layout()
        self.SetupScrolling(scroll_x=True, scroll_y=False)

    def create_icon(self, bmp):
        panel_bmp = BitmapPanel(self, bmp=bmp)
        self.lst_icon.append(panel_bmp)
        self.sizer_icon.Add(panel_bmp)

    def reset_icon(self):
        for icon in self.lst_icon[1:]:
            icon.Destroy()

        self.lst_icon = self.lst_icon[:1]
        self.lst_icon[0].set_bmp(const.BMP_UNSELECTED)
        self.lst_id = [None]


class PropertyPanel(wx.Panel):
    def __init__(self, parent):
        super().__init__(parent)
        self.target_post = self.GetTopLevelParent()
        self.panel_selection = SelectionViewerPanel(self)
        self.spin_offset_x = wx.SpinCtrl(self, -1, value="0", min=-250, max=250,
                                         style=wx.TE_PROCESS_ENTER | wx.SP_HORIZONTAL)
        self.spin_offset_y = wx.SpinCtrl(self, -1, value="0", min=-250, max=250,
                                         style=wx.TE_PROCESS_ENTER)
        self.spin_angle = wx.SpinCtrl(self, -1, value="0", min=-360, max=360,
                                      style=wx.TE_PROCESS_ENTER)
        self.spin_trans = wx.SpinCtrl(self, -1, value="0", min=0, max=254,
                                      style=wx.TE_PROCESS_ENTER)
        self.spin_zoom_x = wx.SpinCtrlDouble(self, -1, value="1.0", min=0.1, max=3.0,
                                             inc=0.01, style=wx.TE_PROCESS_ENTER | wx.SP_HORIZONTAL)
        self.spin_zoom_y = wx.SpinCtrlDouble(self, -1, value="1.0", min=0.1, max=3.0,
                                             inc=0.01, style=wx.TE_PROCESS_ENTER)

        for child in self.spin_zoom_x.GetChildren():
            if type(child) is wx.TextCtrl:
                self.tc_zoom_x = child

        for child in self.spin_zoom_y.GetChildren():
            if type(child) is wx.TextCtrl:
                self.tc_zoom_y = child

        self.combo_blend = wx.ComboBox(self, -1, style=wx.CB_DROPDOWN | wx.CB_READONLY)
        self.ctrl_color = wx.ColourPickerCtrl(self, -1)
        self.spin_alpha = wx.SpinCtrlDouble(self, -1, value="0.3", min=0.1, max=1.0,
                                            inc=0.01, style=wx.TE_PROCESS_ENTER)

        for child in self.spin_alpha.GetChildren():
            if type(child) is wx.TextCtrl:
                self.tc_alpha = child

        self.check_alias = wx.CheckBox(self, -1, "アンチエイリアス", style=wx.CHK_3STATE)
        self.check_flip = wx.CheckBox(self, -1, "左右反転", style=wx.CHK_3STATE)

        sbox = wx.StaticBox(self, -1, "パーツプロパティ")
        self.sbsizer = wx.StaticBoxSizer(sbox, wx.VERTICAL)
        self.setting_widgets()
        self.Disable()

    def setting_widgets(self):
        self.SetBackgroundColour(const.COLOR_NONE)
        self.spin_offset_x.Bind(wx.EVT_SPINCTRL, self.on_offset)
        self.spin_offset_x.Bind(wx.EVT_TEXT_ENTER, self.on_offset)
        self.spin_offset_y.Bind(wx.EVT_SPINCTRL, self.on_offset)
        self.spin_offset_y.Bind(wx.EVT_TEXT_ENTER, self.on_offset)

        self.spin_angle.Bind(wx.EVT_TEXT_ENTER, self.on_angle)
        self.spin_angle.Bind(wx.EVT_SPINCTRL, self.on_angle)

        self.spin_zoom_x.Bind(wx.EVT_SPINCTRLDOUBLE, self.on_zoom)
        self.spin_zoom_x.Bind(wx.EVT_TEXT_ENTER, self.on_zoom)
        self.spin_zoom_y.Bind(wx.EVT_SPINCTRLDOUBLE, self.on_zoom)
        self.spin_zoom_y.Bind(wx.EVT_TEXT_ENTER, self.on_zoom)

        self.spin_trans.Bind(wx.EVT_SPINCTRL, self.on_trans)
        self.spin_trans.Bind(wx.EVT_TEXT_ENTER, self.on_trans)

        self.combo_blend.Bind(wx.EVT_COMBOBOX, self.on_color)
        self.combo_blend.Bind(wx.EVT_MOUSEWHEEL, lambda e: None)
        self.ctrl_color.Bind(wx.EVT_COLOURPICKER_CURRENT_CHANGED, self.on_color)
        self.spin_alpha.Bind(wx.EVT_SPINCTRLDOUBLE, self.on_color)
        self.spin_alpha.Bind(wx.EVT_TEXT_ENTER, self.on_color)

        self.combo_blend.Append(const.MODES_BLEND)
        self.combo_blend.SetValue(const.BlendMode.NONE)

        self.check_alias.Bind(wx.EVT_CHECKBOX, self.on_alias)
        self.check_flip.Bind(wx.EVT_CHECKBOX, self.on_flip)

        sizer_property = wx.FlexGridSizer(rows=5, cols=4, gap=(0, 10))

        sizer_selected = wx.BoxSizer()
        sizer_selected.Add(wx.StaticText(self, -1, "選択中画像:"), 0,
                           wx.RIGHT | wx.ALIGN_CENTER_VERTICAL, 10)
        sizer_selected.Add(self.panel_selection, 1, wx.GROW)

        sizer_offset_x = wx.BoxSizer()
        sizer_offset_y = wx.BoxSizer()
        sizer_offset_x.Add(wx.StaticText(self, -1, "X:"), 0, wx.ALIGN_CENTER_VERTICAL)
        sizer_offset_x.Add(self.spin_offset_x, 1)
        sizer_offset_y.Add(wx.StaticText(self, -1, "Y:"), 0, wx.ALIGN_CENTER_VERTICAL)
        sizer_offset_y.Add(self.spin_offset_y, 1)

        sizer_zoom_x = wx.BoxSizer()
        sizer_zoom_y = wx.BoxSizer()
        sizer_zoom_x.Add(wx.StaticText(self, -1, "X:"), 0, wx.ALIGN_CENTER_VERTICAL)
        sizer_zoom_x.Add(self.spin_zoom_x, 1)
        sizer_zoom_y.Add(wx.StaticText(self, -1, "Y:"), 0, wx.ALIGN_CENTER_VERTICAL)
        sizer_zoom_y.Add(self.spin_zoom_y, 1)

        sizer_property.Add(wx.StaticText(self, -1, "オフセット"), 0, wx.ALIGN_CENTER_VERTICAL)
        sizer_property.Add(sizer_offset_x, 0, wx.GROW)
        sizer_property.Add(sizer_offset_y, 0, wx.GROW | wx.LEFT, 10)
        sizer_property.Add(self.check_alias, 0, wx.LEFT, 15)
        sizer_property.Add(wx.StaticText(self, -1, "角度"), 0, wx.ALIGN_CENTER_VERTICAL)
        sizer_property.Add(self.spin_angle, 0, wx.GROW)
        sizer_property.Add(wx.StaticText(self, -1, ""), 0)
        sizer_property.Add(self.check_flip, 0, wx.LEFT, 15)
        sizer_property.Add(wx.StaticText(self, -1, "拡大率"), 0, wx.ALIGN_CENTER_VERTICAL)
        sizer_property.Add(sizer_zoom_x, 0, wx.GROW)
        sizer_property.Add(sizer_zoom_y, 0, wx.GROW | wx.LEFT, 10)
        sizer_property.Add(wx.StaticText(self, -1, ""))
        sizer_property.Add(wx.StaticText(self, -1, "透過率"), 0, wx.ALIGN_CENTER_VERTICAL)
        sizer_property.Add(self.spin_trans, 0, wx.GROW)
        sizer_property.Add(wx.StaticText(self, -1, ""))
        sizer_property.Add(wx.StaticText(self, -1, ""))
        sizer_property.Add(wx.StaticText(self, -1, "カラーブレンド"),
                           0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 10)
        sizer_property.Add(self.combo_blend, 0)
        sizer_property.Add(self.ctrl_color, 0)
        sizer_property.Add(self.spin_alpha, 0)
        sizer_property.AddGrowableCol(0)

        self.sbsizer.Add(sizer_selected, 0, wx.GROW | wx.TOP | wx.BOTTOM, 10)
        self.sbsizer.Add(sizer_property, 0, wx.ALL)
        self.SetSizer(self.sbsizer)

        self.spin_alpha.Disable()
        self.spin_alpha.Hide()
        self.ctrl_color.Disable()

    def on_offset(self, event):
        self.panel_selection.SetFocus()
        offset = (self.spin_offset_x.GetValue(), self.spin_offset_y.GetValue())
        CONFIG.manager.set_offset(offset)
        wxlib.post_update(self.GetTopLevelParent(), preview=True)

    def on_angle(self, event):
        self.panel_selection.SetFocus()
        angle = self.spin_angle.GetValue()
        CONFIG.manager.set_angle(angle)
        wxlib.post_update(self.target_post, preview=True)

    def on_zoom(self, event):
        self.panel_selection.SetFocus()
        zoom_x = float(self.tc_zoom_x.GetValue())
        zoom_y = float(self.tc_zoom_y.GetValue())
        CONFIG.manager.set_zoom(zoom_x, zoom_y)
        wxlib.post_update(self.target_post, preview=True)

    def on_trans(self, event):
        self.panel_selection.SetFocus()
        transparency = self.spin_trans.GetValue()
        CONFIG.manager.set_transparency(transparency)
        wxlib.post_update(self.target_post, preview=True)

    def on_alias(self, event):
        anti_alias = self.check_alias.GetValue()
        CONFIG.manager.set_alias(anti_alias)
        wxlib.post_update(self.target_post, preview=True)

    def on_flip(self, event):
        is_flip = self.check_flip.GetValue()
        CONFIG.manager.set_flip(is_flip)
        wxlib.post_update(self.target_post, preview=True)

    def on_color(self, event):
        self.panel_selection.SetFocus()
        if event.GetEventType() == wx.wxEVT_COMBOBOX:
            self.switch_blend_visible()

        if event.GetEventType() == wx.wxEVT_COLOURPICKER_CURRENT_CHANGED:
            color_changed = event.GetColour()[:-1]
            self.ctrl_color.SetColour(color_changed)

        mode_blend = self.combo_blend.GetValue()
        color_blend = self.ctrl_color.GetColour()[:-1]
        alpha_blend = float(self.tc_alpha.GetValue())
        CONFIG.manager.set_blend_color(mode_blend, color_blend, alpha_blend)
        wxlib.post_update(self.target_post, preview=True)
        wxlib.post_layout(self.target_post)

    def update_display(self):
        self.panel_selection.update_display()
        color_bg = const.COLOR_FILE if CONFIG.manager.selected_file else const.COLOR_PARTS
        self.SetBackgroundColour(color_bg)

        selections = CONFIG.manager.get_images_selection()
        if not selections:
            self.disable()
        elif len(selections) == 1:
            self.set_properties_single(selections[0])
        else:
            self.set_properties_multi()

        wxlib.post_layout(self.target_post)

    def reset_icon(self):
        self.panel_selection.reset_icon()

    def set_properties_single(self, selection):
        self.Enable()
        self.Refresh()

        offset_x, offset_y = selection.offset
        width, height = CONFIG.manager.size
        self.spin_offset_x.SetValue(offset_x)
        self.spin_offset_y.SetValue(offset_y)
        self.spin_offset_x.SetMin(-width)
        self.spin_offset_x.SetMax(width)
        self.spin_offset_y.SetMin(-height)
        self.spin_offset_y.SetMax(height)
        self.spin_angle.SetValue(selection.angle)
        self.spin_zoom_x.SetValue(selection.zoom_x)
        self.spin_zoom_y.SetValue(selection.zoom_y)
        self.spin_trans.SetValue(selection.transparency)
        self.check_alias.SetValue(selection.anti_alias)
        self.check_flip.SetValue(selection.is_flip)
        self.combo_blend.SetValue(selection.mode_blend)
        self.ctrl_color.SetColour(selection.color_blend)
        self.spin_alpha.SetValue(selection.alpha_blend)
        self.switch_blend_visible()

    def set_properties_multi(self):
        self.Enable()
        self.Refresh()

    def switch_blend_visible(self):
        enable = self.combo_blend.GetValue() != const.BlendMode.NONE
        self.ctrl_color.Enable(enable)

        enable = self.combo_blend.GetValue() == const.BlendMode.ALPHA
        self.spin_alpha.Enable(enable)
        self.spin_alpha.Show(enable)

    def disable(self):
        self.SetBackgroundColour((200, 200, 200))
        self.Disable()


# 素材一覧を表示
class ThumbnailPanel(ScrolledPanel):
    COLS_COUNT = 5
    ROWS_COUNT = 3
    MARGIN = 5
    WIDTH_SIDEBAR = 20
    THUMB_SIZE = (80, 80)
    ICON_SIZE = (100, 100)
    CAPTION_SIZE = (10, 26)
    ICON_WIDTH, ICON_HEIGHT = ICON_SIZE
    CAPTION_WIDTH, CAPTION_HEIGHT = CAPTION_SIZE
    PANEL_SIZE = ((ICON_WIDTH + MARGIN * 4) * COLS_COUNT + WIDTH_SIDEBAR,
                  (ICON_HEIGHT + CAPTION_HEIGHT + MARGIN * 4) * ROWS_COUNT)

    def __init__(self, parent, path, on_dialog):
        super().__init__(parent, size=self.PANEL_SIZE)
        self.parent = parent
        self.path = path
        self.on_dialog = on_dialog
        self.errors = []
        self.sizer = wx.BoxSizer(wx.VERTICAL)
        self.setting_widgets()
        self.show_button(path)

    def setting_widgets(self):
        self.SetupScrolling(scroll_x=False)
        self.SetDoubleBuffered(True)
        self.SetBackgroundColour((255, 255, 255))

    def show_button(self, path):
        if path.is_dir():
            nd_data = self.get_nd_dir(path)
        else:
            nd_data = self.get_nd_frames(path)

        for row in nd_data:
            sizer_row = wx.BoxSizer()
            for path_image, bmp_btn, frames in row:
                if not path_image:
                    break

                bbtn = wx.BitmapButton(self, -1, bmp_btn)
                bbtn.SetToolTip(path_image.stem)
                text = wx.StaticText(self, -1, path_image.stem,
                                     style=wx.ALIGN_CENTER | wx.ST_ELLIPSIZE_END,
                                     size=self.CAPTION_SIZE)

                bbtn.Bind(wx.EVT_LEFT_DOWN, self.on_click_left(path_image, frames))
                if not path_image.is_dir():
                    bbtn.Bind(wx.EVT_RIGHT_DOWN, self.on_click_right(path_image, frames))

                sizer_item = wx.BoxSizer(wx.VERTICAL)
                sizer_item.Add(bbtn, 0)
                sizer_item.Add(text, 0, wx.GROW)
                sizer_row.Add(sizer_item, 0, wx.ALL, 5)

            self.sizer.Add(sizer_row, 0, wx.GROW)

        self.SetSizer(self.sizer)
        self.sizer.Fit(self)

    def get_nd_dir(self, path_folder):
        lst_path = self.get_lst_path(path_folder)
        lst_dir = []

        lst_path_sep = []
        for path in lst_path:
            if self.is_target_separate(path):
                lst_path_sep.append(path)

            else:
                bmp_btn = self.get_bmp_btn(path)
                if not bmp_btn:
                    continue

                lst_dir.append([path, bmp_btn, None])

        for path in lst_path_sep:
            for im_sep, path_sep in editor.separate_sprite_sheet(path):
                icon = editor.create_icon(im_sep, self.ICON_SIZE, self.THUMB_SIZE,
                                          const.BG_PHOTO)
                bmp_btn = wx.Bitmap.FromBufferRGBA(*icon.size, icon.tobytes())
                frames = [im_sep]
                lst_dir.append([path_sep, bmp_btn, frames])

        lst_dir = lst_dir + [[None, None, None]] * (
                self.COLS_COUNT - (len(lst_dir) % self.COLS_COUNT))
        nd_dir = np.array(lst_dir, dtype=object).reshape([-1, self.COLS_COUNT, 3])
        return nd_dir

    def get_nd_frames(self, path_image):
        frames = editor.get_frames(path_image)
        if not frames:
            message = f"{path_image.name}が開けません！"
            caption = "ファイルアクセスエラー"
            wxlib.post_info(self.GetTopLevelParent(), message, caption, wx.ICON_ERROR)
            return []

        lst_frames = []
        for ix, frame in enumerate(frames):
            path_frame = path_image.parent / f"{path_image.stem}【{ix + 1}】"
            images_frame = [frame.convert("RGBA")]
            icon = editor.create_icon(images_frame[0], self.ICON_SIZE, self.THUMB_SIZE,
                                      const.BG_PHOTO)
            bmp = wx.Bitmap.FromBufferRGBA(*icon.size, icon.tobytes())
            lst_frames.append([path_frame, bmp, images_frame])

        lst_frames = lst_frames + [[None, None, None]] * (
                self.COLS_COUNT - (len(lst_frames) % self.COLS_COUNT))
        nd_frames = np.array(lst_frames, dtype=object).reshape([-1, self.COLS_COUNT, 3])
        return nd_frames

    def get_lst_path(self, path_folder):
        lst_path_folder = []
        lst_path_image = []
        # プリセット
        for path in path_folder.iterdir():
            if path.is_dir():
                lst_path_folder.append(path)
            elif path.suffix in const.SUFFIXES_IMAGE:
                lst_path_image.append(path)

        # あぺんど
        folder_append = self.get_another_folder(path_folder, const.FOLDER_MATERIAL,
                                                const.FOLDER_APPEND)
        if folder_append:
            lst_folder_preset = [path_folder.name for path_folder in lst_path_folder]
            for path in folder_append.iterdir():
                if path.is_dir() and (path.name not in lst_folder_preset):
                    lst_path_folder.append(path)
                elif path.suffix in const.SUFFIXES_IMAGE:
                    lst_path_image.append(path)

        lst_path_folder = sorted(lst_path_folder, key=lambda f: f.name)
        lst_path_image = sorted(lst_path_image, key=lambda f: f.name)
        lst_path = lst_path_folder + lst_path_image

        return lst_path

    def get_bmp_btn(self, path):
        path_icon = self.get_path_icon(path)
        im = editor.open_image(path_icon)
        if not im:
            im = editor.open_image(const.PATH_BUTTON_UNKNOWN)
            if not im:
                return False

        if path.is_dir():
            bg = const.BG_FOLDER
            size_thumb = self.ICON_SIZE
        elif getattr(im, "is_animated", False):
            bg = const.BG_ANIMATION
            size_thumb = self.THUMB_SIZE
        else:
            bg = const.BG_PHOTO
            size_thumb = self.THUMB_SIZE

        icon = editor.create_icon(im, self.ICON_SIZE, size_thumb, bg)
        bmp = wx.Bitmap.FromBufferRGBA(*icon.size, icon.tobytes())

        return bmp

    def get_path_icon(self, path):
        if path.is_dir():
            path_icon = const.FOLDER_APPEND_BUTTON / f"{path.stem}.png"
            if not path_icon.exists():
                path_icon = const.FOLDER_BUTTON / f"{path.stem}.png"
                if not path_icon.exists():
                    path_icon = const.PATH_BUTTON_UNKNOWN
        else:
            path_icon = path

        return path_icon

    def get_another_folder(self, path_folder, path_root, path_another):
        lst_parts = list(path_folder.parts)
        for parts_root in path_root.parts:
            if parts_root in lst_parts:
                lst_parts.remove(parts_root)

        child_another = "/".join(lst_parts)
        folder_another = path_another / child_another
        return folder_another if folder_another.exists() else False

    def is_target_separate(self, path):
        is_collage = path.parent.stem == const.ImageType.COLLAGE
        is_sep = any(map(lambda word: word in path.stem, const.KEYWORDS_SEPARATE))
        return is_collage and is_sep

    def on_click_left(self, path, frames=None):
        def inner(event):
            if path.is_dir():
                wxlib.post_select(self.parent, path)
                return

            wxlib.post_append(self.GetTopLevelParent(), path_image=path, frames=frames)

        return inner

    def on_click_right(self, path, frames):
        def inner(event):
            menu = menus.AppendMenu(self.GetParent(), path, frames, None)
            self.GetParent().PopupMenu(menu)

        return inner


class ImageAppendPanel(wx.Panel):
    ORDER_BTN = [const.ImageType.BASE, const.ImageType.COSTUME, const.ImageType.FACE,
                 const.ImageType.BROWS, const.ImageType.EYES, const.ImageType.MOUTH,
                 const.ImageType.ACCESSORY,
                 const.ImageType.FREE]

    FILES_DISPLAY_LIMIT = 500

    def __init__(self, parent, caption, path_init=None, on_dialog=False):
        super().__init__(parent)
        self.on_dialog = on_dialog
        path_init = path_init if path_init else const.FOLDER_MATERIAL / const.ImageType.BASE
        self.panel_thumb = ThumbnailPanel(self, path_init, on_dialog)
        sbox_append = wx.StaticBox(self, -1, caption)
        self.sbsizer_append = wx.StaticBoxSizer(sbox_append, wx.VERTICAL)
        self.sizer_thumb = wx.BoxSizer(wx.VERTICAL)
        self.setting_widgets()
        self.Bind(const.EVT_SELECT, self.on_select_thumb)

    def setting_widgets(self):
        self.SetDoubleBuffered(True)
        sizer_btn = wx.BoxSizer()
        sizer_import = wx.BoxSizer(wx.VERTICAL)
        for parts in self.ORDER_BTN:
            bmp = wx.Bitmap(str(const.FOLDER_WIDGET / f"{parts}.png"))
            btn = wx.BitmapButton(self, -1, bmp)
            btn.SetToolTip(parts)
            folder_parts = const.FOLDER_MATERIAL / parts
            btn.Bind(wx.EVT_BUTTON, self.on_select_btn(folder_parts))
            sizer_btn.Add(btn, 0, wx.ALL, 5)

        bmp_import = wx.Bitmap(str(const.PATH_BTN_IMPORT))
        btn_import = wx.BitmapButton(self, -1, bmp_import)
        btn_import.SetToolTip("画像取込")
        btn_import.Bind(wx.EVT_BUTTON, self.on_import)
        sizer_import.Add(btn_import, 0, wx.ALIGN_RIGHT)
        sizer_btn.Add(sizer_import, 1, wx.GROW | wx.ALL, 5)

        self.sizer_thumb.Add(self.panel_thumb, 1, wx.GROW)
        self.sbsizer_append.Add(sizer_btn, 0, wx.GROW | wx.ALL, 10)
        self.sbsizer_append.Add(self.sizer_thumb, 1, wx.GROW | wx.ALL, 10)
        self.SetSizer(self.sbsizer_append)

    def on_select_btn(self, path_folder):
        def inner(event):
            self.panel_thumb.Destroy()
            self.panel_thumb = ThumbnailPanel(self, path_folder, self.on_dialog)
            self.sizer_thumb.Add(self.panel_thumb, 1, wx.GROW)
            self.sbsizer_append.Layout()

        return inner

    def on_select_thumb(self, event):
        path = event.path
        if path.is_dir() and self.exceeded_display_limit(path):
            message = "選択したフォルダ直下の画像が多すぎます!\n500件以下になるよう減らしてください!"
            caption = "読込件数オーバー"
            wxlib.post_info(self.GetTopLevelParent(), message, caption, wx.ICON_EXCLAMATION)
            return

        self.panel_thumb.Destroy()
        self.panel_thumb = ThumbnailPanel(self, path, self.on_dialog)
        self.sizer_thumb.Add(self.panel_thumb, 1, wx.GROW)
        self.sbsizer_append.Layout()

    def exceeded_display_limit(self, path_folder):
        counter = 0
        for _ in path_folder.iterdir():
            counter += 1
            if counter > self.FILES_DISPLAY_LIMIT:
                return True

        return False

    def on_import(self, event):
        wildcard = ";".join([f"*{suffix}" for suffix in const.SUFFIXES_IMAGE])
        path_image = wxlib.select_file(None, "取り込みたい画像を選択してください。", wildcard)
        if not path_image:
            return

        wxlib.post_append(self.GetTopLevelParent(), path_image)


# 画像構成表示
class PartsTreeCtrl(CustomTreeCtrl):
    STYLE_TREE = TR_DEFAULT_STYLE | TR_HAS_VARIABLE_ROW_HEIGHT | TR_ELLIPSIZE_LONG_ITEMS | TR_TOOLTIP_ON_LONG_ITEMS

    def __init__(self, parent):
        super().__init__(parent, -1, pos=wx.DefaultPosition, size=wx.DefaultSize,
                         style=self.STYLE_TREE, agwStyle=TR_DEFAULT_STYLE,
                         validator=wx.DefaultValidator,
                         name="CustomTreeCtrl")
        self.target_post = self.GetTopLevelParent()
        self.imagelist = wx.ImageList(*const.ICON_SIZE)
        self.order_il = []
        self.SetImageList(self.imagelist)

        self.item_root = self.AddRoot("詳細構成")
        self.item_from = None
        self.accept_label = False
        self.label_prev = ""

        self.Bind(wx.EVT_TREE_BEGIN_DRAG, self.on_drag)
        self.Bind(wx.EVT_TREE_END_DRAG, self.on_drop)

        self.Bind(wx.EVT_LEFT_DOWN, self.on_left)
        self.Bind(wx.EVT_LEFT_DCLICK, self.on_double)
        self.Bind(wx.EVT_RIGHT_DOWN, self.on_right)
        # 消すメリットが分からないのと取返し効かない操作なのでパーツの削除はひとまず封印
        # self.Bind(wx.EVT_MIDDLE_DOWN, self.on_middle)
        # self.Bind(wx.EVT_MIDDLE_DCLICK, self.on_middle)
        self.Bind(wx.EVT_TREE_END_LABEL_EDIT, self.on_label_end)
        self.Bind(EVT_TREE_ITEM_CHECKED, self.on_check)

        font = wx.Font(8, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL,
                       faceName=const.FACE_FONT_GENEI, encoding=wx.FONTENCODING_DEFAULT)
        self.SetFont(font)
        self.SetBackgroundColour((255, 255, 255))

    def update_display(self):
        item_selection = None
        self.clear()
        order_frame = CONFIG.manager.get_order_frame()
        self.update_imagelist(order_frame)
        ix_selection = CONFIG.manager.ix_frame
        for ix, frame in enumerate(order_frame):
            item_frame = self.AppendItem(self.item_root, f"フレーム【{ix + 1}】", data=ix)
            for parts in frame.get_order_parts_display():
                label = parts.label + "　" * (15 - len(parts.label))
                item_parts = self.AppendItem(item_frame, label, data=parts.id_parts,
                                             ct_type=TREE_ITEMTYPE_CHECK)
                ix_icon = self.order_il.index(parts.id_parts)
                self.SetItemImage(item_parts, ix_icon)
                self.CheckItem2(item_parts, parts.visible)

            if ix_selection == ix:
                self.Expand(item_frame)
                item_selection = item_frame

        self.Expand(self.item_root)
        if item_selection:
            item_last = self.GetLastChild(item_selection)
            if item_last:
                self.SelectItem(item_last, True)

            self.SelectItem(item_selection, True)

    def reset_icon(self):
        self.imagelist.RemoveAll()
        self.order_il = []

    def get_lst_expanded(self):
        lst_expanded = [self.IsExpanded(child) for child in self.get_children(self.item_root)]
        count_frame = CONFIG.manager.get_number_lcm()
        if count_frame > len(lst_expanded):
            lst_expanded.extend([False] * (count_frame - len(lst_expanded)))
        else:
            lst_expanded = lst_expanded[:count_frame]

        return lst_expanded

    def update_imagelist(self, order_frame):
        lst_id_exists = [parts.id_parts for frame in order_frame for parts in frame]
        lst_id_remove = list(set(self.order_il) - set(lst_id_exists))
        for id_remove in lst_id_remove:
            self.imagelist.Remove(self.order_il.index(id_remove))
            self.order_il.remove(id_remove)

        for frame in order_frame:
            for parts in frame:
                if parts.id_parts not in self.order_il:
                    self.order_il.append(parts.id_parts)
                    self.imagelist.Add(parts.get_bmp_icon())

    def clear(self):
        self.DeleteChildren(self.item_root)

    def on_drag(self, event):
        event.Allow()
        self.item_from = event.GetItem()

    def on_drop(self, event):
        event.Allow()
        item_to = event.GetItem()
        if not (item_to and item_to.IsOk()):
            return

        item_parent = self.GetItemParent(self.item_from)
        if item_parent == self.item_root:
            return

        if not (self.item_from != item_to and item_parent == self.GetItemParent(item_to)):
            return

        num_frame = self.GetItemData(item_parent)
        id_from, id_to = self.GetItemData(self.item_from), self.GetItemData(item_to)
        CONFIG.manager.sort_parts(num_frame, id_from, id_to)
        wxlib.post_update(self.target_post, True, True, True)

    def get_children(self, item_parent):
        child, cookie = self.GetFirstChild(item_parent)
        children = []
        while child and child.IsOk():
            children.append(child)
            child, cookie = self.GetNextChild(item_parent, cookie)

        return children

    def on_left(self, event):
        id_item, flag = self.HitTest(event.GetPosition())
        if not flag & wx.TREE_HITTEST_ONITEM:
            event.Skip()
            return

        if id_item == self.GetRootItem():
            event.Skip()
            return

        ix_frame, id_image = None, None
        # frame
        if isinstance(self.GetItemData(id_item), int):
            ix_frame = self.GetItemData(id_item)
            self.Expand(id_item)
            item_last = self.GetLastChild(id_item)
            if item_last:
                self.SelectItem(item_last, True)
                self.SelectItem(id_item, True)
        # parts
        else:
            ix_frame = self.GetItemData(self.GetItemParent(id_item))
            id_image = self.GetItemData(id_item)

        CONFIG.manager.select(ix_frame, id_image, event.ControlDown())
        wxlib.post_update(self.target_post, preview=True, prop=True)

        if id_image:
            event.Skip()

    def on_double(self, event):
        id_item, flag = self.HitTest(event.GetPosition())
        if not flag & wx.TREE_HITTEST_ONITEM:
            event.Skip()
            return

        if id_item == self.GetRootItem():
            event.Skip()
            return

        # frame
        if isinstance(self.GetItemData(id_item), int):
            event.Skip()
            return

        self.label_prev = self.GetItemText(id_item)
        self.accept_label = True
        self.EditLabel(id_item)

    def on_label_end(self, event):
        if event.IsEditCancelled():
            return

        label_edit = event.GetLabel()
        id_item = event.GetItem()
        id_image = self.GetItemData(id_item)
        CONFIG.manager.set_label(id_image, label_edit)

        wxlib.post_update(self.target_post, component=True)

    def on_right(self, event):
        id_item, flag = self.HitTest(event.GetPosition())
        if not flag & wx.TREE_HITTEST_ONITEM:
            event.Skip()
            return

        if id_item == self.GetRootItem():
            event.Skip()
            return

        # frame
        if isinstance(self.GetItemData(id_item), int):
            event.Skip()
            return

        id_image = self.GetItemData(id_item)
        menu = menus.ComponentMenu(self.GetTopLevelParent(), id_image)
        self.GetTopLevelParent().PopupMenu(menu)

    def on_middle(self, event):
        id_item, flag = self.HitTest(event.GetPosition())
        if not flag & wx.TREE_HITTEST_ONITEM:
            return

        if id_item == self.GetRootItem():
            return

        # frame
        if isinstance(self.GetItemData(id_item), int):
            return

        id_image = self.GetItemData(id_item)
        CONFIG.manager.remove(id_image)
        wxlib.post_update(self.target_post, True, True, True)

    def on_check(self, event):
        item_checked = event.GetItem()
        ix_frame = self.GetItemData(self.GetItemParent(item_checked))
        id_parts = self.GetItemData(item_checked)
        visible = self.IsItemChecked(item_checked)
        CONFIG.manager.set_parts_visible(id_parts, visible)
        CONFIG.manager.select(ix_frame, id_parts, False)
        wxlib.post_update(self.target_post, preview=True, prop=True)


class FileListCtrl(wx.ListCtrl):
    def __init__(self, parent):
        super().__init__(parent, -1, style=wx.LC_SMALL_ICON | wx.LC_SINGLE_SEL | wx.LC_EDIT_LABELS)
        self.EnableCheckBoxes(True)
        self.target_post = self.GetTopLevelParent()
        self.lst_data = []
        self.imagelist = wx.ImageList(*const.ICON_SIZE)
        self.order_il = []
        self.SetImageList(self.imagelist, wx.IMAGE_LIST_SMALL)

        # click
        self.Bind(wx.EVT_LEFT_DOWN, self.on_left_down)
        self.Bind(wx.EVT_RIGHT_DOWN, self.on_right_down)
        self.Bind(wx.EVT_MIDDLE_DOWN, self.on_middle_down)
        self.Bind(wx.EVT_MIDDLE_DCLICK, self.on_middle_down)
        self.Bind(wx.EVT_LEFT_DCLICK, self.on_double)
        # sort_by_d&d
        self.Bind(wx.EVT_LIST_BEGIN_DRAG, self.on_drag)
        self.Bind(wx.EVT_LEFT_UP, self.on_drop)
        # switch_visible
        self.Bind(wx.EVT_LIST_ITEM_CHECKED, self.on_check)
        self.Bind(wx.EVT_LIST_ITEM_UNCHECKED, self.on_check)

        # edit_label
        self.Bind(wx.EVT_LIST_BEGIN_LABEL_EDIT, self.on_label_begin)
        self.Bind(wx.EVT_LIST_END_LABEL_EDIT, self.on_label_end)

        self.label_prev = ""
        self.accept_label = False

        self.accept_check = True
        self.dragging = False
        self.ix_from = 0
        self.update_display()
        font = wx.Font(8, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL,
                       faceName=const.FACE_FONT_GENEI, encoding=wx.FONTENCODING_DEFAULT)

        self.SetFont(font)

    # 表示の更新
    def update_display(self):
        order_file = CONFIG.manager.get_order_file_display()
        self.update_imagelist(order_file)
        self.ClearAll()
        self.lst_data = []

        for ix, file in enumerate(order_file):
            label = file.label + "　" * (15 - len(file.label))
            item = self.InsertItem(ix, label, self.order_il.index(file.id_file))
            self.lst_data.append(file.id_file)
            self.accept_check = False
            self.CheckItem(item, file.visible)
            self.accept_check = True

    def update_imagelist(self, order_file):
        lst_id_exists = [file.id_file for file in order_file]
        lst_id_remove = list(set(self.order_il) - set(lst_id_exists))
        for id_remove in lst_id_remove:
            self.imagelist.Remove(self.order_il.index(id_remove))
            self.order_il.remove(id_remove)

        for file in order_file:
            if file.id_file not in self.order_il:
                self.order_il.append(file.id_file)
                self.imagelist.Add(file.get_bmp_icon())

    def reset_icon(self):
        self.lst_data = []
        self.imagelist.RemoveAll()
        self.order_il = []

    # パーツセレクト
    def on_left_down(self, event):
        ix_selected, flag = self.HitTest(event.GetPosition())
        if ix_selected < 0:
            event.Skip()
            return

        ix_frame = None
        id_file = self.lst_data[ix_selected]
        CONFIG.manager.select(ix_frame, id_file, event.ControlDown())
        wxlib.post_update(self.target_post, preview=True, prop=True)
        self.Select(ix_selected)
        event.Skip()

    # メニュー表示
    def on_right_down(self, event):
        ix_selected, flag = self.HitTest(event.GetPosition())
        if ix_selected < 0:
            event.Skip()
            return

        id_replace = self.lst_data[ix_selected]
        menu = menus.ComponentMenu(self.GetTopLevelParent(), id_replace)
        self.GetTopLevelParent().PopupMenu(menu)

    # ファイル削除
    def on_middle_down(self, event):
        ix_selected, flag = self.HitTest(event.GetPosition())
        if ix_selected < 0:
            return

        id_file = self.lst_data[ix_selected]
        CONFIG.manager.remove(id_file)
        wxlib.post_update(self.target_post, True, True, True)

    # ラベル編集
    def on_double(self, event):
        ix_selected, flag = self.HitTest(event.GetPosition())
        if ix_selected < 0:
            return

        self.label_prev = self.GetItemText(ix_selected)
        self.accept_label = True
        self.EditLabel(ix_selected)

    # D&Dソート
    def on_drag(self, event):
        if not self.dragging:
            self.dragging = True
            self.ix_from = event.GetIndex()

        event.Skip()

    def on_drop(self, event):
        if not self.dragging:
            event.Skip()
            return

        self.dragging = False
        ix_to, flag = self.HitTest(event.GetPosition())
        if ix_to < 0:
            return

        id_from, id_to = self.lst_data[self.ix_from], self.lst_data[ix_to]

        CONFIG.manager.sort_file(id_from, id_to)
        wxlib.post_update(self.target_post, True, True, True)

    # 表示非表示の一括切り替え
    def on_check(self, event):
        if not self.accept_check:
            return

        ix_checked = event.GetIndex()
        is_checked = True if event.GetEventType() == wx.wxEVT_LIST_ITEM_CHECKED else False
        id_file = self.lst_data[ix_checked]
        CONFIG.manager.set_file_visible(id_file, is_checked)
        wxlib.post_update(self.target_post, preview=True, component=True)

    # ラベルの編集
    def on_label_begin(self, event):
        if not self.accept_label:
            event.Veto()
            return

        self.accept_label = False
        event.Skip()

    def on_label_end(self, event):
        if event.IsEditCancelled():
            return

        label_edit = event.GetLabel()
        ix = event.GetIndex()
        id_image = self.lst_data[ix]
        CONFIG.manager.set_label(id_image, label_edit)
        wxlib.post_update(self.target_post, prop=True, component=True)

    def get_id_selected(self):
        ix_selected = self.GetFirstSelected()
        if ix_selected == -1:
            return False

        id_file = self.lst_data[ix_selected]
        return id_file


class ComponentPanel(wx.Panel):
    def __init__(self, parent):
        super().__init__(parent)
        self.note = wx.Notebook(self, -1)
        self.panel_file = wx.Panel(self.note)
        self.panel_parts = wx.Panel(self.note)

        self.page_file = 0
        self.page_parts = 1

        self.note.InsertPage(self.page_file, self.panel_file, "画像一覧")
        self.note.InsertPage(self.page_parts, self.panel_parts, "詳細構成")

        self.flc = FileListCtrl(self.panel_file)
        self.tree = PartsTreeCtrl(self.panel_parts)

        sbox = wx.StaticBox(self, -1, "画像構成")
        self.sbsizer = wx.StaticBoxSizer(sbox, wx.VERTICAL)
        self.setting_widgets()

        self.item_from = None
        self.children_sorted = []

    def setting_widgets(self):
        self.note.Bind(wx.EVT_NOTEBOOK_PAGE_CHANGED, self.on_change)

        sizer_file = wx.BoxSizer(wx.VERTICAL)
        sizer_file.Add(self.flc, 1, wx.GROW)
        self.panel_file.SetSizer(sizer_file)

        sizer_parts = wx.BoxSizer()
        sizer_parts.Add(self.tree, 1, wx.GROW)
        self.panel_parts.SetSizer(sizer_parts)

        self.sbsizer.Add(self.note, 1, wx.GROW | wx.ALL, 10)
        self.sbsizer.Add(wx.StaticText(self, -1, "　" * 25))

        self.SetSizer(self.sbsizer)
        self.SetDoubleBuffered(True)

    def update_display(self):
        page_selected = self.page_file if CONFIG.manager.selected_file else self.page_parts
        self.note.ChangeSelection(page_selected)
        self.flc.update_display()
        self.tree.update_display()

    def reset_icon(self):
        self.flc.reset_icon()
        self.tree.reset_icon()

    def on_change(self, event):
        ix = event.GetSelection()
        selected_file = ix == 0
        CONFIG.manager.switch_selected_file(selected_file)
        wxlib.post_update(self.GetTopLevelParent(), preview=True, prop=True)


# 画像全体のプロパティ
class CompositePanel(wx.Panel):
    def __init__(self, parent):
        super().__init__(parent)
        self.target_post = self.GetTopLevelParent()

        self.sbox = wx.StaticBox(self, -1, "全体プロパティ")
        self.sbsizer = wx.StaticBoxSizer(self.sbox, wx.VERTICAL)

        self.check_fixed_frames = wx.CheckBox(self, -1, "フレーム数")
        self.spin_num_frames = wx.SpinCtrl(self, -1, min=1, max=99, style=wx.TE_PROCESS_ENTER)

        self.check_fixed_size = wx.CheckBox(self, -1, "画像サイズ")
        self.spin_width = FloatSpin(self, -1, min_val=const.MIN_WIDTH, max_val=const.MAX_WIDTH,
                                    increment=50, digits=0,
                                    style=wx.TE_PROCESS_ENTER | wx.SP_HORIZONTAL)
        self.spin_height = FloatSpin(self, -1, min_val=const.MIN_HEIGHT, max_val=const.MAX_HEIGHT,
                                     increment=50, digits=0, style=wx.TE_PROCESS_ENTER)

        self.radio_single = wx.RadioButton(self, -1, "シングル", style=wx.RB_GROUP)
        self.radio_multi = wx.RadioButton(self, -1, "マルチ")
        self.spin_duration = wx.SpinCtrl(self, -1, min=20, max=1000,
                                         style=wx.TE_PROCESS_ENTER)

        self.panel_grid = ScrolledPanel(self)
        self.grid_duration = Grid(self.panel_grid, -1)
        self.combo_filter_color = wx.ComboBox(self, -1, style=wx.CB_DROPDOWN | wx.CB_READONLY)
        self.combo_filter_image = wx.ComboBox(self, -1, style=wx.CB_DROPDOWN | wx.CB_READONLY)

        self.btn_clear = wx.Button(self, -1, "ALLクリア")
        self.combo_save = wx.ComboBox(self, -1, style=wx.CB_DROPDOWN | wx.CB_READONLY)
        self.btn_save = wx.Button(self, -1, "保存")

        self.setting_widgets()
        self.update_display()

    def setting_widgets(self):
        self.check_fixed_frames.Bind(wx.EVT_CHECKBOX, self.on_check_frames)
        self.spin_num_frames.SetValue(CONFIG.manager.number_frames)
        self.spin_num_frames.Disable()
        self.spin_num_frames.Bind(wx.EVT_SPINCTRL, self.on_spin_frames)
        self.spin_num_frames.Bind(wx.EVT_TEXT_ENTER, self.on_spin_frames)

        width, height = CONFIG.manager.size
        self.check_fixed_size.Bind(wx.EVT_CHECKBOX, self.on_check_size)
        self.spin_width.SetValue(width)
        self.spin_width.Disable()
        self.spin_width.Bind(EVT_FLOATSPIN, self.on_spin_size)
        self.spin_width.Bind(wx.EVT_TEXT_ENTER, self.on_spin_size)
        self.spin_height.SetValue(height)
        self.spin_height.Disable()
        self.spin_height.Bind(EVT_FLOATSPIN, self.on_spin_size)
        self.spin_height.Bind(wx.EVT_TEXT_ENTER, self.on_spin_size)

        self.radio_single.Bind(wx.EVT_RADIOBUTTON, self.on_single)
        self.radio_multi.Bind(wx.EVT_RADIOBUTTON, self.on_multi)
        self.spin_duration.SetValue(CONFIG.manager.durations_multi[0])
        self.spin_duration.Bind(wx.EVT_SPINCTRL, self.on_duration_single)
        self.spin_duration.Bind(wx.EVT_TEXT_ENTER, self.on_duration_single)
        self.grid_duration.SetDefaultEditor(GridCellNumberEditor(20, 1000))
        self.grid_duration.CreateGrid(1, 1)
        self.grid_duration.EnableDragColSize(False)
        self.grid_duration.EnableDragRowSize(False)
        self.grid_duration.DisableDragGridSize()
        self.grid_duration.DisableDragColMove()
        self.grid_duration.HideRowLabels()

        self.grid_duration.Bind(wx.grid.EVT_GRID_CELL_LEFT_CLICK, self.on_grid)
        self.grid_duration.Bind(wx.grid.EVT_GRID_CELL_LEFT_DCLICK, self.on_grid)
        self.grid_duration.Bind(wx.EVT_CHAR, self.on_grid_key)
        self.grid_duration.Bind(wx.grid.EVT_GRID_CELL_CHANGED, self.on_grid_change)
        self.grid_duration.Bind(wx.grid.EVT_GRID_EDITOR_HIDDEN, self.on_hidden)
        self.grid_duration.Bind(wx.grid.EVT_GRID_SELECT_CELL,
                                lambda e: self.grid_duration.ClearSelection())
        self.grid_duration.Bind(wx.PyEventBinder(10010), lambda e: None)

        self.panel_grid.Hide()

        self.combo_filter_color.Append(const.FILTERS_COLOR)
        self.combo_filter_color.SetValue(const.ColorFilter.NONE)
        self.combo_filter_color.Bind(wx.EVT_COMBOBOX, self.on_filter)
        self.combo_filter_color.Bind(wx.EVT_MOUSEWHEEL, lambda e: None)
        self.combo_filter_image.Append(const.FILTERS_IMAGE)
        self.combo_filter_image.SetValue(const.ColorFilter.NONE)
        self.combo_filter_image.Bind(wx.EVT_COMBOBOX, self.on_filter)
        self.combo_filter_image.Bind(wx.EVT_MOUSEWHEEL, lambda e: None)

        self.btn_clear.Bind(wx.EVT_BUTTON, self.on_clear)

        self.combo_save.Append(const.MODES_SAVE)
        self.combo_save.SetValue(const.SaveMode.GIF)
        self.combo_save.Bind(wx.EVT_MOUSEWHEEL, lambda e: None)
        self.btn_save.Bind(wx.EVT_BUTTON, self.on_save)

        sizer_top = wx.BoxSizer()

        sizer_frame = wx.BoxSizer()
        sizer_frame.Add(self.check_fixed_frames, 0, wx.ALIGN_CENTER_VERTICAL)
        sizer_frame.Add(self.spin_num_frames)

        sizer_size = wx.BoxSizer()
        sizer_size.Add(self.check_fixed_size, 0, wx.ALIGN_CENTER_VERTICAL)
        sizer_size.Add(wx.StaticText(self, -1, "X:"), 0, wx.ALIGN_CENTER_VERTICAL)
        sizer_size.Add(self.spin_width, 0, wx.RIGHT, 10)
        sizer_size.Add(wx.StaticText(self, -1, "Y:"), 0, wx.ALIGN_CENTER_VERTICAL)
        sizer_size.Add(self.spin_height)

        sizer_top.Add(sizer_frame, 0, wx.ALL, 5)
        sizer_top.Add(wx.Panel(self), 0, wx.RIGHT, 20)
        sizer_top.Add(sizer_size, 0, wx.ALL, 5)

        sizer_duration = wx.BoxSizer(wx.VERTICAL)
        sizer_radio = wx.BoxSizer()
        sizer_radio.Add(wx.StaticText(self, -1, "表示間隔(ms)"), 0, wx.RIGHT, 10)
        sizer_radio.Add(self.radio_single, 0)
        sizer_radio.Add(self.radio_multi, 0)

        sizer_grid = wx.BoxSizer()
        sizer_grid.Add(self.grid_duration, 0)
        self.panel_grid.SetSizer(sizer_grid)

        sizer_duration.Add(sizer_radio, 0, wx.ALL, 5)
        sizer_duration.Add(self.spin_duration, 0, wx.ALL, 5)
        sizer_duration.Add(self.panel_grid, 0, wx.GROW | wx.ALL, 5)

        sizer_filter = wx.BoxSizer()
        sizer_filter.Add(wx.StaticText(self, -1, "色フィルタ:"), 0, wx.ALIGN_CENTER)
        sizer_filter.Add(self.combo_filter_color, 0, wx.ALL, 5)
        sizer_filter.Add(wx.StaticText(self, -1, "画像フィルタ:"), 0, wx.ALIGN_CENTER)
        sizer_filter.Add(self.combo_filter_image, 0, wx.ALL, 5)

        sizer_save = wx.BoxSizer()
        sizer_save.Add(self.combo_save)
        sizer_save.Add(self.btn_save)
        sizer_save.Add(wx.Panel(self), 1, wx.GROW)
        sizer_save.Add(self.btn_clear)

        self.sbsizer.Add(sizer_top, 0, wx.GROW | wx.ALL, 5)
        self.sbsizer.Add(sizer_duration, 0, wx.GROW | wx.LEFT | wx.RIGHT, 5)
        self.sbsizer.Add(sizer_filter, 0, wx.ALL, 5)
        self.sbsizer.Add(sizer_save, 0, wx.GROW | wx.ALL, 5)
        self.SetSizer(self.sbsizer)

    def update_display(self):
        self.check_fixed_frames.SetValue(CONFIG.manager.fixed_number_frames)
        self.spin_num_frames.Enable(CONFIG.manager.fixed_number_frames)
        self.spin_num_frames.SetValue(CONFIG.manager.number_frames)

        self.check_fixed_size.SetValue(CONFIG.manager.fixed_size)
        self.spin_width.Enable(CONFIG.manager.fixed_size)
        self.spin_height.Enable(CONFIG.manager.fixed_size)
        width, height = CONFIG.manager.size
        self.spin_width.SetValue(width)
        self.spin_height.SetValue(height)

        self.spin_duration.SetValue(CONFIG.manager.duration_single)
        num_cols = self.grid_duration.GetNumberCols()
        delta_col = CONFIG.manager.number_frames - num_cols
        if delta_col > 0:
            self.grid_duration.AppendCols(delta_col)
        elif delta_col < 0:
            self.grid_duration.DeleteCols(pos=0, numCols=-delta_col)

        for ix, d in enumerate(CONFIG.manager.durations_multi):
            self.grid_duration.SetColLabelValue(ix, f"【F{ix + 1}】     ")
            self.grid_duration.SetCellValue(0, ix, str(d))
            self.grid_duration.SetReadOnly(0, ix, True)

        self.grid_duration.AutoSize()

        self.panel_grid.Layout()
        self.panel_grid.SetupScrolling(scroll_x=True, scroll_y=False)

        need_duration = CONFIG.manager.number_frames != 1
        self.spin_duration.Enable(need_duration)
        self.grid_duration.Enable(need_duration)

        self.combo_filter_color.SetValue(CONFIG.manager.filter_color)
        self.combo_filter_image.SetValue(CONFIG.manager.filter_image)

    def on_check_frames(self, event):
        fixed = self.check_fixed_frames.GetValue()
        CONFIG.manager.fix_num_frames(fixed)
        self.spin_num_frames.SetValue(CONFIG.manager.number_frames)
        self.spin_num_frames.Enable(fixed)
        wxlib.post_update(self.target_post, preview=True, component=True)

    def on_spin_frames(self, event):
        num_frames = self.spin_num_frames.GetValue()
        CONFIG.manager.change_number_frames(num_frames)
        self.sbox.SetFocus()
        wxlib.post_update(self.target_post, preview=True, component=True)

    def on_check_size(self, event):
        fixed = self.check_fixed_size.GetValue()
        CONFIG.manager.fix_size(fixed)
        width, height = CONFIG.manager.size
        self.spin_width.SetValue(width)
        self.spin_height.SetValue(height)
        self.spin_width.Enable(fixed)
        self.spin_height.Enable(fixed)
        wxlib.post_update(self.target_post, preview=True, prop=True)

    def on_spin_size(self, event):
        width, height = int(self.spin_width.GetValue()), int(self.spin_height.GetValue())
        self.spin_width.SetValue(width)
        self.spin_height.SetValue(height)
        size = width, height
        CONFIG.manager.change_size(size)
        self.sbox.SetFocus()
        wxlib.post_update(self.target_post, preview=True, prop=True)

    def on_single(self, event):
        self.spin_duration.Show()
        self.panel_grid.Hide()
        wxlib.post_layout(self.target_post)

    def on_multi(self, event):
        self.spin_duration.Hide()
        self.panel_grid.Show()
        wxlib.post_layout(self.target_post)

    def on_duration_single(self, event):
        duration = self.spin_duration.GetValue()
        self.sbox.SetFocus()
        CONFIG.manager.set_duration_single(duration)

    def on_grid(self, event):
        row, col = event.GetRow(), event.GetCol()
        self.grid_duration.SetGridCursor(row, col)
        self.grid_duration.SetReadOnly(row, col, False)
        if self.grid_duration.CanEnableCellControl():
            self.grid_duration.EnableCellEditControl(True)
            self.grid_duration.FindFocus().Bind(wx.EVT_KILL_FOCUS,
                                                lambda
                                                    e: self.grid_duration.DisableCellEditControl())

    def on_grid_key(self, event):
        key = event.GetKeyCode()
        if key == wx.WXK_NONE or self.grid_duration.IsCellEditControlShown():
            event.Skip()
            return

        char_key = chr(key)
        row, col = self.grid_duration.GetGridCursorRow(), self.grid_duration.GetGridCursorCol()
        self.grid_duration.SetReadOnly(row, col, False)
        if self.grid_duration.CanEnableCellControl():
            self.grid_duration.EnableCellEditControl(True)
            spin_cell = self.grid_duration.FindFocus()
            spin_cell.Bind(wx.EVT_KILL_FOCUS, lambda e: self.grid_duration.DisableCellEditControl())
            if char_key.isdecimal():
                spin_cell.SetValue(char_key)
                spin_cell.SetSelection(1, 1)

    def on_grid_change(self, event):
        durations = [int(self.grid_duration.GetCellValue(0, ix))
                     for ix in range(self.grid_duration.NumberCols)]
        CONFIG.manager.set_duration_multi(durations)

    def on_hidden(self, event):
        row, col = event.GetRow(), event.GetCol()
        self.grid_duration.SetReadOnly(row, col, True)

    def on_filter(self, event):
        filter_color = self.combo_filter_color.GetValue()
        filter_image = self.combo_filter_image.GetValue()
        CONFIG.manager.set_filter(filter_color, filter_image)
        wxlib.post_update(self.target_post, preview=True)

    def on_save(self, event):
        if not CONFIG.manager.can_save():
            wxlib.show_message(self, "画像が表示されていません！", "画像未表示", wx.ICON_EXCLAMATION)
            return

        mode_save = self.combo_save.GetValue()
        if mode_save == const.SaveMode.GIF:
            self.save_gif()
        elif mode_save == const.SaveMode.PNG_SEQUENCE:
            self.save_png_sequence()
        elif mode_save == const.SaveMode.PNG_ANIME:
            self.save_apng()

    def save_gif(self):
        path_save = wxlib.save_file(self, "GIF保存", "GIF|*.gif", "たぬき.gif")
        if not path_save:
            return

        wxlib.post_start_progress(self.target_post, "少しお待ちください…", "保存中")
        thread_gif = threading.Thread(target=self.thread_gif, args=(path_save,))
        thread_gif.start()

    def thread_gif(self, path_save):
        with wxlib.progress_context(self.target_post, "保存に失敗しました…", "保存失敗"):
            is_single = self.radio_single.GetValue()
            CONFIG.manager.save_gif(path_save, is_single)
            self.complete_save(path_save.parent)

    def save_png_sequence(self):
        folder_save = wxlib.save_file(self, "連番PNG保存", "保存先フォルダ|", "連番たぬき")
        if not folder_save:
            return

        wxlib.post_start_progress(self.GetTopLevelParent(), "少しお待ちください…", "保存中")
        thread_sequence = threading.Thread(target=self.thread_sequence, args=(folder_save,))
        thread_sequence.start()

    def thread_sequence(self, folder_save):
        with wxlib.progress_context(self.target_post, "保存に失敗しました…", "保存失敗"):
            CONFIG.manager.save_png_sequence(folder_save)
            self.complete_save(folder_save)

    def save_apng(self):
        path_save = wxlib.save_file(self, "APNG保存", "APNG|*.png", "Aたぬき.png")
        if not path_save:
            return

        wxlib.post_start_progress(self.GetTopLevelParent(), "少しお待ちください…", "保存中")
        thread_apng = threading.Thread(target=self.thread_apng, args=(path_save,))
        thread_apng.start()

    def thread_apng(self, path_save):
        with wxlib.progress_context(self.target_post, "保存に失敗しました…", "保存失敗"):
            is_single = self.radio_single.GetValue()
            CONFIG.manager.save_apng(path_save, is_single)
            self.complete_save(path_save.parent)

    def complete_save(self, path_open):
        message = "保存が完了しました。"
        caption = "保存完了"
        wxlib.post_end_progress(self.target_post, message, caption, path_open=path_open)

    def on_clear(self, event):
        style = wx.OK | wx.CANCEL | wx.ICON_EXCLAMATION
        result = wxlib.show_message(self, "作業状況をすべてクリアしますか？", "ALLクリア", style=style)
        if result != wx.ID_OK:
            return

        CONFIG.manager.clear()
        wxlib.post_update(self.target_post, True, True, True)
