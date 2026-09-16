import shutil
import threading
from pathlib import Path
import tkinter as tk
from tkinter import ttk, messagebox

import fitz
import numpy as np
from PIL import Image, ImageTk, ImageDraw
import zxingcpp


BASE_DIR = Path(__file__).resolve().parent
INPUT_DIR = BASE_DIR / "input"
OUTPUT_DIR = BASE_DIR / "output"

INPUT_DIR.mkdir(exist_ok=True)
OUTPUT_DIR.mkdir(exist_ok=True)


def render_pdf_page(page, dpi=300):
    zoom = dpi / 72
    pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom), alpha=False)
    arr = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, pix.n)

    if pix.n == 4:
        arr = arr[:, :, :3]

    return Image.fromarray(arr)


def barcode_points(result):
    """Haal de vier hoekpunten uit een zxing-cpp resultaat."""
    try:
        pos = result.position
        points = []

        for name in ("top_left", "top_right", "bottom_right", "bottom_left"):
            point = getattr(pos, name, None)
            if point is None:
                return None

            x = getattr(point, "x", None)
            y = getattr(point, "y", None)

            if x is None or y is None:
                try:
                    x, y = point
                except Exception:
                    return None

            points.append((int(x), int(y)))

        return points
    except Exception:
        return None


def extract_barcode_from_pdf(pdf_path, preview_callback=None, log_callback=None):
    doc = fitz.open(pdf_path)

    try:
        for page_number in range(len(doc)):
            page = doc.load_page(page_number)
            image = render_pdf_page(page)

            if preview_callback:
                preview_callback(image, page_number + 1, None)

            if log_callback:
                log_callback(f"Pagina {page_number + 1}/{len(doc)} scannen...")

            results = zxingcpp.read_barcodes(image)

            for result in results:
                value = result.text.strip()
                fmt = str(result.format)

                if value:
                    points = barcode_points(result)

                    if preview_callback:
                        preview_callback(image, page_number + 1, points)

                    if log_callback:
                        log_callback(f"Barcode gevonden: {value} ({fmt})")

                    return value, page_number + 1, fmt

        return None, None, None
    finally:
        doc.close()


class BarcodeExtractorApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Barcode Extractor")
        self.root.geometry("860x640")
        self.root.minsize(780, 580)

        self.running = False

        style = ttk.Style()
        try:
            style.theme_use("vista")
        except tk.TclError:
            pass

        container = ttk.Frame(root, padding=16)
        container.pack(fill="both", expand=True)

        title = ttk.Label(container, text="Barcode Extractor", font=("Segoe UI", 18, "bold"))
        title.pack(anchor="w")

        subtitle = ttk.Label(
            container,
            text="Plaats PDF-bestanden in input. De gevonden barcode wordt de bestandsnaam in output.",
        )
        subtitle.pack(anchor="w", pady=(2, 14))

        folders = ttk.Frame(container)
        folders.pack(fill="x", pady=(0, 12))

        ttk.Label(folders, text=f"Input:  {INPUT_DIR}").pack(anchor="w")
        ttk.Label(folders, text=f"Output: {OUTPUT_DIR}").pack(anchor="w")

        controls = ttk.Frame(container)
        controls.pack(fill="x", pady=(0, 12))

        self.scan_button = ttk.Button(controls, text="Scan input map", command=self.start_scan)
        self.scan_button.pack(side="left")

        ttk.Button(controls, text="Open input", command=lambda: self.open_folder(INPUT_DIR)).pack(
            side="left", padx=(8, 0)
        )
        ttk.Button(controls, text="Open output", command=lambda: self.open_folder(OUTPUT_DIR)).pack(
            side="left", padx=(8, 0)
        )

        self.highlight_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(
            controls,
            text="Markeer barcode",
            variable=self.highlight_var,
            command=self.refresh_current_preview,
        ).pack(side="left", padx=(18, 0))

        self.progress = ttk.Progressbar(container, mode="determinate")
        self.progress.pack(fill="x", pady=(0, 10))

        self.status_var = tk.StringVar(value="Klaar")
        ttk.Label(container, textvariable=self.status_var, font=("Segoe UI", 10, "bold")).pack(
            anchor="w", pady=(0, 10)
        )

        body = ttk.Panedwindow(container, orient="horizontal")
        body.pack(fill="both", expand=True)

        preview_frame = ttk.LabelFrame(body, text="Preview", padding=8)
        log_frame = ttk.LabelFrame(body, text="Log", padding=8)
        body.add(preview_frame, weight=1)
        body.add(log_frame, weight=1)

        self.preview_label = ttk.Label(
            preview_frame,
            text="Nog geen pagina geladen",
            anchor="center",
        )
        self.preview_label.pack(fill="both", expand=True)
        self.preview_photo = None
        self.current_preview_image = None
        self.current_preview_page = None
        self.current_barcode_points = None

        self.log_text = tk.Text(
            log_frame,
            wrap="word",
            height=20,
            state="disabled",
            font=("Consolas", 9),
        )
        self.log_text.pack(fill="both", expand=True)

    def open_folder(self, path):
        import os
        os.startfile(path)

    def log(self, text):
        def update():
            self.log_text.configure(state="normal")
            self.log_text.insert("end", text + "\n")
            self.log_text.see("end")
            self.log_text.configure(state="disabled")

        self.root.after(0, update)

    def set_status(self, text):
        self.root.after(0, lambda: self.status_var.set(text))

    def refresh_current_preview(self):
        if self.current_preview_image is not None:
            self.draw_preview(
                self.current_preview_image,
                self.current_preview_page,
                self.current_barcode_points,
            )

    def draw_preview(self, image, page_number, points=None):
        preview = image.copy()

        if points and self.highlight_var.get():
            draw = ImageDraw.Draw(preview)

            xs = [p[0] for p in points]
            ys = [p[1] for p in points]

            pad = max(12, int(min(preview.size) * 0.012))
            left = max(0, min(xs) - pad)
            top = max(0, min(ys) - pad)
            right = min(preview.width - 1, max(xs) + pad)
            bottom = min(preview.height - 1, max(ys) + pad)

            line_width = max(8, int(min(preview.size) * 0.006))

            # Felle groene rand rondom de gevonden barcode.
            draw.rectangle(
                (left, top, right, bottom),
                outline="#39FF14",
                width=line_width,
            )

        preview.thumbnail((390, 390))
        self.preview_photo = ImageTk.PhotoImage(preview)

        label = f"Pagina {page_number}"
        if points:
            label += "  •  barcode gevonden"

        self.preview_label.configure(
            image=self.preview_photo,
            text=label,
            compound="top",
        )

    def update_preview(self, image, page_number, points=None):
        image_copy = image.copy()

        def update():
            self.current_preview_image = image_copy
            self.current_preview_page = page_number
            self.current_barcode_points = points
            self.draw_preview(image_copy, page_number, points)

        self.root.after(0, update)

    def start_scan(self):
        if self.running:
            return

        pdf_files = sorted(INPUT_DIR.glob("*.pdf"))

        if not pdf_files:
            messagebox.showinfo(
                "Barcode Extractor",
                f"Geen PDF-bestanden gevonden in:\n{INPUT_DIR}",
            )
            return

        self.running = True
        self.scan_button.configure(state="disabled")
        self.progress["maximum"] = len(pdf_files)
        self.progress["value"] = 0

        threading.Thread(target=self.scan_files, args=(pdf_files,), daemon=True).start()

    def scan_files(self, pdf_files):
        found_count = 0

        try:
            for index, pdf_path in enumerate(pdf_files, start=1):
                self.set_status(f"Scannen: {pdf_path.name}")
                self.log("")
                self.log(f"[{index}/{len(pdf_files)}] {pdf_path.name}")

                try:
                    barcode, page_number, fmt = extract_barcode_from_pdf(
                        pdf_path,
                        preview_callback=self.update_preview,
                        log_callback=self.log,
                    )

                    if barcode:
                        safe_barcode = "".join(
                            c for c in barcode if c.isalnum() or c in ("-", "_")
                        )

                        if not safe_barcode:
                            self.log("Barcode bevat geen bruikbare tekens.")
                            continue

                        output_path = OUTPUT_DIR / f"{safe_barcode}.pdf"
                        shutil.copy2(pdf_path, output_path)

                        found_count += 1
                        self.log(f"Opgeslagen als: {output_path.name}")
                        self.set_status(f"Gevonden: {barcode}")
                    else:
                        self.log("Geen barcode gevonden.")
                        self.set_status(f"Geen barcode: {pdf_path.name}")

                except Exception as exc:
                    self.log(f"FOUT: {exc}")

                self.root.after(
                    0,
                    lambda v=index: self.progress.configure(value=v),
                )

            self.set_status(
                f"Klaar. {found_count}/{len(pdf_files)} bestand(en) verwerkt."
            )
            self.log("")
            self.log(f"KLAAR: {found_count} barcode(s) gevonden.")

        finally:
            self.running = False
            self.root.after(
                0,
                lambda: self.scan_button.configure(state="normal"),
            )


if __name__ == "__main__":
    root = tk.Tk()
    app = BarcodeExtractorApp(root)
    root.mainloop()
