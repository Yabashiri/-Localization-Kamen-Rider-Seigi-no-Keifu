"""Patch a rebuilt DATA.CVM into the original PS2 ISO layout.

This keeps DATA.CVM at its original LBA. The game ELF contains that LBA as a
literal value, so rebuilding the whole disc with mkisofs moves the container and
breaks early boot.
"""

from __future__ import annotations

import argparse
import shutil
from dataclasses import dataclass
from pathlib import Path

from font_mapping import project_path


SECTOR_SIZE = 2048
PVD_SECTOR = 16


@dataclass
class DirRecord:
    name: str
    record_offset: int
    extent: int
    size: int
    flags: int

    @property
    def end_extent(self) -> int:
        return self.extent + sectors_for_size(self.size)


def sectors_for_size(size: int) -> int:
    return (size + SECTOR_SIZE - 1) // SECTOR_SIZE


def read_u32_both(data: bytes, offset: int) -> int:
    little = int.from_bytes(data[offset : offset + 4], "little")
    big = int.from_bytes(data[offset + 4 : offset + 8], "big")
    if little != big:
        raise ValueError(f"ISO both-endian field mismatch at 0x{offset:X}: {little} != {big}")
    return little


def write_u32_both(handle, offset: int, value: int) -> None:
    handle.seek(offset)
    handle.write(value.to_bytes(4, "little"))
    handle.write(value.to_bytes(4, "big"))


def parse_root_records(iso_path: Path) -> tuple[int, int, list[DirRecord]]:
    with iso_path.open("rb") as handle:
        handle.seek(PVD_SECTOR * SECTOR_SIZE)
        pvd = handle.read(SECTOR_SIZE)
        if pvd[1:6] != b"CD001":
            raise ValueError(f"Not an ISO9660 primary volume descriptor: {iso_path}")

        root_record = pvd[156 : 156 + pvd[156]]
        root_extent = read_u32_both(root_record, 2)
        root_size = read_u32_both(root_record, 10)

        handle.seek(root_extent * SECTOR_SIZE)
        root_data = handle.read(root_size)

    records: list[DirRecord] = []
    pos = 0
    while pos < len(root_data):
        length = root_data[pos]
        if length == 0:
            pos = ((pos // SECTOR_SIZE) + 1) * SECTOR_SIZE
            continue

        record = root_data[pos : pos + length]
        name_len = record[32]
        raw_name = record[33 : 33 + name_len]
        if raw_name == b"\x00":
            name = "."
        elif raw_name == b"\x01":
            name = ".."
        else:
            name = raw_name.decode("ascii")

        records.append(
            DirRecord(
                name=name,
                record_offset=root_extent * SECTOR_SIZE + pos,
                extent=read_u32_both(record, 2),
                size=read_u32_both(record, 10),
                flags=record[25],
            )
        )
        pos += length

    return root_extent, root_size, records


def copy_exact_region(source, dest, source_offset: int, size: int) -> None:
    source.seek(source_offset)
    remaining = size
    while remaining:
        chunk = source.read(min(8 * 1024 * 1024, remaining))
        if not chunk:
            raise EOFError("Unexpected EOF while copying ISO region")
        dest.write(chunk)
        remaining -= len(chunk)


def patch_iso(original_iso: Path, rebuilt_cvm: Path, output_iso: Path, patched_elf: Path | None = None) -> None:
    if not original_iso.is_file():
        raise FileNotFoundError(f"Original ISO not found: {original_iso}")
    if not rebuilt_cvm.is_file():
        raise FileNotFoundError(f"Rebuilt DATA.CVM not found: {rebuilt_cvm}")
    if patched_elf is not None and not patched_elf.is_file():
        raise FileNotFoundError(f"Patched ELF not found: {patched_elf}")

    _, _, records = parse_root_records(original_iso)
    by_name = {record.name.upper(): record for record in records}
    data_record = by_name.get("DATA.CVM;1")
    if data_record is None:
        raise ValueError("DATA.CVM;1 not found in original ISO root")
    elf_record = by_name.get("SLPS_253.02;1")
    if patched_elf is not None and elf_record is None:
        raise ValueError("SLPS_253.02;1 not found in original ISO root")
    if patched_elf is not None and patched_elf.stat().st_size != elf_record.size:
        raise ValueError(
            f"Patched ELF must keep original size: {patched_elf.stat().st_size} != {elf_record.size}"
        )

    rebuilt_size = rebuilt_cvm.stat().st_size
    rebuilt_sectors = sectors_for_size(rebuilt_size)
    old_data_sectors = sectors_for_size(data_record.size)
    delta_sectors = rebuilt_sectors - old_data_sectors

    if delta_sectors < 0:
        delta_sectors = 0

    moving_records = [
        record
        for record in records
        if record.name not in (".", "..")
        and (record.flags & 0x02) == 0
        and record.extent >= data_record.end_extent
    ]
    moving_records.sort(key=lambda record: record.extent)

    output_iso.parent.mkdir(parents=True, exist_ok=True)
    data_offset = data_record.extent * SECTOR_SIZE
    new_extents: dict[str, int] = {"DATA.CVM;1": data_record.extent}

    with original_iso.open("rb") as src, rebuilt_cvm.open("rb") as cvm, output_iso.open("wb") as out:
        copy_exact_region(src, out, 0, data_offset)
        shutil.copyfileobj(cvm, out, length=8 * 1024 * 1024)
        pad = rebuilt_sectors * SECTOR_SIZE - rebuilt_size
        if pad:
            out.write(b"\x00" * pad)

        current_extent = data_record.extent + rebuilt_sectors
        last_copied_source_extent = data_record.end_extent
        for record in moving_records:
            current_offset = current_extent * SECTOR_SIZE
            if out.tell() < current_offset:
                out.write(b"\x00" * (current_offset - out.tell()))
            elif out.tell() != current_offset:
                raise ValueError(f"Output cursor is not sector-aligned for {record.name}")

            new_extents[record.name] = current_extent
            copy_exact_region(src, out, record.extent * SECTOR_SIZE, record.size)
            pad = sectors_for_size(record.size) * SECTOR_SIZE - record.size
            if pad:
                out.write(b"\x00" * pad)
            current_extent += sectors_for_size(record.size)
            last_copied_source_extent = max(last_copied_source_extent, record.end_extent)

        source_tail_offset = last_copied_source_extent * SECTOR_SIZE
        src.seek(0, 2)
        source_size = src.tell()
        if source_tail_offset < source_size:
            copy_exact_region(src, out, source_tail_offset, source_size - source_tail_offset)

    new_volume_size = sectors_for_size(output_iso.stat().st_size)
    with output_iso.open("r+b") as out:
        write_u32_both(out, PVD_SECTOR * SECTOR_SIZE + 80, new_volume_size)
        write_u32_both(out, data_record.record_offset + 10, rebuilt_size)

        for record in moving_records:
            write_u32_both(out, record.record_offset + 2, new_extents[record.name])

        if patched_elf is not None:
            out.seek(elf_record.extent * SECTOR_SIZE)
            with patched_elf.open("rb") as elf:
                shutil.copyfileobj(elf, out, length=8 * 1024 * 1024)

    print(f"Original DATA.CVM LBA: {data_record.extent}")
    print(f"Original DATA.CVM size: {data_record.size} bytes ({old_data_sectors} sectors)")
    print(f"Rebuilt DATA.CVM size:  {rebuilt_size} bytes ({rebuilt_sectors} sectors)")
    print(f"Shifted following files: {len(moving_records)} records (+{delta_sectors} sectors)")
    if patched_elf is not None:
        print(f"Patched ELF LBA: {elf_record.extent}")
    print(f"Built patched ISO: {output_iso} ({output_iso.stat().st_size} bytes)")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--original-iso",
        default=r"E:\Download\Minerva_Myrient\Redump\Sony - PlayStation 2\Kamen Rider - Seigi no Keifu (Japan).iso",
    )
    parser.add_argument("--rebuilt-cvm", default="build/stage/DATA.CVM")
    parser.add_argument("--patched-elf")
    parser.add_argument("--output-iso", default="build/out/kamen_rider_text_smoke.iso")
    args = parser.parse_args()

    patch_iso(
        Path(args.original_iso),
        project_path(args.rebuilt_cvm),
        project_path(args.output_iso),
        project_path(args.patched_elf) if args.patched_elf else None,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
