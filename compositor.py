from PIL import Image, ImageSequence
from dataclasses import dataclass
import pathlib
from itertools import cycle
from config import *
import numpy as np


@dataclass
class BaseImage:
    type_image: str
    path_image: pathlib.Path

    def __post_init__(self):
        self.image = Image.open(self.path_image)
        self.frames = self.create_frames()
        self.iter_frames = None

    def create_frames(self):
        frames = []
        if self.image.is_animated:
            for frame in ImageSequence.Iterator(self.image):
                frame_rgba = frame.convert("RGBA")
                frames.append(frame_rgba)
        else:
            image_rgba = self.image.convert("RGBA")
            frames.append(image_rgba)

        return frames

    def get_size(self):
        return self.image.size

    def get_count_frames(self):
        return len(self.frames)

    def __iter__(self):
        self.iter_frames = iter(self.frames)
        return self

    def __next__(self):
        return next(self.iter_frames)


@dataclass
class PartsImage:
    type_image: str
    path_image: pathlib.Path
    offset_x: int
    offset_y: int
    angle: int
    rate_zoom: float
    need_aligned: bool
    count_frames: int

    def __post_init__(self):
        self.image = Image.open(self.path_image)
        self.frames = self.create_frames()
        self.iter_frames = None

    def create_frames(self):
        frames = []
        lst_alignment = DIC_ALIGNMENT.get(self.type_image, ALIGNMENT_FLAT * self.count_frames)

        frames_cycle = (cycle([frame.copy() for frame in ImageSequence.Iterator(self.image)])
                        if self.image.is_animated else
                        cycle([self.image.copy()]))

        for frame, (offset, angle) in zip(frames_cycle, lst_alignment):
            frame_rgba = frame.convert("RGBA")
            if self.need_aligned:
                frame_crop = frame_rgba.crop(frame_rgba.getbbox())
                frame_crop = frame_crop.crop()
                frame_processed = self.process_image(frame_crop, offset, angle)
            else:
                frame_processed = self.process_image(frame_rgba)

            frames.append(frame_processed)

        return frames

    def process_image(self, image, offset_frame=(0, 0), angle_frame=0):
        size_zoom = [int(s * self.rate_zoom) for s in image.size]
        angle = self.angle + angle_frame
        image_zoom = image.resize(size_zoom, Image.LANCZOS)
        image_rotate = image_zoom.rotate(angle, resample=Image.BICUBIC, expand=True)

        if self.need_aligned:
            offset_x = self.offset_x + offset_frame[0] - int(image_rotate.width / 2)
            offset_y = self.offset_y + offset_frame[1] - int(image_rotate.height / 2)
        else:
            offset_x = self.offset_x
            offset_y = self.offset_y

        width = np.clip(image_rotate.size[0] + offset_x, 0, None)
        height = np.clip(image_rotate.size[1] + offset_y, 0, None)
        size_frame = (width, height)

        image_frame = Image.new("RGBA", size_frame, (255, 255, 255, 0))
        image_frame.paste(image_rotate, (offset_x, offset_y))

        return image_frame

    def __iter__(self):
        self.iter_frames = iter(self.frames)
        return self

    def __next__(self):
        return next(self.iter_frames)


@dataclass
class CompositeImage:
    path_base: pathlib.Path
    lst_parts: list
    duration: int
    order_composite: list

    def __post_init__(self):
        type_image_base = BASE
        if not self.path_base:
            type_image_base = self.lst_parts[0][0]
            self.path_base = self.lst_parts[0][1]
            self.lst_parts = self.lst_parts[1:]

        self.image_base = BaseImage(type_image_base, self.path_base)
        count_frames = self.image_base.get_count_frames()
        self.lst_image_parts = [PartsImage(*record, count_frames) for record in self.lst_parts]
        dic_order = {type_image: ix for ix, type_image in enumerate(self.order_composite)}
        self.lst_image_composite = [self.image_base] + self.lst_image_parts
        self.lst_image_composite.sort(key=lambda image: dic_order.get(image.type_image, 0))

    def save_png(self):
        size_base = self.image_base.get_size()
        frames = [next(iter(image)) for image in self.lst_image_composite]
        image_campus = Image.new("RGBA", size_base, (255, 255, 255, 0))
        for frame in frames:
            image_clear = Image.new("RGBA", image_campus.size, (255, 255, 255, 0))
            image_clear.paste(frame)
            image_campus = Image.alpha_composite(image_campus, image_clear)

        alpha = image_campus.split()[-1]
        image_campus = image_campus.convert("RGB").convert("P", palette=Image.ADAPTIVE,
                                                           colors=255)
        mask = Image.eval(alpha, lambda a: 255 if a <= 128 else 0)
        image_campus.paste(255, mask=mask)
        image_campus.save(PATH_GIF_PREVIEW, transparency=255)

    def save_gif(self, path_save=PATH_GIF_PREVIEW):
        size_base = self.image_base.get_size()
        frames_composite = []

        for frames in zip(*self.lst_image_composite):
            image_campus = Image.new("RGBA", size_base, (255, 255, 255, 0))
            for frame in frames:
                image_clear = Image.new("RGBA", image_campus.size, (255, 255, 255, 0))
                image_clear.paste(frame)
                image_campus = Image.alpha_composite(image_campus, image_clear)

            alpha = image_campus.split()[-1]
            image_campus = image_campus.convert("RGB").convert("P", palette=Image.ADAPTIVE,
                                                               colors=255)
            mask = Image.eval(alpha, lambda a: 255 if a <= 128 else 0)
            image_campus.paste(255, mask=mask)
            frames_composite.append(image_campus)

        frames_composite[0].save(path_save, save_all=True, append_images=frames_composite[1:],
                                 optimize=False, loop=0, duration=self.duration, transparency=255,
                                 disposal=2)

    def get_name_save(self):
        lst_path = [self.path_base] + [args[1] for args in self.lst_parts]
        lst_path = [path for path in lst_path if path]

        name_save = ("".join(
            [path_selected.stem for path_selected in lst_path]) + f"{self.duration}ms.gif")

        return name_save
