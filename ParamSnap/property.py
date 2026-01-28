import bpy
from bpy.props import *
from .utils import *


def on_pointer_kind_enum_changed(self, context):
    if self.stored_pointer_kind == "Camera":
        self.name = "活动相机"
        self.property_path = "bpy.context.scene.camera"


def stored_kind_to_property_name(stored_kind, stored_pointer_kind=None):
    mapping = {
        "FLOAT": "stored_float",
        "INT": "stored_int",
        "BOOL": "stored_bool",
        "STRING": "stored_string",
        "VEC2": "stored_vec2",
        "VEC3": "stored_vec3",
        "VEC4": "stored_vec4",
        "COLOR3": "stored_color3",
        "COLOR4": "stored_color4",
        "ENUM": "stored_enum",
    }
    if stored_kind in mapping:
        return mapping[stored_kind]
    elif stored_kind == "POINTER":
        if stored_pointer_kind == "Action":
            return "stored_action_pointer"
        elif stored_pointer_kind == "Camera":
            return "stored_camera_pointer"
        else:
            return None

    return None


# 参数项属性
class ParamItem(bpy.types.PropertyGroup):
    name: StringProperty(name="", default="Parameter")
    property_path: StringProperty(name="Property Path", default="")

    stored_kind: EnumProperty(
        name="Stored Kind",
        items=[
            ("FLOAT", "Float", ""),
            ("INT", "Int", ""),
            ("BOOL", "Bool", ""),
            ("STRING", "String", ""),
            ("VEC2", "Vec2", ""),
            ("VEC3", "Vec3", ""),
            ("VEC4", "Vec4", ""),
            ("COLOR3", "Color3", ""),
            ("COLOR4", "Color4", ""),
            ("ENUM", "Enum", ""),
            ("IDPROP", "IDProp", ""),
            ("POINTER", "Pointer", ""),
            ("NONE", "None", ""),
        ],
        default="NONE",
    )

    stored_float: FloatProperty(default=0.0, min=0.0, max=1.0)
    stored_int: IntProperty(default=0)
    stored_bool: BoolProperty(default=False)
    stored_string: StringProperty(default="")

    stored_vec2: FloatVectorProperty(size=2, subtype="NONE", default=(0.0, 0.0))
    stored_vec3: FloatVectorProperty(size=3, subtype="NONE", default=(0.0, 0.0, 0.0))
    stored_vec4: FloatVectorProperty(size=4, subtype="NONE", default=(0.0, 0.0, 0.0, 0.0))

    stored_color3: FloatVectorProperty(size=3, subtype="COLOR", min=0.0, max=1.0, default=(0.0, 0.0, 0.0))
    stored_color4: FloatVectorProperty(size=4, subtype="COLOR", min=0.0, max=1.0, default=(0.0, 0.0, 0.0, 1.0))

    # ENUM 存储
    stored_enum: StringProperty(name="Enum Value", default="")

    # 元数据
    stored_json: StringProperty(default="")

    show_property_path: BoolProperty(name="Show Property Path", default=False)

    stored_pointer_kind: EnumProperty(
        name="stored_pointer_kind",
        items=[
            ("Action", "Action", ""),
            ("Camera", "Camera", ""),
            ("NONE", "None", ""),
        ],
        default="NONE",
        update=on_pointer_kind_enum_changed,
    )
    stored_action_pointer: bpy.props.PointerProperty(type=bpy.types.Action)
    stored_camera_pointer: bpy.props.PointerProperty(type=bpy.types.Camera)


# 快照项属性
class ParamSnapItem(bpy.types.PropertyGroup):
    name: StringProperty(name="", default=translations("Snapshot"))
    Param_properties_coll: CollectionProperty(type=ParamItem)
    Param_properties_coll_index: IntProperty(name="Param Properties Index", default=0)


# 插件属性组
class ParamSnapProperty(bpy.types.PropertyGroup):
    ParamSnap_properties_coll: CollectionProperty(type=ParamSnapItem)
    ParamSnap_properties_coll_index: IntProperty(name="ParamSnap Properties Index", default=0)


def register():
    bpy.utils.register_class(ParamItem)
    bpy.utils.register_class(ParamSnapItem)
    bpy.utils.register_class(ParamSnapProperty)
    bpy.types.Scene.paramsnap_properties = PointerProperty(type=ParamSnapProperty)


def unregister():
    bpy.utils.unregister_class(ParamItem)
    bpy.utils.unregister_class(ParamSnapItem)
    bpy.utils.unregister_class(ParamSnapProperty)
    del bpy.types.Scene.paramsnap_properties
