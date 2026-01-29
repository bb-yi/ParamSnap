import bpy

translations_dict = {
    "zh_CN": {
        ("*", "Test Operator Executed"): "测试操作已执行",
        ("*", "Snapshot"): "快照",
        ("*", "Parameter"): "参数",
    },
}


def translations(text):
    return bpy.app.translations.pgettext(text)
