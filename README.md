# Chintan Sans

Chintan Sans is a screen face for a product interface. It is a derivative of [Inter](https://github.com/rsms/inter) 4.2, aimed at the same kind of app face as Atlassian Sans. Inter is a Reserved Font Name, so this family has its own name. It is not Atlassian Sans, and Atlassian does not endorse it.

Atlassian documents their app face as Inter with a fixed set of alternates always on. Chintan Sans bakes those in:

- serif on the capital I
- spur on the capital G
- flat top on the 3
- alternate German double s
- square dots, punctuation, and quotes

Spacing stays a little tighter than Inter. Slashed zero and the tailed l stay optional, for tables and IDs.

## What changed

- Spacing is 48 font units tighter (about 0.4px at 16px) wherever an equal-width group can spare it. Tabular figures stay equal.
- Windows clip metrics cover Vietnamese and stacked accents, while the line box stays on Inter's typo metrics so macOS, modern Windows, and browsers share one line height.
- Unhinted glyphs use grayscale smoothing instead of grid fitting.
- Overlap flags are set so macOS and iOS fill overlapping contours.
- One variable font carries weight 100 to 900 and optical size 14 to 32. Static files cover older apps.

## Use it on a website

The light setup is one variable file, 99 KB, for every weight. See [docs/website.md](docs/website.md).

```html
<link rel="preload" href="/fonts/web/ChintanSans-latin.woff2" as="font" type="font/woff2" crossorigin>
<link rel="stylesheet" href="/css/chintan-web.css">
```

```css
body {
  font-family: "Chintan Sans", sans-serif;
  font-synthesis: none;
}
```

## Files

| Path | Use |
| --- | --- |
| `css/chintan-web.css` | Website stylesheet. See [docs/website.md](docs/website.md). |
| `fonts/web/` | Latin and Latin Extended variable WOFF2 files |
| `fonts/variable/*.ttf` | Install on Windows, macOS, and Linux |
| `fonts/static/` | One file per weight, for apps that ignore variable fonts |
| `css/chintan.css` | Full specimen stylesheet, not the website default |

Useful features already in the font:

- `cv11` single-story a (upright fonts)
- `ss02` disambiguation (serif I, tailed l, slashed zero)
- `tnum` tabular figures
- `opsz` optical size, from 14 (interface) to 32 (display)

## License

SIL Open Font License 1.1. See [OFL.txt](OFL.txt). You can bundle Chintan Sans with a product. You cannot sell the font files by themselves, and you cannot rename a modified version back to Inter.

Chintan Sans is not endorsed by Rasmus Andersson or the Inter project.

## Rebuild

Requires the `inter/` checkout next to this folder.

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python build.py
```

Open `specimen/index.html` through a local web server to review the family.
