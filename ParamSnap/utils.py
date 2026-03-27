import bpy
import re
from bpy.app.translations import pgettext_iface as iface_
import json
from .property import types


_RE_END_INT_INDEX = re.compile(r"\[(\d+)\]$")  # [0]
_RE_END_IDPROP = re.compile(r'\[(?:"[^"]*"|\'[^\']*\')\]$')  # ["Socket_3"] / ['Socket_3']
_RE_SAFE_PATH_BASE = re.compile(r"^bpy\.(?:data|context)")
_RE_SAFE_PATH_TOKEN = re.compile(r'\.[A-Za-z_][A-Za-z0-9_]*|\[(?:\d+|"(?:[^"\\]|\\.)*"|\'(?:[^\'\\]|\\.)*\')\]')
_SAFE_SERIALIZED_PATH_RE = re.compile(r'^bpy\.(?:data|context)(?:\.[A-Za-z_][A-Za-z0-9_]*|\[(?:\d+|"(?:[^"\\]|\\.)*"|\'(?:[^\'\\]|\\.)*\')\])+$')

SERIALIZATION_FORMAT = "ParamSnap"
SERIALIZATION_VERSION = 1

_POINTER_COLLECTIONS = {
    "Action": "actions",
    "Object": "objects",
    "Collection": "collections",
}

_VECTOR_SIZES = {
    "VEC2": 2,
    "VEC3": 3,
    "VEC4": 4,
    "COLOR3": 3,
    "COLOR4": 4,
}

_SERIALIZABLE_KINDS = {"FLOAT", "INT", "BOOLEAN", "STRING", "VEC2", "VEC3", "VEC4", "COLOR3", "COLOR4", "POINTER", "NONE"}


def _safe_meta_loads(raw_meta):
    try:
        meta = json.loads(raw_meta or "{}")
    except Exception:
        meta = {}
    return meta if isinstance(meta, dict) else {}


def is_serialized_property_path_safe(path: str) -> bool:
    if not isinstance(path, str):
        return False
    return bool(_SAFE_SERIALIZED_PATH_RE.fullmatch(path.strip()))


def _get_pointer_collection(pointer_kind):
    collection_name = _POINTER_COLLECTIONS.get(pointer_kind)
    return getattr(bpy.data, collection_name, None) if collection_name else None


def _serialize_pointer_value(pointer_value):
    if pointer_value is None:
        return None
    return {"name": pointer_value.name}


def _serialize_basic_value(value):
    if hasattr(value, "__len__") and not isinstance(value, (str, bytes, bytearray)):
        return list(value)
    return value


def resolve_id_data_path(path: str):
    path = (path or "").strip()
    if not path or not is_serialized_property_path_safe(path):
        return None
    try:
        id_block = eval(path)
    except Exception:
        return None
    return id_block if isinstance(id_block, bpy.types.ID) else None


def id_to_bpy_data_path(id_block):
    if not isinstance(id_block, bpy.types.ID):
        return None
    name = id_block.name.replace('"', '\\"')
    try:
        ptr = id_block.as_pointer()
    except Exception:
        ptr = None
    for attr in dir(bpy.data):
        collection = getattr(bpy.data, attr, None)
        if collection is None or not hasattr(collection, "get"):
            continue
        try:
            item = collection.get(id_block.name)
        except Exception:
            continue
        if not item:
            continue
        try:
            if ptr is None or item.as_pointer() == ptr:
                return f'bpy.data.{attr}["{name}"]'
        except Exception:
            return f'bpy.data.{attr}["{name}"]'
    return None


def _can_store_target_pointer(id_block):
    if not isinstance(id_block, bpy.types.ID):
        return False
    return bool(id_to_bpy_data_path(id_block))


def _set_param_target_pointer(param_item, root_id):
    pointer_value = root_id if _can_store_target_pointer(root_id) else None
    try:
        param_item.target_id_pointer = pointer_value
    except Exception:
        try:
            param_item.target_id_pointer = None
        except Exception:
            pass
        return False
    return pointer_value is not None


def _extract_storable_root_reference(path: str):
    path = (path or "").strip()
    if not is_serialized_property_path_safe(path):
        return None, "", ""

    base_match = _RE_SAFE_PATH_BASE.match(path)
    if not base_match:
        return None, "", ""

    prefix = base_match.group(0)
    best_expr = ""
    best_id = None
    best_path = ""

    for match in _RE_SAFE_PATH_TOKEN.finditer(path, pos=base_match.end()):
        prefix += match.group(0)
        try:
            value = eval(prefix)
        except Exception:
            continue
        if not isinstance(value, bpy.types.ID):
            continue

        value_path = id_to_bpy_data_path(value) or ""
        if not value_path:
            continue

        best_expr = prefix
        best_id = value
        best_path = value_path

    if best_id is None:
        return None, "", ""

    relative_path = path[len(best_expr) :]
    if relative_path.startswith("."):
        relative_path = relative_path[1:]
    return best_id, best_path, relative_path


def _join_id_and_relative_path(root_path, relative_path):
    root_path = (root_path or "").strip()
    relative_path = (relative_path or "").strip()
    if not root_path:
        return ""
    if not relative_path:
        return root_path
    if relative_path.startswith("["):
        return root_path + relative_path
    return root_path + "." + relative_path


def extract_param_target_reference(path: str):
    ptr, prop_token, index = resolve_ui_path(path)
    if ptr is None:
        return None, "", ""

    root_id, root_path, relative_path = _extract_storable_root_reference(path)
    if root_id is not None and relative_path:
        return root_id, root_path, relative_path

    root_id = getattr(ptr, "id_data", None)
    if not isinstance(root_id, bpy.types.ID):
        return None, "", ""

    root_path = id_to_bpy_data_path(root_id) or ""
    normalized_path = (path or "").strip()
    relative_path = ""

    if root_path and normalized_path.startswith(root_path):
        relative_path = normalized_path[len(root_path) :]
        if relative_path.startswith("."):
            relative_path = relative_path[1:]

    if not relative_path:
        try:
            if prop_token and ((prop_token.startswith('["') and prop_token.endswith('"]')) or (prop_token.startswith("['") and prop_token.endswith("']"))):
                base_relative = ptr.path_from_id()
                relative_path = f"{base_relative}{prop_token}" if base_relative else prop_token
            else:
                relative_path = ptr.path_from_id(prop_token)
                if index != -1:
                    relative_path += f"[{index}]"
        except Exception:
            relative_path = ""

    return root_id, root_path, relative_path


def clear_param_target_reference(param_item):
    _set_param_target_pointer(param_item, None)
    param_item.target_id_path = ""
    param_item.target_relative_path = ""


def rebuild_param_target_reference(param_item, full_path=None):
    full_path = (full_path if full_path is not None else getattr(param_item, "property_path", "")) or ""
    root_id, root_path, relative_path = extract_param_target_reference(full_path)
    if not relative_path:
        clear_param_target_reference(param_item)
        return False

    param_item.target_id_path = root_path
    param_item.target_relative_path = relative_path
    _set_param_target_pointer(param_item, root_id)
    return True


def build_param_target_path(param_item, mutate=True):
    relative_path = (getattr(param_item, "target_relative_path", "") or "").strip()
    if not relative_path:
        return ""

    root_id = getattr(param_item, "target_id_pointer", None)
    root_path = ""
    if isinstance(root_id, bpy.types.ID):
        root_path = id_to_bpy_data_path(root_id) or ""
        if root_path and mutate:
            param_item.target_id_path = root_path
    if not root_path:
        stored_root_path = (getattr(param_item, "target_id_path", "") or "").strip()
        root_id = resolve_id_data_path(stored_root_path)
        if root_id is not None:
            if mutate:
                _set_param_target_pointer(param_item, root_id)
            root_path = id_to_bpy_data_path(root_id) or stored_root_path
            if mutate:
                param_item.target_id_path = root_path
        else:
            root_path = stored_root_path

    candidate_path = _join_id_and_relative_path(root_path, relative_path)
    if candidate_path and is_serialized_property_path_safe(candidate_path):
        return candidate_path
    return ""


def get_param_effective_path(param_item, mutate=True):
    current_path = build_param_target_path(param_item, mutate=mutate)
    if current_path:
        return current_path
    return (getattr(param_item, "property_path", "") or "").strip()


def resolve_param_item_path(param_item, mutate=True):
    candidate_paths = []
    current_path = build_param_target_path(param_item, mutate=mutate)
    if current_path:
        candidate_paths.append(current_path)

    legacy_path = (getattr(param_item, "property_path", "") or "").strip()
    if legacy_path and legacy_path not in candidate_paths:
        candidate_paths.append(legacy_path)

    for path in candidate_paths:
        ptr, prop_token, index = resolve_ui_path(path)
        if ptr is not None:
            has_target_reference = bool(getattr(param_item, "target_relative_path", "") and (getattr(param_item, "target_id_pointer", None) is not None or getattr(param_item, "target_id_path", "")))
            if mutate and not has_target_reference:
                rebuild_param_target_reference(param_item, path)
            return ptr, prop_token, index, path
    return None, None, -1, candidate_paths[0] if candidate_paths else ""


def get_value_and_type_from_param_item(param_item, mutate=True):
    ptr, prop_token, index, resolved_path = resolve_param_item_path(param_item, mutate=mutate)
    if ptr is None:
        return None, None, {}, resolved_path
    return *get_value_and_type_from_path(resolved_path), resolved_path


def build_action_slot_path(param_item, mutate=True):
    resolved_path = get_param_effective_path(param_item, mutate=mutate)
    if "." not in resolved_path:
        return ""
    return resolved_path.rsplit(".", 1)[0] + ".action_slot"


def get_param_target_signature(param_item):
    relative_path = (getattr(param_item, "target_relative_path", "") or "").strip()
    root_id = getattr(param_item, "target_id_pointer", None)
    if relative_path and isinstance(root_id, bpy.types.ID):
        try:
            root_sig = root_id.as_pointer()
        except Exception:
            root_sig = id_to_bpy_data_path(root_id) or getattr(param_item, "target_id_path", "")
        return (root_sig, relative_path)
    if relative_path:
        stored_root_path = (getattr(param_item, "target_id_path", "") or "").strip()
        if stored_root_path:
            return (stored_root_path, relative_path)
    return (None, get_param_effective_path(param_item))


def get_target_signature_from_path(path):
    root_id, root_path, relative_path = extract_param_target_reference(path)
    if relative_path and isinstance(root_id, bpy.types.ID):
        try:
            root_sig = root_id.as_pointer()
        except Exception:
            root_sig = root_path
        return (root_sig, relative_path)
    return (None, (path or "").strip())


def param_targets_match(param_item, path):
    return get_param_target_signature(param_item) == get_target_signature_from_path(path)


def is_ui_path_resolvable(path):
    path = (path or "").strip()
    if not path:
        return False
    ptr, prop_token, index = resolve_ui_path(path)
    return ptr is not None and prop_token is not None


def get_param_path_state(param_item):
    property_path = (getattr(param_item, "property_path", "") or "").strip()
    stable_path = build_param_target_path(param_item, mutate=False)

    property_valid = is_ui_path_resolvable(property_path)
    stable_valid = is_ui_path_resolvable(stable_path)

    property_signature = get_target_signature_from_path(property_path) if property_path else None
    stable_signature = get_target_signature_from_path(stable_path) if stable_path else None

    has_path_mismatch = bool(property_path and stable_path and property_path != stable_path)
    same_target = bool(property_path and stable_path and property_signature == stable_signature)
    has_conflict = bool(has_path_mismatch and not same_target)

    recommended_mode = "NONE"
    if has_conflict:
        if stable_valid and not property_valid:
            recommended_mode = "STABLE"
        elif property_valid and not stable_valid:
            recommended_mode = "PROPERTY"

    return {
        "property_path": property_path,
        "stable_path": stable_path,
        "property_valid": property_valid,
        "stable_valid": stable_valid,
        "property_signature": property_signature,
        "stable_signature": stable_signature,
        "has_path_mismatch": has_path_mismatch,
        "same_target": same_target,
        "has_conflict": has_conflict,
        "recommended_mode": recommended_mode,
    }


def serialize_param_item(param_item):
    effective_path = get_param_effective_path(param_item) or param_item.property_path
    value = get_param_stored_val(param_item)
    if param_item.stored_kind == "POINTER":
        value = _serialize_pointer_value(value)
    else:
        value = _serialize_basic_value(value)

    return {
        "enable": bool(param_item.enable),
        "name": param_item.name,
        "property_path": effective_path,
        "target_id_path": getattr(param_item, "target_id_path", ""),
        "target_relative_path": getattr(param_item, "target_relative_path", ""),
        "stored_kind": param_item.stored_kind,
        "stored_pointer_kind": param_item.stored_pointer_kind,
        "stored_action_slots": param_item.stored_action_slots,
        "meta": _safe_meta_loads(param_item.meta),
        "value": value,
    }


def serialize_snapshot_item(snapshot_item):
    return {
        "name": snapshot_item.name,
        "params": [serialize_param_item(param_item) for param_item in snapshot_item.Param_properties_coll],
    }


def build_snapshot_export_payload(snapshot_item):
    return {
        "format": SERIALIZATION_FORMAT,
        "version": SERIALIZATION_VERSION,
        "snapshots": [serialize_snapshot_item(snapshot_item)],
    }


def extract_snapshot_payloads(payload):
    if isinstance(payload, dict):
        if payload.get("format") == SERIALIZATION_FORMAT:
            snapshots = payload.get("snapshots")
            if isinstance(snapshots, list):
                return snapshots
            snapshot = payload.get("snapshot")
            if isinstance(snapshot, dict):
                return [snapshot]
        if "params" in payload:
            return [payload]
    elif isinstance(payload, list):
        return payload
    raise ValueError("Invalid ParamSnap JSON payload")


def _coerce_serialized_value(kind, value):
    if kind == "FLOAT":
        return float(value if value is not None else 0.0)
    if kind == "INT":
        return int(value if value is not None else 0)
    if kind == "BOOLEAN":
        return bool(value)
    if kind == "STRING":
        return "" if value is None else str(value)
    if kind in _VECTOR_SIZES:
        size = _VECTOR_SIZES[kind]
        values = list(value) if isinstance(value, (list, tuple)) else []
        values = values[:size] + [0.0] * max(0, size - len(values))
        return tuple(float(v) for v in values)
    return value


def _resolve_serialized_pointer(pointer_kind, value):
    if value is None:
        return None
    if isinstance(value, dict):
        pointer_name = value.get("name", "")
    else:
        pointer_name = str(value)
    collection = _get_pointer_collection(pointer_kind)
    if collection is None or not pointer_name:
        return None
    return collection.get(pointer_name)


def apply_serialized_param_item(param_item, param_data):
    if not isinstance(param_data, dict):
        raise ValueError("Invalid parameter payload")

    property_path = param_data.get("property_path", "")
    if not is_serialized_property_path_safe(property_path):
        raise ValueError(f"Unsafe property path: {property_path}")

    stored_kind = param_data.get("stored_kind", "NONE")
    if stored_kind not in types or stored_kind not in _SERIALIZABLE_KINDS:
        stored_kind = "NONE"

    stored_pointer_kind = param_data.get("stored_pointer_kind", "NONE")
    if stored_pointer_kind not in _POINTER_COLLECTIONS and stored_pointer_kind != "NONE":
        stored_pointer_kind = "NONE"

    meta = param_data.get("meta", {})
    if not isinstance(meta, dict):
        meta = {}

    param_item.enable = bool(param_data.get("enable", True))
    param_item.name = str(param_data.get("name") or "Parameter")
    param_item.property_path = property_path
    target_id_path = str(param_data.get("target_id_path", "") or "")
    target_relative_path = str(param_data.get("target_relative_path", "") or "")
    param_item.target_id_path = target_id_path if is_serialized_property_path_safe(target_id_path) else ""
    _set_param_target_pointer(param_item, resolve_id_data_path(param_item.target_id_path))
    param_item.target_relative_path = target_relative_path
    if not param_item.target_relative_path:
        rebuild_param_target_reference(param_item, property_path)
    param_item.stored_action_slots = str(param_data.get("stored_action_slots", "") or "")

    if stored_kind == "POINTER":
        pointer_payload = param_data.get("value")
        if isinstance(pointer_payload, dict):
            pointer_name = pointer_payload.get("name", "")
        else:
            pointer_name = str(pointer_payload or "")
        meta["fixed_type"] = stored_pointer_kind
        pointer_value = _resolve_serialized_pointer(stored_pointer_kind, pointer_payload)
        if pointer_name and pointer_value is None:
            meta["unresolved_pointer_name"] = pointer_name
        else:
            meta.pop("unresolved_pointer_name", None)
        assign_stored_from_value(param_item, pointer_value, "POINTER", meta)
        if stored_pointer_kind != "Action":
            param_item.stored_action_slots = ""
        return

    if stored_kind == "NONE":
        param_item.meta = json.dumps(meta)
        param_item.stored_kind = "NONE"
        param_item.stored_pointer_kind = "NONE"
        param_item.stored_action_slots = ""
        return

    value = _coerce_serialized_value(stored_kind, param_data.get("value"))
    assign_stored_from_value(param_item, value, stored_kind, meta)
    param_item.stored_pointer_kind = "NONE"
    param_item.stored_action_slots = ""


def apply_serialized_snapshot_item(snapshot_item, snapshot_data):
    if not isinstance(snapshot_data, dict):
        raise ValueError("Invalid snapshot payload")

    params = snapshot_data.get("params", [])
    if not isinstance(params, list):
        raise ValueError("Snapshot params must be a list")

    snapshot_item.name = str(snapshot_data.get("name") or iface_("Snapshot"))

    skipped_params = 0
    for param_data in params:
        param_item = snapshot_item.Param_properties_coll.add()
        try:
            apply_serialized_param_item(param_item, param_data)
        except Exception:
            snapshot_item.Param_properties_coll.remove(len(snapshot_item.Param_properties_coll) - 1)
            skipped_params += 1

    snapshot_item.Param_properties_coll_index = 0
    return skipped_params


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
    item.meta = json.dumps(meta)  # 转成字符串存入
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


def get_param_stored_val(item):
    val = None
    if item.stored_kind == "POINTER":
        if item.stored_pointer_kind == "Object":
            val = item.stored_object_pointer
        elif item.stored_pointer_kind == "Action":
            val = item.stored_action_pointer
        elif item.stored_pointer_kind == "Collection":
            val = item.stored_collection_pointer
    elif item.stored_kind == "FLOAT":
        val = item.stored_float
    elif item.stored_kind == "INT":
        val = item.stored_int
    elif item.stored_kind == "BOOLEAN":
        val = item.stored_bool
    elif item.stored_kind == "STRING":
        val = item.stored_string
    elif item.stored_kind == "VEC2":
        val = item.stored_vec2
    elif item.stored_kind == "VEC3":
        val = item.stored_vec3
    elif item.stored_kind == "VEC4":
        val = item.stored_vec4
    elif item.stored_kind == "COLOR3":
        val = item.stored_color3
    elif item.stored_kind == "COLOR4":
        val = item.stored_color4
    return val


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
    ptr, prop_token, arr_index, resolved_path = resolve_param_item_path(param_item)
    if ptr is None or prop_token is None:
        return None
    property_name = stored_kind_to_property_name(param_item.stored_kind, param_item.stored_pointer_kind)
    stored_val = getattr(param_item, property_name, None)
    meta = _safe_meta_loads(getattr(param_item, "meta", "{}"))
    if param_item.stored_kind == "POINTER" and stored_val is None and meta.get("unresolved_pointer_name"):
        return None
    if stored_val is not None or param_item.stored_kind == "POINTER":
        setattr(ptr, prop_token, stored_val)
        if param_item.stored_kind == "POINTER" and param_item.stored_pointer_kind == "Action":
            action = getattr(ptr, prop_token)
            slots = getattr(action, "slots", None)
            if not slots:
                return 2
            slot = None
            for s in slots:
                if s.name_display == param_item.stored_action_slots:
                    slot = s
            if slot:
                setattr(ptr, "action_slot", slot)
            else:
                print("动作槽设置失败")
                return 2
        return 1
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
