# starhash

A time-and-place signature for documents and artifacts, written as the sky.

<p align="center"><img src="examples/LICENSE.seal.svg" width="440" alt="A Starhash seal: the sky over Zürich on 28 August 2026, with a ring of ticks carrying a document's hash"></p>

Starhash takes a place, a time and a file, and produces a **seal**: a monochrome SVG of the sky as it stood over that place at that moment, with the file's hash bound to it. The seal can be checked against the file, and the place and time can be read back out of the drawing itself, with no key and no label, by anyone who knows the stars.

```bash
starhash sign contract.pdf --lat 47.3769 --lon 8.5417
starhash verify contract.pdf.seal.svg contract.pdf
starhash read contract.pdf.seal.svg
```

It has no runtime dependencies.

## Sealing a document

```bash
starhash sign contract.pdf --lat 47.3769 --lon 8.5417 --elevation 400
```

```
Sealed  contract.pdf
  at    47.37690°N 8.54170°E, 400 m
  on    2026-08-28T22:00:00Z
  seal  contract.pdf.seal.svg
  id    STARS-Ja6g-a7RJ-rtyh-erHa-Fn76-6q
```

The time defaults to now; pass `--date 2026-08-28T22:00:00Z` (UTC unless an offset is given) to seal for another moment. To avoid typing your position each time, set `STARHASH_LAT`, `STARHASH_LON` and optionally `STARHASH_ELEVATION`. `-o` chooses where the seal is written.

The seal is a drawing and nothing else. There is no hidden record, no text and no font; whatever a seal says, it says in its geometry:

- the **sky** inside the horizon circle, north at the top marked by a wedge, carries the place and time;
- a **ring of 128 ticks** around the horizon carries the document: read clockwise from north, a long tick is 1 and a short tick is 0, spelling the first 128 bits of the file's SHA-256.

Both survive printing. Coordinates are kept to five decimals (about a metre) and time to the second, so the same inputs always give the same seal, byte for byte. The `id` that `sign` prints is a short fingerprint of the exact place, time and document; it is not in the seal, so note it down if you want it.

### What each mark means

Every mark in the drawing carries information; none is ornament. There is no text and no font.

| Mark | Meaning |
| --- | --- |
| Heavy circle | the horizon |
| Small ring at the centre | the zenith, the point overhead |
| Two faint circles | altitudes of 60° and 30°, which give the scale of the projection |
| Wedge on the rim; three strokes | north; east, south and west |
| Dots in five sizes | stars, by brightness |
| Small eight-armed cross | the celestial pole; its height above the horizon is the latitude |
| Curved line | the ecliptic, the path of the Sun, Moon and planets |
| Strokes across it | the twelve signs, every 30°, longer at the equinoxes and solstices |
| Ram's horns | the vernal point, where the count of signs begins; its slow drift among the stars marks the century |
| Disc, part filled | the Moon and its phase, turned towards the Sun |
| Ringed point with a sign | a planet |
| Ring with a centre point, heavier | the Sun |
| Ticks in the rim | the document: 128 bits, clockwise from north, long for 1 |

## Checking a seal

```bash
starhash verify contract.pdf.seal.svg contract.pdf
```

```
Seal shows 47.37698°N 8.50423°E on 2026-08-28T22:00:09Z
  ±    0.00021° lat, 0.030° lon, 7 s
  [pass] drawing is a real sky, read as 2026-08-28T22:00:09Z
  [pass] document is the one in the tick ring
  [skip] no place and time stated, so not compared exactly
```

`verify` works from the drawing alone. It reads the place and time back, redraws that sky and requires every star and planet to be where it should, and compares the file with the tick ring. If you also know what the seal is supposed to say, state it and the drawing is compared against that exactly:

```bash
starhash verify contract.pdf.seal.svg contract.pdf --lat 47.3769 --lon 8.5417 --elevation 400 --date 2026-08-28T22:00:00Z
```

At the default size the drawing resolves a stated place to about a hundred metres and a stated time to the second.

The exit status is 0 if every check that ran passes, 1 if any fails, and 2 if a file cannot be read. The document argument is optional.

## Reading the sky back

```bash
starhash read contract.pdf.seal.svg
```

```
Read from the drawing alone (207 of 207 stars identified)
  place  47.37680°N 8.54235°E
  time   2026-08-28T22:00:00Z
  ±      0.00021° lat, 0.030° lon, 7 s
  from   Moon, Saturn
  ring   sha256 c92ac887811a72a4619b2083b3a89e14…
```

Give it a file as well (`starhash read seal.svg contract.pdf`) and it also checks the file against the tick ring, exiting 1 if they differ. This needs nothing but the drawing.

`read` is the decoding step on its own. The dots are matched to the star catalogue by their mutual angles, which gives latitude and sidereal time; the Moon, Sun and planets then act as clock hands that give the date, and longitude follows. It works on any Starhash drawing, with or without a ring. The date is searched between 1800 and 2200 unless `--from` and `--to` say otherwise.

How sharply a drawing fixes the time depends on what was above the horizon:

| In the sky | Time | Longitude |
| --- | --- | --- |
| Moon | seconds | a few hundredths of a degree |
| Sun, Mercury, Venus or Mars, no Moon | one to a few minutes | up to about a degree |
| Jupiter or Saturn only | minutes to hours | degrees to tens of degrees |
| none of them | not recoverable | not recoverable |

Latitude is always good to about 20 metres. The reading prints its own uncertainty. A slow planet returns to the same spot around its retrograde loop, so a seal showing only Jupiter or Saturn can fit two or three dates a few months apart; when that happens the reading lists the others.

## What a seal does and does not show

A seal is a **claim**, not a proof. `verify` shows that the drawing is a real sky and that the document is the one in its ring. It cannot show that the signer was at that place at that time: the sky of any place and any moment can be computed by anyone. If you need that, pair the seal with something that carries trust of its own, such as a cryptographic signature over the seal file or a public timestamp.

The ring holds 128 bits of the hash, which is ample against forging a second document for an existing seal. `read` and `verify` decode Starhash's own SVG; a printed seal carries everything needed, but reading a photograph or scan of one is not implemented yet.

## Scope

Starhash is a compact model for drawings, examples, and reproducible software experiments. It is not a navigation tool, a survey instrument, or a replacement for a precision ephemeris. The implementation uses low-order planetary elements, selected lunar terms, a small star catalogue, a compact sidereal-time polynomial using UTC as a UT1 proxy, and fixed atmospheric-refraction conditions. It does not apply UT1, ΔT, nutation, aberration, light-time, or stellar proper motion.

Readings are relative to this model, not to a precision ephemeris: the Moon here is within about an arcminute of its true place and the planets within about a tenth of a degree.

## Install

Python 3.9 or later; there are no runtime dependencies. To get the `starhash` command:

```bash
uv tool install git+https://github.com/gbrlpzz/star-hash
```

or `pipx install git+https://github.com/gbrlpzz/star-hash`, or `python3 -m pip install .` from a clone.

To run the tests from a clone:

```bash
python3 -m unittest discover tests
```

## Python API

```python
from star_hash import sign, verify, read_seal, starhash

seal = sign("contract.pdf", latitude=47.3769, longitude=8.5417,
            elevation_m=400.0, date="2026-08-28T22:00:00Z")
seal.save("contract.pdf.seal.svg")
print(seal.digest)                      # STARS-Ja6g-a7RJ-...

result = verify(seal.svg, "contract.pdf")           # from the drawing alone
print(result["ok"], result["checks"], result["reading"])

reading = read_seal(seal.svg)           # from the drawing alone
print(reading.latitude, reading.longitude, reading.time)

sky = starhash(47.3769, 8.5417, "2026-08-28T22:00:00Z")   # bare drawing, no document
sky.save("sky.svg")
```

`sign` and `verify` accept a path or raw bytes for the document. `date` accepts an ISO 8601 string, a `datetime`, a Julian Day number, or `None` for the current UTC time. `starhash seal --lat … --lon …` draws the bare sky from the command line.

## Paper

[`paper/starhash.pdf`](paper/starhash.pdf) is a short note on the model, the seal, the reader and their limits, with measured read-back accuracy. Its source is [`paper/starhash.tex`](paper/starhash.tex); build it with [Tectonic](https://tectonic-typesetting.github.io/): `cd paper && tectonic starhash.tex`.

## License

MIT License. See [`LICENSE`](LICENSE).
