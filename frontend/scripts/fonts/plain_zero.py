"""Build "Atkinson Next Plain Zero": an unslashed zero for numbers.

Atkinson Hyperlegible Next only has a slashed zero. The design uses a plain
zero for amounts, volumes, readings and dates, and keeps the slashed zero in
letter-and-number codes (account and meter IDs). See docs/design/DESIGN_PLAN.md.

The slashed zero is 3 contours: the outer ring and two half-counters split
by the slash. This replaces the two halves with one counter: the outer ring
scaled into the halves' combined bounds and reversed (counters wind the
other way). The output holds only U+0030 (zero and tabular zero.tf) and is
layered over the main font with unicode-range in src/styles/fonts.css.

Licence: SIL OFL 1.1. The source declares no Reserved Font Name; the
modified font is renamed anyway and ships with the same licence.

Usage (needs fonttools and brotli):
    python plain_zero.py <atkinson-...-400-normal.woff2> <out.woff2> [family]
"""
import io
import sys

from fontTools import subset
from fontTools.ttLib import TTFont
from fontTools.ttLib.tables._g_l_y_f import GlyphCoordinates


def main(src, out, family='Atkinson Next Plain Zero'):
    font = TTFont(src)
    glyf = font['glyf']
    zero = glyf['zero']
    coords, ends, flags = zero.getCoordinates(glyf)
    starts = [0] + [e + 1 for e in ends[:-1]]
    contours = [(list(coords[s:e + 1]), list(flags[s:e + 1])) for s, e in zip(starts, ends)]
    if len(contours) != 3:
        sys.exit(f'expected 3 contours in zero, found {len(contours)}')
    (outer, outer_flags), (half_a, _), (half_b, _) = contours

    halves = half_a + half_b
    ix0, ix1 = min(p[0] for p in halves), max(p[0] for p in halves)
    iy0, iy1 = min(p[1] for p in halves), max(p[1] for p in halves)
    ox0, ox1 = min(p[0] for p in outer), max(p[0] for p in outer)
    oy0, oy1 = min(p[1] for p in outer), max(p[1] for p in outer)
    sx, sy = (ix1 - ix0) / (ox1 - ox0), (iy1 - iy0) / (oy1 - oy0)
    inner = [(round(ix0 + (x - ox0) * sx), round(iy0 + (y - oy0) * sy)) for x, y in outer]

    points = outer + inner[::-1]
    zero.coordinates = GlyphCoordinates(points)
    zero.flags = bytearray(outer_flags + outer_flags[::-1])
    zero.endPtsOfContours = [len(outer) - 1, len(points) - 1]
    zero.numberOfContours = 2
    zero.recalcBounds(glyf)

    for record in font['name'].names:
        if record.nameID in (1, 4, 16):
            record.string = family
        elif record.nameID == 6:
            record.string = family.replace(' ', '') + '-Regular'

    # Round-trip through plain TrueType before subsetting to WOFF2.
    buffer = io.BytesIO()
    font.flavor = None
    font.save(buffer)
    buffer.seek(0)
    font = TTFont(buffer)

    options = subset.Options()
    options.flavor = 'woff2'
    options.layout_features = ['tnum']
    options.name_IDs = ['*']
    subsetter = subset.Subsetter(options)
    subsetter.populate(unicodes=[0x30])
    subsetter.subset(font)
    font.flavor = 'woff2'
    font.save(out)
    print(f'{out}: counter fitted to x={ix0}..{ix1} y={iy0}..{iy1}')


if __name__ == '__main__':
    main(*sys.argv[1:])
