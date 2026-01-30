import bpy
from .utils import *
import json


class PARAM_OT_TestOperator(bpy.types.Operator):
    bl_idname = "param.test_operator"
    bl_label = "测试操作"

    def execute(self, context):
        ParamSnap_properties_coll = context.scene.paramsnap_properties.ParamSnap_properties_coll
        ParamSnap_properties_coll_index = context.scene.paramsnap_properties.ParamSnap_properties_coll_index
        activite_snap = ParamSnap_properties_coll[ParamSnap_properties_coll_index]  # 活动的快照集合
        Param_properties_coll = activite_snap.Param_properties_coll
        Param_properties_coll_index = activite_snap.Param_properties_coll_index
        activite_item = Param_properties_coll[Param_properties_coll_index]
        path = 'bpy.data.objects["Cube"].modifiers["GeometryNodes"]["Socket_2"]'
        path = 'bpy.data.objects["BézierCurve"].modifiers["Curve"].object'
        path = 'bpy.data.objects["Cube.001"].modifiers["GeometryNodes"]["Socket_3"]'
        ptr, prop_token, index = resolve_ui_path(path)
        val = getattr(ptr, prop_token, None)
        # icon_value = bpy.types.UILayout.icon(val) if val else 0
        # prop_def = ptr.bl_rna.properties[prop_token]
        # print(pointer.bl_rna.fixed_type)
        # print(type(val).__name__)
        # print(rna)

        return {"FINISHED"}


class PARAM_OT_GenericAddItem(bpy.types.Operator):
    bl_idname = "param.add_item_generic"
    bl_label = "Add Item"
    bl_options = {"REGISTER", "UNDO"}

    # 定义接收路径的参数
    coll_path: bpy.props.StringProperty()
    index_path: bpy.props.StringProperty()

    def execute(self, context):
        # 使用 rna_path_resolve 动态获取集合对象和索引
        try:
            coll = context.path_resolve(self.coll_path)
            new_item = coll.add()
            path_parts = self.index_path.rsplit(".", 1)
            target_data = context.path_resolve(path_parts[0])
            prop_name = path_parts[1]

            setattr(target_data, prop_name, len(coll) - 1)

            return {"FINISHED"}
        except Exception as e:
            self.report({"ERROR"}, f"Path Error: {str(e)}")
            return {"CANCELLED"}


class PARAM_OT_GenericRemoveItem(bpy.types.Operator):
    bl_idname = "param.remove_item_generic"
    bl_label = "Remove Item"
    bl_options = {"REGISTER", "UNDO"}

    coll_path: bpy.props.StringProperty()
    index_path: bpy.props.StringProperty()

    def execute(self, context):
        try:
            coll = context.path_resolve(self.coll_path)

            # 获取当前索引
            path_parts = self.index_path.rsplit(".", 1)
            target_data = context.path_resolve(path_parts[0])
            prop_name = path_parts[1]
            idx = getattr(target_data, prop_name)

            if len(coll) > 0 and 0 <= idx < len(coll):
                coll.remove(idx)
                # 安全更新索引，防止越界
                setattr(target_data, prop_name, max(0, idx - 1))
                return {"FINISHED"}

            return {"CANCELLED"}
        except Exception as e:
            self.report({"ERROR"}, f"Remove Error: {str(e)}")
            return {"CANCELLED"}


class PARAM_OT_GenericMoveItem(bpy.types.Operator):
    bl_idname = "param.move_item_generic"
    bl_label = "Move Item"
    bl_options = {"REGISTER", "UNDO"}

    coll_path: bpy.props.StringProperty()
    index_path: bpy.props.StringProperty()
    # 方向参数：'UP' 或 'DOWN'
    direction: bpy.props.EnumProperty(items=[("UP", "Up", ""), ("DOWN", "Down", "")], default="UP")

    def execute(self, context):
        try:
            coll = context.path_resolve(self.coll_path)

            path_parts = self.index_path.rsplit(".", 1)
            target_data = context.path_resolve(path_parts[0])
            prop_name = path_parts[1]
            idx = getattr(target_data, prop_name)

            if self.direction == "UP" and idx > 0:
                coll.move(idx, idx - 1)
                setattr(target_data, prop_name, idx - 1)
            elif self.direction == "DOWN" and idx < len(coll) - 1:
                coll.move(idx, idx + 1)
                setattr(target_data, prop_name, idx + 1)

            return {"FINISHED"}
        except Exception as e:
            self.report({"ERROR"}, f"Move Error: {str(e)}")
            return {"CANCELLED"}


class PARAMS_OT_AddParamToCol(bpy.types.Operator):
    bl_idname = "param.add_param_to_col"
    bl_label = "Add Param to Col"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        # 获取数据路径
        bpy.ops.ui.copy_data_path_button(full_path=True)
        full_path = context.window_manager.clipboard
        ParamSnap_properties_coll = context.scene.paramsnap_properties.ParamSnap_properties_coll
        ParamSnap_properties_coll_index = context.scene.paramsnap_properties.ParamSnap_properties_coll_index
        if len(ParamSnap_properties_coll) == 0:
            bpy.ops.param.add_item_generic(coll_path="scene.paramsnap_properties.ParamSnap_properties_coll", index_path="scene.paramsnap_properties.ParamSnap_properties_coll_index")
        activite_snap = ParamSnap_properties_coll[ParamSnap_properties_coll_index]  # 活动的快照集合
        Param_properties_coll = activite_snap.Param_properties_coll
        new_item = Param_properties_coll.add()
        new_item.name = get_ui_name_from_path(full_path)
        new_item.property_path = full_path
        activite_snap.Param_properties_coll_index = len(Param_properties_coll) - 1
        self.report({"INFO"}, f"Added Parameter to ParamSnap {new_item.name}")
        # 刷新界面
        for area in context.screen.areas:
            area.tag_redraw()

        value_copy, type_tag, meta = get_value_and_type_from_path(new_item.property_path)
        assign_stored_from_value(new_item, value_copy, type_tag, meta)
        return {"FINISHED"}


class PARAM_OT_SyncParamOperator(bpy.types.Operator):
    bl_idname = "param.sync_param"
    bl_label = "同步参数"
    bl_options = {"REGISTER", "UNDO"}
    bl_description = "将当前值设置为存储值"

    ParamIndex: bpy.props.IntProperty()

    def execute(self, context):
        ParamSnap_properties_coll = context.scene.paramsnap_properties.ParamSnap_properties_coll
        ParamSnap_properties_coll_index = context.scene.paramsnap_properties.ParamSnap_properties_coll_index
        activite_snap = ParamSnap_properties_coll[ParamSnap_properties_coll_index]  # 指定的快照集合
        param_item = activite_snap.Param_properties_coll[self.ParamIndex]  # 指定的参数项
        try:
            flag = apply_stored_to_target(param_item)
            if flag == None:
                self.report({"ERROR"}, f"同步失败: {param_item.name}")
            elif flag == 2:
                self.report({"WARNING"}, f"动作槽为空: {param_item.name}")
            # 立即刷新视图
            for area in context.screen.areas:
                area.tag_redraw()
        except Exception as e:
            # self.report({"ERROR"}, f"同步失败: {param_item.name},{e}")
            return {"CANCELLED"}
        return {"FINISHED"}


class PARAM_OT_SyncAllParamsOperator(bpy.types.Operator):
    bl_idname = "param.sync_all_params"
    bl_label = "同步所有参数"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        coll = context.scene.paramsnap_properties.ParamSnap_properties_coll[context.scene.paramsnap_properties.ParamSnap_properties_coll_index]
        for i in range(len(coll.Param_properties_coll)):
            try:
                bpy.ops.param.sync_param(ParamIndex=i)
            except Exception as e:
                self.report({"ERROR"}, f"{e}")
        # 刷新界面
        for area in context.screen.areas:
            area.tag_redraw()
        return {"FINISHED"}


class PARAM_OT_CopySnapshot(bpy.types.Operator):
    bl_idname = "param.copy_snapshot"
    bl_label = "复制快照"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        Snapshot_coll = context.scene.paramsnap_properties.ParamSnap_properties_coll
        activite_snapshot = context.scene.paramsnap_properties.ParamSnap_properties_coll[context.scene.paramsnap_properties.ParamSnap_properties_coll_index]
        copy_coll = Snapshot_coll.add()
        for i in range(len(activite_snapshot.Param_properties_coll)):
            # print(activite_snapshot.Param_properties_coll[i].name)
            copy_param = copy_coll.Param_properties_coll.add()
            param = activite_snapshot.Param_properties_coll[i]
            for prop in param.bl_rna.properties:
                id = prop.identifier
                if id == "rna_type" or prop.is_readonly:
                    continue
                try:
                    setattr(copy_param, id, getattr(param, id))
                except Exception as e:
                    print(f"复制快照{param.name}失败: {e}")
                    pass
            copy_coll.Param_properties_coll_index = activite_snapshot.Param_properties_coll_index

        # 刷新界面
        for area in context.screen.areas:
            area.tag_redraw()
        return {"FINISHED"}


# TODO 更新存储值
class PARAM_OT_UpdateStoredValue(bpy.types.Operator):
    bl_idname = "param.update_stored_value"
    bl_label = "更新存储值"
    bl_options = {"REGISTER", "UNDO"}
    bl_description = "将当前值设置为存储值"

    ParamIndex: bpy.props.IntProperty()

    def execute(self, context):
        ParamSnap_properties_coll = context.scene.paramsnap_properties.ParamSnap_properties_coll
        ParamSnap_properties_coll_index = context.scene.paramsnap_properties.ParamSnap_properties_coll_index
        activite_snap = ParamSnap_properties_coll[ParamSnap_properties_coll_index]  # 指定的快照集合
        param_item = activite_snap.Param_properties_coll[self.ParamIndex]  # 指定的参数项
        prop_name = stored_kind_to_property_name(param_item.stored_kind, param_item.stored_pointer_kind)
        val, type, meta = get_value_and_type_from_path(param_item.property_path)
        setattr(param_item, prop_name, val)
        if param_item.stored_kind == "POINTER" and param_item.stored_pointer_kind == "Action":
            slot_val, type, meta = get_value_and_type_from_path(param_item.property_path.rsplit(".", 1)[0] + ".action_slot")
            if slot_val:
                setattr(param_item, "stored_action_slots", slot_val.name_display)
        return {"FINISHED"}


class PARAM_OT_SwapParam(bpy.types.Operator):
    bl_idname = "param.swap_param"
    bl_label = "交换参数"
    bl_options = {"REGISTER", "UNDO"}
    bl_description = "交换当前值和存储值"

    ParamIndex: bpy.props.IntProperty()

    def execute(self, context):
        ParamSnap_properties_coll = context.scene.paramsnap_properties.ParamSnap_properties_coll
        ParamSnap_properties_coll_index = context.scene.paramsnap_properties.ParamSnap_properties_coll_index
        activite_snap = ParamSnap_properties_coll[ParamSnap_properties_coll_index]  # 指定的快照集合
        param_item = activite_snap.Param_properties_coll[self.ParamIndex]  # 指定的参数项
        ptr, prop_token, index = resolve_ui_path(param_item.property_path)
        current_val = getattr(ptr, prop_token, None)
        if isinstance(current_val, bpy.types.ID):
            current_val = current_val  # 指针类型先保持（你后面 assign_stored_from_value 会处理）
        elif hasattr(current_val, "__len__") and not isinstance(current_val, (str, bytes, bytearray)):
            current_val = tuple(current_val)  # vec/color/array 冻结成 tuple
        # print(f"当前值: {(current_val)},存储值: {(get_param_stored_val(param_item))}")
        slot_name = None
        if param_item.stored_kind == "POINTER" and param_item.stored_pointer_kind == "Action":
            slot_val, type, meta = get_value_and_type_from_path(param_item.property_path.rsplit(".", 1)[0] + ".action_slot")
            if slot_val:
                slot_name = slot_val.name_display

        flag = apply_stored_to_target(param_item)
        meta = json.loads(param_item.meta)
        if param_item.stored_kind == "POINTER":
            meta["fixed_type"] = param_item.stored_pointer_kind
        # print("meta:", meta)
        # print(f"111当前值: {(current_val)},存储值: {(get_param_stored_val(param_item))}")
        assign_stored_from_value(param_item, current_val, param_item.stored_kind, meta)
        if param_item.stored_kind == "POINTER" and param_item.stored_pointer_kind == "Action":
            if not slot_name:
                slot_name = ""
            setattr(param_item, "stored_action_slots", slot_name)
        if flag == None:
            self.report({"ERROR"}, f"同步失败: {param_item.name}")
        elif flag == 2:
            self.report({"WARNING"}, f"动作槽为空: {param_item.name}")
        # 立即刷新视图
        for area in context.screen.areas:
            area.tag_redraw()
        try:
            pass
        except Exception as e:
            print(f"交换参数{param_item.name}失败: {e}")
            return {"CANCELLED"}
        return {"FINISHED"}


class PARAM_OT_AddActionToParam(bpy.types.Operator):
    bl_idname = "param.add_action_to_param"
    bl_label = "Add Action to Param"
    bl_options = {"REGISTER", "UNDO"}

    name: bpy.props.StringProperty()
    path: bpy.props.StringProperty()

    def execute(self, context):
        self.report({"INFO"}, f"Added Action to Param {self.name}, {self.path}")
        ParamSnap_properties_coll = context.scene.paramsnap_properties.ParamSnap_properties_coll
        ParamSnap_properties_coll_index = context.scene.paramsnap_properties.ParamSnap_properties_coll_index
        if len(ParamSnap_properties_coll) == 0:
            bpy.ops.param.add_item_generic(coll_path="scene.paramsnap_properties.ParamSnap_properties_coll", index_path="scene.paramsnap_properties.ParamSnap_properties_coll_index")
        activite_snap = ParamSnap_properties_coll[ParamSnap_properties_coll_index]  # 活动的快照集合
        param = activite_snap.Param_properties_coll.add()
        param.name = self.name + "_animation"
        param.property_path = self.path
        param.stored_kind = "POINTER"
        param.stored_pointer_kind = "Action"
        val, type, meta = get_value_and_type_from_path(param.property_path)
        setattr(param, "stored_action_pointer", val)
        slot_val, type, meta = get_value_and_type_from_path(param.property_path.rsplit(".", 1)[0] + ".action_slot")
        if slot_val:
            setattr(param, "stored_action_slots", slot_val.name_display)
        activite_snap.Param_properties_coll_index = len(activite_snap.Param_properties_coll) - 1
        for area in context.screen.areas:
            area.tag_redraw()
        return {"FINISHED"}


def register():
    bpy.utils.register_class(PARAM_OT_TestOperator)
    bpy.utils.register_class(PARAM_OT_GenericAddItem)
    bpy.utils.register_class(PARAM_OT_GenericRemoveItem)
    bpy.utils.register_class(PARAM_OT_GenericMoveItem)
    bpy.utils.register_class(PARAMS_OT_AddParamToCol)
    bpy.utils.register_class(PARAM_OT_SyncParamOperator)
    bpy.utils.register_class(PARAM_OT_SyncAllParamsOperator)
    bpy.utils.register_class(PARAM_OT_CopySnapshot)
    bpy.utils.register_class(PARAM_OT_UpdateStoredValue)
    bpy.utils.register_class(PARAM_OT_AddActionToParam)
    bpy.utils.register_class(PARAM_OT_SwapParam)


def unregister():
    bpy.utils.unregister_class(PARAM_OT_TestOperator)
    bpy.utils.unregister_class(PARAM_OT_GenericAddItem)
    bpy.utils.unregister_class(PARAM_OT_GenericRemoveItem)
    bpy.utils.unregister_class(PARAM_OT_GenericMoveItem)
    bpy.utils.unregister_class(PARAMS_OT_AddParamToCol)
    bpy.utils.unregister_class(PARAM_OT_SyncParamOperator)
    bpy.utils.unregister_class(PARAM_OT_SyncAllParamsOperator)
    bpy.utils.unregister_class(PARAM_OT_CopySnapshot)
    bpy.utils.unregister_class(PARAM_OT_UpdateStoredValue)
    bpy.utils.unregister_class(PARAM_OT_AddActionToParam)
    bpy.utils.unregister_class(PARAM_OT_SwapParam)
