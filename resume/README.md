# Résumé — Nisandre Stewart

One-page résumé built on the [Awesome-CV](https://github.com/posquit0/Awesome-CV)
LaTeX template (CC BY-SA 4.0).

| File | What it is |
| --- | --- |
| `nisandre-stewart-resume.tex` | The résumé source — this is the file you edit |
| `awesome-cv.cls` | The Awesome-CV document class (see *Local changes* below) |
| `nisandre-stewart-resume.pdf` | The compiled one-page result |
| `AWESOME-CV-LICENCE` | Upstream template licence |

## Compiling on Overleaf

1. Create a blank project.
2. Upload **both** `nisandre-stewart-resume.tex` and `awesome-cv.cls`.
3. Set the main document to `nisandre-stewart-resume.tex`
   (file menu ▸ *Set as main document*).
4. **Menu ▸ Compiler ▸ LuaLaTeX** (or XeLaTeX). It will not build with
   pdfLaTeX — the template uses `fontspec` and needs a Unicode engine.

## Compiling locally

Needs a TeX installation with `fontspec`, `fontawesome5` (or `fontawesome6`),
and the Source Sans 3 + Roboto fonts installed system-wide.

```sh
make          # or: lualatex nisandre-stewart-resume.tex
```

On Debian/Ubuntu the TeX side is:

```sh
sudo apt install texlive-luatex texlive-latex-extra texlive-fonts-extra lmodern fonts-roboto
```

Source Sans 3 is not packaged, so fetch the OTFs from
[adobe-fonts/source-sans](https://github.com/adobe-fonts/source-sans/releases),
drop them in `/usr/local/share/fonts/`, and run `fc-cache -f`.

## Local changes to `awesome-cv.cls`

The class is upstream Awesome-CV with three portability edits, each marked in
the file as a local modification:

- **Font Awesome 5 fallback.** Upstream requires `fontawesome6`; if the TeX
  installation only ships `fontawesome5`, the class loads that instead and
  aliases the handful of icon macros Font Awesome renamed between v5 and v6.
- **Engine guard.** `Renderer=HarfBuzz` is a LuaTeX feature, so it is now only
  set under LuaTeX. This lets the document build under XeLaTeX as well.
- **Font fallback.** Falls back Source Sans 3 → Source Sans Pro → Latin Modern
  Sans, warning rather than failing when the preferred fonts are absent. Layout
  is tuned for Source Sans 3; the Latin Modern fallback runs wider and will
  push the résumé onto a second page.

## Keeping it to one page

The layout is tuned to fill exactly one letter-size page. If you add a bullet,
something has to come out. The levers, roughly in order of how much room they
buy:

- number of bullets per role
- `\geometry{...}` margins in the preamble
- `\renewcommand{\acvSectionTopSkip}{...}` in the preamble
- the `10pt` class option

Check the page count after any edit — LaTeX will silently spill onto page two.
