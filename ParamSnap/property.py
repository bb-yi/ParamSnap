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


def property_path_update(self, context):
    try:
        from .utils import rebuild_param_target_reference

        rebuild_param_target_reference(self, self.property_path)
    except Exception:
        pass


# 参数项属性
def stored_bool_display_get(self):
    try:
        from .utils import get_param_bool_display_value

        return get_param_bool_display_value(self)
    except Exception:
        return bool(self.stored_bool)


def stored_bool_display_set(self, value):
    try:
        from .utils import set_param_bool_display_value

        set_param_bool_display_value(self, value)
    except Exception:
        self.stored_bool = bool(value)


def current_bool_display_get(self):
    try:
        from .utils import get_param_current_bool_display_value

        return get_param_current_bool_display_value(self)
    except Exception:
        return False


def current_bool_display_set(self, value):
    try:
        from .utils import set_param_current_bool_display_value

        set_param_current_bool_display_value(self, value)
    except Exception:
        pass


class ParamItem(bpy.types.PropertyGroup):
    copy_selected: BoolProperty(name="Selected", default=False)
    enable: BoolProperty(name="enable", default=True)
    name: StringProperty(name="", default="Parameter", description="Display name for this parameter")
    category: StringProperty(name="Category", default="Other", description="Parameter category used for grouping")
    property_path: StringProperty(name="Property Path", default="", description="Full Blender RNA path for this parameter", update=property_path_update)
    target_id_pointer: PointerProperty(type=bpy.types.ID)
    target_id_path: StringProperty(name="Target ID Path", default="", description="Resolved root datablock path")
    target_relative_path: StringProperty(name="Target Relative Path", default="", description="Path relative to the root datablock")
    target_layer_collection_pointer: PointerProperty(type=bpy.types.Collection)
    target_layer_collection_view_layer: StringProperty(name="Target View Layer", default="")
    target_layer_collection_property: StringProperty(name="Target LayerCollection Property", default="")

    stored_kind: EnumProperty(
        name="Stored Kind",
        items=[(t, t, "") for t in types],
        default="NONE",
        description="Stored value type",
    )

    stored_float: FloatProperty(default=0.0)
    stored_int: IntProperty(default=0)
    stored_bool: BoolProperty(default=False)
    stored_bool_display: BoolProperty(get=stored_bool_display_get, set=stored_bool_display_set)
    current_bool_display: BoolProperty(get=current_bool_display_get, set=current_bool_display_set)
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
            ("NodeTree", "NodeTree", ""),
            ("NONE", "None", ""),
        ],
        default="NONE",
        description="Stored pointer type",
    )
    stored_action_pointer: bpy.props.PointerProperty(type=bpy.types.Action)
    stored_action_slots: bpy.props.StringProperty(default="")
    stored_object_pointer: bpy.props.PointerProperty(type=bpy.types.Object)
    stored_collection_pointer: bpy.props.PointerProperty(type=bpy.types.Collection)
    stored_node_tree_pointer: bpy.props.PointerProperty(type=bpy.types.NodeTree)


def switch_enable_update(self, context):
    ParamSnap_properties_coll = context.scene.paramsnap_properties.ParamSnap_properties_coll
    ParamSnap_properties_coll_index = context.scene.paramsnap_properties.ParamSnap_properties_coll_index
    activite_snap = ParamSnap_properties_coll[ParamSnap_properties_coll_index]
    for i in range(len(activite_snap.Param_properties_coll)):
        activite_snap.Param_properties_coll[i].enable = self.switch_enable
    for area in context.screen.areas:
        area.tag_redraw()


# 快照项属性
class ParamSnapItem(bpy.types.PropertyGroup):
    name: StringProperty(name="", default=translations("Snapshot"))
    Param_properties_coll: CollectionProperty(type=ParamItem)
    Param_properties_coll_index: IntProperty(name="Param Properties Index", default=0)
    collapsed_categories: StringProperty(name="Collapsed Categories", default="[]")
    switch_enable: BoolProperty(name="Switch Enable", default=True, update=switch_enable_update)


# 插件属性组
class ParamSnapProperty(bpy.types.PropertyGroup):
    ParamSnap_properties_coll: CollectionProperty(type=ParamSnapItem)
    ParamSnap_properties_coll_index: IntProperty(name="ParamSnap Properties Index", default=0)
    param_clipboard: StringProperty(name="Parameter Clipboard", default="")
    show_param_properties: BoolProperty(name="Show Parameter Details", default=False)
    show_reference_properties: BoolProperty(name="Show Property References", default=False)


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
