"""Render KFI museum pages from game assets for layout/color previews."""

from __future__ import annotations

import argparse
import math
import struct
from dataclasses import dataclass
from pathlib import Path

from PIL import Image

from font_mapping import project_path
from kfi_museum_pilot import (
    KFI36_RSC,
    KFI36_TEXTURE_A,
    KFI36_TEXTURE_B,
    KFI36_TXD_OFFSET,
    render_kfi36_textures,
)
from txd_import_png import png_index_to_native_index, psmt8_swizzled_offset
from txd_inspect import parse_children, read_chunk, texture_summaries


KFI_BG_RSC = Path("game_dump/DATA/KFI_BG_TEX.RSC")
KFI_BG_DFF_RSC = Path("game_dump/DATA/KFI_BG_DFF.RSC")
KFI_NA_TEX_RSC = Path("game_dump/DATA/KFI_NA_TEX.RSC")
KFI_NA_DFF_RSC = Path("game_dump/DATA/KFI_NA_DFF.RSC")
KFI_BG_TXD_OFFSET = 0x5C
KFI_NA_TXD_OFFSET = 0x5C
TEXTURE_DATA_HEADER = 0x50
SCREEN_SIZE = (640, 448)

RW_CONTAINERS = {0x03, 0x06, 0x07, 0x08, 0x0E, 0x0F, 0x10, 0x14, 0x1A}


def native_to_png_index(index: int) -> int:
    for png_index in range(256):
        if png_index_to_native_index(png_index) == index:
            return png_index
    raise ValueError(f"No PNG index maps to native index {index}")


NATIVE_TO_PNG = [native_to_png_index(index) for index in range(256)]


@dataclass(frozen=True)
class Frame:
    matrix: tuple[float, float, float, float, float, float, float, float, float]
    position: tuple[float, float, float]
    parent: int


@dataclass(frozen=True)
class Geometry:
    vertices: list[tuple[float, float, float]]
    uvs: list[tuple[float, float]]
    triangles: list[tuple[int, int, int, int]]


@dataclass(frozen=True)
class DffModel:
    frames: list[Frame]
    atomic_frame: int
    materials: list[str | None]
    geometry: Geometry


def embedded_txd(path: Path, offset: int) -> bytes:
    data = project_path(path).read_bytes()
    chunk = read_chunk(data, offset, len(data))
    if chunk is None or chunk.chunk_id != 0x16:
        raise ValueError(f"No TXD chunk at 0x{offset:x} in {path}")
    return data[offset : chunk.end_offset]


def rsc_embedded_txd(data: bytes, offset: int) -> bytes:
    chunk = read_chunk(data, offset, len(data))
    if chunk is None or chunk.chunk_id != 0x16:
        raise ValueError(f"No TXD chunk at 0x{offset:x}")
    return data[offset : chunk.end_offset]


def texture_map(txd_data: bytes) -> dict[str, dict]:
    report = {
        "path": "embedded",
        "size": len(txd_data),
        "chunks": parse_children(txd_data, 0, len(txd_data), 0, None),
    }
    return {str(texture["texture"]).lower(): texture for texture in texture_summaries(report)}


def decode_8bpp_rgba(txd_data: bytes, texture_name: str, force_opaque: bool = False) -> Image.Image:
    texture = texture_map(txd_data)[texture_name.lower()]
    if texture["bpp"] != 8:
        raise NotImplementedError(f"Only 8bpp PS2 textures are supported, got {texture['bpp']}")

    width = int(texture["width"])
    height = int(texture["height"])
    payload_offset = int(texture["data_payload_offset"])
    payload = txd_data[payload_offset : payload_offset + int(texture["data_size"])]
    pixel_data = payload[TEXTURE_DATA_HEADER : TEXTURE_DATA_HEADER + width * height]
    clut = payload[TEXTURE_DATA_HEADER + width * height :][:1024]

    indices = bytearray(width * height)
    for y in range(height):
        for x in range(width):
            native_index = pixel_data[psmt8_swizzled_offset(x, y, width)]
            indices[y * width + x] = NATIVE_TO_PNG[native_index]

    image = Image.new("P", (width, height), 0)
    palette = [0] * 768
    alpha = [255] * 256
    for png_index in range(256):
        native_index = png_index_to_native_index(png_index)
        start = native_index * 4
        r, g, b, a = clut[start : start + 4]
        palette[png_index * 3 : png_index * 3 + 3] = [r, g, b]
        alpha[png_index] = 255 if force_opaque else 0 if a == 0 else min(255, int(round(a * 255 / 128)))
    image.putpalette(palette)
    image.info["transparency"] = bytes(alpha)
    image.putdata(indices)
    return image.convert("RGBA")


def load_textures(path: Path, offset: int, force_opaque: bool = False) -> dict[str, Image.Image]:
    txd_data = embedded_txd(path, offset)
    return {name: decode_8bpp_rgba(txd_data, name, force_opaque=force_opaque) for name in texture_map(txd_data)}


def load_rsc_textures(data: bytes, offset: int) -> dict[str, Image.Image]:
    txd_data = rsc_embedded_txd(data, offset)
    return {name: decode_8bpp_rgba(txd_data, name) for name in texture_map(txd_data)}


def iter_rw_chunks(data: bytes, start: int, limit: int):
    offset = start
    while offset < limit:
        if offset + 12 > limit:
            break
        chunk_id, size, version = struct.unpack_from("<III", data, offset)
        payload = offset + 12
        end = payload + size
        if end > limit:
            break
        yield offset, chunk_id, size, version, payload, end
        offset = end


def c_string(data: bytes) -> str:
    return data.split(b"\0", 1)[0].decode("ascii", errors="replace")


def find_dff_start(data: bytes, label: str) -> int:
    position = data.find(label.encode("ascii"))
    if position < 0:
        raise ValueError(f"{label} not found")
    for offset in range(position, min(len(data) - 12, position + 0x200), 4):
        chunk_id, size, version = struct.unpack_from("<III", data, offset)
        if chunk_id == 0x10 and 0 < size < 0x200000 and version == 0x1003FFFF:
            return offset
    raise ValueError(f"No DFF clump near {label}")


def parse_frame_list(data: bytes, start: int, limit: int) -> list[Frame]:
    struct_chunk = next(iter_rw_chunks(data, start, limit))
    if struct_chunk[1] != 0x01:
        raise ValueError("Frame list does not start with Struct")
    payload = struct_chunk[4]
    count = struct.unpack_from("<I", data, payload)[0]
    frames: list[Frame] = []
    offset = payload + 4
    for _index in range(count):
        values = struct.unpack_from("<12fii", data, offset)
        frames.append(Frame(matrix=values[:9], position=values[9:12], parent=int(values[12])))
        offset += 56
    return frames


def parse_materials(data: bytes, start: int, limit: int) -> list[str | None]:
    materials: list[str | None] = []
    for _offset, chunk_id, _size, _version, payload, end in iter_rw_chunks(data, start, limit):
        if chunk_id != 0x07:
            continue
        texture_name: str | None = None

        def walk(child_start: int, child_limit: int) -> None:
            nonlocal texture_name
            for _o, child_id, _s, _v, child_payload, child_end in iter_rw_chunks(data, child_start, child_limit):
                if child_id == 0x02 and texture_name is None:
                    value = c_string(data[child_payload:child_end])
                    if value:
                        texture_name = value.lower()
                if child_id in RW_CONTAINERS:
                    walk(child_payload, child_end)

        walk(payload, end)
        materials.append(texture_name)
    return materials


def parse_geometry(data: bytes, start: int, limit: int) -> tuple[Geometry, list[str | None]]:
    children = list(iter_rw_chunks(data, start, limit))
    struct_chunk = children[0]
    if struct_chunk[1] != 0x01:
        raise ValueError("Geometry does not start with Struct")
    payload = data[struct_chunk[4] : struct_chunk[5]]
    flags = struct.unpack_from("<H", payload, 0)[0]
    texture_sets = payload[2]
    triangle_count, vertex_count, _morph_count = struct.unpack_from("<III", payload, 4)
    offset = 16
    if flags & 0x08:
        offset += vertex_count * 4

    uvs: list[tuple[float, float]] = []
    for _index in range(vertex_count * max(1, texture_sets)):
        uvs.append(struct.unpack_from("<ff", payload, offset))
        offset += 8

    triangles: list[tuple[int, int, int, int]] = []
    for _index in range(triangle_count):
        triangles.append(struct.unpack_from("<HHHH", payload, offset))
        offset += 8

    offset += 16 + 8
    vertices: list[tuple[float, float, float]] = []
    for _index in range(vertex_count):
        vertices.append(struct.unpack_from("<fff", payload, offset))
        offset += 12

    materials: list[str | None] = []
    for child in children:
        if child[1] == 0x08:
            materials = parse_materials(data, child[4], child[5])
    return Geometry(vertices=vertices, uvs=uvs, triangles=triangles), materials


def parse_dff(data: bytes, label: str) -> DffModel:
    start = find_dff_start(data, label)
    limit = start + 12 + struct.unpack_from("<I", data, start + 4)[0]
    frames: list[Frame] = []
    geometry: Geometry | None = None
    materials: list[str | None] = []
    atomic_frame = 0

    def walk(child_start: int, child_limit: int) -> None:
        nonlocal frames, geometry, materials, atomic_frame
        for _offset, chunk_id, _size, _version, payload, end in iter_rw_chunks(data, child_start, child_limit):
            if chunk_id == 0x0E:
                frames = parse_frame_list(data, payload, end)
            elif chunk_id == 0x0F:
                geometry, materials = parse_geometry(data, payload, end)
            elif chunk_id == 0x14:
                children = list(iter_rw_chunks(data, payload, end))
                if children and children[0][1] == 0x01:
                    atomic_frame = struct.unpack_from("<I", data, children[0][4])[0]
            if chunk_id in RW_CONTAINERS:
                walk(payload, end)

    walk(start + 12, limit)
    if geometry is None:
        raise ValueError(f"No geometry in {label}")
    return DffModel(frames=frames, atomic_frame=atomic_frame, materials=materials, geometry=geometry)


@dataclass(frozen=True)
class Transform:
    right: tuple[float, float, float]
    up: tuple[float, float, float]
    at: tuple[float, float, float]
    position: tuple[float, float, float]


IDENTITY_TRANSFORM = Transform(
    right=(1.0, 0.0, 0.0),
    up=(0.0, 1.0, 0.0),
    at=(0.0, 0.0, 1.0),
    position=(0.0, 0.0, 0.0),
)


def transform_direction(transform: Transform, vector: tuple[float, float, float]) -> tuple[float, float, float]:
    x, y, z = vector
    return (
        transform.right[0] * x + transform.up[0] * y + transform.at[0] * z,
        transform.right[1] * x + transform.up[1] * y + transform.at[1] * z,
        transform.right[2] * x + transform.up[2] * y + transform.at[2] * z,
    )


def transform_point(transform: Transform, point: tuple[float, float, float]) -> tuple[float, float, float]:
    x, y, z = transform_direction(transform, point)
    return (
        x + transform.position[0],
        y + transform.position[1],
        z + transform.position[2],
    )


def compose_transform(parent: Transform, frame: Frame) -> Transform:
    local = Transform(
        right=frame.matrix[0:3],
        up=frame.matrix[3:6],
        at=frame.matrix[6:9],
        position=frame.position,
    )
    return Transform(
        right=transform_direction(parent, local.right),
        up=transform_direction(parent, local.up),
        at=transform_direction(parent, local.at),
        position=transform_point(parent, local.position),
    )


def frame_transform(frames: list[Frame], index: int) -> Transform:
    transform = IDENTITY_TRANSFORM
    chain: list[int] = []
    while 0 <= index < len(frames):
        chain.append(index)
        index = frames[index].parent
    for frame_index in reversed(chain):
        transform = compose_transform(transform, frames[frame_index])
    return transform


def normalize_kfi_dark_red(image: Image.Image) -> Image.Image:
    """Convert KFI mask-red ink entries to neutral paper ink.

    Several KFI UI textures store dark ink/line art as low-red palette entries.
    In-game they are rendered as neutral gray/olive through the menu render
    state; a straight RGBA dump shows them as visible red artifacts.
    """

    image = image.copy()
    pixels = image.load()
    for y in range(image.height):
        for x in range(image.width):
            r, g, b, a = pixels[x, y]
            if a and 34 <= r and g <= 125 and b <= 125 and r > g * 1.25 and r > b * 1.25:
                value = max(28, min(100, int(32 + r * 0.25)))
                pixels[x, y] = (int(value * 0.86), int(value * 0.90), int(value * 0.78), a)
    return image


def render_texture_piece(
    canvas: Image.Image,
    texture: Image.Image,
    screen_box: tuple[int, int, int, int],
    uv_box: tuple[int, int, int, int],
    normalize_red: bool,
) -> None:
    left, top, right, bottom = screen_box
    uv_left, uv_top, uv_right, uv_bottom = uv_box
    if right <= left or bottom <= top or uv_right <= uv_left or uv_bottom <= uv_top:
        return
    crop = texture.crop(
        (
            max(0, uv_left),
            max(0, uv_top),
            min(texture.width, uv_right),
            min(texture.height, uv_bottom),
        )
    )
    if normalize_red:
        crop = normalize_kfi_dark_red(crop)
    resized = crop.resize((right - left, bottom - top), Image.Resampling.BILINEAR)
    if normalize_red:
        resized = normalize_kfi_dark_red(resized)
    canvas.alpha_composite(resized, (left, top))


def render_dff(
    canvas: Image.Image,
    model: DffModel,
    textures: dict[str, Image.Image],
    normalize_red: bool = True,
) -> None:
    transform = frame_transform(model.frames, model.atomic_frame)
    geometry = model.geometry
    for material_index, texture_name in enumerate(model.materials):
        if not texture_name or texture_name.endswith("m"):
            continue
        texture = textures.get(texture_name)
        if texture is None:
            continue
        vertex_indices: set[int] = set()
        for triangle in geometry.triangles:
            if triangle[2] == material_index:
                vertex_indices.update((triangle[0], triangle[1], triangle[3]))
        if not vertex_indices:
            continue

        xs: list[float] = []
        ys: list[float] = []
        us: list[float] = []
        vs: list[float] = []
        for vertex_index in vertex_indices:
            x, y, z = transform_point(transform, geometry.vertices[vertex_index])
            u, v = geometry.uvs[vertex_index]
            xs.append(x * 10)
            ys.append(-y * 10)
            us.append(u * texture.width)
            vs.append(v * texture.height)

        render_texture_piece(
            canvas,
            texture,
            (
                math.floor(min(xs)),
                math.floor(min(ys)),
                math.ceil(max(xs)),
                math.ceil(max(ys)),
            ),
            (
                math.floor(min(us)),
                math.floor(min(vs)),
                math.ceil(max(us)),
                math.ceil(max(vs)),
            ),
            normalize_red=normalize_red,
        )


def replace_textures_with_pngs(textures: dict[str, Image.Image], pngs: list[Path]) -> dict[str, Image.Image]:
    result = dict(textures)
    for path in pngs:
        stem = path.stem.lower()
        for texture_name in list(result):
            if stem.endswith(texture_name):
                result[texture_name] = Image.open(path).convert("RGBA")
    return result


def render_kfi36_page(use_generated_english: bool, output: Path) -> Path:
    output = project_path(output)
    output.parent.mkdir(parents=True, exist_ok=True)

    canvas = Image.new("RGBA", SCREEN_SIZE, (146, 151, 130, 255))
    bg_textures = load_textures(KFI_BG_RSC, KFI_BG_TXD_OFFSET)
    name_textures = load_textures(KFI_NA_TEX_RSC, KFI_NA_TXD_OFFSET, force_opaque=True)

    kfi36_data = project_path(KFI36_RSC).read_bytes()
    char_textures = load_rsc_textures(kfi36_data, 0xB8)
    shadow_textures = load_rsc_textures(kfi36_data, 0x218E8)
    body_textures = load_rsc_textures(kfi36_data, KFI36_TXD_OFFSET)

    if use_generated_english:
        generated = render_kfi36_textures(
            project_path("textures_en/EXPORT_TXD/KFI/museum_pilot")
        )
        body_textures = replace_textures_with_pngs(body_textures, list(generated))

    render_dff(
        canvas,
        parse_dff(project_path(KFI_BG_DFF_RSC).read_bytes(), "KFI_BG_0100.dff"),
        bg_textures,
    )
    render_dff(canvas, parse_dff(kfi36_data, "KFI_SH_3600.dff"), shadow_textures, normalize_red=False)
    render_dff(canvas, parse_dff(kfi36_data, "KFI_CH_3600.dff"), char_textures, normalize_red=False)
    render_dff(
        canvas,
        parse_dff(project_path(KFI_NA_DFF_RSC).read_bytes(), "KFI_NA_3600.dff"),
        name_textures,
    )
    render_dff(canvas, parse_dff(kfi36_data, "KFI_TX_3600.dff"), body_textures)

    canvas.convert("RGB").save(output)
    return output


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", default="build/museum_pilot_preview/asset_pipeline")
    parser.add_argument("--english", action="store_true")
    args = parser.parse_args()

    output_dir = project_path(args.output_dir)
    original = render_kfi36_page(False, output_dir / "kfi36_assets_original.png")
    print(f"Original asset preview: {original}")
    if args.english:
        english = render_kfi36_page(True, output_dir / "kfi36_assets_english_preview.png")
        print(f"English asset preview: {english}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
