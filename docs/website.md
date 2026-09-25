# Use Chintan Sans on a website

Use the light build. One variable file covers weights 100 to 900. A typical English page downloads 99 KB. Italic and accented European text download extra files only when those characters appear.

Do not link `css/chintan.css` on a website. That file lists every static weight and is for the specimen, not for production.

## Files to copy

```
css/chintan-web.css
fonts/web/ChintanSans-latin.woff2
fonts/web/ChintanSans-latin-ext.woff2
fonts/web/ChintanSans-Italic-latin.woff2
fonts/web/ChintanSans-Italic-latin-ext.woff2
```

Keep that folder shape. The CSS points at `../fonts/web/`.

From another project you can skip the copy and load the published CSS:

```html
<link rel="stylesheet" href="https://cdn.jsdelivr.net/gh/chintan-diwakar/chintan-sans@v1.300/css/chintan-web.css">
```

## Preload the one file a page always needs

Put this in `<head>` before the stylesheet. Preload only the Latin roman file. Preloading italic or Latin Extended makes the page heavier for no benefit.

```html
<link rel="preload" href="/fonts/web/ChintanSans-latin.woff2" as="font" type="font/woff2" crossorigin>
<link rel="stylesheet" href="/css/chintan-web.css">
```

`crossorigin` is required. Without it the browser downloads the font twice.

If you use the jsDelivr URL, preload that same latin file from jsDelivr, with `crossorigin`.

## Set the family once

```css
body {
  font-family: "Chintan Sans", sans-serif;
  font-weight: 400;
  font-synthesis: none;
  font-optical-sizing: auto;
}

h1, h2 {
  font-weight: 560;
  letter-spacing: -0.03em;
}

strong, b {
  font-weight: 650;
}
```

`font-synthesis: none` stops the browser from painting a fake bold. Pick a real weight instead: 400 body, 500 labels, 600 buttons, 700 emphasis.

Italic is a normal `font-style: italic` or `<em>`. The italic file is fetched only for italic text.

## What the browser downloads

| Page text | Download |
| --- | --- |
| English, or other Latin text | `ChintanSans-latin.woff2`, 99 KB |
| Italic on that page | plus `ChintanSans-Italic-latin.woff2`, 108 KB |
| Vietnamese or accented Latin | plus the matching `latin-ext` file, 117 KB upright or 127 KB italic |

Weights do not add files. `font-weight: 300` and `font-weight: 700` come from the same variable file.

Greek and Cyrillic are not in the light build. For those, use `fonts/variable/ChintanSans-Variable.woff2` (about 344 KB) instead of the Latin subset.

## IDs and tables

The serif I, spurred G, flat-top 3, and square punctuation are already the default. For a tailed l and a slashed zero, add:

```css
.ids {
  font-feature-settings: "ss02" 1, "tnum" 1;
  font-variant-numeric: tabular-nums;
}
```

## Leave these out of a website

- The static TTF, WOFF, and WOFF2 files under `fonts/static/`. Those are for installing the font on a computer, or for an old browser that cannot read a variable font.
- A preload for every file.
- `font-family` lists that name both "Chintan Sans" and "Chintan Sans Variable". The light CSS uses one family name.
