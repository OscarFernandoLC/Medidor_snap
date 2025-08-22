bl_info = {
    "name": "Medidor con Snap",
    "author": "Oscar + ChatGPT",
    "version": (1, 14),
    "blender": (3, 6, 0),
    "location": "View3D > Header",
    "description": "Mide distancia, controla Snap y aplica Mirror desde borde seleccionado",
    "category": "Mesh",
}

import bpy
import bmesh
from mathutils import Vector

def get_resultado_formateado(context):
    resultado = context.scene.get("ultima_distancia", "")
    if resultado and not resultado.startswith("Selecciona") and not resultado.startswith("Modo") and not resultado.startswith("Error"):
        return resultado
    return "Medir"

class MESH_OT_MedirDistancia(bpy.types.Operator):
    bl_idname = "mesh.medir_distancia"
    bl_label = "Medir distancia"
    bl_description = "Mide la distancia entre dos vértices seleccionados"

    def execute(self, context):
        obj = context.object
        if obj is None or obj.type != 'MESH' or obj.mode != 'EDIT':
            self.report({'WARNING'}, "Debes estar en modo Edición y tener un objeto tipo MESH")
            context.scene["ultima_distancia"] = "Modo incorrecto"
            return {'CANCELLED'}
        bm = bmesh.from_edit_mesh(obj.data)
        verts = [v for v in bm.verts if v.select]
        if len(verts) != 2:
            self.report({'WARNING'}, "Selecciona exactamente 2 vértices")
            context.scene["ultima_distancia"] = "Selecciona 2 vértices"
            return {'CANCELLED'}
        distancia = (verts[0].co - verts[1].co).length
        unidad = context.scene.unit_settings.length_unit
        scale = context.scene.unit_settings.scale_length
        if scale == 0:
            context.scene["ultima_distancia"] = "Error: Unit Scale = 0"
            self.report({'ERROR'}, "La escala de unidad es cero. No se puede calcular la distancia.")
            return {'CANCELLED'}
        factor = {
            'MILLIMETERS': 1000,
            'CENTIMETERS': 100,
            'METERS': 1,
            'KILOMETERS': 0.001,
            'INCHES': 39.3701,
            'FEET': 3.28084
        }.get(unidad, 1)
        etiquetas = {
            'MILLIMETERS': 'mm',
            'CENTIMETERS': 'cm',
            'METERS': 'm',
            'KILOMETERS': 'km',
            'INCHES': 'in',
            'FEET': 'ft'
        }
        etiqueta = etiquetas.get(unidad, 'm')
        resultado = f"{distancia * factor * scale:.2f} {etiqueta}"
        context.scene["ultima_distancia"] = resultado
        self.report({'INFO'}, f"Distancia: {resultado}")
        return {'FINISHED'}

class MESH_OT_ToggleSnapVertex(bpy.types.Operator):
    bl_idname = "mesh.toggle_snap_vertex"
    bl_label = "Toggle Snap Vértice"
    bl_description = "Activa o desactiva Snap solo en modo Vértice"

    def execute(self, context):
        ts = context.scene.tool_settings
        snap_elements = ts.snap_elements

        if 'VERTEX' in snap_elements:
            ts.snap_elements = set()
            self.report({'INFO'}, "Snap Vértice desactivado")
        else:
            ts.snap_elements = {'VERTEX'}
            self.report({'INFO'}, "Snap Vértice activado")

        return {'FINISHED'}

class MESH_OT_OrigenDesdeEdge(bpy.types.Operator):
    bl_idname = "mesh.mirror_selection"
    bl_label = "Origen desde Edge + Mirror"
    bl_description = "Coloca el origen en el centro del borde seleccionado y agrega modificador Mirror"

    def execute(self, context):
        obj = context.object

        if obj.mode != 'EDIT':
            bpy.ops.object.mode_set(mode='EDIT')
        bpy.ops.mesh.select_mode(type="EDGE")

        bm = bmesh.from_edit_mesh(obj.data)
        bm.edges.ensure_lookup_table()
        selected_edges = [e for e in bm.edges if e.select]

        if len(selected_edges) != 1:
            self.report({'WARNING'}, "Selecciona solo un borde")
            return {'CANCELLED'}

        edge = selected_edges[0]
        v1, v2 = edge.verts
        edge_center = (v1.co + v2.co) / 2.0

        bpy.ops.object.mode_set(mode='OBJECT')
        world_pos = obj.matrix_world @ edge_center
        context.scene.cursor.location = world_pos
        bpy.ops.object.origin_set(type='ORIGIN_CURSOR', center='MEDIAN')

        bpy.ops.object.mode_set(mode='EDIT')

        if not obj.modifiers.get("Mirror"):
            mirror = obj.modifiers.new(name="Mirror", type='MIRROR')
            mirror.use_axis[0] = True

            while obj.modifiers[0] != mirror:
                bpy.ops.object.modifier_move_up(modifier=mirror.name)
        else:
            self.report({'INFO'}, "Ya tiene un modificador Mirror")

        return {'FINISHED'}

class MESH_OT_OrigenDesdeSeleccion(bpy.types.Operator):
    bl_idname = "mesh.origen_desde_seleccion"
    bl_label = "Origen desde Selección"
    bl_description = "Coloca el origen en el centro de la selección actual (vértices, cara o arista)"

    def execute(self, context):
        obj = context.object

        if obj is None or obj.type != 'MESH':
            self.report({'WARNING'}, "Selecciona un objeto tipo malla")
            return {'CANCELLED'}

        bpy.ops.object.mode_set(mode='EDIT')
        bm = bmesh.from_edit_mesh(obj.data)
        bm.verts.ensure_lookup_table()
        selected_verts = [v.co for v in bm.verts if v.select]

        if not selected_verts:
            self.report({'WARNING'}, "No hay vértices seleccionados")
            return {'CANCELLED'}

        center = sum(selected_verts, Vector()) / len(selected_verts)
        bpy.ops.object.mode_set(mode='OBJECT')

        old_cursor = context.scene.cursor.location.copy()
        context.scene.cursor.location = obj.matrix_world @ center
        bpy.ops.object.origin_set(type='ORIGIN_CURSOR', center='MEDIAN')
        context.scene.cursor.location = old_cursor  
        bpy.ops.object.mode_set(mode='EDIT')

        return {'FINISHED'}

class MESH_OT_snap_x_zero(bpy.types.Operator):
    bl_idname = "mesh.snap_x_zero"
    bl_label = "Alinear a X = 0"
    bl_description = "Mueve los vértices seleccionados a X = 0"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        obj = context.active_object
        if not obj or obj.type != 'MESH':
            self.report({'WARNING'}, "Selecciona una malla")
            return {'CANCELLED'}

        if obj.mode != 'EDIT':
            self.report({'WARNING'}, "Debes estar en modo Edición")
            return {'CANCELLED'}

        bm = bmesh.from_edit_mesh(obj.data)
        for v in bm.verts:
            if v.select:
                v.co.x = 0

        bmesh.update_edit_mesh(obj.data)
        self.report({'INFO'}, "Vértices alineados a X = 0")
        return {'FINISHED'}


def draw_button(self, context):
    layout = self.layout
    obj = context.object

    if obj and obj.type == 'MESH' and obj.mode == 'EDIT':
        texto = get_resultado_formateado(context)
        layout.separator()
        layout.operator("mesh.medir_distancia", text=texto, icon="DRIVER_DISTANCE")

    layout.separator()
    layout.operator("mesh.toggle_snap_vertex", text="VERTEX", icon='SNAP_VERTEX')

    ts = context.scene.tool_settings
    row = layout.row(align=True)
    row.prop_enum(ts, "snap_target", 'CLOSEST', text="", icon='EVENT_C')
    row.prop_enum(ts, "snap_target", 'ACTIVE', text="", icon='EVENT_A')

    layout.separator()
    layout.operator("mesh.mirror_selection", text="Mirror", icon='MOD_MIRROR')
    layout.operator("mesh.origen_desde_seleccion", text="SnapO", icon='PIVOT_CURSOR')

    layout.operator("mesh.snap_x_zero", text="X = 0", icon='FULLSCREEN_EXIT')


classes = (
    MESH_OT_MedirDistancia,
    MESH_OT_ToggleSnapVertex,
    MESH_OT_OrigenDesdeEdge,
    MESH_OT_OrigenDesdeSeleccion,
    MESH_OT_snap_x_zero,
)
def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.VIEW3D_MT_editor_menus.append(draw_button)

def unregister():
    bpy.types.VIEW3D_MT_editor_menus.remove(draw_button)
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)

if __name__ == "__main__":
    register()
