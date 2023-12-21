from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

bl_info = {
    "name": "OpenCue",
    "author": "Nuwan Jayawardene",
    "version": (0, 0, 0, 1),
    "blender": (3, 3, 1),
    "description": "OpenCue client for Blender.",
    "location": "Output Properties > OpenCue",
    "category": "System",
}

import bpy

from . import Setup

class SubmitJob(bpy.types.Operator):
    bl_idname = "object.submit_job"
    bl_label = "My Operator"

    def execute(self, context):
        retrieved_output_path = bpy.context.preferences.addons[__name__].preferences.output_path
        layerData = {
            'name': context.scene.layer_name,
            'layerType': 'Blender',
            'cmd': {
                'blenderFile': bpy.data.filepath,
                'outputPath': retrieved_output_path,
                'outputFormat': 'PNG'
            },
            'layerRange': '1',
            'chunk': '1',
            'cores': '0',
            'env': {},
            'services': [],
            'limits': [],
            'dependType': '',
            'dependsOne': None
        }

        jobData = {
            'name': context.scene.job_name,
            'username': context.scene.usr_name,
            'show': "testing",
            'shot': context.scene.shot_name,
            'layers': layerData
        }

        from . import Submission
        Submission.submit(jobData)


class OpenCuePanel(bpy.types.Panel):
    """A custom panel in the 3D View Properties region"""
    bl_label = "OpenCue"
    bl_idname = "SCENE_PT_layout"  # VIEW_3D_opencue_panel
    bl_space_type = 'PROPERTIES'  # VIEW_3D
    bl_region_type = 'WINDOW'  # UI
    bl_category = "render"  # Properties

    def draw(self, context):
        layout = self.layout

        col = layout.column()
        col.prop(context.scene, "job_name")

        col = layout.column()
        col.prop(context.scene, "usr_name")

        col = layout.column()
        col.prop(context.scene, "layer_name")

        col = layout.column()
        col.prop(context.scene, "shot_name")

        col = layout.column()
        col.operator("object.submit_job", text="Submit")


class OpenCueAddonPreferences(bpy.types.AddonPreferences):
    bl_idname = __name__

    is_dependency_install: bpy.props.BoolProperty(
        name="Dependency Install",
        default=False,
        description="Flag to indicate if dependencies have been installed during first install",
    )

    use_gpu: bpy.props.BoolProperty(
        name="Use GPU for rendering",
        default=False,
        description="Enable to utilize GPU rendering for jobs",
    )

    output_path: bpy.props.StringProperty(
        name="OpenCue output path",
        default="",
    )
    def draw(self, context):
        layout = self.layout
        layout.prop(self, "use_gpu")
        layout.prop(self, "output_path")

def register():
    bpy.utils.register_class(OpenCueAddonPreferences)

    bpy.types.Scene.job_name = bpy.props.StringProperty(
        name="Job name",
        description="Name of job submission",
        default=""
    )

    bpy.types.Scene.usr_name = bpy.props.StringProperty(
        name="User name",
        description="Name of user performing job submission",
        default=""
    )

    bpy.types.Scene.layer_name = bpy.props.StringProperty(
        name="Layer name",
        description="Job submission layer name",
        default=""
    )

    bpy.types.Scene.shot_name = bpy.props.StringProperty(
        name="Shot name",
        description="Shot name",
        default=""
    )

    bpy.utils.register_class(OpenCuePanel)

    # Check if dependencies are not installed
    addon_pref = bpy.context.preferences.addons[__name__].preferences
    if not addon_pref.is_dependency_install:
        Setup.installModule()
        bpy.context.preferences.addons[__name__].preferences.is_dependency_install = True
        bpy.utils.register_class(SubmitJob)
    else:
        Setup.installOpencueModules()
        bpy.utils.register_class(SubmitJob)


def unregister():
    bpy.utils.unregister_class(OpenCuePanel)
    bpy.utils.unregister_class(SubmitJob)
    bpy.utils.unregister_class(OpenCueAddonPreferences)
    del bpy.types.Scene.job_name
    del bpy.types.Scene.usr_name
    del bpy.types.Scene.layer_name

    Setup.removeOpencueModules()


if __name__ == "__main__":
    register()
