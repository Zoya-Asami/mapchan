#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
mapchan.py
GPX 轨迹 → 多种地图投影 → SVG + PNG → ZIP

v1.0 内置：
  1. Web 墨卡托 (Web Mercator / EPSG:3857)
  2. 等距圆柱 (Equirectangular / Plate Carrée)
  3. 中国 1963 等差分纬线多圆锥投影
  4. 双标准纬线等积圆锥投影（中国）

仅使用 Python 标准库。
"""

from __future__ import annotations

import argparse
import math
import os
import struct
import sys
import tempfile
import zlib
import zipfile
import xml.etree.ElementTree as ET


# ============================================================
# GPX
# ============================================================

def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def parse_gpx(path: str):
    root = ET.parse(path).getroot()
    tracks = []

    for seg in root.iter():
        if _local(seg.tag) != "trkseg":
            continue

        pts = []
        for p in seg:
            if _local(p.tag) != "trkpt":
                continue
            lat = p.get("lat")
            lon = p.get("lon")
            if lat is not None and lon is not None:
                pts.append((float(lat), float(lon)))

        if pts:
            tracks.append(pts)

    if not tracks:
        raise ValueError("GPX 中没有找到有效的 trkseg / trkpt。")

    return tracks


# ============================================================
# 投影
# ============================================================

class Projection:
    name = "Unknown"
    slug = "unknown"

    def forward(self, lat: float, lon: float):
        """纬度、经度（度）→ 投影平面 x、y。"""
        raise NotImplementedError


class WebMercator(Projection):
    name = "Web 墨卡托 (EPSG:3857)"
    slug = "webmercator"

    # Web Mercator 的有效纬度范围
    MAX_LAT = 85.0511287798066

    def forward(self, lat: float, lon: float):
        lat = max(-self.MAX_LAT, min(self.MAX_LAT, lat))
        lam = math.radians(lon)
        phi = math.radians(lat)

        x = lam
        y = math.log(math.tan(math.pi / 4.0 + phi / 2.0))
        return x, y


class Equirectangular(Projection):
    name = "等距圆柱"
    slug = "equirectangular"

    def forward(self, lat: float, lon: float):
        # 单位球上的等距圆柱（Plate Carrée）：
        # x = λ, y = φ
        return math.radians(lon), math.radians(lat)

class AlbersChina(Projection):
    """Albers Equal Area Conic，中华人民共和国全国地图常用参数。

    中央经线：110°E
    标准纬线：25°N、47°N
    """

    name = "双标准纬线等积圆锥（中国）"
    slug = "albers_china"

    CENTRAL_MERIDIAN = math.radians(110.0)
    STANDARD_PARALLEL_1 = math.radians(25.0)
    STANDARD_PARALLEL_2 = math.radians(47.0)

    def __init__(self):
        phi1 = self.STANDARD_PARALLEL_1
        phi2 = self.STANDARD_PARALLEL_2

        self.n = 0.5 * (math.sin(phi1) + math.sin(phi2))
        self.C = (
            math.cos(phi1) ** 2
            + 2.0 * self.n * math.sin(phi1)
        )
        self.rho0 = self._rho(0.0)

    def _rho(self, phi):
        value = self.C - 2.0 * self.n * math.sin(phi)
        if value < 0:
            raise ValueError("Latitude is outside the valid range of the Albers projection.")
        return math.sqrt(value) / self.n

    def forward(self, lat, lon):
        phi = math.radians(lat)
        lam = math.radians(lon)

        theta = self.n * (lam - self.CENTRAL_MERIDIAN)
        rho = self._rho(phi)

        x = rho * math.sin(theta)
        y = self.rho0 - rho * math.cos(theta)

        return x, y


# ---- 中国 1963 等差分纬线多圆锥投影 ----
#
# 1963 方案的样条函数和投影常数参考：
# fanfanpa/Latitudinally-Equal-Differential-Polyconic-Projection
# 该项目 README 标明其投影实现参考 Ishisashi 的 D3 实现。
#
# 这里不依赖该项目或任何第三方 Python 包；只保留投影所需的
# 标准库 math 实现。
#
# 1963 方案通常以东经 150°为中央经线；因此这里先把经度
# 转换为相对于 150°E 的经差，再代入投影公式。


def _yn_spline_1963(phi: float) -> float:
    sgn = 1.0 if phi >= 0.0 else -1.0
    a = abs(phi)

    if a < 0.17453292519943295:       # 10°
        return 1.5271229924920866 * phi - 1.0100872528750704 * phi**3
    elif a < 0.26179938779914946:    # 15°
        return (
            -sgn * 0.030891469712581106
            + 2.0581082437382188 * phi
            - sgn * 3.0423213880097015 * phi**2
            + 4.80031859563621 * phi**3
        )
    elif a < 0.3490658503988659:     # 20°
        return (
            sgn * 0.1709495921326784
            - 0.25481995149626163 * phi
            + sgn * 5.792413538906713 * phi**2
            - 6.448415280566685 * phi**3
        )
    elif a < 0.41015237421866746:
        return (
            -sgn * 0.28946654896159746
            + 3.702165304164013 * phi
            - sgn * 5.543514198334726 * phi**2
            + 4.376598322920309 * phi**3
        )
    elif a < 0.5235987755982989:      # 30°
        return (
            sgn * 0.05307970360138684
            + 1.1966604667323502 * phi
            + sgn * 0.5652029393012619 * phi**2
            - 0.5879933114879028 * phi**3
        )
    elif a < 0.6981317007977318:      # 40°
        return (
            -sgn * 0.040699882295465985
            + 1.7339779143697747 * phi
            - sgn * 0.4609977943109389 * phi**2
            + 0.06530636594774145 * phi**3
        )
    elif a < 0.7853981633974483:      # 45°
        return (
            -sgn * 0.04647955512903578
            + 1.758814228894522 * phi
            - sgn * 0.49657319433412633 * phi**2
            + 0.08229236824622688 * phi**3
        )
    elif a < 0.8726646259971648:      # 50°
        return (
            sgn * 0.1627992073626043
            + 0.95942824006174 * phi
            + sgn * 0.5212366581549931 * phi**2
            - 0.3496795494905096 * phi**3
        )
    elif a < 1.0471975511965979:      # 60°
        return (
            -sgn * 0.4934162518439651
            + 3.21533081588828 * phi
            - sgn * 2.063837273596045 * phi**2
            + 0.637745957300319 * phi**3
        )
    elif a < 1.160643952576229:
        return (
            sgn * 2.6323996710067004
            - 5.739472179818403 * phi
            + sgn * 6.487369693488941 * phi**2
            - 2.0841877591265408 * phi**3
        )
    elif a < 1.2217304763960306:
        return (
            -sgn * 0.06331771971040438
            + 1.228342673479739 * phi
            + sgn * 0.4839654299919428 * phi**2
            - 0.36002872649885964 * phi**3
        )
    elif a < 1.3089969389957472:      # 75°
        return (
            -sgn * 3.0290030290957928
            + 8.510682027411134 * phi
            - sgn * 5.4767104266122795 * phi**2
            + 1.2662644622104196 * phi**3
        )
    elif a < 1.3962634015954636:      # 80°
        return (
            -sgn * 2.455207302687121
            + 7.195639090376726 * phi
            - sgn * 4.472091624338152 * phi**2
            + 1.0104403849224408 * phi**3
        )
    else:
        return (
            -sgn * 0.9501716941205609
            + 3.9619320258354533 * phi
            - sgn * 2.156119537089983 * phi**2
            + 0.45754277629984 * phi**3
        )


def _xn_spline_1963(phi: float) -> float:
    a = abs(phi)

    if a < 0.17453292519943295:       # 10°
        return 2.589813150474736 - 0.8852514776808 * a**2 + 0.2156744452624301 * a**3
    elif a < 0.26179938779914946:    # 15°
        return (
            2.5888006039905727
            + 0.01740439203101801 * a
            - 0.9849712985176455 * a**2
            + 0.4061252741874958 * a**3
        )
    elif a < 0.3490658503988659:     # 20°
        return (
            2.586566421877108
            + 0.043006233184045874 * a
            - 1.082763128239835 * a**2
            + 0.5306376989417948 * a**3
        )
    elif a < 0.41015237421866746:
        return (
            2.591710444836326
            - 0.0012033876081931026 * a
            - 0.9561118939763797 * a**2
            + 0.4096946790514837 * a**3
        )
    elif a < 0.5235987755982989:      # 30°
        return (
            2.59129428902019
            + 0.0018405236962004488 * a
            - 0.9635333097616526 * a**2
            + 0.41572610887429085 * a**3
        )
    elif a < 0.6981317007977318:      # 40°
        return (
            2.6488583874553955
            - 0.3279774654850895 * a
            - 0.333627350175674 * a**2
            + 0.014715520269682264 * a**3
        )
    elif a < 0.7853981633974483:      # 45°
        return (
            2.7684001717397826
            - 0.8416704441069918 * a
            + 0.40218364083780167 * a**2
            - 0.33660834893374025 * a**3
        )
    elif a < 0.8726646259971648:      # 50°
        return (
            3.0046791444742453
            - 1.74418963913175 * a
            + 1.5513067698258702 * a**2
            - 0.8243113521328783 * a**3
        )
    elif a < 1.0471975511965979:      # 60°
        return (
            2.4264910216094973
            + 0.24347471315274363 * a
            - 0.7263887996642484 * a**2
            + 0.04570426884999046 * a**3
        )
    elif a < 1.160643952576229:
        return (
            0.32726032286130863
            + 6.257327676281242 * a
            - 6.469195356322702 * a**2
            + 1.8736963702754696 * a**3
        )
    elif a < 1.2217304763960306:
        return (
            5.713126712541212
            - 7.663909007178327 * a
            + 5.525212232676679 * a**2
            - 1.5710601966665094 * a**3
        )
    elif a < 1.3089969389957472:      # 75°
        return (
            -2.20484561744157
            + 11.778936570366538 * a
            - 10.388973342594724 * a**2
            + 2.77091918593635 * a**3
        )
    elif a < 1.3962634015954636:      # 80°
        return (
            16.061152339503188
            - 30.08364709073422 * a
            + 21.59168483466383 * a**2
            - 5.3728885456523585 * a**3
        )
    else:
        return (
            -3.317160382002574
            + 11.55243539777649 * a
            - 8.22796269096389 * a**2
            + 1.7460279117901278 * a**3
        )


class Chinese1963(Projection):
    name = "中国 1963 等差分纬线多圆锥投影"
    slug = "chinese1963"

    CENTRAL_MERIDIAN = 150.0

    def forward(self, lat: float, lon: float):
        # 1963 方案以东经 150°为中央经线。
        lam = math.radians(lon - self.CENTRAL_MERIDIAN)
        phi = math.radians(lat)

        b = 1.1
        C = 0.028937262380344605
        lambda_n = math.pi

        y0 = 0.9953537 * phi + 0.01476138 * phi**3
        yn = _yn_spline_1963(phi)
        xn = _xn_spline_1963(phi)

        if phi == 0.0:
            x = xn * b * (1.0 - C * abs(lam)) * lam / lambda_n
            y = 0.0
            return x, y

        dy = yn - y0

        # 在极端数值情况下避免除零；正常地理范围不会触发。
        if abs(dy) < 1e-15:
            x = xn * b * (1.0 - C * abs(lam)) * lam / lambda_n
            return x, y0

        rho = (xn * xn + dy * dy) / (2.0 * dy)

        arg = xn / rho
        arg = max(-1.0, min(1.0, arg))
        delta_phi_n = math.asin(arg)

        delta_phi = (
            delta_phi_n
            * b
            * (1.0 - C * abs(lam))
            * lam
            / lambda_n
        )

        y = y0 + rho * (1.0 - math.cos(delta_phi))
        x = rho * math.sin(delta_phi)

        return x, y


PROJECTIONS = [
    WebMercator(),
    Equirectangular(),
    Chinese1963(),
    AlbersChina(),
]


# ============================================================
# 投影后的轨迹 → 画布坐标
# ============================================================

def project_tracks(tracks, projection, width, height, margin):
    projected = []

    for track in tracks:
        pts = []
        for lat, lon in track:
            x, y = projection.forward(lat, lon)
            if math.isfinite(x) and math.isfinite(y):
                pts.append((x, y))
        if pts:
            projected.append(pts)

    if not projected:
        raise ValueError("投影后没有有效坐标。")

    all_x = [x for t in projected for x, _ in t]
    all_y = [y for t in projected for _, y in t]

    xmin, xmax = min(all_x), max(all_x)
    ymin, ymax = min(all_y), max(all_y)

    avail_w = width - 2 * margin
    avail_h = height - 2 * margin

    if avail_w <= 0 or avail_h <= 0:
        raise ValueError("画布尺寸必须大于两倍 margin。")

    dx = xmax - xmin
    dy = ymax - ymin

    # 单点 / 单纬线 / 单经线轨迹也能正常输出。
    if dx == 0.0:
        dx = 1.0
    if dy == 0.0:
        dy = 1.0

    scale = min(avail_w / dx, avail_h / dy)

    used_w = dx * scale
    used_h = dy * scale
    offset_x = (width - used_w) / 2.0
    offset_y = (height - used_h) / 2.0

    out = []
    for track in projected:
        xs = [offset_x + (x - xmin) * scale for x, _ in track]
        ys = [offset_y + (ymax - y) * scale for _, y in track]
        out.append((xs, ys))

    info = {
        "scale": scale,
        "x_range": (xmin, xmax),
        "y_range": (ymin, ymax),
    }
    return out, info


# ============================================================
# SVG
# ============================================================

def build_svg(xy, width, height, stroke, stroke_width, stroke_opacity):
    parts = []

    for xs, ys in xy:
        if not xs:
            continue

        d = "M {:.3f} {:.3f}".format(xs[0], ys[0])
        d += "".join(
            "L {:.3f} {:.3f}".format(x, y)
            for x, y in zip(xs[1:], ys[1:])
        )

        parts.append(
            '<path d="{}" fill="none" stroke="{}" stroke-width="{}" '
            'stroke-opacity="{}" stroke-linecap="round" '
            'stroke-linejoin="round"/>'
            .format(d, stroke, stroke_width, stroke_opacity)
        )

    body = "\n  ".join(parts)

    return (
        '<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" '
        'viewBox="0 0 {w} {h}">\n'
        '  <rect width="{w}" height="{h}" fill="#ffffff"/>\n'
        '  {body}\n'
        '</svg>\n'
    ).format(w=width, h=height, body=body)


# ============================================================
# 极简 PNG 光栅化
# ============================================================

def _draw_segment(buf, w, h, x0, y0, x1, y1, lo, hi):
    dx = abs(x1 - x0)
    sx = 1 if x0 < x1 else -1
    dy = -abs(y1 - y0)
    sy = 1 if y0 < y1 else -1
    err = dx + dy

    while True:
        for yy in range(y0 - lo, y0 + hi + 1):
            if yy < 0 or yy >= h:
                continue

            row = yy * w
            for xx in range(x0 - lo, x0 + hi + 1):
                if 0 <= xx < w:
                    buf[row + xx] = 0

        if x0 == x1 and y0 == y1:
            break

        e2 = 2 * err
        if e2 >= dy:
            err += dy
            x0 += sx
        if e2 <= dx:
            err += dx
            y0 += sy


def rasterize_png(xy, width, height, stroke_width, ss=2):
    ss = max(1, int(ss))
    W2, H2 = width * ss, height * ss
    buf = bytearray([255]) * (W2 * H2)

    size = max(1, int(round(stroke_width * ss)))
    lo = (size - 1) // 2
    hi = size - 1 - lo

    for xs, ys in xy:
        px = [int(round(v * ss)) for v in xs]
        py = [int(round(v * ss)) for v in ys]

        if not px:
            continue

        for i in range(1, len(px)):
            _draw_segment(
                buf, W2, H2,
                px[i - 1], py[i - 1],
                px[i], py[i],
                lo, hi,
            )

        if len(px) == 1:
            _draw_segment(
                buf, W2, H2,
                px[0], py[0], px[0], py[0],
                lo, hi,
            )

    img = bytearray(width * height * 3)

    if ss == 1:
        for j in range(height):
            src = j * W2
            dst = j * width * 3

            for i in range(width):
                v = buf[src + i]
                p = dst + i * 3
                img[p] = img[p + 1] = img[p + 2] = v
    else:
        inv = 1.0 / (ss * ss)

        for j in range(height):
            rows = [
                (j * ss + k) * W2
                for k in range(ss)
            ]
            dst = j * width * 3

            for i in range(width):
                total = 0

                for row in rows:
                    base = row + i * ss
                    for k in range(ss):
                        total += buf[base + k]

                v = int(total * inv + 0.5)
                p = dst + i * 3
                img[p] = img[p + 1] = img[p + 2] = v

    def chunk(tag, data):
        return (
            struct.pack(">I", len(data))
            + tag
            + data
            + struct.pack(">I", zlib_crc32(tag + data))
        )

    raw = bytearray()

    for j in range(height):
        raw.append(0)
        s = j * width * 3
        raw.extend(img[s:s + width * 3])

    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(
            b"IHDR",
            struct.pack(
                ">IIBBBBB",
                width, height, 8, 2, 0, 0, 0
            ),
        )
        + chunk(b"IDAT", zlib.compress(bytes(raw), 6))
        + chunk(b"IEND", b"")
    )


def zlib_crc32(data):
    return zlib.crc32(data) & 0xFFFFFFFF


# ============================================================
# 单个投影生成
# ============================================================

def render_projection(
    tracks,
    projection,
    width=1800,
    height=1200,
    margin=70,
    stroke="#111111",
    stroke_width=2.2,
    stroke_opacity="1",
    ss=2,
):
    xy, info = project_tracks(
        tracks,
        projection,
        width,
        height,
        margin,
    )

    svg = build_svg(
        xy,
        width,
        height,
        stroke,
        stroke_width,
        stroke_opacity,
    )

    png = rasterize_png(
        xy,
        width,
        height,
        stroke_width,
        ss=ss,
    )

    return svg, png, info


# ============================================================
# 交互选择
# ============================================================

def choose_projections():
    print()
    print("请选择要生成的投影（可多选）：")
    for i, projection in enumerate(PROJECTIONS, 1):
        print(f"  [{i}] {projection.name}")
    print("  [a] 全部生成")
    print()

    while True:
        answer = input("请输入编号，例如 1 3，或输入 all：").strip().lower()

        if answer in ("a", "all"):
            return PROJECTIONS[:]

        tokens = answer.replace(",", " ").split()
        selected = []
        ok = True

        for token in tokens:
            if not token.isdigit():
                ok = False
                break

            n = int(token)
            if not 1 <= n <= len(PROJECTIONS):
                ok = False
                break

            projection = PROJECTIONS[n - 1]
            if projection not in selected:
                selected.append(projection)

        if ok and selected:
            return selected

        print("输入无效，请重新选择。")


# ============================================================
# 主程序
# ============================================================

def main(argv=None):
    ap = argparse.ArgumentParser(
        description="GPX 轨迹 → 多种地图投影 → SVG/PNG ZIP"
    )
    ap.add_argument("gpx", help="输入 GPX 文件")
    ap.add_argument("--width", type=int, default=1800)
    ap.add_argument("--height", type=int, default=1200)
    ap.add_argument("--margin", type=int, default=70)
    ap.add_argument("--stroke", default="#111111")
    ap.add_argument("--stroke-width", type=float, default=2.2)
    ap.add_argument("--stroke-opacity", default="1")
    ap.add_argument("--ss", type=int, default=2, help="PNG 超采样倍数（默认 2）")
    ap.add_argument(
        "--projection",
        nargs="+",
        choices=["webmercator", "equirectangular", "chinese1963"],
        help="直接指定投影；省略则运行时询问",
    )
    args = ap.parse_args(argv)

    if args.width <= 0 or args.height <= 0:
        ap.error("width 和 height 必须为正数。")
    if args.margin < 0:
        ap.error("margin 不能为负数。")
    if args.ss <= 0:
        ap.error("ss 必须为正整数。")

    gpx_path = args.gpx
    base = os.path.splitext(os.path.basename(gpx_path))[0]
    output_dir = os.path.dirname(os.path.abspath(gpx_path))
    zip_path = os.path.join(output_dir, base + ".zip")

    print("读入:", gpx_path)
    tracks = parse_gpx(gpx_path)

    n_pts = sum(len(t) for t in tracks)
    print(f"  独立轨迹 {len(tracks)} 条，共 {n_pts} 个 trkpt")

    if args.projection:
        lookup = {p.slug: p for p in PROJECTIONS}
        selected = [lookup[name] for name in args.projection]
    else:
        selected = choose_projections()

    print()
    print("将生成：")
    for projection in selected:
        print("  -", projection.name)
    print()

    # 与 ZIP 同目录建立临时工作目录；成功后全部打包并删除。
    with tempfile.TemporaryDirectory(prefix="mapchan_") as temp_dir:
        output_files = []

        for projection in selected:
            print(f"[{projection.name}]")

            svg, png, info = render_projection(
                tracks,
                projection,
                width=args.width,
                height=args.height,
                margin=args.margin,
                stroke=args.stroke,
                stroke_width=args.stroke_width,
                stroke_opacity=args.stroke_opacity,
                ss=args.ss,
            )

            stem = f"{base}_{projection.slug}"
            svg_path = os.path.join(temp_dir, stem + ".svg")
            png_path = os.path.join(temp_dir, stem + ".png")

            with open(svg_path, "w", encoding="utf-8") as f:
                f.write(svg)

            with open(png_path, "wb") as f:
                f.write(png)

            output_files.extend([svg_path, png_path])

            print(
                "  范围 x={:.6f} ~ {:.6f}, y={:.6f} ~ {:.6f}".format(
                    info["x_range"][0],
                    info["x_range"][1],
                    info["y_range"][0],
                    info["y_range"][1],
                )
            )
            print("  ✓ SVG:", os.path.basename(svg_path))
            print("  ✓ PNG:", os.path.basename(png_path))

        # 同名 ZIP 已存在时直接覆盖。
        with zipfile.ZipFile(
            zip_path,
            "w",
            compression=zipfile.ZIP_DEFLATED,
            compresslevel=6,
        ) as zf:
            for path in output_files:
                zf.write(path, arcname=os.path.basename(path))

    print()
    print("完成：", zip_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
