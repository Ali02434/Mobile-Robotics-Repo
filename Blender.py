"""Hohlen Becher in Blender anzeigen und als OBJ fuer FoundationPose exportieren."""

import math
from pathlib import Path

import bpy
from mathutils import Euler


OUTPUT_DIR = Path(__file__).resolve().parent
HOEHE = 0.09
DURCHMESSER_OBEN = 0.078
DURCHMESSER_UNTEN = 0.052
WANDSTAERKE = 0.002
BODENSTAERKE = 0.002
SEGMENTE = 96

# Die Standardobjekte entfernen, damit nur das neue Mesh zu sehen ist.
bpy.ops.object.select_all(action="SELECT")
bpy.ops.object.delete(use_global=False)

bpy.context.scene.unit_settings.system = "METRIC"
bpy.context.scene.unit_settings.length_unit = "MILLIMETERS"

radius_unten = DURCHMESSER_UNTEN / 2
radius_oben = DURCHMESSER_OBEN / 2
radius_innen_oben = radius_oben - WANDSTAERKE
radius_innen_unten = (
    radius_unten
    + (radius_oben - radius_unten) * BODENSTAERKE / HOEHE
    - WANDSTAERKE
)
if min(radius_innen_oben, radius_innen_unten) <= 0 or BODENSTAERKE >= HOEHE:
    raise ValueError("Wand- oder Bodenstaerke ist fuer diese Bechermasse zu gross")

# Vier Ringe bilden Aussenwand, Rand und Innenwand. Zwei Mittelpunkte
# schliessen nur den Boden; die obere Oeffnung bleibt frei.
vertices = []
for radius, z in (
    (radius_unten, 0.0),
    (radius_oben, HOEHE),
    (radius_innen_oben, HOEHE),
    (radius_innen_unten, BODENSTAERKE),
):
    for i in range(SEGMENTE):
        angle = 2 * math.pi * i / SEGMENTE
        vertices.append((radius * math.cos(angle), radius * math.sin(angle), z))

unten_mitte = len(vertices)
vertices.append((0.0, 0.0, 0.0))
innen_mitte = len(vertices)
vertices.append((0.0, 0.0, BODENSTAERKE))

faces = []
for i in range(SEGMENTE):
    j = (i + 1) % SEGMENTE
    au = i
    au_next = j
    ao = SEGMENTE + i
    ao_next = SEGMENTE + j
    io = 2 * SEGMENTE + i
    io_next = 2 * SEGMENTE + j
    iu = 3 * SEGMENTE + i
    iu_next = 3 * SEGMENTE + j

    faces.extend((
        (au, au_next, ao_next), (au, ao_next, ao),       # Aussenwand
        (ao, ao_next, io_next), (ao, io_next, io),       # Rand
        (io, io_next, iu_next), (io, iu_next, iu),       # Innenwand
        (au, unten_mitte, au_next),                       # Unterseite
        (iu, iu_next, innen_mitte),                       # Innenboden
    ))

mesh = bpy.data.meshes.new("Becher_Test_Mesh")
mesh.from_pydata(vertices, [], faces)
mesh.update()
becher = bpy.data.objects.new("Becher_Test", mesh)
bpy.context.collection.objects.link(becher)
bpy.ops.object.select_all(action="DESELECT")
becher.select_set(True)
bpy.context.view_layer.objects.active = becher
becher.name = "Becher_Test"
becher.data.name = "Becher_Test_Mesh"

material = bpy.data.materials.new(name="Becher_Blau")
material.diffuse_color = (0.12, 0.45, 0.9, 1.0)
becher.data.materials.append(material)

# Ansicht auf den kleinen Becher ausrichten und seine Farbe anzeigen.
for screen in bpy.data.screens:
    for area in screen.areas:
        if area.type == "VIEW_3D":
            space = area.spaces.active
            space.region_3d.view_location = (0, 0, HOEHE / 2)
            space.region_3d.view_distance = 0.35
            space.region_3d.view_rotation = Euler(
                (math.radians(55), 0, math.radians(35)), "XYZ"
            ).to_quaternion()
            space.shading.type = "SOLID"
            space.shading.color_type = "MATERIAL"

obj_path = OUTPUT_DIR / "Becher_Test.obj"
bpy.ops.wm.obj_export(
    filepath=str(obj_path),
    export_selected_objects=True,
    export_triangulated_mesh=True,
    export_materials=False,
    forward_axis="Y",
    up_axis="Z",
)

# Die .blend-Datei kann spaeter direkt mit Blender geoeffnet werden.
bpy.context.preferences.filepaths.save_version = 0
blend_path = OUTPUT_DIR / "Becher_Test.blend"
bpy.ops.wm.save_as_mainfile(filepath=str(blend_path))
print(f"Erstellt: {obj_path}")
print(f"Blender-Projekt: {blend_path}")

