import bpy
from .utils import *
import json
from .i18n import translations
import sys
from . import bl_info

BLENDER_ICONS = {i.identifier for i in bpy.types.UILayout.bl_rna.functions["prop"].parameters["icon"].enum_items}


# item面板
# 快照集合面板
class PARAMS_UL_SnapshotList(bpy.types.UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        row = layout.row(align=True)
        # ---- ① 编号（极窄） ----
        num_col = row.column(align=True)
        num_col.ui_units_x = 1  # 这一列固定宽度，自己微调到合适
        num_col.alignment = "LEFT"
        num_col.label(text=f"{index+1}:")
        row.prop(item, "name", text="", icon="BOOKMARKS")


class PARAMS_UL_ParamList(bpy.types.UIList):
    def show_stored(self, row, item, text=""):
        if item.stored_kind == "NONE":
            return None
        prop_name = stored_kind_to_property_name(item.stored_kind, item.stored_pointer_kind)
        if not prop_name:
            return None
        meta = json.loads(item.meta)
        icon = meta.get("icon", None)
        if prop_name == "stored_bool":
            icon = get_toggle_icon(icon, not item.stored_bool)
            text = "存储的值"
        if icon not in BLENDER_ICONS:
            icon = "NONE"
        row = row.row()
        row.prop(item, prop_name, icon=icon, text=text)
        if item.stored_kind == "POINTER" and item.stored_pointer_kind == "Action":
            row.prop(item, "stored_action_slots", text=text)
        return getattr(item, prop_name, None)

    def show_prop_path(self, row, item, text=""):
        try:
            obj, prop_token, arr_index = resolve_ui_path(item.property_path)
            val_row = row.row()
            # --- A) IDProperty：prop_token 形如 '["Socket_3"]'
            if prop_token == None or obj == None:
                row = row.row()
                row.label(text=text)
                row.alert = True
                return row.label(text=f"路径属性不存在", icon="ERROR")
            if prop_token.startswith('["') or prop_token.startswith("['"):
                val_row.prop(obj, prop_token, text=text)
            else:
                # --- B) 普通 RNA 属性
                if hasattr(obj, "bl_rna") and prop_token in obj.bl_rna.properties:
                    attr_value = getattr(obj, prop_token)
                    is_color = hasattr(obj.bl_rna.properties[prop_token], "subtype") and obj.bl_rna.properties[prop_token].subtype == "COLOR"
                    if hasattr(attr_value, "__len__") and len(attr_value) in (2, 3) and not is_color and obj.bl_rna.properties[prop_token].type == "FLOAT":
                        val_row = row.row(align=True)
                        val_row.prop(obj, prop_token, index=0, text=text)
                        val_row.prop(obj, prop_token, index=1, text=text)
                        if len(attr_value) == 3:
                            val_row.prop(obj, prop_token, index=2, text=text)
                    else:
                        if arr_index != -1:
                            val_row.prop(obj, prop_token, index=arr_index, text=text)
                        else:
                            if obj.bl_rna.properties.get(prop_token).type == "BOOLEAN":
                                text = "当前的值"
                            val_row.prop(obj, prop_token, text=text)
                            if item.stored_kind == "POINTER" and item.stored_pointer_kind == "Action":
                                val_row.prop(obj, "action_slot", text=text)
        except Exception as e:
            row = row.row()
            row.label(text=text)
            row.alert = True
            print(e)
            row.label(text=f"{e}", icon="ERROR")

    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        row = layout.row(align=True)

        # ---- ① 编号（极窄） ----
        num_col = row.column(align=True)
        num_col.ui_units_x = 1  # 这一列固定宽度，自己微调到合适
        num_col.alignment = "LEFT"
        num_col.label(text=f"{index+1}:")
        main_split = row.split(factor=0.2, align=True)
        # ---- ② 名称 ----
        name_col = main_split.row()
        name_col.prop(item, "name", text="", emboss=True, icon="BOOKMARKS")
        right_row = main_split.row(align=True)
        # ---- ④ 实际属性控件 ----
        if item.property_path:
            self.show_prop_path(right_row, item)
        self.show_stored(right_row, item)
        sync_row = right_row.row(align=True)
        op = sync_row.operator("param.sync_param", text="", icon="FILE_REFRESH")
        op.ParamIndex = index


class VIEW3D_PT_ParamSnapPanel(bpy.types.Panel):
    """在 3D 视图侧边栏创建面板"""

    bl_label = "参数快照 (ParamSnap)"
    bl_idname = "VIEW3D_PT_paramsnap"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "ParamSnap"

    def draw(self, context):
        layout = self.layout
        scene = context.scene

        col = layout.column(align=True)
        col.operator("param.test_operator", text="测试操作")

        col = layout.column()
        row = col.row(align=True)
        col.label(text=translations("快照列表"))
        col.label(text=translations("使用方法:  右键任意参数,添加到活动快照"), icon="INDIRECT_ONLY_ON")
        row = col.row(align=True)
        row.template_list("PARAMS_UL_SnapshotList", "", scene.paramsnap_properties, "ParamSnap_properties_coll", scene.paramsnap_properties, "ParamSnap_properties_coll_index", rows=6)
        col1 = row.column(align=True)
        coll_path = "scene.paramsnap_properties.ParamSnap_properties_coll"
        index_path = "scene.paramsnap_properties.ParamSnap_properties_coll_index"
        op = col1.operator("param.add_item_generic", text="", icon="ADD")
        op.coll_path = coll_path
        op.index_path = index_path
        op = col1.operator("param.remove_item_generic", text="", icon="REMOVE")
        op.coll_path = coll_path
        op.index_path = index_path
        col1.separator()
        op = col1.operator("param.move_item_generic", text="", icon="TRIA_UP")
        op.coll_path = coll_path
        op.index_path = index_path
        op.direction = "UP"
        op = col1.operator("param.move_item_generic", text="", icon="TRIA_DOWN")
        op.coll_path = coll_path
        op.index_path = index_path
        op.direction = "DOWN"

        row = col.row(align=True)
        if len(scene.paramsnap_properties.ParamSnap_properties_coll) != 0:
            col.label(text=translations("|参数列表|------|参数名称|-------|当前值|------|存储值|------|同步选中参数|"))
            row = col.row(align=True)
            row.template_list(
                "PARAMS_UL_ParamList",
                "",
                scene.paramsnap_properties.ParamSnap_properties_coll[scene.paramsnap_properties.ParamSnap_properties_coll_index],
                "Param_properties_coll",
                scene.paramsnap_properties.ParamSnap_properties_coll[scene.paramsnap_properties.ParamSnap_properties_coll_index],
                "Param_properties_coll_index",
                rows=6,
            )
            col1 = row.column(align=True)
            snap_idx = scene.paramsnap_properties.ParamSnap_properties_coll_index
            coll_path = f"scene.paramsnap_properties.ParamSnap_properties_coll[{snap_idx}].Param_properties_coll"
            index_path = f"scene.paramsnap_properties.ParamSnap_properties_coll[{snap_idx}].Param_properties_coll_index"

            op = col1.operator("param.add_item_generic", text="", icon="ADD")
            op.coll_path = coll_path
            op.index_path = index_path

            op = col1.operator("param.remove_item_generic", text="", icon="REMOVE")
            op.coll_path = coll_path
            op.index_path = index_path

            col1.separator()

            op = col1.operator("param.move_item_generic", text="", icon="TRIA_UP")
            op.coll_path = coll_path
            op.index_path = index_path
            op.direction = "UP"
            op = col1.operator("param.move_item_generic", text="", icon="TRIA_DOWN")
            op.coll_path = coll_path
            op.index_path = index_path
            op.direction = "DOWN"
        col = layout.column(align=True)
        if len(scene.paramsnap_properties.ParamSnap_properties_coll) != 0:
            col.prop(scene.paramsnap_properties, "show_param_properties", text="显示参数信息", icon="TRIA_DOWN" if scene.paramsnap_properties.show_param_properties else "TRIA_RIGHT")
        if scene.paramsnap_properties.show_param_properties:
            if len(scene.paramsnap_properties.ParamSnap_properties_coll) > 0:
                activite_Snap = scene.paramsnap_properties.ParamSnap_properties_coll[scene.paramsnap_properties.ParamSnap_properties_coll_index]
                if len(activite_Snap.Param_properties_coll) > 0:
                    activite_params = activite_Snap.Param_properties_coll[activite_Snap.Param_properties_coll_index]
                    box = col.box()
                    box.prop(activite_params, "name", text="参数名称")
                    row = box.row()
                    valid_path = resolve_ui_path(activite_params.property_path)[0]
                    row.alert = not valid_path
                    row.prop(activite_params, "property_path", text="属性路径")
                    box.prop(activite_params, "stored_kind", text="数据类型")
                    if activite_params.stored_kind == "POINTER":
                        box.prop(activite_params, "stored_pointer_kind", text="指针类型")
                    row = box.row()
                    PARAMS_UL_ParamList.show_prop_path(self, row, activite_params, "当前的值")
                    row = box.row()
                    PARAMS_UL_ParamList.show_stored(self, row, activite_params, "存储的值")
                    col = box.column()
                    col.prop(activite_params, "meta", text="元数据")
                    op = col.operator("param.sync_param", text="同步当前参数", icon="FILE_REFRESH")
                    op.ParamIndex = activite_Snap.Param_properties_coll_index

        col = layout.column(align=True)
        col.scale_y = 2.0
        col.operator("param.sync_all_params", text="同步所有参数", icon="FILE_REFRESH")
        col = layout.column()
        col.operator("param.copy_snapshot", text="复制快照", icon="COPYDOWN")

        col = layout.column()
        version_str = ".".join(map(str, bl_info["version"]))
        col.alignment = "EXPAND"
        col.label(text=f"Version: {version_str}", icon="INFO")


def draw_property_context_menu(self, context):
    layout = self.layout

    # 检查当前是否点击了有效的属性
    prop = getattr(context, "button_prop", None)
    ptr = getattr(context, "button_pointer", None)
    # index = getattr(context, "button_index", -1)  # 获取点击的维度，如 X 轴

    if prop and ptr:
        layout.separator()
        op = layout.operator("param.add_param_to_col", text="添加到活动快照", icon="INDIRECT_ONLY_ON")
    # else:
    #     layout.label(text="请选择属性", icon="ERROR")


# 哪些 tab 我们关心，以及它们该返回什么 target_id
def _resolve_target_id_from_properties(context):
    space = context.space_data
    tab = space.context if (space and space.type == "PROPERTIES") else ""

    # 1) 先处理 Pin（最重要）
    pinned = None
    if space and space.type == "PROPERTIES" and getattr(space, "use_pin_id", False):
        pinned = space.pin_id  # 可能是 Object / Material / Mesh / Scene / World ...

    # 2) 再根据 tab 选择“真正要挂 action 的 ID”
    base = pinned

    # 没 pin 时，base 从当前上下文补
    if base is None:
        if tab == "SCENE":
            base = context.scene
        elif tab == "WORLD":
            base = context.scene.world if context.scene else None
        elif tab == "MATERIAL":
            base = context.material or (context.active_object.active_material if context.active_object else None)
        else:
            base = context.active_object

    # 3) tab 分发成最终 target_id
    if tab == "OBJECT":
        # 目标是 Object（骨骼动画也挂在 Armature Object 上）
        return base if isinstance(base, bpy.types.Object) else context.active_object

    if tab == "DATA":
        # 数据属性：如果 base 是 Object，就返回它的 data；如果本身就是 Mesh/Curve/... 就直接返回
        if isinstance(base, bpy.types.Object):
            return base.data
        return base

    if tab == "MATERIAL":
        # 材质属性：pin 了材质就用材质；pin 了物体就用它 active_material
        if isinstance(base, bpy.types.Material):
            return base
        if isinstance(base, bpy.types.Object):
            return base.active_material
        return context.material

    if tab == "SCENE":
        return base if isinstance(base, bpy.types.Scene) else context.scene

    if tab == "WORLD":
        if isinstance(base, bpy.types.World):
            return base
        return context.scene.world if context.scene else None

    # 其它 tab 先返回 base（你也可以扩展）
    return base


def id_to_bpy_data_path(id_block):
    """返回类似 bpy.data.objects["Cube"] / bpy.data.materials["Mat"] 的路径字符串"""
    if not isinstance(id_block, bpy.types.ID):
        return None

    name = id_block.name.replace('"', '\\"')

    # 用指针比对最可靠
    try:
        ptr = id_block.as_pointer()
    except Exception:
        ptr = None

    # 扫描 bpy.data 的所有集合（objects/meshes/materials/actions/...)
    for attr in dir(bpy.data):
        col = getattr(bpy.data, attr, None)
        if col is None:
            continue

        # bpy.data.xxx 通常是 bpy_prop_collection：有 get()/keys()
        if not hasattr(col, "get"):
            continue

        try:
            item = col.get(id_block.name)
        except Exception:
            continue

        if not item:
            continue

        # 可能同名但不同实例，用指针确认
        try:
            if ptr is None or item.as_pointer() == ptr:
                return f'bpy.data.{attr}["{name}"]'
        except Exception:
            # 某些类型可能没 as_pointer，但一般 ID 都有；这里兜底：直接按名字认为匹配
            return f'bpy.data.{attr}["{name}"]'

    return None


def get_action_full_path(id_block):
    base = id_to_bpy_data_path(id_block)
    return (base + ".animation_data.action") if base else None


# 1) 改 draw 函数签名：多一个 panel_name
def sna_add_to_action_panel(self, context, panel_name):
    layout = self.layout
    # layout.label(text=panel_name)

    id_block = _resolve_target_id_from_properties(context)
    base = id_to_bpy_data_path(id_block)  # 这里返回 bpy.data.xxx["Name"]
    path = base + ".animation_data.action"

    op = layout.operator("param.add_action_to_param", text="添加到活动快照", icon="INDIRECT_ONLY_ON")
    op.name = id_block.name + "animation"
    op.path = path

    if panel_name == "MATERIAL_PT_animation":
        mat = id_block if isinstance(id_block, bpy.types.Material) else None
        if mat:
            mat_base = id_to_bpy_data_path(mat)  # bpy.data.materials["Mat"]
            nt = getattr(mat, "node_tree", None)
            if nt and mat_base:
                nt_path = mat_base + ".node_tree.animation_data.action"
                op = layout.operator("param.add_action_to_param", text="添加着色器节点树动作到活动快照", icon="INDIRECT_ONLY_ON")
                op.name = mat.name
                op.path = nt_path
    elif panel_name == "DATA_PT_mesh_animation":
        mesh = id_block if isinstance(id_block, bpy.types.Mesh) else None
        if mesh:
            mesh_base = id_to_bpy_data_path(mesh)  # bpy.data.meshes["Suzanne"]
            shape_keys = getattr(mesh, "shape_keys", None)
            if shape_keys and mesh_base:
                sk_path = mesh_base + ".shape_keys.animation_data.action"
                op = layout.operator("param.add_action_to_param", text="添加形状键动作到活动快照", icon="INDIRECT_ONLY_ON")
                op.name = mesh.name
                op.path = sk_path


"""
DATA_PT_armature_animation      # 骨骼数据块（Armature Data）动画
DATA_PT_camera_animation        # 相机数据动画
DATA_PT_curve_animation         # 曲线数据（Curve）动画
DATA_PT_curves_animation        # 新版 Curves（头发曲线）数据动画
DATA_PT_grease_pencil_animation # Grease Pencil 数据动画
DATA_PT_lattice_animation       # 晶格(Lattice)数据动画
DATA_PT_light_animation         # 灯光数据动画
DATA_PT_lightprobe_animation    # 光照探头(Light Probe)数据动画
DATA_PT_mesh_animation          # 网格(Mesh)数据动画
DATA_PT_metaball_animation      # Metaball 数据动画
DATA_PT_speaker_animation       # 扬声器(Speaker)数据动画
DATA_PT_volume_animation        # Volume 数据动画

MATERIAL_PT_animation           # 材质动画
OBJECT_PT_animation             # 物体(Object)动画（含骨骼姿态动画）
SCENE_PT_animation              # 场景动画
TEXTURE_PT_animation            # 旧纹理系统动画（老系统）
WORLD_PT_animation              # 世界(World)动画
"""
# 2) 你的面板表保持不变（值仍然是同一个函数）
PT_animation = {
    "DATA_PT_armature_animation": "",
    "DATA_PT_camera_animation": "",
    "DATA_PT_curve_animation": "",
    "DATA_PT_curves_animation": "",
    "DATA_PT_grease_pencil_animation": "",
    "DATA_PT_lattice_animation": "",
    "DATA_PT_light_animation": "",
    "DATA_PT_lightprobe_animation": "",
    "DATA_PT_mesh_animation": "",
    "DATA_PT_metaball_animation": "",
    "DATA_PT_speaker_animation": "",
    "DATA_PT_volume_animation": "",
    "MATERIAL_PT_animation": "",
    "OBJECT_PT_animation": "",
    "SCENE_PT_animation": "",
    "TEXTURE_PT_animation": "",
    "WORLD_PT_animation": "",
}

_PT_wrapped_draw = {}


def register_animation_panels():
    for panel_name, draw_func in PT_animation.items():
        panel_cls = getattr(bpy.types, panel_name, None)
        if not panel_cls:
            continue

        def _wrapped(self, context, _panel_name=panel_name, _draw=sna_add_to_action_panel):
            return _draw(self, context, _panel_name)

        _PT_wrapped_draw[panel_name] = _wrapped
        panel_cls.append(_wrapped)


def unregister_animation_panels():
    for panel_name, wrapped in _PT_wrapped_draw.items():
        panel_cls = getattr(bpy.types, panel_name, None)
        if not panel_cls:
            continue
        try:
            panel_cls.remove(wrapped)
        except ValueError:
            pass
    _PT_wrapped_draw.clear()


def register():
    bpy.utils.register_class(PARAMS_UL_SnapshotList)
    bpy.utils.register_class(PARAMS_UL_ParamList)
    bpy.utils.register_class(VIEW3D_PT_ParamSnapPanel)
    bpy.types.WM_MT_button_context.append(draw_property_context_menu)
    register_animation_panels()


def unregister():
    bpy.utils.unregister_class(PARAMS_UL_SnapshotList)
    bpy.utils.unregister_class(PARAMS_UL_ParamList)
    bpy.utils.unregister_class(VIEW3D_PT_ParamSnapPanel)
    bpy.types.WM_MT_button_context.remove(draw_property_context_menu)
    unregister_animation_panels()
