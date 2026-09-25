#!/usr/bin/env python3
"""Build Chintan Sans from the local Inter variable fonts.

Chintan Sans is a renamed, screen-focused derivative. Inter is a Reserved
Font Name, so it is not used as the family name. The build:

- bakes the Inter alternates used for an Atlassian-style app face
- tightens spacing without breaking equal-width groups (tabular figures)
- sets Windows clip metrics, an unhinted gasp table, and macOS overlap flags
- writes a variable font plus static TTF, WOFF, and WOFF2 files

Run from this directory:

    python3 -m venv .venv
    .venv/bin/pip install -r requirements.txt
    .venv/bin/python build.py
"""

from __future__ import annotations

import logging
from collections import defaultdict
from copy import deepcopy
from pathlib import Path

from fontTools.ttLib import TTFont, newTable
from fontTools.varLib.instancer import instantiateVariableFont, setMacOverlapFlags

logging.getLogger("fontTools").setLevel(logging.ERROR)

ROOT = Path(__file__).resolve().parent
SOURCE = ROOT.parent / "inter" / "docs" / "font-files"
OUT = ROOT / "fonts"
CSS_PATH = ROOT / "css" / "chintan.css"

FAMILY = "Chintan Sans"
VARIABLE_FAMILY = "Chintan Sans Variable"
# Filenames and PostScript names cannot contain spaces.
PS_FAMILY = "ChintanSans"
VERSION = "1.300"
VENDOR = "CHSN"
# Inter features Atlassian turns on for every UI string.
DIRECTION_FEATURES = ("cv08", "cv10", "cv09", "cv07", "cv14", "ss07", "ss08")
# Units removed from each advance when every glyph that shares that
# advance can spare them. 48 units is about 0.4px at 16px (UPM 2048).
TRACK = 48
# Positive right sidebearing left in place after tracking.
FLOOR = 56

WEIGHTS = (
    (100, "Thin"),
    (200, "ExtraLight"),
    (300, "Light"),
    (400, "Regular"),
    (500, "Medium"),
    (600, "SemiBold"),
    (700, "Bold"),
    (800, "ExtraBold"),
    (900, "Black"),
)

USE_TYPO_METRICS = 1 << 7
ITALIC_BIT = 1 << 0
BOLD_BIT = 1 << 5
REGULAR_BIT = 1 << 6
# Unhinted outlines: grayscale smoothing, no grid fit.
GASP_SMOOTH = 0x0002 | 0x0008

COPYRIGHT = (
    "Copyright 2016 The Inter Project Authors. "
    "Copyright 2026 Chintan."
)
TRADEMARK = "Chintan Sans. Inter is a trademark of rsms."
DESCRIPTION = (
    "Chintan Sans is a screen-focused derivative of Inter for product interfaces. "
    "Defaults use the Inter alternates from the Atlassian app-face recipe: "
    "serif I, spurred G, flat-top 3, alternate German double s, and square "
    "punctuation and quotes. Spacing is slightly tighter than Inter. "
    "Original design by Rasmus Andersson and the Inter Project Authors. "
    "Chintan Sans is not endorsed by the Inter project or by Atlassian."
)
DESIGNER = "Rasmus Andersson"
MANUFACTURER = "Chintan"
LICENSE = (
    "This Font Software is licensed under the SIL Open Font License, Version 1.1. "
    "This license is available with a FAQ at: http://scripts.sil.org/OFL"
)
LICENSE_URL = "http://scripts.sil.org/OFL"
DESIGNER_URL = "https://rsms.me/"


def main() -> None:
    roman_src = SOURCE / "InterVariable.ttf"
    italic_src = SOURCE / "InterVariable-Italic.woff2"
    if not roman_src.is_file() or not italic_src.is_file():
        raise SystemExit(f"Missing Inter sources in {SOURCE}")

    print("Preparing roman variable font")
    roman = prepare(TTFont(roman_src), italic=False)
    print("Preparing italic variable font")
    italic = prepare(TTFont(italic_src), italic=True)

    win_ascent, win_descent = family_vertical_clip(roman, italic)
    print(f"Windows clip box: ascent {win_ascent}, descent {win_descent}")
    apply_vertical_clip(roman, win_ascent, win_descent)
    apply_vertical_clip(italic, win_ascent, win_descent)

    variable_dir = OUT / "variable"
    static_dir = OUT / "static"
    variable_dir.mkdir(parents=True, exist_ok=True)
    static_dir.mkdir(parents=True, exist_ok=True)

    variable_files = []
    for font, stem in (
        (roman, f"{PS_FAMILY}-Variable"),
        (italic, f"{PS_FAMILY}-VariableItalic"),
    ):
        ttf = variable_dir / f"{stem}.ttf"
        woff2 = variable_dir / f"{stem}.woff2"
        print(f"Writing {stem}")
        write_font(font, ttf, woff2)
        variable_files.append((ttf, woff2))

    static_faces = []
    for source, is_italic in ((roman, False), (italic, True)):
        for weight, weight_name in WEIGHTS:
            stem = file_stem(weight_name, is_italic)
            print(f"Instancing {stem}")
            instance = instantiateVariableFont(
                source,
                {"wght": weight, "opsz": 14},
                static=True,
                optimize=True,
            )
            finalize_static(instance, weight, weight_name, is_italic, win_ascent, win_descent)
            ttf = static_dir / f"{stem}.ttf"
            woff2 = static_dir / f"{stem}.woff2"
            woff = static_dir / f"{stem}.woff"
            write_font(instance, ttf, woff2, woff)
            static_faces.append((weight, is_italic, stem))
            del instance

    write_css(static_faces)
    write_web_subsets()
    validate(roman, italic, win_ascent, win_descent, variable_files, static_dir, static_faces)
    print(f"Done. Fonts in {OUT}")


def prepare(font: TTFont, italic: bool) -> TTFont:
    baked = bake_direction(font)
    print(f"  direction glyphs updated: {baked}")
    changed, sample = tighten(font)
    print(f"  advances tightened: {changed}")
    for name, before, after in sample:
        print(f"    {name}: {before} -> {after}")
    setMacOverlapFlags(font["glyf"])
    set_gasp(font)
    apply_common_metadata(font, italic)
    apply_variable_names(font, italic)
    recompute_head_bbox(font)
    font["OS/2"].recalcAvgCharWidth(font)
    return font


def bake_direction(font: TTFont) -> int:
    """Make the Atlassian app-face alternates the default drawings.

    Each affected glyph keeps its name, so Unicode coverage stays put.
    The alternate glyph is left in place, which makes the OpenType
    feature a no-op instead of a second design.
    """
    pairs = direction_pairs(font)
    if not pairs:
        return 0
    glyf = font["glyf"]
    hmtx = font["hmtx"].metrics
    gvar = font["gvar"].variations
    hvar = font["HVAR"].table.AdvWidthMap.mapping
    names = {name for pair in pairs for name in pair}
    saved_glyf = {name: glyf[name] for name in names}
    saved_hmtx = {name: hmtx[name] for name in names}
    saved_gvar = {name: gvar.get(name) for name in names}
    saved_hvar = {name: hvar.get(name) for name in names}
    for source, target in pairs:
        glyf[source] = deepcopy(saved_glyf[target])
        hmtx[source] = saved_hmtx[target]
        if source in gvar:
            del gvar[source]
        if saved_gvar[target] is not None:
            gvar[source] = deepcopy(saved_gvar[target])
        if saved_hvar[target] is not None:
            hvar[source] = saved_hvar[target]
    copy_gpos_records(font, pairs)
    return len(pairs)


def direction_pairs(font: TTFont) -> list[tuple[str, str]]:
    gsub = font["GSUB"].table
    maps = []
    for tag in DIRECTION_FEATURES:
        mapping = {}
        for record in gsub.FeatureList.FeatureRecord:
            if record.FeatureTag != tag:
                continue
            for index in record.Feature.LookupListIndex:
                lookup = gsub.LookupList.Lookup[index]
                for subtable in lookup.SubTable:
                    table = getattr(subtable, "ExtSubTable", subtable)
                    found = getattr(table, "mapping", None)
                    if found:
                        mapping.update(found)
        maps.append(mapping)
    order = set(font.getGlyphOrder())
    sources = set().union(*maps) if maps else set()
    pairs = []
    for source in sources:
        if source not in order:
            continue
        target = source
        for mapping in maps:
            target = mapping.get(target, target)
        if target != source and target in order:
            pairs.append((source, target))
    return pairs


def copy_gpos_records(font: TTFont, pairs: list[tuple[str, str]]) -> None:
    gpos = font["GPOS"].table
    for lookup in gpos.LookupList.Lookup:
        for subtable in lookup.SubTable:
            table = getattr(subtable, "ExtSubTable", subtable)
            for coverage_name, array_name, record_name in (
                ("BaseCoverage", "BaseArray", "BaseRecord"),
                ("MarkCoverage", "MarkArray", "MarkRecord"),
                ("LigatureCoverage", "LigatureArray", "LigatureAttach"),
            ):
                coverage = getattr(table, coverage_name, None)
                array = getattr(table, array_name, None)
                if coverage is None or array is None or not hasattr(coverage, "glyphs"):
                    continue
                glyphs = list(coverage.glyphs)
                index = {name: i for i, name in enumerate(glyphs)}
                records = getattr(array, record_name)
                saved = {name: deepcopy(records[index[name]]) for name in glyphs}
                for source, target in pairs:
                    if source in saved and target in saved:
                        records[index[source]] = deepcopy(saved[target])


def tighten(font: TTFont) -> tuple[int, list[tuple[str, int, int]]]:
    """Tighten every advance that still has right sidebearing to spare.

    Glyphs that already share a width keep sharing it, except a variant
    that is already overflowing its box. Marks are not touched.
    """
    hmtx = font["hmtx"].metrics
    watch = ("n", "o", "H", "a", "e", "space", "zero.tf", "one.tf", "four.tf")
    before = {name: hmtx[name][0] for name in watch if name in hmtx}
    groups: dict[int, list[str]] = defaultdict(list)
    for name in font.getGlyphOrder():
        advance, _lsb = hmtx[name]
        if advance > 0:
            groups[advance].append(name)

    changed = 0
    for names in groups.values():
        eligible = [name for name in names if spare_right(font, name) > 0]
        if not eligible:
            continue
        cut = min(TRACK, min(spare_right(font, name) for name in eligible))
        if cut <= 0:
            continue
        for name in eligible:
            advance, lsb = hmtx[name]
            updated = advance - cut
            if updated < 1:
                raise SystemExit(f"Refusing negative advance on {name}")
            hmtx[name] = (updated, lsb)
            changed += 1

    for name, (advance, _lsb) in hmtx.items():
        if advance < 0 or advance > 65535:
            raise SystemExit(f"Advance out of range on {name}: {advance}")
    return changed, [(name, old, hmtx[name][0]) for name, old in before.items()]


def spare_right(font: TTFont, name: str) -> int:
    advance, _lsb = font["hmtx"][name]
    glyph = font["glyf"][name]
    # Combining marks often use a 1-unit advance with ink left of x=0.
    if advance < 80:
        return 0
    if glyph.numberOfContours == 0 and not glyph.isComposite():
        if advance < 200:
            return 0
        keep = max(FLOOR, int(advance * 0.8))
        return max(0, advance - keep)
    x_max = getattr(glyph, "xMax", None)
    if x_max is None or x_max <= 0:
        return 0
    return max(0, advance - x_max - FLOOR)


def set_gasp(font: TTFont) -> None:
    gasp = newTable("gasp")
    gasp.version = 1
    gasp.gaspRange = {0xFFFF: GASP_SMOOTH}
    font["gasp"] = gasp


def apply_common_metadata(font: TTFont, italic: bool) -> None:
    head = font["head"]
    head.fontRevision = 1.3
    head.macStyle = ITALIC_BIT if italic else 0
    os2 = font["OS/2"]
    os2.achVendID = VENDOR
    os2.fsType = 0
    os2.fsSelection = (ITALIC_BIT if italic else REGULAR_BIT) | USE_TYPO_METRICS
    os2.usWeightClass = 400
    set_name(font, 0, COPYRIGHT)
    set_name(font, 5, f"Version {VERSION}")
    set_name(font, 7, TRADEMARK)
    set_name(font, 8, MANUFACTURER)
    set_name(font, 9, DESIGNER)
    set_name(font, 10, DESCRIPTION)
    set_name(font, 11, LICENSE_URL)
    set_name(font, 12, DESIGNER_URL)
    set_name(font, 13, LICENSE)
    set_name(font, 14, LICENSE_URL)


def apply_variable_names(font: TTFont, italic: bool) -> None:
    prefix = f"{PS_FAMILY}VariableItalic" if italic else f"{PS_FAMILY}Variable"
    style = "Italic" if italic else "Regular"
    full = f"{VARIABLE_FAMILY} {style}" if italic else VARIABLE_FAMILY
    for rec in list(font["name"].names):
        text = rec.toUnicode()
        updated = (
            text.replace("InterVariableItalic", prefix)
            .replace("InterVariable", prefix)
            .replace("Inter Variable", VARIABLE_FAMILY)
        )
        if updated != text:
            font["name"].setName(
                updated, rec.nameID, rec.platformID, rec.platEncID, rec.langID
            )
    set_name(font, 1, VARIABLE_FAMILY)
    set_name(font, 2, style)
    set_name(font, 3, f"{VERSION};{VENDOR};{prefix}")
    set_name(font, 4, full)
    set_name(font, 6, prefix)
    set_name(font, 16, VARIABLE_FAMILY)
    set_name(font, 17, style)
    set_name(font, 25, prefix)


def family_vertical_clip(roman: TTFont, italic: TTFont) -> tuple[int, int]:
    y_max = 0
    y_min = 0
    for font in (roman, italic):
        low, high = glyph_y_bounds(font)
        y_min = min(y_min, low)
        y_max = max(y_max, high)
        for weight, opsz in ((100, 32), (900, 32), (900, 14)):
            inst = instantiateVariableFont(
                font, {"wght": weight, "opsz": opsz}, static=True, optimize=False
            )
            low, high = glyph_y_bounds(inst)
            y_min = min(y_min, low)
            y_max = max(y_max, high)
            del inst
    os2 = roman["OS/2"]
    ascent = max(y_max, os2.sTypoAscender)
    descent = max(-y_min, -os2.sTypoDescender)
    return int(ascent), int(descent)


def glyph_y_bounds(font: TTFont) -> tuple[int, int]:
    glyf = font["glyf"]
    y_min = 0
    y_max = 0
    for name in font.getGlyphOrder():
        glyph = glyf[name]
        top = getattr(glyph, "yMax", None)
        bottom = getattr(glyph, "yMin", None)
        if top is None or bottom is None:
            continue
        y_max = max(y_max, top)
        y_min = min(y_min, bottom)
    return y_min, y_max


def apply_vertical_clip(font: TTFont, ascent: int, descent: int) -> None:
    # Typo and hhea metrics stay on Inter's line box so CSS line-height
    # matches across macOS, modern Windows, and browsers. usWinAscent
    # covers the real outlines so older Windows GDI does not clip accents.
    os2 = font["OS/2"]
    os2.usWinAscent = ascent
    os2.usWinDescent = descent
    os2.fsSelection |= USE_TYPO_METRICS
    hhea = font["hhea"]
    hhea.ascent = os2.sTypoAscender
    hhea.descent = os2.sTypoDescender
    hhea.lineGap = os2.sTypoLineGap


def finalize_static(font, weight: int, weight_name: str, italic: bool, ascent: int, descent: int) -> None:
    for tag in ("fvar", "gvar", "HVAR", "MVAR", "avar", "cvar", "STAT"):
        if tag in font:
            del font[tag]
    style = style_name(weight_name, italic)
    legacy_family, legacy_style = legacy_names(weight, weight_name, italic)
    ps = file_stem(weight_name, italic)
    full = FAMILY if style == "Regular" else f"{FAMILY} {style}"
    set_name(font, 1, legacy_family)
    set_name(font, 2, legacy_style)
    set_name(font, 3, f"{VERSION};{VENDOR};{ps}")
    set_name(font, 4, full)
    set_name(font, 5, f"Version {VERSION}")
    set_name(font, 6, ps)
    set_name(font, 16, FAMILY)
    set_name(font, 17, style)
    drop_name(font, 25)

    selection = USE_TYPO_METRICS
    mac = 0
    if italic:
        selection |= ITALIC_BIT
        mac |= ITALIC_BIT
    if weight == 700:
        selection |= BOLD_BIT
        mac |= 1 << 1
    elif weight == 400 and not italic:
        selection |= REGULAR_BIT
    os2 = font["OS/2"]
    os2.fsSelection = selection
    os2.usWeightClass = weight
    os2.fsType = 0
    os2.achVendID = VENDOR
    font["head"].macStyle = mac
    font["head"].fontRevision = 1.2
    setMacOverlapFlags(font["glyf"])
    set_gasp(font)
    apply_vertical_clip(font, ascent, descent)
    recompute_head_bbox(font)
    os2.recalcAvgCharWidth(font)


def style_name(weight_name: str, italic: bool) -> str:
    if italic and weight_name == "Regular":
        return "Italic"
    if italic:
        return f"{weight_name} Italic"
    return weight_name


def file_stem(weight_name: str, italic: bool) -> str:
    if italic and weight_name == "Regular":
        return f"{PS_FAMILY}-Italic"
    if italic:
        return f"{PS_FAMILY}-{weight_name}Italic"
    return f"{PS_FAMILY}-{weight_name}"


def legacy_names(weight: int, weight_name: str, italic: bool) -> tuple[str, str]:
    """Windows GDI only understands Regular, Italic, Bold, and Bold Italic."""
    if weight in (400, 700):
        family = FAMILY
        if weight == 700 and italic:
            return family, "Bold Italic"
        if weight == 700:
            return family, "Bold"
        if italic:
            return family, "Italic"
        return family, "Regular"
    family = f"{FAMILY} {weight_name}"
    return family, ("Italic" if italic else "Regular")


def set_name(font: TTFont, name_id: int, text: str) -> None:
    name = font["name"]
    slots = {
        (rec.platformID, rec.platEncID, rec.langID)
        for rec in name.names
        if rec.nameID == name_id
    }
    if not slots:
        slots = {(3, 1, 0x409)}
    for platform, encoding, language in slots:
        name.setName(text, name_id, platform, encoding, language)


def drop_name(font: TTFont, name_id: int) -> None:
    font["name"].names = [rec for rec in font["name"].names if rec.nameID != name_id]


def recompute_head_bbox(font: TTFont) -> None:
    glyf = font["glyf"]
    x_min = y_min = x_max = y_max = None
    for name in font.getGlyphOrder():
        glyph = glyf[name]
        left = getattr(glyph, "xMin", None)
        if left is None:
            continue
        right, bottom, top = glyph.xMax, glyph.yMin, glyph.yMax
        x_min = left if x_min is None else min(x_min, left)
        x_max = right if x_max is None else max(x_max, right)
        y_min = bottom if y_min is None else min(y_min, bottom)
        y_max = top if y_max is None else max(y_max, top)
    head = font["head"]
    head.xMin, head.yMin, head.xMax, head.yMax = x_min, y_min, x_max, y_max


WEB_LATIN = (
    "U+0000-00FF,U+0131,U+0152-0153,U+02BB-02BC,U+02C6,U+02DA,U+02DC,"
    "U+0304,U+0308,U+0329,U+2000-206F,U+20AC,U+2122,U+2190-2193,U+2212,"
    "U+2215,U+FEFF,U+FFFD"
)
WEB_LATIN_EXT = (
    "U+0100-02AF,U+1E00-1EFF,U+2020,U+20A0-20AB,U+20AD-20CF,U+2113,"
    "U+2C60-2C7F,U+A720-A7FF"
)


def write_web_subsets() -> None:
    """Latin variable WOFF2 files for websites. Other scripts stay in the full fonts."""
    from fontTools.subset import Subsetter, Options, parse_unicodes

    web = OUT / "web"
    web.mkdir(parents=True, exist_ok=True)
    jobs = (
        (f"{PS_FAMILY}-Variable.ttf", WEB_LATIN, f"{PS_FAMILY}-latin.woff2"),
        (f"{PS_FAMILY}-Variable.ttf", WEB_LATIN_EXT, f"{PS_FAMILY}-latin-ext.woff2"),
        (f"{PS_FAMILY}-VariableItalic.ttf", WEB_LATIN, f"{PS_FAMILY}-Italic-latin.woff2"),
        (f"{PS_FAMILY}-VariableItalic.ttf", WEB_LATIN_EXT, f"{PS_FAMILY}-Italic-latin-ext.woff2"),
    )
    for source_name, unicodes, dest_name in jobs:
        font = TTFont(OUT / "variable" / source_name)
        options = Options()
        options.layout_features = ["*"]
        options.ignore_missing_unicodes = True
        subsetter = Subsetter(options=options)
        subsetter.populate(unicodes=parse_unicodes(unicodes))
        subsetter.subset(font)
        font.flavor = "woff2"
        dest = web / dest_name
        font.save(dest)
        print(f"  web {dest_name} {dest.stat().st_size // 1024}KB")


def write_font(font: TTFont, ttf: Path, woff2: Path, woff: Path | None = None) -> None:
    font.flavor = None
    font.save(ttf)
    packed = TTFont(ttf)
    packed.flavor = "woff2"
    packed.save(woff2)
    if woff is not None:
        legacy = TTFont(ttf)
        legacy.flavor = "woff"
        legacy.save(woff)


def write_css(static_faces: list[tuple[int, bool, str]]) -> None:
    CSS_PATH.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "/* Chintan Sans. SIL Open Font License 1.1. See ../OFL.txt.",
        "   Use Chintan Sans Variable where the browser understands variable fonts.",
        "   Chintan Sans is the static fallback for older browsers. */",
        "",
        "@font-face {",
        f'  font-family: "{VARIABLE_FAMILY}";',
        "  font-style: normal;",
        "  font-weight: 100 900;",
        "  font-display: swap;",
        f'  src: url("../fonts/variable/{PS_FAMILY}-Variable.woff2") format("woff2"),',
        f'       url("../fonts/variable/{PS_FAMILY}-Variable.ttf") format("truetype");',
        "}",
        "@font-face {",
        f'  font-family: "{VARIABLE_FAMILY}";',
        "  font-style: italic;",
        "  font-weight: 100 900;",
        "  font-display: swap;",
        f'  src: url("../fonts/variable/{PS_FAMILY}-VariableItalic.woff2") format("woff2"),',
        f'       url("../fonts/variable/{PS_FAMILY}-VariableItalic.ttf") format("truetype");',
        "}",
        "",
    ]
    for weight, italic, stem in static_faces:
        style = "italic" if italic else "normal"
        lines.extend(
            [
                "@font-face {",
                f'  font-family: "{FAMILY}";',
                f"  font-style: {style};",
                f"  font-weight: {weight};",
                "  font-display: swap;",
                f'  src: url("../fonts/static/{stem}.woff2") format("woff2"),',
                f'       url("../fonts/static/{stem}.woff") format("woff"),',
                f'       url("../fonts/static/{stem}.ttf") format("truetype");',
                "}",
            ]
        )
    lines.extend(
        [
            "",
            ".chintan {",
            f'  font-family: "{VARIABLE_FAMILY}", "{FAMILY}", sans-serif;',
            "  font-synthesis: none;",
            "  font-optical-sizing: auto;",
            "}",
            ".chintan-data {",
            '  font-feature-settings: "ss02" 1, "tnum" 1;',
            "  font-variant-numeric: tabular-nums;",
            "}",
            ".chintan-single-story {",
            '  font-feature-settings: "cv11" 1;',
            "}",
            "",
        ]
    )
    CSS_PATH.write_text("\n".join(lines))


def check_direction(font: TTFont, label: str, check) -> None:
    eye = font["glyf"]["i"]
    check(
        eye.isComposite() and any(component.glyphName == "uni0307.ss07" for component in eye.components),
        f"{label} i does not use the square dot",
    )
    check(font["glyf"]["G"].numberOfContours == 2, f"{label} G has no spur")
    check(font["glyf"]["I"].xMax > 600, f"{label} I is not the wide serif form")
    check(
        font["glyf"]["quoteleft"].xMax == font["glyf"]["quoteleft.ss08"].xMax,
        f"{label} quotes are not the square form",
    )


def validate(roman, italic, win_ascent, win_descent, variable_files, static_dir, static_faces) -> None:
    problems = []

    def check(condition: bool, message: str) -> None:
        if not condition:
            problems.append(message)

    advances = [roman["hmtx"][f"{name}.tf"][0] for name in ("zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine")]
    check(len(set(advances)) == 1, f"tabular figures diverged: {advances}")
    check("Inter" not in roman["name"].getDebugName(1), "variable family still contains Inter")
    check(roman["name"].getDebugName(1) == VARIABLE_FAMILY, "unexpected variable family name")
    check(italic["head"].macStyle & ITALIC_BIT, "italic variable font is not marked italic")
    check(roman["OS/2"].fsType == 0, "font is not installable")
    check(roman["OS/2"].fsSelection & USE_TYPO_METRICS, "typo metrics bit is off")
    check("gasp" in roman and roman["gasp"].gaspRange.get(0xFFFF) == GASP_SMOOTH, "gasp table missing")
    check(roman["glyf"]["a"].flags[0] & 0x40, "macOS overlap flag missing on a")
    cmap = roman.getBestCmap()
    for char in ("A", "a", "é", "ế", "Я", "Ω", "€"):
        check(ord(char) in cmap, f"missing {char}")
    check(roman["OS/2"].usWinAscent >= roman["head"].yMax, "win ascent clips outlines")
    check(roman["OS/2"].usWinDescent >= -roman["head"].yMin, "win descent clips outlines")
    check(roman["OS/2"].usWinAscent == win_ascent, "clip ascent mismatch")
    check(roman["hhea"].ascent == roman["OS/2"].sTypoAscender, "hhea and typo metrics differ")
    check(roman["hmtx"]["n"][0] < 1210, "spacing was not tightened")
    check_direction(roman, "roman", check)
    check_direction(italic, "italic", check)
    check(len({roman["hmtx"][name][0] for name in ("zero.tf", "one.tf", "eight.tf")}) == 1, "tabular set broke")

    for ttf, woff2 in variable_files:
        opened = TTFont(woff2)
        check(opened["name"].getDebugName(1) == VARIABLE_FAMILY, f"{woff2.name} failed to reload")
        check(woff2.stat().st_size < ttf.stat().st_size, f"{woff2.name} is not smaller than the ttf")

    regular = TTFont(static_dir / f"{file_stem('Regular', False)}.ttf")
    bold_italic = TTFont(static_dir / f"{file_stem('Bold', True)}.ttf")
    medium = TTFont(static_dir / f"{file_stem('Medium', False)}.ttf")
    check(regular["name"].getDebugName(1) == FAMILY, "static family name")
    check(regular["name"].getDebugName(2) == "Regular", "static regular style")
    check(regular["name"].getDebugName(16) == FAMILY, "typographic family")
    check("fvar" not in regular, "static font still has fvar")
    check(medium["name"].getDebugName(1) == f"{FAMILY} Medium", "medium legacy family")
    check(medium["name"].getDebugName(2) == "Regular", "medium legacy style")
    check(medium["name"].getDebugName(17) == "Medium", "medium typographic style")
    check(medium["OS/2"].usWeightClass == 500, "medium weight class")
    check(bold_italic["name"].getDebugName(2) == "Bold Italic", "bold italic style")
    check(bold_italic["OS/2"].fsSelection & ITALIC_BIT, "bold italic bit")
    check(bold_italic["OS/2"].fsSelection & BOLD_BIT, "bold bit")
    check(bold_italic["post"].italicAngle < 0, "italic angle")
    for _weight, _italic, stem in static_faces:
        for ext in (".ttf", ".woff2", ".woff"):
            path = static_dir / f"{stem}{ext}"
            check(path.is_file() and path.stat().st_size > 1000, f"missing {path.name}")
    reserved = ("Inter", "Inter Variable", "InterVariable")
    for font in (regular, medium, bold_italic):
        for name_id in (1, 2, 4, 6, 16, 17):
            value = font["name"].getDebugName(name_id) or ""
            check(value not in reserved, f"reserved name in {value}")
    if problems:
        raise SystemExit("Validation failed:\n- " + "\n- ".join(problems))
    print("Validation passed")
    print(f"  regular a advance {regular['hmtx']['a'][0]}")
    print(f"  tabular figure advance {advances[0]}")
    print(f"  variable woff2 {variable_files[0][1].stat().st_size} bytes")
    print(f"  regular woff2 {(static_dir / (file_stem('Regular', False) + '.woff2')).stat().st_size} bytes")


if __name__ == "__main__":
    main()
