# Mobile Robotics: Becher und Flasche mit FoundationPose

Dieses Projekt enthält zwei selbst modellierte Objekte für die 6D-Pose-Schätzung mit einer RealSense D435 und [NVlabs/FoundationPose](https://github.com/NVlabs/FoundationPose).

| Objekt | Blender-Skript | 3D-Ansicht | Mesh für FoundationPose |
| --- | --- | --- | --- |
| Hohler Becher | `Blender.py` | `Becher_Test.blend` | `Becher_Test.obj` |
| Plastikflasche mit geschlossenem Deckel | `Flasche.py` | `Flasche_500ml.blend` | `Flasche_500ml.obj` und `Flasche_500ml.mtl` |

Die OBJ-Koordinaten sind in Metern. Der Becher ist 90 mm hoch und oben 78 mm breit, mit 2 mm Wand- und Bodenstärke. Die Flasche ist 230 mm hoch, maximal 65 mm breit und hat einen 30 mm breiten Deckel. Ihre Form zwischen den gemessenen Stellen ist nach einem Foto angenähert. Vor einer metrisch genauen Pose die Maße an den echten Objekten prüfen.

## Modelle in Blender ansehen oder neu erzeugen

```bash
blender Becher_Test.blend
blender Flasche_500ml.blend
```

Nach Änderungen an den Skripten werden `.blend` und `.obj` neu erzeugt mit:

```bash
blender --background --python Blender.py
blender --background --python Flasche.py
```

## FoundationPose starten

Nach der Einrichtung gemäß `INSTALLATION_NEUER_PC.md` im FoundationPose-Environment:

```bash
python foundationpose_live.py --foundationpose-dir /PFAD/ZU/FoundationPose --serial DEINE_SERIENNUMMER
```

Der Live-Adapter verwendet automatisch `Becher_Test.obj` und `Flasche_500ml.obj`. Modellgewichte und das FoundationPose-Repository werden separat installiert.
