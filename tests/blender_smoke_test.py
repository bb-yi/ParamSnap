"""
Run with:
    blender --background --factory-startup --python tests/blender_smoke_test.py --python-exit-code 1
"""

from __future__ import annotations

import math
import os
import sys
import traceback

import bpy


REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

import ParamSnap
from ParamSnap import utils
from ParamSnap import ui


PREFIX = "PS_TEST_"


def log(message: str):
    print(f"[ParamSnapTest] {message}")


def fail(message: str):
    raise AssertionError(message)


def assert_true(condition: bool, message: str):
    if not condition:
        fail(message)


def assert_equal(actual, expected, message: str):
    if actual != expected:
        fail(f"{message}: expected {expected!r}, got {actual!r}")


def assert_close(actual: float, expected: float, message: str, tol: float = 1e-6):
    if not math.isclose(actual, expected, rel_tol=tol, abs_tol=tol):
        fail(f"{message}: expected {expected!r}, got {actual!r}")


def assert_sequence_close(actual, expected, message: str, tol: float = 1e-6):
    actual_list = list(actual)
    expected_list = list(expected)
    if len(actual_list) != len(expected_list):
        fail(f"{message}: length mismatch {len(actual_list)} != {len(expected_list)}")
    for index, (a, b) in enumerate(zip(actual_list, expected_list)):
        if not math.isclose(float(a), float(b), rel_tol=tol, abs_tol=tol):
            fail(f"{message}: index {index} expected {b!r}, got {a!r}")


def ensure_addon_registered():
    if not hasattr(bpy.types.Scene, "paramsnap_properties"):
        ParamSnap.register()


def cleanup_test_data():
    for obj in list(bpy.data.objects):
        if obj.name.startswith(PREFIX):
            bpy.data.objects.remove(obj, do_unlink=True)

    for mesh in list(bpy.data.meshes):
        if mesh.name.startswith(PREFIX):
            bpy.data.meshes.remove(mesh)

    for material in list(bpy.data.materials):
        if material.name.startswith(PREFIX):
            bpy.data.materials.remove(material)

    for action in list(bpy.data.actions):
        if action.name.startswith(PREFIX):
            bpy.data.actions.remove(action)

    for node_group in list(bpy.data.node_groups):
        if node_group.name.startswith(PREFIX):
            bpy.data.node_groups.remove(node_group)

    for collection in list(bpy.data.collections):
        if collection.name.startswith(PREFIX):
            bpy.data.collections.remove(collection)


def reset_snapshot_state():
    props = bpy.context.scene.paramsnap_properties
    while props.ParamSnap_properties_coll:
        props.ParamSnap_properties_coll.remove(len(props.ParamSnap_properties_coll) - 1)
    props.ParamSnap_properties_coll_index = 0


def make_fixture():
    scene = bpy.context.scene

    root_collection = bpy.data.collections.new(f"{PREFIX}RootCollection")
    scene.collection.children.link(root_collection)

    instance_collection = bpy.data.collections.new(f"{PREFIX}InstanceCollection")
    scene.collection.children.link(instance_collection)

    parent_mesh = bpy.data.meshes.new(f"{PREFIX}ParentMesh")
    parent_obj = bpy.data.objects.new(f"{PREFIX}Parent", parent_mesh)
    root_collection.objects.link(parent_obj)

    child_mesh = bpy.data.meshes.new(f"{PREFIX}Mesh")
    child_obj = bpy.data.objects.new(f"{PREFIX}Object", child_mesh)
    root_collection.objects.link(child_obj)

    child_obj.location = (1.25, 2.5, 3.75)
    child_obj.pass_index = 7
    child_obj.hide_render = True
    child_obj.rotation_mode = "XYZ"
    child_obj.parent = parent_obj

    instance_obj = bpy.data.objects.new(f"{PREFIX}InstanceObject", None)
    root_collection.objects.link(instance_obj)
    instance_obj.instance_type = "COLLECTION"
    instance_obj.instance_collection = instance_collection

    child_obj["ps_float"] = 3.5
    child_obj["ps_label"] = "hello-idprop"

    bevel = child_obj.modifiers.new(f"{PREFIX}Bevel", "BEVEL")
    bevel.width = 0.125

    material = bpy.data.materials.new(f"{PREFIX}Material")
    material.use_nodes = True
    principled = next(node for node in material.node_tree.nodes if node.type == "BSDF_PRINCIPLED")
    principled.inputs[0].default_value = (0.1, 0.2, 0.3, 0.4)
    child_obj.data.materials.append(material)

    action = bpy.data.actions.new(f"{PREFIX}Action")
    child_obj.animation_data_create()
    child_obj.animation_data.action = action
    compositor_group = bpy.data.node_groups.new(f"{PREFIX}CompositorGroupA", "CompositorNodeTree")
    compositor_group_alt = bpy.data.node_groups.new(f"{PREFIX}CompositorGroupB", "CompositorNodeTree")
    scene.compositing_node_group = compositor_group

    paths = {
        "root_object": f'bpy.data.objects["{child_obj.name}"]',
        "root_collection": f'bpy.data.collections["{root_collection.name}"]',
        "root_material": f'bpy.data.materials["{material.name}"]',
        "root_action": f'bpy.data.actions["{action.name}"]',
        "float_rna": f'bpy.data.objects["{child_obj.name}"].modifiers["{bevel.name}"].width',
        "int_rna": f'bpy.data.objects["{child_obj.name}"].pass_index',
        "bool_rna": f'bpy.data.objects["{child_obj.name}"].hide_render',
        "string_rna": f'bpy.data.objects["{child_obj.name}"].name',
        "enum_rna": f'bpy.data.objects["{child_obj.name}"].rotation_mode',
        "vec3_rna": f'bpy.data.objects["{child_obj.name}"].location',
        "vec_component": f'bpy.data.objects["{child_obj.name}"].location[1]',
        "color4_rna": f'bpy.data.materials["{material.name}"].node_tree.nodes["{principled.name}"].inputs[0].default_value',
        "pointer_object": f'bpy.data.objects["{child_obj.name}"].parent',
        "pointer_collection": f'bpy.data.objects["{instance_obj.name}"].instance_collection',
        "pointer_action": f'bpy.data.objects["{child_obj.name}"].animation_data.action',
        "pointer_node_tree": f'bpy.data.scenes["{scene.name}"].compositing_node_group',
        "idprop_object_float": f'bpy.data.objects["{child_obj.name}"]["ps_float"]',
        "idprop_object_string": f'bpy.data.objects["{child_obj.name}"]["ps_label"]',
        "layer_collection_exclude": f'bpy.data.scenes["{scene.name}"].view_layers["{bpy.context.view_layer.name}"].layer_collection.children["{root_collection.name}"].exclude',
    }

    return {
        "scene": scene,
        "root_collection": root_collection,
        "instance_collection": instance_collection,
        "instance_obj": instance_obj,
        "parent_obj": parent_obj,
        "child_obj": child_obj,
        "bevel": bevel,
        "material": material,
        "principled": principled,
        "action": action,
        "compositor_group": compositor_group,
        "compositor_group_alt": compositor_group_alt,
        "paths": paths,
    }


def find_layer_collection(layer_collection, target_collection):
    if layer_collection.collection == target_collection:
        return layer_collection
    for child in layer_collection.children:
        found = find_layer_collection(child, target_collection)
        if found:
            return found
    return None


def new_param_item(path: str, label: str):
    props = bpy.context.scene.paramsnap_properties
    if not props.ParamSnap_properties_coll:
        snapshot = props.ParamSnap_properties_coll.add()
        snapshot.name = f"{PREFIX}Snapshot"
        props.ParamSnap_properties_coll_index = 0
    snapshot = props.ParamSnap_properties_coll[props.ParamSnap_properties_coll_index]
    param = snapshot.Param_properties_coll.add()
    param.name = label
    param.property_path = path
    value, value_type, meta, resolved_path = utils.get_value_and_type_from_param_item(param)
    assert_true(resolved_path == path or resolved_path.endswith(param.target_relative_path), f"{label}: expected a resolved path")
    assert_true(value_type not in {None, "UNDEFINED"}, f"{label}: failed to infer a stored type")
    utils.assign_stored_from_value(param, value, value_type, meta)
    return param, value, value_type, meta


def test_root_id_resolution(paths, fixture):
    log("Testing root datablock resolution")
    assert_equal(utils.resolve_id_data_path(paths["root_object"]), fixture["child_obj"], "Object root path should resolve")
    assert_equal(utils.resolve_id_data_path(paths["root_collection"]), fixture["root_collection"], "Collection root path should resolve")
    assert_equal(utils.resolve_id_data_path(paths["root_material"]), fixture["material"], "Material root path should resolve")
    assert_equal(utils.resolve_id_data_path(paths["root_action"]), fixture["action"], "Action root path should resolve")


def test_path_resolution(paths, fixture):
    log("Testing path parsing across common RNA and IDProperty cases")

    common_paths = [
        "float_rna",
        "int_rna",
        "bool_rna",
        "string_rna",
        "enum_rna",
        "vec3_rna",
        "vec_component",
        "color4_rna",
        "pointer_object",
        "pointer_collection",
        "pointer_action",
        "pointer_node_tree",
        "idprop_object_float",
        "idprop_object_string",
        "layer_collection_exclude",
    ]
    for key in common_paths:
        ptr, prop_token, arr_index = utils.resolve_ui_path(paths[key])
        assert_true(ptr is not None, f"{key}: resolve_ui_path returned no owner")
        assert_true(prop_token is not None, f"{key}: resolve_ui_path returned no token")
        assert_true(utils.is_ui_path_resolvable(paths[key]), f"{key}: path should be resolvable")

    ptr, prop_token, arr_index = utils.resolve_ui_path(paths["vec_component"])
    assert_equal(ptr, fixture["child_obj"], "Array component owner should be the object")
    assert_equal(prop_token, "location", "Array component property should resolve to location")
    assert_equal(arr_index, 1, "Array component index should be preserved")


def test_value_type_detection(paths, fixture):
    log("Testing value/type detection for common Blender property kinds")

    cases = [
        ("float_rna", "FLOAT"),
        ("int_rna", "INT"),
        ("bool_rna", "BOOLEAN"),
        ("string_rna", "STRING"),
        ("enum_rna", "STRING"),
        ("vec3_rna", "VEC3"),
        ("color4_rna", "COLOR4"),
        ("pointer_object", "POINTER"),
        ("pointer_collection", "POINTER"),
        ("pointer_action", "POINTER"),
        ("pointer_node_tree", "POINTER"),
        ("layer_collection_exclude", "BOOLEAN"),
    ]
    for key, expected_type in cases:
        value, value_type, meta = utils.get_value_and_type_from_path(paths[key])
        assert_equal(value_type, expected_type, f"{key}: detected type")
        assert_true(isinstance(meta, dict), f"{key}: meta should be a dict")
        assert_true(value is not None, f"{key}: value should not be None")

    _, _, obj_meta = utils.get_value_and_type_from_path(paths["pointer_object"])
    _, _, collection_meta = utils.get_value_and_type_from_path(paths["pointer_collection"])
    _, _, action_meta = utils.get_value_and_type_from_path(paths["pointer_action"])
    _, _, node_tree_meta = utils.get_value_and_type_from_path(paths["pointer_node_tree"])
    assert_equal(obj_meta.get("fixed_type"), "Object", "Object pointer should expose fixed type")
    assert_equal(collection_meta.get("fixed_type"), "Collection", "Collection pointer should expose fixed type")
    assert_equal(action_meta.get("fixed_type"), "Action", "Action pointer should expose fixed type")
    assert_equal(node_tree_meta.get("fixed_type"), "NodeTree", "NodeTree pointer should expose fixed type")


def test_snapshot_roundtrip(paths, fixture):
    log("Testing snapshot storage and apply flow for common supported types")

    param, stored_value, _, _ = new_param_item(paths["float_rna"], "Float RNA")
    fixture["bevel"].width = 0.5
    assert_equal(utils.apply_stored_to_target(param), 1, "Float RNA apply should succeed")
    assert_close(fixture["bevel"].width, stored_value, "Float RNA should restore the original value")

    param, stored_value, _, _ = new_param_item(paths["int_rna"], "Int RNA")
    fixture["child_obj"].pass_index = 2
    assert_equal(utils.apply_stored_to_target(param), 1, "Int RNA apply should succeed")
    assert_equal(fixture["child_obj"].pass_index, stored_value, "Int RNA should restore the original value")

    param, stored_value, _, _ = new_param_item(paths["bool_rna"], "Boolean RNA")
    fixture["child_obj"].hide_render = False
    assert_equal(utils.apply_stored_to_target(param), 1, "Boolean RNA apply should succeed")
    assert_equal(fixture["child_obj"].hide_render, stored_value, "Boolean RNA should restore the original value")

    param, stored_value, _, _ = new_param_item(paths["vec3_rna"], "Vector RNA")
    fixture["child_obj"].location = (9.0, 8.0, 7.0)
    assert_equal(utils.apply_stored_to_target(param), 1, "Vector RNA apply should succeed")
    assert_sequence_close(fixture["child_obj"].location, stored_value, "Vector RNA should restore the original value")

    param, stored_value, _, _ = new_param_item(paths["color4_rna"], "Color RNA")
    fixture["principled"].inputs[0].default_value = (0.9, 0.8, 0.7, 0.6)
    assert_equal(utils.apply_stored_to_target(param), 1, "Color RNA apply should succeed")
    assert_sequence_close(fixture["principled"].inputs[0].default_value, stored_value, "Color RNA should restore the original value")

    param, stored_value, _, _ = new_param_item(paths["pointer_object"], "Pointer Object")
    fixture["child_obj"].parent = None
    assert_equal(utils.apply_stored_to_target(param), 1, "Object pointer apply should succeed")
    assert_equal(fixture["child_obj"].parent, stored_value, "Object pointer should restore the original target")

    param, stored_value, _, _ = new_param_item(paths["pointer_collection"], "Pointer Collection")
    fixture["instance_obj"].instance_collection = None
    assert_equal(utils.apply_stored_to_target(param), 1, "Collection pointer apply should succeed")
    assert_equal(fixture["instance_obj"].instance_collection, stored_value, "Collection pointer should restore the original target")

    param, stored_value, _, _ = new_param_item(paths["pointer_node_tree"], "Pointer NodeTree")
    fixture["scene"].compositing_node_group = fixture["compositor_group_alt"]
    assert_equal(utils.apply_stored_to_target(param), 1, "NodeTree pointer apply should succeed")
    assert_equal(fixture["scene"].compositing_node_group, stored_value, "NodeTree pointer should restore the original target")

    layer_collection = find_layer_collection(bpy.context.view_layer.layer_collection, fixture["root_collection"])
    layer_collection.exclude = True
    param, stored_value, _, _ = new_param_item(paths["layer_collection_exclude"], "LayerCollection Exclude")
    assert_equal(stored_value, True, "LayerCollection exclude should capture the current value")
    layer_collection.exclude = False
    assert_equal(utils.apply_stored_to_target(param), 1, "LayerCollection exclude apply should succeed")
    assert_equal(layer_collection.exclude, True, "LayerCollection exclude should restore the stored value")


def test_layer_collection_button_path(paths, fixture):
    log("Testing LayerCollection exclude path construction from button context")

    layer_collection = find_layer_collection(bpy.context.view_layer.layer_collection, fixture["root_collection"])
    prop = layer_collection.bl_rna.properties["exclude"]

    class FakeContext:
        scene = fixture["scene"]
        view_layer = bpy.context.view_layer
        button_pointer = layer_collection
        button_prop = prop
        window_manager = bpy.context.window_manager

    full_path = utils.get_button_property_path(FakeContext())
    assert_equal(full_path, paths["layer_collection_exclude"], "LayerCollection button path should be stable")
    assert_true(utils.is_ui_path_resolvable(full_path), "LayerCollection button path should resolve")

    layer_collection.exclude = True
    param, stored_value, value_type, meta = new_param_item(full_path, "LayerCollection Button Exclude")
    assert_equal(value_type, "BOOLEAN", "LayerCollection button path should store a boolean")
    assert_equal(stored_value, True, "LayerCollection button path should capture the current value")
    layer_collection.exclude = False
    assert_equal(utils.apply_stored_to_target(param), 1, "LayerCollection button path should sync")
    assert_equal(layer_collection.exclude, True, "LayerCollection button path should restore exclude")

    param.current_bool_display = True
    assert_equal(layer_collection.exclude, False, "LayerCollection current display value should use include semantics")
    param.current_bool_display = False
    assert_equal(layer_collection.exclude, True, "LayerCollection current display false should exclude the collection")

    param.stored_bool_display = True
    assert_equal(param.stored_bool, False, "LayerCollection stored display true should store exclude false")
    layer_collection.exclude = True
    assert_equal(utils.apply_stored_to_target(param), 1, "LayerCollection include stored value should sync")
    assert_equal(layer_collection.exclude, False, "LayerCollection include stored value should include the collection")


def test_copy_snapshot_layer_collection_no_side_effect(paths, fixture):
    log("Testing snapshot copy does not touch LayerCollection current state")

    reset_snapshot_state()
    layer_collection = find_layer_collection(bpy.context.view_layer.layer_collection, fixture["root_collection"])
    layer_collection.exclude = True
    param, _, _, _ = new_param_item(paths["layer_collection_exclude"], "LayerCollection Copy")
    param.stored_bool_display = True
    assert_equal(param.stored_bool, False, "Stored include display should invert to exclude False")

    layer_collection.exclude = True
    before_state = layer_collection.exclude
    result = bpy.ops.param.copy_snapshot()
    assert_equal(result, {"FINISHED"}, "Copy snapshot operator should finish")
    assert_equal(layer_collection.exclude, before_state, "Copying a snapshot must not modify the current collection state")

    props = bpy.context.scene.paramsnap_properties
    copied_snapshot = props.ParamSnap_properties_coll[props.ParamSnap_properties_coll_index]
    copied_param = copied_snapshot.Param_properties_coll[0]
    assert_equal(copied_param.stored_bool, False, "Copied parameter should keep stored raw exclude value")
    assert_equal(copied_param.target_layer_collection_pointer, fixture["root_collection"], "Copied parameter should keep collection reference")
    assert_true("current_bool_display" not in utils.PARAM_ITEM_COPY_FIELDS, "Copy field whitelist must not include live bool proxy")
    assert_true("stored_bool_display" not in utils.PARAM_ITEM_COPY_FIELDS, "Copy field whitelist must not include stored bool proxy")


def test_layer_collection_rename_rebuild(paths, fixture):
    log("Testing LayerCollection target rebuilding after collection rename")

    reset_snapshot_state()
    layer_collection = find_layer_collection(bpy.context.view_layer.layer_collection, fixture["root_collection"])
    layer_collection.exclude = True
    param, stored_value, _, _ = new_param_item(paths["layer_collection_exclude"], "LayerCollection Rename")
    old_path = param.property_path

    fixture["root_collection"].name = f"{PREFIX}RootCollectionRenamed"
    stable_path = utils.build_param_target_path(param, mutate=False)
    assert_true(stable_path != old_path, "LayerCollection stable path should change after collection rename")
    assert_true(fixture["root_collection"].name in stable_path, "LayerCollection stable path should use the new collection name")
    assert_true(utils.is_ui_path_resolvable(stable_path), "LayerCollection stable path should remain resolvable after rename")
    assert_true(not utils.is_ui_path_resolvable(old_path), "Old LayerCollection path should become stale after rename")

    ptr, prop_token, _, resolved_path = utils.resolve_param_item_path(param, mutate=False)
    assert_true(ptr is not None, "LayerCollection renamed target should still resolve")
    assert_equal(prop_token, "exclude", "LayerCollection renamed property should remain exclude")
    assert_equal(resolved_path, stable_path, "LayerCollection renamed target should prefer rebuilt path")

    ptr.exclude = False
    assert_equal(utils.apply_stored_to_target(param), 1, "LayerCollection renamed target should sync")
    assert_equal(ptr.exclude, stored_value, "LayerCollection renamed target should restore stored state")

    path_state = utils.get_param_path_state(param)
    assert_true(path_state["stable_valid"], "LayerCollection stable reference should be valid after rename")
    assert_true(not path_state["property_valid"], "LayerCollection original property path should be stale after rename")
    assert_equal(path_state["recommended_mode"], "STABLE", "LayerCollection rename conflict should recommend stable reference")


def test_compositor_node_group_snapshot(paths, fixture):
    log("Testing scene compositor node group snapshot, swap, and JSON roundtrip")

    reset_snapshot_state()
    scene = fixture["scene"]
    scene.compositing_node_group = fixture["compositor_group"]
    param, stored_value, value_type, meta = new_param_item(paths["pointer_node_tree"], "Compositor Node Group")
    assert_equal(value_type, "POINTER", "Compositor node group should store as a pointer")
    assert_equal(meta.get("fixed_type"), "NodeTree", "Compositor node group pointer should be a NodeTree")
    assert_equal(param.stored_pointer_kind, "NodeTree", "Stored pointer kind should be NodeTree")
    assert_equal(param.stored_node_tree_pointer, fixture["compositor_group"], "Stored node tree should be the active compositor group")

    scene.compositing_node_group = fixture["compositor_group_alt"]
    assert_equal(utils.apply_stored_to_target(param), 1, "Compositor node group sync should succeed")
    assert_equal(scene.compositing_node_group, stored_value, "Compositor node group should restore the stored group")

    scene.compositing_node_group = fixture["compositor_group_alt"]
    snapshot = bpy.context.scene.paramsnap_properties.ParamSnap_properties_coll[0]
    snapshot.Param_properties_coll_index = 0
    result = bpy.ops.param.swap_param(ParamIndex=0)
    assert_equal(result, {"FINISHED"}, "Compositor node group swap should finish")
    assert_equal(scene.compositing_node_group, fixture["compositor_group"], "Compositor node group swap should apply stored value")
    assert_equal(param.stored_node_tree_pointer, fixture["compositor_group_alt"], "Compositor node group swap should store previous current value")

    payload = utils.build_snapshot_export_payload(snapshot)
    serialized = payload["snapshots"][0]["params"][0]
    assert_equal(serialized["stored_pointer_kind"], "NodeTree", "JSON export should preserve NodeTree pointer kind")
    assert_equal(serialized["value"]["name"], fixture["compositor_group_alt"].name, "JSON export should preserve NodeTree name")

    imported_snapshot = bpy.context.scene.paramsnap_properties.ParamSnap_properties_coll.add()
    skipped = utils.apply_serialized_snapshot_item(imported_snapshot, payload["snapshots"][0])
    assert_equal(skipped, 0, "JSON import should accept NodeTree pointer parameters")
    imported_param = imported_snapshot.Param_properties_coll[0]
    assert_equal(imported_param.stored_pointer_kind, "NodeTree", "JSON import should restore NodeTree pointer kind")
    assert_equal(imported_param.stored_node_tree_pointer, fixture["compositor_group_alt"], "JSON import should restore NodeTree pointer")

    FakeContext = type(
        "FakeContext",
        (),
        {
            "scene": scene,
            "view_layer": bpy.context.view_layer,
            "button_pointer": fixture["compositor_group"],
            "button_prop": fixture["compositor_group"].bl_rna.properties["name"],
            "window_manager": bpy.context.window_manager,
        },
    )

    scene.compositing_node_group = fixture["compositor_group"]
    rewritten_path = utils.get_button_property_path(FakeContext())
    assert_equal(rewritten_path, paths["pointer_node_tree"], "Right-clicking the compositor node group name should store the scene pointer path")

    reset_snapshot_state()

    class FakeArea:
        def tag_redraw(self):
            pass

    class FakeScreen:
        areas = [FakeArea()]

    FakeOperatorContext = type("FakeOperatorContext", (FakeContext,), {"screen": FakeScreen()})

    class FakeOperator:
        def report(self, level, message):
            pass

    assert_equal(ParamSnap.operators.PARAMS_OT_AddParamToCol.execute(FakeOperator(), FakeOperatorContext()), {"FINISHED"}, "Right-click add on compositor node group name should finish")
    added_snapshot = bpy.context.scene.paramsnap_properties.ParamSnap_properties_coll[0]
    added_param = added_snapshot.Param_properties_coll[0]
    assert_equal(added_param.property_path, paths["pointer_node_tree"], "Right-click add should store compositor node group pointer path")
    assert_equal(added_param.stored_pointer_kind, "NodeTree", "Right-click add should store a NodeTree pointer")
    assert_equal(added_param.stored_node_tree_pointer, fixture["compositor_group"], "Right-click add should store the active compositor group")

    reset_snapshot_state()
    assert_equal(bpy.ops.param.add_scene_compositor_node_group(), {"FINISHED"}, "Panel add compositor node group operator should finish")
    added_snapshot = bpy.context.scene.paramsnap_properties.ParamSnap_properties_coll[0]
    added_param = added_snapshot.Param_properties_coll[0]
    assert_equal(added_param.property_path, paths["pointer_node_tree"], "Panel add should store compositor node group pointer path")
    assert_equal(added_param.stored_pointer_kind, "NodeTree", "Panel add should store a NodeTree pointer")


def test_param_category_and_copy_paste(paths, fixture):
    log("Testing parameter categories and copying selected params through the parameter clipboard")

    reset_snapshot_state()
    props = bpy.context.scene.paramsnap_properties
    source = props.ParamSnap_properties_coll.add()
    source.name = f"{PREFIX}Source"
    target_a = props.ParamSnap_properties_coll.add()
    target_a.name = f"{PREFIX}TargetA"
    props.ParamSnap_properties_coll_index = 0

    layer_collection = find_layer_collection(bpy.context.view_layer.layer_collection, fixture["root_collection"])
    layer_collection_path = utils.build_layer_collection_property_path(bpy.context, layer_collection, "exclude")
    param_collection, _, _, _ = new_param_item(layer_collection_path, "Collection State Param")
    param_collection.category = utils.infer_param_category(param_collection.property_path)
    param_collection.copy_selected = True
    assert_equal(param_collection.category, "Collection State", "LayerCollection exclude should infer Collection State category")

    param_compositor, _, _, _ = new_param_item(paths["pointer_node_tree"], "Compositor Param")
    param_compositor.category = utils.infer_param_category(param_compositor.property_path)
    param_compositor.copy_selected = True
    assert_equal(param_compositor.category, "Compositor", "Scene compositor node group should infer Compositor category")

    source.collapsed_categories = '["Compositor"]'
    assert_equal(bpy.ops.param.toggle_param_category(category="Compositor"), {"FINISHED"}, "Toggle category should expand a collapsed category")
    assert_true("Compositor" not in source.collapsed_categories, "Category should be removed from collapsed list after toggle")
    assert_equal(bpy.ops.param.toggle_param_category(category="Compositor"), {"FINISHED"}, "Toggle category should collapse a category")
    assert_true("Compositor" in source.collapsed_categories, "Category should be added to collapsed list after toggle")
    assert_equal(bpy.ops.param.select_param(index=1), {"FINISHED"}, "Grouped list row select should finish")
    assert_equal(source.Param_properties_coll_index, 1, "Grouped list row select should update active parameter index")
    ui._PARAM_CATEGORY_FILTER = "Compositor"
    filter_self = type("FilterSelf", (), {"bitflag_filter_item": 1 << 30})()
    filter_flags, _filter_order = ui.PARAMS_UL_ParamList.filter_items(filter_self, bpy.context, source, "Param_properties_coll")
    visible_flags = [bool(flag & filter_self.bitflag_filter_item) for flag in filter_flags]
    assert_equal(visible_flags, [False, True], "Category UIList filter should only show matching params")
    ui._PARAM_CATEGORY_FILTER = ""

    assert_equal(bpy.ops.param.copy_selected_params(), {"FINISHED"}, "Copy selected params should finish")
    assert_true(props.param_clipboard.strip(), "Copy selected params should fill the parameter clipboard")
    assert_true(any(param.copy_selected for param in source.Param_properties_coll), "Copy should leave source selection intact for repeated pastes")

    props.ParamSnap_properties_coll_index = 1
    assert_equal(bpy.ops.param.paste_copied_params(include_values=True), {"FINISHED"}, "Paste selected params should finish")
    assert_equal(len(target_a.Param_properties_coll), 2, "Target snapshot should receive selected parameters")
    copied_categories = {param.category for param in target_a.Param_properties_coll}
    assert_equal(copied_categories, {"Collection State", "Compositor"}, "Pasted params should preserve categories")
    assert_true(not any(param.copy_selected for param in target_a.Param_properties_coll), "Pasted params should not remain selected in targets")

    target_a.Param_properties_coll.clear()
    scene = bpy.context.scene
    original_group = fixture["compositor_group"]
    current_group = bpy.data.node_groups.new(f"{PREFIX}ClipboardCurrent", "CompositorNodeTree")
    scene.compositing_node_group = current_group
    assert_equal(bpy.ops.param.paste_copied_params(include_values=False), {"FINISHED"}, "Paste references only should finish")
    target_compositor = next(param for param in target_a.Param_properties_coll if param.category == "Compositor")
    assert_equal(target_compositor.stored_node_tree_pointer, current_group, "Reference-only paste should capture the target snapshot current value")
    scene.compositing_node_group = original_group

    payload = utils.build_snapshot_export_payload(source)
    categories = {param_data["category"] for param_data in payload["snapshots"][0]["params"]}
    assert_equal(categories, {"Collection State", "Compositor"}, "JSON export should preserve parameter categories")

    imported = props.ParamSnap_properties_coll.add()
    skipped = utils.apply_serialized_snapshot_item(imported, payload["snapshots"][0])
    assert_equal(skipped, 0, "JSON import with categories should not skip params")
    imported_categories = {param.category for param in imported.Param_properties_coll}
    assert_equal(imported_categories, {"Collection State", "Compositor"}, "JSON import should restore parameter categories")


def test_datablock_rename_rebuild(paths, fixture):
    log("Testing datablock-follow path rebuilding after a rename")

    param, _, _, _ = new_param_item(paths["float_rna"], "Rename Rebuild")
    old_path = param.property_path

    fixture["child_obj"].name = f"{PREFIX}ObjectRenamed"

    stable_path = utils.build_param_target_path(param, mutate=False)
    assert_true(stable_path != old_path, "Stable path should change after renaming the root datablock")
    assert_true(fixture["child_obj"].name in stable_path, "Stable path should contain the new object name")
    assert_true(utils.is_ui_path_resolvable(stable_path), "Stable path after rename should remain resolvable")

    path_state = utils.get_param_path_state(param)
    assert_true(path_state["stable_valid"], "Stable path should be valid after rename")
    assert_true(not path_state["property_valid"], "Original property_path should become stale after rename")
    assert_equal(path_state["recommended_mode"], "STABLE", "Rename conflict should recommend datablock reference mode")

    ptr, prop_token, _, resolved_path = utils.resolve_param_item_path(param, mutate=False)
    assert_equal(ptr, fixture["bevel"], "Resolved pointer after rename should still point at the modifier")
    assert_equal(prop_token, "width", "Resolved property after rename should still be width")
    assert_equal(resolved_path, stable_path, "Resolved path should prefer the rebuilt datablock path")


def main():
    ensure_addon_registered()
    cleanup_test_data()
    reset_snapshot_state()

    try:
        fixture = make_fixture()
        paths = fixture["paths"]

        test_root_id_resolution(paths, fixture)
        test_path_resolution(paths, fixture)
        test_value_type_detection(paths, fixture)
        test_snapshot_roundtrip(paths, fixture)
        test_layer_collection_button_path(paths, fixture)
        test_copy_snapshot_layer_collection_no_side_effect(paths, fixture)
        test_layer_collection_rename_rebuild(paths, fixture)
        test_compositor_node_group_snapshot(paths, fixture)
        test_param_category_and_copy_paste(paths, fixture)
        test_datablock_rename_rebuild(paths, fixture)

        log("All ParamSnap smoke tests passed")
    finally:
        reset_snapshot_state()
        cleanup_test_data()


if __name__ == "__main__":
    try:
        main()
    except Exception:
        traceback.print_exc()
        raise SystemExit(1)
