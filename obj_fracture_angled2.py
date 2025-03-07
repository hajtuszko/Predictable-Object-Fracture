import bpy
import bmesh
import random
from mathutils import Vector
import math

# Informacje o pluginie
bl_info = {
    "blender": (4, 2, 0),
    "category": "Object",
    "description": "Splits selected mesh object into parts with seed and plane angle control.",
    "author": "Patryk powered by Grok & Kosmik123",
    "version": (1, 1, 2),  # Zaktualizowana wersja
}

def get_object_bounds(obj):
    """Oblicza granice obiektu na podstawie wierzchołków w przestrzeni globalnej."""
    if obj.type != 'MESH':
        print(f"{obj.name} nie jest siatką!")
        return None
    
    mesh = obj.data
    min_coords = Vector((float('inf'), float('inf'), float('inf')))
    max_coords = Vector((-float('inf'), -float('inf'), -float('inf')))
    
    for vert in mesh.vertices:
        world_coord = obj.matrix_world @ vert.co
        min_coords.x = min(min_coords.x, world_coord.x)
        min_coords.y = min(min_coords.y, world_coord.y)
        min_coords.z = min(min_coords.z, world_coord.z)
        max_coords.x = max(max_coords.x, world_coord.x)
        max_coords.y = max(max_coords.y, world_coord.y)
        max_coords.z = max(max_coords.z, world_coord.z)
    
    return min_coords, max_coords

def create_cutting_plane(point, normal, thickness=0.001):
    """Tworzy płaszczyznę tnącą o grubości 0,001 m."""
    bpy.ops.mesh.primitive_plane_add(size=10, location=point)
    plane_obj = bpy.context.active_object
    plane_obj.name = "CuttingPlane"
    
    plane_obj.rotation_mode = 'QUATERNION'
    up_vector = Vector((0, 0, 1))
    plane_obj.rotation_quaternion = up_vector.rotation_difference(normal)
    
    solidify = plane_obj.modifiers.new(name="Solidify", type='SOLIDIFY')
    solidify.thickness = thickness
    bpy.context.view_layer.objects.active = plane_obj
    bpy.ops.object.modifier_apply(modifier="Solidify")
    
    return plane_obj

def calculate_object_volume(obj):
    """Oblicza objętość obiektu na podstawie siatki."""
    if not obj or obj.type != 'MESH':
        print("Please select a mesh object.")
        return 0.0
    
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.mode_set(mode='OBJECT')
    mesh = obj.to_mesh()
    bm = bmesh.new()
    bm.from_mesh(mesh)
    
    volume = bm.calc_volume()
    
    bm.free()
    obj.to_mesh_clear()
    
    print(f"Object '{obj.name}' has a volume of: {volume:.6f} cubic units")
    return volume

def cut_and_separate(obj, plane):
    """Przecina obiekt grubą płaszczyzną i rozdziela na dwa obiekty."""
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.select_all(action='DESELECT')
    obj.select_set(True)
    print(f"Przecinanie {obj.name} płaszczyzną")
    
    original_matrix = obj.matrix_world.copy()
    
    point, normal = plane
    cutting_plane = create_cutting_plane(point, normal, thickness=0.001)
    
    bpy.context.view_layer.objects.active = obj
    bool_mod = obj.modifiers.new(name="BooleanCut", type='BOOLEAN')
    bool_mod.operation = 'DIFFERENCE'
    bool_mod.object = cutting_plane
    bool_mod.solver = 'EXACT'
    
    obj.select_set(True)
    bpy.ops.object.modifier_apply(modifier="BooleanCut")
    
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.mesh.separate(type='LOOSE')
    bpy.ops.object.mode_set(mode='OBJECT')
    
    new_objects = bpy.context.selected_objects
    new_objects.remove(cutting_plane)
    
    zaznaczenie = ""
    for obiekt in new_objects:
        zaznaczenie += obiekt.name + ", "
    print(f"Zaznaczenie to: {zaznaczenie}")
    
    if len(new_objects) != 2:
        print(f"Nie udało się rozdzielić {obj.name} na dokładnie 2 części! Ilosc czesci to {len(new_objects)}")
        bpy.data.objects.remove(cutting_plane, do_unlink=True)
        return None, None
    
    new_obj1, new_obj2 = new_objects
    
    bpy.context.view_layer.objects.active = cutting_plane
    cutting_plane.select_set(True)
    
    new_obj1.matrix_world = original_matrix
    new_obj2.matrix_world = original_matrix
    
    new_obj1.select_set(False)
    new_obj2.select_set(False)
    
    bpy.ops.object.delete()
    return new_obj1, new_obj2

def process_object(obj):
    """Wypełnia miejsca cięcia i optymalizuje powierzchnie."""
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.select_all(action='DESELECT')
    obj.select_set(True)
    
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='DESELECT')
    
    bm = bmesh.from_edit_mesh(obj.data)
    bm.edges.ensure_lookup_table()
    for edge in bm.edges:
        if edge.is_boundary:
            edge.select = True
    
    if any(e.select for e in bm.edges):
        bpy.ops.mesh.edge_face_add()
        bpy.ops.mesh.select_all(action='SELECT')
        bpy.ops.mesh.tris_convert_to_quads()
        bpy.ops.mesh.normals_make_consistent(inside=False)
        print(f"Wypełniono i przetworzono powierzchnie dla {obj.name}")
    else:
        print(f"Brak otwartych krawędzi w {obj.name}")
    
    bpy.ops.object.mode_set(mode='OBJECT')

def rename_selected_objects():
    """Zmienia nazwy wybranych obiektów na *nazwa*_PartX."""
    active_obj = bpy.context.active_object
    selected_objs = [obj for obj in bpy.context.selected_objects]
    
    if not active_obj or not selected_objs:
        print("No active object or no other selected objects.")
        return
    
    base_name = active_obj.name.split('_')[0]  # Usuwa wszystko po _
    
    for index, obj in enumerate(selected_objs, start=1):
        obj.name = f"{base_name}_Part{index}"
    
    print("Objects renamed successfully.")

class OBJECT_OT_Fracture(bpy.types.Operator):
    """Rozdziela wybrany obiekt na określoną liczbę części z kontrolą seeda i kąta płaszczyzn"""
    bl_idname = "object.fracture_break"
    bl_label = "Break"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return context.active_object is not None and context.active_object.type == 'MESH'

    def execute(self, context):
        obj = context.active_object
        if not obj or obj.type != 'MESH':
            self.report({'ERROR'}, "Brak poprawnego obiektu wejściowego!")
            return {'CANCELLED'}
        
        target_count = context.scene.fracture_count
        seed_value = context.scene.fracture_seed
        if target_count < 2:
            self.report({'ERROR'}, "Liczba części musi być co najmniej 2!")
            return {'CANCELLED'}
        
        self.report({'INFO'}, f"Podział obiektu {obj.name} na {target_count} części z seedem {seed_value}")
        
        # Ustawienie seeda dla losowości
        random.seed(seed_value)
        
        # Lista do śledzenia wszystkich utworzonych obiektów
        all_objects = [obj]
        # Słownik do zapisywania płaszczyzn cięcia dla każdego obiektu (obiekt -> normalna)
        cutting_planes = {obj: None}  # Początkowy obiekt nie ma jeszcze płaszczyzny
        
        while len(all_objects) < target_count:
            if not all_objects:
                self.report({'ERROR'}, "Brak obiektów do dalszego podziału!")
                return {'CANCELLED'}
            
            # Wybierz obiekt o największej objętości
            obj_to_split = max(all_objects, key=calculate_object_volume)
            all_objects.remove(obj_to_split)
            
            # Generuj losową płaszczyznę z uwzględnieniem poprzedniej
            bounds = get_object_bounds(obj_to_split)
            if not bounds:
                self.report({'ERROR'}, f"Nie udało się obliczyć granic dla {obj_to_split.name}!")
                return {'CANCELLED'}
            center = (bounds[0] + bounds[1]) / 2
            point = center
            
            # Pobierz poprzednią normalną dla tego obiektu, jeśli istnieje
            previous_normal = cutting_planes.get(obj_to_split)
            
            # Generuj nową normalną z ograniczeniem kąta >= 45 stopni
            attempts = 0
            max_attempts = 100  # Ograniczenie, aby uniknąć nieskończonej pętli
            while attempts < max_attempts:
                normal = Vector((random.uniform(-1, 1), random.uniform(-1, 1), random.uniform(-1, 1))).normalized()
                if previous_normal is None:
                    break  # Pierwsze cięcie nie wymaga ograniczenia kąta
                angle = normal.angle(previous_normal)  # Kąt w radianach
                if angle >= math.radians(45):  # Co najmniej 45 stopni
                    break
                attempts += 1
            if attempts >= max_attempts:
                self.report({'WARNING'}, f"Nie udało się znaleźć normalnej z kątem >= 45° dla {obj_to_split.name}, użyto losowej.")
            
            plane = (point, normal)
            
            # Podziel wybrany obiekt
            self.report({'INFO'}, f"Dzielimy obiekt {obj_to_split.name} z normalną {normal}!")
            new_obj1, new_obj2 = cut_and_separate(obj_to_split, plane)
            if not new_obj1 or not new_obj2:
                self.report({'ERROR'}, f"Nie udało się rozdzielić {obj_to_split.name}!")
                return {'CANCELLED'}
            
            # Przetwórz nowe obiekty
            process_object(new_obj1)
            process_object(new_obj2)
            
            # Zapisz płaszczyznę cięcia dla nowych obiektów
            cutting_planes[new_obj1] = normal
            cutting_planes[new_obj2] = normal
            
            # Dodaj nowe obiekty do listy
            all_objects.extend([new_obj1, new_obj2])
            print(f"Aktualna liczba obiektów: {len(all_objects)}")
        
        # Zaznacz wszystkie utworzone obiekty
        bpy.ops.object.select_all(action='DESELECT')
        for o in all_objects:
            o.select_set(True)
        bpy.context.view_layer.objects.active = all_objects[0]  # Ustaw pierwszy jako aktywny
        
        # Wywołaj funkcję zmiany nazw
        rename_selected_objects()
        
        self.report({'INFO'}, f"Pomyślnie podzielono {obj.name} na {len(all_objects)} części")
        return {'FINISHED'}

class OBJECT_PT_FracturePanel(bpy.types.Panel):
    """Panel narzędzia Object Fracture Tool"""
    bl_label = "Object Fracture Tool"
    bl_idname = "OBJECT_PT_fracture"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "Object"

    def draw(self, context):
        layout = self.layout
        layout.prop(context.scene, "fracture_count", text="Count")
        layout.prop(context.scene, "fracture_seed", text="Seed")
        layout.operator("object.fracture_break", text="Break")

# Definiuj właściwości sceny
bpy.types.Scene.fracture_count = bpy.props.IntProperty(
    name="Count",
    description="Number of parts to split the object into",
    default=2,
    min=2,
    soft_max=10
)

bpy.types.Scene.fracture_seed = bpy.props.IntProperty(
    name="Seed",
    description="Seed value for consistent fracture planes (1-1000)",
    default=1,
    min=1,
    max=1000
)

def register():
    bpy.utils.register_class(OBJECT_OT_Fracture)
    bpy.utils.register_class(OBJECT_PT_FracturePanel)

def unregister():
    bpy.utils.unregister_class(OBJECT_OT_Fracture)
    bpy.utils.unregister_class(OBJECT_PT_FracturePanel)
    del bpy.types.Scene.fracture_count
    del bpy.types.Scene.fracture_seed

if __name__ == "__main__":
    register()