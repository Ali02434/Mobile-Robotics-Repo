"""Flasche nach Foto modellieren, in Blender anzeigen und als OBJ exportieren.

Alle Masse stehen unten in Millimetern. Die Form zwischen den gemessenen
Stellen ist eine Annaeherung an das Foto.
"""

import math
from pathlib import Path

import bpy
from mathutils import Euler


OUTPUT_DIR = Path(__file__).resolve().parent
SEGMENTE = 96

# (Hoehe, Radius, Material): Gesamt 230 mm hoch, maximal 65 mm breit.
# Die Griffzone ist von 110 bis 140 mm etwa 50 mm breit.
# Der geschlossene Deckel ist 30 mm breit und endet bei 230 mm.
PROFIL_MM = [
    (0, 27.0, "flasche"),
    (2, 29.5, "flasche"),
    (7, 32.0, "flasche"),
    (14, 32.5, "flasche"),
    (91, 32.5, "flasche"),
    (97, 31.5, "flasche"),
    (103, 29.0, "flasche"),
    (110, 25.0, "flasche"),
    (115, 25.0, "flasche"),
    (135, 25.0, "flasche"),
    (140, 25.0, "flasche"),
    (146, 29.0, "flasche"),
    (152, 32.0, "flasche"),
    (159, 32.5, "flasche"),
    (169, 32.0, "flasche"),
    (179, 30.0, "flasche"),
    (189, 26.5, "flasche"),
    (198, 21.0, "flasche"),
    (205, 15.0, "flasche"),
    (209, 13.5, "flasche"),
    (210, 13.5, "flasche"),
    (210, 14.5, "deckel"),
    (212, 15.0, "deckel"),
    (215, 15.0, "deckel"),
    (216, 14.6, "deckel"),
    (217, 15.0, "deckel"),
    (227, 15.0, "deckel"),
    (229, 14.5, "deckel"),
    (230, 12.5, "deckel"),
]

bpy.ops.object.select_all(action="SELECT")
bpy.ops.object.delete(use_global=False)
bpy.context.scene.unit_settings.system = "METRIC"
bpy.context.scene.unit_settings.length_unit = "MILLIMETERS"

flaschen_material = bpy.data.materials.new(name="Flasche_Hellblau")
flaschen_material.diffuse_color = (0.55, 0.85, 0.9, 1.0)
deckel_material = bpy.data.materials.new(name="Deckel_Gruen")
deckel_material.diffuse_color = (0.02, 0.35, 0.23, 1.0)

# Rotationskoerper um die Z-Achse: jede Profilzeile bildet einen Ring.
vertices = []
for hoehe_mm, radius_mm, _ in PROFIL_MM:
    for i in range(SEGMENTE):
        winkel = 2 * math.pi * i / SEGMENTE
        vertices.append((
            radius_mm * math.cos(winkel) / 1000,
            radius_mm * math.sin(winkel) / 1000,
            hoehe_mm / 1000,
        ))

unten_mitte = len(vertices)
vertices.append((0.0, 0.0, 0.0))
oben_mitte = len(vertices)
vertices.append((0.0, 0.0, 0.230))

faces = []
material_indices = []
for ring in range(len(PROFIL_MM) - 1):
    material = 1 if PROFIL_MM[ring + 1][2] == "deckel" else 0
    for i in range(SEGMENTE):
        j = (i + 1) % SEGMENTE
        faces.append((
            ring * SEGMENTE + i,
            ring * SEGMENTE + j,
            (ring + 1) * SEGMENTE + j,
            (ring + 1) * SEGMENTE + i,
        ))
        material_indices.append(material)

for i in range(SEGMENTE):
    j = (i + 1) % SEGMENTE
    faces.append((i, unten_mitte, j))
    material_indices.append(0)
    last = (len(PROFIL_MM) - 1) * SEGMENTE
    faces.append((last + i, last + j, oben_mitte))
    material_indices.append(1)

mesh = bpy.data.meshes.new("Flasche_Mesh")
mesh.from_pydata(vertices, [], faces)
mesh.materials.append(flaschen_material)
mesh.materials.append(deckel_material)
mesh.update()
for polygon, material_index in zip(mesh.polygons, material_indices):
    polygon.material_index = material_index
    polygon.use_smooth = len(polygon.vertices) == 4

flasche = bpy.data.objects.new("Plastikflasche_500ml", mesh)
bpy.context.collection.objects.link(flasche)
bpy.ops.object.select_all(action="DESELECT")
flasche.select_set(True)
bpy.context.view_layer.objects.active = flasche

for screen in bpy.data.screens:
    for area in screen.areas:
        if area.type == "VIEW_3D":
            space = area.spaces.active
            space.region_3d.view_location = (0, 0, 0.115)
            space.region_3d.view_distance = 0.55
            space.region_3d.view_rotation = Euler(
                (math.radians(65), 0, math.radians(25)), "XYZ"
            ).to_quaternion()
            space.shading.type = "SOLID"
            space.shading.color_type = "MATERIAL"

obj_path = OUTPUT_DIR / "Flasche_500ml.obj"
bpy.ops.wm.obj_export(
    filepath=str(obj_path),
    export_selected_objects=True,
    export_triangulated_mesh=True,
    export_materials=True,
    forward_axis="Y",
    up_axis="Z",
)

bpy.context.preferences.filepaths.save_version = 0
blend_path = OUTPUT_DIR / "Flasche_500ml.blend"
bpy.ops.wm.save_as_mainfile(filepath=str(blend_path))
print(f"Erstellt: {obj_path}")
print(f"Blender-Projekt: {blend_path}")
