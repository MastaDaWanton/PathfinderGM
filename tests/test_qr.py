"""The QR encoder, and the one bug in it that no picture would have shown.

`pathfindergm/qr.py` is hand-rolled because `requirements.txt` says dependencies are the
expensive thing in a frozen build. The risk that buys is obvious: a QR code that is
structurally beautiful and unreadable looks exactly like one that works, and there is no
way to tell by eye. So it was cross-checked twice before these fixtures were frozen.

**What the cross-check found, 2026-09-17.** The format information was being written
least-significant-bit first. Every other part of the encoder was already byte-identical to
an independent implementation — bitstream, Reed-Solomon, interleaving, zigzag placement,
mask selection, all of it — and the codes were unreadable anyway, because the fifteen bits
that tell a scanner which mask was applied were backwards. `test_the_format_bits_match_the
_published_table` below is not the test that caught it (those values were right); the
placement is, via the frozen matrices.

**How the fixtures were verified.** Each matrix here was rendered and decoded by OpenCV's
`QRCodeDetector` — a decoder with no shared lineage with this code — and came back as
exactly the input string, for versions 1 through 6. They were also compared module by
module against `segno`. Neither library is a dependency of this project or of this suite:
they were installed into a throwaway virtualenv, used once, and thrown away. What is
committed is the verified output, which is why these are literals rather than a round
trip through the encoder that produced them.

One difference from segno is deliberate and is not a defect in either: where the data ends
exactly on a codeword boundary, this module emits the `0xEC` pad codeword that
ISO/IEC 18004 section 7.4.10 specifies and segno emits a zero byte. Pad codewords sit
after the terminator and are never interpreted, so both decode identically — OpenCV reads
both. A test asserting byte-identity with segno would therefore have been a test of a
coin-flip, which is why it is not here.
"""
from __future__ import annotations

import hashlib

import pytest

from pathfindergm import qr

# ISO/IEC 18004 Table C.1, error correction level M. Transcribed from the published
# table rather than computed, so a mistake in `_format_bits` cannot agree with itself.
FORMAT_M = [
    "101010000010010", "101000100100101", "101111001111100", "101101101001011",
    "100010111111001", "100000011001110", "100111110010111", "100101010100000",
]

# Verified by OpenCV's decoder, as described above. Rows are top to bottom, '1' is dark.
GOLDEN = {
    "A": (
        '111111101001001111111'
        '100000101111101000001'
        '101110100010101011101'
        '101110101101101011101'
        '101110100111001011101'
        '100000100101101000001'
        '111111101010101111111'
        '000000001101100000000'
        '101101110011101001011'
        '010110010101111001000'
        '110011101101000001101'
        '101101000001001111100'
        '100111100100100100100'
        '000000001011001001001'
        '111111101001100101000'
        '100000101100000110110'
        '101110100110111110001'
        '101110101111001111110'
        '101110101010101100000'
        '100000100010010100101'
        '111111101000010010000'),
    "http://192.168.1.14:8917/": (
        '1111111000010010001111111'
        '1000001000111001001000001'
        '1011101011010010101011101'
        '1011101010000100001011101'
        '1011101011111010001011101'
        '1000001010011011101000001'
        '1111111010101010101111111'
        '0000000010111001000000000'
        '1011111001010101101111100'
        '0111100000100110010000010'
        '1001011101010101001101011'
        '0101010100001000100010001'
        '1101111010101100001110111'
        '1110110110000110000001010'
        '1001011101011001010101011'
        '1011110000110001000001001'
        '1010001001011100111110100'
        '0000000011001110100011100'
        '1111111000000000101011111'
        '1000001010010011100011011'
        '1011101010011101111111100'
        '1011101010011011101110111'
        '1011101010100000010000101'
        '1000001001010010101111001'
        '1111111011000101011111111'),
    "http://192.168.1.14:54321/?k=ABCDEFGHJK": (
        '11111110110110110100101111111'
        '10000010010000001100001000001'
        '10111010101101100101001011101'
        '10111010011110100100101011101'
        '10111010001010110100101011101'
        '10000010110001000100101000001'
        '11111110101010101010101111111'
        '00000000011000011000100000000'
        '10100011000011011011000100101'
        '01000001100011001011011000011'
        '00101010101110110111101011101'
        '01001000110110101011001000000'
        '11100110110101111010011000001'
        '01011001110011001101011000111'
        '00011110110010011001110101001'
        '10101100101111001010100110000'
        '01110010100001011011011101001'
        '00010100010110001111001001111'
        '11100111111011110001000100001'
        '00111101110110110010001000000'
        '11001111011101111001111111010'
        '00000000101101101101100011101'
        '11111110110110011010101010001'
        '10000010010111010010100010011'
        '10111010010001011011111110001'
        '10111010001110001110100110001'
        '10111010111111010100000110111'
        '10000010000010000010100100000'
        '11111110101110011101101100001'),
}


def flat(matrix) -> str:
    return "".join("".join(str(cell) for cell in row) for row in matrix)


@pytest.mark.parametrize("mask", range(8))
def test_the_format_bits_match_the_published_table(mask):
    """Fifteen bits of BCH that a scanner reads before anything else.

    Computed here and transcribed there, so the two can only agree by being right."""
    assert f"{qr._format_bits(mask):015b}" == FORMAT_M[mask]


@pytest.mark.parametrize("text", sorted(GOLDEN))
def test_the_matrix_is_the_one_a_decoder_read_back(text):
    """The frozen output of a build whose codes OpenCV decoded to exactly these strings.

    This is the test that would have caught the format bits being written backwards: the
    encoder was otherwise byte-identical to an independent implementation and the codes
    were still unreadable, and nothing about the picture looked wrong."""
    assert flat(qr.matrix(text)) == GOLDEN[text]


def test_a_long_string_still_lands_on_the_version_that_was_verified():
    """Version 6, kept as a digest because 1,681 modules of literal would bury the file.
    Decoded by OpenCV to the same hundred characters."""
    m = qr.matrix("x" * 100)
    assert len(m) == 41
    assert hashlib.sha256(flat(m).encode()).hexdigest() == (
        "3b1cbac996b5a950f7fb084505c80f58f5a2d87789861f63eb6c2d0a2337e9d0")


# Each version's last byte that fits, and the first that does not. A byte-mode header is
# twelve bits — four of mode and eight of length — so the usable payload is
# (codewords * 8 - 12) // 8, which is why every boundary below is odd-looking rather than
# a round number.
@pytest.mark.parametrize("length,version", [
    (1, 1), (14, 1), (15, 2), (26, 2), (27, 3), (42, 3),
    (43, 4), (62, 4), (63, 5), (84, 5), (85, 6), (106, 6),
])
def test_the_smallest_version_that_fits_is_the_one_chosen(length, version):
    """Tested at both sides of every boundary, because an off-by-one here does not fail
    — it silently returns the next size up, and a bigger code than the data needs is one
    that is harder to scan from across a room, for nothing."""
    assert len(qr.matrix("x" * length)) == 17 + 4 * version


def test_too_much_data_refuses_rather_than_producing_something_unreadable():
    """The ceiling is version 6, and it is a real ceiling rather than a silent wrap.

    Versions 7 and up need a version-information block this module does not write. An
    encoder that ignored that would emit a symbol no scanner can read, which is the one
    failure mode a QR code must never have — it looks exactly like a working one."""
    with pytest.raises(qr.TooMuchToEncode):
        qr.matrix("x" * 200)


def test_the_finder_patterns_and_the_dark_module_are_where_a_scanner_looks():
    """The three corners a camera locks onto before it reads anything, and the one
    module the spec fixes as always dark."""
    m = qr.matrix("http://192.168.1.14:8917/")
    size = len(m)
    for top, left in ((0, 0), (0, size - 7), (size - 7, 0)):
        for r in range(7):
            for c in range(7):
                edge = r in (0, 6) or c in (0, 6)
                core = 2 <= r <= 4 and 2 <= c <= 4
                assert m[top + r][left + c] == (1 if (edge or core) else 0)
    assert m[size - 8][8] == 1


def test_the_svg_carries_a_quiet_zone_and_a_light_ground():
    """Four modules of margin, because a scanner may simply fail without them — and a
    light background, because these pages are near-black and a dark-on-dark code is one
    a camera never finds at all."""
    svg = qr.svg("http://192.168.1.14:8917/")
    size = len(qr.matrix("http://192.168.1.14:8917/"))
    assert f'viewBox="0 0 {size + 8} {size + 8}"' in svg
    assert 'fill="#f3e7c8"' in svg
