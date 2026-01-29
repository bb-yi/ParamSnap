# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTIBILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program. If not, see <http://www.gnu.org/licenses/>.

# TODO 动画数据路径快速选择

bl_info = {
    "name": "Paramsnap",
    "author": "LEDingQ",
    "description": "",
    "blender": (2, 80, 0),
    "version": (0, 0, 1),
    "location": "",
    "warning": "",
    "category": "Generic",
}

import bpy
from . import operators
from . import ui
from .i18n import translations_dict
from . import property


def register():
    try:
        bpy.app.translations.register(__name__, translations_dict)
    except:
        pass
    property.register()
    operators.register()
    ui.register()


def unregister():
    try:
        bpy.app.translations.unregister(__name__)
    except:
        pass
    property.unregister()
    operators.unregister()
    ui.unregister()
