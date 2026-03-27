import bpy
from bpy_extras.io_utils import ExportHelper, ImportHelper
from .utils import *
import json
from .i18n import translatef


def get_active_snapshot(context):
    scene_props = context.scene.paramsnap_properties
    snapshot_coll = scene_props.ParamSnap_properties_coll
    if len(snapshot_coll) == 0:
        return None
    snap_index = max(0, min(scene_props.ParamSnap_properties_coll_index, len(snapshot_coll) - 1))
    scene_props.ParamSnap_properties_coll_index = snap_index
    return snapshot_coll[snap_index]


def get_active_param(context):
    snapshot = get_active_snapshot(context)
    if snapshot is None:
        return None

    param_coll = snapshot.Param_properties_coll
    if len(param_coll) == 0:
        return None

    param_index = max(0, min(snapshot.Param_properties_coll_index, len(param_coll) - 1))
    snapshot.Param_properties_coll_index = param_index
    return param_coll[param_index]


def redraw_areas(context):
    for area in context.screen.areas:
        area.tag_redraw()


def import_snapshots_from_payload(context, payload):
    scene_props = context.scene.paramsnap_properties
    snapshot_coll = scene_props.ParamSnap_properties_coll
    snapshot_payloads = extract_snapshot_payloads(payload)

    imported_count = 0
    skipped_params = 0
    for snapshot_data in snapshot_payloads:
        snapshot_item = snapshot_coll.add()
        try:
            skipped_params += apply_serialized_snapshot_item(snapshot_item, snapshot_data)
        except Exception:
            snapshot_coll.remove(len(snapshot_coll) - 1)
            continue
        scene_props.ParamSnap_properties_coll_index = len(snapshot_coll) - 1
        imported_count += 1

    redraw_areas(context)
    return imported_count, skipped_params


class PARAM_OT_GenericAddItem(bpy.types.Operator):
    bl_idname = "param.add_item_generic"
    bl_label = "Add Item"
    bl_options = {"REGISTER", "UNDO"}
    bl_description = "Add Item"

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
    bl_description = "Remove Item"

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
    bl_description = "Move Item"

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


class PARAM_OT_GenericMoveItemToEnd(bpy.types.Operator):
    bl_idname = "param.move_item_to_end_generic"
    bl_label = "Move Item To End"
    bl_options = {"REGISTER", "UNDO"}
    bl_description = "Move Item To End"

    coll_path: bpy.props.StringProperty()
    index_path: bpy.props.StringProperty()

    # 移动到最顶端还是最底端
    where: bpy.props.EnumProperty(
        items=[
            ("TOP", "Top", "Move to the first position"),
            ("BOTTOM", "Bottom", "Move to the last position"),
        ],
        default="TOP",
    )

    def execute(self, context):
        try:
            coll = context.path_resolve(self.coll_path)

            path_parts = self.index_path.rsplit(".", 1)
            target_data = context.path_resolve(path_parts[0])
            prop_name = path_parts[1]
            idx = getattr(target_data, prop_name)

            n = len(coll)
            if n <= 1:
                return {"CANCELLED"}

            # 目标位置
            new_idx = 0 if self.where == "TOP" else (n - 1)

            # 如果已经在目标位置，直接结束
            if idx == new_idx:
                return {"FINISHED"}

            # move(from, to)
            coll.move(idx, new_idx)
            setattr(target_data, prop_name, new_idx)

            return {"FINISHED"}

        except Exception as e:
            self.report({"ERROR"}, f"Move Error: {str(e)}")
            return {"CANCELLED"}


class PARAMS_OT_AddParamToCol(bpy.types.Operator):
    bl_idname = "param.add_param_to_col"
    bl_label = "Add Parameter to Snapshot"
    bl_options = {"REGISTER", "UNDO"}
    bl_description = "Add the selected property to the active snapshot"

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
        new_item = None
        has = False
        for i in range(len(Param_properties_coll)):
            if param_targets_match(Param_properties_coll[i], full_path):
                new_item = Param_properties_coll[i]
                has = True
                activite_snap.Param_properties_coll_index = i
                new_item.property_path = full_path
                print(translatef("Parameter already exists"))
                break
        if not has:
            new_item = Param_properties_coll.add()
            new_item.name = get_ui_name_from_path(full_path)
            new_item.property_path = full_path
            activite_snap.Param_properties_coll_index = len(Param_properties_coll) - 1
        value_copy, type_tag, meta, resolved_path = get_value_and_type_from_param_item(new_item)
        assign_stored_from_value(new_item, value_copy, type_tag, meta)
        self.report({"INFO"}, translatef("Added parameter to ParamSnap: {name}", name=new_item.name))
        # 刷新界面
        for area in context.screen.areas:
            area.tag_redraw()
        return {"FINISHED"}


class PARAM_OT_SyncParamOperator(bpy.types.Operator):
    bl_idname = "param.sync_param"
    bl_label = "Sync"
    bl_options = {"REGISTER", "UNDO"}
    bl_description = "Apply stored value to the current property"

    ParamIndex: bpy.props.IntProperty()

    def execute(self, context):
        ParamSnap_properties_coll = context.scene.paramsnap_properties.ParamSnap_properties_coll
        ParamSnap_properties_coll_index = context.scene.paramsnap_properties.ParamSnap_properties_coll_index
        activite_snap = ParamSnap_properties_coll[ParamSnap_properties_coll_index]  # 指定的快照集合
        param_item = activite_snap.Param_properties_coll[self.ParamIndex]  # 指定的参数项
        try:
            flag = apply_stored_to_target(param_item)
            if flag == None:
                self.report({"ERROR"}, translatef("Failed to sync parameter: {name}", name=param_item.name))
            elif flag == 2:
                self.report({"WARNING"}, translatef("Action slot is empty: {name}", name=param_item.name))
            # 立即刷新视图
            for area in context.screen.areas:
                area.tag_redraw()
        except Exception as e:
            # self.report({"ERROR"}, f"同步失败: {param_item.name},{e}")
            return {"CANCELLED"}
        return {"FINISHED"}


class PARAM_OT_SyncAllParamsOperator(bpy.types.Operator):
    bl_idname = "param.sync_all_params"
    bl_label = "Sync All Parameters"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        coll = context.scene.paramsnap_properties.ParamSnap_properties_coll[context.scene.paramsnap_properties.ParamSnap_properties_coll_index]
        for i in range(len(coll.Param_properties_coll)):
            enable = coll.Param_properties_coll[i].enable
            if not enable:
                continue
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
    bl_label = "Copy Snapshot"
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
                    print(f"Copy snapshot {param.name} failed: {e}")
                    pass
            copy_coll.Param_properties_coll_index = activite_snapshot.Param_properties_coll_index
        context.scene.paramsnap_properties.ParamSnap_properties_coll_index = len(Snapshot_coll) - 1

        # 刷新界面
        redraw_areas(context)
        return {"FINISHED"}


class PARAM_OT_ExportSnapshotJson(bpy.types.Operator, ExportHelper):
    bl_idname = "param.export_snapshot_json"
    bl_label = "Export JSON"
    bl_description = "Export the selected snapshot as a JSON file"

    filename_ext = ".json"
    filter_glob: bpy.props.StringProperty(default="*.json", options={"HIDDEN"})

    def invoke(self, context, event):
        snapshot = get_active_snapshot(context)
        if snapshot is None:
            self.report({"ERROR"}, translatef("No snapshot available to export"))
            return {"CANCELLED"}

        clean_name = bpy.path.clean_name(snapshot.name or "Snapshot")
        self.filepath = f"{clean_name}{self.filename_ext}"
        context.window_manager.fileselect_add(self)
        return {"RUNNING_MODAL"}

    def execute(self, context):
        snapshot = get_active_snapshot(context)
        if snapshot is None:
            self.report({"ERROR"}, translatef("No snapshot available to export"))
            return {"CANCELLED"}

        payload = build_snapshot_export_payload(snapshot)
        try:
            with open(self.filepath, "w", encoding="utf-8") as file:
                json.dump(payload, file, ensure_ascii=False, indent=2)
        except Exception as exc:
            self.report({"ERROR"}, translatef("Failed to export snapshot: {error}", error=exc))
            return {"CANCELLED"}

        self.report({"INFO"}, translatef("Snapshot exported: {name}", name=snapshot.name))
        return {"FINISHED"}


class PARAM_OT_CopySnapshotJson(bpy.types.Operator):
    bl_idname = "param.copy_snapshot_json"
    bl_label = "Copy JSON"
    bl_description = "Copy the selected snapshot to the clipboard as JSON"

    def execute(self, context):
        snapshot = get_active_snapshot(context)
        if snapshot is None:
            self.report({"ERROR"}, translatef("No snapshot available to copy"))
            return {"CANCELLED"}

        payload = build_snapshot_export_payload(snapshot)
        context.window_manager.clipboard = json.dumps(payload, ensure_ascii=False, indent=2)
        self.report({"INFO"}, translatef("Snapshot JSON copied: {name}", name=snapshot.name))
        return {"FINISHED"}


class PARAM_OT_ImportSnapshotJson(bpy.types.Operator, ImportHelper):
    bl_idname = "param.import_snapshot_json"
    bl_label = "Import JSON"
    bl_options = {"REGISTER", "UNDO"}
    bl_description = "Import snapshots from a JSON file and select the imported snapshot"

    filename_ext = ".json"
    filter_glob: bpy.props.StringProperty(default="*.json", options={"HIDDEN"})

    def execute(self, context):
        try:
            with open(self.filepath, "r", encoding="utf-8") as file:
                payload = json.load(file)
        except Exception as exc:
            self.report({"ERROR"}, translatef("Failed to read JSON: {error}", error=exc))
            return {"CANCELLED"}

        try:
            imported_count, skipped_params = import_snapshots_from_payload(context, payload)
        except Exception as exc:
            self.report({"ERROR"}, translatef("Failed to import snapshots: {error}", error=exc))
            return {"CANCELLED"}

        if imported_count == 0:
            self.report({"ERROR"}, translatef("No snapshots were imported"))
            return {"CANCELLED"}

        level = {"WARNING"} if skipped_params else {"INFO"}
        self.report(level, translatef("Imported {count} snapshot(s), skipped {skipped} invalid parameter(s)", count=imported_count, skipped=skipped_params))
        return {"FINISHED"}


class PARAM_OT_PasteSnapshotJson(bpy.types.Operator):
    bl_idname = "param.paste_snapshot_json"
    bl_label = "Paste JSON"
    bl_options = {"REGISTER", "UNDO"}
    bl_description = "Import snapshots from the clipboard and select the imported snapshot"

    def execute(self, context):
        clipboard = context.window_manager.clipboard
        if not clipboard.strip():
            self.report({"ERROR"}, translatef("Clipboard is empty"))
            return {"CANCELLED"}

        try:
            payload = json.loads(clipboard)
        except Exception as exc:
            self.report({"ERROR"}, translatef("Clipboard does not contain valid JSON: {error}", error=exc))
            return {"CANCELLED"}

        try:
            imported_count, skipped_params = import_snapshots_from_payload(context, payload)
        except Exception as exc:
            self.report({"ERROR"}, translatef("Failed to import snapshots: {error}", error=exc))
            return {"CANCELLED"}

        if imported_count == 0:
            self.report({"ERROR"}, translatef("No snapshots were imported"))
            return {"CANCELLED"}

        level = {"WARNING"} if skipped_params else {"INFO"}
        self.report(
            level,
            translatef(
                "Imported {count} snapshot(s) from the clipboard, skipped {skipped} invalid parameter(s)",
                count=imported_count,
                skipped=skipped_params,
            ),
        )
        return {"FINISHED"}


class PARAM_OT_ResolvePathConflict(bpy.types.Operator):
    bl_idname = "param.resolve_path_conflict"
    bl_label = "Resolve Path Conflict"
    bl_options = {"REGISTER", "UNDO"}
    bl_description = "Resolve the mismatch between the property path and the datablock reference"

    mode: bpy.props.EnumProperty(
        items=[
            ("STABLE", "Use Datablock Reference", ""),
            ("PROPERTY", "Use Property Path", ""),
        ],
        default="STABLE",
    )

    def execute(self, context):
        param_item = get_active_param(context)
        if param_item is None:
            self.report({"ERROR"}, translatef("No parameter available to resolve"))
            return {"CANCELLED"}

        path_state = get_param_path_state(param_item)
        if self.mode == "STABLE":
            target_path = path_state["stable_path"]
            if not target_path:
                self.report({"ERROR"}, translatef("Datablock reference is unavailable: {name}", name=param_item.name))
                return {"CANCELLED"}
            if not path_state["stable_valid"]:
                self.report({"ERROR"}, translatef("Datablock reference cannot be resolved: {name}", name=param_item.name))
                return {"CANCELLED"}

            param_item.property_path = target_path
            rebuild_param_target_reference(param_item, target_path)
            self.report({"INFO"}, translatef("Conflict resolved with the datablock reference: {name}", name=param_item.name))
        else:
            target_path = path_state["property_path"]
            if not target_path:
                self.report({"ERROR"}, translatef("Property path is unavailable: {name}", name=param_item.name))
                return {"CANCELLED"}
            if not path_state["property_valid"]:
                self.report({"ERROR"}, translatef("Property path cannot be resolved: {name}", name=param_item.name))
                return {"CANCELLED"}
            if not rebuild_param_target_reference(param_item, target_path):
                self.report({"ERROR"}, translatef("Property path cannot be resolved: {name}", name=param_item.name))
                return {"CANCELLED"}

            self.report({"INFO"}, translatef("Conflict resolved with the property path: {name}", name=param_item.name))

        redraw_areas(context)
        return {"FINISHED"}


class PARAM_OT_ResolveAllPathConflicts(bpy.types.Operator):
    bl_idname = "param.resolve_all_path_conflicts"
    bl_label = "Resolve All Conflicts"
    bl_options = {"REGISTER", "UNDO"}
    bl_description = "Resolve all path conflicts in the active snapshot"

    def execute(self, context):
        snapshot = get_active_snapshot(context)
        if snapshot is None:
            self.report({"ERROR"}, translatef("No snapshot available to resolve conflicts"))
            return {"CANCELLED"}

        total_conflicts = 0
        resolved_conflicts = 0
        failed_conflicts = 0

        for param_item in snapshot.Param_properties_coll:
            path_state = get_param_path_state(param_item)
            if not path_state["has_conflict"]:
                continue

            total_conflicts += 1
            target_path = ""
            preferred_mode = path_state.get("recommended_mode", "NONE")

            if preferred_mode == "PROPERTY":
                if path_state["property_valid"] and path_state["property_path"]:
                    target_path = path_state["property_path"]
                elif path_state["stable_valid"] and path_state["stable_path"]:
                    target_path = path_state["stable_path"]
            else:
                if path_state["stable_valid"] and path_state["stable_path"]:
                    target_path = path_state["stable_path"]
                elif path_state["property_valid"] and path_state["property_path"]:
                    target_path = path_state["property_path"]

            if not target_path:
                failed_conflicts += 1
                continue

            try:
                param_item.property_path = target_path
                rebuild_param_target_reference(param_item, target_path)
                resolved_conflicts += 1
            except Exception:
                failed_conflicts += 1

        redraw_areas(context)

        if total_conflicts == 0:
            self.report({"INFO"}, translatef("No conflicts found in the active snapshot"))
            return {"FINISHED"}

        level = {"INFO"} if failed_conflicts == 0 else {"WARNING"}
        self.report(
            level,
            translatef(
                "Resolved {resolved} of {total} conflict(s), failed {failed}",
                resolved=resolved_conflicts,
                total=total_conflicts,
                failed=failed_conflicts,
            ),
        )
        return {"FINISHED"}


class PARAM_OT_UpdateStoredValue(bpy.types.Operator):
    bl_idname = "param.update_stored_value"
    bl_label = "Update Stored Value"
    bl_options = {"REGISTER", "UNDO"}
    bl_description = "Capture the current property value as the stored value"

    ParamIndex: bpy.props.IntProperty()

    def execute(self, context):
        ParamSnap_properties_coll = context.scene.paramsnap_properties.ParamSnap_properties_coll
        ParamSnap_properties_coll_index = context.scene.paramsnap_properties.ParamSnap_properties_coll_index
        activite_snap = ParamSnap_properties_coll[ParamSnap_properties_coll_index]  # 指定的快照集合
        param_item = activite_snap.Param_properties_coll[self.ParamIndex]  # 指定的参数项
        prop_name = stored_kind_to_property_name(param_item.stored_kind, param_item.stored_pointer_kind)
        val, type, meta, resolved_path = get_value_and_type_from_param_item(param_item)
        if not prop_name or type is None:
            self.report({"ERROR"}, translatef("Failed to update stored value: {name}", name=param_item.name))
            return {"CANCELLED"}
        setattr(param_item, prop_name, val)
        if param_item.stored_kind == "POINTER" and param_item.stored_pointer_kind == "Action":
            slot_path = build_action_slot_path(param_item)
            slot_val, type, meta = get_value_and_type_from_path(slot_path) if slot_path else (None, None, {})
            if slot_val:
                setattr(param_item, "stored_action_slots", slot_val.name_display)
        return {"FINISHED"}


class PARAM_OT_UpdateAllStoredValue(bpy.types.Operator):
    bl_idname = "param.update_all_stored_value"
    bl_label = "Update All Stored Values"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        coll = context.scene.paramsnap_properties.ParamSnap_properties_coll[context.scene.paramsnap_properties.ParamSnap_properties_coll_index]
        for i in range(len(coll.Param_properties_coll)):
            enable = coll.Param_properties_coll[i].enable
            if not enable:
                continue
            try:
                bpy.ops.param.update_stored_value(ParamIndex=i)
            except Exception as e:
                self.report({"ERROR"}, f"{e}")
        # 刷新界面
        for area in context.screen.areas:
            area.tag_redraw()
        return {"FINISHED"}


class PARAM_OT_SwapParam(bpy.types.Operator):
    bl_idname = "param.swap_param"
    bl_label = "Swap Parameter"
    bl_options = {"REGISTER", "UNDO"}
    bl_description = "Swap the current property value and stored value"

    ParamIndex: bpy.props.IntProperty()

    def execute(self, context):
        ParamSnap_properties_coll = context.scene.paramsnap_properties.ParamSnap_properties_coll
        ParamSnap_properties_coll_index = context.scene.paramsnap_properties.ParamSnap_properties_coll_index
        activite_snap = ParamSnap_properties_coll[ParamSnap_properties_coll_index]  # 指定的快照集合
        param_item = activite_snap.Param_properties_coll[self.ParamIndex]  # 指定的参数项
        ptr, prop_token, index, resolved_path = resolve_param_item_path(param_item)
        if ptr is None or prop_token is None:
            self.report({"ERROR"}, translatef("Failed to resolve parameter path: {name}", name=param_item.name))
            return {"CANCELLED"}
        current_val = getattr(ptr, prop_token, None)
        if isinstance(current_val, bpy.types.ID):
            current_val = current_val  # 指针类型先保持（你后面 assign_stored_from_value 会处理）
        elif hasattr(current_val, "__len__") and not isinstance(current_val, (str, bytes, bytearray)):
            current_val = tuple(current_val)  # vec/color/array 冻结成 tuple
        # print(f"当前值: {(current_val)},存储值: {(get_param_stored_val(param_item))}")
        slot_name = None
        if param_item.stored_kind == "POINTER" and param_item.stored_pointer_kind == "Action":
            slot_path = build_action_slot_path(param_item)
            slot_val, type, meta = get_value_and_type_from_path(slot_path) if slot_path else (None, None, {})
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
            self.report({"ERROR"}, translatef("Failed to sync parameter: {name}", name=param_item.name))
        elif flag == 2:
            self.report({"WARNING"}, translatef("Action slot is empty: {name}", name=param_item.name))
        # 立即刷新视图
        for area in context.screen.areas:
            area.tag_redraw()
        try:
            pass
        except Exception as e:
            print(f"Swap parameter {param_item.name} failed: {e}")
            return {"CANCELLED"}
        return {"FINISHED"}


class PARAM_OT_SwapAllParam(bpy.types.Operator):
    bl_idname = "param.swap_all_param"
    bl_label = "Swap All Parameters"
    bl_options = {"REGISTER", "UNDO"}
    bl_description = "Swap all enabled parameters"

    def execute(self, context):
        coll = context.scene.paramsnap_properties.ParamSnap_properties_coll[context.scene.paramsnap_properties.ParamSnap_properties_coll_index]
        for i in range(len(coll.Param_properties_coll)):
            enable = coll.Param_properties_coll[i].enable
            if not enable:
                continue
            try:
                bpy.ops.param.swap_param(ParamIndex=i)
            except Exception as e:
                self.report({"ERROR"}, f"{e}")
        # 刷新界面
        for area in context.screen.areas:
            area.tag_redraw()
        return {"FINISHED"}


class PARAM_OT_AddActionToParam(bpy.types.Operator):
    bl_idname = "param.add_action_to_param"
    bl_label = "Add Action Parameter"
    bl_options = {"REGISTER", "UNDO"}

    name: bpy.props.StringProperty()
    path: bpy.props.StringProperty()

    def execute(self, context):
        self.report({"INFO"}, translatef("Added action parameter: {name}", name=self.name))
        ParamSnap_properties_coll = context.scene.paramsnap_properties.ParamSnap_properties_coll
        ParamSnap_properties_coll_index = context.scene.paramsnap_properties.ParamSnap_properties_coll_index
        if len(ParamSnap_properties_coll) == 0:
            bpy.ops.param.add_item_generic(coll_path="scene.paramsnap_properties.ParamSnap_properties_coll", index_path="scene.paramsnap_properties.ParamSnap_properties_coll_index")
        activite_snap = ParamSnap_properties_coll[ParamSnap_properties_coll_index]  # 活动的快照集合
        snap_coll = activite_snap.Param_properties_coll
        param = None
        has = False
        for i in range(len(snap_coll)):
            if param_targets_match(snap_coll[i], self.path):
                param = snap_coll[i]
                has = True
                activite_snap.Param_properties_coll_index = i
                param.property_path = self.path
                print(translatef("Parameter already exists"))
                break
        if not has:
            param = snap_coll.add()
            param.name = self.name + "_animation"
            param.property_path = self.path
            param.stored_kind = "POINTER"
            param.stored_pointer_kind = "Action"
            activite_snap.Param_properties_coll_index = len(snap_coll) - 1
        val, type, meta, resolved_path = get_value_and_type_from_param_item(param)
        setattr(param, "stored_action_pointer", val)
        slot_path = build_action_slot_path(param)
        slot_val, type, meta = get_value_and_type_from_path(slot_path) if slot_path else (None, None, {})
        if slot_val:
            setattr(param, "stored_action_slots", slot_val.name_display)

        for area in context.screen.areas:
            area.tag_redraw()
        return {"FINISHED"}


class PARAM_OT_InverEnable(bpy.types.Operator):
    bl_idname = "param.inver_enable"
    bl_label = "Invert Selection"
    bl_options = {"REGISTER", "UNDO"}
    bl_description = "Invert the enabled state of all parameters in the active snapshot"

    def execute(self, context):
        ParamSnap_properties_coll = context.scene.paramsnap_properties.ParamSnap_properties_coll
        ParamSnap_properties_coll_index = context.scene.paramsnap_properties.ParamSnap_properties_coll_index
        activite_snap = ParamSnap_properties_coll[ParamSnap_properties_coll_index]
        for i in range(len(activite_snap.Param_properties_coll)):
            activite_snap.Param_properties_coll[i].enable = not activite_snap.Param_properties_coll[i].enable
        for area in context.screen.areas:
            area.tag_redraw()
        return {"FINISHED"}


classes = [
    PARAM_OT_GenericAddItem,
    PARAM_OT_GenericRemoveItem,
    PARAM_OT_GenericMoveItem,
    PARAM_OT_GenericMoveItemToEnd,
    PARAMS_OT_AddParamToCol,
    PARAM_OT_SyncParamOperator,
    PARAM_OT_SyncAllParamsOperator,
    PARAM_OT_CopySnapshot,
    PARAM_OT_ExportSnapshotJson,
    PARAM_OT_CopySnapshotJson,
    PARAM_OT_ImportSnapshotJson,
    PARAM_OT_PasteSnapshotJson,
    PARAM_OT_ResolvePathConflict,
    PARAM_OT_ResolveAllPathConflicts,
    PARAM_OT_UpdateStoredValue,
    PARAM_OT_UpdateAllStoredValue,
    PARAM_OT_AddActionToParam,
    PARAM_OT_SwapParam,
    PARAM_OT_SwapAllParam,
    PARAM_OT_InverEnable,
]


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
