import bpy
from .utils import *
from .property import *


# item面板
# 快照集合面板
class PARAMS_UL_SnapshotList(bpy.types.UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        row = layout.row(align=True)
        row.split(factor=0.1).label(text=f"{index + 1}:")
        row.prop(item, "name", text="", emboss=False, icon_value=icon)


class PARAMS_UL_ParamList(bpy.types.UIList):
    def show_stored(self, row, item, text):
        if item.stored_kind != "NONE":
            meta = json.loads(item.stored_json) if item.stored_json else {}
            property_name = stored_kind_to_property_name(item.stored_kind, item.stored_pointer_kind)
            if item.stored_kind == "FLOAT":
                slider = meta.get("subtype") in {"FACTOR", "PERCENTAGE"}
                row.prop(item, "stored_float", text=text, slider=slider)
                return item.stored_float
            elif item.stored_kind == "INT":
                row.prop(item, "stored_int", text=text)
                return item.stored_int
            elif item.stored_kind == "BOOL":
                row.prop(item, "stored_bool", text=text)
                return item.stored_bool
            elif item.stored_kind == "STRING":
                row.prop(item, "stored_string", text=text)
                return item.stored_string
            elif item.stored_kind == "VEC2":
                row.prop(item, "stored_vec2", text=text)
                return item.stored_vec2
            elif item.stored_kind == "VEC3":
                row.prop(item, "stored_vec3", text=text)
                return item.stored_vec3
            elif item.stored_kind == "VEC4":
                row.prop(item, "stored_vec4", text=text)
                return item.stored_vec4
            elif item.stored_kind == "COLOR3":
                row.prop(item, "stored_color3", text=text)
                return item.stored_color3
            elif item.stored_kind == "COLOR4":
                row.prop(item, "stored_color4", text=text)
                return item.stored_color4
            elif item.stored_kind == "IDPROP":
                row.prop(item, "stored_json", text=text)
                return item.stored_json
            elif item.stored_kind == "ENUM":
                row.prop(item, "stored_enum", text=text)
                return item.stored_enum
            elif item.stored_kind == "POINTER":
                if item.stored_pointer_kind == "Action":
                    row.prop(item, "stored_action_pointer", text=text)
                    return item.stored_action_pointer
                elif item.stored_pointer_kind == "Camera":
                    row.prop(item, "stored_camera_pointer", text=text)
                    return item.stored_camera_pointer
            elif item.stored_kind == "NONE":
                return None

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
                    if hasattr(attr_value, "__len__") and len(attr_value) in (2, 3) and not is_color:
                        val_row.prop(obj, prop_token, index=0, text=text)
                        val_row.prop(obj, prop_token, index=1, text=text)
                        if len(attr_value) == 3:
                            val_row.prop(obj, prop_token, index=2, text=text)
                    else:
                        if arr_index != -1:
                            val_row.prop(obj, prop_token, index=arr_index, text=text)
                        else:
                            val_row.prop(obj, prop_token, text=text)
        except Exception as e:
            row = row.row()
            row.label(text=text)
            row.label(text=f"{e}", icon="ERROR")

    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        row = layout.row(align=True)

        # ---- ① 编号（极窄） ----
        num = row.row(align=True)
        num.alignment = "RIGHT"
        num.label(text=f"{index+1}:")

        # ---- ② 名称 ----
        name_col = row.row(align=True)
        name_col.prop(item, "name", text="", emboss=True, icon="BOOKMARKS")

        # ---- ③ 路径（可压缩）----
        if item.show_property_path:
            path_col = row.row(align=False)
            path_col.scale_x = 1.5
            path_col.prop(item, "property_path", text="")
        else:
            # ---- ④ 实际属性控件 ----
            if item.property_path:
                self.show_prop_path(row, item)
            self.show_stored(row, item, "")
            sync_row = row.row(align=True)
            op = sync_row.operator("param.sync_param", text="", icon="FILE_REFRESH")
            op.ParamIndex = index
        row = row.row(align=True)
        row.prop(item, "show_property_path", text="", icon="SCRIPT")


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
            col.label(text=translations("参数列表"))
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
        if len(scene.paramsnap_properties.ParamSnap_properties_coll) > 0:
            activite_Snap = scene.paramsnap_properties.ParamSnap_properties_coll[scene.paramsnap_properties.ParamSnap_properties_coll_index]
            if len(activite_Snap.Param_properties_coll) > 0:
                activite_params = activite_Snap.Param_properties_coll[activite_Snap.Param_properties_coll_index]
                box = col.box()
                # box.alert = True
                box.prop(activite_params, "name", text="参数名称")
                row = box.row()
                valid_path = resolve_ui_path(activite_params.property_path)[0]
                row.alert = not valid_path
                row.prop(activite_params, "property_path", text="属性路径")
                box.prop(activite_params, "stored_kind", text="数据类型")
                if activite_params.stored_kind == "POINTER":
                    box.prop(activite_params, "stored_pointer_kind", text="指针类型")
                col = box.column()
                obj, prop_token, arr_index = resolve_ui_path(activite_params.property_path)
                now_val = getattr(obj, prop_token)
                stored_val = PARAMS_UL_ParamList.show_stored(self, col, activite_params, "存储的值")
                type_valid = type(now_val) == type(stored_val)
                col.alert = type_valid
                PARAMS_UL_ParamList.show_prop_path(self, col, activite_params, "当前的值")
                PARAMS_UL_ParamList.show_stored(self, col, activite_params, "存储的值")

                # print(type(stored_val), type(now_val))
        col = layout.column(align=True)
        col.scale_y = 2.0
        col.operator("param.sync_all_params", text="同步所有参数", icon="FILE_REFRESH")


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
