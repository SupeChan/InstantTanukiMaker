import wx
from wx.lib.scrolledpanel import ScrolledPanel
from wx.adv import AnimationCtrl
import ctypes
import re
from config import *
import compositor


class MainFrame(wx.Frame):
    def __init__(self):
        super().__init__(None, -1, "たぬこら")
        self.image_composite = None
        self.order_composite = ORDER_COMPOSITE_DEFAULT

        icon = wx.Icon(str(PATH_ICON))
        self.SetIcon(icon)
        self.panel = ScrolledPanel(self)
        self.widgets_composite = []
        self.ctrl_anime = AnimationCtrl(self.panel, -1, size=SIZE_ANIME)
        self.combo_base = wx.ComboBox(self.panel, -1, style=STYLE_CB)
        self.dic_image_base = {}
        self.spin_duration = wx.SpinCtrl(self.panel, -1, max=1000, min=20,
                                         style=wx.TE_PROCESS_ENTER)
        self.btn_play = wx.Button(self.panel, -1, "再生")
        self.btn_save = wx.Button(self.panel, -1, "保存")
        self.sizer_main = wx.BoxSizer()
        self.setting_widgets()

    def setting_widgets(self):
        self.panel.SetupScrolling()
        self.spin_duration.SetValue(100)
        self.combo_base.Disable()
        self.btn_save.Disable()

        menubar = wx.MenuBar()
        menu_config = wx.Menu()
        menu_order = menu_config.Append(-1, "順序変更")
        menubar.Append(menu_config, "設定")
        self.SetMenuBar(menubar)

        sizer_preview = wx.BoxSizer(wx.VERTICAL)
        sbox_base = wx.StaticBox(self.panel, -1, BASE)
        sbsizer_base = wx.StaticBoxSizer(sbox_base)
        fxsizer_base = wx.FlexGridSizer(rows=2, cols=3, gap=(5, 5))
        fxsizer_base.AddGrowableCol(0)
        fxsizer_base.AddGrowableCol(1)
        fxsizer_composite = self.create_widgets_parts()

        combo_folder = wx.ComboBox(self.panel, -1, choices=list(DIC_FOLDER_BASE.keys()),
                                   style=STYLE_CB)
        btn_append_base = wx.Button(self.panel, -1, "外部画像取込")

        fxsizer_base.Add(wx.StaticText(self.panel, -1, "分類", style=wx.ALIGN_CENTER), 1, wx.GROW)
        fxsizer_base.Add(wx.StaticText(self.panel, -1, "選択画像", style=wx.ALIGN_CENTER), 1, wx.GROW)
        fxsizer_base.Add(wx.StaticText(self.panel, -1, "", style=wx.ALIGN_CENTER), 1, wx.GROW)
        fxsizer_base.Add(combo_folder, 1, wx.GROW)
        fxsizer_base.Add(self.combo_base, 1, wx.GROW)
        fxsizer_base.Add(btn_append_base, 1, wx.GROW)
        sbsizer_base.Add(fxsizer_base, 1, wx.GROW)

        sbox_duration = wx.StaticBox(self.panel, -1, "表示間隔(ミリ秒)1000~20")
        sbsizer_duration = wx.StaticBoxSizer(sbox_duration)
        sbsizer_duration.Add(self.spin_duration, 1, wx.GROW)

        # fxsizer_composite.Add(wx.StaticText(self.panel, -1, ""), 1, wx.GROW)
        fxsizer_composite.Add(sbsizer_duration, 1, wx.GROW)
        fxsizer_composite.Add(self.btn_play, 0, wx.GROW)

        combo_folder.Bind(wx.EVT_COMBOBOX, self.on_select)
        self.combo_base.Bind(wx.EVT_COMBOBOX, self.on_preview)

        btn_append_base.Bind(wx.EVT_BUTTON, self.on_append_base)

        self.Bind(wx.EVT_MENU, self.on_order, menu_order)
        self.spin_duration.Bind(wx.EVT_SPINCTRL, self.on_preview)
        self.spin_duration.Bind(wx.EVT_TEXT_ENTER, self.on_preview)
        self.btn_play.Bind(wx.EVT_BUTTON, self.on_play)
        self.btn_save.Bind(wx.EVT_BUTTON, self.on_save)

        sizer_preview.Add(sbsizer_base, 0, wx.GROW | wx.ALL, 5)
        sizer_preview.Add(wx.StaticText(self.panel, -1, ""), 0, wx.GROW | wx.ALL, 5)

        sizer_preview.Add(fxsizer_composite, 1, wx.GROW | wx.ALL, 5)
        sizer_preview.Add(wx.StaticText(self.panel, -1, ""), 0, wx.GROW | wx.ALL, 5)
        sizer_preview.Add(self.btn_save, 0, wx.GROW | wx.ALL, 5)

        self.sizer_main.Add(self.ctrl_anime, 0, wx.ALIGN_CENTER | wx.ALL, 5)
        self.sizer_main.Add(sizer_preview, 1, wx.GROW | wx.ALL, 5)

        self.panel.SetSizer(self.sizer_main)
        self.sizer_main.Fit(self)
        self.Centre()

    def create_widgets_parts(self):
        fxsizer_composite = wx.FlexGridSizer(rows=5, cols=2, gap=(15, 5))
        fxsizer_composite.AddGrowableCol(0)
        fxsizer_composite.AddGrowableCol(1)
        for label_parts in LST_ORDER_PARTS:
            dic_parts = DIC_DIC_PARTS.get(label_parts)
            choices = list(dic_parts.keys()) + ["無し"]
            width, height = SIZE_ANIME

            sbox_parts = wx.StaticBox(self.panel, -1, label_parts)
            sbsizer_parts = wx.StaticBoxSizer(sbox_parts, wx.VERTICAL)
            gbsizer_config = wx.GridBagSizer(5, 5)

            gbsizer_config.AddGrowableCol(0)

            stext_image = wx.StaticText(self.panel, -1, "選択画像", style=wx.ALIGN_CENTER)
            stext_offset = wx.StaticText(self.panel, -1, "オフセット", style=wx.ALIGN_CENTER)
            stext_angle = wx.StaticText(self.panel, -1, "角度", style=wx.ALIGN_CENTER)
            stext_zoom = wx.StaticText(self.panel, -1, "拡大率", style=wx.ALIGN_CENTER)

            combo_image = wx.ComboBox(self.panel, -1, choices=choices, style=STYLE_CB)
            spin_x = wx.SpinCtrl(self.panel, -1, max=width, min=-width,
                                 style=wx.SP_HORIZONTAL | wx.TE_PROCESS_ENTER)
            spin_y = wx.SpinCtrl(self.panel, -1, max=height, min=-height, style=wx.TE_PROCESS_ENTER)
            spin_angle = wx.SpinCtrl(self.panel, -1, max=359, min=-359, style=wx.TE_PROCESS_ENTER)
            spin_zoom = wx.SpinCtrlDouble(self.panel, -1, max=3, min=0.1, inc=0.01)
            check_aligned = wx.CheckBox(self.panel, -1, "位置合わせ")
            btn_append = wx.Button(self.panel, -1, "外部画像取込")

            spin_zoom.SetValue(1.0)

            gbsizer_config.Add(stext_image, (0, 0), (1, 1), wx.GROW)
            gbsizer_config.Add(stext_offset, (0, 1), (1, 1))
            gbsizer_config.Add(stext_angle, (0, 2), (1, 1))
            gbsizer_config.Add(stext_zoom, (0, 3), (1, 1))

            gbsizer_config.Add(combo_image, (1, 0), (1, 1), wx.GROW)
            gbsizer_config.Add(spin_x, (1, 1), (1, 1))
            gbsizer_config.Add(spin_y, (2, 1), (1, 1))
            gbsizer_config.Add(spin_angle, (1, 2), (1, 1))
            gbsizer_config.Add(spin_zoom, (1, 3), (1, 1))
            gbsizer_config.Add(check_aligned, (2, 0), (1, 1))
            gbsizer_config.Add(btn_append, (2, 2), (1, 2), wx.GROW)

            sbsizer_parts.Add(gbsizer_config, 1, wx.GROW)

            fxsizer_composite.Add(sbsizer_parts, 1, wx.GROW)

            widgets_parts = [combo_image, spin_x, spin_y, spin_angle, spin_zoom, check_aligned]
            for widget in widgets_parts[1:]:
                widget.Disable()

            if not DIC_ALIGNMENT.get(label_parts, False):
                check_aligned.Hide()

            # ちょっと発火条件については考える
            combo_image.Bind(wx.EVT_COMBOBOX, self.on_preview)
            for spin in widgets_parts[1:-2]:
                spin.Bind(wx.EVT_TEXT_ENTER, self.on_preview)
                spin.Bind(wx.EVT_KILL_FOCUS, self.on_preview)
                spin.Bind(wx.EVT_SPINCTRL, self.on_preview)

            spin_zoom.Bind(wx.EVT_SPINCTRLDOUBLE, self.on_preview)
            check_aligned.Bind(wx.EVT_CHECKBOX, self.on_preview)
            btn_append.Bind(wx.EVT_BUTTON, self.on_append_parts(label_parts, combo_image))

            self.widgets_composite.append(widgets_parts)

        return fxsizer_composite

    def on_order(self, event):
        title = "順序変更"
        message = "画像の順序変更\nリストの上にあるほど画面奥に、\n下にあるほど手前に表示されます。"
        order = list(range(len(self.order_composite)))
        with wx.RearrangeDialog(self, message, title, order=order,
                                items=self.order_composite) as dial:
            result = dial.ShowModal()
            if not result == wx.ID_OK:
                return

            self.order_composite = dial.GetList().GetItems()
            self.on_preview(None)

    def on_select(self, event):
        combo_folder = event.GetEventObject()
        key = combo_folder.GetValue()
        path_folder = DIC_FOLDER_BASE.get(key, False)
        if path_folder:
            self.dic_image_base = {path_image.stem: path_image for path_image in
                                   path_folder.glob("*.*")}
            keys = list(self.dic_image_base.keys())
            self.combo_base.Clear()
            self.combo_base.AppendItems(keys)

        self.combo_base.Enable(bool(path_folder))

    def on_append_base(self, event):
        with wx.FileDialog(self, "取り込みたい画像を選択してください。", "外部画像取込", wildcard="*.png;*.gif") as dial:
            result = dial.ShowModal()
            if not result == wx.ID_OK:
                return

            path_image_append = pathlib.Path(dial.GetPath())

        self.dic_image_base.update({path_image_append.stem: path_image_append})
        self.combo_base.Enable()
        self.combo_base.SetItems(list(self.dic_image_base.keys()))
        self.combo_base.SetValue(path_image_append.stem)
        self.on_preview(None)

    def on_append_parts(self, label_parts, combo_image):
        def inner(event):
            with wx.FileDialog(self, "取り込みたい画像を選択してください。", "外部画像取込",
                               wildcard="*.png;*.gif") as dial:
                result = dial.ShowModal()
                if not result == wx.ID_OK:
                    return

                path_image_append = pathlib.Path(dial.GetPath())

            dic_parts = DIC_DIC_PARTS.get(label_parts)
            dic_parts.update({path_image_append.stem: path_image_append})
            combo_image.SetItems(list(dic_parts.keys()) + ["無し"])
            combo_image.SetValue(path_image_append.stem)
            self.on_preview(None)

        return inner

    def on_preview(self, event):
        image_composite = self.create_image_composite()
        if not image_composite:
            return

        image_composite.save_gif()
        self.ctrl_anime.LoadFile(str(PATH_GIF_PREVIEW))
        self.btn_play.SetLabel("再生")
        self.btn_save.Enable()
        self.sizer_main.Fit(self)

        if event:
            event.Skip()

    def on_play(self, event):
        if self.ctrl_anime.IsPlaying():
            self.ctrl_anime.Stop()
            self.btn_play.SetLabel("再生")
        else:
            self.ctrl_anime.Play()
            self.btn_play.SetLabel("停止")

    def on_save(self, event):
        image_composite = self.create_image_composite()
        if not image_composite:
            with wx.MessageDialog(self, "画像が選択されていません。", "画像未選択",
                                  style=wx.ICON_ERROR) as dial:
                dial.ShowModal()

            return

        name_save = image_composite.get_name_save()
        with wx.FileDialog(self, "名前を付けて保存", wildcard="*.gif",
                           defaultFile=name_save,
                           style=wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT) as dial:
            result = dial.ShowModal()
            if not result == wx.ID_OK:
                return

            path_save = pathlib.Path(dial.GetPath())

        image_composite.save_gif(path_save)
        with wx.MessageDialog(self, "たぬき画像を保存しました。", "保存完了", style=wx.ICON_INFORMATION) as dial:
            dial.ShowModal()

    def create_image_composite(self):
        path_image_base = self.dic_image_base.get(self.combo_base.GetValue(), False)
        lst_parts = []

        key_offset = None
        if path_image_base:
            stem_base = path_image_base.stem
            for key in DIC_TANUKI_OFFSET.keys():
                match_offset = re.search(key, stem_base)
                if match_offset:
                    key_offset = match_offset.group()

        offset_tanuki_x, offset_tanuki_y = DIC_TANUKI_OFFSET.get(key_offset, (0, 0))

        for label_parts, widgets_parts in zip(LST_ORDER_PARTS, self.widgets_composite):
            dic_parts = DIC_DIC_PARTS.get(label_parts, False)
            cb_image, spin_x, spin_y, spin_angle, spin_zoom, check_aligned = widgets_parts
            path_image_parts = dic_parts.get(cb_image.GetValue(), False)
            [widget.Enable(bool(path_image_parts)) for widget in widgets_parts[1:]]
            if not path_image_parts:
                continue

            offset_x, offset_y = (
                spin_x.GetValue() + offset_tanuki_x, -spin_y.GetValue() + offset_tanuki_y)
            angle = spin_angle.GetValue()

            rate_zoom = spin_zoom.GetValue()

            need_aligned = check_aligned.GetValue()
            lst_parts.append(
                [label_parts, path_image_parts, offset_x, offset_y, angle, rate_zoom, need_aligned])

        if not (path_image_base or lst_parts):
            return False

        duration = self.spin_duration.GetValue()
        image_composite = compositor.CompositeImage(path_image_base, lst_parts,
                                                    duration, self.order_composite)
        return image_composite


if __name__ == '__main__':
    ctypes.windll.shcore.SetProcessDpiAwareness(PROCESS_PER_MONITOR_DPI_AWARE)
    app = wx.App()

    name_instance = f"{app.GetAppName()}-{wx.GetUserId()}"
    instance = wx.SingleInstanceChecker(name_instance)
    if instance.IsAnotherRunning():
        wx.Exit()

    frame = MainFrame()
    frame.Show()
    app.MainLoop()
