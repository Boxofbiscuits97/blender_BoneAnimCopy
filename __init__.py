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

bl_info = {
    "name" : "Bone Animation Copy Tool",
    "author" : "Kumopult <kumopult@qq.com>, CCrashCup, & Boxofbiscuits97",
    "description" : "Copy animation between different armature by bone constraint",
    "blender" : (3, 3, 0),
    "version" : (1, 0, 1),
    "location" : "View 3D > Toolshelf",
    "category" : "Animation",
    "doc_url": "https://github.com/Boxofbiscuits97/blender_BoneAnimCopy",
    # VScode debug：Ctrl + Shift + P
}

import bpy
from . import data
from . import mapping
from .utilfuncs import *

class BAC_PT_Panel(bpy.types.Panel):
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "BoneAnimCopy"
    bl_label = "Bone Animation Copy Tool"
    
    def draw(self, context):
        layout = self.layout
        
        split = layout.row().split(factor=0.2)
        left = split.column()
        right = split.column()
        left.label(text='Map skeleton:')
        left.label(text='Constrained target:')
        right.prop(bpy.context.scene, 'kumopult_bac_owner', text='', icon='ARMATURE_DATA', translate=False)
        if bpy.context.scene.kumopult_bac_owner != None and bpy.context.scene.kumopult_bac_owner.type == 'ARMATURE':
            s = get_state()
            right.prop(s, 'selected_target', text='', icon='ARMATURE_DATA', translate=False)
            
            if s.target == None:
                layout.label(text='Select another skeleton object as a constraint target to continue operation', icon='INFO')
            else:
                mapping.draw_panel(layout.row())
                row = layout.row()
                row.prop(s, 'preview', text='Preview constraint', icon= 'HIDE_OFF' if s.preview else 'HIDE_ON')
                row.operator('kumopult_bac.bake', text='Baking animation', icon='NLA')
        else:
            right.label(text='Unexpected mapping skeleton object', icon='ERROR')


class BAC_State(bpy.types.PropertyGroup):
    def update_target(self, context):
        self.owner = bpy.context.scene.kumopult_bac_owner
        self.target = self.selected_target

        for m in self.mappings:
            m.apply()
    
    def update_preview(self, context):
        for m in self.mappings:
            m.apply()
    
    def update_active(self, context):
        if self.sync_select:
            self.update_select(bpy.context)
            owner_active = self.owner.data.bones.get(self.mappings[self.active_mapping].owner)
            self.owner.data.bones.active = owner_active
            target_active = self.target.data.bones.get(self.mappings[self.active_mapping].target)
            self.target.data.bones.active = target_active
    
    def update_select(self, context):
        if self.sync_select:
            owner_selection = []
            target_selection = []
            for m in self.mappings:
                if m.selected:
                    owner_selection.append(m.owner)
                    target_selection.append(m.target)
            for bone in self.owner.data.bones:
                bone.select = bone.name in owner_selection
            for bone in self.target.data.bones:
                bone.select = bone.name in target_selection
    
    selected_target: bpy.props.PointerProperty(
        type=bpy.types.Object,
        override={'LIBRARY_OVERRIDABLE'},
        poll=lambda self, obj: obj.type == 'ARMATURE' and obj != bpy.context.scene.kumopult_bac_owner,
        update=update_target
    )
    target: bpy.props.PointerProperty(type=bpy.types.Object, override={'LIBRARY_OVERRIDABLE'})
    owner: bpy.props.PointerProperty(type=bpy.types.Object, override={'LIBRARY_OVERRIDABLE'})
    
    mappings: bpy.props.CollectionProperty(type=data.BAC_BoneMapping, override={'LIBRARY_OVERRIDABLE', 'USE_INSERTION'})
    active_mapping: bpy.props.IntProperty(default=-1, override={'LIBRARY_OVERRIDABLE'}, update=update_active)
    selected_count:bpy.props.IntProperty(default=0, override={'LIBRARY_OVERRIDABLE'}, update=update_select)
    
    editing_type: bpy.props.IntProperty(description="Used to record panel types", override={'LIBRARY_OVERRIDABLE'})
    preview: bpy.props.BoolProperty(
        default=True, 
        description="Switch all constraints to preview the animation of baking",
        override={'LIBRARY_OVERRIDABLE'},
        update=update_preview
    )

    sync_select: bpy.props.BoolProperty(default=False, name='Synchronous selection', description="Click on the list item to automatically activate the corresponding bone when checking the list item", override={'LIBRARY_OVERRIDABLE'})
    calc_offset: bpy.props.BoolProperty(default=True, name='Automatic rotation bias', description="Set the mapping target and automatically calculate the rotation bias", override={'LIBRARY_OVERRIDABLE'})
    ortho_offset: bpy.props.BoolProperty(default=True, name='Orthogonal', description="Multiple of the calculation result is approximately 90°", override={'LIBRARY_OVERRIDABLE'})
    
    def get_target_armature(self):
        return self.target.data

    def get_owner_armature(self):
        return self.owner.data
    
    def get_target_pose(self):
        return self.target.pose

    def get_owner_pose(self):
        return self.owner.pose

    def get_active_mapping(self):
        return self.mappings[self.active_mapping]
    
    def get_mapping_by_target(self, name):
        if name != "":
            for i, m in enumerate(self.mappings):
                if m.target == name:
                    return m, i
        return None, -1

    def get_mapping_by_owner(self, name):
        if name != "":
            for i, m in enumerate(self.mappings):
                if m.owner == name:
                    return m, i
        return None, -1

    def get_selection(self):
        indices = []

        if self.selected_count == 0 and len(self.mappings) > self.active_mapping >= 0:
            indices.append(self.active_mapping)
        else:
            for i in range(len(self.mappings) - 1, -1, -1):
                if self.mappings[i].selected:
                    indices.append(i)
        return indices
    
    def add_mapping(self, owner, target, index=-1):
        # When it is not introduced in index, take the activation item as the index
        if index == -1:
            index = self.active_mapping + 1
        # Here you need to detect whether the target bones have already been mapping
        m, i = self.get_mapping_by_owner(owner)
        if m:
            # If already exist, cover the original skeleton and return mapping and index values
            m.target = target
            self.active_mapping = i
            return m, i
        else:
            # If it does not exist, create a new mapping, and the same return mapping and index value
            m = self.mappings.add()
            m.selected_owner = owner
            m.target = target
            # return m, len(self.mappings) - 1
            self.mappings.move(len(self.mappings) - 1, index)
            self.active_mapping = index
            return self.mappings[index], index
    
    def remove_mapping(self):
        for i in self.get_selection():
            self.mappings[i].clear()
            self.mappings.remove(i)
        # Select status update
        self.active_mapping = min(self.active_mapping, len(self.mappings) - 1)
        self.selected_count = 0

classes = (
	BAC_PT_Panel, 
	*data.classes,
	*mapping.classes,
	BAC_State,
)

def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.Scene.kumopult_bac_owner = bpy.props.PointerProperty(type=bpy.types.Object, poll=lambda self, obj: obj.type == 'ARMATURE')
    bpy.types.Armature.kumopult_bac = bpy.props.PointerProperty(type=BAC_State, override={'LIBRARY_OVERRIDABLE'})
    print("hello kumopult!")

def unregister():
    for cls in classes:
        bpy.utils.unregister_class(cls)
    del bpy.types.Scene.kumopult_bac_owner
    del bpy.types.Armature.kumopult_bac
    print("goodbye kumopult!")
