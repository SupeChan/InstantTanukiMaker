import json
from PIL import Image
import numpy as np
import pathlib
from itertools import cycle
from collections import Iterator

import const
from image_manager import ImageManager, FrameImage, FileImage, PartsImage
import editor

TYPE = "_type"
VALUE = "value"
VERSION = "version"


class InstantEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, ImageManager):
            return obj.to_json()
        elif isinstance(obj, FrameImage):
            return obj.to_json()
        elif isinstance(obj, FileImage):
            value = self.convert_value(obj)
            return {TYPE: FileImage.__name__, VALUE: value}
        elif isinstance(obj, PartsImage):
            value = self.convert_value(obj)
            return {TYPE: PartsImage.__name__, VALUE: value}
        elif isinstance(obj, np.ndarray):
            return {TYPE: np.ndarray.__name__, VALUE: obj.tolist()}
        elif isinstance(obj, np.integer):
            return int(obj)
        elif isinstance(obj, np.floating):
            return float(obj)
        elif isinstance(obj, Image.Image):
            return {TYPE: Image.Image.__name__, VALUE: editor.encode_image(obj)}
        elif isinstance(obj, pathlib.Path):
            return None
        elif isinstance(obj, cycle):
            return None
        elif isinstance(obj, Iterator):
            return None
        else:
            return obj

    def convert_value(self, obj):
        value = {key: {TYPE: tuple.__name__, VALUE: val} if isinstance(val, tuple) else val
                 for key, val in obj.__dict__.items()}

        return value


class InstantDecoder(json.JSONDecoder):
    def __init__(self, *args, **kwargs):
        json.JSONDecoder.__init__(self, object_hook=self.object_hook, *args, **kwargs)

    def object_hook(self, obj):
        if TYPE not in obj:
            return obj

        type_obj = obj.get(TYPE)
        if type_obj == ImageManager.__name__:
            manager = ImageManager(**obj[VALUE])
            # id文字列からXXXImageのポインタに戻す
            manager.convert_id2img()
            return manager
        elif type_obj == FrameImage.__name__:
            return FrameImage(**obj[VALUE])
        elif type_obj == FileImage.__name__:
            return FileImage(**obj[VALUE])
        elif type_obj == PartsImage.__name__:
            return PartsImage(**obj[VALUE])
        elif type_obj == Image.Image.__name__:
            return editor.decode_image(obj[VALUE])
        elif type_obj == np.ndarray.__name__:
            return np.array(obj[VALUE])
        elif type_obj == tuple.__name__:
            return tuple(obj[VALUE])


class Config:
    def __init__(self):
        self.manager = ImageManager()
        self.dir_dialog = None

    def save_manager(self, path_save):
        with open(path_save, "w") as f:
            json.dump(self.manager, f, cls=InstantEncoder, ensure_ascii=False, indent=4)

    def load_manager(self, path_json):
        with open(path_json, "r") as f:
            dic_json = json.loads(f.read())

        is_target, message = self.check_json(dic_json)
        if not is_target:
            return False, message

        with open(path_json, "r") as f:
            manager = json.load(f, cls=InstantDecoder)

        self.manager = manager
        return True, "読込が完了しました！"

    def check_json(self, dic_json):
        is_project = dic_json.get(TYPE, None) == ImageManager.__name__
        if not is_project:
            return False, "たぬこらのプロジェクトファイルではありません！"

        # バージョンチェック
        version_json = dic_json[VALUE][VERSION]
        for v_json, v_app in zip(version_json.split("."), const.VERSION.split(".")):
            if int(v_json) > int(v_app):
                return False, ("プロジェクトファイルのバージョンが今のアプリより新しいため読み込めません！\n"
                               "たぬこらのバージョンをあげてみて下さい！")

        return True, "チェック完了"


CONFIG = Config()
