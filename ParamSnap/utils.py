import bpy
import re
from bpy.app.translations import pgettext_iface as iface_
import json
from .property import types


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


def stored_kind_to_property_name(kind, ptr_kind=None):
    if kind == "POINTER":
        return {
            "Action": "stored_action_pointer",
            "Object": "stored_object_pointer",
            "Collection": "stored_collection_pointer",
        }.get(ptr_kind)
    return {
        "FLOAT": "stored_float",
        "INT": "stored_int",
        "BOOLEAN": "stored_bool",
        "STRING": "stored_string",
        "VEC2": "stored_vec2",
        "VEC3": "stored_vec3",
        "VEC4": "stored_vec4",
        "COLOR3": "stored_color3",
        "COLOR4": "stored_color4",
        "NONE": "",
    }.get(kind)


def get_value_and_type_from_path(path: str):
    ptr, prop_token, index = resolve_ui_path(path)
    if ptr is None:
        return None, None, {}
    val = None
    type = "UNDEFINED"
    meta = {}
    prop_rna = ptr.bl_rna.properties.get(prop_token)
    if prop_rna:
        meta["is_rna"] = "True"
        meta["rna_type"] = prop_rna.type
        meta["subtype"] = getattr(prop_rna, "subtype", None)
        meta["icon"] = getattr(prop_rna, "icon", "NONE")
        meta["array_length"] = int(getattr(prop_rna, "array_length", 0) or 0)
        val = getattr(ptr, prop_token, None)
        if meta["rna_type"] in types:
            type = meta["rna_type"]
            if meta["array_length"] == 1:
                type = "FLOAT"
            elif meta["array_length"] == 2:
                type = "VEC2"
            elif meta["array_length"] == 3:
                type = "VEC3"
            elif meta["array_length"] == 4:
                type = "VEC4"
            if meta["subtype"] == "COLOR":
                if meta["array_length"] == 3:
                    type = "COLOR3"
                elif meta["array_length"] == 4:
                    type = "COLOR4"
            if meta["rna_type"] == "POINTER":
                ft = getattr(prop_rna, "fixed_type", None)
                meta["fixed_type"] = getattr(ft, "identifier", None) or getattr(ft, "name", None)
        elif meta["rna_type"] == "ENUM":
            type = "STRING"
    else:
        meta["is_rna"] = "False"
        val = getattr(ptr, prop_token, None)
        if val:
            if isinstance(val, bpy.types.ID):
                type = "POINTER"
                meta["rna_type"] = "POINTER"
                if isinstance(val, bpy.types.Object):
                    meta["fixed_type"] = "Object"
                elif isinstance(val, bpy.types.Action):
                    meta["fixed_type"] = "Action"
                elif isinstance(val, bpy.types.Collection):
                    meta["fixed_type"] = "Collection"
                else:
                    meta["fixed_type"] = "UNKNOWN"
            elif isinstance(val, (list, tuple)):
                n = len(val)
                if n == 2:
                    type = "VEC2"
                elif n == 3:
                    type = "VEC3"
                elif n == 4:
                    type = "VEC4"
                else:
                    type = "UNDEFINED"
            elif isinstance(val, bool):
                type = "BOOLEAN"
            elif isinstance(val, int):
                type = "INT"
            elif isinstance(val, float):
                type = "FLOAT"
            elif isinstance(val, str):
                type = "STRING"
    # print("val type meta", val, type, meta)
    return val, type, meta


def assign_stored_from_value(item, val, type, meta):
    item.meta = json.dumps(meta)
    if type == "POINTER":
        item.stored_kind = "POINTER"
        item.stored_pointer_kind = meta["fixed_type"]
        if meta["fixed_type"] == "Object":
            item.stored_object_pointer = val
        elif meta["fixed_type"] == "Action":
            item.stored_action_pointer = val
        elif meta["fixed_type"] == "Collection":
            item.stored_collection_pointer = val
    elif type == "FLOAT":
        item.stored_kind = "FLOAT"
        item.stored_float = val
    elif type == "INT":
        item.stored_kind = "INT"
        item.stored_int = val
    elif type == "BOOLEAN":
        item.stored_kind = "BOOLEAN"
        item.stored_bool = val
    elif type == "STRING":
        item.stored_kind = "STRING"
        item.stored_string = val
    elif type == "VEC2":
        item.stored_kind = "VEC2"
        item.stored_vec2 = val
    elif type == "VEC3":
        item.stored_kind = "VEC3"
        item.stored_vec3 = val
    elif type == "VEC4":
        item.stored_kind = "VEC4"
        item.stored_vec4 = val
    elif type == "COLOR3":
        item.stored_kind = "COLOR3"
        item.stored_color3 = val
    elif type == "COLOR4":
        item.stored_kind = "COLOR4"
        item.stored_color4 = val


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
    ptr, prop_token, arr_index = resolve_ui_path(param_item.property_path)
    property_name = stored_kind_to_property_name(param_item.stored_kind, param_item.stored_pointer_kind)
    stored_val = getattr(param_item, property_name, None)
    if stored_val is not None or param_item.stored_kind == "POINTER":
        setattr(ptr, prop_token, stored_val)
        if param_item.stored_kind == "POINTER" and param_item.stored_pointer_kind == "Action":
            action = getattr(ptr, prop_token)
            slots = getattr(action, "slots", None)
            slot = None
            for s in slots:
                if s.name_display == param_item.stored_action_slots:
                    slot = s
            if slot:
                setattr(ptr, "action_slot", slot)
            else:
                return None
        return True
    return None


# 定义图标对
ICON_TOGGLES = {
    "CHECKBOX_HLT": ("CHECKBOX_HLT_OFF", "CHECKBOX_HLT_ON"),
    "HIDE": ("HIDE_OFF", "HIDE_ON"),
    "RESTRICT_VIEW": ("RESTRICT_VIEW_OFF", "RESTRICT_VIEW_ON"),
}


def get_toggle_icon(base_name, state):
    # 如果 base_name 在映射表里，根据布尔值返回对应的
    for key, pair in ICON_TOGGLES.items():
        if key in base_name:
            return pair[1] if state else pair[0]
    return base_name  # 找不到就返回原样
