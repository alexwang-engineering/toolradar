#!/usr/bin/env python3
"""
ToolRadar macOS app icon — Howl's Moving Castle style
Reference: baomii.com Howl's Moving Castle widget icon pack (patreon.com/boomii)
           The castle-on-hills icon: warm golden background, scalloped border,
           castle sitting on rolling green hills, warm storybook illustration palette.
Colour palette cross-referenced with:
  ColorsWall Howl's fanart:  #EAC41A #E88DA7 #782C2C #5C949C #D4D4A4
  trycolors.com / COLOURlovers Howl's palette confirmed similar warm gold + teal
  boardmix Miyazaki: #4F90CA (accent only), #7B852E (hills green)
"""
from PIL import Image, ImageDraw, ImageFilter
import math, os

# ── Palette (all from real film/reference research) ──────────────────────────
SKY_ZENITH   = (138, 182, 212)   # soft warm blue at very top
SKY_MID      = (210, 175,  90)   # golden-wheat mid sky (#D2AF5A)
SKY_HORIZON  = (228, 196, 100)   # warm amber horizon (#E4C464)
HILL_DARK    = ( 80, 115,  40)   # deep green hills (slightly darker than #7B852E)
HILL_MID     = (120, 155,  55)   # mid green
HILL_LIGHT   = (160, 195,  80)   # highlight green (sunlit)
BORDER_OUTER = (210, 165,  72)   # scalloped border outer #D2A548 (warm gold)
BORDER_INNER = (240, 210, 120)   # scalloped border inner rim (light gold)
CASTLE_DRK   = ( 80,  50,  22)   # castle deep shadow
CASTLE_MID   = (115,  78,  42)   # castle warm brown body
CASTLE_LIT   = (160, 115,  65)   # sunlit face of castle
CHIMNEY_C    = ( 65,  40,  15)   # chimney dark
WINDOW_GLOW  = (245, 200,  60)   # warm Calcifer-gold window #F5C83C
FIRE_ORANGE  = (231, 120,  50)   # Calcifer ember orange
BG_FILL      = (235, 215, 155)   # overall warm cream bg behind scallops


def lerp(a, b, t):
    return a + (b - a) * t

def lerp_c(c1, c2, t):
    return tuple(int(lerp(c1[i], c2[i], t)) for i in range(3))


def draw_icon(size):
    f = size / 1024.0
    img = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img, 'RGBA')

    # ── Cream/parchment outer background (behind scallop border) ────────────
    draw.rectangle([0, 0, size, size], fill=BG_FILL + (255,))

    # ── Scalloped border ─────────────────────────────────────────────────────
    # Draw circles around the perimeter to create the scalloped/cookie-dough edge
    margin = int(28 * f)
    scallop_r = max(2, int(22 * f))
    # How many scallops fit along each side
    inner_size = size - 2 * margin
    n_side = max(4, int(inner_size / max(1, scallop_r * 1.5)))
    positions = []
    step = inner_size / n_side
    for i in range(n_side):
        t = i * step + step / 2
        positions += [
            (margin + t,       margin),               # top
            (margin + t,       size - margin),         # bottom
            (margin,           margin + t),            # left
            (size - margin,    margin + t),            # right
        ]
    # Outer (darker gold) scallop circles
    for cx, cy in positions:
        r = scallop_r + int(3 * f)
        draw.ellipse([cx - r, cy - r, cx + r, cy + r],
                     fill=BORDER_OUTER + (255,))
    # Inner (lighter gold) rim
    for cx, cy in positions:
        r = scallop_r - int(2 * f)
        draw.ellipse([cx - r, cy - r, cx + r, cy + r],
                     fill=BORDER_INNER + (255,))

    # ── Inner scene area (clipped to a rounded rect inside the border) ───────
    pad = int(40 * f)
    scene_box = [pad, pad, size - pad, size - pad]
    # Scene background — filled first with sky
    draw.rounded_rectangle(scene_box, radius=int(18 * f), fill=SKY_ZENITH + (255,))

    # ── Sky gradient (warm golden, not cold blue) ─────────────────────────────
    clip_l, clip_t, clip_r, clip_b = scene_box
    scene_h = clip_b - clip_t
    scene_w = clip_r - clip_l
    for y in range(clip_t, clip_b):
        t = (y - clip_t) / scene_h
        if t < 0.35:
            c = lerp_c(SKY_ZENITH, SKY_MID, t / 0.35)
        else:
            c = lerp_c(SKY_MID, SKY_HORIZON, (t - 0.35) / 0.65)
        draw.line([(clip_l, y), (clip_r, y)], fill=c + (255,))

    # Re-clip rounded corners (paint over sky with transparent bg outside rounded rect)
    mask = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    mdraw = ImageDraw.Draw(mask)
    mdraw.rounded_rectangle(scene_box, radius=int(18 * f), fill=(0, 0, 0, 255))
    # Apply: only keep pixels inside scene_box
    result = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    result.paste(Image.new('RGBA', (size, size), BG_FILL + (255,)), (0, 0))
    # Re-paint scallops
    for cx, cy in positions:
        r = scallop_r + int(3 * f)
        ImageDraw.Draw(result).ellipse([cx - r, cy - r, cx + r, cy + r],
                                        fill=BORDER_OUTER + (255,))
    for cx, cy in positions:
        r = scallop_r - int(2 * f)
        ImageDraw.Draw(result).ellipse([cx - r, cy - r, cx + r, cy + r],
                                        fill=BORDER_INNER + (255,))
    # Paste sky into scene box
    result.paste(img, (0, 0), mask)
    img = result
    draw = ImageDraw.Draw(img, 'RGBA')

    # ── Warm sun glow near horizon (right side, characteristic Ghibli sun) ───
    sun_cx = int(820 * f)
    sun_cy = int(520 * f)
    for r_pct, alpha in [(0.14, 20), (0.10, 35), (0.07, 55), (0.045, 90), (0.028, 140)]:
        r = int(size * r_pct)
        draw.ellipse([sun_cx - r, sun_cy - r, sun_cx + r, sun_cy + r],
                     fill=(255, 230, 150, alpha))

    # ── Rolling hills (ellipses for organic shape) ────────────────────────────
    # Back hill (lighter, distant)
    bh_cy = int(680 * f)
    draw.ellipse([int(-50*f), bh_cy, int(700*f), bh_cy + int(260*f)],
                 fill=HILL_MID + (255,))
    # Another back hill right side
    draw.ellipse([int(400*f), bh_cy + int(20*f), int(1100*f), bh_cy + int(280*f)],
                 fill=HILL_MID + (255,))
    # Front hill (darker, closer)
    fh_cy = int(730*f)
    draw.ellipse([int(-80*f), fh_cy, int(800*f), fh_cy + int(320*f)],
                 fill=HILL_DARK + (255,))
    # Front hill right
    draw.ellipse([int(350*f), fh_cy + int(30*f), int(1150*f), fh_cy + int(330*f)],
                 fill=HILL_DARK + (255,))
    # Sunlit highlight on front hill
    draw.ellipse([int(80*f), fh_cy - int(10*f), int(560*f), fh_cy + int(100*f)],
                 fill=HILL_LIGHT + (160,))
    # Fill bottom of scene below hills
    draw.rectangle([clip_l, int(780*f), clip_r, clip_b], fill=HILL_DARK + (255,))

    # ── Calcifer glow (warm fire under castle body) ──────────────────────────
    gc_x = int(512 * f)
    gc_y = int(710 * f)
    for r, alpha, col in [
        (int(100*f), 25, (245, 200, 60)),
        (int(70*f),  45, (245, 180, 50)),
        (int(48*f),  75, (235, 140, 40)),
        (int(28*f), 120, (220, 110, 30)),
        (int(14*f), 170, (200,  80, 20)),
    ]:
        draw.ellipse([gc_x - r, gc_y - r//2, gc_x + r, gc_y + r//2],
                     fill=col + (alpha,))

    # ── Castle legs ──────────────────────────────────────────────────────────
    lw = int(17 * f)
    def leg(pts, w):
        scaled = [(int(x*f), int(y*f)) for x, y in pts]
        for i in range(len(scaled) - 1):
            draw.line([scaled[i], scaled[i+1]], fill=CASTLE_DRK + (255,), width=w)
        for p in scaled[1:-1]:
            r = w // 2 + int(3*f)
            draw.ellipse([p[0]-r, p[1]-r, p[0]+r, p[1]+r], fill=CASTLE_DRK + (255,))
    leg([(350, 700), (260, 768), (305, 820)], lw)
    leg([(450, 708), (408, 775), (438, 820)], lw)
    leg([(574, 708), (616, 775), (586, 820)], lw)
    leg([(674, 700), (764, 768), (718, 820)], lw)

    # ── Castle body (warmer tones, sitting on hill) ──────────────────────────
    # Left wing
    draw.rectangle([int(122*f), int(568*f), int(376*f), int(698*f)],
                   fill=CASTLE_MID + (255,))
    draw.rectangle([int(122*f), int(568*f), int(376*f), int(582*f)],
                   fill=CASTLE_LIT + (255,))  # sunlit top

    # Right wing
    draw.rectangle([int(648*f), int(548*f), int(902*f), int(698*f)],
                   fill=CASTLE_MID + (255,))
    draw.rectangle([int(648*f), int(548*f), int(902*f), int(562*f)],
                   fill=CASTLE_LIT + (255,))

    # Main body
    draw.rectangle([int(304*f), int(438*f), int(720*f), int(704*f)],
                   fill=CASTLE_MID + (255,))
    draw.rectangle([int(304*f), int(438*f), int(720*f), int(454*f)],
                   fill=CASTLE_LIT + (255,))
    draw.rectangle([int(700*f), int(438*f), int(720*f), int(704*f)],
                   fill=CASTLE_DRK + (255,))  # right shadow

    # Panel seams
    for px in [400, 490, 580, 668]:
        draw.rectangle([int(px*f), int(458*f), int((px+5)*f), int(684*f)],
                       fill=CASTLE_DRK + (200,))

    # Upper tower
    draw.rectangle([int(390*f), int(308*f), int(634*f), int(448*f)],
                   fill=CASTLE_MID + (255,))
    draw.rectangle([int(390*f), int(308*f), int(634*f), int(322*f)],
                   fill=CASTLE_LIT + (255,))
    # Battlements
    for bx in range(int(390*f), int(634*f), max(1, int(40*f))):
        draw.rectangle([bx, int(286*f), bx + int(22*f), int(308*f)],
                       fill=CASTLE_DRK + (255,))

    # Tall spire
    sp_cx = int(512 * f)
    sp_w  = int(60 * f)
    sp_y1 = int(172 * f)
    draw.rectangle([sp_cx - sp_w//2, sp_y1, sp_cx + sp_w//2, int(308*f)],
                   fill=CASTLE_DRK + (255,))
    draw.polygon([(sp_cx - sp_w//2 - int(8*f), sp_y1),
                  (sp_cx + sp_w//2 + int(8*f), sp_y1),
                  (sp_cx, sp_y1 - int(55*f))],
                 fill=CASTLE_DRK + (255,))
    # spire lit edge
    draw.line([(sp_cx - int(2*f), sp_y1), (sp_cx - int(4*f), sp_y1 - int(55*f))],
              fill=CASTLE_MID + (200,), width=max(1, int(4*f)))

    # Side turrets
    draw.rectangle([int(730*f), int(388*f), int(808*f), int(548*f)],
                   fill=CASTLE_DRK + (255,))
    draw.rectangle([int(730*f), int(388*f), int(808*f), int(400*f)],
                   fill=CASTLE_MID + (200,))
    draw.rectangle([int(216*f), int(408*f), int(298*f), int(568*f)],
                   fill=CASTLE_DRK + (255,))
    draw.rectangle([int(216*f), int(408*f), int(298*f), int(420*f)],
                   fill=CASTLE_MID + (200,))

    # ── Chimneys ─────────────────────────────────────────────────────────────
    chimneys = [
        (162, 510, 18, 68), (238, 436, 15, 78), (322, 380, 17, 68),
        (424, 310, 13, 54), (600, 314, 13, 54),
        (698, 374, 17, 74), (780, 424, 15, 70), (870, 494, 18, 65),
    ]
    for cx_c, ty, cw, ch in chimneys:
        cx_c, ty = int(cx_c*f), int(ty*f)
        cw, ch   = int(cw*f), int(ch*f)
        draw.rectangle([cx_c - cw//2, ty, cx_c + cw//2, ty + ch],
                       fill=CHIMNEY_C + (255,))
        cap_x = int(5*f)
        draw.rectangle([cx_c - cw//2 - cap_x, ty - int(8*f),
                        cx_c + cw//2 + cap_x, ty + int(4*f)],
                       fill=(40, 22, 5, 255))

    # ── Smoke (soft, warm tinted) ─────────────────────────────────────────────
    if size >= 64:
        for cx_c, ty, cw, ch in chimneys[:4]:
            cx_c, ty = int(cx_c*f), int(ty*f)
            for ox, oy, r, a in [(0,-18,12,45),(6,-36,16,32),(-5,-58,20,20),(8,-82,24,10)]:
                sr = int(r*f)
                sx, sy = cx_c + int(ox*f), ty + int(oy*f)
                draw.ellipse([sx-sr, sy-sr, sx+sr, sy+sr], fill=(220,205,175, a))

    # ── Windows (warm golden glow — Calcifer candle warmth) ──────────────────
    windows = [
        (336,492,28,40),(406,492,28,40),(476,492,28,40),(546,492,28,40),(616,492,28,40),
        (436,354,24,34),(512,354,24,34),(588,354,24,34),
        (154,604,24,34),(222,604,24,34),(298,604,24,34),
        (676,586,24,34),(748,586,24,34),(818,586,24,34),
    ]
    for wx, wy, ww, wh in windows:
        wx, wy, ww, wh = int(wx*f), int(wy*f), int(ww*f), int(wh*f)
        if ww < 3 or wh < 3:
            continue
        pad = int(5*f)
        draw.rectangle([wx-pad, wy-pad, wx+ww+pad, wy+wh+pad], fill=(245,200,60,30))
        draw.rectangle([wx, wy, wx+ww, wy+wh], fill=WINDOW_GLOW + (200,))
        draw.rectangle([wx, wy, wx+ww, wy+wh],
                       outline=CASTLE_DRK + (255,), width=max(1, int(2*f)))

    # ── Sparkle dots (decorative, like baomii icons) ─────────────────────────
    if size >= 128:
        sparkles = [(200,200),(820,180),(160,620),(860,340),(780,720),(240,760)]
        for sx, sy in sparkles:
            sx, sy = int(sx*f), int(sy*f)
            sr = max(2, int(6*f))
            draw.ellipse([sx-sr, sy-sr, sx+sr, sy+sr], fill=(255,240,180,160))
            draw.line([(sx-sr*2, sy),(sx+sr*2, sy)], fill=(255,240,180,100), width=max(1,int(2*f)))
            draw.line([(sx, sy-sr*2),(sx, sy+sr*2)], fill=(255,240,180,100), width=max(1,int(2*f)))

    # ── Decorative gold border line inside scallops ───────────────────────────
    border_pad = int(46 * f)
    border_w   = max(1, int(4 * f))
    draw.rounded_rectangle(
        [border_pad, border_pad, size - border_pad, size - border_pad],
        radius=int(14 * f),
        outline=BORDER_OUTER + (200,),
        width=border_w
    )

    return img


# ── Generate iconset ──────────────────────────────────────────────────────────
iconset = '/Users/wjl/tools-discovery/ToolRadar.iconset'
os.makedirs(iconset, exist_ok=True)

print("Rendering 1024×1024 master…")
master = draw_icon(1024)

specs = [
    (16,   'icon_16x16.png'),
    (32,   'icon_16x16@2x.png'),
    (32,   'icon_32x32.png'),
    (64,   'icon_32x32@2x.png'),
    (128,  'icon_128x128.png'),
    (256,  'icon_128x128@2x.png'),
    (256,  'icon_256x256.png'),
    (512,  'icon_256x256@2x.png'),
    (512,  'icon_512x512.png'),
    (1024, 'icon_512x512@2x.png'),
]
for px, name in specs:
    if px == 1024:
        img = master
    elif px <= 32:
        img = draw_icon(px)
    else:
        img = master.resize((px, px), Image.LANCZOS)
    img.save(os.path.join(iconset, name), 'PNG')
    print(f"  ✓ {name}  ({px}×{px})")

print("\nDone — run:  iconutil -c icns ToolRadar.iconset")
