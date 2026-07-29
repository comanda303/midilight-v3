from __future__ import annotations
import numpy as np

def _hsv_to_rgb(h: np.ndarray, s: np.ndarray, v: np.ndarray) -> np.ndarray:
    h = h % 1.0
    i = (h * 6).astype(np.int32)
    f = h * 6 - i
    p = v * (1.0 - s)
    q = v * (1.0 - f * s)
    t = v * (1.0 - (1.0 - f) * s)
    i6 = i % 6
    r = np.select([i6==0,i6==1,i6==2,i6==3,i6==4,i6==5], [v,q,p,p,t,v])
    g = np.select([i6==0,i6==1,i6==2,i6==3,i6==4,i6==5], [t,v,v,q,p,p])
    b = np.select([i6==0,i6==1,i6==2,i6==3,i6==4,i6==5], [p,p,t,v,v,q])
    return (np.stack([r, g, b], axis=-1) * 255).clip(0, 255).astype(np.uint8)

def _apply_symmetry(frame: np.ndarray, sym: float) -> np.ndarray:
    H, W = frame.shape[:2]
    if sym < 0.33:
        return frame
    left = frame[:, :W//2].copy()
    frame[:, W - W//2:] = left[:, ::-1]
    if sym >= 0.66:
        top = frame[:H//2, :].copy()
        frame[H - H//2:, :] = top[::-1, :]
    return frame

def _apply_blur(frame: np.ndarray, amount: float) -> np.ndarray:
    if amount < 0.02:
        return frame
    import cv2
    k = max(1, int(amount * 10)) * 2 + 1
    return cv2.GaussianBlur(frame, (k, k), 0)

def _algo_plasma(H, W, p, t, beat):
    Y, X = np.mgrid[0:H, 0:W].astype(np.float32)
    Y /= H; X /= W
    spd = 0.3 + p['speed'] * 2.0
    scl = 2.0 + p['scale'] * 8.0
    v = (np.sin(X * scl * 2*np.pi + t * spd)
       + np.sin(Y * scl * 2*np.pi + t * spd * 0.7)
       + np.sin((X + Y) * scl * np.pi + t * spd * 1.2)
       + np.sin(np.sqrt(np.clip((X-0.5)**2+(Y-0.5)**2,0,None)) * scl * 2*np.pi))
    v = (v / 4.0 + 0.5)
    v = np.clip(v + beat * p['beat_react'] * 0.4, 0, 1)
    hue = np.clip(p['hue'] + (v - 0.5) * p['color_spread'], 0, 1)
    sat = np.full_like(v, p['saturation'])
    v_out = np.clip((v - 0.5) * (1 + p['contrast'] * 3) + 0.5, 0, 1)
    return _hsv_to_rgb(hue, sat, v_out)

def _algo_fire(H, W, p, t, beat, buf):
    if 'fire' not in buf or buf['fire'].shape != (H, W):
        buf['fire'] = np.zeros((H, W), dtype=np.float32)
    fb = buf['fire']
    density = 0.3 + p['rhythm_density'] * 0.7
    spd = 0.05 + p['speed'] * 0.3
    ignite = np.random.random(W) < density
    fb[-1] = np.where(ignite, 1.0, np.maximum(fb[-1] - 0.1, 0))
    fb[-1] = np.minimum(1.0, fb[-1] + beat * p['beat_react'] * 0.8)
    spread = (np.roll(fb, -1, axis=1) + np.roll(fb, 1, axis=1) + fb) / 3.0
    fb[:-1] = np.clip(fb[:-1] + (spread[1:] - fb[:-1]) * spd - 0.02, 0, 1)
    r = np.clip(fb * 3.0, 0, 1)
    g = np.clip(fb * 3.0 - 1.0, 0, 1)
    b = np.clip(fb * 3.0 - 2.0, 0, 1)
    rgb = (np.stack([r, g, b], axis=-1) * 255).astype(np.uint8)
    hue_shift = p['hue']
    if hue_shift > 0.01:
        rgb = np.roll(rgb, int(hue_shift * 2), axis=-1)
    return rgb

def _algo_noise(H, W, p, t, beat):
    Y, X = np.mgrid[0:H, 0:W].astype(np.float32)
    Y /= H; X /= W
    spd = 0.2 + p['speed'] * 1.5
    scl = 1.0 + p['scale'] * 5.0
    octaves = max(1, int(1 + p['rhythm_density'] * 4))
    angle = p['direction'] * 2 * np.pi
    dx, dy = np.cos(angle), np.sin(angle)
    v = np.zeros((H, W), dtype=np.float32)
    amp, freq = 1.0, scl
    for _ in range(octaves):
        v += amp * np.sin((X*dx + Y*dy) * freq * 2*np.pi + t*spd)
        v += amp * np.sin((X*dy - Y*dx) * freq * np.pi + t*spd*1.3)
        amp *= 0.5; freq *= 2.0
    v = np.clip((v + 2) / 4 + beat * p['beat_react'] * 0.3, 0, 1)
    hue = np.clip(p['hue'] + (v-0.5)*p['color_spread'], 0, 1)
    sat = np.full_like(v, p['saturation'])
    v_out = np.clip((v-0.5)*(1+p['contrast']*3)+0.5, 0, 1)
    return _hsv_to_rgb(hue, sat, v_out)

def _algo_bars(H, W, p, t, beat):
    spd = 0.5 + p['speed'] * 4.0
    density = max(1, int(1 + p['rhythm_density'] * 15))
    x_pos = np.linspace(0, np.pi * 2 * density, W, dtype=np.float32)
    y_pos = np.linspace(0, np.pi * 2 * density, H, dtype=np.float32)
    hbars = (np.sin(x_pos + t * spd) * 0.5 + 0.5).reshape(1, W).repeat(H, axis=0)
    vbars = (np.sin(y_pos + t * spd * 1.3) * 0.5 + 0.5).reshape(H, 1).repeat(W, axis=1)
    d = p['direction']
    v = hbars * (1-d) + vbars * d
    v = np.clip(v + beat * p['beat_react'] * 0.5, 0, 1)
    hue = np.full((H, W), p['hue'], dtype=np.float32)
    sat = np.full((H, W), p['saturation'], dtype=np.float32)
    v_out = np.clip((v-0.5)*(1+p['contrast']*3)+0.5, 0, 1)
    return _hsv_to_rgb(hue, sat, v_out.astype(np.float32))

def _algo_radial(H, W, p, t, beat):
    Y, X = np.mgrid[0:H, 0:W].astype(np.float32)
    r = np.sqrt(((X - W/2)/W)**2 + ((Y - H/2)/H)**2)
    spd = 0.5 + p['speed'] * 3.0
    density = 1 + p['rhythm_density'] * 8
    v = np.sin(r * density * 2*np.pi - t * spd) * 0.5 + 0.5
    v = np.clip(v + beat * p['beat_react'] * (1-r), 0, 1)
    hue = np.clip(p['hue'] + r * p['color_spread'], 0, 1).astype(np.float32)
    sat = np.full((H, W), p['saturation'], dtype=np.float32)
    v_out = np.clip((v-0.5)*(1+p['contrast']*3)+0.5, 0, 1).astype(np.float32)
    return _hsv_to_rgb(hue, sat, v_out)

def _algo_stars(H, W, p, t, beat, buf):
    N = 300
    if 'stars' not in buf:
        buf['stars'] = np.random.rand(N, 3).astype(np.float32)
    stars = buf['stars']
    speed = 0.002 + p['speed'] * 0.05
    stars[:, 2] -= speed + beat * p['beat_react'] * 0.08
    reset = stars[:, 2] <= 0
    if reset.any():
        stars[reset, :2] = np.random.rand(int(reset.sum()), 2)
        stars[reset, 2] = 1.0
    z = np.maximum(stars[:, 2], 0.001)
    sx = (((stars[:, 0] - 0.5) / z + 0.5) * W).astype(np.float32)
    sy = (((stars[:, 1] - 0.5) / z + 0.5) * H).astype(np.float32)
    bri = ((1.0 - z) * p['saturation'] * 255).clip(0, 255).astype(np.uint8)
    canvas = np.zeros((H, W, 3), dtype=np.uint8)
    mask = (sx >= 0) & (sx < W) & (sy >= 0) & (sy < H)
    ix = sx[mask].astype(int)
    iy = sy[mask].astype(int)
    b = bri[mask]
    h6 = int((p['hue'] % 1.0) * 6) % 6
    mults = [(1,.5,0),(.7,1,0),(0,1,.5),(0,.7,1),(.5,0,1),(1,0,.7)]
    rm, gm, bm = mults[h6]
    canvas[iy, ix, 0] = (b * rm).astype(np.uint8)
    canvas[iy, ix, 1] = (b * gm).astype(np.uint8)
    canvas[iy, ix, 2] = (b * bm).astype(np.uint8)
    return canvas

def _algo_comet(H, W, p, t, beat):
    vertical = p['direction'] > 0.5
    L = H if vertical else W
    speed = 4.0 + p['speed'] * 60.0          # px / sec
    pos = (t * speed) % L
    tail = 2.0 + p['scale'] * (L * 0.6)
    idx = np.arange(L).astype(np.float32)
    dist = (pos - idx) % L                             # distance behind the head
    bright = np.exp(-dist / tail)
    bright = np.clip(bright * (1.0 + beat * p['beat_react'] * 0.5), 0.0, 1.0)
    if vertical:
        b = bright[:, None] * np.ones((1, W), np.float32)
    else:
        b = bright[None, :] * np.ones((H, 1), np.float32)
    hue = np.full((H, W), p['hue'], np.float32)
    sat = np.full((H, W), p['saturation'], np.float32) * (1.0 - b * 0.6)
    return _hsv_to_rgb(hue, sat, b)

def _algo_chase(H, W, p, t, beat):
    horizontal = p['direction'] <= 0.5
    L = W if horizontal else H
    period = int(4 + p['rhythm_density'] * 10)
    dash = max(1, int(period * (0.3 + p['scale'] * 0.4)))
    speed = 3.0 + p['speed'] * 30.0
    phase = int(t * speed)
    idx = np.arange(L)
    on = (((idx + phase) % period) < dash).astype(np.float32)
    group = (((idx + phase) // period) % 2).astype(np.float32)
    hue_line = (p['hue'] + group * p['color_spread'] * 0.5) % 1.0
    if horizontal:
        on_g = on[None, :] * np.ones((H, 1), np.float32)
        hue = hue_line[None, :] * np.ones((H, 1), np.float32)
    else:
        on_g = on[:, None] * np.ones((1, W), np.float32)
        hue = hue_line[:, None] * np.ones((1, W), np.float32)
    bg = beat * p['beat_react'] * 0.25
    val = np.maximum(on_g, bg)
    sat = np.full((H, W), p['saturation'], np.float32)
    return _hsv_to_rgb(hue, sat, val)

def _algo_wipe(H, W, p, t, beat):
    horizontal = p['direction'] <= 0.5
    L = W if horizontal else H
    speed = 0.2 + p['speed'] * 2.0            # wipes / sec
    phase = t * speed
    pass_i = int(phase)
    front = (phase - pass_i) * L
    idx = np.arange(L).astype(np.float32)
    base = p['hue']
    spread = p['color_spread']
    hue_new = (base + (pass_i + 1) * spread) % 1.0
    hue_old = (base + pass_i * spread) % 1.0
    hue_line = np.where(idx < front, hue_new, hue_old).astype(np.float32)
    edge = np.exp(-np.abs(idx - front) / 2.0)          # bright leading edge
    val_line = np.clip(0.85 + edge * 0.15 + beat * p['beat_react'] * 0.1, 0.0, 1.0)
    sat_line = p['saturation'] * (1.0 - edge * 0.7)
    if horizontal:
        hue = hue_line[None, :] * np.ones((H, 1), np.float32)
        val = val_line[None, :] * np.ones((H, 1), np.float32)
        sat = sat_line[None, :] * np.ones((H, 1), np.float32)
    else:
        hue = hue_line[:, None] * np.ones((1, W), np.float32)
        val = val_line[:, None] * np.ones((1, W), np.float32)
        sat = sat_line[:, None] * np.ones((1, W), np.float32)
    return _hsv_to_rgb(hue, sat, val)

def _algo_sparkle(H, W, p, t, beat, buf):
    if 'sparkle_grid' not in buf or buf['sparkle_grid'].shape != (H, W):
        buf['sparkle_grid'] = np.zeros((H, W), np.float32)
        buf['sparkle_hue'] = np.zeros((H, W), np.float32)
    g = buf['sparkle_grid']
    hue_g = buf['sparkle_hue']
    decay = 0.82 + (1.0 - p['speed']) * 0.15
    g *= decay
    base = p['hue']
    spread = p['color_spread']

    def _spawn(n):
        if n <= 0:
            return
        ys = np.random.randint(0, H, n)
        xs = np.random.randint(0, W, n)
        g[ys, xs] = 1.0
        hue_g[ys, xs] = (base + (np.random.rand(n) - 0.5) * spread) % 1.0

    _spawn(int(1 + p['rhythm_density'] * 8))
    if beat > 0.5:
        _spawn(int(5 + p['beat_react'] * 45))

    sat = p['saturation'] * (1.0 - g * 0.4)
    return _hsv_to_rgb(hue_g, sat, g)

def _algo_pinwheel(H, W, p, t, beat):
    cy, cx = (H - 1) / 2.0, (W - 1) / 2.0
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    ang = np.arctan2(yy - cy, xx - cx)
    arms = int(2 + round(p['symmetry'] * 8))
    dir_sign = 1.0 if p['direction'] >= 0.5 else -1.0
    speed = 0.3 + p['speed'] * 3.0
    rot = t * speed * dir_sign
    v = np.sin(ang * arms - rot) * 0.5 + 0.5
    k = 2.0 + p['contrast'] * 12.0            # sharpen into bold spokes
    val = np.clip((v - 0.5) * k + 0.5, 0.0, 1.0)
    val = np.clip(val + beat * p['beat_react'] * 0.3, 0.0, 1.0)
    hue = (p['hue'] + (ang / (2.0 * np.pi)) * p['color_spread']) % 1.0
    sat = np.full((H, W), p['saturation'], np.float32)
    return _hsv_to_rgb(hue.astype(np.float32), sat, val.astype(np.float32))

def _algo_scanner(H, W, p, t, beat, buf):
    if 'scanner_st' not in buf:
        buf['scanner_st'] = {'pos': 0.0, 'vel': 1.0, 'last_t': t}
    st = buf['scanner_st']
    dt = min(max(t - st['last_t'], 0.0), 0.1)
    st['last_t'] = t
    speed = 0.2 + p['speed'] * 2.0
    if beat and p['beat_react'] > 0.6:
        st['vel'] = -st['vel']
    st['pos'] += st['vel'] * speed * dt
    if st['pos'] >= 1.0:
        st['pos'] = 1.0
        st['vel'] = -abs(st['vel'])
    elif st['pos'] <= 0.0:
        st['pos'] = 0.0
        st['vel'] = abs(st['vel'])
    vertical = p['direction'] >= 0.5
    n = H if vertical else W
    axis = np.arange(n) / max(n - 1, 1)
    width = 0.03 + p['scale'] * 0.10
    tail_len = width * (2.0 + p['blur_glow'] * 8.0)
    d = axis - st['pos']
    head = np.exp(-(d / width) ** 2)
    behind = d * -np.sign(st['vel'])
    trail = np.where(behind > 0, np.exp(-behind / tail_len) * 0.7, 0.0)
    v = np.maximum(head, trail)
    if p['symmetry'] >= 0.5:
        v = np.maximum(v, v[::-1])
    if beat:
        v = np.clip(v * (1.0 + p['beat_react']), 0.0, 1.0)
    if vertical:
        v2 = np.tile(v[:, None], (1, W))
    else:
        v2 = np.tile(v[None, :], (H, 1))
    h2 = np.full((H, W), p['hue'] % 1.0)
    s2 = np.full((H, W), p['saturation'])
    return _hsv_to_rgb(h2, s2, v2)

def _algo_sparkle_v2(H, W, p, t, beat, buf):
    gh = max(2, int(4 + (1.0 - p['scale']) * 12))
    gw = max(2, gh * 2)
    if 'sparkle_st' not in buf or buf['sparkle_st']['val'].shape != (gh, gw):
        buf['sparkle_st'] = {'val': np.zeros((gh, gw)), 'hue': np.zeros((gh, gw))}
    st = buf['sparkle_st']
    decay = 0.80 + (1.0 - p['speed']) * 0.17
    st['val'] *= decay
    rate = p['rhythm_density'] * 0.05
    spawn = np.random.random((gh, gw)) < rate
    if beat:
        burst = 0.05 + p['beat_react'] * 0.30
        spawn |= np.random.random((gh, gw)) < burst
    n_new = int(spawn.sum())
    if n_new:
        spread = p['color_spread'] * 0.5
        st['hue'][spawn] = (p['hue']
                            + (np.random.random(n_new) - 0.5) * 2.0 * spread) % 1.0
        st['val'][spawn] = 1.0
    yi = (np.arange(H) * gh) // H
    xi = (np.arange(W) * gw) // W
    v = np.clip(st['val'][yi[:, None], xi[None, :]], 0.0, 1.0)
    v = v ** (0.5 + p['contrast'] * 1.5)
    h = st['hue'][yi[:, None], xi[None, :]]
    s = np.full((H, W), p['saturation'])
    return _hsv_to_rgb(h, s, v)

def _algo_wipe_v2(H, W, p, t, beat):
    speed = 0.15 + p['speed'] * 1.2
    phase = t * speed
    k = int(phase)
    prog = phase - k
    step = 0.12 + p['color_spread'] * 0.38
    hue_new = (p['hue'] + k * step) % 1.0
    hue_old = (p['hue'] + (k - 1) * step) % 1.0
    theta = p['direction'] * 2.0 * np.pi
    yy, xx = np.mgrid[0:H, 0:W]
    u = ((xx / max(W - 1, 1) - 0.5) * np.cos(theta)
         + (yy / max(H - 1, 1) - 0.5) * np.sin(theta))
    span = 0.5 * (abs(np.cos(theta)) + abs(np.sin(theta))) + 1e-6
    u = u / span * 0.5 + 0.5
    filled = u < prog
    old_v = 1.0 - p['contrast'] * 0.6
    v = np.where(filled, 1.0, old_v)
    soft = 0.02 + p['blur_glow'] * 0.10
    edge = np.exp(-((u - prog) / soft) ** 2)
    v = np.clip(v + edge * (0.3 + beat * p['beat_react']), 0.0, 1.0)
    h = np.where(filled, hue_new, hue_old)
    s = np.clip(p['saturation'] - edge * 0.8, 0.0, 1.0)
    return _hsv_to_rgb(h, s, v)

def _algo_bounce(H, W, p, t, beat, buf):
    if 'bounce_st' not in buf:
        ang = np.random.random() * 2.0 * np.pi
        buf['bounce_st'] = {'pos': np.array([0.5, 0.5]),
                            'dir': np.array([np.cos(ang), np.sin(ang)]),
                            'last_t': t, 'flash': 0.0}
    st = buf['bounce_st']
    dt = min(max(t - st['last_t'], 0.0), 0.1)
    st['last_t'] = t
    speed = 0.10 + p['speed'] * 0.8
    st['pos'] += st['dir'] * speed * dt
    r = 0.08 + p['scale'] * 0.20
    for i in (0, 1):
        if st['pos'][i] < r:
            st['pos'][i] = r
            st['dir'][i] = abs(st['dir'][i])
        elif st['pos'][i] > 1.0 - r:
            st['pos'][i] = 1.0 - r
            st['dir'][i] = -abs(st['dir'][i])
    st['flash'] *= 0.85
    if beat:
        st['flash'] = p['beat_react']
    rr = r * (1.0 + st['flash'] * 0.6)
    yy, xx = np.mgrid[0:H, 0:W]
    x = xx / max(W - 1, 1)
    y = yy / max(H - 1, 1)
    d = np.sqrt((x - st['pos'][0]) ** 2 + (y - st['pos'][1]) ** 2)
    edge = 0.02 + p['blur_glow'] * rr
    v = np.clip(1.0 - (d - rr) / edge, 0.0, 1.0)
    if p['symmetry'] >= 0.5:
        v = np.maximum(v, v[:, ::-1])
    v = np.clip(v * (0.85 + st['flash'] * 0.5), 0.0, 1.0)
    hue = (p['hue'] + st['pos'][0] * p['color_spread'] * 0.5) % 1.0
    h = np.full((H, W), hue)
    s = np.full((H, W), p['saturation'])
    return _hsv_to_rgb(h, s, v)

def _algo_checker(H, W, p, t, beat, buf):
    if 'checker_st' not in buf:
        buf['checker_st'] = {'phase': 0, 'level': 1.0, 'last_t': t, 'last_flip': t}
    st = buf['checker_st']
    dt = min(max(t - st['last_t'], 0.0), 0.1)
    st['last_t'] = t
    interval = 1.0 / (0.5 + p['speed'] * 3.0)
    flip = False
    if beat and p['beat_react'] >= 0.3:
        flip = True
    elif p['beat_react'] < 0.3 and (t - st['last_flip']) >= interval:
        flip = True
    if flip:
        st['phase'] ^= 1
        st['level'] = 1.0
        st['last_flip'] = t
    else:
        fade = 0.3 + p['speed'] * 1.5
        st['level'] = max(st['level'] - fade * dt, 0.30)
    ny = max(1, int(round(2 + (1.0 - p['scale']) * 5)))
    nx = max(1, int(round(ny * W / max(H, 1))))
    yy, xx = np.mgrid[0:H, 0:W]
    scroll = int(t * (2.0 + p['speed'] * 10.0)) if p['direction'] >= 0.5 else 0
    cell = (((xx + scroll) * nx) // W + (yy * ny) // H) % 2
    lit = cell == st['phase']
    contrast = p['contrast']
    v = np.where(lit, st['level'], st['level'] * (1.0 - contrast) * 0.5)
    hue = p['hue']
    h = np.where(lit, hue % 1.0, (hue + 0.5 * p['color_spread']) % 1.0)
    s = np.full((H, W), p['saturation'])
    return _hsv_to_rgb(h, s, v)

_ALGOS = [_algo_plasma, _algo_fire, _algo_noise, _algo_bars, _algo_radial, _algo_stars,
          _algo_comet, _algo_chase, _algo_wipe, _algo_sparkle, _algo_pinwheel,
          _algo_scanner, _algo_sparkle_v2, _algo_wipe_v2, _algo_bounce, _algo_checker]

_STATEFUL_ALGOS = (_algo_fire, _algo_stars, _algo_sparkle, _algo_scanner,
                    _algo_sparkle_v2, _algo_bounce, _algo_checker)

def _build_params(faders: list[float]) -> dict:
    return {
        'beat_react':     faders[1],
        'rhythm_density': faders[2],
        'speed':          faders[3],
        'hue':            faders[4],
        'saturation':     faders[5],
        'color_spread':   faders[6],
        'scale':          faders[7],
        'direction':      faders[8],
        'symmetry':       faders[9],
        'contrast':       faders[10],
        'blur_glow':      faders[11],
    }

class Generator:
    def __init__(self):
        self._buf: dict = {}

    def algo_count(self) -> int:
        return len(_ALGOS)

    def render_index(self, idx: int, H: int, W: int, faders: list[float],
                      t: float, beat: float, buf: dict) -> np.ndarray:
        p = _build_params(faders)
        algo = _ALGOS[idx]
        if algo in _STATEFUL_ALGOS:
            frame = algo(H, W, p, t, beat, buf)
        else:
            frame = algo(H, W, p, t, beat)
        frame = _apply_symmetry(frame, p['symmetry'])
        frame = _apply_blur(frame, p['blur_glow'])
        return frame

    def render(self, H: int, W: int, faders: list[float], t: float, beat: float) -> np.ndarray:
        algo_idx = min(int(faders[0] * len(_ALGOS)), len(_ALGOS) - 1)
        return self.render_index(algo_idx, H, W, faders, t, beat, self._buf)
