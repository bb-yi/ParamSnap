import bpy
from bpy.props import *
from .i18n import translations

types = [
    "FLOAT",
    "INT",
    "BOOLEAN",
    "STRING",
    "VEC2",
    "VEC3",
    "VEC4",
    "COLOR3",
    "COLOR4",
    "POINTER",
    "UNDEFINED",
    "NONE",
]


# 参数项属性
class ParamItem(bpy.types.PropertyGroup):
    name: StringProperty(name="", default="Parameter")
    property_path: StringProperty(name="Property Path", default="")

    stored_kind: EnumProperty(
        name="Stored Kind",
        items=[(t, t, "") for t in types],
        default="NONE",
    )

    stored_float: FloatProperty(default=0.0)
    stored_int: IntProperty(default=0)
    stored_bool: BoolProperty(default=False)
    stored_string: StringProperty(default="")

    stored_vec2: FloatVectorProperty(size=2, subtype="NONE", default=(0.0, 0.0))
    stored_vec3: FloatVectorProperty(size=3, subtype="NONE", default=(0.0, 0.0, 0.0))
    stored_vec4: FloatVectorProperty(size=4, subtype="NONE", default=(0.0, 0.0, 0.0, 0.0))

    stored_color3: FloatVectorProperty(size=3, subtype="COLOR", min=0.0, max=1.0, default=(0.0, 0.0, 0.0))
    stored_color4: FloatVectorProperty(size=4, subtype="COLOR", min=0.0, max=1.0, default=(0.0, 0.0, 0.0, 1.0))

    # 元数据
    meta: StringProperty(default="{}")

    stored_pointer_kind: EnumProperty(
        name="stored_pointer_kind",
        items=[
            ("Action", "Action", ""),
            ("Object", "Object", ""),
            ("Collection", "Collection", ""),
            ("NONE", "None", ""),
        ],
        default="NONE",
    )
    stored_action_pointer: bpy.props.PointerProperty(type=bpy.types.Action)
    stored_object_pointer: bpy.props.PointerProperty(type=bpy.types.Object)
    stored_collection_pointer: bpy.props.PointerProperty(type=bpy.types.Collection)


# 快照项属性
class ParamSnapItem(bpy.types.PropertyGroup):
    name: StringProperty(name="", default=translations("Snapshot"))
    Param_properties_coll: CollectionProperty(type=ParamItem)
    Param_properties_coll_index: IntProperty(name="Param Properties Index", default=0)


# 插件属性组
class ParamSnapProperty(bpy.types.PropertyGroup):
    ParamSnap_properties_coll: CollectionProperty(type=ParamSnapItem)
    ParamSnap_properties_coll_index: IntProperty(name="ParamSnap Properties Index", default=0)
    show_param_properties: BoolProperty(name="Show Param Properties", default=True)


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
