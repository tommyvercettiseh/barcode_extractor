import shutil
import threading
from pathlib import Path
import tkinter as tk
from tkinter import ttk, messagebox

import fitz
import numpy as np
from PIL import Image, ImageTk
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


def extract_barcode_from_pdf(pdf_path, preview_callback=None, log_callback=None):
    doc = fitz.open(pdf_path)

    try:
        for page_number in range(len(doc)):
            page = doc.load_page(page_number)
            image = render_pdf_page(page)

            if preview_callback:
                preview_callback(image, page_number + 1)

            if log_callback:
                log_callback(f"Pagina {page_number + 1}/{len(doc)} scannen...")

            results = zxingcpp.read_barcodes(image)

            for result in results:
                value = result.text.strip()
                fmt = str(result.format)

                if value:
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
        self.root.geometry("820x620")
        self.root.minsize(760, 560)

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

        ttk.Button(controls, text="Open input", command=lambda: self.open_folder(INPUT_DIR)).pack(side="left", padx=(8, 0))
        ttk.Button(controls, text="Open output", command=lambda: self.open_folder(OUTPUT_DIR)).pack(side="left", padx=(8, 0))

        self.progress = ttk.Progressbar(container, mode="determinate")
        self.progress.pack(fill="x", pady=(0, 10))

        self.status_var = tk.StringVar(value="Klaar")
        ttk.Label(container, textvariable=self.status_var, font=("Segoe UI", 10, "bold")).pack(anchor="w", pady=(0, 10))

        body = ttk.Panedwindow(container, orient="horizontal")
        body.pack(fill="both", expand=True)

        preview_frame = ttk.LabelFrame(body, text="Preview", padding=8)
        log_frame = ttk.LabelFrame(body, text="Log", padding=8)
        body.add(preview_frame, weight=1)
        body.add(log_frame, weight=1)

        self.preview_label = ttk.Label(preview_frame, text="Nog geen pagina geladen", anchor="center")
        self.preview_label.pack(fill="both", expand=True)
        self.preview_photo = None

        self.log_text = tk.Text(log_frame, wrap="word", height=20, state="disabled", font=("Consolas", 9))
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

    def update_preview(self, image, page_number):
        def update():
            preview = image.copy()
            preview.thumbnail((360, 360))
            self.preview_photo = ImageTk.PhotoImage(preview)
            self.preview_label.configure(image=self.preview_photo, text=f"Pagina {page_number}", compound="top")

        self.root.after(0, update)

    def start_scan(self):
        if self.running:
            return

        pdf_files = sorted(INPUT_DIR.glob("*.pdf"))

        if not pdf_files:
            messagebox.showinfo("Barcode Extractor", f"Geen PDF-bestanden gevonden in:\n{INPUT_DIR}")
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
                        safe_barcode = "".join(c for c in barcode if c.isalnum() or c in ("-", "_"))
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

                self.root.after(0, lambda v=index: self.progress.configure(value=v))

            self.set_status(f"Klaar. {found_count}/{len(pdf_files)} bestand(en) verwerkt.")
            self.log("")
            self.log(f"KLAAR: {found_count} barcode(s) gevonden.")

        finally:
            self.running = False
            self.root.after(0, lambda: self.scan_button.configure(state="normal"))


if __name__ == "__main__":
    root = tk.Tk()
    app = BarcodeExtractorApp(root)
    root.mainloop()
