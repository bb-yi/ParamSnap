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
        return getattr(item, prop_name, None)

    def show_prop_path(self, row, item, text=""):
        try:
            obj, prop_token, arr_index = resolve_ui_path(item.property_path)
            val_row = row.row()
            # --- A) IDProperty：prop_token 形如 '["Socket_3"]'
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
        except Exception as e:
            row = row.row()
            row.label(text=text)
            row.alert = True
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
    else:
        layout.label(text="请选择属性", icon="ERROR")


def register():
    bpy.utils.register_class(PARAMS_UL_SnapshotList)
    bpy.utils.register_class(PARAMS_UL_ParamList)
    bpy.utils.register_class(VIEW3D_PT_ParamSnapPanel)
    bpy.types.WM_MT_button_context.append(draw_property_context_menu)


def unregister():
    bpy.utils.unregister_class(PARAMS_UL_SnapshotList)
    bpy.utils.unregister_class(PARAMS_UL_ParamList)
    bpy.utils.unregister_class(VIEW3D_PT_ParamSnapPanel)
    bpy.types.WM_MT_button_context.remove(draw_property_context_menu)
