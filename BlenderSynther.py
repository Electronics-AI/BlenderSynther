bl_info = {
    "name": "BlenderSynther",
    "author": "Electronics-AI",
    "version": (0, 1),
    "blender": (2, 91, 0),
    "location": "View3D > Toolshelf > BlenderSynther",
    "description": "Add-on for synthetic data generation",
    "warning": "",
    "doc_url": "https://github.com/Electronics-AI/BlenderSynther.git",
    "category": "Development",
}


import bpy
import itertools
import random
import json
import os
from os.path import exists as path_exists
from os.path import join as join_path
from math import radians, sin, cos, tan, sqrt, floor
from mathutils import Vector
from bpy.types import (Panel, Operator, PropertyGroup) 
from bpy.props import (PointerProperty, BoolProperty, StringProperty,
                       IntProperty, FloatProperty, EnumProperty)


class BS_BlenderSyntherButtonsPanel(Panel):
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "BlenderSynther"
    bl_options = {'DEFAULT_CLOSED'}
    
    def draw(self, context):
        pass


class BS_DatasetJSONGenerator:
    __slots__ = ("_dataset_info", "_dataset_info_json_name",
                 "_rendered_images_folder_path", "_dataset_with_segmentation_masks")
                 
    def __init__(self, context, struct_labeled_objects):
        self._dataset_info_json_name = "dataset_info.json"
        self._rendered_images_folder_path = context.scene.rendered_images_folder
        self._dataset_with_segmentation_masks = context.scene.generate_segmentation_masks
        self._dataset_info = self._compose_dataset_info(context, struct_labeled_objects)
    
    def generate_json(self):
        dataset_info_json_path = join_path(self._rendered_images_folder_path, self._dataset_info_json_name)
        
        with open(dataset_info_json_path, "w") as dij:
            json.dump(self._dataset_info, dij, indent=1)
            
    def _compose_dataset_info(self, context, struct_labeled_objects):
        dataset_info = dict()
        
        images_size = (context.scene.render.resolution_x, context.scene.render.resolution_y)
        rendered_images_format = context.scene.rendered_images_file_format
        
        dataset_info["images_size"] = images_size
        dataset_info["rendered_images_format"] = rendered_images_format
        
        if self._dataset_with_segmentation_masks:
            labeled_objects_info = self._get_labeled_objects_info(struct_labeled_objects)
            dataset_info["labeled_objects_info"] = labeled_objects_info
        
        return dataset_info
            
    def _get_labeled_objects_info(self, struct_labeled_objects):
        labeled_objects_info = dict()
        
        for label_name, label_objects in struct_labeled_objects.items():
            labeled_objects_info[label_name] = list()
            for label_object in label_objects:
                object_parent_name = label_object[0]
                label_object_pass_index = bpy.data.objects[object_parent_name].pass_index
                labeled_objects_info[label_name].append(label_object_pass_index)

        return labeled_objects_info


class BS_CompositorNodesManager:
    __slots__ = ("_render_layers_node", "_composite_node")
    
    def __init__(self, context):
        self._add_basic_nodes(context)
        self._connect_basic_nodes(context)
        
    @property
    def render_layers_node(self):
        return self._render_layers_node
    
    def _connect_basic_nodes(self, context):
        context.scene.use_nodes = True
        
        context.scene.node_tree.links.new(self._render_layers_node.outputs["Image"], 
                                          self._composite_node.inputs["Image"])
        
    def _add_basic_nodes(self, context):
        context.scene.use_nodes = True
        
        render_layers_node_name = "Render Layers"
        composite_node_name = "Composite"
        
        nodes = context.scene.node_tree.nodes
        
        # Render Layers Node
        if nodes.get(render_layers_node_name, None):
             self._render_layers_node = nodes[render_layers_node_name]
        else:
            self._render_layers_node = nodes.new("CompositorNodeRLayers")
        self._render_layers_node.location = (0, 0)
        
        # Composite Node
        if nodes.get(composite_node_name, None):
             self._composite_node = nodes[composite_node_name]
        else:
            self._composite_node = nodes.new("CompositorNodeComposite")
        self._composite_node.location = (200, 200) 
     
############################################################################################################
#                                           LABELED OBJECTS
############################################################################################################
class BS_PT_LabeledObjects(BS_BlenderSyntherButtonsPanel):
    bl_label = "Labeled Objects"
    bl_idname = "BS_PT_LABELED_OBJECTS"

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        flow = layout.grid_flow(row_major=True, even_columns=False, even_rows=False, align=True)
      
        col = flow.column()
        col.label(text="Collection of objects to label")
        col.prop(scene, "labeled_objects_collection", text="")
        

class BS_PT_LabeledobjectSettings(BS_BlenderSyntherButtonsPanel):
    pass
    
class BS_PGT_LabeledObjectsProperies(PropertyGroup):
    bpy.types.Scene.labeled_objects_collection = PointerProperty(
                                      type=bpy.types.Collection,
                                      name="Labeled Objects Collection")
                                      
class BS_LabeledObjects:    
    __slots__ = ("_all_parent_objects", "_all_label_names", "_structured_labeled_objects",
                 "_number_of_models", "_pass_index_step")
             
    @property
    def structured_labeled_objects(self):
        return self._structured_labeled_objects
    
    @property
    def all_parent_objects(self):
        return self._all_parent_objects
    
    @property
    def number_of_models(self):
        return self._number_of_models
    
    def insert_animation_keyframe(self, frame_num):
        self._randomly_rotate()
        for parent_object in self._all_parent_objects:
            parent_object.keyframe_insert(data_path="rotation_euler", index=-1, frame=frame_num)
            
    def _randomly_rotate(self):     
        for parent_object in self._all_parent_objects:
            orient_axis = random.randint(0, 2)
            rotation_degree = radians(random.randint(117, 454))
            parent_object.rotation_euler[orient_axis] = rotation_degree
            
    def __init__(self, context):
        labeled_objects_collection = context.scene.labeled_objects_collection
        
        if labeled_objects_collection:
            self._all_parent_objects = self._get_all_parent_objects(labeled_objects_collection)
            self._all_label_names = self._get_all_label_names(labeled_objects_collection)
            self._structured_labeled_objects = self._get_structured_labeled_objects(labeled_objects_collection)
            self._number_of_models = len(self._all_parent_objects)
            self._setup_properties(context)
        else:
            raise Exception("You have to specify the labeled objects collection")
    
    def _setup_properties(self, context):
        # Set pass indexes
        context.view_layer.use_pass_object_index = True
    
        pass_indexes = self._get_pass_indexes()
        for label_objects in self._structured_labeled_objects.values():
            for model_objects in label_objects:
                self._set_model_pass_index(model_objects, next(pass_indexes))
                    
    def _set_model_pass_index(self, model_objects, pass_index):
        for model_object in model_objects:
             bpy.data.objects[model_object].pass_index = pass_index
    
    def _get_pass_indexes(self):
        number_of_models = self._number_of_models
        if number_of_models < 255:
            pass_index_step = (2**8 - 1) // number_of_models
        else: 
            pass_index_step = (2**16 - 1) // number_of_models
        
        for model_num in range(1, number_of_models + 1):
            yield model_num * pass_index_step    
            
    def _get_all_label_names(self, labeled_objects_collection):
        return tuple([label_coll.name for label_coll in labeled_objects_collection.children])
    
    def _get_structured_labeled_objects(self, labeled_objects_collection):
        labeled_objects = dict()
        for label_collection in labeled_objects_collection.children:
            label_name = label_collection.name
            label_objects = self._get_labeled_objects_for_collection(label_collection)
            labeled_objects[label_name] = label_objects

        return labeled_objects
            
    def _get_all_parent_objects(self, labeled_objects_collection):
        all_parent_objects = list()
        
        for label_collection in labeled_objects_collection.children:
            all_parent_objects.extend(self._get_parent_objects_for_collection(label_collection))
            
        return tuple(all_parent_objects)  
    
    def _get_labeled_objects_for_collection(self, label_collection):
        parent_objects = self._get_parent_objects_for_collection(label_collection)
        label_objects = dict([(parent_object.name, list()) for parent_object in parent_objects])
        
        child_objects = [object for object in label_collection.objects if object.parent is not None]
        for child_object in child_objects: 
            parent_object = child_object.parent
            while parent_object.parent is not None:
                parent_object = parent_object.parent
            else:
                label_objects[parent_object.name].append(child_object.name)
                    
        return tuple([(parent, *childs) for parent, childs in label_objects.items()])
    
    def _get_parent_objects_for_collection(self, label_collection):
        return tuple([object for object in label_collection.objects if object.parent is None])
     

############################################################################################################
#                                           BACKGROUND
############################################################################################################
class BS_PT_Background(BS_BlenderSyntherButtonsPanel):
    bl_label = "Background"
    bl_idname = "BS_PT_BACKGROUND"

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        flow = layout.grid_flow(row_major=True, even_columns=False, even_rows=False, align=True)
      
        col = flow.column()
        col.label(text="Background Type")
        col.prop(scene, "background_type", text="")
    
        
class BS_PT_BackgroundSettings(BS_BlenderSyntherButtonsPanel):
    bl_label = "Background Settings"
    bl_idname = "BS_PT_BACKGROUND_SETTINGS"
    bl_parent_id = "BS_PT_BACKGROUND"
    
    def draw(self, context):
        layout = self.layout
        scene = context.scene
        flow = layout.grid_flow(row_major=True, even_columns=False, even_rows=False, align=True)
      
        if scene.background_type == "plane":
            col = flow.column()
            col.prop(scene, "randomly_change_bg_brightness", text="Randomly Change Plane Brightness")
            
            col.label(text="Plane used as background")
            col.prop(scene, "background_plane", text="")
            col.separator()
            
            col.label(text="Plane textures folder path")
            col.prop(scene, "plane_textures_folder", text="")
            
        elif scene.background_type == "custom":
            pass

        
class BS_PGT_BackgroundProperies(PropertyGroup):
    bpy.types.Scene.background_type = EnumProperty(
                                      items=(("plane", "Plane", ""),
                                             ("custom", "Custom", "")),
                                      name="Background Type")
    bpy.types.Scene.background_plane = PointerProperty(
                                      type=bpy.types.Object,
                                      name="Background Plane")                                    
    bpy.types.Scene.plane_textures_folder = StringProperty(
                                      subtype="DIR_PATH",
                                      default="background/textures/folder/",
                                      name="Plane Textures Folder")
    bpy.types.Scene.randomly_change_bg_brightness = BoolProperty(
                                      default=True,
                                      name="Randomly Change BG Brightness")
        
        

class BS_BackgroundPlane:
    __slots__ = ("_plane", "_material")
    
    def insert_animation_keyframe(self, frame_num):
        self._material.insert_animation_keyframe(frame_num)
        
    def __init__(self, context):
        self._plane = self._set_plane(context)
        self._material = self._Material(context, self._plane)
        
    def set_next_texture(self):
        self._material.set_next_texture()
          
    def _set_plane(self, context):
        plane = context.scene.background_plane
        if plane: 
            return plane
        raise Exception("You have to specify the plane")
        
    class _Material:
        __slots__ = ("_vary_brightness", "_material_textures_folder",
                         "_material", "_name", "_plane",
                         "_material_texture_paths", "_allowed_texture_extensions",
                         "_emission_node", "_image_texture_node", "_material_output_node")
            
        def __init__(self, context, plane):
            self._plane = plane
            self._allowed_texture_extensions = (".png", ".jpg", ".jpeg",)
            self._name = "BS Plane Material"
            self._vary_brightness = context.scene.randomly_change_bg_brightness
            self._material_textures_folder = self._set_textures_folder(context)
            self._material_texture_paths = self._get_material_texture_paths()
            self._material = self._create_material(context)
        
        def insert_animation_keyframe(self, frame_num):
            self._randomly_change_brightness()
            self._emission_node.inputs["Strength"].keyframe_insert(data_path="default_value", frame=frame_num)
            
        def _set_textures_folder(self, context):
            plane_textures_folder = context.scene.plane_textures_folder

            for file_name in os.listdir(plane_textures_folder):
                if file_name.endswith(self._allowed_texture_extensions):
                    return plane_textures_folder
                    
            raise FileNotFoundError("Background textures folder must have at least 1 texture",
                                        "with allowed extension.\n",
                                        f"Allowed extensions are {allowed_texture_extensions}")
    
        def _create_material(self, context):
            material_name = self._name
                
            # Clear backround material node tree
            material = bpy.data.materials.get(material_name, None)
            if material:
                material.node_tree.nodes.clear()
            else:     
                material = bpy.data.materials.new(material_name)
                    
            material.use_nodes = True
            material_nodes = material.node_tree.nodes
                
            # Add all the needed nodes 
            self._material_output_node = material_nodes.new('ShaderNodeOutputMaterial')
            self._emission_node = material_nodes.new("ShaderNodeEmission")
            self._image_texture_node = material_nodes.new("ShaderNodeTexImage")
                
            # Set node locations
            self._material_output_node.location = (500, 0)
            self._emission_node.location = (300, 0)
            self._image_texture_node.location = (0, 0)
                
            # Connect nodes
            material.node_tree.links.new(self._image_texture_node.outputs["Color"],
                                                self._emission_node.inputs["Color"])
            material.node_tree.links.new(self._emission_node.outputs["Emission"],
                                                self._material_output_node.inputs["Surface"])
                
            # Set background plane material
            self._plane.active_material = material
                
            return material
            
        def _randomly_change_brightness(self):
            emission_strength = random.uniform(0.050, 2.990)
            self._emission_node.inputs["Strength"].default_value = emission_strength
                    
        def _get_material_texture_paths(self):
            material_textures_folder = itertools.cycle(os.listdir(self._material_textures_folder))
            material_textures_folder_path = self._material_textures_folder
                
            for material_texture_file in material_textures_folder:
                yield join_path(material_textures_folder_path, material_texture_file) 
                
        def set_next_texture(self):
            material_texture_path = next(self._material_texture_paths)
            material_texture = bpy.data.images.load(material_texture_path, check_existing=True)
            self._image_texture_node.image = material_texture
            #bpy.data.images.remove(material_texture)
                 
class BS_BackgroundCustom:
    def __init__(self, context):
        pass
        
    def _compose_transforms(self, context):
        pass


############################################################################################################
#                                              LIGHTS
############################################################################################################
class BS_PT_Lights(BS_BlenderSyntherButtonsPanel):
    bl_label = "Lights"
    bl_idname = "BS_PT_LIGHTS"

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        flow = layout.grid_flow(row_major=True, even_columns=False, even_rows=False, align=True)
      
        col = flow.column()
        col.prop(scene, "randomly_toggle_lights")
        
        col = flow.column()
        col.enabled = context.scene.randomly_toggle_lights
        col.label(text="Lights collection")
        col.prop(scene, "lights_collection", text="")
        
        
class BS_PGT_LightsProperties(PropertyGroup):
    bpy.types.Scene.lights_collection = PointerProperty(
                                      type=bpy.types.Collection,
                                      name="Lights Collection")
    bpy.types.Scene.randomly_toggle_lights = BoolProperty(
                                      default=True,
                                      name="Randomly Toggle Lights")

     
class BS_Lights:
    __slots__ = ("_lights", "_num_lights",)
    
    def insert_animation_keyframe(self, frame_num):
        self._randomly_toggle()
        for light in self._lights:
            light.keyframe_insert(data_path="hide_render", frame=frame_num)
            
    def _randomly_toggle(self):
        lights_to_toggle = random.choices(self._lights, k=random.randint(1, self._num_lights))
        
        for light in lights_to_toggle:
            light.hide_viewport = not light.hide_viewport
            light.hide_render = not light.hide_render
            
    def __init__(self, context):
        if context.scene.lights_collection:
            self._lights = context.scene.lights_collection.all_objects
            self._num_lights = len(self._lights)
            
            
            
############################################################################################################
#                                              CAMERA
############################################################################################################
class BS_OT_CameraSetupToTrack(Operator):
    bl_label = "Setup The Camera"
    bl_idname = "camera.setup_to_track"
    _camera_container_name = "Camera Container" 
    
    def execute(self, context):
        camera_container = BS_CameraContainer()
        #  simplify camera setup
        
        return {"FINISHED"}
    
    
class BS_PGT_CameraProperies(PropertyGroup):
    bpy.types.Scene.shooting_camera = PointerProperty(
                                      type=bpy.types.Object,
                                      name="Shooting Camera")
    bpy.types.Scene.camera_position_type = EnumProperty(
                                      items=(("fixed", "Fixed", ""),
                                             ("follow_path", "Follow Path", "")),
                                      name="Camera Position Type") 
                                          
# Inner of 
class Paths:
    _half_loxodrome = None
    
    def execute(self, context):
        camera_paths_collection = BS_CollectionsManager().camera_paths_collection
        points = self._get_loxocurve_points()
        loxocurve = bpy.data.curves.new("loxo", type='CURVE')
        loxocurve.dimensions = '3D'
        loxocurve.resolution_u = 2
        spline = loxocurve.splines.new('NURBS')
        spline.points.add(count=len(points) - 1)

        for i, bp in enumerate(spline.points):
            bp.co = (*points[i], 1)

        loxodrome = bpy.data.objects.new(self.bl_label, loxocurve)    
        camera_paths_collection.objects.link(loxodrome)
        
        return {"FINISHED"}
    
    def _get_loxocurve_points(self):
        spirals = 17
        revs = 23
        angle_step = 10
        
        a = 1 / spirals
        degs = floor(180 * revs)
        end_degs = 0 if self._half_loxodrome else degs
        segs = [radians(d) for d in range(-degs, end_degs, angle_step)]
        
        loxocurve_points = list()
        for t in segs:
            den = sqrt(1 + a**2 * t**2)
            x = cos(t) / den
            y = sin(t) / den
            z = -a * t / den
            loxocurve_points.append(Vector((x, y, z)))    
             
        return loxocurve_points

class BS_OT_FullLoxoromeGenerator(Paths, Operator):
    bl_label = "Full Sphere"
    bl_idname = 'curve.full_sphere' 
    _half_loxodrome = False


class BS_OT_HalfLoxoromeGenerator(Paths, Operator):
    bl_label = "Half Sphere"
    bl_idname = 'curve.half_sphere' 
    _half_loxodrome = True
    
    
class BS_PT_Camera(BS_BlenderSyntherButtonsPanel):
    bl_label = "Camera"
    bl_idname = "BS_PT_CAMERA"
    
    def draw(self, context):
        layout = self.layout
        scene = context.scene
        flow = layout.grid_flow(row_major=True, even_columns=False, even_rows=False, align=True)
        
        col = flow.column()
        col.label(text="Shooting camera")
        col.prop(scene, "shooting_camera", text="")
        col.separator()
        
        col.label(text="Camera position type")
        col.prop(scene, "camera_position_type", text="")
        
        
class BS_PT_CameraSettings(BS_BlenderSyntherButtonsPanel):
    bl_label = "Camera Settings"
    bl_idname = "BS_PT_CAMERA_SETTINGS"
    bl_parent_id = "BS_PT_CAMERA"

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        flow = layout.grid_flow(row_major=True, even_columns=False, even_rows=False, align=True)
        
        if scene.camera_position_type == "follow_path":   
            col = flow.column()       
            col.label(text="Generate a path")
            col.operator("curve.full_sphere")
            col.operator("curve.half_sphere")
            col.separator()
            
            col.label(text="Camera Setup")
            col.operator("camera.setup_to_track")
        elif scene.camera_position_type == "fixed":
            pass
             
              
class BS_Camera:
    _camera_container_name = "Camera Container"
    
    class _Fixed:
        pass
    
    class _FollowingPath:
        pass
    
    @property
    def camera_container(self):
        return bpy.data.objects.get(self._camera_container_name, None)
    
    def setup_tracking_camera(self, context):
        scene = context.scene
        labeled_object = xyu
        camera_container = BS_Camera().camera_container
        tracking_camera = scene.shooting_camera
        camera_container_collection = BS_CollectionsManager().camera_container_collection
        
        # Link the tracking camera to the Camera Container collection
        for tracking_camera_collection in tracking_camera.users_collection:
            tracking_camera_collection.objects.unlink(tracking_camera)
        camera_container_collection.objects.link(tracking_camera)
        
        # Set the camera to the 3D cursor location
        cursor_location = scene.cursor.location
        tracking_camera.location = cursor_location
        
        # Set Camera Container as a parent of the tracking camera
        tracking_camera.parent = camera_container
        
        # Set Camera constraint to track the model
        if tracking_camera.constraints.get("BS Track To", None) is None:
            tracking_camera_track_to_constr = tracking_camera.constraints.new(type="TRACK_TO")
            # SET CONSTARINT NAME
        else:
            tracking_camera_track_to_constr = tracking_camera.constraints["BS Track To"]
            
        tracking_camera_track_to_constr.target = labeled_object
    
    def setup_camera_container(self, context):
        camera_container = BS_CameraContainer().camera_container
        camera_paths_collection = BS_CollectionsManager().camera_paths_collection
        
        def create_camera_container(self):
            camera_container_collection = BS_CollectionsManager().camera_container_collection
            if bpy.data.objects.get(self._camera_container_name, None) is None:
                camera_container = bpy.data.objects.new(self._camera_container_name, None)
                camera_container_collection.objects.link(camera_container)
            
        def set_follow_path_constraint(camera_container, context):
            if camera_container.constraints.get("BS Follow Path", None) is None:
                camera_container_follow_path_constr = camera_container.constraints.new(type="FOLLOW_PATH")
            else:
                camera_container_follow_path_constr = camera_container.constraints["BS Follow Path"]
                
            follow_path_constraint.target = camera_paths_collection.objects[0]
            follow_path_constraint.use_fixed_location = True
            follow_path_constraint.use_curve_follow = True
            follow_path_constraint.use_curve_radius = False
            follow_path_constraint.forward_axis = "FORWARD_Z"
            follow_path_constraint.up_axis = "UP_Y"
            
            bpy.context.view_layer.objects.active = camera_container
            bpy.ops.constraint.followpath_path_animate({"constraint": camera_container_follow_path_constr}, 
                                                        constraint="BS Follow Path")
                                              

############################################################################################################
#                                           ANNOTATIONS
############################################################################################################
class BS_PT_Annotations(BS_BlenderSyntherButtonsPanel):
    bl_label = "Annotations"
    bl_idname = "BS_PT_ANNOTATIONS"

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        flow = layout.grid_flow(row_major=True, even_columns=False, even_rows=False, align=True)
        
        col = flow.column()
        col.prop(scene, "generate_segmentation_masks")
         
        col = flow.column()
        col.enabled = scene.generate_segmentation_masks
        col.label(text="Where to save the segmentation masks")
        col.prop(scene, "segmentation_masks_folder", text="")
      
          
class BS_PGT_AnnotationsProperies(PropertyGroup):
    bpy.types.Scene.segmentation_masks_folder = StringProperty(
                                      subtype="DIR_PATH",
                                      default="segmentation/masks/folder/",
                                      name="Segmentation Masks Folder")
    bpy.types.Scene.generate_segmentation_masks = BoolProperty(
                                      default=False,
                                      name="Generate Segmentation Masks") 
                                                       
class BS_Annotations:
    __slots__ = ("_divide_node", "_segmentation_output_node",
                 "_segmentation_masks_folder", "_segmentation_color_mode", 
                 "_divide_node_name", "_segmentation_output_node_name",
                 "_segmentation_image_name")
    
    def set_index(self, index):
        segmentation_image_name = self._segmentation_image_name.format(index=index)
        self._segmentation_output_node.file_slots[0].path = segmentation_image_name
    
    def __init__(self, context, num_models):
        self._divide_node_name = "BS Divide"
        self._segmentation_output_node_name = "BS Segmentation Output"
        
        if context.scene.generate_segmentation_masks:
            self._segmentation_image_name = "##########"
            self._segmentation_color_mode = "BW"
            self._segmentation_masks_folder = self._set_segmentation_masks_folder(context)
            
            self._add_compositor_nodes(context)
            self._setup_compositor_nodes(num_models)
            self._connect_compositor_nodes(context)
        else:
            self._delete_compositor_nodes(context)
    
    def _delete_compositor_nodes(self, context):
        nodes = context.scene.node_tree.nodes
        
        if nodes.get(self._divide_node_name, None):
            nodes.remove(nodes[self._divide_node_name])
            
        if nodes.get(self._segmentation_output_node_name, None):
            nodes.remove(nodes[self._segmentation_output_node_name])
        
    def _set_segmentation_masks_folder(self, context):
        segmentation_masks_folder = context.scene.segmentation_masks_folder
        
        if path_exists(segmentation_masks_folder):
            return segmentation_masks_folder
        raise FileNotFoundError(f"Specified segmentation masks folder '{segmentation_masks_folder}' "
                                 "does not exist")
                                 
    def _setup_compositor_nodes(self, num_models):
        segm_masks_color_depth = 8 if num_models < 256 else 16
        divide_node_div_factor = 2**8 -1 if num_models < 256 else 2**16 - 1
        
        # Divide Node
        self._divide_node.operation = "DIVIDE"
        self._divide_node.inputs[1].default_value = divide_node_div_factor  
        
        # File Output (Segmentation Mask) Node
        self._segmentation_output_node.base_path = self._segmentation_masks_folder
        self._segmentation_output_node.format.color_mode = self._segmentation_color_mode
        self._segmentation_output_node.format.color_depth = str(segm_masks_color_depth)
        self._segmentation_output_node.file_slots[0].path = self._segmentation_image_name
        
    def _connect_compositor_nodes(self, context):
        node_tree = context.scene.node_tree
        render_layers_node = BS_CompositorNodesManager(context).render_layers_node 
        
        node_tree.links.new(render_layers_node.outputs["IndexOB"],
                            self._divide_node.inputs[0])
        node_tree.links.new(self._divide_node.outputs["Value"],
                            self._segmentation_output_node.inputs[0])
        
    def _add_compositor_nodes(self, context):
        context.scene.use_nodes = True
        
        divide_node_name = self._divide_node_name
        segmentation_output_node_name = self._segmentation_output_node_name
        
        nodes = context.scene.node_tree.nodes
        
        # Divide Node
        if nodes.get(divide_node_name, None):
             self._divide_node = nodes[divide_node_name]
        else:
            self._divide_node = nodes.new("CompositorNodeMath")
            self._divide_node.name = divide_node_name
        self._divide_node.location = (400, 0)
        
        # File (Segmentation Mask) Output Node
        if nodes.get(segmentation_output_node_name, None):
             self._segmentation_output_node = nodes[segmentation_output_node_name]
        else:
            self._segmentation_output_node = nodes.new("CompositorNodeOutputFile")
            self._segmentation_output_node.name = segmentation_output_node_name 
        self._segmentation_output_node.location = (400, -300)
        
        
############################################################################################################
#                                            RENDER
############################################################################################################
class BS_PGT_RenderProperies(PropertyGroup):
    bpy.types.Scene.rendered_images_folder = StringProperty(
                                      subtype="DIR_PATH",
                                      default="rendered/images/folder/",
                                      name="Rendered Images Folder")
    bpy.types.Scene.rendered_images_file_format = EnumProperty(
                                      items=(("JPEG", "JPEG", ""),
                                             ("PNG", "PNG", "")),
                                      name="Rendered Images File Format")
        
        
class BS_PT_Render(BS_BlenderSyntherButtonsPanel):
    bl_label = "Render"
    bl_idname = "BS_PT_RENDER"
    
    def draw(self, context):
        layout = self.layout
        scene = context.scene
        flow = layout.grid_flow(row_major=True, even_columns=False, even_rows=False, align=True)
        
        col = flow.column()    
        col.label(text="Rendered images file format")
        col.prop(scene, "rendered_images_file_format", text="")
        col.separator()
        
        col.label(text="Where to save the rendered images")
        col.prop(scene, "rendered_images_folder", text="")
                                                                                                                                                                           

class BS_Render:
    __slots__ = ("_render_output_node", "_rendered_images_folder", 
                 "_rendered_images_color_mode", "_render_output_node_name",
                 "_rendered_image_name")
    
    def set_index(self, index):
        rendered_image_name = self._rendered_image_name.format(index=index)
        self._render_output_node.file_slots[0].path = rendered_image_name
    
    def _set_rendered_images_folder(self, context):
        rendered_images_folder = context.scene.rendered_images_folder
        if path_exists(rendered_images_folder):
            return rendered_images_folder
        raise FileNotFoundError(f"Specified rendered images folder '{rendered_images_folder}' "
                                 "does not exist")
                                 
    def __init__(self, context):
        self._rendered_image_name = "##########"
        self._render_output_node_name = "BS Render Output"
        self._rendered_images_color_mode = "RGB"
        self._rendered_images_folder = self._set_rendered_images_folder(context)
        
        self._add_compositor_nodes(context)
        self._setup_compositor_nodes(context)
        self._connect_compositor_nodes(context)
        
    def _add_compositor_nodes(self, context):
        context.scene.use_nodes = True
        
        render_output_node_name = self._render_output_node_name
        nodes = context.scene.node_tree.nodes
        
        # Rendered Output Node
        if nodes.get(render_output_node_name, None):
             self._render_output_node = nodes[render_output_node_name]
        else:
            self._render_output_node = nodes.new("CompositorNodeOutputFile")
            self._render_output_node.name = render_output_node_name
        self._render_output_node.location = (500, 200)
    
    def _setup_compositor_nodes(self, context):
        rendered_image_format = context.scene.rendered_images_file_format
        
        self._render_output_node.base_path = self._rendered_images_folder
        self._render_output_node.format.file_format = rendered_image_format
        self._render_output_node.format.color_mode = self._rendered_images_color_mode
        self._render_output_node.file_slots[0].path = self._rendered_image_name
        
    def _connect_compositor_nodes(self, context):
        node_tree = context.scene.node_tree
        render_layers_node = BS_CompositorNodesManager(context).render_layers_node 
        
        node_tree.links.new(render_layers_node.outputs["Image"],
                            self._render_output_node.inputs[0])

    
############################################################################################################
#                                       DATASET GENERATION
############################################################################################################  
class BS_PT_DatasetGeneration(BS_BlenderSyntherButtonsPanel):
    bl_label = "Dataset Generation"
    bl_idname = "BS_PT_DATASET_GENERATION"

    def draw(self, context):
        layout = self.layout
        scene = context.scene 
        flow = layout.grid_flow(row_major=True, even_columns=False, even_rows=False, align=True)
        
        col = flow.column() 

        col.prop(scene, "items_to_generate")
        col.separator()
        
        col.prop(scene, "first_item_index")
        col.separator()
        
        col.operator("bs.generate_dataset")
        
        
class BS_PGT_DatasetGenerationProperties(PropertyGroup):
    bpy.types.Scene.items_to_generate = IntProperty(
                                        default=1,
                                        min=1,
                                        name="Items To Generate")
    bpy.types.Scene.first_item_index = IntProperty(
                                        default=0,
                                        min=0,
                                        name="First Item Index")
    
    
class BS_OT_GenerateDataset(Operator):
    bl_label = "Generate Dataset"
    bl_idname = "bs.generate_dataset"
    
    def execute(self, context):
        dataset_generator = BS_DatasetGenerator(context)
        
        bpy.app.handlers.frame_change_pre.clear()
        bpy.app.handlers.frame_change_pre.append(dataset_generator.set_next_scene_render_state)

        bpy.ops.render.render("INVOKE_DEFAULT", animation=True)  
        
        return {"FINISHED"}

class BS_DatasetGenerator:
    __slots__ = ("_items_to_generate", "_first_item_index", 
                 "_labeled_objects", "_background", "_lights",
                 "_render", "_annotations", "_dataset_json_generator",
                 "_objects_to_animate", "_scene_render_changes")
    
    def __init__(self, context):
        if context.scene.generate_segmentation_masks:
            context.scene.render.engine = "CYCLES"
        
        self._items_to_generate = int(context.scene.items_to_generate)
        self._first_item_index = int(context.scene.first_item_index)
        self._check_item_indices_correctness(self._items_to_generate, self._first_item_index)
                       
        self._labeled_objects = BS_LabeledObjects(context)
        self._background = self._select_background(context)
        self._lights = BS_Lights(context)
        self._render = BS_Render(context)
        self._annotations = BS_Annotations(context, self._labeled_objects.number_of_models)
        self._dataset_json_generator = BS_DatasetJSONGenerator(
                                       context=context,
                                       struct_labeled_objects=self._labeled_objects.structured_labeled_objects) 
        
        self._objects_to_animate = self._compose_objects_to_animate(context)
        self._scene_render_changes = self._compose_scene_render_changes(context)
        self._compose_animation(context)
        self._dataset_json_generator.generate_json()
                
        if context.scene.background_type == "plane":
            self._background.set_next_texture()
    
    def _compose_scene_render_changes(self, context):
        scene_render_changes = list()
        if context.scene.background_type == "plane":
            scene_render_changes.append(self._background.set_next_texture)
            return tuple(scene_render_changes)
        
    def set_next_scene_render_state(self, *args):
        for scene_change in self._scene_render_changes:
            scene_change()    
        
    def _select_background(self, context):
        if context.scene.background_type == "plane":
            return BS_BackgroundPlane(context)
        elif context.scene.background_type == "custom":
            return BS_BackgroundCustom(context)
        
    def _check_item_indices_correctness(self, items_to_generate, first_item_index):
        max_animation_frames = 1_048_574  # Blender constant
        if (first_item_index + items_to_generate) > max_animation_frames:
            raise Exception("You cannot generate so many items with such a first item index")
    
    def _compose_objects_to_animate(self, context):
        objects_to_animate = list()
        
        objects_to_animate.append(self._labeled_objects)
        if context.scene.randomly_toggle_lights:
            objects_to_animate.append(self._lights)
        if context.scene.randomly_change_bg_brightness:
            objects_to_animate.append(self._background)
        
        return tuple(objects_to_animate)
    
    def _compose_animation(self, context):
        first_item_index = self._first_item_index
        last_item_index = self._first_item_index + self._items_to_generate - 1
        
        context.scene.frame_start = first_item_index
        context.scene.frame_end = last_item_index
            
        for frame_num in range(first_item_index, last_item_index + 1):
            context.scene.frame_current = frame_num
            
            for animated_object in self._objects_to_animate:
                animated_object.insert_animation_keyframe(frame_num)       
        
        context.scene.frame_current = first_item_index
        
        
############################################################################################################
#
############################################################################################################                       
classes = (BS_PGT_LabeledObjectsProperies, BS_PGT_BackgroundProperies,
           BS_PGT_LightsProperties, BS_PGT_CameraProperies, 
           BS_PGT_AnnotationsProperies, BS_PGT_RenderProperies, BS_PGT_DatasetGenerationProperties, 
           BS_PT_LabeledObjects, BS_PT_Background,
           BS_PT_BackgroundSettings, BS_PT_Lights,
           BS_PT_Camera, BS_PT_CameraSettings, BS_PT_Annotations,
           BS_PT_Render, BS_PT_DatasetGeneration, 
           BS_OT_FullLoxoromeGenerator, BS_OT_HalfLoxoromeGenerator,
           BS_OT_CameraSetupToTrack,
           BS_OT_GenerateDataset, 
           )

def register():
    for cls in classes:
        bpy.utils.register_class(cls)
                                      

def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
    
    
if __name__ == '__main__':
    from functools import partial
    from time import process_time
    from datetime import datetime
    #from bpy.app.handlers import persistent
    
    register()
    
    context = bpy.context
    scene = context.scene
    # Animation Compositor
    #dataset_generator = BS_DatasetGenerator(context)
    #bg_plane = BS_BackgroundPlane(context)
    #bg_plane.set_next_texture()
    #bpy.app.handlers.frame_change_pre.clear()
    #bpy.app.handlers.frame_change_pre.append(dataset_generator._background.randomly_change)
    
    #for frame_num in range(105):
    #    scene.frame_set(frame_num)
    #    dataset_generator._apply_environment_transforms()
        
     #   for parent_object in labeled_objects.all_parent_objects:
     #       parent_object.keyframe_insert(data_path="rotation_euler", index=-1)
        
        # BG apply_animation_transforms    
    #for frame_num in range(105):
    #    bpy.data.materials["BS Plane Material"].node_tree.nodes["Emission"].inputs[1].keyframe_insert("default_value", frame=frame_num)
    
    #bpy.ops.render.render("INVOKE_DEFAULT", animation=True)   
    #bpy.ops.render.render(context, "INVOKE_DEFAULT")
    #bpy.app.timers.register(bs_render)      
    #context = bpy.context
    #start_time = process_time()
    
    #labeled_objects = BS_LabeledObjects(context)
    #lights = BS_Lights(context)
    #background = BS_Background(context)
    
    #def render_next_scene(*args, **kwargs):
    #    global context
    #    print("---------------------------------------------")
    #    random.seed(datetime.now())
    #    labeled_objects.randomly_rotate()
    #    lights.randomly_toggle()
    #    background.randomly_change()
    #    bpy.ops.render.render("INVOKE_DEFAULT", write_still=True) 
        
    #bpy.app.handlers.render_complete.append(render_next_scene)
    #bpy.ops.render.render("INVOKE_DEFAULT", write_still=True)    
    #bpy.app.handlers.render_complete.clear()

    # 1000 - 0.0047 sec
    # 10000 - 0.0515 sec
    #print("Execution time:", (process_time() - start_time) / 10, "(sec)")
