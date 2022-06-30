import wx
from PIL import Image, ImageSequence, ImageFilter, ImageOps, ImageDraw, ImageChops
from dataclasses import dataclass
import pathlib
from itertools import cycle
from collections import OrderedDict
from config import *
import numpy as np


class PartsImage:
    def __init__(self, path_image, size_base, count_frames, offsets_tanuki, frames):
        self.path_image = path_image
        self.is_base = (self.path_image.parent == FOLDER_MATERIAL / TRANSPARENT
                        or self.path_image.parent.parent == FOLDER_BASE)
        self.visible = True
        self.size = (0, 0)
        self.size_base = size_base
        self.count_frames = count_frames
        self.offsets = [(0, 0)] * self.count_frames
        self.angles = [0] * self.count_frames
        self.zoom = 1.0
        self.anti_alias = True
        self.is_flip = False
        self.alignment = None
        self.color_multiply = None
        self.has_costume = False

        self.offsets_tanuki = offsets_tanuki if not self.is_base else [(0, 0)] * self.count_frames
        self.is_animated = None if not frames else len(frames) > 1
        self.frames_origin = self.load_frames() if not frames else frames
        self.frames_processed = self.create_frames()
        self.frames_mask = self.get_frames_mask()
        self.iter_frames = None

    def get_type(self):
        if self.path_image.parent.stem in TYPES_IMAGE_REPLACE:
            return self.path_image.parent.stem

        elif self.path_image.parent.parent.stem in TYPES_IMAGE_REPLACE:
            return self.path_image.parent.parent.stem

        else:
            return ETC

    def load_frames(self):
        image = Image.open(self.path_image)
        self.size = image.size
        self.is_animated = image.is_animated
        frames = [frame.convert("RGBA") for frame in ImageSequence.Iterator(image)]
        return frames

    def create_frames(self):
        aligmnents = DIC_ALIGNMENT.get(self.alignment, ALIGNMENT_FLAT * self.count_frames)
        offsets_alignment = cycle([alignment[0] for alignment in aligmnents])
        angles_alignment = cycle([alignment[1] for alignment in aligmnents])

        offsets = [(xt + x + xa, yt + y + ya) for (xt, yt), (x, y), (xa, ya) in
                   zip(self.offsets_tanuki, self.offsets, offsets_alignment)]

        angles = [a + ad for a, ad in zip(self.angles, angles_alignment)]
        frames_cycle = (cycle(self.frames_origin) if not (self.is_base and self.has_costume) else
                        cycle(self.clip_face_for_costume()))

        frames_processed = []
        for frame, offset, angle in zip(frames_cycle, offsets, angles):
            frame_processed = self.process_image(frame, offset, angle)
            if self.color_multiply:
                frame_processed = self.multiply_color(frame_processed)

            frames_processed.append(frame_processed)

        return frames_processed

    def process_image(self, image, offset, angle):
        image = image.crop(image.getbbox()) if self.alignment else image
        image = image.transpose(Image.FLIP_LEFT_RIGHT) if self.is_flip else image
        size_zoom = [int(self.zoom * dim) for dim in image.size]
        image = image.resize(size_zoom, Image.LANCZOS)
        image = image.rotate(angle, resample=Image.BICUBIC, expand=True)

        width_base, height_base = self.size_base
        center_x, center_y = [width_base // 2 - image.width // 2,
                              height_base // 2 - image.height // 2]
        offset_x, offset_y = (offset[0] + center_x, offset[1] + center_y)

        image_frame = Image.new("RGBA", self.size_base, (255, 255, 255, 0))
        image_frame.paste(image, (offset_x, offset_y))

        return image_frame

    def clip_face_for_costume(self):
        for key in DIC_TANUKI_OFFSET.keys():
            if key in self.path_image.stem:
                x_tanuki, y_tanuki = DIC_TANUKI_OFFSET.get(key, OFFSET_FLAT)[0]
                break

        else:
            x_tanuki, y_tanuki = OFFSET_FLAT[0]

        images_face = []
        for im_face, mask in zip(self.frames_origin, self.frames_mask):
            im_face = im_face.copy()
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
                offset_adjust = (mask.width // 2 - im_face.width // 2 - x_tanuki,
                                 mask.height // 2 - im_face.height // 2 - y_tanuki)
                campus = Image.new("RGBA", mask.size, (0, 0, 0, 255))
                campus.paste(im_face, offset_adjust)
                im_face = campus

            images_face.append(im_face)

        return images_face

    def multiply_color(self, image):
        alpha = image.split()[-1]
        color_mask = Image.new("RGBA", image.size, self.color_multiply)
        image_multiply = ImageChops.multiply(image, color_mask)
        image_multiply.putalpha(alpha)
        return image_multiply

    def set_properties(self, ix_frame, offset, angle, zoom, anti_alias, is_flip, alignment,
                       color_multiply):
        self.offsets[ix_frame] = offset
        self.angles[ix_frame] = angle
        self.zoom = zoom
        self.anti_alias = anti_alias
        self.is_flip = is_flip
        self.alignment = alignment
        self.color_multiply = color_multiply

        self.frames_processed = self.create_frames()

    def get_properties(self):
        properties = {"offset": self.offsets, "angle": self.angles, "zoom": self.zoom,
                      "anti_alias": self.anti_alias, "is_flip": self.is_flip,
                      "alignment": self.alignment,
                      "color_multiply": self.color_multiply}
        return properties

    def change_base_composite(self, size_base, count_frames, offsets_tanuki, has_costume):
        lst_changed = [not self.size_base == size_base,
                       not self.count_frames == count_frames,
                       not self.offsets_tanuki == offsets_tanuki,
                       not self.has_costume == has_costume]

        if not any(lst_changed):
            return

        self.size_base = size_base
        delta_frames = count_frames - self.count_frames
        self.offsets = (self.offsets[:count_frames] if delta_frames <= 0
                        else self.offsets + (OFFSET_FLAT * delta_frames))
        self.angles = (self.angles[:count_frames] if delta_frames <= 0
                       else self.angles + (ANGLE_FLAT * delta_frames))
        self.count_frames = count_frames

        self.offsets_tanuki = (offsets_tanuki if not self.is_base and not has_costume
                               else [(0, 0)] * self.count_frames)

        self.has_costume = has_costume
        self.frames_processed = self.create_frames()

    def get_frame(self, ix):
        return self.frames_processed[ix]

    def get_frames_mask(self):
        frames_mask = [im.convert("RGBA").split()[-1] for im in
                       ImageSequence.Iterator(Image.open(PATH_MASK_FACE))] if self.is_base else []
        return frames_mask

    def __iter__(self):
        self.iter_frames = iter(self.frames_processed)
        return self

    def __next__(self):
        return next(self.iter_frames)


class CompositeImage:
    def __init__(self):
        self.od_parts = OrderedDict()
        self.ids_visible = []
        self.filter_image = None
        self.filter_color = None
        self.count_frames = 1
        self.duration = 100
        self.size_base = DEFAULT_BASE_SIZE
        self.size_specify = None
        self.count_frames_specify = None
        self.count_id_issued = 0
        self.offsets_tanuki = [(0, 0)] * self.count_frames
        self.dic_func_filter_image = {FILTER_IMAGE_CONTOUR: self.filtering_image_line,
                                      FILTER_IMAGE_DOT: self.filtering_image_dot,
                                      FILTER_IMAGE_FANCY: self.filtering_image_fancy}

        self.dic_func_filter_color = {FILTER_COLOR_GAMING: self.filtering_color_gaming,
                                      FILTER_COLOR_MONOCHROME: self.filtering_color_monochrome,
                                      FILTER_COLOR_INVERT: self.filtering_color_invert}

    def issue_id(self):
        id_image = f"ID_{self.count_id_issued}"
        self.count_id_issued += 1
        return id_image

    def append(self, path_image, frames):
        image_append = PartsImage(path_image, self.size_base, self.count_frames,
                                  self.offsets_tanuki, frames)
        type_append = image_append.get_type()
        id_append = None
        if type_append in TYPES_IMAGE_REPLACE:
            for id_parts, image_parts in zip(self.od_parts.keys(), self.od_parts.values()):
                if type_append == image_parts.get_type():
                    id_append = id_parts

        id_append = id_append if id_append else self.issue_id()
        self.od_parts[id_append] = image_append

        self.ids_visible.append(id_append)
        self.change_size_base()
        return id_append, self.count_frames, image_append.is_animated

    def remove(self, id_image):
        if id_image not in self.od_parts.keys():
            return False

        del self.od_parts[id_image]
        if id_image in self.ids_visible:
            self.ids_visible.remove(id_image)

        self.change_size_base()
        return self.count_frames

    def clear(self):
        self.od_parts = OrderedDict()
        self.ids_visible = []
        self.change_size_base()

    def sort(self, order_id):
        self.od_parts = OrderedDict(
            sorted(self.od_parts.items(), key=lambda x: order_id.index(x[0])))

        self.change_size_base()

    def set_visible(self, ids_visible):
        self.ids_visible = ids_visible
        self.change_size_base()

    def set_properties(self, id_image, ix_frame, offset, angle, zoom, anti_alias, is_flip,
                       alignment, color_multiply):
        image_parts = self.od_parts.get(id_image, False)
        if not image_parts:
            return

        image_parts.set_properties(ix_frame, offset, angle, zoom, anti_alias, is_flip,
                                   alignment, color_multiply)

    def set_params(self, size_specify, count_frames_specify, filter_image, filter_color, duration):
        self.size_specify = size_specify
        self.count_frames_specify = count_frames_specify
        self.filter_image = filter_image
        self.filter_color = filter_color
        self.duration = duration
        self.change_size_base()

    def get_properties(self, id_image):
        image_parts = self.od_parts.get(id_image, False)
        properties = image_parts.get_properties()
        return properties

    def change_size_base(self):
        size_change, count_frames_change, stem_base = self.get_params_from_images()
        self.size_base = self.size_specify if self.size_specify else size_change
        self.count_frames = self.count_frames_specify if self.count_frames_specify else count_frames_change

        if self.has_costume():
            self.offsets_tanuki = OFFSET_FLAT * self.count_frames

        else:
            for key in DIC_TANUKI_OFFSET.keys():
                if key in stem_base:
                    self.offsets_tanuki = DIC_TANUKI_OFFSET.get(key,
                                                                OFFSET_FLAT) * self.count_frames
                    break

            else:
                self.offsets_tanuki = OFFSET_FLAT * self.count_frames

        for image_parts in self.od_parts.values():
            image_parts.change_base_composite(self.size_base, self.count_frames,
                                              self.offsets_tanuki, self.has_costume())

    def composite_frame(self, num_frame):
        images_visible = self.get_images_visible()
        frames = [image.frames_processed[num_frame] for image in images_visible]
        show_background = True
        image_campus = self.composite_image(frames, num_frame, show_background)
        return image_campus

    def save_gif(self, path_save=PATH_GIF_PREVIEW, show_background=True):
        images_visible = self.get_images_visible()
        frames_composite = []
        for num_frame, frames in enumerate(zip(*images_visible)):
            image_campus = self.composite_image(frames, num_frame, show_background)
            # gif作成のための下処理
            alpha = image_campus.split()[-1]

            # 減色処理
            image_campus = image_campus.convert("RGB").quantize(method=Image.MEDIANCUT,
                                                                kmeans=100).convert("RGB")
            # 最端の画素が黒だと背景と同化してしまう。
            # そうすると透過されて表示上端が欠けてしまうので(0,0,0)から(1,1,1)色を置換する。
            black = (0, 0, 0)
            black_replace = (1, 1, 1)
            r, g, b = image_campus.split()
            r = r.point(lambda x: 1 if x == black[0] else 0, mode="1")
            g = g.point(lambda x: 1 if x == black[1] else 0, mode="1")
            b = b.point(lambda x: 1 if x == black[2] else 0, mode="1")
            mask = ImageChops.logical_and(r, g)
            mask = ImageChops.logical_and(mask, b)
            image_campus.paste(Image.new("RGB", image_campus.size, black_replace), mask=mask)

            image_composite = image_campus.convert("RGB").convert("P", palette=Image.ADAPTIVE,
                                                                  colors=255)

            mask = Image.eval(alpha, lambda a: 255 if a <= 100 else 0)
            image_composite.paste(255, mask=mask)

            frames_composite.append(image_composite)

        frames_composite[0].save(path_save, save_all=True, append_images=frames_composite[1:],
                                 optimize=False, loop=0, duration=self.duration, transparency=255,
                                 disposal=2)

    def composite_image(self, frames, num_frame, show_background):
        if not frames:
            return self.create_chess_board()

        lst_anti_alias = self.get_lst_has_anti_alias()
        has_anti_alias = any(lst_anti_alias)
        image_campus = Image.new("RGBA", self.size_base, (255, 255, 255, 0))
        frames_unified = []
        for frame, anti_alias in zip(frames, lst_anti_alias):
            frame_unified = Image.new("RGBA", image_campus.size, (255, 255, 255, 0))
            frame_unified.paste(frame)
            image_campus = Image.alpha_composite(image_campus, frame_unified)
            frames_unified.append(frame_unified)

        alpha_original = image_campus.split()[-1]
        if has_anti_alias:
            image_smooth = image_campus.filter(ImageFilter.GaussianBlur(0.75))
            image_campus = Image.new("RGBA", self.size_base, (255, 255, 255, 0))
            for frame, anti_alias in zip(frames_unified, lst_anti_alias):
                if anti_alias:
                    alpha = frame.split()[-1]
                    mask_edge = (alpha.filter(ImageFilter.FIND_EDGES).convert("L")
                                 .filter(ImageFilter.GaussianBlur(0.75)))
                    mask_edge = Image.eval(mask_edge, lambda a: 255 if a > 48 else 0)
                    image_smooth.putalpha(mask_edge)
                    image_campus = Image.alpha_composite(image_campus, image_smooth)

                image_campus = Image.alpha_composite(image_campus, frame)

        image_campus.putalpha(alpha_original)

        func_filter_image = self.dic_func_filter_image.get(self.filter_image, False)
        if func_filter_image:
            image_campus = func_filter_image(image_campus)

        func_filter_color = self.dic_func_filter_color.get(self.filter_color, False)
        if func_filter_color:
            image_campus = func_filter_color(image_campus, num_frame)

        if show_background:
            image_chess = self.create_chess_board()
            image_campus = Image.alpha_composite(image_chess, image_campus)

        return image_campus

    def filtering_image_line(self, image):
        alpha = image.split()[-1]
        image_line = image.filter(ImageFilter.CONTOUR).convert("L").convert("RGBA")
        image_line = image_line.filter(ImageFilter.SMOOTH_MORE)
        image_line.putalpha(alpha)

        return image_line

    # 何も選択していない画像にコンバートしたalphaをputalphaするとWX側でエラーを吐く
    def filtering_image_dot(self, image):
        dot_level = 3
        alpha = image.split()[-1]

        image = image.convert("RGB").convert("P", palette=Image.ADAPTIVE, colors=64)
        image = (image.resize([x // dot_level for x in image.size], Image.LINEAR)
                 .resize(image.size, Image.LINEAR))
        alpha = alpha.convert("RGB").convert("P", palette=Image.ADAPTIVE, colors=64)
        alpha = (alpha.resize([x // dot_level for x in alpha.size], Image.LINEAR)
                 .resize(alpha.size, Image.LINEAR))
        alpha = Image.eval(alpha.convert("L"), lambda x: 255 if x > 0 else 0)

        image = image.convert("RGBA")
        image.putalpha(alpha)
        return image

    def filtering_image_fancy(self, image):
        level_fancy = 5
        alpha = image.split()[-1]

        image_fancy = image.copy()
        # maxfilterによって輪郭が黒く表示されるよう背景を黒くする。
        image_fancy.paste(Image.new("RGBA", image_fancy.size, (0, 0, 0, 0)), ImageOps.invert(alpha))

        image_fancy = image_fancy.filter(ImageFilter.MaxFilter(level_fancy))
        image_fancy = image_fancy.filter(ImageFilter.GaussianBlur(1))
        image_fancy.putalpha(alpha)
        return image_fancy

    def filtering_color_gaming(self, image, num_frame):
        hue_hsv = [int(i * 255 / (self.count_frames + 1))
                   for i in range(self.count_frames)][num_frame]
        image = image.convert("RGBA")
        alpha = image.split()[-1]
        color_mask = Image.new("HSV", image.size, (hue_hsv, 255, 255)).convert("RGBA")
        image_gaming = Image.blend(image, color_mask, 0.3)
        image_gaming.putalpha(alpha)
        return image_gaming

    def filtering_color_monochrome(self, image, num_frame):
        image_mono = image.convert("LA").convert("RGBA")
        return image_mono

    def filtering_color_invert(self, image, num_frame):
        image_rgb = image.convert("RGB")
        alpha = image.convert("RGBA").split()[-1]
        image_invert = ImageOps.invert(image_rgb).convert("RGBA")
        image_invert.putalpha(alpha)
        return image_invert

    def create_chess_board(self):
        width, height = self.size_base
        tile_white = np.array([200] * 100).reshape(10, 10)
        tile_gray = np.array([128] * 100).reshape(10, 10)

        tile = np.block([[tile_white, tile_gray],
                         [tile_gray, tile_white]])
        w, h = tile.shape
        rep_width, rep_height = -(-width // w), -(-height // h)
        board = np.tile(tile, (rep_height, rep_width))
        image_board = Image.fromarray(board).convert("RGBA").crop((0, 0, *self.size_base))
        return image_board

    def has_composite_image(self):
        return any(self.get_images_visible())

    def get_images_visible(self):
        images_visible = [image_parts
                          for id_image, image_parts in
                          zip(self.od_parts.keys(), self.od_parts.values())
                          if id_image in self.ids_visible]
        return images_visible

    def get_lst_has_anti_alias(self):
        return [parts.anti_alias for parts in self.od_parts.values()]

    def has_costume(self):
        return COSTUME in [image_parts.get_type() for image_parts in self.od_parts.values()]

    def get_params_from_images(self):
        stem_base = ""
        size_change = DEFAULT_BASE_SIZE
        count_frames_change = 1
        for image_parts in self.od_parts.values():
            size_parts = image_parts.size
            count_frames_parts = len(image_parts.frames_origin)

            if image_parts.is_base:
                size_change = size_parts
                count_frames_change = count_frames_parts
                stem_base = image_parts.path_image.stem
                break

            size_change = size_parts if size_parts > size_change else size_change
            count_frames_change = (count_frames_parts if count_frames_parts > count_frames_change
                                   else count_frames_change)

        return size_change, count_frames_change, stem_base
