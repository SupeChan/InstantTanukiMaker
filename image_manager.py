from PIL import Image, ImageSequence, ImageOps, ImageFilter, UnidentifiedImageError
import numpy as np
from itertools import cycle
import wx
import pathlib
from dataclasses import dataclass, field

import const
import editor

import time


@dataclass
class PartsImage:
    id_file: str
    id_parts: str
    type_image: const.ImageType
    label: str
    image: Image.Image

    icon: Image.Image = None
    offset: np.ndarray = np.array([0, 0])
    offset_center: np.ndarray = None
    angle: int = 0
    zoom_x: float = 1.0
    zoom_y: float = 1.0
    transparency: int = 0
    anti_alias: bool = True
    is_flip: bool = False
    visible: bool = True
    mode_blend: const.BlendMode = const.BlendMode.NONE
    color_blend: tuple[int, int, int] = (255, 0, 0)
    alpha_blend: float = 0.3
    clippers_id: list = field(default_factory=list)
    image_edit: Image.Image = None
    layer: Image.Image = None

    def __post_init__(self):
        if self.offset_center is None:
            left, top, right, bottom = self.image.getbbox()
            width, height = self.image.size
            self.offset_center = np.array((left + (right - left) // 2 - width // 2,
                                           top + (bottom - top) // 2 - height // 2))
            self.image = self.image.crop(self.image.getbbox())

        if not self.icon:
            self.icon = editor.create_icon(self.image, const.ICON_SIZE, const.THUMB_SIZE,
                                           const.BG_PARTS)

        if not self.image_edit:
            self.edit_image()

    def edit_image(self):
        image_edit = self.image.convert("RGBA")
        image_edit = ImageOps.mirror(image_edit) if self.is_flip else image_edit
        size_zoom = (int(image_edit.width * self.zoom_x),
                     int(image_edit.height * self.zoom_y))

        image_edit = image_edit.resize(size_zoom, Image.LANCZOS)
        alpha = image_edit.split()[-1]
        mask = Image.eval(alpha, lambda a: np.clip(a - self.transparency, 0, 255))
        image_edit.putalpha(mask)
        image_edit = image_edit.rotate(self.angle, resample=Image.BICUBIC, expand=True)

        if self.mode_blend != const.BlendMode.NONE:
            image_edit = editor.blend_color(image_edit, self.color_blend,
                                            self.mode_blend, self.alpha_blend)

        self.image_edit = image_edit

    def create_layer(self, size_layer, offset_base):
        campus_layer = Image.new("RGBA", size_layer, (255, 255, 255, 0))
        offset = np.array(size_layer) // 2 - np.array(
            self.image_edit.size) // 2 + self.offset + self.offset_center
        if self.type_image not in const.TYPES_BASE:
            offset = offset + offset_base

        campus_layer.paste(self.image_edit, tuple(offset))
        return campus_layer

    def edit_layer(self, layer, clippers, color_selection):
        layer = editor.clip_by_images(layer, clippers)
        if color_selection:
            layer = editor.draw_selection_marker(layer, color_selection)

        self.layer = layer

    def overwrite_property(self, parts_replace, clippers_id=None):
        self.offset = parts_replace.offset
        self.angle = parts_replace.angle
        self.zoom_x = parts_replace.zoom_x
        self.zoom_y = parts_replace.zoom_y
        self.transparency = parts_replace.transparency
        self.anti_alias = parts_replace.anti_alias
        self.is_flip = parts_replace.is_flip
        self.visible = parts_replace.visible
        self.mode_blend = parts_replace.mode_blend
        self.color_blend = parts_replace.color_blend
        self.alpha_blend = parts_replace.alpha_blend
        self.clippers_id = parts_replace.clippers_id if clippers_id is None else clippers_id
        self.edit_image()

    def set_offset(self, offset):
        self.offset = offset

    def add_offset(self, offset_delta, size):
        limit_x, limit_y = size
        self.offset = self.offset + offset_delta
        offset_x, offset_y = self.offset
        self.offset = np.array([np.clip(offset_x, -limit_x, limit_x),
                                np.clip(offset_y, -limit_y, limit_y)])

    def set_angle(self, angle):
        self.angle = angle
        self.edit_image()

    def add_angle(self, angle_delta):
        self.angle = np.clip(self.angle + angle_delta, -360, 360)
        self.edit_image()

    def set_zoom(self, zoom_x, zoom_y):
        self.zoom_x = zoom_x
        self.zoom_y = zoom_y
        self.edit_image()

    def set_transparency(self, transparency):
        self.transparency = transparency
        self.edit_image()

    def set_alias(self, anti_alias):
        self.anti_alias = anti_alias

    def set_flip(self, is_flip):
        self.is_flip = is_flip
        self.edit_image()

    def set_blend_color(self, mode_blend, color_blend, alpha_blend):
        self.mode_blend = mode_blend
        self.color_blend = color_blend
        self.alpha_blend = alpha_blend
        self.edit_image()

    def add_clipper(self, id_parts):
        if id_parts not in self.clippers_id:
            self.clippers_id.append(id_parts)

    def remove_clipper(self, id_parts):
        if id_parts in self.clippers_id:
            self.clippers_id.remove(id_parts)

    def update_clipper(self, dic_update_parts):
        self.clippers_id = [dic_update_parts.get(id_clipper, id_clipper) for id_clipper in
                            self.clippers_id]
        self.clippers_id = list(filter(None, self.clippers_id))

    def collide(self, pos):
        x, y = pos
        width, height = self.image_edit.size
        if not (0 <= x < width and 0 <= y < height):
            return False

        alpha = self.image_edit.split()[-1]
        alpha_pixel = alpha.getpixel((x, y))

        return bool(alpha_pixel)

    def get_bmp_icon(self):
        bmp = wx.Bitmap.FromBufferRGBA(*self.icon.size, self.icon.tobytes())
        return bmp


@dataclass
class FileImage:
    id_file: str
    path_image: pathlib.Path
    frames: list = None
    cycle_image: cycle = None

    icon: Image.Image = None
    label: str = None
    type_image: const.ImageType = None
    size: np.ndarray = None
    number_frames: int = None

    offset: np.ndarray = np.array([0, 0])
    angle: int = 0
    zoom_x: float = 1.0
    zoom_y: float = 1.0
    transparency: int = 0
    anti_alias: bool = True
    is_flip: bool = False
    visible: bool = True
    mode_blend: const.BlendMode = const.BlendMode.NONE
    color_blend: tuple[int, int, int] = (255, 0, 0)
    alpha_blend: float = 0.3
    clippers_id: list = field(default_factory=list)

    def __post_init__(self):
        exists_frames = bool(self.frames)
        if not exists_frames:
            im = Image.open(self.path_image)
            self.frames = [frame.convert("RGBA") for frame in ImageSequence.Iterator(im)]

        if not self.icon:
            self.icon = editor.create_icon(self.frames[0], const.ICON_SIZE, const.THUMB_MINI_SIZE,
                                           const.BG_FILE,
                                           alignment="topleft")

        if self.label is None:
            self.label = self.path_image.stem

        if self.type_image is None:
            self.type_image = self.get_type(self.path_image, exists_frames)

        if self.size is None:
            self.size = np.array(self.frames[0].size)

        if self.number_frames is None:
            self.number_frames = len(self.frames)

    def get_type(self, path_image, frames):
        in_material = const.FOLDER_MATERIAL in path_image.parents
        in_append = const.FOLDER_APPEND in path_image.parents
        if not (in_material or in_append):
            return const.ImageType.ETC

        path_root = const.FOLDER_MATERIAL if in_material else const.FOLDER_APPEND
        for type_image in const.TYPES_IMAGE:
            if path_root / type_image in path_image.parents:
                if type_image == const.ImageType.BASE:
                    if path_image.parent.stem == const.ImageType.COLLAGE:
                        is_sep = any(map(lambda w: w in path_image.stem, const.KEYWORDS_SEPARATE))
                        return const.ImageType.ETC if is_sep else const.ImageType.COLLAGE

                    elif const.KEYWORD_TRANSPARENT in path_image.stem:
                        return const.ImageType.TRANSPARENT

                    else:
                        return const.ImageType.BASE

                else:
                    return const.ImageType.ETC if frames else type_image

        return const.ImageType.ETC

    def set_offset(self, offset):
        self.offset = offset

    def add_offset(self, offset_delta, size):
        limit_x, limit_y = size
        self.offset = self.offset + offset_delta
        offset_x, offset_y = self.offset
        self.offset = np.array([np.clip(offset_x, -limit_x, limit_x),
                                np.clip(offset_y, -limit_y, limit_y)])

    def set_angle(self, angle):
        self.angle = angle

    def add_angle(self, angle_delta):
        self.angle = np.clip(self.angle + angle_delta, -360, 360)

    def set_zoom(self, zoom_x, zoom_y):
        self.zoom_x = zoom_x
        self.zoom_y = zoom_y

    def set_transparency(self, transparency):
        self.transparency = transparency

    def set_alias(self, anti_alias):
        self.anti_alias = anti_alias

    def set_flip(self, is_flip):
        self.is_flip = is_flip

    def set_blend_color(self, mode_blend, color_blend, alpha_blend):
        self.mode_blend = mode_blend
        self.color_blend = color_blend
        self.alpha_blend = alpha_blend

    def add_clipper(self, id_file):
        if id_file not in self.clippers_id:
            self.clippers_id.append(id_file)

    def remove_clipper(self, id_file):
        if id_file in self.clippers_id:
            self.clippers_id.remove(id_file)

    def update_clipper(self, dic_update_file):
        self.clippers_id = [dic_update_file.get(id_clipper, id_clipper) for id_clipper in
                            self.clippers_id]
        self.clippers_id = list(filter(None, self.clippers_id))

    def overwrite_property(self, file_replace):
        self.offset = file_replace.offset
        self.angle = file_replace.angle
        self.zoom_x = file_replace.zoom_x
        self.zoom_y = file_replace.zoom_y
        self.transparency = file_replace.transparency
        self.anti_alias = file_replace.anti_alias
        self.is_flip = file_replace.is_flip
        self.visible = file_replace.visible
        self.mode_blend = file_replace.mode_blend
        self.color_blend = file_replace.color_blend
        self.alpha_blend = file_replace.alpha_blend
        self.clippers_id = file_replace.clippers_id.copy()

    # self.iconに直接bmpを与えたかったけどbmpはpickle化出来なかったので都度変換する。
    def get_bmp_icon(self):
        bmp = wx.Bitmap.FromBufferRGBA(*self.icon.size, self.icon.tobytes())
        return bmp

    def __iter__(self):
        self.cycle_image = cycle(self.frames)
        return self

    def __next__(self):
        return next(self.cycle_image)


@dataclass
class FrameImage:
    order_parts: list = field(default_factory=list)
    iter_frame: list = field(default_factory=list)

    def append(self, parts_append, id_file_replace=None):
        if not id_file_replace:
            self.order_parts.append(parts_append)
            return

        # 既に削除してしまって同じID_FILEがない場合スキップ
        lst_id_file = [parts.id_file for parts in self.order_parts]
        if id_file_replace not in lst_id_file:
            return

        ix_replace = lst_id_file.index(id_file_replace)
        parts_replace = self.order_parts[ix_replace]
        parts_append.overwrite_property(parts_replace)
        self.order_parts[ix_replace] = parts_append

    def replace_parts(self, parts, id_replace):
        lst_id_parts = [parts.id_parts for parts in self.order_parts]
        ix_replace = lst_id_parts.index(id_replace)
        self.order_parts[ix_replace] = parts

    def remove_by_id_file(self, id_file):
        lst_id_file = [parts.id_file for parts in self.order_parts]
        if id_file not in lst_id_file:
            return

        ix_remove = [parts.id_file for parts in self.order_parts].index(id_file)
        del self.order_parts[ix_remove]

    def remove_by_id_parts(self, id_parts):
        lst_id_parts = [parts.id_parts for parts in self.order_parts]
        if id_parts not in lst_id_parts:
            return

        ix_remove = lst_id_parts.index(id_parts)
        del self.order_parts[ix_remove]

    def sort_file(self, order_id_file):
        self.order_parts = sorted(self.order_parts, key=lambda p: order_id_file.index(p.id_file))

    def sort_parts(self, id_from, id_to):
        lst_id = [parts.id_parts for parts in self.order_parts]
        ix_from, ix_to = lst_id.index(id_from), lst_id.index(id_to)
        parts_insert = self.order_parts.pop(ix_from)
        self.order_parts.insert(ix_to, parts_insert)

    def composite_image(self, size, offset_base, selections=None, selected_file=False):
        color_marker = (0, 255, 0) if selected_file else (0, 0, 255)
        if selections is None:
            selections = []

        order_parts = self.order_parts.copy()
        if not any([parts.visible for parts in order_parts]):
            image_empty = Image.new("RGBA", size, (255, 255, 255, 0))
            return image_empty

        # レイヤーの作成
        dic_layer = {parts.id_parts: parts.create_layer(size, offset_base)
                     for parts in order_parts}
        for parts in order_parts:
            clippers = [dic_layer.get(id_clipper) for id_clipper in parts.clippers_id]
            color_selection = color_marker if parts.id_file in selections else None
            parts.edit_layer(dic_layer.get(parts.id_parts), clippers, color_selection)
            dic_layer[parts.id_parts] = parts.layer

        # 合成
        campus_frame = Image.new("RGBA", size, (255, 255, 255, 0))
        for parts in order_parts:
            if not parts.visible:
                continue

            campus_frame = Image.alpha_composite(campus_frame, parts.layer)

        # アンチエイリアス
        alpha_campus = campus_frame.split()[-1]
        campus_smooth = campus_frame.filter(ImageFilter.GaussianBlur(0.75))
        for parts in order_parts:
            if not parts.visible:
                continue

            if parts.anti_alias:
                campus_frame = editor.apply_anti_alias(campus_frame, campus_smooth, parts.layer)

            campus_frame = Image.alpha_composite(campus_frame, parts.layer)
            # クリッパーで切り取った部分にもアンチエイリアスを掛ける
            clippers = [parts_clipper for parts_clipper in order_parts if
                        parts_clipper.id_parts in parts.clippers_id]
            for parts_clipper in clippers:
                if parts_clipper.anti_alias:
                    campus_frame = editor.apply_anti_alias(campus_frame, campus_smooth,
                                                           parts_clipper.layer, parts.layer)

        campus_frame.putalpha(alpha_campus)
        return campus_frame

    def get_collide_image(self, pos):
        for parts in self.order_parts[::-1]:
            if not parts.visible:
                continue

            if editor.collide_point(parts.layer, pos):
                return parts

        return None

    def get_order_parts(self):
        return self.order_parts.copy()

    def get_order_parts_display(self):
        return self.order_parts[::-1].copy()

    def to_json(self):
        dic_frame = {"_type": FrameImage.__name__, "value": self.__dict__.copy()}
        dic_frame["value"]["order_parts"] = [parts.id_parts for parts in self.order_parts]
        return dic_frame

    def convert_id2img(self, dic_image):
        self.order_parts = [dic_image.get(id_parts) for id_parts in self.order_parts]

    def __iter__(self):
        self.iter_frame = iter(self.order_parts)
        return self

    def __next__(self):
        return next(self.iter_frame)


@dataclass
class ImageManager:
    version: str = const.VERSION
    dic_image: dict = field(default_factory=dict)
    order_frame: list = field(default_factory=lambda: [FrameImage()])
    order_file: dict = field(default_factory=dict)
    dic_file_children: dict = field(default_factory=dict)
    # selection
    ix_frame: int = 0
    selections: list = field(default_factory=list)
    id_selection_file: str = None
    selected_file: bool = True
    marked_selection: bool = False
    # property
    number_frames: int = 1
    size: tuple[int, int] = const.DEFAULT_SIZE
    duration_single: int = 100
    durations_multi: list = field(default_factory=lambda: [100])
    filter_color: const.ColorFilter = const.ColorFilter.NONE
    filter_image: const.ImageFilter = const.ImageFilter.NONE
    fixed_size: bool = False
    fixed_number_frames: bool = False
    # system
    offset_base: np.ndarray = const.OFFSET_FLAT
    id_file: int = 0
    id_parts: int = 0

    # デバッグ用
    def show_data(self):
        print("order_file", len(self.order_file))
        for file in self.order_file.values():
            print("  ", file.label)

        print("order_frame", len(self.order_frame))
        for frame in self.order_frame:
            print("  ", len(frame.order_parts), frame.order_parts)

        print("lst_parts")
        for lst_parts in self.dic_file_children.values():
            print("  ", len(lst_parts), lst_parts)

        print("dic_image", len(self.dic_image))
        for image in self.dic_image.values():
            print(image.label)

        print("selections", self.ix_frame, self.selections, self.is_selected())

    # 画像の追加
    def append(self, path_image, frames=None):
        file = self.create_file_image(path_image, frames)
        if not file:
            return False

        id_replace = self.get_id_replace(file.type_image)
        if id_replace:
            self.replace_file(file, id_replace)
        else:
            self.order_file[file.id_file] = file
            self.append_parts(file)

        id_image = (file.id_file if self.selected_file else
                    self.dic_file_children.get(file.id_file)[0].id_parts)
        self.select(None, id_image, False)
        self.set_offset_base()

        return True

    def append_parts(self, file, id_replace=None):
        for ix, (frame, im_parts) in enumerate(zip(self.order_frame, file)):
            label = f"【F{ix + 1}】{file.label}"
            parts = self.create_parts_image(file, im_parts, label)
            self.dic_file_children[file.id_file].append(parts)
            frame.append(parts, id_replace)

        self.adjust_system()

    # 画像の置換
    def replace(self, path_image, id_replace, frames=None):
        replaced_file = self.is_file(id_replace)
        file_new = self.create_file_image(path_image, frames, replaced_file)
        if not file_new:
            return False

        if replaced_file:
            self.replace_file(file_new, id_replace)
        else:
            self.replace_parts(file_new, id_replace)

        return True

    def replace_file(self, file_new, id_replace):
        file_old = self.dic_image.get(id_replace)
        lst_id_old = self.get_lst_clippers_id(id_replace)
        file_new.overwrite_property(file_old)

        # order_file
        files = list(self.order_file.values())
        ix_replace = [file.id_file for file in files].index(id_replace)
        files[ix_replace] = file_new
        self.order_file = {file.id_file: file for file in files}

        # dic_image
        del self.dic_image[id_replace]
        for parts in self.dic_file_children.get(id_replace):
            if parts:
                del self.dic_image[parts.id_parts]

        # dic_lst_parts
        del self.dic_file_children[id_replace]
        # selections
        if id_replace in self.selections:
            ix = self.selections.index(id_replace)
            self.selections[ix] = file_new.id_file

        self.append_parts(file_new, id_replace)

        lst_id_new = self.get_lst_clippers_id(file_new.id_file)
        dic_update_file = {id_replace: file_new.id_file}
        dic_update_parts = {id_old: id_new for id_old, id_new in zip(lst_id_old, lst_id_new)}
        self.update_clipper(dic_update_file, dic_update_parts)

    def replace_parts(self, file_new, id_replace):
        parts_old = self.dic_image.get(id_replace)
        file_replace = self.order_file.get(parts_old.id_file)
        ix_replace = self.get_ix_frame_by_id_parts(id_replace)
        im_parts = [im_parts for ix, im_parts in zip(range(ix_replace + 1), file_new)
                    if ix == ix_replace][0]
        label = f"【F{ix_replace + 1}】{file_replace.label}"
        parts_new = self.create_parts_image(file_replace, im_parts, label)
        parts_new.overwrite_property(parts_old)
        frame = self.order_frame[ix_replace]
        frame.replace_parts(parts_new, id_replace)
        self.dic_file_children.get(parts_old.id_file)[ix_replace] = parts_new
        del self.dic_image[id_replace]

        dic_update_parts = {parts_old.id_parts: parts_new.id_parts}
        self.update_clipper(None, dic_update_parts)
        self.select(ix_replace, parts_new.id_parts, False)

    # 画像の削除
    def remove(self, id_image):
        if self.is_file(id_image):
            self.remove_by_id_file(id_image)
        else:
            self.remove_by_id_parts(id_image)

        self.set_offset_base()

    def remove_by_id_file(self, id_file):
        lst_id_parts = [parts.id_parts for parts in self.dic_file_children.get(id_file) if parts]
        del self.order_file[id_file]
        del self.dic_file_children[id_file]
        del self.dic_image[id_file]
        for id_parts in lst_id_parts:
            del self.dic_image[id_parts]

        if id_file in self.selections:
            self.selections.remove(id_file)

        for frame in self.order_frame:
            frame.remove_by_id_file(id_file)

        dic_update_file = {id_file: None}
        dic_update_parts = {id_parts: None for id_parts in lst_id_parts}
        self.update_clipper(dic_update_file, dic_update_parts)

        self.adjust_system()

    def remove_by_id_parts(self, id_parts):
        parts = self.dic_image.get(id_parts)
        lst_parts = self.dic_file_children.get(parts.id_file)
        lst_parts[lst_parts.index(parts)] = None
        self.dic_file_children[parts.id_file] = lst_parts
        del self.dic_image[id_parts]
        for frame in self.order_frame:
            frame.remove_by_id_parts(id_parts)

        if parts.id_file in self.selections:
            self.selections.remove(parts.id_file)

        dic_update_parts = {id_parts: None}
        self.update_clipper(None, dic_update_parts)

    # クリッパー
    def add_clipper(self, id_target, id_clipper):
        image = self.dic_image.get(id_target)
        image.add_clipper(id_clipper)
        if self.is_parts(id_target):
            return

        children_target = self.dic_file_children.get(id_target)
        children_clipper = self.dic_file_children.get(id_clipper)
        for parts_target, parts_clipper in zip(children_target, children_clipper):
            if parts_target and parts_clipper:
                parts_target.add_clipper(parts_clipper.id_parts)

    def remove_clipper(self, id_target, id_clipper):
        image = self.dic_image.get(id_target)
        image.remove_clipper(id_clipper)
        if self.is_parts(id_target):
            return

        children_target = self.dic_file_children.get(id_target)
        children_clipper = self.dic_file_children.get(id_clipper)
        for parts_target, parts_clipper in zip(children_target, children_clipper):
            if parts_target and parts_clipper:
                parts_target.remove_clipper(parts_clipper.id_parts)

    # 画像の交換・削除に伴うクリッパーのid更新
    def update_clipper(self, dic_update_file, dic_update_parts):
        for file in list(self.order_file.values()):
            if dic_update_file:
                file.update_clipper(dic_update_file)

            for parts in list(self.dic_file_children.get(file.id_file)):
                if parts:
                    parts.update_clipper(dic_update_parts)

    # オールクリア　初期化
    def clear(self):
        # data
        self.order_file = {}
        self.order_frame = [FrameImage()]
        self.dic_file_children = {}
        self.dic_image = {}

        # selection
        self.ix_frame = 0
        self.selections = []
        self.selected_file = True
        self.marked_selection = False

        # property
        self.number_frames = 1
        self.size = const.DEFAULT_SIZE
        self.duration_single = 100
        self.durations_multi = [100]
        self.filter_color = const.ColorFilter.NONE
        self.filter_image = const.ImageFilter.NONE
        self.fixed_size = False
        self.fixed_number_frames = False

        # system
        self.offset_base = np.array([0, 0])
        self.id_file = 0
        self.id_parts = 0

    # フレーム・画像選択
    def shift_ix_frame(self, ix_delta):
        self.ix_frame = (self.ix_frame + ix_delta) % self.number_frames
        if self.ix_frame < 0:
            self.ix_frame = self.number_frames - 1

    def select(self, ix_frame, id_image, ctrl_down):
        if ix_frame is not None:
            self.ix_frame = ix_frame

        if id_image is not None:
            self.selected_file = self.is_file(id_image)
            image_select = self.dic_image.get(id_image, None)
            id_file = image_select.id_file

            if ctrl_down:
                if id_file in self.selections:
                    self.selections.remove(id_file)
                else:
                    self.selections.append(id_file)
            else:
                self.selections = [id_file]

    def select_by_pos(self, pos, ctrl_down):
        frame = self.order_frame[self.ix_frame]
        parts = frame.get_collide_image(pos)
        if not parts:
            return False

        id_file = parts.id_file
        if ctrl_down:
            if id_file in self.selections:
                self.selections.remove(id_file)
                return False
            else:
                self.selections.append(id_file)
        else:
            if id_file in self.selections:
                pass
            else:
                self.selections = [id_file]

        return id_file

    def get_image_by_pos(self, pos):
        frame = self.order_frame[self.ix_frame]
        parts = frame.get_collide_image(pos)

        if not parts:
            return None

        id_image = parts.id_file if self.selected_file else parts.id_parts
        return id_image

    def switch_selected_file(self, selected):
        self.selected_file = selected

    def is_selected(self):
        return any(self.selections)

    # データ取得
    def get_images_selection(self):
        return self.get_selection_file() if self.selected_file else self.get_selection_parts()

    def get_preview(self):
        frame = self.order_frame[self.ix_frame]
        # frame = self.order_frame[self.ix_frame]
        if self.marked_selection:
            im_preview = frame.composite_image(self.size, self.offset_base,
                                               self.selections, self.selected_file)
        else:
            im_preview = frame.composite_image(self.size, self.offset_base)

        if self.filter_image != const.ImageFilter.NONE:
            im_preview = editor.filtering_image(
                [im_preview], self.filter_image, self.number_frames, self.ix_frame)[0]

        if self.filter_color != const.ColorFilter.NONE:
            im_preview = editor.filtering_color(
                [im_preview], self.filter_color, self.number_frames, self.ix_frame)[0]

        image_chess = editor.create_chess_board(self.size, self.selected_file)
        im_preview = Image.alpha_composite(image_chess, im_preview)
        return im_preview

    def get_selection_file(self):
        files_selection = [self.order_file.get(id_file) for id_file in self.selections]
        return files_selection

    def get_selection_parts(self):
        if self.selected_file:
            parts_selection = []
            for id_file in self.selections:
                children = self.dic_file_children.get(id_file)
                children = [parts for parts in children if parts]
                parts_selection.extend(children)

            return parts_selection

        order_parts = self.order_frame[self.ix_frame].order_parts
        parts_selection = []
        for parts in order_parts:
            if parts.id_file in self.selections:
                parts_selection.append(parts)

        return parts_selection

    def get_selections_id(self):
        lst_id = []
        for selection in self.get_images_selection():
            id_image = selection.id_file if self.selected_file else selection.id_parts
            lst_id.append(id_image)

        return lst_id

    def get_ix_frame_by_id_parts(self, id_parts):
        parts = self.dic_image.get(id_parts)
        ix_frame = self.dic_file_children.get(parts.id_file).index(parts)
        return ix_frame

    def get_lst_clippers_id(self, id_clipper):
        if self.is_file(id_clipper):
            lst_clippers_id = [parts_new.id_parts
                               for parts_new in self.dic_file_children.get(id_clipper)]
        else:
            lst_clippers_id = [id_clipper]

        return lst_clippers_id

    def get_order_file_display(self):
        return list(self.order_file.values())[::-1]

    def get_order_parts_display(self, id_parts):
        ix_frame = self.get_ix_frame_by_id_parts(id_parts)
        frame = self.order_frame[ix_frame]
        order_parts = frame.get_order_parts()
        return order_parts[::-1]

    def get_order_frame(self):
        return self.order_frame

    def get_image(self, id_image):
        return self.dic_image.get(id_image)

    def is_file(self, id_image):
        return isinstance(self.get_image(id_image), FileImage)

    def is_parts(self, id_image):
        return isinstance(self.get_image(id_image), PartsImage)

    def can_marking(self):
        return self.filter_color == const.ColorFilter.NONE and self.filter_image == const.ImageFilter.NONE

    def switch_marking(self):
        if self.can_marking():
            self.marked_selection = not self.marked_selection

    # 画像プロパティ設定
    def set_offset(self, offset):
        if self.selected_file:
            for file in self.get_selection_file():
                file.set_offset(offset)

        for parts in self.get_selection_parts():
            parts.set_offset(offset)

    def add_offset(self, offset):
        if self.selected_file:
            for file in self.get_selection_file():
                file.add_offset(offset, self.size)

        for parts in self.get_selection_parts():
            parts.add_offset(offset, self.size)

    def set_angle(self, angle):
        if self.selected_file:
            for file in self.get_selection_file():
                file.set_angle(angle)

        for parts in self.get_selection_parts():
            parts.set_angle(angle)

    def add_angle(self, angle):
        if self.selected_file:
            for file in self.get_selection_file():
                file.add_angle(angle)

        for parts in self.get_selection_parts():
            parts.add_angle(angle)

    def set_zoom(self, zoom_x, zoom_y):
        if self.selected_file:
            for file in self.get_selection_file():
                file.set_zoom(zoom_x, zoom_y)

        for parts in self.get_selection_parts():
            parts.set_zoom(zoom_x, zoom_y)

    def set_transparency(self, transparency):
        if self.selected_file:
            for file in self.get_selection_file():
                file.set_transparency(transparency)

        for parts in self.get_selection_parts():
            parts.set_transparency(transparency)

    def set_alias(self, anti_alias):
        if self.selected_file:
            for file in self.get_selection_file():
                file.set_alias(anti_alias)

        for parts in self.get_selection_parts():
            parts.set_alias(anti_alias)

    def set_flip(self, is_flip):
        if self.selected_file:
            for file in self.get_selection_file():
                file.set_flip(is_flip)

        for parts in self.get_selection_parts():
            parts.set_flip(is_flip)

    def set_blend_color(self, mode_blend, color_blend, alpha_blend):
        if self.selected_file:
            for file in self.get_selection_file():
                file.set_blend_color(mode_blend, color_blend, alpha_blend)

        for parts in self.get_selection_parts():
            parts.set_blend_color(mode_blend, color_blend, alpha_blend)

    def set_file_visible(self, id_file, visible):
        file = self.order_file.get(id_file)
        file.visible = visible
        for parts in self.dic_file_children.get(id_file):
            if parts:
                parts.visible = visible

    def set_parts_visible(self, id_parts, visible):
        self.dic_image.get(id_parts).visible = visible

    def set_label(self, id_image, label):
        image = self.get_image(id_image)
        image.label = label
        if isinstance(image, PartsImage):
            return

        for ix, parts in enumerate(self.dic_file_children.get(id_image)):
            if parts:
                parts.label = f"【F{ix + 1}】{label}"

    # 合成プロパティ設定
    def fix_num_frames(self, fixed):
        self.fixed_number_frames = fixed
        if not fixed:
            self.change_number_frames(self.get_number_lcm())

    def change_number_frames(self, number_frames):
        if self.number_frames < number_frames:
            self.extend_frames(number_frames)
        elif self.number_frames > number_frames:
            self.reduce_frames(number_frames)

    def extend_frames(self, count_extend):
        for val in zip(range(count_extend), *self.order_file.values()):
            ix, lst_parts = val[0], val[1:]
            if self.number_frames > ix:
                continue

            # frame = self.order_frame.get(ix, FrameImage())
            frame = FrameImage()
            for im_parts, file in zip(lst_parts, self.order_file.values()):
                label = f"【F{ix + 1}】{file.label}"
                parts = self.create_parts_image(file, im_parts, label)
                clippers_id = [parts.id_parts for parts in frame.order_parts
                               if parts.id_file in file.clippers_id]
                parts.overwrite_property(file, clippers_id)
                frame.append(parts)
                self.dic_file_children[file.id_file].append(parts)

            self.order_frame.append(frame)
            self.durations_multi.append(self.duration_single)

        self.number_frames = count_extend

    def reduce_frames(self, count_reduce):
        for frame in self.order_frame[count_reduce:]:
            for parts in frame:
                if parts:
                    del self.dic_image[parts.id_parts]

        self.dic_file_children = {id_file: lst_parts[:count_reduce]
                                  for id_file, lst_parts in
                                  zip(list(self.dic_file_children.keys()),
                                      list(self.dic_file_children.values()))}

        self.order_frame = self.order_frame[:count_reduce]
        self.durations_multi = self.durations_multi[:count_reduce]
        self.number_frames = count_reduce
        if self.ix_frame >= self.number_frames:
            self.ix_frame = self.number_frames - 1

    def fix_size(self, fixed):
        self.fixed_size = fixed
        if not fixed:
            self.size = self.get_size_adjust()

    def change_size(self, size):
        self.size = size

    def set_duration_single(self, duration):
        self.duration_single = duration

    def set_duration_multi(self, durations):
        self.durations_multi = durations

    def set_filter(self, filter_color, filter_image):
        self.filter_color = filter_color
        self.filter_image = filter_image
        if not self.can_marking():
            self.marked_selection = False

    # ソート
    def sort_file(self, id_from, id_to):
        files = list(self.order_file.values())
        lst_id = [file.id_file for file in files]
        ix_from, ix_to = lst_id.index(id_from), lst_id.index(id_to)
        file_insert = files.pop(ix_from)
        files.insert(ix_to, file_insert)
        self.order_file = {file.id_file: file for file in files}
        # フレームもファイル順通りにソート
        order_id_file = list(self.order_file.keys())
        for frame in self.order_frame:
            frame.sort_file(order_id_file)

        self.set_offset_base()

    def sort_parts(self, num_frame, id_from, id_to):
        frame = self.order_frame[num_frame]
        frame.sort_parts(id_from, id_to)

    # 合成、保存
    def get_frames_composite(self):
        frames_composite = [frame.composite_image(self.size, self.offset_base) for frame in
                            self.order_frame]

        if self.filter_image != const.ImageFilter.NONE:
            frames_composite = editor.filtering_image(frames_composite, self.filter_image)

        if self.filter_color != const.ColorFilter.NONE:
            frames_composite = editor.filtering_color(frames_composite, self.filter_color)

        return frames_composite

    def save_preview(self, is_single):
        frames_composite = self.get_frames_composite()
        image_chess = editor.create_chess_board(self.size, self.selected_file)
        frames_composite = [Image.alpha_composite(image_chess, frame) for frame in frames_composite]
        duration = self.duration_single if is_single else self.durations_multi
        editor.save_gif(const.PATH_GIF_PREVIEW, frames_composite, duration)

    def save_gif(self, path_save, is_single):
        frames_composite = self.get_frames_composite()
        duration = self.duration_single if is_single else self.durations_multi
        editor.save_gif(path_save, frames_composite, duration)

    def save_png_sequence(self, folder_save):
        frames_composite = self.get_frames_composite()
        editor.save_png_sequence(folder_save, frames_composite)

    def save_apng(self, path_save, is_single):
        frames_composite = self.get_frames_composite()
        duration = self.duration_single if is_single else self.durations_multi
        editor.save_apng(path_save, frames_composite, duration)

    def can_save(self):
        return any(
            [parts.visible for frame in self.order_frame for parts in
             frame.order_parts])

    # システム用
    def set_offset_base(self):
        for file in list(self.order_file.values()):
            if file.type_image in const.TYPES_BASE:
                for key in list(const.DIC_BASE_OFFSET.keys()):
                    if key in file.label:
                        self.offset_base = const.DIC_BASE_OFFSET.get(key)
                        break
                else:
                    self.offset_base = const.OFFSET_FLAT

    def adjust_system(self):
        # サイズ調整
        if not self.fixed_size:
            self.size = self.get_size_adjust()

        # フレーム拡張

        if not self.fixed_number_frames:
            number_lcm = self.get_number_lcm()
            self.change_number_frames(number_lcm)

    def get_size_adjust(self):
        lst_width, lst_height = [], []
        for file in list(self.order_file.values()):
            width, height = file.size
            lst_width.append(width)
            lst_height.append(height)

        width, height = ((max(lst_width), max(lst_height)) if lst_width and lst_height else
                         const.DEFAULT_SIZE)

        size_adjust = (np.clip(width, const.MIN_WIDTH, const.MAX_WIDTH),
                       np.clip(height, const.MIN_HEIGHT, const.MAX_HEIGHT))
        return size_adjust

    def get_number_lcm(self):
        lst_count = list(set([file.number_frames for file in list(self.order_file.values())]))
        return np.lcm.reduce(lst_count) if lst_count else 1

    def get_id_replace(self, type_image):
        if type_image not in const.TYPES_REPLACE:
            return None

        lst_id = [file.id_file for file in list(self.order_file.values()) if
                  file.type_image == type_image]
        id_replace = lst_id[0] if lst_id else None
        return id_replace

    def create_file_image(self, path_image, frames, is_append=True):
        id_file = self.issue_id_file()
        try:
            file = FileImage(id_file, path_image, frames)

        except (UnidentifiedImageError, FileNotFoundError, PermissionError):
            return False

        if is_append:
            self.dic_file_children[file.id_file] = []
            self.dic_image[file.id_file] = file

        return file

    def create_parts_image(self, file, im_parts, label):
        id_parts = self.issue_id_parts()
        parts = PartsImage(file.id_file, id_parts, file.type_image, label, im_parts)
        self.dic_image[id_parts] = parts
        return parts

    def issue_id_file(self):
        id_issue = f"ID_FILE_{self.id_file}"
        self.id_file += 1
        return id_issue

    def issue_id_parts(self):
        id_issue = f"ID_PARTS_{self.id_parts}"
        self.id_parts += 1
        return id_issue

    def to_json(self):
        dic_manager = {"_type": ImageManager.__name__, "value": self.__dict__.copy()}
        dic_manager["value"]["order_file"] = {file.id_file: file.id_file for file in
                                              self.order_file.values()}
        dic_manager["value"]["dic_file_children"] = {
            id_file: [parts.id_parts if parts else None for parts in children]
            for id_file, children in
            zip(self.dic_file_children.keys(),
                self.dic_file_children.values())}

        return dic_manager

    def convert_id2img(self):
        self.order_file = {id_file: self.dic_image.get(id_file) for id_file in self.order_file}
        self.dic_file_children = {id_file: [self.dic_image.get(id_parts) for id_parts in children]
                                  for id_file, children in
                                  zip(list(self.dic_file_children.keys()),
                                      list(self.dic_file_children.values()))}

        for frame in self.order_frame:
            frame.convert_id2img(self.dic_image)
