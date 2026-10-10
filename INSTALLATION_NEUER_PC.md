# Installation auf einem neuen PC (Vorlage)

Stand: 10.10.2026. Ziel-PC: **Ubuntu 22.04.5 LTS, Intel Core i7-13700, 32 GB RAM, NVIDIA RTX A2000 12 GB, RealSense D435**. Die Installation ist noch nicht auf diesem PC getestet. NVIDIA führt die RTX A2000 mit [Compute Capability 8.6](https://developer.nvidia.com/cuda/gpus); die GPU erfüllt damit die grundsätzliche CUDA-Anforderung. Die angegebene „CUDA 13“-Version allein sagt noch nicht, ob das Toolkit mit `nvcc` installiert ist oder nur der Treiber diese CUDA-Version unterstützt.

## 1. Hardware und Treiber prüfen

1. D435 an einen USB-3-Port anschließen. NVIDIA-Treiber gemäß GPU/Distribution installieren; danach `nvidia-smi` prüfen. Wenn CUDA 13 als Toolkit verwendet wird, ist laut [NVIDIA mindestens Treiber 580](https://docs.nvidia.com/deploy/cuda-compatibility/minor-version-compatibility.html) nötig.
2. `lsusb` und `python d435_rgb.py --list` nach Installation von `pyrealsense2` zur Kameraerkennung nutzen. Bei Zugriffsproblemen die zur installierten [librealsense-Version passenden Linux-udev-Regeln](https://github.com/realsenseai/librealsense/blob/master/doc/distribution_linux.md) einrichten und neu anmelden.
3. GPU-Modell, Treiberversion, Linux-Version und `nvcc --version` notieren. FoundationPose baut CUDA-Erweiterungen; ein passendes CUDA-Toolkit mit `nvcc` ist für den Conda-Weg nötig.

## 2. Anwendung und FoundationPose installieren

Miniforge/Conda, Git und ein CUDA-Toolkit passend zum **PyTorch-Build** installieren. `nvidia-smi` zeigt die vom Treiber unterstützte CUDA-Version; `nvcc --version` zeigt das für Erweiterungen verwendete Toolkit. Beide können verschieden sein. Den PyTorch-CUDA-Build über die [offizielle PyTorch-Auswahl](https://pytorch.org/get-started/locally/) bestimmen. Die folgende `cu124`-URL ist das **Beispiel aus dem FoundationPose-README**; dafür beim Bauen der CUDA-Erweiterungen ein passendes 12.4-Toolkit über `CUDA_HOME` auswählen. Falls nur CUDA 13 als Toolkit vorhanden ist, den kompatiblen PyTorch-Build und Toolkit-Pfad zuerst zusammen festlegen.

```bash
git clone https://github.com/NVlabs/FoundationPose.git
cd FoundationPose
conda env create -f environment.yml
conda activate foundationpose
python -m pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu124
export CUDA_HOME=/usr/local/cuda-12.4  # Beispiel: Pfad an nvcc-Installation anpassen
export PATH="$CUDA_HOME/bin:$PATH"
python -m pip install --no-build-isolation "git+https://github.com/facebookresearch/pytorch3d.git"
python -m pip install --no-build-isolation "git+https://github.com/NVlabs/nvdiffrast.git"
python -m pip install -r requirements.txt
bash build_all_conda.sh
python -m pip install pyrealsense2 opencv-python
```

Die offiziellen [Conda-Schritte](https://github.com/NVlabs/FoundationPose#env-setup-option-2-conda-local) nennen Python 3.11, PyTorch3D, NVDiffRast und `build_all_conda.sh`. Wenn der Toolkit-Pfad abweicht, `CUDA_HOME` anpassen. Die NVIDIA-Treiberversion muss den ausgewählten CUDA-Build unterstützen. Bei Installationsfehlern zuerst diese Kompatibilität prüfen; nicht blind Pakete hoch- oder herabstufen.

## 3. Modellgewichte und Demo

Die offiziellen [Netzgewichte](https://github.com/NVlabs/FoundationPose#data-prepare) in `FoundationPose/weights/` ablegen: Refiner `2023-10-28-18-33-37`, Scorer `2024-01-11-20-02-45`. Die offiziellen Demodaten nach `FoundationPose/demo_data/` entpacken. Danach aus dem FoundationPose-Verzeichnis:

```bash
conda activate foundationpose
python check_env.py
python run_demo.py
```

Erst wenn die Demo eine Pose und Visualisierung erzeugt, die eigene Kamera anschließen. Gewichte und Daten werden nicht mit diesem kleinen Projekt mitgeliefert; Bezugsquelle und endgültige Dateinamen nach Download protokollieren. Mit der 12-GB-A2000 zuerst **ein Objekt** testen und GPU-Speicher mit `nvidia-smi` beobachten; zwei parallele Objektzustände und die erste Registrierung benötigen mehr Speicher.

## 4. D435 prüfen und Projekt starten

Das Projekt auf den PC kopieren/klonen. Im aktivierten `foundationpose`-Environment:

```bash
cd /PFAD/ZUM/Hackathon
python d435_rgb.py --list
python d435_rgb.py --serial DEINE_SERIENNUMMER
```

`d435_rgb.py` testet **nur RGB**. Der Live-Adapter verarbeitet RGB-D und FoundationPose. Für den ersten Modelltest ein Mesh in realer Größe laden, danach beide Objekte zusammen testen.

Der Live-Adapter verwendet standardmäßig die selbst modellierten Meshes `Becher_Test.obj` und `Flasche_500ml.obj`. Die Flasche benötigt zusätzlich `Flasche_500ml.mtl` im gleichen Ordner. Aus dem Projektordner im aktivierten Environment starten:

```bash
python foundationpose_live.py --foundationpose-dir /PFAD/ZU/FoundationPose --serial DEINE_SERIENNUMMER
```

Für einen Speichertest mit nur einem Objekt `--mesh Becher_Test.obj` ergänzen. Die `.blend`-Dateien dienen zum Bearbeiten in Blender; FoundationPose lädt die `.obj`-Dateien. Mit `blender --python Blender.py` oder `blender --python Flasche.py` werden die Modelle und Exporte neu erzeugt.

`--mesh-scale` skaliert die OBJ-Koordinaten vor FoundationPose in Meter. Die selbst modellierten OBJ-Dateien sind bereits in Metern; Standard `1` ist dafür richtig, sofern die angegebenen Maße mit den realen Objekten übereinstimmen. Nach einer Messung gilt bei Abweichung `Faktor = reales Maß in Metern / entsprechendes Mesh-Maß`. Für zwei Objekte können zwei Faktoren angegeben werden, z. B. `--mesh-scale 1.0 0.8`. Die Faktoren werden im JSONL-Protokoll mitgeschrieben.

Beim Start für Objekt 1 und 2 jeweils mit der Maus eine enge ROI ziehen und mit Enter bestätigen. Danach die grün markierte Maske mit Enter bestätigen; eine andere Taste verwirft sie. `1` oder `2` startet die Registrierung des jeweiligen Objekts erneut, `Q` beendet. Die Posen werden als JSON-Zeilen in `poses.jsonl` geschrieben; die 4×4-Matrix transformiert Mesh-Koordinaten in den optischen Farbkamerarahmen. Ohne Desktop funktioniert dieser interaktive Start nicht. Der Adapter wurde mangels Ziel-PC/Kamera/GPU bisher nur statisch geprüft.

## 5. Ergebnis auf dem Ziel-PC festhalten

Für reproduzierbare Neuinstallation diese Werte in die Projektdokumentation übernehmen: FoundationPose-Commit (`git rev-parse HEAD`), Conda-Export (`conda env export --from-history`), `python -m pip freeze`, `nvidia-smi`, `nvcc --version`, D435-Firmware/Seriennummer, Meshversionen und SHA-256-Prüfsummen der Gewichte. Die endgültige Anleitung kann erst nach einem erfolgreichen Test mit den beiden Meshes und der Ziel-GPU als verifiziert gelten.
