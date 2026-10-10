#!/usr/bin/env python3
"""Live 6D-Pose für zwei bekannte Objekte mit D435 und NVlabs/FoundationPose."""

import argparse
import json
from pathlib import Path
import sys
import time


ROOT = Path(__file__).resolve().parent
DEFAULT_MESHES = (
    ROOT / "Becher_Test.obj",
    ROOT / "Flasche_500ml.obj",
)


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--foundationpose-dir", type=Path, required=True)
    parser.add_argument("--mesh", type=Path, nargs="+", default=DEFAULT_MESHES,
                        metavar="OBJ", help="ein oder zwei Meshes; Standard: beide gelieferten")
    parser.add_argument("--mesh-scale", type=float, nargs="+", default=[1.0], metavar="FAKTOR",
                        help="Mesh-Koordinaten vor Pose-Schätzung in Meter skalieren; ein Wert für alle oder je Objekt")
    parser.add_argument("--serial", help="RealSense-Seriennummer")
    parser.add_argument("--width", type=int, default=640)
    parser.add_argument("--height", type=int, default=480)
    parser.add_argument("--fps", type=int, default=30)
    parser.add_argument("--output", type=Path, default=ROOT / "poses.jsonl")
    parser.add_argument("--register-iterations", type=int, default=5)
    parser.add_argument("--track-iterations", type=int, default=2)
    args = parser.parse_args(argv)
    if min(args.width, args.height, args.fps,
           args.register_iterations, args.track_iterations) <= 0:
        parser.error("Auflösung, FPS und Iterationen müssen positiv sein")
    if len(args.mesh) not in (1, 2):
        parser.error("Ein oder zwei Meshes angeben")
    if len(args.mesh_scale) not in (1, len(args.mesh)) or any(s <= 0 for s in args.mesh_scale):
        parser.error("--mesh-scale benötigt einen positiven Wert oder einen Wert je Mesh")
    if len(args.mesh_scale) == 1:
        args.mesh_scale *= len(args.mesh)
    if not (args.foundationpose_dir / "estimater.py").is_file():
        parser.error("--foundationpose-dir muss das NVlabs/FoundationPose-Repository enthalten")
    for run_name in ("2023-10-28-18-33-37", "2024-01-11-20-02-45"):
        for filename in ("config.yml", "model_best.pth"):
            weight = args.foundationpose_dir / "weights" / run_name / filename
            if not weight.is_file():
                parser.error(f"FoundationPose-Gewicht fehlt: {weight}")
    for mesh in args.mesh:
        if not mesh.is_file():
            parser.error(f"Mesh fehlt: {mesh}")
    return args


def camera_matrix(intrinsics, np):
    return np.array([[intrinsics.fx, 0, intrinsics.ppx],
                     [0, intrinsics.fy, intrinsics.ppy],
                     [0, 0, 1]], dtype=np.float32)


def select_mask(image_bgr, depth_m, name, cv2, np):
    """ROI per Maus wählen; GrabCut erzeugt daraus eine binäre Objektmaske."""
    title = f"{name}: Objekt eng einrahmen, Enter bestaetigt"
    x, y, w, h = map(int, cv2.selectROI(title, image_bgr, False, False))
    cv2.destroyWindow(title)
    if w < 10 or h < 10:
        return None
    gc_mask = np.zeros(image_bgr.shape[:2], np.uint8)
    bg = np.zeros((1, 65), np.float64)
    fg = np.zeros((1, 65), np.float64)
    cv2.grabCut(image_bgr, gc_mask, (x, y, w, h), bg, fg, 5, cv2.GC_INIT_WITH_RECT)
    mask = np.isin(gc_mask, (cv2.GC_FGD, cv2.GC_PR_FGD)) & (depth_m > 0.001)
    if np.count_nonzero(mask) < 100:
        print(f"{name}: zu wenige Objektpixel mit gültiger Tiefe; erneut wählen")
        return None
    preview = image_bgr.copy()
    preview[mask] = (0.5 * preview[mask] + 0.5 * np.array([0, 255, 0])).astype(np.uint8)
    cv2.imshow("Maske: Enter akzeptiert, andere Taste verwirft", preview)
    key = cv2.waitKey(0) & 0xFF
    cv2.destroyWindow("Maske: Enter akzeptiert, andere Taste verwirft")
    return mask if key in (10, 13) else None


def draw_pose(image, pose, mesh_bounds, K, color, cv2, np):
    lo, hi = mesh_bounds
    corners = np.array([[x, y, z] for x in (lo[0], hi[0])
                        for y in (lo[1], hi[1]) for z in (lo[2], hi[2])])
    xyz = corners @ pose[:3, :3].T + pose[:3, 3]
    if np.any(xyz[:, 2] <= 0.001):
        return
    uv = xyz[:, :2] / xyz[:, 2, None]
    uv = uv @ np.diag([K[0, 0], K[1, 1]]) + K[:2, 2]
    uv = np.rint(uv).astype(int)
    for i in range(8):
        for bit in (1, 2, 4):
            j = i ^ bit
            if i < j:
                cv2.line(image, tuple(uv[i]), tuple(uv[j]), color, 2)


def run(args):
    try:
        import cv2
        import numpy as np
        import pyrealsense2 as rs
        import trimesh
        import nvdiffrast.torch as dr
        import torch
        from learning.training.predict_pose_refine import PoseRefinePredictor
        from learning.training.predict_score import ScorePredictor
        from estimater import FoundationPose
    except ImportError as exc:
        raise RuntimeError(f"Abhängigkeit fehlt: {exc}. Siehe INSTALLATION_NEUER_PC.md") from exc
    if not torch.cuda.is_available():
        raise RuntimeError("PyTorch erkennt keine NVIDIA-GPU. Treiber/CUDA-Build prüfen")

    meshes = [trimesh.load(str(p), force="mesh", process=False) for p in args.mesh]
    for mesh, mesh_scale in zip(meshes, args.mesh_scale):
        mesh.apply_scale(mesh_scale)
    for path, mesh in zip(args.mesh, meshes):
        if len(mesh.vertices) == 0 or len(mesh.faces) == 0 or not np.isfinite(mesh.vertices).all():
            raise RuntimeError(f"Ungültiges Mesh: {path}")
        print(f"{path.name} ({path.parent.name}): Ausdehnung {mesh.extents} Mesh-Einheiten")
    scorer, refiner, glctx = ScorePredictor(), PoseRefinePredictor(), dr.RasterizeCudaContext()
    estimators = [FoundationPose(model_pts=m.vertices, model_normals=m.vertex_normals,
                                 mesh=m, scorer=scorer, refiner=refiner, glctx=glctx,
                                 debug=0, debug_dir=str(ROOT / "debug" / f"obj{i}"))
                  for i, m in enumerate(meshes, 1)]
    poses = [None] * len(meshes)
    pending = set(range(len(meshes)))
    colors = [(0, 200, 255), (255, 100, 0)]
    ctx = rs.context()
    devices = list(ctx.query_devices())
    serials = [d.get_info(rs.camera_info.serial_number) for d in devices]
    if not serials:
        raise RuntimeError("Keine RealSense gefunden")
    if args.serial and args.serial not in serials:
        raise RuntimeError(f"Kamera {args.serial} nicht gefunden: {serials}")
    if not args.serial and len(serials) > 1:
        raise RuntimeError("Mehrere Kameras vorhanden: --serial angeben")
    serial = args.serial or serials[0]
    pipeline = rs.pipeline(ctx)
    config = rs.config()
    config.enable_device(serial)
    config.enable_stream(rs.stream.color, args.width, args.height, rs.format.bgr8, args.fps)
    config.enable_stream(rs.stream.depth, args.width, args.height, rs.format.z16, args.fps)
    profile = pipeline.start(config)
    try:
        scale = profile.get_device().first_depth_sensor().get_depth_scale()
        align = rs.align(rs.stream.color)
        intr = profile.get_stream(rs.stream.color).as_video_stream_profile().get_intrinsics()
        K = camera_matrix(intr, np)
        print(f"D435 {serial}, Depth-Skala {scale} m/Einheit. ROI 1/2 wählen; Q beendet.")
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open("a", encoding="utf-8") as log:
            while True:
                frames = align.process(pipeline.wait_for_frames(timeout_ms=5000))
                color_frame, depth_frame = frames.get_color_frame(), frames.get_depth_frame()
                if not color_frame or not depth_frame:
                    continue
                bgr = np.asanyarray(color_frame.get_data()).copy()
                depth = np.asanyarray(depth_frame.get_data()).astype(np.float32) * scale
                rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
                if rgb.shape[:2] != depth.shape:
                    raise RuntimeError("Ausrichtung fehlgeschlagen: RGB/Depth haben verschiedene Größen")
                statuses = ["uninitialisiert" if p is None else "tracking" for p in poses]
                for i in range(len(meshes)):
                    try:
                        if i in pending:
                            mask = select_mask(bgr, depth, f"Objekt {i+1}", cv2, np)
                            pending.remove(i)
                            if mask is None:
                                continue
                            pose = estimators[i].register(K=K, rgb=rgb, depth=depth,
                                                          ob_mask=mask,
                                                          iteration=args.register_iterations)
                            statuses[i] = "registriert"
                        elif poses[i] is not None:
                            pose = estimators[i].track_one(rgb=rgb, depth=depth, K=K,
                                                           iteration=args.track_iterations)
                        else:
                            continue
                        if pose is None or np.shape(pose) != (4, 4) or not np.isfinite(pose).all():
                            raise RuntimeError("ungültige Pose")
                        poses[i] = np.asarray(pose)
                    except (RuntimeError, ValueError) as exc:
                        print(f"Objekt {i+1}: {exc}; Registrierung erneut nötig", file=sys.stderr)
                        poses[i] = None
                        pending.add(i)
                        statuses[i] = "verloren"
                display = bgr.copy()
                for i, (pose, mesh) in enumerate(zip(poses, meshes)):
                    if pose is not None:
                        draw_pose(display, pose, mesh.bounds, K, colors[i], cv2, np)
                    record = {"object_id": i + 1, "mesh": str(args.mesh[i]),
                              "mesh_scale_to_m": args.mesh_scale[i],
                              "camera_serial": serial, "frame_id": color_frame.get_frame_number(),
                              "camera_timestamp_ms": color_frame.get_timestamp(),
                              "camera_timestamp_domain": str(color_frame.get_frame_timestamp_domain()),
                              "received_at_unix_ns": time.time_ns(), "camera_K": K.tolist(),
                              "depth_scale_m": scale, "status": statuses[i],
                              "T_camera_object": pose.tolist() if pose is not None else None}
                    log.write(json.dumps(record) + "\n")
                    cv2.putText(display, f"{i+1}: {statuses[i]}", (10, 28 + 28*i),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.7, colors[i], 2)
                log.flush()
                cv2.imshow("FoundationPose | 1/2: neu registrieren | Q: Ende", display)
                key = cv2.waitKey(1) & 0xFF
                if key in (ord("q"), ord("Q"), 27):
                    break
                if key in (ord("1"), ord("2")):
                    i = key - ord("1")
                    if i < len(meshes):
                        poses[i] = None
                        pending.add(i)
    finally:
        pipeline.stop()
        cv2.destroyAllWindows()


def main(argv=None):
    args = parse_args(argv)
    sys.path.insert(0, str(args.foundationpose_dir.resolve()))
    try:
        run(args)
    except (RuntimeError, OSError) as exc:
        print(f"Fehler: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
