from PIL import Image, ImageSequence, ImageChops
import wx
import pathlib
import math
import threading
import sys
from config import *

import transparator


def create_transparent(parent, event):
    path_image = select_file(None, "肌を透過したい画像を選択", "たぬき画像(png,gif)|*.gif;*.png")
    if not path_image:
        return

    dial_pro = wx.ProgressDialog("透過画像作成中", "しばらくお待ちください…", parent=parent,
                                 style=wx.PD_APP_MODAL | wx.PD_SMOOTH)
    dial_pro.Pulse()

    thread_mask = threading.Thread(target=transparator.get_mask_by_edge_cv,
                                   args=(path_image, parent, event, dial_pro))
    thread_mask.start()


def clip_face_for_costume(parent, event):
    path_image = select_file(None, "きぐるみ用に顔をきりぬきたい画像を選択", "たぬき画像(png,gif)|*.gif;*.png")
    if not path_image:
        return

    for key in DIC_TANUKI_OFFSET.keys():
        if key in path_image.stem:
            x_tanuki, y_tanuki = DIC_TANUKI_OFFSET.get(key, OFFSET_FLAT)[0]
            break

    else:
        x_tanuki, y_tanuki = OFFSET_FLAT[0]

    images_source = [im.convert("RGBA") for im in ImageSequence.Iterator(Image.open(path_image))]
    lst_mask = [im.convert("RGBA").split()[-1] for im in
                ImageSequence.Iterator(Image.open(PATH_MASK_FACE))]

    images_face = []
    for im_face, mask in zip(images_source, lst_mask):
        offset_mask = (im_face.width // 2 - mask.width // 2 + x_tanuki,
                       im_face.height // 2 - mask.height // 2 + y_tanuki)
        alpha_mask = Image.new("L", im_face.size, 0)
        alpha_mask.paste(mask, offset_mask)
        alpha_mask = alpha_mask.convert("1")
        alpha_face = im_face.split()[-1].convert("1")

        alpha = ImageChops.logical_and(alpha_face, alpha_mask).convert("L")
        im_face.putalpha(alpha)
        # たぬきごとのオフセットを与えていた場合、顔位置を標準に合わせる
        if x_tanuki or y_tanuki:
            offset_adjust = (mask.width // 2 - im_face.width//2 - x_tanuki,
                             mask.height // 2 - im_face.height // 2 - y_tanuki)
            campus = Image.new("RGBA", mask.size, (0, 0, 0, 255))
            campus.paste(im_face, offset_adjust)
            im_face = campus

        images_face.append(im_face)

    path_image=pathlib.Path(path_image.parent/f"{path_image.stem}きぐるみ顔{path_image.suffix}")
    wx.PostEvent(parent, event(path_image=path_image, frames=images_face))


def separate_animation():
    lst_path = select_file(None, "アニメーション画像選択(複数選択可)",
                           "アニメーション画像(png,gif)|*.gif;*.png", style=wx.FD_MULTIPLE)
    if not lst_path:
        return

    folder_save = select_folder(None, "保存先ディレクトリ選択")
    if not folder_save:
        return

    is_saved = False
    for path_image in lst_path:
        image = Image.open(path_image)
        if not image.is_animated:
            show_message(None, f"{path_image.name}はアニメーション画像ではありません。", "分割対象外")
            continue

        folder_separate = folder_save / path_image.stem
        folder_separate.mkdir(exist_ok=True)
        digits_zfill = int(math.log(image.n_frames, 10)) + 1
        for ix, frame in enumerate(ImageSequence.Iterator(image)):
            frame.save(
                folder_separate / f"{path_image.stem}【{str(ix + 1).zfill(digits_zfill)}】.png")

        is_saved = True

    if is_saved:
        show_message(None, "分割画像を保存しました。", "分割完了")


def connect_frames(duration):
    folder_frame = select_folder(None, "結合したい画像が入ったフォルダを選択")
    if not folder_frame:
        return

    name_default = folder_frame.stem + ".gif"
    with wx.FileDialog(None, "GIF保存", defaultFile=name_default, wildcard="gifファイル(gif)|*.gif",
                       style=wx.FD_SAVE) as dial:
        if not dial.ShowModal() == wx.ID_OK:
            return False

        path_save = dial.GetPath()

    frames = []
    for path_image in folder_frame.glob("*.png"):
        frame = Image.open(path_image).convert("RGBA")
        alpha = frame.split()[-1]
        black = (0, 0, 0)
        black_replace = (1, 1, 1)

        # 減色処理
        frame = frame.convert("RGB").quantize(colors=255, method=Image.MEDIANCUT,
                                              kmeans=100).convert("RGB")
        r, g, b = frame.split()
        r = r.point(lambda x: 1 if x == black[0] else 0, mode="1")
        g = g.point(lambda x: 1 if x == black[1] else 0, mode="1")
        b = b.point(lambda x: 1 if x == black[2] else 0, mode="1")
        mask = ImageChops.logical_and(r, g)
        mask = ImageChops.logical_and(mask, b)
        frame.paste(Image.new("RGB", frame.size, black_replace), mask=mask)
        frame = frame.convert("RGB").convert("P", palette=Image.ADAPTIVE, colors=255)
        mask = Image.eval(alpha, lambda a: 255 if a <= 128 else 0)
        frame.paste(255, mask=mask)
        frames.append(frame)

    if not frames:
        show_message(None, "フォルダ内にPNG画像がありませんでした。", "画像なし", wx.ICON_ERROR)
        return

    frames[0].save(path_save, save_all=True, append_images=frames[1:],
                   optimize=False, loop=0, duration=duration, transparency=255,
                   disposal=2)

    show_message(None, "GIF画像を保存しました。", "GIF作成")


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


def show_message(parent, message, caption, style=wx.ICON_INFORMATION):
    with wx.MessageDialog(parent, message, caption, style=style) as dial:
        dial.ShowModal()


if __name__ == '__main__':
    app = wx.App()
    separate_animation()
