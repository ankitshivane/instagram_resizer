# app.py (validated / corrected)
import os
import math
import threading
import traceback
from PIL import Image, ImageFilter, ImageOps, ImageDraw, ImageFont, ImageTk
import tkinter as tk
from tkinter import filedialog, colorchooser, messagebox, simpledialog
from tkinter import ttk

# Try optional advanced DnD support (not required)
try:
    from tkinterdnd2 import DND_FILES, TkinterDnD
    DND_AVAILABLE = True
except Exception:
    DND_AVAILABLE = False

# ----------------- Configuration / presets -----------------
ASPECT_PRESETS = {
    "1:1": (1, 1),
    "4:5": (4, 5),
    "9:16": (9, 16),
    "16:9": (16, 9),
    "3:2": (3, 2),
    "custom": None,
}

DEFAULT_OUTPUT_DIR = os.path.join(os.getcwd(), "output")

# ----------------- Image utility functions -----------------
def compute_canvas_size(w, h, a, b):
    """Compute minimal integer canvas dimensions with aspect a:b so that canvas_w >= w & canvas_h >= h."""
    if a <= 0 or b <= 0:
        raise ValueError("Aspect components must be > 0")
    k = max(w / a, h / b)
    canvas_w = int(math.ceil(k * a))
    canvas_h = int(math.ceil(k * b))
    return canvas_w, canvas_h

def create_blurred_background(img, canvas_size, blur_radius=25):
    """Create blurred background from image by resizing to cover and center-cropping, then blurring."""
    canvas_w, canvas_h = canvas_size
    w, h = img.size
    scale = max(canvas_w / w, canvas_h / h)
    cover_size = (int(round(w * scale)), int(round(h * scale)))
    cover = img.resize(cover_size, Image.LANCZOS)
    left = (cover.width - canvas_w) // 2
    top = (cover.height - canvas_h) // 2
    cover = cover.crop((left, top, left + canvas_w, top + canvas_h))
    blurred = cover.filter(ImageFilter.GaussianBlur(radius=blur_radius))
    return blurred

def compose_fit_canvas(img, aspect_a, aspect_b, bg_mode, bg_color):
    """Fit mode: keep full image and center it on canvas sized to aspect (no crop)."""
    w, h = img.size
    canvas_w, canvas_h = compute_canvas_size(w, h, aspect_a, aspect_b)
    if bg_mode == "blur":
        bg = create_blurred_background(img, (canvas_w, canvas_h))
    else:
        bg = Image.new("RGB", (canvas_w, canvas_h), bg_color)
    offset_x = (canvas_w - w) // 2
    offset_y = (canvas_h - h) // 2
    bg.paste(img, (offset_x, offset_y))
    return bg

def compose_fill_canvas(img, aspect_a, aspect_b, bg_mode, bg_color):
    """Fill mode: scale to cover canvas and center-crop (may crop parts)."""
    w, h = img.size
    canvas_w, canvas_h = compute_canvas_size(w, h, aspect_a, aspect_b)
    scale = max(canvas_w / w, canvas_h / h)
    new_size = (int(round(w * scale)), int(round(h * scale)))
    resized = img.resize(new_size, Image.LANCZOS)
    left = (resized.width - canvas_w) // 2
    top = (resized.height - canvas_h) // 2
    return resized.crop((left, top, left + canvas_w, top + canvas_h))

def compose_stretch_canvas(img, aspect_a, aspect_b, bg_mode, bg_color):
    """Stretch mode: force image to canvas size (distorts)."""
    w, h = img.size
    canvas_w, canvas_h = compute_canvas_size(w, h, aspect_a, aspect_b)
    return img.resize((canvas_w, canvas_h), Image.BILINEAR)

def ImageColor_getrgb_safe(color_str):
    """Try to interpret a tkinter color string or hex to (r,g,b)."""
    if isinstance(color_str, tuple) and len(color_str) == 3:
        return color_str
    color = color_str
    if isinstance(color, str) and color.startswith("#") and len(color) == 7:
        try:
            r = int(color[1:3], 16)
            g = int(color[3:5], 16)
            b = int(color[5:7], 16)
            return (r, g, b)
        except Exception:
            pass
    # fallback white
    return (255, 255, 255)

def apply_text_watermark(base_img, text, position, opacity, font_size, color):
    """Overlay text watermark. Returns new image (RGB)."""
    if not text:
        return base_img
    base = base_img.convert("RGBA")
    txt_layer = Image.new("RGBA", base.size, (255,255,255,0))
    draw = ImageDraw.Draw(txt_layer)

    # Try to load a truetype font; fall back to default
    try:
        font = ImageFont.truetype("arial.ttf", font_size)
    except Exception:
        font = ImageFont.load_default()

    # Pillow's textbbox may not exist on very old versions; handle gracefully
    try:
        text_bbox = draw.textbbox((0,0), text, font=font)
        text_w = text_bbox[2] - text_bbox[0]
        text_h = text_bbox[3] - text_bbox[1]
    except Exception:
        text_w, text_h = draw.textsize(text, font=font)

    margin = int(max(8, base.width * 0.02))
    if position == "bottom-right":
        x = base.width - text_w - margin
        y = base.height - text_h - margin
    elif position == "bottom-left":
        x = margin
        y = base.height - text_h - margin
    elif position == "top-left":
        x = margin
        y = margin
    elif position == "top-right":
        x = base.width - text_w - margin
        y = margin
    else:  # center
        x = (base.width - text_w) // 2
        y = (base.height - text_h) // 2

    r, g, b = ImageColor_getrgb_safe(color)
    alpha = int(255 * (opacity / 100.0))
    draw.text((x, y), text, font=font, fill=(r, g, b, alpha))
    combined = Image.alpha_composite(base, txt_layer).convert("RGB")
    return combined

def apply_logo_watermark(base_img, logo_img, position, opacity, scale_ratio=0.15, margin_ratio=0.02):
    """Overlay logo (logo_img) onto base_img with given opacity and position.
       scale_ratio = fraction of base image width used for logo width.
    """
    if logo_img is None:
        return base_img
    base = base_img.convert("RGBA")
    logo = logo_img.convert("RGBA")

    target_w = max(1, int(base.width * scale_ratio))
    scale = target_w / logo.width
    new_size = (max(1, int(logo.width * scale)), max(1, int(logo.height * scale)))
    logo = logo.resize(new_size, Image.LANCZOS)

    if opacity < 100:
        alpha = logo.split()[3].point(lambda p: int(p * (opacity / 100.0)))
        logo.putalpha(alpha)

    margin = int(max(8, base.width * margin_ratio))
    if position == "bottom-right":
        x = base.width - logo.width - margin
        y = base.height - logo.height - margin
    elif position == "bottom-left":
        x = margin
        y = base.height - logo.height - margin
    elif position == "top-left":
        x = margin
        y = margin
    elif position == "top-right":
        x = base.width - logo.width - margin
        y = margin
    else:  # center
        x = (base.width - logo.width) // 2
        y = (base.height - logo.height) // 2

    tmp = Image.new("RGBA", base.size, (255,255,255,0))
    tmp.paste(logo, (x, y), logo)
    combined = Image.alpha_composite(base, tmp).convert("RGB")
    return combined

# ----------------- GUI Application -----------------
class ResizerApp:
    def __init__(self, root):
        self.root = root
        root.title("Instagram Photo Resizer (Batch + DnD + Watermark)")
        root.geometry("1000x640")

        # state
        self.files = []
        self.current_image = None
        self.bg_color = "#000000"
        self.bg_mode = tk.StringVar(value="color")
        self.mode = tk.StringVar(value="fit")
        self.aspect_var = tk.StringVar(value="1:1")
        self.custom_aspect_w = tk.StringVar(value="1")
        self.custom_aspect_h = tk.StringVar(value="1")

        # watermark state
        self.wm_type = tk.StringVar(value="none")
        self.wm_text = tk.StringVar(value="")
        self.wm_logo_path = None
        self.wm_position = tk.StringVar(value="bottom-right")
        self.wm_opacity = tk.IntVar(value=80)
        self.wm_font_size = tk.IntVar(value=32)
        self.output_dir = tk.StringVar(value=DEFAULT_OUTPUT_DIR)

        # Top controls
        top_frame = tk.Frame(root, padx=8, pady=8)
        top_frame.pack(side=tk.TOP, fill=tk.X)

        btn_load = tk.Button(top_frame, text="Load Image(s)", command=self.load_images)
        btn_load.pack(side=tk.LEFT, padx=4)

        btn_folder = tk.Button(top_frame, text="Load Folder", command=self.load_folder)
        btn_folder.pack(side=tk.LEFT, padx=4)

        btn_clear = tk.Button(top_frame, text="Clear List", command=self.clear_list)
        btn_clear.pack(side=tk.LEFT, padx=4)

        btn_open_out = tk.Button(top_frame, text="Open Output Folder", command=self.open_output_dir)
        btn_open_out.pack(side=tk.LEFT, padx=4)

        tk.Label(top_frame, text="  Output:").pack(side=tk.LEFT)
        tk.Entry(top_frame, textvariable=self.output_dir, width=40).pack(side=tk.LEFT, padx=4)
        tk.Button(top_frame, text="Browse", command=self.choose_output_dir).pack(side=tk.LEFT)

        # Left: controls panel
        # control_frame = tk.Frame(root, width=320, padx=10, pady=6)
        # control_frame.pack(side=tk.LEFT, fill=tk.Y)
        # Left: controls panel (scrollable to ensure Save buttons always visible)
        left_container = tk.Frame(root, width=340)
        left_container.pack(side=tk.LEFT, fill=tk.Y)

        canvas = tk.Canvas(left_container, borderwidth=0, width=340)
        scrollbar = tk.Scrollbar(left_container, orient="vertical", command=canvas.yview)
        control_frame = tk.Frame(canvas, padx=10, pady=6)

        control_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(
                scrollregion=canvas.bbox("all")
            )
        )
        canvas.create_window((0, 0), window=control_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # File list
        tk.Label(control_frame, text="Files to process:").pack(anchor="w")
        self.file_listbox = tk.Listbox(control_frame, width=48, height=10, selectmode=tk.SINGLE)
        self.file_listbox.pack()
        self.file_listbox.bind("<<ListboxSelect>>", self.on_select_listbox)

        # Aspect ratio
        tk.Label(control_frame, text="Target Aspect Ratio").pack(anchor="w", pady=(8,0))
        aspect_menu = tk.OptionMenu(control_frame, self.aspect_var, *ASPECT_PRESETS.keys(), command=self._on_aspect_change)
        aspect_menu.config(width=14)
        aspect_menu.pack(pady=4)

        custom_frame = tk.Frame(control_frame)
        tk.Label(custom_frame, text="W:").pack(side=tk.LEFT)
        tk.Entry(custom_frame, textvariable=self.custom_aspect_w, width=4).pack(side=tk.LEFT, padx=2)
        tk.Label(custom_frame, text="H:").pack(side=tk.LEFT)
        tk.Entry(custom_frame, textvariable=self.custom_aspect_h, width=4).pack(side=tk.LEFT, padx=2)
        custom_frame.pack(anchor="w")

        # Resize type
        tk.Label(control_frame, text="Resize Type").pack(anchor="w", pady=(8,0))
        tk.Radiobutton(control_frame, text="Fit (no crop)", variable=self.mode, value="fit").pack(anchor="w")
        tk.Radiobutton(control_frame, text="Fill (crop)", variable=self.mode, value="fill").pack(anchor="w")
        tk.Radiobutton(control_frame, text="Stretch (distort)", variable=self.mode, value="stretch").pack(anchor="w")

        # Background options
        tk.Label(control_frame, text="Background").pack(anchor="w", pady=(8,0))
        tk.Radiobutton(control_frame, text="Solid Color", variable=self.bg_mode, value="color").pack(anchor="w")
        tk.Radiobutton(control_frame, text="Blurred Background", variable=self.bg_mode, value="blur").pack(anchor="w")
        tk.Button(control_frame, text="Choose Color", command=self.choose_color).pack(pady=6)

        # Watermark section
        tk.Label(control_frame, text="Watermark (optional)").pack(anchor="w", pady=(8,0))
        tk.Radiobutton(control_frame, text="None", variable=self.wm_type, value="none", command=self._on_wm_change).pack(anchor="w")
        tk.Radiobutton(control_frame, text="Text", variable=self.wm_type, value="text", command=self._on_wm_change).pack(anchor="w")
        tk.Radiobutton(control_frame, text="Logo", variable=self.wm_type, value="logo", command=self._on_wm_change).pack(anchor="w")

        wm_text_frame = tk.Frame(control_frame)
        tk.Label(wm_text_frame, text="Text:").pack(side=tk.LEFT)
        tk.Entry(wm_text_frame, textvariable=self.wm_text, width=18).pack(side=tk.LEFT)
        wm_text_frame.pack(pady=4)

        wm_logo_frame = tk.Frame(control_frame)
        tk.Button(wm_logo_frame, text="Select Logo", command=self.choose_logo).pack(side=tk.LEFT)
        self.wm_logo_label = tk.Label(wm_logo_frame, text="No file")
        self.wm_logo_label.pack(side=tk.LEFT, padx=6)
        wm_logo_frame.pack(pady=2)

        pos_frame = tk.Frame(control_frame)
        tk.Label(pos_frame, text="Position:").pack(side=tk.LEFT)
        pos_menu = tk.OptionMenu(pos_frame, self.wm_position, "bottom-right", "bottom-left", "top-left", "top-right", "center")
        pos_menu.config(width=10)
        pos_menu.pack(side=tk.LEFT)
        pos_frame.pack(pady=4)

        tk.Label(control_frame, text="Opacity (%)").pack(anchor="w")
        tk.Scale(control_frame, from_=10, to=100, orient=tk.HORIZONTAL, variable=self.wm_opacity).pack(fill=tk.X)

        tk.Label(control_frame, text="Font size (text wm)").pack(anchor="w")
        tk.Scale(control_frame, from_=12, to=96, orient=tk.HORIZONTAL, variable=self.wm_font_size).pack(fill=tk.X)

        # Save button (batch)
        save_btn = tk.Button(
            control_frame,
            text="Resize & Save (Batch)",
            bg="#4CAF50",
            fg="white",
            width=24,
            height=2,
            font=("Segoe UI", 10, "bold"),
            command=self.start_batch_process
        )
        save_btn.pack(pady=12)

        # Quick single-image save button
        single_btn = tk.Button(control_frame, text="Resize & Save (Single)", bg="#1976D2", fg="white", width=24, command=self.save_single_selected)
        single_btn.pack(pady=6)

        # Right: preview and DnD area
        right_frame = tk.Frame(root, padx=10, pady=6)
        right_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        instructions = ("Drag & drop image files or folders onto the preview area (if supported),\n"
                        "or use 'Load Image(s)' / 'Load Folder'.\n\n"
                        "Select files from the list to preview them.\n"
                        "Settings apply to all files in the list when Batch processing.")
        tk.Label(right_frame, text=instructions, justify="left").pack(anchor="w")

        self.preview_label = tk.Label(right_frame, text="Drop images here (or load) \n\n[Drag & Drop may need tkinterdnd2 installed]",
                                      bd=1, relief=tk.SUNKEN, width=60, height=20)
        self.preview_label.pack(fill=tk.BOTH, expand=True)

        # Bind DnD if available (and if using TkinterDnD root)
        if DND_AVAILABLE:
            try:
                self.preview_label.drop_target_register(DND_FILES)
                self.preview_label.dnd_bind('<<Drop>>', self._on_drop)
            except Exception:
                # ignore DnD binding failures
                pass

        # Progress & logs
        self.progress = ttk.Progressbar(right_frame, orient="horizontal", length=400, mode="determinate")
        self.progress.pack(pady=6)
        self.log_text = tk.Text(right_frame, height=8)
        self.log_text.pack(fill=tk.X, pady=4)

    # ---------- File operations ----------
    def load_images(self):
        paths = filedialog.askopenfilenames(title="Select images", filetypes=[("Images","*.png;*.jpg;*.jpeg;*.bmp;*.webp")])
        if paths:
            self.add_files(paths)

    def load_folder(self):
        folder = filedialog.askdirectory(title="Select folder containing images")
        if not folder:
            return
        exts = (".png", ".jpg", ".jpeg", ".bmp", ".webp")
        found = []
        for root_dir, _, files in os.walk(folder):
            for f in files:
                if f.lower().endswith(exts):
                    found.append(os.path.join(root_dir, f))
        if found:
            self.add_files(found)
        else:
            messagebox.showinfo("No images", "No image files found in that folder.")

    def add_files(self, paths):
        added = 0
        for p in paths:
            if p not in self.files and os.path.isfile(p):
                self.files.append(p)
                self.file_listbox.insert(tk.END, os.path.basename(p))
                added += 1
        self.log(f"Added {added} files. Total: {len(self.files)}")

    def clear_list(self):
        self.files.clear()
        self.file_listbox.delete(0, tk.END)
        self.preview_label.config(image="", text="Drop images here (or load)")
        self.log("Cleared file list.")

    def choose_output_dir(self):
        d = filedialog.askdirectory(title="Choose output directory")
        if d:
            self.output_dir.set(d)

    def open_output_dir(self):
        d = self.output_dir.get()
        if not os.path.exists(d):
            messagebox.showwarning("Not found", f"Output directory does not exist: {d}")
            return
        try:
            if os.name == "nt":
                os.startfile(d)
            elif os.name == "posix":
                import subprocess
                subprocess.Popen(["xdg-open", d])
            else:
                messagebox.showinfo("Open folder", f"Open folder: {d}")
        except Exception as e:
            messagebox.showerror("Error", f"Could not open folder: {e}")

    def choose_color(self):
        color = colorchooser.askcolor(title="Choose background color", color=self.bg_color)
        if color and color[1]:
            self.bg_color = color[1]
            self.log(f"Background color set to {self.bg_color}")

    def choose_logo(self):
        p = filedialog.askopenfilename(title="Select logo image", filetypes=[("Images","*.png;*.jpg;*.jpeg;*.bmp;*.webp")])
        if p:
            self.wm_logo_path = p
            self.wm_logo_label.config(text=os.path.basename(p))
            self.log(f"Selected logo: {p}")

    # ---------- DnD handler ----------
    def _on_drop(self, event):
        data = event.data
        paths = self._parse_dnd_filenames(data)
        self.add_files(paths)

    def _parse_dnd_filenames(self, raw):
        parts = []
        cur = ""
        in_brace = False
        for ch in raw:
            if ch == "{":
                in_brace = True
                cur = ""
            elif ch == "}":
                in_brace = False
                parts.append(cur)
                cur = ""
            elif ch == " " and not in_brace:
                if cur:
                    parts.append(cur)
                    cur = ""
            else:
                cur += ch
        if cur:
            parts.append(cur)
        return [p for p in parts if os.path.isfile(p)]

    # ---------- Listbox select ----------
    def on_select_listbox(self, event):
        sel = event.widget.curselection()
        if not sel:
            return
        idx = sel[0]
        path = self.files[idx]
        try:
            img = Image.open(path).convert("RGB")
            self.current_image = img
            self.display_preview(img)
        except Exception as e:
            self.log(f"Failed to open {path}: {e}")

    def display_preview(self, pil_img):
        max_w, max_h = 700, 460
        preview = pil_img.copy()
        preview.thumbnail((max_w, max_h), Image.LANCZOS)
        try:
            self._preview_tk = ImageTk.PhotoImage(preview)
            self.preview_label.config(image=self._preview_tk, text="")
        except Exception:
            self.preview_label.config(text="Preview not available")

    def _on_aspect_change(self, *_):
        pass

    def _on_wm_change(self, *_):
        pass

    def log(self, msg):
        self.log_text.insert(tk.END, msg + "\n")
        self.log_text.see(tk.END)

    # ---------- Batch processing ----------
    def start_batch_process(self):
        if not self.files:
            messagebox.showwarning("No files", "Please add one or more images first.")
            return
        out_dir = self.output_dir.get() or DEFAULT_OUTPUT_DIR
        os.makedirs(out_dir, exist_ok=True)

        proceed = messagebox.askyesno("Start batch", f"Process {len(self.files)} files and save to:\n{out_dir}\n\nProceed?")
        if not proceed:
            return

        thread = threading.Thread(target=self._batch_process_thread, args=(out_dir,))
        thread.start()

    def _batch_process_thread(self, out_dir):
        total = len(self.files)
        self.progress["maximum"] = total
        self.progress["value"] = 0
        success = 0
        for i, path in enumerate(list(self.files), start=1):
            try:
                self.log(f"[{i}/{total}] Processing: {path}")
                img = Image.open(path).convert("RGB")
                a, b = self.get_aspect()
                mode = self.mode.get()
                bg_mode = self.bg_mode.get()
                bg_color = self.bg_color

                if mode == "fit":
                    out_img = compose_fit_canvas(img, a, b, bg_mode, bg_color)
                elif mode == "fill":
                    out_img = compose_fill_canvas(img, a, b, bg_mode, bg_color)
                elif mode == "stretch":
                    out_img = compose_stretch_canvas(img, a, b, bg_mode, bg_color)
                else:
                    raise RuntimeError("Unknown mode")

                if self.wm_type.get() == "text" and self.wm_text.get().strip():
                    out_img = apply_text_watermark(out_img, self.wm_text.get().strip(),
                                                   self.wm_position.get(), self.wm_opacity.get(), self.wm_font_size.get(), "#ffffff")
                elif self.wm_type.get() == "logo" and self.wm_logo_path and os.path.isfile(self.wm_logo_path):
                    logo = Image.open(self.wm_logo_path).convert("RGBA")
                    out_img = apply_logo_watermark(out_img, logo, self.wm_position.get(), self.wm_opacity.get())

                fname = os.path.splitext(os.path.basename(path))[0]
                out_name = f"{fname}_resized.jpg"
                out_path = os.path.join(out_dir, out_name)
                out_img.save(out_path, "JPEG", quality=95, optimize=True)
                self.log(f"Saved → {out_path}")
                success += 1
            except Exception as e:
                self.log(f"Error processing {path}: {e}\n{traceback.format_exc()}")
            finally:
                self.progress["value"] = i

        messagebox.showinfo("Batch complete", f"Processed {success}/{total} files.\nSaved to: {out_dir}")
        self.log(f"Batch finished: {success}/{total}")
        self.progress["value"] = 0

    def save_single_selected(self):
        sel = self.file_listbox.curselection()
        if not sel:
            messagebox.showwarning("No selection", "Select a file in the list for single save.")
            return
        idx = sel[0]
        path = self.files[idx]
        try:
            img = Image.open(path).convert("RGB")
            a, b = self.get_aspect()
            mode = self.mode.get()
            bg_mode = self.bg_mode.get()
            bg_color = self.bg_color

            if mode == "fit":
                out_img = compose_fit_canvas(img, a, b, bg_mode, bg_color)
            elif mode == "fill":
                out_img = compose_fill_canvas(img, a, b, bg_mode, bg_color)
            elif mode == "stretch":
                out_img = compose_stretch_canvas(img, a, b, bg_mode, bg_color)
            else:
                raise RuntimeError("Unknown mode")

            if self.wm_type.get() == "text" and self.wm_text.get().strip():
                out_img = apply_text_watermark(out_img, self.wm_text.get().strip(),
                                               self.wm_position.get(), self.wm_opacity.get(), self.wm_font_size.get(), "#ffffff")
            elif self.wm_type.get() == "logo" and self.wm_logo_path and os.path.isfile(self.wm_logo_path):
                logo = Image.open(self.wm_logo_path).convert("RGBA")
                out_img = apply_logo_watermark(out_img, logo, self.wm_position.get(), self.wm_opacity.get())

            # ask where to save single file
            save_path = filedialog.asksaveasfilename(defaultextension=".jpg",
                                                     filetypes=[("JPEG", "*.jpg"), ("PNG", "*.png")],
                                                     initialfile=os.path.splitext(os.path.basename(path))[0] + "_resized")
            if not save_path:
                return
            ext = os.path.splitext(save_path)[1].lower()
            if ext in (".jpg", ".jpeg"):
                out_img.save(save_path, "JPEG", quality=95, optimize=True)
            else:
                out_img.save(save_path)
            messagebox.showinfo("Saved", f"Saved: {save_path}")
            self.log(f"Single saved → {save_path}")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to process/save: {e}\n{traceback.format_exc()}")

    def get_aspect(self):
        key = self.aspect_var.get()
        if key != "custom":
            val = ASPECT_PRESETS.get(key)
            return val if val is not None else (1,1)
        try:
            a = float(self.custom_aspect_w.get())
            b = float(self.custom_aspect_h.get())
            if a <= 0 or b <= 0:
                raise ValueError
            return (a, b)
        except Exception:
            messagebox.showwarning("Invalid aspect", "Please enter valid positive numbers for custom W and H.")
            return (1,1)

# ----------------- Launch -----------------
def main():
    if DND_AVAILABLE:
        root = TkinterDnD.Tk()
    else:
        root = tk.Tk()
    app = ResizerApp(root)
    root.mainloop()

if __name__ == "__main__":
    main()
