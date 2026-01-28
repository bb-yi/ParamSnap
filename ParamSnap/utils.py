import bpy
import re
from bpy.app.translations import pgettext_iface as iface_
import json


def translations(text):
    return bpy.app.translations.pgettext(text)


_RE_END_INT_INDEX = re.compile(r"\[(\d+)\]$")  # [0]
_RE_END_IDPROP = re.compile(r'\[(?:"[^"]*"|\'[^\']*\')\]$')  # ["Socket_3"] / ['Socket_3']


def resolve_ui_path(path: str):
    """
    安全解析 UI 数据路径。
    失败时返回 (None, None, -1)
    """
    path = path.strip()
    if not path:
        return None, None, -1

    index = -1

    try:
        # 1) 剥末尾 [数字]（RNA数组分量）
        m = _RE_END_INT_INDEX.search(path)
        if m:
            index = int(m.group(1))
            path = path[: m.start()]

        # 2) IDProperty：["key"]
        m = _RE_END_IDPROP.search(path)
        if m:
            prop_token = path[m.start() :]  # '["Socket_3"]'
            obj_expr = path[: m.start()]  # 前半对象

            ptr = eval(obj_expr)
            if ptr is None:
                return None, None, -1

            # 检查 key 是否存在
            key = prop_token[2:-2]
            if key not in ptr.keys():
                return None, None, -1

            return ptr, prop_token, -1

        # 3) 普通 RNA
        if "." not in path:
            return None, None, -1

        obj_expr, prop_name = path.rsplit(".", 1)
        ptr = eval(obj_expr)

        if ptr is None:
            return None, None, -1

        # 属性不存在
        if not hasattr(ptr, "bl_rna") or prop_name not in ptr.bl_rna.properties:
            return None, None, -1

        # 如果是数组分量，检查索引有效
        if index != -1:
            prop = ptr.bl_rna.properties[prop_name]
            if not getattr(prop, "is_array", False):
                return None, None, -1
            if index >= getattr(prop, "array_length", 0):
                return None, None, -1

        return ptr, prop_name, index

    except Exception:
        return None, None, -1


def get_value_and_type_from_path(path: str):
    ptr, prop_token, index = resolve_ui_path(path)
    if ptr is None:
        return None, None, {}

    meta = {}

    # -------- IDProperty --------
    if prop_token.startswith(('["', "['")):
        key = prop_token[2:-2]
        v = ptr.get(key)

        try:
            ui = ptr.id_properties_ui(key).as_dict()
            meta.update(ui)
        except:
            pass

        meta["source"] = "IDPROP"

        if isinstance(v, (list, tuple)):
            return list(v), "ARRAY", meta
        return v, "SCALAR", meta

    # -------- RNA --------
    rna = ptr.bl_rna.properties[prop_token]
    meta.update(
        {
            "source": "RNA",
            "rna_type": rna.type,
            "subtype": getattr(rna, "subtype", None),
            "is_array": getattr(rna, "is_array", False),
            "array_length": getattr(rna, "array_length", 0),
            "hard_min": getattr(rna, "hard_min", None),
            "hard_max": getattr(rna, "hard_max", None),
            "soft_min": getattr(rna, "soft_min", None),
            "soft_max": getattr(rna, "soft_max", None),
            "step": getattr(rna, "step", None),
            "precision": getattr(rna, "precision", None),
            "unit": getattr(rna, "unit", None),
        }
    )

    v = getattr(ptr, prop_token)

    if index != -1:
        return v[index], "SCALAR", meta

    if meta["is_array"]:
        return list(v), "ARRAY", meta

    return v, rna.type, meta


def assign_stored_from_value(item, val, rna_type, meta):
    item.stored_json = json.dumps(meta or {}, ensure_ascii=False)

    # ENUM
    if rna_type == "ENUM":
        item.stored_kind = "ENUM"
        item.stored_enum = str(val)
        return

    # 颜色
    if meta.get("subtype") == "COLOR" and isinstance(val, (list, tuple)):
        item.stored_kind = "COLOR4" if len(val) >= 4 else "COLOR3"
        getattr(item, f"stored_color{len(val[:4])}")[:] = val[:4]
        return

    # 向量 / 数组
    if isinstance(val, (list, tuple)):
        n = len(val)
        if n == 2:
            item.stored_kind = "VEC2"
            item.stored_vec2 = val
        elif n == 3:
            item.stored_kind = "VEC3"
            item.stored_vec3 = val
        elif n == 4:
            item.stored_kind = "VEC4"
            item.stored_vec4 = val
        else:
            item.stored_kind = "IDPROP"
        return

    # 标量
    if isinstance(val, bool):
        item.stored_kind = "BOOL"
        item.stored_bool = val
        return
    if isinstance(val, int):
        item.stored_kind = "INT"
        item.stored_int = val
        return
    if isinstance(val, float):
        item.stored_kind = "FLOAT"
        item.stored_float = val
        return
    if isinstance(val, str):
        item.stored_kind = "STRING"
        item.stored_string = val
        return

    item.stored_kind = "IDPROP"


def get_ui_name_from_path(path: str) -> str:
    ptr, prop_token, index = resolve_ui_path(path)

    # ---- ① NodeSocket（inputs[x] / outputs[x] 被解析成 socket 指针）----
    # 你的 resolve_ui_path 如果对 inputs[1].default_value 这种返回的是 socket 对象，这里就会命中
    if hasattr(ptr, "name") and hasattr(ptr, "bl_rna"):
        # 尽量只把 NodeSocket 当成 socket（避免误伤别的有 name 的 RNA 对象）
        type_name = getattr(ptr.bl_rna, "identifier", "")
        if "NodeSocket" in type_name:
            return iface_(ptr.name)

    # ---- ② IDProperty（如 modifiers["GeometryNodes"]["Socket_3"]）----
    if (prop_token.startswith('["') and prop_token.endswith('"]')) or (prop_token.startswith("['") and prop_token.endswith("']")):
        key = prop_token[2:-2]

        # 有些 IDProp 会带 UI 元数据（min/max/subtype/name/description）
        try:
            ui_dict = ptr.id_properties_ui(key).as_dict()
        except Exception:
            ui_dict = None

        if ui_dict:
            # Blender 的 UI 元信息里常见的是 description；部分场景可能有 name
            label = ui_dict.get("name") or ui_dict.get("description") or key
            # 尝试翻译（如果 label 本身就是中文或没有翻译条目，iface_ 会原样返回）
            return iface_(label)

        return key

    # ---- ③ 普通 RNA 属性（如 cycles.samples）----
    if hasattr(ptr, "bl_rna") and prop_token in ptr.bl_rna.properties:
        rna = ptr.bl_rna.properties[prop_token]
        # 用 translation_context 才能对齐 Blender UI 的翻译
        ctx = getattr(rna, "translation_context", None)
        try:
            return iface_(rna.name, ctx)
        except TypeError:
            # 某些版本/类型 ctx 可能不兼容，兜底
            return iface_(rna.name)

    # ---- ④ 兜底：至少翻译一下 token 本身（多数不会有条目）----
    return iface_(prop_token)


def apply_stored_to_target(param_item):
    """
    将 ParamItem 里 stored_* 的值写回到 param_item.property_path 指向的属性。
    依赖你的 resolve_ui_path(path) 返回 (ptr, prop_token, index)
    """
    ptr, prop_token, arr_index = resolve_ui_path(param_item.property_path)
    if ptr is None or prop_token is None or arr_index is None:
        return None

    kind = param_item.stored_kind

    # -------- A) IDProperty：prop_token 是 '["Socket_3"]' / "['Socket_3']" --------
    if (prop_token.startswith('["') and prop_token.endswith('"]')) or (prop_token.startswith("['") and prop_token.endswith("']")):
        key = prop_token[2:-2]

        if kind == "FLOAT":
            ptr[key] = float(param_item.stored_float)
        elif kind == "INT":
            ptr[key] = int(param_item.stored_int)
        elif kind == "BOOL":
            ptr[key] = bool(param_item.stored_bool)
        elif kind == "STRING":
            ptr[key] = str(param_item.stored_string)
        elif kind == "ENUM":
            # IDProperty 没有“枚举”类型，通常就是字符串
            ptr[key] = str(param_item.stored_enum)
        elif kind in {"VEC2", "VEC3", "VEC4"}:
            vec = getattr(param_item, f"stored_{kind.lower()}")  # stored_vec2/3/4
            ptr[key] = list(vec)
        elif kind in {"COLOR3", "COLOR4"}:
            col = param_item.stored_color3 if kind == "COLOR3" else param_item.stored_color4
            ptr[key] = list(col)
        else:
            # 兜底：不建议 eval json 写回，这里先不做
            raise ValueError(f"Unsupported stored_kind for IDProperty: {kind}")

        return True

    # -------- B) RNA 属性 --------
    if not (hasattr(ptr, "bl_rna") and prop_token in ptr.bl_rna.properties):
        raise ValueError(f"Not an RNA property: {prop_token}")

    rna = ptr.bl_rna.properties[prop_token]

    # 1) ENUM
    if kind == "ENUM" or rna.type == "ENUM":
        # Blender 枚举值是 identifier 字符串
        setattr(ptr, prop_token, str(param_item.stored_enum))
        return True

    # 2) 标量
    if kind == "FLOAT":
        if arr_index != -1 and getattr(rna, "is_array", False):
            arr = ptr.path_resolve(prop_token)
            arr[arr_index] = float(param_item.stored_float)
        else:
            setattr(ptr, prop_token, float(param_item.stored_float))
        return True

    if kind == "INT":
        if arr_index != -1 and getattr(rna, "is_array", False):
            arr = ptr.path_resolve(prop_token)
            arr[arr_index] = int(param_item.stored_int)
        else:
            setattr(ptr, prop_token, int(param_item.stored_int))
        return True

    if kind == "BOOL":
        if arr_index != -1 and getattr(rna, "is_array", False):
            arr = ptr.path_resolve(prop_token)
            arr[arr_index] = bool(param_item.stored_bool)
        else:
            setattr(ptr, prop_token, bool(param_item.stored_bool))
        return True

    if kind == "STRING":
        setattr(ptr, prop_token, str(param_item.stored_string))
        return True

    # 3) 向量 / 数组 / 颜色（整体写回）
    if kind in {"VEC2", "VEC3", "VEC4"}:
        vec = getattr(param_item, f"stored_{kind.lower()}")  # stored_vec2/3/4
        setattr(ptr, prop_token, list(vec))
        return True

    if kind in {"COLOR3", "COLOR4"}:
        col = param_item.stored_color3 if kind == "COLOR3" else param_item.stored_color4
        setattr(ptr, prop_token, list(col))
        return True
    if kind == "POINTER":
        if param_item.stored_pointer_kind == "Action":
            setattr(ptr, prop_token, param_item.stored_action_pointer)
        elif param_item.stored_pointer_kind == "Camera":
            cam_obj = next((obj for obj in bpy.data.objects if obj.type == "CAMERA" and obj.data == param_item.stored_camera_pointer), None)
            if cam_obj is not None:
                setattr(ptr, prop_token, cam_obj)
        else:
            setattr(ptr, prop_token, None)
        return True

    raise ValueError(f"Unsupported stored_kind: {kind}")
