import wx
from PIL import (Image, ImageChops, ImageOps, ImageDraw, ImageFont, ImageFilter, ImageSequence,
                 UnidentifiedImageError)

import cv2
import numpy as np
import math
import base64

from itertools import cycle
import const

from PIL import ImageFile

ImageFile.LOAD_TRUNCATED_IMAGES = True


# 透過画像の作成
def make_transparent(frames, colors_target, face_only):
    try:
        im_face = Image.open(const.PATH_MASK_FACE)
        cycle_mask_face = cycle([ImageOps.invert(im.convert("RGBA").split()[-1])
                                 for im in ImageSequence.Iterator(im_face)])
        frames_trans = []
        for frame_origin, mask_face in zip(frames, cycle_mask_face):
            mask_trans = get_mask_trans(frame_origin, colors_target)
            if face_only:
                mask_trans = ImageChops.lighter(mask_trans, mask_face)

            image_trans = frame_origin.convert("RGBA")
            alpha = image_trans.split()[-1]
            mask_trans = ImageChops.darker(mask_trans, alpha)
            image_trans.putalpha(mask_trans)
            frames_trans.append(image_trans)

        return frames_trans

    except Exception as e:
        return False


def get_mask_trans(frame, colors_target):
    alpha = frame.convert("RGBA").split()[-1]
    mask = Image.eval(alpha, lambda a: 255 if a <= 100 else 0)
    frame_black = frame.convert("RGB")
    frame_black.paste((0, 0, 0), mask)
    frame_white = replace_color_hsv(frame_black, (0, 0, 0), (0, 0, 255)).convert("RGB")
    frame_white.paste((0, 0, 0), mask)
    cnts_mask = []
    for frame_bw in [frame_black, frame_white]:
        nd_image = np.array(frame_bw, np.uint8)
        nd_image = cv2.cvtColor(nd_image, cv2.COLOR_RGB2BGR)
        nd_gray = np.array(frame_bw.convert("L"))
        retval, nd_thresh = cv2.threshold(nd_gray, 0, 255, cv2.THRESH_OTSU)
        cnts, hie = cv2.findContours(nd_thresh, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
        for ix, cnt in enumerate(cnts):
            ix_next, ix_prev, child, parent = hie[0][ix]
            area = cv2.contourArea(cnt)

            # 面積の小さい部分はスキップ
            if area <= 10:
                continue

            # 親がおらず十分な大きさの子がいる輪郭はスキップ
            rate = 0.1
            if parent == -1 and child != -1:
                area_children = get_area_children(cnts, hie, child)
                if area_children / area >= rate:
                    continue

            nd_cnt = nd_image.copy()
            mask_cnt = np.zeros_like(nd_thresh, np.uint8)
            cv2.drawContours(mask_cnt, [cnt], 0, 255, -1)

            mask_cnt = cv2.cvtColor(mask_cnt, cv2.COLOR_GRAY2BGR)
            nd_cnt = cv2.bitwise_and(mask_cnt, nd_cnt)
            nd_cnt = cv2.cvtColor(nd_cnt, cv2.COLOR_BGR2HSV_FULL)
            # 輪郭を検出できなかった場合はスキップする。
            if not nd_cnt.any():
                continue

            color_mode_hsv = get_color_mode(nd_cnt, (0, 0, 0))
            if within_range_hsv(color_mode_hsv, colors_target):
                cnts_mask.append(cnt)

    nd_mask = np.zeros_like(nd_thresh, np.uint8)
    for cnt_face in cnts_mask:
        cv2.drawContours(nd_mask, [cnt_face], 0, 255, -1)

    mask_trans = cv2.cvtColor(nd_mask, cv2.COLOR_GRAY2BGR)
    mask_trans = Image.fromarray(mask_trans).convert("L")
    mask_trans = ImageOps.invert(mask_trans)

    image_replace = frame.convert("RGBA")
    for color in colors_target:
        image_replace = replace_color_hsv(image_replace, color, (0, 0, 0, 0))

    alpha_replace = image_replace.split()[-1]
    mask_trans = ImageChops.darker(mask_trans, alpha_replace)
    return mask_trans


def get_area_children(cnts, hie, child):
    ix_next = child
    area_children = 0
    while ix_next != -1:
        area_children += cv2.contourArea(cnts[ix_next])
        ix_next, ix_prev, child, parent = hie[0][ix_next]

    return area_children


def get_color_mode(nd_image, color_ignore):
    im = Image.fromarray(nd_image, "HSV")
    colors = im.getcolors(im.width * im.height)
    lst_count = [count for count, color in colors if color != color_ignore]
    ix_mode = lst_count.index(max(lst_count))
    count, color_mode = colors[ix_mode]
    return color_mode


def within_range_hsv(color_hsv, colors_target):
    for color_target in colors_target:
        h, s, v = color_target
        color_low = (h - 2, s - 5, v - 10)
        color_high = (h + 2, s + 5, v + 10)
        lst_matched = []
        for c, cl, ch in zip(color_hsv, color_low, color_high):
            lst_matched.append(cl <= c <= ch)

        if all(lst_matched):
            return True

    return False


def convert_rgb2hsv_full(rgb):
    image = Image.new("RGB", (1, 1), color=rgb)
    nd_image = np.array(image)
    nd_hsv = cv2.cvtColor(nd_image, cv2.COLOR_RGB2HSV_FULL)
    color_hsv = tuple(nd_hsv[0][0])
    return color_hsv


# 色の置換
def replace_color_hsv(image, color_target, color_replace):
    image_hsv = image.convert("HSV")
    h, s, v = image_hsv.split()
    h = h.point(lambda x: 1 if -2 <= x - color_target[0] <= 2 else 0, mode="1")
    s = s.point(lambda x: 1 if -5 <= x - color_target[1] <= 5 else 0, mode="1")
    v = v.point(lambda x: 1 if -10 <= x - color_target[2] <= 10 else 0, mode="1")
    mask = ImageChops.logical_and(h, s)
    mask = ImageChops.logical_and(mask, v)
    image_replace = image.convert("RGBA")
    image_replace.paste(Image.new("RGBA", image_replace.size, color_replace), mask=mask)
    return image_replace


# サムネイルアイコン作成
# size_icon:アイコンサイズ,size_thumb:アイコンに張り付けるサムネイルサイズ
def create_icon(im, size_icon, size_thumb=None, bg=None, alignment="Center"):
    size_thumb = size_thumb if size_thumb else size_icon
    im_thumb = im.convert("RGBA")
    bbox = im_thumb.getbbox()
    im_thumb = im_thumb.crop(bbox)
    im_thumb.thumbnail(size_thumb, Image.LANCZOS)
    campus_icon = Image.new("RGBA", size_icon, (255, 255, 255, 0))
    if alignment == "Center":
        offset = [(dim - dim_thumb) // 2 for dim, dim_thumb in zip(size_icon, im_thumb.size)]
    else:
        size = [(85 * dim) // 100 for dim in size_icon]
        offset = [(dim - dim_thumb) // 2 + 1 for dim, dim_thumb in zip(size, im_thumb.size)]
    campus_icon.paste(im_thumb, offset)

    if bg:
        bg = bg.convert("RGBA")
        bbox = bg.getbbox()
        im_bg = bg.crop(bbox)
        im_bg.thumbnail(size_icon, Image.LANCZOS)
        campus_bg = Image.new("RGBA", size_icon, (255, 255, 255, 0))
        offset = [(dim - dim_bg) // 2 for dim, dim_bg in zip(size_icon, im_bg.size)]

        campus_bg.paste(im_bg, offset)
        campus_icon = Image.alpha_composite(campus_bg, campus_icon)

    return campus_icon


# 画像にテキストを描画
def draw_text(im, text, size, path_font, color, bbox):
    im_draw = im.convert("RGBA")
    left, top, right, bottom = bbox
    center_x, center_y = left + (right - left) // 2, top + (bottom - top) // 2
    draw = ImageDraw.Draw(im_draw)
    font = ImageFont.truetype(str(path_font), size)
    w, h = draw.textsize(text, font=font)
    pos_draw = center_x - w // 2, center_y - h // 2
    draw.text(pos_draw, text, font=font, fill=color)
    return im_draw


# チェス盤作成
def create_chess_board(size, selected_file=True):
    width, height = size
    white_file = np.array((200, 210, 200), dtype=np.uint8)
    white_parts = np.array((200, 200, 215), dtype=np.uint8)
    gray_file = np.array((128, 138, 128), dtype=np.uint8)
    gray_parts = np.array((128, 128, 145), dtype=np.uint8)

    white = white_file if selected_file else white_parts
    gray = gray_file if selected_file else gray_parts
    tile_white = np.array([white] * 100).reshape(10, 10, 3)
    tile_gray = np.array([gray] * 100).reshape(10, 10, 3)
    tile = np.block([[[tile_white], [tile_gray]],
                     [[tile_gray], [tile_white]]])

    w, h = tile.shape[:-1]
    rep_width, rep_height = -(-width // w), -(-height // h)
    board = np.tile(tile, (rep_height, rep_width, 1))
    image_chess = Image.fromarray(board).convert("RGBA").crop((0, 0, *size))
    return image_chess


# 指定のポイントに表示されている画素があるか
def collide_point(im, point):
    x, y = point
    width, height = im.size
    if not (0 <= x < width and 0 <= y < height):
        return False

    alpha = im.split()[-1]
    alpha_pixel = alpha.getpixel((x, y))

    return bool(alpha_pixel)


# カラーブレンド
def multiply_color(image, color, *args):
    alpha = image.split()[-1]
    color_mask = Image.new("RGBA", image.size, color)
    image_edit = ImageChops.multiply(image, color_mask)
    image_edit.putalpha(alpha)
    return image_edit


def screen_color(image, color, *args):
    alpha = image.split()[-1]
    color_mask = Image.new("RGBA", image.size, color)
    image_edit = ImageChops.screen(image, color_mask)
    image_edit.putalpha(alpha)
    return image_edit


def overlay_color(image, color, *args):
    alpha = image.split()[-1]
    color_mask = Image.new("RGBA", image.size, color)
    image_edit = ImageChops.overlay(image, color_mask)
    image_edit.putalpha(alpha)
    return image_edit


def blend_alpha(image, color, alpha_blend, mode_color="RGBA"):
    alpha = image.split()[-1]
    color_mask = Image.new(mode_color, image.size, color).convert("RGBA")
    image_edit = Image.blend(image, color_mask, alpha_blend)
    image_edit.putalpha(alpha)
    return image_edit


DIC_FUNC_BLEND = {const.BlendMode.MULTIPLY: multiply_color,
                  const.BlendMode.SCREEN: screen_color,
                  const.BlendMode.OVERLAY: overlay_color,
                  const.BlendMode.ALPHA: blend_alpha}


def blend_color(image, color, mode_blend, alpha_blend=0):
    image_blend = image.convert("RGBA")
    func_blend = DIC_FUNC_BLEND.get(mode_blend)
    image_blend = func_blend(image_blend, color, alpha_blend)
    return image_blend


# カラーフィルター
def filtering_monochrome(frames, *args):
    return [im.convert("LA").convert("RGBA") for im in frames]


def filtering_ash(frames, *args):
    white = (255, 255, 255)
    alpha = 0.6
    return [blend_alpha(im.convert("LA").convert("RGBA"), white, alpha) for im in frames]


def filtering_gaming(frames, num=None, ix=None):
    num = num if num is not None else len(frames)
    if num and ix:
        lst_hsv = [(int(i * 255 / (num + 1)), 255, 255) for i in range(num)]
        lst_hsv = [lst_hsv[ix]]
    else:
        lst_hsv = [(int(i * 255 / (num + 1)), 255, 255) for i in range(len(frames))]

    frames_gaming = []
    for im, hsv in zip(frames, lst_hsv):
        im_gaming = blend_alpha(im, hsv, 0.3, "HSV")
        frames_gaming.append(im_gaming)

    return frames_gaming


DIC_FUNC_COLOR = {const.ColorFilter.MONO: filtering_monochrome,
                  const.ColorFilter.ASH: filtering_ash,
                  const.ColorFilter.GAMING: filtering_gaming}


def filtering_color(frames, mode_filter, num=None, ix=None):
    func_color = DIC_FUNC_COLOR.get(mode_filter)
    frames_color = func_color(frames, num, ix)
    return frames_color


# 画像フィルター
def filtering_line(frames, *args):
    frames_line = []
    for im in frames:
        alpha = im.split()[-1]
        im_line = im.filter(ImageFilter.CONTOUR).convert("L").convert("RGBA")
        im_line = im_line.filter(ImageFilter.SMOOTH_MORE)
        im_line.putalpha(alpha)
        frames_line.append(im_line)

    return frames_line


def filtering_coloring(frames, *args):
    frames_color = []
    for im in frames:
        alpha = im.split()[-1]
        im_color = Image.eval(im.convert("L"), lambda x: 255 if x > 15 else 0)
        alpha = ImageChops.darker(alpha, ImageOps.invert(im_color))
        im_color = im_color.convert("RGBA")
        im_color.putalpha(alpha)
        frames_color.append(im_color)

    return frames_color


def filtering_dot(frames, *args):
    dot_level = 3
    frames_dot = []
    for im in frames:
        alpha = im.split()[-1]
        im_dot = im.convert("RGB").convert("P", palette=Image.ADAPTIVE, colors=64)
        im_dot = (im_dot.resize([x // dot_level for x in im_dot.size], Image.LINEAR)
                  .resize(im_dot.size, Image.LINEAR))
        alpha = alpha.convert("RGB").convert("P", palette=Image.ADAPTIVE, colors=64)
        alpha = (alpha.resize([x // dot_level for x in alpha.size], Image.LINEAR)
                 .resize(alpha.size, Image.LINEAR))
        alpha = Image.eval(alpha.convert("L"), lambda x: 255 if x > 0 else 0)
        im_dot = im_dot.convert("RGBA")
        im_dot.putalpha(alpha)
        frames_dot.append(im_dot)

    return frames_dot


def filtering_mochi(frames, num, ix, rate=0.025):
    if num == 1:
        return frames

    num_frames = num if num is not None else len(frames)
    num_front = num_frames // 2 + 1
    num_back = -(-num_frames // 2) - 1
    inc = rate / num_front
    lst_front = [(1 + inc * i, 1 - inc * i) for i in range(num_front)]
    lst_back = lst_front[-2:-2 - num_back:-1]
    lst_zoom = lst_front + lst_back

    if ix is not None:
        lst_zoom = [lst_zoom[ix]]

    frames_mochi = []
    for frame, zoom in zip(frames, lst_zoom):
        bbox = frame.getbbox()

        if not bbox:
            frames_mochi.append(frame)
            continue

        left, top, right, bottom = bbox
        frame_mochi = frame.crop(frame.getbbox())
        center_x = left + frame_mochi.width // 2
        campus = Image.new("RGBA", frame.size, (255, 255, 255, 0))

        zoom_x, zoom_y = zoom
        width, height = int(frame_mochi.width * zoom_x), int(frame_mochi.height * zoom_y)
        width = width if width % 2 == 0 else width + 1

        frame_mochi = frame_mochi.resize((width, height), Image.LANCZOS)
        pos_paste = (center_x - frame_mochi.width // 2, bottom - frame_mochi.height)
        campus.paste(frame_mochi, pos_paste)
        frames_mochi.append(campus)

    return frames_mochi


DIC_FUNC_IMAGE = {const.ImageFilter.LINE: filtering_line,
                  const.ImageFilter.COLORING: filtering_coloring,
                  const.ImageFilter.DOT: filtering_dot,
                  const.ImageFilter.MOCHI: filtering_mochi}


def filtering_image(frames, mode_filter, num=None, ix=None):
    func_image = DIC_FUNC_IMAGE.get(mode_filter)
    frames_image = func_image(frames, num, ix)
    return frames_image


# GIF保存
def save_gif(path_save, frames, duration):
    frame_union, rate_changed = union_frames(frames)
    if rate_changed <= const.THRESHOLD_CONVERT_SINGLE:
        frames_convert = convert_single_palette(frames, frame_union)
    else:
        frames_convert = convert_multi_palette(frames)

    frames_convert[0].save(path_save, save_all=True, append_images=frames_convert[1:],
                           optimize=False, loop=0, duration=duration, transparency=255, disposal=2)


def union_frames(frames):
    width = sum([frame.width for frame in frames])
    height = max([frame.height for frame in frames])
    campus_union = Image.new("RGBA", (width, height), (255, 255, 255, 0))
    pos_x = 0
    set_pre = set()

    rates_changed = []
    for frame in frames:
        campus_union.paste(frame, (pos_x, 0))
        colors = campus_union.convert("RGB").getcolors(campus_union.width * campus_union.height)
        dic_count = {tuple(color): count for count, color in colors}
        set_colors = set([color for count, color in colors])
        delta_pixel = sum(
            [dic_count.get(tuple(color)) for color in list(set_colors - set_pre)]) if set_pre else 0
        rates_changed.append(delta_pixel / (frame.width * frame.height))

        pos_x += frame.width
        set_pre = set_colors

    rate_changed = sum(rates_changed)
    return campus_union, rate_changed


def convert_single_palette(frames, frame_union):
    campus_union = frame_union.convert("RGBA")
    alpha = campus_union.split()[-1]

    # 透過部分の色を統一して減色
    mask = Image.eval(alpha, lambda a: 255 if a <= 100 else 0)
    campus_union.paste((0, 0, 0, 0), mask)

    # median_cut+k_means colors=255で1色透過のために残す
    campus_union = campus_union.convert("RGB").quantize(colors=255, method=Image.Quantize.MEDIANCUT,
                                                        kmeans=100)
    # 透過部分に透過色を設定 255は空けておいた256色目のインデックス
    campus_union.paste(255, mask=mask)

    # 結合画像をフレームごとに分割
    pos_x = 0
    frames_convert = []
    for frame in frames:
        bbox = (pos_x, 0, pos_x + frame.width, frame.height)
        frame_conv = campus_union.crop(bbox)
        frames_convert.append(frame_conv)
        pos_x += frame.width

    return frames_convert


def convert_multi_palette(frames):
    frames_convert = []
    for frame in frames:
        alpha = frame.split()[-1]
        mask = Image.eval(alpha, lambda a: 255 if a <= 100 else 0)
        frame.paste((0, 0, 0, 0), mask)

        # 減色処理
        frame_conv = frame.convert("RGB").quantize(colors=255, method=Image.Quantize.MEDIANCUT,
                                                   kmeans=100)

        # 透過部を透過色に置換
        frame_conv.paste(255, mask=mask)
        frames_convert.append(frame_conv)

    return frames_convert


def save_png_sequence(folder_save, frames):
    folder_save.mkdir(exist_ok=True)
    digits_zfill = int(math.log(len(frames), 10)) + 1
    for ix, frame in enumerate(frames):
        path_seq = folder_save / f"【F{ix + 1}】{folder_save.stem}.png"
        frame.save(path_seq)


def save_png_sequence_contour(folder_save, frames, trim, area_omit):
    folder_save.mkdir(exist_ok=True)
    for ix_frame, frame in enumerate(frames):
        folder_frame = folder_save / f"【F{ix_frame + 1}】"
        folder_frame.mkdir(exist_ok=True)
        lst_im_sep = separate_contours(frame, trim, area_omit)
        for ix_sep, im_sep in enumerate(lst_im_sep):
            path_sep = folder_frame / f"【F{ix_frame + 1}】{folder_save.stem}({ix_sep + 1}).png"
            im_sep.save(path_sep)


def save_apng(path_save, frames, duration):
    # 背景色置き換え
    color_bg = (1, 1, 1)
    for frame in frames:
        r, g, b, alpha = frame.split()
        r = r.point(lambda x: 1 if x == color_bg[0] else 0, mode="1")
        g = g.point(lambda x: 1 if x == color_bg[1] else 0, mode="1")
        b = b.point(lambda x: 1 if x == color_bg[2] else 0, mode="1")
        mask = ImageChops.logical_and(r, g)
        mask = ImageChops.logical_and(mask, b)
        frame.paste(Image.new("RGBA", frame.size, (0, 0, 0, 0)), mask=mask)
        frame.putalpha(alpha)
        mask = Image.eval(alpha, lambda e: 255 if e == 0 else 0)
        frame.paste((*color_bg, 0), mask)

    frames[0].save(path_save, save_all=True, append_images=frames[1:], optimize=False, loop=0, duration=duration)


# 加工
def open_image(path_image):
    try:
        im = Image.open(path_image)
    except (UnidentifiedImageError, FileNotFoundError, PermissionError):
        return False

    return im


def get_frames(path_image):
    try:
        frames = [im.convert("RGBA") for im in ImageSequence.Iterator(Image.open(path_image))]
    except (UnidentifiedImageError, FileNotFoundError, PermissionError):
        return False

    return frames


def draw_selection_marker(im, color_outline):
    color_out_line_bgr = [color_outline[ix] for ix in [2, 1, 0]]
    alpha = im.convert("RGBA").split()[-1]
    nd_campus = cv2.cvtColor(np.array(im.convert("RGBA"), np.uint8), cv2.COLOR_RGB2BGR)
    nd_alpha = np.array(alpha, np.uint8)

    retval, nd_thresh = cv2.threshold(nd_alpha, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    cnts, _ = cv2.findContours(nd_alpha, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    for cnt in cnts:
        cv2.drawContours(nd_campus, [cnt], 0, color_out_line_bgr, 5)
        cv2.drawContours(nd_alpha, [cnt], 0, (255, 255, 255), 5)

    nd_campus = cv2.cvtColor(nd_campus, cv2.COLOR_BGR2RGB)
    im_marked = Image.fromarray(nd_campus).convert("RGBA")
    alpha_outline = Image.fromarray(nd_alpha)
    alpha_clip = Image.eval(alpha, lambda e: 0 if e == 0 else 255)
    alpha_outline = ImageChops.darker(alpha_clip, alpha_outline)
    im_marked.putalpha(alpha_outline)
    return im_marked


def clip_by_images(im, clippers):
    threshold_visible = 235
    im_target = im.convert("RGBA")
    alpha_target = im_target.split()[-1]
    for im_clip in clippers:
        alpha_target_binary = Image.eval(alpha_target, lambda e: 255 if e > 0 else 0)
        alpha_clip = Image.eval(im_clip.split()[-1], lambda e: 255 if e > threshold_visible else 0)
        alpha_clip = ImageChops.darker(alpha_target_binary, alpha_clip)
        alpha_clip = ImageChops.invert(alpha_clip)
        alpha_target = ImageChops.darker(alpha_target, alpha_clip)

    im_target.putalpha(alpha_target)
    return im_target


def apply_anti_alias(campus_origin, campus_smooth, im_inner, im_outer=None):
    alpha = im_inner.split()[-1]
    mask_edge = (alpha.filter(ImageFilter.FIND_EDGES).convert("L")
                 .filter(ImageFilter.GaussianBlur(0.75)))
    mask_edge = Image.eval(mask_edge, lambda a: 255 if a > 48 else 0)
    if im_outer:
        alpha_outer = im_outer.split()[-1]
        mask_edge = ImageChops.darker(mask_edge, alpha_outer)

    campus_smooth.putalpha(mask_edge)
    campus_alias = Image.alpha_composite(campus_origin, campus_smooth)
    return campus_alias


def clip_for_costume(path_image, frames):
    for key in const.DIC_BASE_OFFSET.keys():
        if key in path_image.stem:
            offset_x, offset_y = const.DIC_BASE_OFFSET.get(key)
            break
    else:
        offset_x, offset_y = const.OFFSET_FLAT

    cycle_mask = cycle([im.convert("RGBA").split()[-1]
                        for im in ImageSequence.Iterator(Image.open(const.PATH_MASK_COSTUME))])

    frames_clip = []
    for im_face, mask in zip(frames, cycle_mask):
        offset_mask = (im_face.width // 2 - mask.width // 2 + offset_x,
                       im_face.height // 2 - mask.height // 2 + offset_y)
        alpha_mask = Image.new("L", im_face.size, 0)
        alpha_mask.paste(mask, offset_mask)
        alpha_mask = alpha_mask.convert("1")
        alpha_face = im_face.split()[-1].convert("1")

        alpha = ImageChops.logical_and(alpha_face, alpha_mask).convert("L")
        im_face.putalpha(alpha)
        # たぬきごとのオフセットを与えていた場合、顔位置を標準に合わせる
        if offset_x or offset_y:
            offset_adjust = (mask.width // 2 - im_face.width // 2,
                             mask.height // 2 - im_face.height // 2)
            campus = Image.new("RGBA", mask.size, (0, 0, 0, 255))
            campus.paste(im_face, offset_adjust)
            im_face = campus

        frames_clip.append(im_face)

    return frames_clip


# [腕と手]のようなスプライトシートを輪郭ごとに分割
def separate_sprite_sheet(path_file):
    im = open_image(path_file)
    if not im:
        return []

    alpha = im.convert("RGBA").split()[-1]
    nd_alpha = np.array(alpha, np.uint8)
    center_x = im.width // 2
    is_arm = "[腕と手]" in path_file.stem

    retval, nd_thresh = cv2.threshold(nd_alpha, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    cnts, _ = cv2.findContours(nd_alpha, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    lst_sep = []
    counter_left = 0
    counter_right = 0
    area_omit = 10
    for cnt in cnts:
        if cv2.contourArea(cnt) <= area_omit:
            continue

        mask_sep = np.zeros_like(nd_thresh, np.uint8)
        cv2.drawContours(mask_sep, [cnt], 0, 255, -1)
        mask_sep = cv2.cvtColor(mask_sep, cv2.COLOR_GRAY2BGR)
        mask_sep = Image.fromarray(mask_sep).convert("L")
        mask_sep = ImageChops.darker(mask_sep, alpha)

        image_sep = im.convert("RGBA")
        image_sep.putalpha(mask_sep)

        if is_arm:
            pos_x = min([x for tup in cnt for x, y in tup])
            if pos_x <= center_x:
                path_sep = path_file.parent / f"【右手{counter_right}】{path_file.stem}.png"
                counter_right += 1
            else:
                path_sep = path_file.parent / f"【左手{counter_left}】{path_file.stem}.png"
                counter_left += 1

        else:
            path_sep = path_file.parent / f"【{counter_right}】{path_file.stem}.png"
            counter_right += 1

        image_sep = image_sep.crop(image_sep.getbbox())
        lst_sep.append([image_sep, path_sep])

    return lst_sep[::-1]


# 目やにんじんのような分解して使いたいアニメーション画像を輪郭ごとに分割
def separate_contours(frame, trim, area_omit):
    alpha = frame.convert("RGBA").split()[-1]
    nd_alpha = np.array(alpha, np.uint8)
    retval, nd_thresh = cv2.threshold(nd_alpha, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    cnts, _ = cv2.findContours(nd_alpha, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    lst_im_sep = []

    for cnt in cnts:
        # 小さすぎるものは除外
        if cv2.contourArea(cnt) < area_omit:
            continue

        mask_sep = np.zeros_like(nd_thresh, np.uint8)
        cv2.drawContours(mask_sep, [cnt], 0, 255, -1)
        mask_sep = cv2.cvtColor(mask_sep, cv2.COLOR_GRAY2BGR)
        mask_sep = Image.fromarray(mask_sep).convert("L")
        mask_sep = ImageChops.darker(mask_sep, alpha)

        image_sep = frame.convert("RGBA")
        image_sep.putalpha(mask_sep)

        if trim:
            image_sep = image_sep.crop(image_sep.getbbox())

        lst_im_sep.append(image_sep)

    return lst_im_sep


def encode_image(im):
    nd_im = np.array(im)
    nd_im = cv2.cvtColor(nd_im, cv2.COLOR_RGBA2BGRA)
    _, enc_im = cv2.imencode(".png", nd_im)
    bytes_im = enc_im.tobytes()
    bytes_enc = base64.b64encode(bytes_im).decode("utf-8")
    return bytes_enc


def decode_image(byte_im):
    byte_dec = base64.b64decode(byte_im)
    nd_dec = np.frombuffer(byte_dec, dtype='uint8')
    nd_im = cv2.imdecode(nd_dec, cv2.IMREAD_UNCHANGED)
    nd_im = cv2.cvtColor(nd_im, cv2.COLOR_BGRA2RGBA)
    im = Image.fromarray(nd_im).convert("RGBA")
    return im


# 部品作成用
def create_bitmap_icon():
    import pathlib
    size_icon = (100,100)
    width, height = size_icon
    app = wx.App()
    with wx.DirDialog(None, "アイコンフォルダを選択") as dial:
        result = dial.ShowModal()
        if result != wx.ID_OK:
            return

        folder = pathlib.Path(dial.GetPath())

    for path_image in folder.iterdir():
        image_original = Image.open(path_image).convert("RGBA")
        bbox = image_original.getbbox()
        image_crop = image_original.crop(bbox)
        image_crop.thumbnail(size_icon, Image.Resampling.LANCZOS)
        image_campus = Image.new("RGBA", size_icon, (255, 255, 255, 0))
        offset = [(dim_icon - dim_image) // 2 for dim_icon, dim_image in
                  zip(size_icon, image_crop.size)]
        offset = (width - image_crop.width) // 2, height - image_crop.height
        image_campus.paste(image_crop, offset)

        image_campus.save(path_image.parent / f"{path_image.stem}.png")
