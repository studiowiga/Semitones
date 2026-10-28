"""Physically based render of the four socket-head cap screws (light from the left).

The screws of the design picture were lit from the right. They are erased from
the plate and replaced by a rendered model, lit like the rest of the relit pedal:

  * geometry: cylindrical head with a rounded top edge, very slightly domed
    turned face, hexagon socket with a conical entry and a drill-point bottom
  * material: stainless steel, GGX specular + small diffuse, Schlick Fresnel,
    concentric turning marks on the face (micro normal perturbation)
  * lighting: key soft-box from the left / slightly above, weak fill from the
    upper right, studio environment for reflections
  * soft cast shadow on the plate (ray marched in the height field, area light),
    contact ambient occlusion, occlusion inside the socket
  * rendered 3x supersampled, then box-filtered (anti-aliasing)
"""
import numpy as np
import cv2


def _norm(v):
    v = np.asarray(v, np.float64)
    return v / np.linalg.norm(v)


L_KEY = _norm([-0.80, -0.30, 0.52])     # from the left, slightly above (screen y is down)
L_FILL = _norm([0.55, -0.55, 0.62])
VIEW = np.array([0.0, 0.0, 1.0])


def _heightfield(n, R, ss, rot):
    """Height field (pixels) of one screw, centred in an n x n grid; R = head radius in px."""
    c = (n - 1) / 2.0
    yy, xx = np.mgrid[0:n, 0:n].astype(np.float64)
    x, y = xx - c, yy - c
    r = np.sqrt(x * x + y * y)
    Hh = 0.42 * R                    # head height
    fil = 0.11 * R                   # top edge fillet radius
    dome = 0.025 * R
    h = np.zeros((n, n))
    head = r <= R
    top = Hh + dome * (1 - (r / R) ** 2)
    edge = r > (R - fil)
    t = np.clip((r - (R - fil)) / fil, 0, 1)
    drop = fil * (1 - np.sqrt(np.clip(1 - t * t, 0, 1)))
    h = np.where(head, top - np.where(edge, drop, 0), 0.0)
    # hexagon socket
    af = 0.86 * R                    # across flats
    ang = np.arctan2(y, x) - rot
    sector = np.mod(ang + np.pi / 6, np.pi / 3) - np.pi / 6
    hexd = r * np.cos(sector)        # distance to the nearest flat direction
    inside = hexd <= af / 2
    entry = (r <= af / 2 * 1.16) & ~inside                       # conical entry chamfer
    depth = 0.60 * R
    cone = np.clip(1 - r / (af / 2), 0, 1) * 0.10 * R           # drill point bottom
    sock = top - depth - cone
    h = np.where(inside & head, sock, h)
    ch = np.clip((af / 2 * 1.16 - r) / (af / 2 * 0.16), 0, 1)
    h = np.where(entry & head, top - ch * 0.22 * R, h)
    region = np.where(inside & head, 2, np.where(entry & head, 3, np.where(head, np.where(edge, 1, 0), -1)))
    return h, r, region, Hh


def _ggx(n, l, v, alpha):
    hv = l + v
    hv = hv / np.linalg.norm(hv, axis=-1, keepdims=True)
    nh = np.clip((n * hv).sum(-1), 0, 1)
    nl = np.clip((n * l).sum(-1), 0, 1)
    nv = np.clip((n * v).sum(-1), 1e-3, 1)
    a2 = alpha * alpha
    d = a2 / (np.pi * (nh * nh * (a2 - 1) + 1) ** 2)
    k = alpha / 2
    g = (nl / (nl * (1 - k) + k)) * (nv / (nv * (1 - k) + k))
    return d * g / np.maximum(4 * nl * nv, 1e-4) * nl, nl


def _env(rv):
    """Studio environment seen in reflections: soft box on the left, dark floor."""
    box = np.exp(-(1 - np.clip((rv * L_KEY).sum(-1), -1, 1)) / 0.10) * 2.4
    fill = np.exp(-(1 - np.clip((rv * L_FILL).sum(-1), -1, 1)) / 0.18) * 0.35
    sky = 0.035 + 0.10 * np.clip(rv[..., 2], 0, 1) ** 3
    floor = 0.02
    return np.where(rv[..., 2] > -0.1, sky + box + fill, floor)


def render(canvas, cx, cy, R, seed=0, exposure=1.0):
    """Render one screw into canvas (float RGB, sRGB) at (cx, cy) with head radius R (px)."""
    rng = np.random.default_rng(seed)
    ss = 3
    half = int(np.ceil(R * 2.1))
    x0, y0 = int(round(cx)) - half, int(round(cy)) - half
    n = 2 * half
    N = n * ss
    rot = rng.uniform(0, np.pi / 3)
    # supersampled geometry (coordinates in output pixels * ss)
    h, r, region, Hh = _heightfield(N, R * ss, ss, rot)
    off = (cx - (x0 + half)) * ss, (cy - (y0 + half)) * ss
    M = np.float32([[1, 0, off[0]], [0, 1, off[1]]])
    h = cv2.warpAffine(h.astype(np.float32), M, (N, N), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT)
    region = cv2.warpAffine(region.astype(np.float32), M, (N, N), flags=cv2.INTER_NEAREST, borderValue=-1)
    r = cv2.warpAffine(r.astype(np.float32), M, (N, N), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)
    gy, gx = np.gradient(h.astype(np.float64))
    nrm = np.dstack([-gx, -gy, np.ones_like(gx)])
    # concentric turning marks on the face, fine radial grain elsewhere
    cxs, cys = (N - 1) / 2 + off[0], (N - 1) / 2 + off[1]
    yy, xx = np.mgrid[0:N, 0:N].astype(np.float64)
    dx, dy = xx - cxs, yy - cys
    rr = np.sqrt(dx * dx + dy * dy) + 1e-6
    turn = (np.sin(rr * 1.9) * 0.05 + np.sin(rr * 0.73 + 1.3) * 0.03 + np.sin(rr * 4.1) * 0.02) * (region == 0)
    grain = cv2.GaussianBlur(rng.normal(0, 1, (N, N)), (0, 0), 0.8) * 0.02
    nrm[..., 0] += (dx / rr) * turn + grain * (region >= 0)
    nrm[..., 1] += (dy / rr) * turn + cv2.GaussianBlur(rng.normal(0, 1, (N, N)), (0, 0), 0.8) * 0.02 * (region >= 0)
    nrm /= np.linalg.norm(nrm, axis=-1, keepdims=True)

    v = np.broadcast_to(VIEW, nrm.shape)
    rough = np.select([region == 0, region == 1, region == 2, region == 3], [0.30, 0.14, 0.45, 0.20], 0.3)
    spec_k, nl_k = _ggx(nrm, np.broadcast_to(L_KEY, nrm.shape), v, rough)
    spec_f, nl_f = _ggx(nrm, np.broadcast_to(L_FILL, nrm.shape), v, rough)
    rv = 2 * nrm[..., 2:3] * nrm - v                       # reflection of the view ray
    F0 = 0.60
    fres = F0 + (1 - F0) * (1 - np.clip(nrm[..., 2], 0, 1)) ** 5
    env = _env(rv) * (0.35 + 0.65 * (1 - rough))           # rough metal blurs the environment
    # occlusion: socket interior gets little light, chamfer partly
    depth_rel = np.clip((Hh * ss - h) / (0.6 * R * ss), 0, 1)
    occ = np.where(region == 2, 0.05 + 0.30 * (1 - depth_rel) ** 3, np.where(region == 3, 0.80, 1.0))
    # self shadow of the socket walls (key light)
    sh_self = np.ones((N, N))
    Lxy = np.array([L_KEY[0], L_KEY[1]]); Lxy_n = Lxy / np.linalg.norm(Lxy)
    slope = L_KEY[2] / np.linalg.norm(Lxy)
    hmap = h.astype(np.float32)
    for t in np.linspace(1.0, 0.7 * R * ss, 18):
        mx = (xx + Lxy_n[0] * t).astype(np.float32); my = (yy + Lxy_n[1] * t).astype(np.float32)
        hs = cv2.remap(hmap, mx, my, cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT, borderValue=0)
        sh_self = np.minimum(sh_self, np.clip(1 - (hs - (h + t * slope)) / (0.06 * R * ss), 0, 1))
    key = 2.4
    # turned face: anisotropic "bow-tie" highlight along the radius pointing to the light
    radx, rady = dx / rr, dy / rr
    cosr = np.abs(radx * Lxy_n[0] + rady * Lxy_n[1])
    aniso = (np.exp(-(1 - cosr) / 0.012) * 1.3 + np.exp(-(1 - cosr) / 0.06) * 0.35 + np.exp(-(1 - cosr) / 0.3) * 0.08) * (region == 0)
    aniso *= np.clip(rr / (0.35 * R * ss), 0, 1) * np.clip((0.88 * R * ss - rr) / (0.1 * R * ss), 0, 1)
    side = np.where(radx * Lxy_n[0] + rady * Lxy_n[1] > 0, 1.0, 0.45)       # stronger on the lit side
    # micro scratches and slight tarnish on the face
    scr = np.zeros((N, N))
    for _ in range(14):
        a0 = rng.uniform(0, np.pi); px_, py_ = rng.uniform(0, N, 2); ln = rng.uniform(0.2, 0.6) * R * ss
        d_ = np.abs((xx - px_) * np.sin(a0) - (yy - py_) * np.cos(a0))
        along = np.abs((xx - px_) * np.cos(a0) + (yy - py_) * np.sin(a0))
        scr = np.maximum(scr, np.clip(1 - d_ / 0.9, 0, 1) * np.clip(1 - along / ln, 0, 1) * rng.uniform(0.3, 1))
    scr *= (region == 0)
    tarn = 1 - 0.10 * cv2.GaussianBlur(rng.random((N, N)), (0, 0), 6 * ss) * (region >= 0)
    lin = (fres * (spec_k * key * sh_self + spec_f * 0.5) + fres * env * occ
           + 0.03 * (nl_k * key * sh_self + nl_f * 0.4) * occ
           + aniso * side * key * 0.22 * sh_self + scr * 0.06) * tarn
    tint = np.array([0.95, 0.97, 1.02])
    lin = lin[..., None] * tint * exposure          # light received at this spot of the pedal
    srgb = np.where(lin <= 0.0031308, lin * 12.92, 1.055 * np.power(np.clip(lin, 0, None), 1 / 2.4) - 0.055)
    srgb = np.clip(srgb * 0.80, 0, 1)
    alpha = (region >= 0).astype(np.float64)
    # box filter down to output resolution
    def down(a):
        return cv2.resize(a, (n, n), interpolation=cv2.INTER_AREA)
    col = np.dstack([down((srgb[..., i] * alpha)) for i in range(3)])
    a_ = down(alpha)
    col = col / np.maximum(a_[..., None], 1e-4)

    # cast shadow + contact occlusion on the plate (output resolution)
    hd = down(h.astype(np.float64)).astype(np.float32)
    yy1, xx1 = np.mgrid[0:n, 0:n].astype(np.float32)
    vis = np.zeros((n, n), np.float32)
    dirs = []
    for k in range(7):                          # area light: jittered directions
        a = np.deg2rad(rng.uniform(-9, 9)); e = rng.uniform(-0.06, 0.06)
        lx = Lxy_n[0] * np.cos(a) - Lxy_n[1] * np.sin(a); ly = Lxy_n[0] * np.sin(a) + Lxy_n[1] * np.cos(a)
        dirs.append((lx, ly, slope * (1 + e)))
    for lx, ly, sl in dirs:
        occl = np.zeros((n, n), np.float32)
        for t in np.linspace(0.6, 2.2 * R, 40):
            hs = cv2.remap(hd, (xx1 + lx * t).astype(np.float32), (yy1 + ly * t).astype(np.float32), cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT, borderValue=0)
            occl = np.maximum(occl, np.clip((hs - (hd + t * sl)) / (0.05 * R), 0, 1))
        vis += 1 - occl
    vis /= len(dirs)
    vis = cv2.GaussianBlur(vis, (0, 0), 1.6)
    dist = np.sqrt((xx1 - (cx - x0)) ** 2 + (yy1 - (cy - y0)) ** 2)
    ao = 1 - 0.60 * np.exp(-np.clip(dist - R, 0, None) / (0.10 * R)) * (dist > R - 1)
    plate_mul = (0.50 + 0.50 * vis) * ao

    reg = canvas[y0:y0 + n, x0:x0 + n]
    out = reg * plate_mul[..., None]
    out = out * (1 - a_[..., None]) + col * a_[..., None]
    canvas[y0:y0 + n, x0:x0 + n] = np.clip(out, 0, 1)
    return canvas


def _membrane(target, known, iters=500):
    """Harmonic interpolation of target where known == 0 (Jacobi iterations)."""
    out = target.copy()
    unk = known == 0
    if unk.any():
        out[unk] = target[~unk].mean(0) if (~unk).any() else 0
    for _ in range(iters):
        out = np.where(unk[..., None], cv2.blur(out, (3, 3)), target)
    return out


def erase(img, cx, cy, r, mode='from_below', plate=None, channel=None):
    """Remove a screw (and its shadow) from the source picture (float RGB).

    * brushing is vertical: the hole is refilled with the plate rows just beyond
      it, reflected (below for the top screws, above for the bottom ones);
    * the brightness is then levelled to the surroundings with a harmonic
      (seamless) correction computed only from plate pixels;
    * the hole never touches the plate edges / bevels (plate box, inset);
    * channel=(x0, y0, slope, above, below): a straight groove that ran under the
      screw is extended through the hole, up to the plate edge.
    """
    H, W = img.shape[:2]
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    d = np.sqrt((xx - cx) ** 2 + (yy - cy) ** 2)
    inset = 4.0
    if plate is not None:
        px0, py0, px1, py1 = plate
        inner = ((xx > px0 + inset) & (xx < px1 - inset) & (yy > py0 + inset) & (yy < py1 - inset))
    else:
        inner = np.ones((H, W), bool)
    hole = (d <= r) & inner
    band = np.zeros((H, W), bool)
    if channel is not None:
        lx0, ly0, slope, above, below = channel
        u = np.array([1.0, slope]); u /= np.linalg.norm(u)
        nrm_ = np.array([-u[1], u[0]])                        # points below the line
        perp = (xx - lx0) * nrm_[0] + (yy - ly0) * nrm_[1]
        along = (xx - cx) * u[0] + (yy - cy) * u[1]
        band = (perp > -above) & (perp < below) & (along > -r - 2) & inner
        hole = hole | band
    ys_, xs_ = np.nonzero(hole)
    y0, y1 = ys_.min(), ys_.max() + 1
    x0, x1 = xs_.min(), xs_.max() + 1
    fill = img.copy()
    rows = np.arange(y0, y1)
    skip = 16                      # skip the rows right next to the hole (old shadow tails)
    if mode == 'from_below':
        src = np.clip(2 * (y1 + skip) - rows, 0, H - 1)
        fill[y0:y1, x0:x1] = img[src][:, x0:x1]
    elif mode == 'from_above':
        src = np.clip(2 * (y0 - skip) - rows, 0, H - 1)
        fill[y0:y1, x0:x1] = img[src][:, x0:x1]
    else:                          # ('patch', sx0, sy0, sx1, sy1): tile a clean plate patch
        _, sx0, sy0, sx1, sy1 = mode
        pt = img[int(sy0):int(sy1), int(sx0):int(sx1)]
        reps = (int(np.ceil((y1 - y0) / pt.shape[0])) + 1, int(np.ceil((x1 - x0) / pt.shape[1])) + 1, 1)
        fill[y0:y1, x0:x1] = np.tile(pt, reps)[:y1 - y0, :x1 - x0]
    if channel is not None:
        # extrude the groove along its own direction from the upstream side
        pc = np.stack([xx - cx, yy - cy], -1)
        a_ = pc[..., 0] * u[0] + pc[..., 1] * u[1]
        q = np.clip(r * r - (pc[..., 0] ** 2 + pc[..., 1] ** 2 - a_ ** 2), 0, None)
        t = a_ + np.sqrt(q) + 8.0           # start a little beyond the hole (old glare)
        mx = (xx - t * u[0]).astype(np.float32); my = (yy - t * u[1]).astype(np.float32)
        ext = cv2.remap(img.astype(np.float32), mx, my, cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)
        bsoft = cv2.GaussianBlur(band.astype(np.float32), (0, 0), 1.2)
        fill = fill * (1 - bsoft[..., None]) + ext * bsoft[..., None]
    # seamless brightness: harmonic correction from the plate pixels around the hole
    pad = 20
    bx0, by0, bx1, by1 = max(0, x0 - pad), max(0, y0 - pad), min(W, x1 + pad), min(H, y1 + pad)
    sub_img = cv2.GaussianBlur(img[by0:by1, bx0:bx1], (0, 0), 3.0)
    sub_fill = cv2.GaussianBlur(fill[by0:by1, bx0:bx1], (0, 0), 3.0)
    hsub = hole[by0:by1, bx0:bx1].astype(np.uint8)
    known = (~hole[by0:by1, bx0:bx1]) & inner[by0:by1, bx0:bx1]
    ring = (cv2.dilate(hsub, np.ones((25, 25), np.uint8)) > 0) & ~(cv2.dilate(hsub, np.ones((9, 9), np.uint8)) > 0) & known
    diff = np.where(ring[..., None], sub_img - sub_fill, 0).astype(np.float32)
    corr = _membrane(diff, ring.astype(np.uint8))
    if channel is not None:
        corr *= (1 - cv2.GaussianBlur(band[by0:by1, bx0:bx1].astype(np.float32), (0, 0), 2.0))[..., None]
    fill[by0:by1, bx0:bx1] += corr * hole[by0:by1, bx0:bx1][..., None]
    m = cv2.GaussianBlur(hole.astype(np.float32), (0, 0), 1.5) * inner
    return img * (1 - m[..., None]) + fill * m[..., None]
