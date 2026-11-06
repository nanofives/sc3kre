#!/usr/bin/env python3
"""Build native five-zoom snow images and an explicit attribute segment."""

from __future__ import annotations

import argparse
import hashlib
import math
import random
import re
import struct
from pathlib import Path

IXF_SIGNATURE = 0x80C381D7
SEGMENT_GROUP = 0x739A4081
IMAGE_BASE = 0xFFFC4400
ATTR_BASE = 0xFFFC4600
# SIMSPR registers 0x7300 as the basic cISC3CitySpriteInst implementation.
# Its QueryInterface explicitly accepts IID 0x7100, which is what the native
# CitySpriteAttrib CreateSprite method requests.
BASIC_CITY_SPRITE_CLSID = 0x00007300
SIZES = ((8, 4), (16, 8), (32, 16), (64, 32), (128, 64))
VARIANT_COUNT = 3
ROTATION_COUNT = 4
TRANSPARENT = 0xF81F


def image_id(zoom: int, variant: int) -> int:
    return IMAGE_BASE + zoom * 0x10 + variant


def refpack_literal_encode(raw: bytes) -> bytes:
    output = bytearray(b"\x10\xfb" + len(raw).to_bytes(3, "big"))
    remainder = len(raw) & 3
    body_end = len(raw) - remainder
    position = 0
    while position < body_end:
        count = min(112, body_end - position) & ~3
        output.append(0xE0 + (count - 4) // 4)
        output.extend(raw[position:position + count])
        position += count
    output.append(0xFC + remainder)
    output.extend(raw[body_end:])
    return bytes(output)


def refpack_encode(raw: bytes) -> bytes:
    """Losslessly compress long transparent runs with native distance-2 copies.

    Keep the established literal encoding elsewhere. This reduces the large
    temporary input allocation in SIMSPR without changing a decoded pixel.
    """
    output=bytearray(b'\x10\xfb'+len(raw).to_bytes(3,'big'))
    pending=0
    def literals(end):
        nonlocal pending
        while end-pending>=4:
            n=min(112,(end-pending)&~3)
            output.append(0xE0+(n-4)//4)
            output.extend(raw[pending:pending+n]);pending+=n
    for match in re.finditer(b'(?:\x1f\xf8){8,}',raw):
        start=match.start()+2 # seed the distance-two copy
        literals(start)
        remaining=match.end()-start
        while remaining>=5:
            count=min(1028,remaining);lead=start-pending
            assert 0<=lead<=3
            encoded=count-5
            output.extend((0xC0|((encoded>>8)<<2)|lead,0,1,encoded&255))
            output.extend(raw[pending:start])
            start+=count;remaining-=count;pending=start
    literals(len(raw))
    output.append(0xFC+len(raw)-pending);output.extend(raw[pending:])
    return bytes(output)

def refpack_decode(stream: bytes) -> bytes:
    """Decode the literal and long-copy forms emitted by this compiler."""
    assert stream[:2]==b'\x10\xfb'
    expected=int.from_bytes(stream[2:5],'big');out=bytearray();pos=5
    while pos<len(stream):
        op=stream[pos];pos+=1
        if op>=0xFC:
            n=op&3;out.extend(stream[pos:pos+n]);pos+=n;break
        if op>=0xE0:
            n=((op&31)<<2)+4;out.extend(stream[pos:pos+n]);pos+=n
        else:
            assert 0xC0<=op<0xE0
            b1,b2,b3=stream[pos:pos+3];pos+=3
            n=op&3;out.extend(stream[pos:pos+n]);pos+=n
            offset=((op&16)<<12)+(b1<<8)+b2+1
            count=((op&12)<<6)+b3+5
            assert 0<offset<=len(out)
            chunk=bytes(out[-offset:])
            out.extend((chunk*((count+offset-1)//offset))[:count])
    assert len(out)==expected and pos==len(stream)
    return bytes(out)

def sprite_resource(width: int, height: int, raw: bytes) -> bytes:
    stream = refpack_encode(raw)
    assert refpack_decode(stream)==raw
    return struct.pack(
        "<BBHIIII", 7, 1, 0, 0x00080000,
        width, height, 4 + len(stream)
    ) + stream


def pack_rgb565(width: int, height: int, values: list[int]) -> bytes:
    strides = bytearray()
    stored: list[int] = []
    running = 0
    for y in range(height):
        row = values[y * width:(y + 1) * width]
        begin = 0
        while begin < width and row[begin] == TRANSPARENT:
            begin += 1
        if begin == width:
            span = 0
            opaque = True
        else:
            end = width
            while end > begin and row[end - 1] == TRANSPARENT:
                end -= 1
            span = end - begin
            opaque = TRANSPARENT not in row[begin:end]
            stored.extend(row[begin:end])
        strides.extend(struct.pack(
            "<IHH", running, begin, span | (0x8000 if opaque else 0)
        ))
        running += span
    pixels = struct.pack(f"<{len(stored)}H", *stored)
    length = 16 + len(strides) + len(pixels)
    return struct.pack(
        "<IHHHHHH", length, width, height, 4, 7, TRANSPARENT, 0
    ) + strides + pixels


def make_snow_cell(width: int, height: int, zoom: int,
                   variant: int) -> list[int]:
    """Create opaque snow flecks with transparent gaps for terrain blending."""
    rng = random.Random(0x8005A0E0 + zoom * 193 + variant * 977)
    pixels = [TRANSPARENT] * (width * height)
    palette = (0x9CF3, 0xAD75, 0xBDF7, 0xC638, 0xCE79)
    for y in range(height):
        for x in range(width):
            nx = abs((x + 0.5) - width / 2) / (width / 2)
            ny = abs((y + 0.5) - height / 2) / (height / 2)
            diamond = 1.0 - nx - ny
            if diamond <= 0:
                continue

            u = (x + 0.5) / width
            v = (y + 0.5) / height
            broad = math.sin(u * 6.4 + v * 3.1 + variant * 1.9)
            cross = math.sin(u * 11.2 - v * 7.7 + variant * 0.8)
            drift = math.sin(u * 3.8 - v * 9.2 + variant * 2.3)
            edge = min(1.0, diamond * max(3.2, height / 3.0))

            # SC3K has keyed transparency here, not soft alpha. Irregular gaps
            # let the player's original terrain remain visibly present. The
            # low-frequency field makes patches, not salt-and-pepper glitter.
            field = 0.58 * broad + 0.29 * cross + 0.18 * drift
            threshold = -0.34 + (1.0 - edge) * 0.34
            if zoom == 0:
                threshold -= 0.24
            elif zoom == 1:
                threshold -= 0.12
            if field < threshold or (zoom >= 2 and rng.random() < 0.025):
                continue

            shade = 1 + int((broad + cross + 2.0) * 0.65)
            shade += rng.choice((-1, 0, 0, 0, 1))
            shade = max(0, min(len(palette) - 1, shade))
            pixels[y * width + x] = palette[shade]
    return pixels


def city_sprite_attrib(variant: int) -> bytes:
    frame_count = len(SIZES) * ROTATION_COUNT
    payload = bytearray(b"BIN\r")
    payload.extend(struct.pack("<II", 1, BASIC_CITY_SPRITE_CLSID))
    payload.extend(struct.pack(
        "<6B", len(SIZES), ROTATION_COUNT, frame_count,
        frame_count, 1, 0
    ))
    payload.extend(struct.pack("<IH", 0, frame_count))
    for zoom in range(len(SIZES)):
        for rotation in range(ROTATION_COUNT):
            frame = zoom * ROTATION_COUNT + rotation
            payload.extend(struct.pack(
                "<HII BHH", frame, 0, image_id(zoom, variant), 0, 0, 0
            ))
    expected = 24 + frame_count * 15
    if len(payload) != expected:
        raise RuntimeError(f"attribute length {len(payload)} != {expected}")
    return bytes(payload)


def write_ixf(path: Path,
              resources: list[tuple[int, int, int, bytes]]) -> None:
    offset = 4 + 20 * (len(resources) + 1)
    table = bytearray(struct.pack("<I", IXF_SIGNATURE))
    payload = bytearray()
    for group, instance, resource_type, data in resources:
        table.extend(struct.pack(
            "<IIIII", group, instance, resource_type, offset, len(data)
        ))
        payload.extend(data)
        offset += len(data)
    table.extend(bytes(20))
    path.write_bytes(table + payload)


def write_sii(path: Path) -> None:
    lines = [
        "; SimCity 3000 Image Info",
        "; Native depth-sorted snow cells v0.8.1",
        "; Format: ImageID, Span L, Span T, Span R, Span B",
        f"Record Count: {len(SIZES) * VARIANT_COUNT}",
    ]
    for zoom, (width, height) in enumerate(SIZES):
        for variant in range(VARIANT_COUNT):
            lines.append(
                f"{image_id(zoom, variant):08X}, "
                f"{width // 2}, {height // 2}, {width // 2}, {height // 2}"
            )
    path.write_text("\n".join(lines) + "\n", encoding="ascii", newline="\r\n")


def read_ixf(path: Path) -> list[tuple[int, int, int, bytes]]:
    raw = path.read_bytes()
    if len(raw) < 24 or struct.unpack_from("<I", raw)[0] != IXF_SIGNATURE:
        raise RuntimeError(f"{path.name}: invalid IXF signature")
    records: list[tuple[int, int, int, bytes]] = []
    cursor = 4
    while cursor + 20 <= len(raw):
        group, instance, resource_type, offset, size = struct.unpack_from(
            "<IIIII", raw, cursor
        )
        cursor += 20
        if group == instance == resource_type == 0:
            break
        if offset > len(raw) or size > len(raw) - offset:
            raise RuntimeError(f"{path.name}: record points outside the archive")
        records.append((group, instance, resource_type,
                        raw[offset:offset + size]))
    else:
        raise RuntimeError(f"{path.name}: missing IXF index terminator")
    return records


def validate_outputs(dat_path: Path, attrib_path: Path) -> None:
    expected_images = {
        image_id(zoom, variant)
        for zoom in range(len(SIZES))
        for variant in range(VARIANT_COUNT)
    }
    dat_records = read_ixf(dat_path)
    actual_pairs = {(group, instance, resource_type)
                    for group, instance, resource_type, _ in dat_records}
    expected_pairs = {(0, instance, resource_type)
                      for instance in expected_images
                      for resource_type in (0, 1)}
    if len(dat_records) != len(expected_pairs) or actual_pairs != expected_pairs:
        raise RuntimeError("sprite DAT does not contain every image/span pair")

    attrib_records = read_ixf(attrib_path)
    if len(attrib_records) != VARIANT_COUNT:
        raise RuntimeError("attribute IXF does not contain exactly three records")
    for variant, (group, instance, resource_type, payload) in enumerate(attrib_records):
        if (group, instance, resource_type) != (
                SEGMENT_GROUP, ATTR_BASE + variant, 0x6300):
            raise RuntimeError("attribute IXF key mismatch")
        if len(payload) != 324 or payload[:4] != b"BIN\r":
            raise RuntimeError("attribute payload header/length mismatch")
        version, clsid = struct.unpack_from("<II", payload, 4)
        counts = struct.unpack_from("<6B", payload, 12)
        layer_flags, frame_count = struct.unpack_from("<IH", payload, 18)
        if (version, clsid, counts, layer_flags, frame_count) != (
                1, BASIC_CITY_SPRITE_CLSID, (5, 4, 20, 20, 1, 0), 0, 20):
            raise RuntimeError("attribute payload fields do not match native schema")
        cursor = 24
        for frame in range(frame_count):
            frame_id, image_group, instance_id, direction, x_off, y_off = \
                struct.unpack_from("<HII BHH", payload, cursor)
            cursor += 15
            expected_instance = image_id(frame // ROTATION_COUNT, variant)
            if (frame_id, image_group, instance_id, direction, x_off, y_off) != (
                    frame, 0, expected_instance, 0, 0, 0):
                raise RuntimeError("attribute frame reference mismatch")
            if instance_id not in expected_images:
                raise RuntimeError("attribute references a missing sprite image")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("output_dat", type=Path)
    parser.add_argument("output_sii", type=Path)
    parser.add_argument("output_attrib_ixf", type=Path)
    args = parser.parse_args()
    resources: list[tuple[int, int, int, bytes]] = []
    for zoom, (width, height) in enumerate(SIZES):
        for variant in range(VARIANT_COUNT):
            instance = image_id(zoom, variant)
            span = struct.pack(
                "<HHHH", width // 2, height // 2, width // 2, height // 2
            )
            image = sprite_resource(
                width, height,
                pack_rgb565(width, height,
                            make_snow_cell(width, height, zoom, variant))
            )
            resources.extend(((0, instance, 1, span),
                              (0, instance, 0, image)))
    write_ixf(args.output_dat, resources)
    write_sii(args.output_sii)
    attrib_resources = [
        (SEGMENT_GROUP, ATTR_BASE + variant, 0x6300,
         city_sprite_attrib(variant))
        for variant in range(VARIANT_COUNT)
    ]
    write_ixf(args.output_attrib_ixf, attrib_resources)
    validate_outputs(args.output_dat, args.output_attrib_ixf)
    for output in (args.output_dat, args.output_sii, args.output_attrib_ixf):
        digest = hashlib.sha256(output.read_bytes()).hexdigest()
        print(f"{digest}  {output.name}")


if __name__ == "__main__":
    main()
