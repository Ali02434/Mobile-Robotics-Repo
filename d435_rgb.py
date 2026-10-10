#!/usr/bin/env python3
"""D435-Farbbild: python d435_rgb.py | --list | --serial NUMMER.

Installation: python -m pip install pyrealsense2 opencv-python numpy
Tasten: S = unveraendertes Bild speichern, Q/Esc = Ende.
Nur der Farbsensor wird aktiviert. OpenCV verwendet BGR-Kanalreihenfolge.
"""
import argparse
from datetime import datetime, timezone
from pathlib import Path
import sys
import time


def process_frame(frame_bgr, metadata):
    """Eigene CV hier einbauen. frame_bgr: uint8, Form (Hoehe, Breite, 3).

    metadata enthaelt Kamera-Seriennummer, Frame-ID, Kamerazeitstempel
    und Empfangszeit. Kamerazeiten verschiedener Geraete sind nicht
    automatisch synchronisiert.
    Spaeter z.B.: results = model(frame_bgr, verbose=False)
    Modell einmal vor der Schleife laden, nicht bei jedem Bild!
    """
    return frame_bgr


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--list', action='store_true', help='Kameras auflisten')
    parser.add_argument('--serial', help='Seriennummer bei mehreren Kameras')
    parser.add_argument('--width', type=int, default=640)
    parser.add_argument('--height', type=int, default=480)
    parser.add_argument('--fps', type=int, default=30)
    parser.add_argument('--output', type=Path, default=Path('captures'))
    parser.add_argument('--headless', action='store_true', help='Ohne Fenster; Ctrl+C beendet')
    args = parser.parse_args()
    if min(args.width, args.height, args.fps) <= 0:
        parser.error('Aufloesung und FPS muessen positiv sein.')

    try:
        import pyrealsense2 as rs
        import numpy as np
        import cv2
    except ImportError as exc:
        print(f'Fehlendes Paket: {exc}\nInstallation: python -m pip install '
              'pyrealsense2 opencv-python numpy', file=sys.stderr)
        return 1

    pipeline = None
    started = False
    window = 'D435 RGB | S: Bild speichern | Q/Esc: Ende'
    try:
        context = rs.context()
        devices = list(context.query_devices())
        if not devices:
            raise RuntimeError('Keine RealSense gefunden. USB-Datenkabel, USB-Port '
                               'und Linux-udev-Regeln pruefen.')
        serials = []
        for device in devices:
            serial = device.get_info(rs.camera_info.serial_number)
            serials.append(serial)
            print(f'{device.get_info(rs.camera_info.name)} | Seriennummer: {serial}')
        if args.list:
            return 0
        if args.serial and args.serial not in serials:
            raise RuntimeError('Gewaehlte Seriennummer wurde nicht gefunden.')
        if not args.serial and len(serials) > 1:
            raise RuntimeError('Mehrere Kameras gefunden. Mit --serial NUMMER auswaehlen.')
        serial = args.serial or serials[0]

        pipeline = rs.pipeline(context)
        config = rs.config()
        config.enable_device(serial)
        config.disable_all_streams()
        config.enable_stream(rs.stream.color, args.width, args.height,
                             rs.format.bgr8, args.fps)
        pipeline.start(config)
        started = True
        if not args.headless:
            cv2.namedWindow(window, cv2.WINDOW_NORMAL)
        print(f'RGB aktiv: {args.width}x{args.height}, {args.fps} FPS. '
              f'Bilder: {args.output.resolve()}')
        print('Ctrl+C beendet das Programm.')
        count = 0
        report_time = time.monotonic()
        while True:
            frames = pipeline.wait_for_frames(timeout_ms=5000)
            color = frames.get_color_frame()
            if not color:
                continue
            # Kopie bleibt auch nach Freigabe des SDK-Frames gueltig.
            frame_bgr = np.asanyarray(color.get_data()).copy()
            metadata = {
                'camera_serial': serial,
                'frame_id': color.get_frame_number(),
                'camera_timestamp_ms': color.get_timestamp(),
                'timestamp_domain': str(color.get_frame_timestamp_domain()),
                'received_at_unix_ns': time.time_ns(),
            }
            display = process_frame(frame_bgr.copy(), metadata)
            count += 1
            now = time.monotonic()
            if now - report_time >= 2:
                print(f'Empfang/Verarbeitung: {count / (now - report_time):.1f} FPS '
                      f'| Frame {metadata["frame_id"]}', flush=True)
                count = 0
                report_time = now
            if args.headless:
                continue
            cv2.imshow(window, display)
            key = cv2.waitKey(1) & 0xFF
            if key in (ord('q'), ord('Q'), 27):
                break
            if key in (ord('s'), ord('S')):
                args.output.mkdir(parents=True, exist_ok=True)
                stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S_%fZ')
                path = args.output / f'{serial}_{stamp}_{metadata["frame_id"]}.png'
                if not cv2.imwrite(str(path), frame_bgr):
                    raise RuntimeError(f'Bild konnte nicht gespeichert werden: {path}')
                print(f'Gespeichert: {path}')
            if cv2.getWindowProperty(window, cv2.WND_PROP_VISIBLE) < 1:
                break
    except KeyboardInterrupt:
        print('\nBeendet.')
    except (RuntimeError, OSError, cv2.error) as exc:
        print(f'Fehler: {exc}\nAndere Kamera-Programme schliessen. '
              'USB-3-Datenkabel und Zugriffsrechte pruefen. '
              'Bei Profilfehlern Standard 640x480/30 verwenden. '
              'Ohne Desktop: --headless verwenden.', file=sys.stderr)
        return 1
    finally:
        if started:
            pipeline.stop()
        if not args.headless:
            cv2.destroyAllWindows()
    return 0


if __name__ == '__main__':
    sys.exit(main())
