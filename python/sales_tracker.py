import customtkinter as ctk
from tkinter import messagebox, filedialog, Canvas, PhotoImage
import sys
import json
import csv
import os
import random
import numpy as np
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont, ImageTk

def resource_path(relative):
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, relative)
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), relative)

def app_data_path():
    return os.path.join(os.path.expanduser("~"), "Documents")

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("dark-blue")

BLACK = "#0a0a0a"
RED = "#ff0040"
DARK_RED = "#8b0000"
NEON_RED = "#ff1a1a"
CARD_BG = "#1a1a1a"
TEXT_COLOR = "#ffffff"
GRAY = "#2a2a2a"
HOVER_RED = "#cc0033"
INPUT_BG = "#111111"
BORDER = "#333333"
LABEL_GRAY = "#888888"
GOLD = "#ffd700"
GOLD_DARK = "#b8960f"
JAR_CAPACITY = 1000.0
COIN_COLORS = ["#ffd700", "#ffec80", "#daa520", "#ffdf00"]


class CashJar(ctk.CTkFrame):
    def __init__(self, parent, **kwargs):
        super().__init__(parent, fg_color=CARD_BG, corner_radius=12, border_width=1, border_color="#333333", **kwargs)
        self.jar_w = 160
        self.jar_h = 200
        self.canvas = Canvas(self, bg=CARD_BG, highlightthickness=0, width=self.jar_w, height=self.jar_h)
        self.canvas.pack(padx=10, pady=8)

        self.body_x1 = 35
        self.body_x2 = 125
        self.body_y1 = 50
        self.body_y2 = 175
        self.neck_x1 = 55
        self.neck_x2 = 105
        self.neck_y1 = 25
        self.neck_y2 = 50
        self.rim_y = 22

        self.current_amount = 0.0
        self.fill_level = 0.0
        self.target_fill = 0.0
        self.coins = []
        self.sparks = []
        self.dumping = False
        self.dump_alpha = 1.0
        self.animating = False
        self._loop_running = False

        self.amount_label = ctk.CTkLabel(self, text="₱0 / ₱1,000", font=("Consolas", 11, "bold"), text_color=GOLD)
        self.amount_label.pack()

        self.draw_jar()
        self.refresh()

    def draw_jar(self):
        c = self.canvas
        c.delete("jar")
        kw = {"tags": "jar"}
        c.create_rectangle(self.body_x1, self.body_y1, self.body_x2, self.body_y2, outline="#555555", width=2, fill="#0d0d0d", **kw)
        c.create_rectangle(self.neck_x1, self.neck_y1, self.neck_x2, self.neck_y2, outline="#555555", width=2, fill="#0d0d0d", **kw)
        c.create_arc(self.neck_x1, self.rim_y - 10, self.neck_x2, self.neck_y1 + 10, start=0, extent=180, style="arc", outline="#666666", width=2, **kw)
        c.create_line(self.neck_x1 - 8, self.rim_y, self.neck_x2 + 8, self.rim_y, fill="#666666", width=3, **kw)
        for i in range(3):
            x = self.body_x1 + 15 + i * 25
            c.create_line(x, self.body_y1 + 8, x, self.body_y2 - 8, fill="#1a1a1a", width=1, **kw)

    def refresh(self):
        self.draw_fill()
        self.update_coins()
        self.update_sparks()
        if self.coins or self.sparks or (abs(self.fill_level - self.target_fill) > 0.5) or self.dumping:
            self._loop_running = True
            self.after(33, self.refresh)
        else:
            self._loop_running = False

    def draw_fill(self):
        self.canvas.delete("fill")
        y2 = self.body_y2 - 2
        x1 = self.body_x1 + 2
        x2 = self.body_x2 - 2
        y1 = y2 - self.fill_level
        if self.fill_level > 0:
            if abs(self.fill_level - self.target_fill) > 0.5:
                self.fill_level += (self.target_fill - self.fill_level) * 0.15
            else:
                self.fill_level = self.target_fill
            y1 = y2 - self.fill_level
            if y1 < self.body_y1 + 2:
                y1 = self.body_y1 + 2
            shade = int(20 + (y1 / (y2 - self.body_y1)) * 25)
            col = f"#{min(200, 60 + shade):02x}{0:02x}{min(40, shade):02x}"
            self.canvas.create_rectangle(x1, y1, x2, y2, fill=col, outline="", tags="fill")
            self.canvas.create_line(x1 + 8, y1 + 5, x1 + 8, y2 - 5, fill="#ff6688", width=1, tags="fill")
        self.amount_label.configure(text=f"₱{int(self.current_amount)} / ₱{int(JAR_CAPACITY)}")

    def add_to_jar(self, amount):
        self.current_amount = min(self.current_amount + amount, JAR_CAPACITY)
        self.target_fill = (self.current_amount / JAR_CAPACITY) * (self.body_y2 - self.body_y1 - 4)
        self.spawn_coin(amount)
        if not self._loop_running:
            self.refresh()
        if self.current_amount >= JAR_CAPACITY and not self.dumping:
            self.after(800, self.start_dump)

    def spawn_coin(self, amount):
        num_coins = max(1, min(5, int(amount / 10) + 1))
        center_x = (self.neck_x1 + self.neck_x2) // 2
        for _ in range(num_coins):
            coin = {
                "x": center_x + random.randint(-12, 12),
                "y": self.rim_y + 5,
                "vy": 0,
                "vx": random.uniform(-1.5, 1.5),
                "r": 5 + (amount / JAR_CAPACITY) * 3,
                "color": random.choice(COIN_COLORS),
                "target_y": self.body_y2 - self.fill_level - 5,
            }
            self.coins.append(coin)
        self.animating = True

    def update_coins(self):
        to_remove = []
        for coin in self.coins:
            self.canvas.delete(f"coin_{id(coin)}")
            coin["vy"] += 0.8
            coin["y"] += coin["vy"]
            coin["x"] += coin["vx"]
            if coin["y"] >= coin["target_y"]:
                coin["y"] = coin["target_y"]
                self.spawn_sparks(coin["x"], coin["y"])
                to_remove.append(coin)
                continue
            r = coin["r"]
            self.canvas.create_oval(coin["x"] - r, coin["y"] - r, coin["x"] + r, coin["y"] + r, fill=coin["color"], outline=GOLD_DARK, width=1, tags=f"coin_{id(coin)}")
            self.canvas.create_line(coin["x"] - r * 0.5, coin["y"] - r * 0.3, coin["x"] + r * 0.3, coin["y"] - r * 0.6, fill="#fff8dc", width=1, tags=f"coin_{id(coin)}")
        for coin in to_remove:
            self.coins.remove(coin)

    def spawn_sparks(self, x, y):
        for i in range(4):
            self.sparks.append({
                "x": x, "y": y,
                "vx": (i - 1.5) * 2,
                "vy": -2 - i,
                "life": 8,
                "color": GOLD if i % 2 == 0 else NEON_RED,
            })

    def update_sparks(self):
        to_remove = []
        for s in self.sparks:
            self.canvas.delete(f"spark_{id(s)}")
            s["life"] -= 1
            if s["life"] <= 0:
                to_remove.append(s)
                continue
            s["x"] += s["vx"]
            s["y"] += s["vy"]
            s["vy"] += 0.5
            r = max(1, s["life"] // 3)
            self.canvas.create_oval(s["x"] - r, s["y"] - r, s["x"] + r, s["y"] + r, fill=s["color"], outline="", tags=f"spark_{id(s)}")
        for s in to_remove:
            self.sparks.remove(s)

    def start_dump(self):
        self.dumping = True
        for i in range(20):
            self.after(i * 50, lambda idx=i: self.dump_frame(idx))

    def dump_frame(self, idx):
        self.canvas.delete("dump_coin")
        cx = (self.body_x1 + self.body_x2) / 2
        for i in range(8):
            angle = (i / 8) * 6.28 + idx * 0.3
            dist = 10 + idx * 4
            x = cx + dist * (0.5 + 0.5 * (angle / 6.28))
            y = self.body_y1 + 20 - idx * 3
            r = 4
            self.canvas.create_oval(x - r, y - r, x + r, y + r, fill=GOLD, outline=GOLD_DARK, tags="dump_coin")

        if idx < 15:
            flash_color = f"#{min(255, idx * 17):02x}{max(0, 255 - idx * 17):02x}00"
            self.canvas.create_rectangle(self.body_x1, self.body_y1, self.body_x2, self.body_y2, fill=flash_color, outline="", tags="dump_coin")
        if idx == 19:
            self.canvas.delete("dump_coin")
            self.current_amount = 0.0
            self.fill_level = 0.0
            self.target_fill = 0.0
            self.dumping = False
            self.canvas.delete("fill")
            self.amount_label.configure(text="CASHOUT! 🎉", text_color=NEON_RED)
            self.after(1500, lambda: self.amount_label.configure(text_color=GOLD))




class WarlocksSalesTracker(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("WARLOCKS SALES TRACKER")
        self.configure(fg_color=BLACK)
        self.after(100, lambda: self.state("zoomed"))
        self.minsize(1200, 750)

        self.products = []
        self.sales = []
        self.current_quantity = 1
        self.selected_product_idx = None
        self.menu_open = False
        self.menu_frame = None
        self.product_row_widgets = []
        self.history_row_widgets = []

        self.setup_ui()
        self.load_data()

    def setup_ui(self):
        header = ctk.CTkFrame(self, fg_color=BLACK, corner_radius=0)
        header.pack(fill="x", padx=0, pady=(10, 0))
        header.pack_propagate(False)

        top_row = ctk.CTkFrame(header, fg_color=BLACK, height=40)
        top_row.pack(fill="x")
        top_row.pack_propagate(False)

        ctk.CTkButton(top_row, text="\u2630", command=self.toggle_menu, width=35, height=35, fg_color=DARK_RED, hover_color=RED, font=("Consolas", 16, "bold"), corner_radius=6).pack(side="left", padx=(20, 10), anchor="center", pady=2)

        aktura_path = resource_path("aktura.ttf")

        logo_path = resource_path("logo_accent.png")
        self._logo_w = 0

        logo_row = ctk.CTkFrame(header, fg_color=BLACK, height=200)
        logo_row.pack(fill="x")
        logo_row.pack_propagate(False)

        self._header_lbl = ctk.CTkLabel(logo_row, text="", fg_color=BLACK, height=200, compound="center")
        self._header_lbl.pack(fill="both", expand=True)

        self._aktura_path = aktura_path
        self._logo_path = logo_path
        self._logo_pil = None
        self._logo_row = logo_row

        if os.path.exists(logo_path):
            pil_logo = Image.open(logo_path).convert("RGBA")
            target_h = 200
            ratio = target_h / pil_logo.height
            pil_logo = pil_logo.resize((int(pil_logo.width * ratio), target_h), Image.LANCZOS)
            self._logo_pil = pil_logo
            self._logo_w = pil_logo.size[0]

        self.header = header
        self.after(300, self._init_header_animation)
        self.header.bind("<Configure>", lambda e: self._on_header_resize())

        self.tabview = ctk.CTkTabview(self, fg_color=BLACK, segmented_button_fg_color=DARK_RED, segmented_button_selected_color=RED, segmented_button_selected_hover_color=HOVER_RED, text_color=TEXT_COLOR, corner_radius=10)
        self.tabview.pack(fill="both", padx=0, pady=(10, 0))

        self.tab_dashboard = self.tabview.add("DASHBOARD")
        self.tab_history = self.tabview.add("SALES HISTORY")

        self.setup_dashboard()
        self.setup_history_tab()

        footer = ctk.CTkFrame(self, fg_color=BLACK, corner_radius=0, height=30)
        footer.pack(fill="x")
        footer.pack_propagate(False)
        ctk.CTkLabel(footer, text="Created by NightmareRle", font=("Consolas", 11), text_color="#999999").pack(expand=True)
        ctk.CTkLabel(footer, text="All rights reserved", font=("Consolas", 10), text_color="#777777").pack(expand=True)

    def toggle_menu(self):
        if self.menu_open and self.menu_frame:
            self.menu_frame.destroy()
            self.menu_frame = None
            self.menu_open = False
            return
        self.menu_frame = ctk.CTkFrame(self, fg_color="#1a1a1a", corner_radius=10, border_width=2, border_color=RED)
        self.menu_frame.place(x=20, y=60)
        for text, cmd in [("  Dashboard  ", lambda: self.tabview.set("DASHBOARD")), ("  Sales History  ", lambda: self.tabview.set("SALES HISTORY")), ("  Save Data  ", self.save_to_file), ("  Load Data  ", self.load_from_file), ("  Export CSV  ", self.export_csv)]:
            ctk.CTkButton(self.menu_frame, text=text, command=cmd, width=170, height=40, fg_color="transparent", hover_color=DARK_RED, font=("Consolas", 12, "bold"), text_color=TEXT_COLOR, anchor="w", corner_radius=5).pack(padx=5, pady=2)
        self.menu_open = True

    def close_menu(self):
        if self.menu_open and self.menu_frame:
            self.menu_frame.destroy()
            self.menu_frame = None
            self.menu_open = False

    def _init_header_animation(self):
        if not os.path.exists(self._aktura_path):
            return
        self._header_phase = 0
        if getattr(self, "_anim_running", False):
            return
        if self._build_header_masks():
            self._anim_running = True
            self._animate_header()

    def _on_header_resize(self):
        if not os.path.exists(self._aktura_path):
            return
        try:
            self.after_cancel(self._resize_job)
        except Exception:
            pass
        self._resize_job = self.after(150, self._build_header_masks)

    def _build_header_masks(self):
        label_w = self._header_lbl.winfo_width()
        if label_w < 50:
            self.after(200, self._init_header_animation)
            return False

        text = "W  A  R  L  O  C  K  S"
        logo_gap = 10
        logo_w = self._logo_w if self._logo_pil else 0
        text_area_w = (label_w - logo_w - logo_gap * 2) // 2 if logo_w else label_w // 2

        best_size = 44
        fnt = None
        for sz in range(44, 10, -1):
            try:
                fnt = ImageFont.truetype(self._aktura_path, sz)
                tmp = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
                bbox = tmp.textbbox((0, 0), text, font=fnt)
                tw = bbox[2] - bbox[0]
                if tw <= text_area_w:
                    best_size = sz
                    break
            except:
                pass

        self._cached_label_w = label_w
        self._cached_best_size = best_size

        fnt = ImageFont.truetype(self._aktura_path, best_size)
        tmp = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
        bbox = tmp.textbbox((0, 0), text, font=fnt)
        tw = bbox[2] - bbox[0]
        th = bbox[3] - bbox[1] + 10

        self._cached_tw = tw
        self._cached_th = th

        outline_px = 4
        img_w = tw + outline_px * 2
        img_h = th + outline_px * 2

        white_layer = Image.new("L", (img_w, img_h), 0)
        d = ImageDraw.Draw(white_layer)
        d.text((outline_px, outline_px), text, font=fnt, fill=255)

        text_arr = np.array(white_layer) > 0
        dilated_arr = np.zeros((img_h, img_w), dtype=bool)
        for dx in range(-outline_px, outline_px + 1):
            for dy in range(-outline_px, outline_px + 1):
                if dx * dx + dy * dy <= outline_px * outline_px:
                    y_lo = max(0, dy)
                    y_hi = min(img_h, img_h + dy)
                    x_lo = max(0, dx)
                    x_hi = min(img_w, img_w + dx)
                    sy_lo = y_lo - dy
                    sy_hi = y_hi - dy
                    sx_lo = x_lo - dx
                    sx_hi = x_hi - dx
                    dilated_arr[y_lo:y_hi, x_lo:x_hi] |= text_arr[sy_lo:sy_hi, sx_lo:sx_hi]

        outline_arr = np.where(text_arr, 0, dilated_arr.astype(np.uint8) * 255)
        outline_mask = Image.fromarray(outline_arr.astype(np.uint8))

        self._font_obj = fnt
        mask_np = np.array(outline_mask)
        self._outline_mask_arr = mask_np
        self._text_mask_cache = white_layer
        self._cached_text_size = (img_w, img_h)
        ys_np, xs_np = np.nonzero(mask_np)
        self._outline_xs = xs_np.astype(np.int32)
        self._outline_ys = ys_np.astype(np.int32)
        self._outline_coords = mask_np
        tl = Image.new("RGBA", (img_w, img_h), (0, 0, 0, 0))
        ImageDraw.Draw(tl).text((0, 0), text, font=fnt, fill=(60, 0, 15, 255), mask=white_layer)
        self._text_layer_cache = tl
        return True

    def _animate_header(self):
        if not os.path.exists(self._aktura_path):
            return
        if not hasattr(self, "_outline_xs") or self._outline_xs.size == 0:
            self.after(50, self._animate_header)
            return

        label_w = self._cached_label_w
        target_h = 200
        tw = self._cached_tw
        img_w, img_h = self._cached_text_size
        outline_mask = self._outline_mask_arr
        xs = self._outline_xs
        ys = self._outline_ys
        text_layer = self._text_layer_cache
        steps = 12

        phase = self._header_phase % steps
        self._header_phase += 1

        wave = (np.sin(xs.astype(np.float64) * 0.06 + phase * 1.2) + 1.0) / 2.0
        v = (wave * 255).astype(np.uint8)
        col_arr = np.zeros((img_h, img_w, 3), dtype=np.uint8)
        col_arr[ys, xs, 0] = v
        col_arr[ys, xs, 1] = (v * 0.15).astype(np.uint8)
        col_arr[ys, xs, 2] = (v * 0.10).astype(np.uint8)

        rgba = np.zeros((img_h, img_w, 4), dtype=np.uint8)
        rgba[:, :, :3] = col_arr
        rgba[:, :, 3] = outline_mask
        gradient = Image.fromarray(rgba)

        combined = Image.alpha_composite(gradient, text_layer)

        logo_gap = 10
        logo_w = self._logo_w if self._logo_pil else 0
        canvas = Image.new("RGBA", (label_w, target_h), (10, 10, 10, 255))
        text_y = (target_h - img_h) // 2

        if self._logo_pil:
            total_w = tw * 2 + logo_w + logo_gap * 2
            left_x = (label_w - total_w) // 2
            canvas.paste(combined, (max(0, left_x), text_y), combined)
            logo_x = left_x + tw + logo_gap
            canvas.paste(self._logo_pil, (logo_x, 0), self._logo_pil)
            right_x = logo_x + logo_w + logo_gap
            canvas.paste(combined, (right_x, text_y), combined)
        else:
            left_x = (label_w - tw) // 2
            canvas.paste(combined, (max(0, left_x), text_y), combined)

        self._header_photo = ctk.CTkImage(light_image=canvas, dark_image=canvas, size=(label_w, target_h))
        self._header_lbl.configure(image=self._header_photo, compound="center")
        self.after(45, self._animate_header)

    def setup_dashboard(self):
        self.tab_dashboard.grid_columnconfigure(0, weight=30, minsize=400)
        self.tab_dashboard.grid_columnconfigure(1, weight=24, minsize=300)
        self.tab_dashboard.grid_columnconfigure(2, weight=8, minsize=150)
        self.tab_dashboard.grid_rowconfigure(0, weight=1)

        left = ctk.CTkFrame(self.tab_dashboard, fg_color=CARD_BG, corner_radius=12, border_width=1, border_color="#333333")
        left.grid(row=0, column=0, padx=(0, 8), pady=8, sticky="nsew")

        ctk.CTkLabel(left, text="PRODUCTS", font=("Consolas", 14, "bold"), text_color=RED).pack(fill="x", padx=15, pady=(12, 4))
        ctk.CTkFrame(left, fg_color=RED, height=2).pack(fill="x", padx=15, pady=(0, 8))

        cashier_row = ctk.CTkFrame(left, fg_color="transparent")
        cashier_row.pack(fill="x", padx=15, pady=(0, 8))
        ctk.CTkLabel(cashier_row, text="CASHIER:", font=("Consolas", 11), text_color=LABEL_GRAY).pack(side="left", padx=(0, 8))
        self.cashier_name = ctk.CTkEntry(cashier_row, placeholder_text="Enter name...", fg_color=INPUT_BG, border_color=BORDER, text_color=TEXT_COLOR, font=("Consolas", 12), height=34, corner_radius=6)
        self.cashier_name.pack(side="left", fill="x", expand=True)

        list_box = ctk.CTkFrame(left, fg_color=INPUT_BG, corner_radius=8, border_width=1, border_color=BORDER)
        list_box.pack(fill="both", expand=True, padx=15, pady=(0, 8))
        list_box.grid_columnconfigure(0, weight=1)
        list_box.grid_rowconfigure(1, weight=1)

        hdr = ctk.CTkFrame(list_box, fg_color="#0d0d0d", corner_radius=0)
        hdr.grid(row=0, column=0, sticky="ew")
        for text, w in [("NAME", 220), ("PRICE", 110), ("CATEGORY", 160)]:
            ctk.CTkLabel(hdr, text=text, font=("Consolas", 11, "bold"), text_color=RED, width=w, anchor="w").pack(side="left", padx=10, pady=8)

        self.product_scroll = ctk.CTkScrollableFrame(list_box, fg_color="transparent", scrollbar_fg_color=DARK_RED, scrollbar_button_color=DARK_RED, scrollbar_button_hover_color=RED)
        self.product_scroll.grid(row=1, column=0, sticky="nsew", padx=2, pady=2)

        btn_bar = ctk.CTkFrame(left, fg_color="transparent")
        btn_bar.pack(fill="x", padx=15, pady=(0, 12))
        ctk.CTkButton(btn_bar, text="ADD", command=self.show_add_dialog, width=100, height=36, fg_color=DARK_RED, hover_color=RED, font=("Consolas", 11, "bold"), corner_radius=6).pack(side="left", padx=(0, 8))
        ctk.CTkButton(btn_bar, text="REMOVE", command=self.remove_product, width=100, height=36, fg_color="#440000", hover_color="#660000", font=("Consolas", 11, "bold"), corner_radius=6).pack(side="left")

        right = ctk.CTkFrame(self.tab_dashboard, fg_color=CARD_BG, corner_radius=12, border_width=1, border_color="#333333")
        right.grid(row=0, column=1, padx=8, pady=8, sticky="nsew")

        ctk.CTkLabel(right, text="QUANTITY", font=("Consolas", 11, "bold"), text_color=RED).pack(anchor="w", padx=15, pady=(12, 5))
        qf = ctk.CTkFrame(right, fg_color="transparent")
        qf.pack(fill="x", padx=15, pady=(0, 4))
        ctk.CTkButton(qf, text="-", width=44, height=36, command=lambda: self.change_quantity(-1), fg_color=DARK_RED, hover_color=RED, font=("Consolas", 16, "bold"), corner_radius=6).pack(side="left")
        self.qty_label = ctk.CTkLabel(qf, text="1", font=("Consolas", 16, "bold"), text_color=NEON_RED, width=60)
        self.qty_label.pack(side="left", padx=8)
        ctk.CTkButton(qf, text="+", width=44, height=36, command=lambda: self.change_quantity(1), fg_color=DARK_RED, hover_color=RED, font=("Consolas", 16, "bold"), corner_radius=6).pack(side="left")

        mf = ctk.CTkFrame(right, fg_color="transparent")
        mf.pack(fill="x", padx=15, pady=(0, 4))
        self.manual_qty = ctk.CTkEntry(mf, width=70, fg_color=INPUT_BG, border_color=BORDER, text_color=TEXT_COLOR, font=("Consolas", 12), height=34, corner_radius=6)
        self.manual_qty.pack(side="left")
        self.manual_qty.insert(0, "1")
        ctk.CTkButton(mf, text="SET", command=self.set_manual_qty, width=45, height=34, fg_color=DARK_RED, hover_color=RED, font=("Consolas", 10, "bold"), corner_radius=6).pack(side="left", padx=6)

        ctk.CTkButton(right, text="ADD SALE", command=self.add_sale, fg_color=RED, hover_color=HOVER_RED, font=("Consolas", 11, "bold"), height=36, corner_radius=6).pack(fill="x", padx=15, pady=(6, 4))

        self.cash_jar = CashJar(right)
        self.cash_jar.pack(fill="x", padx=10, pady=(0, 12))

        calc_card = ctk.CTkFrame(self.tab_dashboard, fg_color=CARD_BG, corner_radius=12, border_width=1, border_color="#333333")
        calc_card.grid(row=0, column=2, padx=(8, 0), pady=8, sticky="nsew")

        ctk.CTkLabel(calc_card, text="CALCULATOR", font=("Consolas", 10, "bold"), text_color=RED).pack(fill="x", padx=6, pady=(8, 4))
        ctk.CTkFrame(calc_card, fg_color=RED, height=2).pack(fill="x", padx=6, pady=(0, 4))

        self.calc_display = ctk.CTkEntry(calc_card, fg_color="#0a0a0a", border_color=RED, text_color=NEON_RED, font=("Consolas", 14, "bold"), justify="right", height=34, corner_radius=6, border_width=2)
        self.calc_display.pack(fill="x", padx=6, pady=(0, 4))
        self.calc_display.insert(0, "0")

        cg = ctk.CTkFrame(calc_card, fg_color="transparent")
        cg.pack(fill="both", expand=True, padx=4, pady=(0, 6))
        for i in range(4):
            cg.grid_columnconfigure(i, weight=1)
        for i in range(5):
            cg.grid_rowconfigure(i, weight=1)

        btns = [
            ("C", 0, 0, RED), ("(", 0, 1, GRAY), (")", 0, 2, GRAY), ("/", 0, 3, DARK_RED),
            ("7", 1, 0, GRAY), ("8", 1, 1, GRAY), ("9", 1, 2, GRAY), ("*", 1, 3, DARK_RED),
            ("4", 2, 0, GRAY), ("5", 2, 1, GRAY), ("6", 2, 2, GRAY), ("-", 2, 3, DARK_RED),
            ("1", 3, 0, GRAY), ("2", 3, 1, GRAY), ("3", 3, 2, GRAY), ("+", 3, 3, DARK_RED),
        ]
        for text, r, c, color in btns:
            ctk.CTkButton(cg, text=text, command=lambda t=text: self.calc_button(t), fg_color=color, hover_color=RED if color != RED else "#ff3333", font=("Consolas", 9, "bold"), corner_radius=4, height=30).grid(row=r, column=c, padx=1, pady=1, sticky="nsew")
        ctk.CTkButton(cg, text="0", command=lambda: self.calc_button("0"), fg_color=GRAY, hover_color=DARK_RED, font=("Consolas", 9, "bold"), corner_radius=4, height=30).grid(row=4, column=0, padx=1, pady=1, sticky="nsew")
        ctk.CTkButton(cg, text=".", command=lambda: self.calc_button("."), fg_color=GRAY, hover_color=DARK_RED, font=("Consolas", 9, "bold"), corner_radius=4, height=30).grid(row=4, column=1, padx=1, pady=1, sticky="nsew")
        ctk.CTkButton(cg, text="=", command=lambda: self.calc_button("="), fg_color=RED, hover_color=HOVER_RED, font=("Consolas", 9, "bold"), corner_radius=4, height=30).grid(row=4, column=2, columnspan=2, padx=1, pady=1, sticky="nsew")

    def setup_history_tab(self):
        self.tab_history.grid_columnconfigure(0, weight=1)
        self.tab_history.grid_rowconfigure(1, weight=1)

        sf = ctk.CTkFrame(self.tab_history, fg_color=CARD_BG, corner_radius=10, border_width=1, border_color="#333333")
        sf.grid(row=0, column=0, padx=10, pady=(10, 5), sticky="ew")
        si = ctk.CTkFrame(sf, fg_color="transparent")
        si.pack(fill="x", padx=15, pady=10)
        ctk.CTkLabel(si, text="SEARCH:", font=("Consolas", 11), text_color=LABEL_GRAY).pack(side="left")
        self.search_var = ctk.CTkEntry(si, width=280, fg_color=INPUT_BG, border_color=BORDER, text_color=TEXT_COLOR, font=("Consolas", 12), height=34, corner_radius=6)
        self.search_var.pack(side="left", padx=(8, 12))
        self.search_var.bind("<KeyRelease>", lambda e: self.filter_history())
        ctk.CTkButton(si, text="CLEAR", command=self.clear_search, width=70, height=34, fg_color=DARK_RED, hover_color=RED, font=("Consolas", 10, "bold"), corner_radius=6).pack(side="left")

        hc = ctk.CTkFrame(self.tab_history, fg_color=CARD_BG, corner_radius=10, border_width=1, border_color="#333333")
        hc.grid(row=1, column=0, padx=10, pady=5, sticky="nsew")
        hc.grid_columnconfigure(0, weight=1)
        hc.grid_rowconfigure(1, weight=1)

        hh = ctk.CTkFrame(hc, fg_color="#0d0d0d", corner_radius=0)
        hh.grid(row=0, column=0, sticky="ew")
        for text, w in [("DATE", 150), ("CASHIER", 120), ("PRODUCT", 180), ("QTY", 60), ("PRICE", 80), ("TOTAL", 80), ("", 50)]:
            ctk.CTkLabel(hh, text=text, font=("Consolas", 11, "bold"), text_color=RED, width=w, anchor="w").pack(side="left", padx=8, pady=8)

        self.history_scroll = ctk.CTkScrollableFrame(hc, fg_color="transparent", scrollbar_fg_color=DARK_RED, scrollbar_button_color=DARK_RED, scrollbar_button_hover_color=RED)
        self.history_scroll.grid(row=1, column=0, sticky="nsew", padx=2, pady=2)

        hb = ctk.CTkFrame(self.tab_history, fg_color=CARD_BG, corner_radius=10, border_width=1, border_color="#333333")
        hb.grid(row=2, column=0, padx=10, pady=(5, 10), sticky="ew")
        hbi = ctk.CTkFrame(hb, fg_color="transparent")
        hbi.pack(fill="x", padx=15, pady=8)
        self.history_stats = ctk.CTkLabel(hbi, text="ITEMS: 0  |  REVENUE: ₱0.00", font=("Consolas", 12, "bold"), text_color=LABEL_GRAY)
        self.history_stats.pack(side="left")
        ctk.CTkButton(hbi, text="CLEAR ALL", command=self.clear_history, fg_color="#220000", hover_color="#440000", font=("Consolas", 10, "bold"), width=100, height=34, corner_radius=6).pack(side="right")

    def show_add_dialog(self):
        win = ctk.CTkToplevel(self)
        win.title("Add Product")
        win.geometry("380x320")
        win.configure(fg_color=BLACK)
        win.transient(self)
        win.grab_set()

        ctk.CTkLabel(win, text="ADD PRODUCT", font=("Consolas", 16, "bold"), text_color=RED).pack(pady=14)

        ctk.CTkLabel(win, text="NAME", font=("Consolas", 10), text_color=LABEL_GRAY).pack(anchor="w", padx=35)
        name_e = ctk.CTkEntry(win, fg_color=INPUT_BG, border_color=BORDER, text_color=TEXT_COLOR, font=("Consolas", 12), width=300, height=36, corner_radius=6)
        name_e.pack(pady=(2, 10))

        ctk.CTkLabel(win, text="PRICE (₱)", font=("Consolas", 10), text_color=LABEL_GRAY).pack(anchor="w", padx=35)
        price_e = ctk.CTkEntry(win, fg_color=INPUT_BG, border_color=BORDER, text_color=TEXT_COLOR, font=("Consolas", 12), width=300, height=36, corner_radius=6)
        price_e.pack(pady=(2, 10))

        ctk.CTkLabel(win, text="CATEGORY", font=("Consolas", 10), text_color=LABEL_GRAY).pack(anchor="w", padx=35)
        cat_e = ctk.CTkEntry(win, fg_color=INPUT_BG, border_color=BORDER, text_color=TEXT_COLOR, font=("Consolas", 12), width=300, height=36, corner_radius=6)
        cat_e.pack(pady=(2, 14))

        def do_add():
            name = name_e.get().strip()
            price_str = price_e.get().strip()
            cat = cat_e.get().strip() or "Uncategorized"
            if not name:
                messagebox.showwarning("Warning", "Enter a name")
                return
            try:
                price = float(price_str)
                if price < 0:
                    raise ValueError
            except ValueError:
                messagebox.showwarning("Warning", "Enter a valid price")
                return
            self.products.append({"id": int(datetime.now().timestamp() * 1000), "name": name, "price": price, "category": cat})
            self.update_product_list()
            self.save_data()
            win.destroy()

        ctk.CTkButton(win, text="ADD", command=do_add, fg_color=RED, hover_color=HOVER_RED, font=("Consolas", 12, "bold"), height=38, corner_radius=6).pack(pady=4)

    def update_product_list(self):
        for w in self.product_row_widgets:
            w.destroy()
        self.product_row_widgets.clear()
        self.selected_product_idx = None
        for i, p in enumerate(self.products):
            row = ctk.CTkFrame(self.product_scroll, fg_color="transparent", height=38)
            row.pack(fill="x", pady=1)
            row.pack_propagate(False)
            self.product_row_widgets.append(row)
            ctk.CTkLabel(row, text=p["name"], font=("Consolas", 12), text_color=TEXT_COLOR, width=220, anchor="w").pack(side="left", padx=10, pady=4)
            ctk.CTkLabel(row, text=f"₱{p['price']:.2f}", font=("Consolas", 12), text_color=NEON_RED, width=110, anchor="w").pack(side="left", padx=10, pady=4)
            ctk.CTkLabel(row, text=p["category"], font=("Consolas", 12), text_color="#aaaaaa", width=160, anchor="w").pack(side="left", padx=10, pady=4)
            row.bind("<Button-1>", lambda e, idx=i: self.select_product(idx))
            for child in row.winfo_children():
                child.bind("<Button-1>", lambda e, idx=i: self.select_product(idx))

    def select_product(self, idx):
        self.selected_product_idx = idx
        for i, row in enumerate(self.product_row_widgets):
            row.configure(fg_color=DARK_RED if i == idx else "transparent")

    def remove_product(self):
        if self.selected_product_idx is None:
            messagebox.showwarning("Warning", "Select a product first")
            return
        if messagebox.askyesno("Confirm", "Remove this product?"):
            del self.products[self.selected_product_idx]
            self.selected_product_idx = None
            self.update_product_list()
            self.save_data()

    def change_quantity(self, delta):
        self.current_quantity = max(1, self.current_quantity + delta)
        self.qty_label.configure(text=str(self.current_quantity))
        self.manual_qty.delete(0, "end")
        self.manual_qty.insert(0, str(self.current_quantity))

    def set_manual_qty(self):
        try:
            v = int(self.manual_qty.get())
            if v > 0:
                self.current_quantity = v
                self.qty_label.configure(text=str(v))
        except ValueError:
            messagebox.showwarning("Warning", "Enter a valid number")

    def add_sale(self):
        if self.selected_product_idx is None:
            messagebox.showwarning("Warning", "Select a product from the list")
            return
        product = self.products[self.selected_product_idx]
        cashier = self.cashier_name.get().strip() or "Unknown"
        sale = {
            "id": int(datetime.now().timestamp() * 1000),
            "productName": product["name"],
            "price": product["price"],
            "category": product.get("category", "N/A"),
            "quantity": self.current_quantity,
            "total": round(product["price"] * self.current_quantity, 2),
            "cashier": cashier,
            "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        self.sales.append(sale)
        self.cash_jar.add_to_jar(sale["total"])
        self.current_quantity = 1
        self.qty_label.configure(text="1")
        self.manual_qty.delete(0, "end")
        self.manual_qty.insert(0, "1")
        self.filter_history()
        self.save_data()

    def filter_history(self):
        search = self.search_var.get().strip().lower()
        filtered = []
        for s in reversed(self.sales):
            if search in s["productName"].lower() or search in s.get("cashier", "").lower() or search in s.get("category", "").lower():
                filtered.append(s)
        self.render_history(filtered)

    def render_history(self, items):
        for w in self.history_row_widgets:
            w.destroy()
        self.history_row_widgets.clear()
        total = 0.0
        count = 0
        for sale in items:
            row = ctk.CTkFrame(self.history_scroll, fg_color="transparent", height=36)
            row.pack(fill="x", pady=1)
            row.pack_propagate(False)
            self.history_row_widgets.append(row)
            for v, w in [(sale["date"], 150), (sale.get("cashier", "N/A"), 120), (sale["productName"], 180), (str(sale["quantity"]), 60), (f"₱{sale['price']:.2f}", 80), (f"₱{sale['total']:.2f}", 80)]:
                ctk.CTkLabel(row, text=v, font=("Consolas", 11), text_color="#cccccc", width=w, anchor="w").pack(side="left", padx=8, pady=4)
            ctk.CTkButton(row, text="X", command=lambda sid=sale["id"]: self.remove_sale(sid), width=32, height=24, fg_color="#220000", hover_color="#8b0000", text_color=RED, font=("Consolas", 10, "bold"), corner_radius=4).pack(side="left", padx=6, pady=0)
            total += sale["total"]
            count += sale["quantity"]
        self.history_stats.configure(text=f"ITEMS: {count}  |  REVENUE: ₱{total:.2f}")

    def remove_sale(self, sale_id):
        sale = next((s for s in self.sales if s["id"] == sale_id), None)
        if sale is None:
            return
        desc = f"{sale['productName']} x{sale['quantity']} (₱{sale['total']:.2f})"
        if not messagebox.askyesno("Remove Sale", f"Remove this sale?\n\n{desc}  —  {sale.get('cashier', 'N/A')}  {sale['date']}"):
            return
        self.sales.remove(sale)
        self.filter_history()
        self.save_data()

    def clear_search(self):
        self.search_var.delete(0, "end")
        self.filter_history()

    def clear_history(self):
        if self.sales and messagebox.askyesno("Confirm", "Clear ALL sales history?"):
            self.sales = []
            self.filter_history()
            self.save_data()

    def calc_button(self, char):
        current = self.calc_display.get()
        if char == "C":
            self.calc_display.delete(0, "end")
            self.calc_display.insert(0, "0")
        elif char == "=":
            try:
                result = eval(self.calc_display.get())
                self.calc_display.delete(0, "end")
                self.calc_display.insert(0, str(round(result, 2)))
            except:
                self.calc_display.delete(0, "end")
                self.calc_display.insert(0, "ERROR")
        elif current == "0" and char not in ["(", ")"]:
            self.calc_display.delete(0, "end")
            self.calc_display.insert(0, char)
        else:
            self.calc_display.insert("end", char)

    def save_data(self):
        with open(os.path.join(app_data_path(), "sales_data.json"), "w") as f:
            json.dump({"products": self.products, "sales": self.sales}, f, indent=2)

    def load_data(self):
        try:
            with open(os.path.join(app_data_path(), "sales_data.json"), "r") as f:
                data = json.load(f)
                self.products = data.get("products", [])
                self.sales = data.get("sales", [])
                self.update_product_list()
                self.filter_history()
        except FileNotFoundError:
            pass

    def save_to_file(self):
        self.close_menu()
        path = filedialog.asksaveasfilename(defaultextension=".json", filetypes=[("JSON", "*.json")], initialfile="sales_data.json")
        if path:
            with open(path, "w") as f:
                json.dump({"products": self.products, "sales": self.sales}, f, indent=2)
            messagebox.showinfo("Saved", f"Data saved to:\n{path}")

    def load_from_file(self):
        self.close_menu()
        path = filedialog.askopenfilename(filetypes=[("JSON", "*.json")])
        if path:
            try:
                with open(path, "r") as f:
                    data = json.load(f)
                    self.products = data.get("products", [])
                    self.sales = data.get("sales", [])
                    self.update_product_list()
                    self.filter_history()
                    self.save_data()
                    messagebox.showinfo("Loaded", "Data loaded!")
            except Exception as e:
                messagebox.showerror("Error", str(e))

    def export_csv(self):
        self.close_menu()
        if not self.sales:
            messagebox.showwarning("Warning", "No sales to export")
            return
        path = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV", "*.csv")], initialfile="sales_export.csv")
        if path:
            with open(path, "w", newline="") as f:
                w = csv.writer(f)
                w.writerow(["Date", "Cashier", "Product", "Category", "Quantity", "Price", "Total"])
                for s in self.sales:
                    w.writerow([s["date"], s.get("cashier", ""), s["productName"], s.get("category", ""), s["quantity"], s["price"], s["total"]])
            messagebox.showinfo("Exported", f"CSV saved to:\n{path}")


if __name__ == "__main__":
    try:
        app = WarlocksSalesTracker()
        app.mainloop()
    except Exception:
        pass
