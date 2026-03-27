import bpy
from .utils import *
import json
from .i18n import translations, translatef
from . import ADDON_VERSION

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
            text = translations("Stored Value")
        if icon not in BLENDER_ICONS:
            icon = "NONE"
        row = row.row()
        row.prop(item, prop_name, icon=icon, text=text)
        if item.stored_kind == "POINTER" and item.stored_pointer_kind == "Action":
            row.prop(item, "stored_action_slots", text=translations("Action Slot"))
        return getattr(item, prop_name, None)

    def show_prop_path(self, row, item, text=""):
        try:
            obj, prop_token, arr_index, resolved_path = resolve_param_item_path(item, mutate=False)
            val_row = row.row()
            # --- A) IDProperty：prop_token 形如 '["Socket_3"]'
            if prop_token == None or obj == None:
                row = row.row()
                row.label(text=text)
                row.alert = True
                return row.label(text=translations("Path not found"), icon="ERROR")
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
                                text = translations("Current Value")
                            val_row.prop(obj, prop_token, text=text)
                            if item.stored_kind == "POINTER" and item.stored_pointer_kind == "Action":
                                val_row.prop(obj, "action_slot", text=translations("Action Slot"))
        except Exception as e:
            row = row.row()
            row.label(text=text)
            row.alert = True
            print(e)
            row.label(text=f"{e}", icon="ERROR")

    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        path_state = get_param_path_state(item) if (item.property_path or item.target_relative_path) else None
        row = layout.row(align=True)
        col_enable = row.column(align=True)
        enable = getattr(item, "enable", False)
        col_enable.ui_units_x = 1.2
        col_enable.alignment = "LEFT"
        col_enable.prop(item, "enable", icon="HIDE_OFF" if enable else "HIDE_ON", text="", emboss=False)

        # ---- ① 编号（极窄） ----
        num_col = row.column(align=True)
        num_col.ui_units_x = 1  # 这一列固定宽度，自己微调到合适
        num_col.alignment = "LEFT"
        num_col.label(text=f"{index+1}:")
        main_split = row.split(factor=0.2, align=True)
        # ---- ② 名称 ----
        name_col = main_split.row()
        name_col.enabled = enable
        name_col.prop(item, "name", text="", emboss=True, icon="BOOKMARKS")
        right_row = main_split.row(align=True)
        right_row.enabled = enable
        if path_state and path_state["has_conflict"]:
            warn_row = right_row.row(align=True)
            warn_row.alert = True
            warn_row.label(text="", icon="ERROR")
        # ---- ④ 实际属性控件 ----
        if item.property_path or item.target_relative_path:
            self.show_prop_path(right_row, item)
        self.show_stored(right_row, item)
        sync_row = right_row.row(align=True)
        sync_row.enabled = enable
        op = sync_row.operator("param.sync_param", text="", icon="FILE_REFRESH")
        op.ParamIndex = index
        op = sync_row.operator("param.update_stored_value", text="", icon="ANIM")
        op.ParamIndex = index
        op = sync_row.operator("param.swap_param", text="", icon="UV_SYNC_SELECT")
        op.ParamIndex = index


class VIEW3D_PT_ParamSnapPanel(bpy.types.Panel):
    """在 3D 视图侧边栏创建面板"""

    bl_label = "Parameter Snapshot"
    bl_idname = "VIEW3D_PT_paramsnap"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "ParamSnap"

    def draw(self, context):
        layout = self.layout
        scene = context.scene

        col = layout.column()
        row = col.row(align=True)
        col.label(text=translations("Snapshots"))
        col.label(text=translations("How to use: Right-click any property and add it to the active snapshot"), icon="INDIRECT_ONLY_ON")
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
        col1.separator()
        col1.operator("param.copy_snapshot", text="", icon="COPYDOWN")

        export_row = col.row(align=True)
        export_row.enabled = len(scene.paramsnap_properties.ParamSnap_properties_coll) != 0
        export_row.operator("param.export_snapshot_json", text=translations("Export JSON"), icon="EXPORT")
        export_row.operator("param.copy_snapshot_json", text=translations("Copy JSON"), icon="COPYDOWN")

        import_row = col.row(align=True)
        import_row.operator("param.import_snapshot_json", text=translations("Import JSON"), icon="IMPORT")
        import_row.operator("param.paste_snapshot_json", text=translations("Paste JSON"), icon="PASTEDOWN")

        row = col.row(align=True)
        if len(scene.paramsnap_properties.ParamSnap_properties_coll) != 0:
            ParamSnap_properties_coll = context.scene.paramsnap_properties.ParamSnap_properties_coll
            ParamSnap_properties_coll_index = context.scene.paramsnap_properties.ParamSnap_properties_coll_index
            activite_snap = ParamSnap_properties_coll[ParamSnap_properties_coll_index]
            row_tile = col.row(align=True)
            row_tile_left = row_tile.split(factor=0.8, align=True)
            row_tile_left_1 = row_tile_left.row(align=True)
            row_tile_left_2 = row_tile_left_1.row(align=True)
            row_tile_left_2.scale_x = 0.25
            row_tile_left_2.label(text="")
            # row_tile_left_1.prop(activite_snap, "switch_enable", text="", emboss=False, icon="HIDE_OFF" if activite_snap.switch_enable else "HIDE_ON")
            row_tile_left_1.operator("param.inver_enable", text="", icon="ARROW_LEFTRIGHT", emboss=False)
            row_tile_left_1.label(text=f"|{translations('Parameter Name')}|")
            row_tile_left_1.label(text=f"|{translations('Current Value')}|")
            row_tile_left_1.label(text=f"|{translations('Stored Value')}|")
            row_tile_left.label(text=f"|{translations('Sync')}|")
            row_tile_left.label(text=f"|{translations('Update')}|")
            row_tile_left.label(text=f"|{translations('Swap')}|")

            # col.label(text=translations("|参数列表|------|参数名称|-------|当前值|------|存储值|------|同步选中参数|"))
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

            col1.separator()

            op = col1.operator("param.move_item_to_end_generic", text="", icon="TRIA_UP_BAR")
            op.coll_path = coll_path
            op.index_path = index_path
            op.where = "TOP"
            op = col1.operator("param.move_item_to_end_generic", text="", icon="TRIA_DOWN_BAR")
            op.coll_path = coll_path
            op.index_path = index_path
            op.where = "BOTTOM"

            col1.separator()
            col1.operator("param.resolve_all_path_conflicts", text="", icon="CHECKMARK")
        col = layout.column(align=True)
        if len(scene.paramsnap_properties.ParamSnap_properties_coll) != 0:
            col.prop(
                scene.paramsnap_properties,
                "show_param_properties",
                text=translations("Show Parameter Details"),
                icon="TRIA_DOWN" if scene.paramsnap_properties.show_param_properties else "TRIA_RIGHT",
            )
        if scene.paramsnap_properties.show_param_properties:
            if len(scene.paramsnap_properties.ParamSnap_properties_coll) > 0:
                activite_Snap = scene.paramsnap_properties.ParamSnap_properties_coll[scene.paramsnap_properties.ParamSnap_properties_coll_index]
                if len(activite_Snap.Param_properties_coll) > 0:
                    activite_params = activite_Snap.Param_properties_coll[activite_Snap.Param_properties_coll_index]
                    box = col.box()
                    box.prop(activite_params, "enable", text=translations("Enabled"), icon="HIDE_OFF" if activite_params.enable else "HIDE_ON", emboss=True)
                    box = col.box()
                    box.enabled = activite_params.enable
                    box.prop(activite_params, "name", text=translations("Parameter Name"))
                    box.prop(
                        scene.paramsnap_properties,
                        "show_reference_properties",
                        text=translations("Show Property References"),
                        icon="TRIA_DOWN" if scene.paramsnap_properties.show_reference_properties else "TRIA_RIGHT",
                    )
                    _resolved_ptr, prop_token, arr_index, resolved_path = resolve_param_item_path(activite_params, mutate=False)
                    path_state = get_param_path_state(activite_params)
                    if scene.paramsnap_properties.show_reference_properties:
                        ref_box = box.box()
                        row = ref_box.row()
                        row.alert = (bool(path_state["property_path"]) and not path_state["property_valid"]) or path_state["has_conflict"]
                        row.prop(activite_params, "property_path", text=translations("Property Path"))
                        if activite_params.target_id_pointer is not None:
                            target_name = getattr(activite_params.target_id_pointer, "name_full", activite_params.target_id_pointer.name)
                            ref_box.label(text=translatef("Follow Datablock: {name}", name=target_name), icon="LINKED")
                        if activite_params.target_relative_path:
                            rel_row = ref_box.row()
                            rel_row.enabled = False
                            rel_row.label(text=translatef("Relative Path: {path}", path=activite_params.target_relative_path), icon="RNA")
                        if path_state["stable_path"] and path_state["stable_path"] != path_state["property_path"]:
                            stable_row = ref_box.row()
                            stable_row.enabled = False
                            stable_row.label(text=translatef("Datablock Reference Path: {path}", path=path_state["stable_path"]), icon="LINKED")
                        if path_state["has_conflict"]:
                            conflict_box = ref_box.box()
                            conflict_box.alert = True
                            conflict_box.label(text=translations("Property path and datablock reference point to different targets"), icon="ERROR")
                            if not path_state["property_valid"]:
                                conflict_box.label(text=translations("Property path is no longer valid"), icon="UNLINKED")
                            if path_state["stable_path"] and not path_state["stable_valid"]:
                                conflict_box.label(text=translations("Datablock reference is no longer valid"), icon="UNLINKED")
                            action_row = conflict_box.row(align=True)
                            stable_action = action_row.row(align=True)
                            stable_action.enabled = path_state["stable_valid"]
                            op = stable_action.operator("param.resolve_path_conflict", text=translations("Use Datablock Reference"), icon="LINKED")
                            op.mode = "STABLE"
                            property_action = action_row.row(align=True)
                            property_action.enabled = path_state["property_valid"]
                            op = property_action.operator("param.resolve_path_conflict", text=translations("Prefer Property Path"), icon="RNA")
                            op.mode = "PROPERTY"
                        elif path_state["has_path_mismatch"]:
                            info_box = ref_box.box()
                            info_box.label(text=translations("Property path and datablock reference resolve to the same target"), icon="INFO")
                        if resolved_path and resolved_path not in {path_state["property_path"], path_state["stable_path"]}:
                            live_row = ref_box.row()
                            live_row.enabled = False
                            live_row.label(text=translatef("Resolved Path: {path}", path=resolved_path), icon="FILE_REFRESH")
                    if 0:
                        box.prop(activite_params, "meta", text="元数据")
                    box.prop(activite_params, "stored_kind", text=translations("Value Type"))
                    if activite_params.stored_kind == "POINTER":
                        box.prop(activite_params, "stored_pointer_kind", text=translations("Pointer Type"))
                    val_box = box.box()
                    col = val_box.column(align=True)
                    PARAMS_UL_ParamList.show_prop_path(self, col, activite_params, translations("Current Value"))
                    PARAMS_UL_ParamList.show_stored(self, col, activite_params, translations("Stored Value"))
                    col = box.column(align=True)
                    # col.prop(activite_params, "meta", text="元数据")
                    op = col.operator("param.sync_param", text=translations("Sync Selected Parameter"), icon="FILE_REFRESH")
                    op.ParamIndex = activite_Snap.Param_properties_coll_index
                    op = col.operator("param.update_stored_value", text=translations("Update Stored Value"), icon="ANIM")
                    op.ParamIndex = activite_Snap.Param_properties_coll_index
                    op = col.operator("param.swap_param", text=translations("Swap Parameter"), icon="UV_SYNC_SELECT")
                    op.ParamIndex = activite_Snap.Param_properties_coll_index

        col = layout.column(align=True)
        col.scale_y = 2.0
        row = col.row(align=True)
        main_split = row.split(factor=0.8, align=True)
        main_split.operator("param.sync_all_params", text=translations("Sync All Parameters"), icon="FILE_REFRESH")
        main_split.operator("param.update_all_stored_value", text=translations("Update All Stored Values"), icon="ANIM")
        main_split.operator("param.swap_all_param", text=translations("Swap All Parameters"), icon="UV_SYNC_SELECT")

        col = layout.column()
        col.operator("param.copy_snapshot", text=translations("Copy Snapshot"), icon="COPYDOWN")

        col = layout.column()
        version_str = ".".join(map(str, ADDON_VERSION))
        col.alignment = "EXPAND"
        col.label(text=translatef("Version: {version}", version=version_str), icon="INFO")


def draw_property_context_menu(self, context):
    layout = self.layout

    prop = getattr(context, "button_prop", None)
    ptr = getattr(context, "button_pointer", None)
    # index = getattr(context, "button_index", -1)  # 获取点击的维度，如 X 轴

    if prop and ptr:
        layout.separator()
        layout.operator("param.add_param_to_col", text=translations("Add to Active Snapshot"), icon="INDIRECT_ONLY_ON")
    # else:
    #     layout.label(text="请选择属性", icon="ERROR")


# 从活动属性面板获取数据块
def _resolve_target_id_from_properties(context):
    space = context.space_data
    tab = space.context if (space and space.type == "PROPERTIES") else ""
    pinned = None
    if space and space.type == "PROPERTIES" and getattr(space, "use_pin_id", False):
        pinned = space.pin_id  # 可能是 Object / Material / Mesh / Scene / World ...
    base = pinned
    if base is None:
        if tab == "SCENE":
            base = context.scene
        elif tab == "WORLD":
            base = context.scene.world if context.scene else None
        elif tab == "MATERIAL":
            base = context.material or (context.active_object.active_material if context.active_object else None)
        else:
            base = context.active_object
    if tab == "OBJECT":
        return base if isinstance(base, bpy.types.Object) else context.active_object
    if tab == "DATA":
        if isinstance(base, bpy.types.Object):
            return base.data
        return base
    if tab == "MATERIAL":
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
    return base


# 添加到动画面板的部分
def sna_add_to_action_panel(self, context, panel_name):
    layout = self.layout
    # layout.label(text=panel_name)

    id_block = _resolve_target_id_from_properties(context)
    base = id_to_bpy_data_path(id_block)  # 这里返回 bpy.data.xxx["Name"]
    path = base + ".animation_data.action"

    op = layout.operator("param.add_action_to_param", text=translations("Add to Active Snapshot"), icon="INDIRECT_ONLY_ON")
    op.name = id_block.name
    op.path = path

    if panel_name == "MATERIAL_PT_animation":
        mat = id_block if isinstance(id_block, bpy.types.Material) else None
        if mat:
            mat_base = id_to_bpy_data_path(mat)  # bpy.data.materials["Mat"]
            nt = getattr(mat, "node_tree", None)
            if nt and mat_base:
                nt_path = mat_base + ".node_tree.animation_data.action"
                op = layout.operator("param.add_action_to_param", text=translations("Add Shader Node Tree Action to Active Snapshot"), icon="INDIRECT_ONLY_ON")
                op.name = mat.name
                op.path = nt_path
    elif panel_name == "DATA_PT_mesh_animation":
        mesh = id_block if isinstance(id_block, bpy.types.Mesh) else None
        if mesh:
            mesh_base = id_to_bpy_data_path(mesh)  # bpy.data.meshes["Suzanne"]
            shape_keys = getattr(mesh, "shape_keys", None)
            if shape_keys and mesh_base:
                sk_path = mesh_base + ".shape_keys.animation_data.action"
                op = layout.operator("param.add_action_to_param", text=translations("Add Shape Key Action to Active Snapshot"), icon="INDIRECT_ONLY_ON")
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
_BUTTON_CONTEXT_MENU_CLS = None


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


def _resolve_button_context_menu_cls():
    for menu_name in ("UI_MT_button_context_menu", "WM_MT_button_context"):
        menu_cls = getattr(bpy.types, menu_name, None)
        if menu_cls is not None:
            return menu_cls
    return None


def register():
    global _BUTTON_CONTEXT_MENU_CLS
    bpy.utils.register_class(PARAMS_UL_SnapshotList)
    bpy.utils.register_class(PARAMS_UL_ParamList)
    bpy.utils.register_class(VIEW3D_PT_ParamSnapPanel)
    _BUTTON_CONTEXT_MENU_CLS = _resolve_button_context_menu_cls()
    if _BUTTON_CONTEXT_MENU_CLS is not None:
        _BUTTON_CONTEXT_MENU_CLS.append(draw_property_context_menu)
    else:
        print("ParamSnap: button context menu type not found, skip context menu registration")
    register_animation_panels()


def unregister():
    global _BUTTON_CONTEXT_MENU_CLS
    bpy.utils.unregister_class(PARAMS_UL_SnapshotList)
    bpy.utils.unregister_class(PARAMS_UL_ParamList)
    bpy.utils.unregister_class(VIEW3D_PT_ParamSnapPanel)
    menu_cls = _BUTTON_CONTEXT_MENU_CLS or _resolve_button_context_menu_cls()
    if menu_cls is not None:
        try:
            menu_cls.remove(draw_property_context_menu)
        except ValueError:
            pass
    _BUTTON_CONTEXT_MENU_CLS = None
    unregister_animation_panels()
