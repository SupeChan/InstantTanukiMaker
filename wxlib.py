import wx
import pathlib

from contextlib import contextmanager

import const


# show_dialog
def show_message(parent, message, caption, style=wx.ICON_INFORMATION):
    with wx.MessageDialog(parent, message, caption, style) as dial:
        result = dial.ShowModal()

    return result


def select_file(parent, caption, wildcard, style=wx.FD_DEFAULT_STYLE):
    with wx.FileDialog(parent, caption, wildcard=wildcard, style=style) as dial:
        if not dial.ShowModal() == wx.ID_OK:
            return False

        result = ([pathlib.Path(path) for path in dial.GetPaths()] if style == wx.FD_MULTIPLE
                  else pathlib.Path(dial.GetPath()))

        return result


def select_folder(parent, message):
    with wx.DirDialog(parent, message) as dial:
        if not dial.ShowModal() == wx.ID_OK:
            return False

        return pathlib.Path(dial.GetPath())


def save_file(parent, caption, wildcard, name_save, style=wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT):
    with wx.FileDialog(parent, caption, wildcard=wildcard, defaultFile=name_save, style=style) as dial:
        if not dial.ShowModal() == wx.ID_OK:
            return False

        return pathlib.Path(dial.GetPath())


# post_event
def post_update(target_post, preview=False, prop=False, component=False,reset=False):
    wx.PostEvent(target_post, const.EVENT_UPDATE(preview=preview, property=prop, component=component,reset=reset))


def post_append(target_post, path_image, frames=None, id_replace=None):
    wx.PostEvent(target_post, const.EVENT_APPEND(path_image=path_image, frames=frames, id_replace=id_replace))


def post_info(target_post, message, caption, style=wx.ICON_INFORMATION):
    wx.PostEvent(target_post, const.EVENT_INFO(message=message, caption=caption, style=style))


def post_start_progress(target_post, message, caption):
    wx.PostEvent(target_post, const.EVENT_START_PROGRESS(message=message, caption=caption))


def post_end_progress(target_post, message="", caption="", style=wx.ICON_INFORMATION, path_open=None, need_play=False):
    wx.PostEvent(target_post,
                 const.EVENT_END_PROGRESS(message=message, caption=caption, style=style,
                                          path_open=path_open, need_play=need_play))


def post_play(target_post):
    wx.PostEvent(target_post, const.EVENT_PLAY())


def post_layout(target_post):
    wx.PostEvent(target_post, const.EVENT_LAYOUT())


def post_select(target_post, path):
    wx.PostEvent(target_post, const.EVENT_SELECT(path=path))


@contextmanager
def progress_context(target_post, message, caption):
    try:
        yield
    except Exception as e:
        message = message + f"\n{e}"
        post_end_progress(target_post, message, caption, wx.ICON_ERROR)
