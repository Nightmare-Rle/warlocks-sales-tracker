from PIL import Image, ImageDraw, ImageFilter, ImageOps
import numpy as np

img = Image.open("C:/sales-tracker/logo.png").convert("RGBA")
data = np.array(img)

white_threshold = 220
r, g, b, a = data[:,:,0], data[:,:,1], data[:,:,2], data[:,:,3]
white_mask = (r > white_threshold) & (g > white_threshold) & (b > white_threshold)
data[white_mask] = [0, 0, 0, 0]

cleaned = Image.fromarray(data)

alpha = cleaned.split()[3]
logo_pixels = np.array(alpha)
has_content = logo_pixels > 10
if not has_content.any():
    print("Logo is empty after bg removal, using original")
    cleaned = img

inv = ImageOps.invert(cleaned.convert("RGB")).convert("RGBA")
inv_data = np.array(inv)
orig_alpha = np.array(cleaned.split()[3])
inv_data[:,:,3] = orig_alpha
bright_logo = Image.fromarray(inv_data)

alpha = bright_logo.split()[3]
edge = alpha.filter(ImageFilter.FIND_EDGES)
edge = edge.filter(ImageFilter.MaxFilter(5))
edge = edge.filter(ImageFilter.GaussianBlur(radius=4))

glow_data = np.array(edge)
red_glow = np.zeros((*glow_data.shape, 4), dtype=np.uint8)
red_glow[:,:,0] = 255
red_glow[:,:,1] = 0
red_glow[:,:,2] = 64
red_glow[:,:,3] = np.clip(glow_data * 3, 0, 255)
glow_layer = Image.fromarray(red_glow)
glow_layer = glow_layer.filter(ImageFilter.GaussianBlur(radius=6))

result = Image.new("RGBA", bright_logo.size, (0, 0, 0, 0))
result = Image.alpha_composite(result, glow_layer)
result = Image.alpha_composite(result, bright_logo)

padding = 15
new_w = result.width + padding * 2
new_h = result.height + padding * 2
final = Image.new("RGBA", (new_w, new_h), (0, 0, 0, 0))

final.paste(result, (padding, padding), result)

final.save("C:/sales-tracker/logo_accent.png")
print("Done! Logo is now bright with red outlines")
