import wx
from wx.lib.scrolledpanel import ScrolledPanel
import pathlib
import win32gui, win32con
import numpy as np
import os
import threading

import const
from config import CONFIG
import widgets
import menus
import wxlib

import ctypes


class DropTarget(wx.FileDropTarget):
    LIMIT_DROP = 10

    def __init__(self, parent):
        super().__init__()
        self.parent = parent

    def OnDragOver(self, x, y, defResult):
        return defResult if self.parent.IsFocusable() else wx.DragError

    def OnDropFiles(self, x, y, filenames):
        if not self.parent.IsFocusable():
            return True

        count_files = len(filenames)
        if count_files > self.LIMIT_DROP:
            message = "一度にドロップできるファイル数は10件までです！"
            caption = "ファイルドロップ数オーバー"
            wxlib.post_info(self.parent, message, caption, style=wx.ICON_EXCLAMATION)
            return True

        for path in filenames:
            path_drop = pathlib.Path(path)
            if path_drop.suffix in const.SUFFIXES_IMAGE:
                wxlib.post_append(self.parent, path_drop)

            else:
                message = f"{path_drop.name}は画像追加の対象外です!\n追加できる画像の拡張子はjpg,png,gifのみです！"
                caption = "対象外ファイル"
                wxlib.post_info(self.parent, message, caption, style=wx.ICON_EXCLAMATION)

        return True


class MainFrame(wx.Frame):
    def __init__(self):
        super().__init__(None, -1, "たぬこら")
        # progress
        self.dial_progress = None
        self.is_progress = False
        self.message = ""
        self.caption = ""
        self.style = wx.ICON_INFORMATION
        self.path_open = None
        self.need_play = False

        icon = wx.Icon(str(const.PATH_ICON))
        self.SetIcon(icon)

        self.panel = ScrolledPanel(self)

        # left
        self.panel_component = widgets.ComponentPanel(self.panel)
        # middle
        self.panel_preview = widgets.PreviewPanel(self.panel)
        self.panel_property = widgets.PropertyPanel(self.panel)
        # right
        self.panel_append = widgets.ImageAppendPanel(self.panel, "画像追加")
        self.panel_composite = widgets.CompositePanel(self.panel)
        self.sizer = wx.BoxSizer()
        self.setting_widgets()

    def setting_widgets(self):
        self.SetIcon(wx.Icon(str(const.PATH_ICON)))
        self.SetMenuBar(menus.MenuBar())
        self.CreateStatusBar()
        self.SetDropTarget(DropTarget(self))
        self.panel.SetupScrolling(scrollToTop=False, scrollIntoView=False)
        self.panel.SetDoubleBuffered(True)

        self.Bind(const.EVT_APPEND, self.on_append)
        self.Bind(const.EVT_UPDATE, self.on_update)
        self.Bind(const.EVT_LAYOUT, self.on_layout)
        self.Bind(const.EVT_INFO, self.on_info)
        self.Bind(const.EVT_START_PROGRESS, self.on_start_progress)
        self.Bind(const.EVT_END_PROGRESS, self.on_end_progress)
        self.Bind(const.EVT_PLAY, self.on_play)
        self.Bind(wx.EVT_ACTIVATE, self.on_deactivate)
        self.Bind(wx.EVT_CLOSE, self.on_close)

        sizer_m = wx.BoxSizer()
        sizer_r = wx.BoxSizer(wx.VERTICAL)

        sizer_m_inner = wx.BoxSizer(wx.VERTICAL)
        sizer_m_inner.Add(self.panel_preview, 0, wx.ALIGN_CENTER)
        sizer_m_inner.Add(self.panel_property, 0, wx.GROW | wx.TOP, 10)

        sizer_m.Add(sizer_m_inner, 0, wx.ALIGN_CENTER)

        sizer_composite = wx.BoxSizer()
        sizer_composite.Add(self.panel_composite, 1)

        sizer_r.Add(self.panel_append, 1, wx.GROW | wx.RIGHT, 10)
        sizer_r.Add(sizer_composite, 0, wx.GROW | wx.RIGHT | wx.BOTTOM, 10)

        self.sizer.Add(self.panel_component, 0, wx.GROW | wx.ALL, 10)
        self.sizer.Add(wx.Panel(self.panel), 1)
        self.sizer.Add(sizer_m, 0, wx.GROW | wx.ALL, 10)
        self.sizer.Add(wx.Panel(self.panel), 1)
        self.sizer.Add(sizer_r, 0, wx.GROW | wx.TOP | wx.LEFT, 10)
        self.panel.SetSizer(self.sizer)
        self.sizer.Fit(self)

        margin = 50
        size = [dim + margin for dim in self.GetSize()]
        self.SetSize(size)
        self.Centre()

    def on_left(self, event):
        self.PopupMenu(menus.ComponentMenu(self, None))

    def on_append(self, event):
        if event.id_replace:
            is_completed = CONFIG.manager.replace(event.path_image, event.id_replace, event.frames)
        else:
            is_completed = CONFIG.manager.append(event.path_image, event.frames)

        if not is_completed:
            message = f"{event.path_image.stem}が開けません！"
            caption = "ファイルアクセスエラー"
            wxlib.show_message(None, message, caption, wx.ICON_ERROR)
            return

        wxlib.post_update(self, True, True, True)

    def on_update(self, event):
        if event.reset:
            self.panel_component.reset_icon()
            self.panel_property.reset_icon()

        if event.preview:
            self.panel_preview.update_display()

        if event.property:
            self.panel_property.update_display()

        if event.component:
            self.panel_component.update_display()
            self.panel_composite.update_display()

    def on_layout(self, event):
        self.sizer.Layout()
        self.panel.FitInside()

    def on_info(self, event):
        wxlib.show_message(self, event.message, event.caption, event.style)

    # ダイアログ作成中に完了するような作業だと順序が前後することがあるため
    # finish_progressで吸収しなくちゃいけなくなった
    def on_start_progress(self, event):
        self.is_progress = True
        self.dial_progress = wx.ProgressDialog(event.caption, event.message, parent=None,
                                               style=wx.PD_APP_MODAL | wx.PD_SMOOTH | wx.PD_AUTO_HIDE)
        self.dial_progress.Pulse()
        if not self.is_progress:
            self.finish_progress()

    def on_end_progress(self, event):
        self.message = event.message
        self.caption = event.caption
        self.style = event.style
        self.path_open = event.path_open
        self.need_play = event.need_play
        self.is_progress = False
        self.finish_progress()

    def finish_progress(self):
        if not isinstance(self.dial_progress, wx.ProgressDialog):
            return

        self.dial_progress.Destroy()
        self.dial_progress = None

        # PD_APP_MODALのプログレスダイアログを閉じるとバグで親ウインドウの表示位置が背面に下がるため前面に持ってくる
        self.Raise()
        if self.message:
            wxlib.show_message(self, self.message, self.caption, self.style)

        if self.path_open:
            os.startfile(self.path_open)

        if self.need_play:
            self.panel_preview.show_animation()

    def on_play(self, event):
        wxlib.post_start_progress(self, "少しお待ちください…", "プレビュー作成中")
        is_single = self.panel_composite.radio_single.GetValue()
        thread_preview = threading.Thread(target=self.save_preview, args=(is_single,), daemon=True)
        thread_preview.start()

    def save_preview(self, is_single):
        with wxlib.progress_context(self, "プレビューの作成に失敗しました…", "プレビュー作成失敗"):
            CONFIG.manager.save_preview(is_single)
            wxlib.post_end_progress(self, need_play=True)

    # color_picker_dialogの位置調整
    def on_deactivate(self, event):
        if event.GetActive():
            return

        hwnd_dial = win32gui.FindWindow(None, "色の設定")
        if not hwnd_dial:
            return

        left, top = self.GetPosition()
        width, height = self.GetSize()
        right = left + width

        l, t, r, b = win32gui.GetWindowRect(hwnd_dial)
        width_dial, height_dial = r - l, b - t
        pos = (np.clip(right - width_dial, 0, const.WIDTH_WORKING - width_dial),
               np.clip(top, 0, const.HEIGHT_WORKING - height_dial))
        try:
            win32gui.SetWindowPos(hwnd_dial, win32con.HWND_TOP, *pos, width_dial, height_dial,
                                  win32con.SWP_SHOWWINDOW)
        except Exception:
            pass

    def on_close(self, event):
        message = "終了してよろしいですか？"
        caption = "終了確認"
        style = wx.ICON_EXCLAMATION | wx.OK | wx.CANCEL
        result = wxlib.show_message(self, message, caption, style)
        if result != wx.ID_OK:
            return

        self.Destroy()


class WatchFilter(wx.EventFilter):
    def __init__(self):
        super().__init__()

    def FilterEvent(self, event):
        t = event.GetEventType()
        obj = event.GetEventObject()
        if t != 10121:
            if t == wx.wxEVT_MENU_HIGHLIGHT:
                print("highlight", end="")

            print(t)

        return self.Event_Skip


if __name__ == '__main__':
    PROCESS_PER_MONITOR_DPI_AWARE = 2
    ctypes.windll.shcore.SetProcessDpiAwareness(PROCESS_PER_MONITOR_DPI_AWARE)
    wx.DisableAsserts()
    app = wx.App()
    name_instance = f"{app.GetAppName()}-{wx.GetUserId()}"
    instance = wx.SingleInstanceChecker(name_instance)
    if instance.IsAnotherRunning():
        wx.Exit()

    # watcher = WatchFilter()
    # app.AddFilter(watcher)

    MainFrame().Show()
    app.MainLoop()
