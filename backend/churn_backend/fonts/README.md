# Open Sans static PDF fonts

* Origin: the official [Google Fonts Open Sans directory](https://github.com/google/fonts/tree/8b0a1d0f5983c89bc2b93f1b5fb55f9e252744b5/ofl/opensans), revision `8b0a1d0f5983c89bc2b93f1b5fb55f9e252744b5`.
* Input: `OpenSans[wdth,wght].ttf`, internal version **3.003**. Source SHA-256: `36643644f318a812aab2d2ed3bb98f8cf0872527f835fe9398d95fe6b9adb878`.
* Licence: **SIL Open Font License 1.1**; the upstream copyright and complete licence are preserved verbatim in [OFL.txt](OFL.txt). Copyright 2020 The Open Sans Project Authors.
* Preparation: 11 November 2026, fontTools **4.68.0**, static instances at `wdth=100`, `wght=400` and `wght=700`, with names updated from the upstream STAT table. These TTFs contain no `fvar` table. The PostScript names are `OpenSansRoman-Regular` and `OpenSansRoman-Bold`; their weight classes are 400 and 700.
* Runtime: ReportLab registers these module-relative files as `BriefBody` and `BriefBold`. No fontTools, OS font installation, variable font engine or network access is needed at runtime.
* Verified glyphs in both faces: U+2212 minus, U+2013 en dash, U+00B7 middle dot, U+2022 bullet, U+2265 greater-than-or-equal, U+2018/U+2019/U+201C/U+201D curly quotes, and normal Malay/English text. Unsupported glyphs retain the explicit PDF font error.

Reproduce the static instances after downloading the pinned official variable TTF:

```python
from fontTools.ttLib import TTFont
from fontTools.varLib.instancer import instantiateVariableFont

for weight, style in [(400, 'Regular'), (700, 'Bold')]:
    source = TTFont('OpenSans[wdth,wght].ttf')
    static = instantiateVariableFont(source, {'wdth': 100, 'wght': weight},
                                     inplace=False, updateFontNames=True)
    assert 'fvar' not in static
    assert static['OS/2'].usWeightClass == weight
    static.save('OpenSans-' + style + '.ttf')
```

Generated asset SHA-256 values:

* `OpenSans-Regular.ttf`: `1ccd8617e514453139f9f37f2067cc8e3ccc8da726a53c9b8d53a39f84a6c613`
* `OpenSans-Bold.ttf`: `2cab467a4982410c9c13212d58f5ea4cdb759ff85bac33785c0054e49f51aa10`

The static font binaries and OFL licence ship with the application; source downloads and temporary preparation outputs do not.
