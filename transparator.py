import wx
from PIL import Image, ImageChops, ImageOps, ImageSequence
import cv2
import numpy as np

import extra

HSV_SKIN = (12, 26, 249)
HSV_SKIN_KAMEHAME = (13, 75, 241)
HSV_SKIN_AMAZON_BITTER = (22, 132, 239)
HSV_SKIN_MARUZEN = (8, 47, 202)
HSV_CHEEK = (3, 47, 253)
AREA_LIMIT = 30000

COLORS_FACE = [HSV_SKIN, HSV_CHEEK, HSV_SKIN_KAMEHAME, HSV_SKIN_AMAZON_BITTER, HSV_SKIN_MARUZEN]


def get_mask_by_edge_cv(path_selected, dest, event, dial_pro):
    try:
        image_original = Image.open(path_selected)
        frames = []
        for frame in ImageSequence.Iterator(image_original):
            alpha = frame.convert("RGBA").split()[-1]
            nd_image = np.array(frame.convert("RGB"), np.uint8)
            nd_image = cv2.cvtColor(nd_image, cv2.COLOR_RGB2BGR)
            nd_gray = np.array(frame.convert("L"))
            retval, nd_thresh = cv2.threshold(nd_gray, 0, 255,
                                              cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
            cnts, _ = cv2.findContours(nd_thresh, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)

            cnts_face = []
            for cnt in cnts:
                m = cv2.moments(cnt)
                if m["m00"] >= AREA_LIMIT:
                    continue

                nd_cnt = nd_image.copy()
                mask_cnt = np.zeros_like(nd_thresh, np.uint8)
                cv2.drawContours(mask_cnt, [cnt], 0, 255, -1)
                mask_cnt = cv2.cvtColor(mask_cnt, cv2.COLOR_BGR2RGB)

                # チャンネルを合わせる必要がある。
                # 1チャンネルのマスクを使用したい場合は同じ画像を2つ与えてmaskにマスクを与える。
                # でもグレースケールでは動かないかも
                nd_cnt = cv2.bitwise_and(mask_cnt, nd_cnt)
                nd_cnt = cv2.cvtColor(nd_cnt, cv2.COLOR_BGR2HSV_FULL)
                # 色が薄いとhsvのカラーが消滅することがある？
                # 検出できなかった場合はスキップする。
                if not nd_cnt.any():
                    continue

                color_mode_hsv = get_color_mode(nd_cnt)
                if within_range_hsv(color_mode_hsv):
                    cnts_face.append(cnt)

            mask_face = np.zeros_like(nd_thresh, np.uint8)
            for cnt_face in cnts_face:
                cv2.drawContours(mask_face, [cnt_face], 0, 255, -1)

            mask_face = cv2.cvtColor(mask_face, cv2.COLOR_GRAY2BGR)
            mask_face = Image.fromarray(mask_face).convert("L")
            mask_face = ImageOps.invert(mask_face)
            mask_face = ImageChops.darker(mask_face, alpha)

            image_face = image_original.convert("RGBA")
            image_face.putalpha(mask_face)

            frames.append(image_face)

        extra.show_message(dest, "透過画像の作成が完了しました。", "作成完了")
        wx.PostEvent(dest, event(path_image=path_selected, frames=frames))

    except Exception as e:
        extra.show_message(dest, f"透過画像の作成に失敗しました。\n{e}", "透過画像作成エラー", wx.ICON_WARNING)

    finally:
        dial_pro.Destroy()


# 色の最頻値を求める
def get_color_mode(nd_image):
    nd_trans = [1000000, 1000, 1]
    nd_image = nd_image * nd_trans
    nd_image = nd_image.sum(axis=2)
    nd_image = nd_image.flatten()
    nd_image = nd_image[nd_image.nonzero()]

    uniques, counts = np.unique(nd_image, return_counts=True)
    color_mode = uniques[counts == np.amax(counts)].min()
    color_mode = [int(str(color_mode).zfill(9)[3 * i:(3 * (i + 1))]) for i in range(3)]
    return color_mode


def within_range_hsv(color_hsv):
    for color_face in COLORS_FACE:
        h, s, v = color_face
        color_low = (h - 2, s - 5, v - 10)
        color_high = (h + 2, s + 5, v + 10)
        lst_matched = []
        for c, cl, ch in zip(color_hsv, color_low, color_high):
            lst_matched.append(cl <= c <= ch)

        if all(lst_matched):
            return True

    return False
