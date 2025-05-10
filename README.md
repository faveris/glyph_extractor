## What is this?

Glyph Extractor is a small Python script for extracting font glyphs as PNG files. It supports TTF and OTF fonts and is capable of extracting all glyphs from them, including coloured emojis.

## Usage

* Clone this repo
* Install requirements with `pip install -r requirements.pip`
* Run the script `python extract_glyphs.py <path_to_font>`
* Find extracted glyphs in the `output` folder

Please note: if you want to extract glyphs with embedded colours (e.g. emojis) from an OTF font, you may also need to install Cairo binaries. You can do this with: `brew install cairo` on MacOS. Please see the [CairoSVG documentation](https://cairosvg.org/documentation/#installation) for other platforms.

## Features

* Extracts all possible glyphs from the font file including emoji variations (skin tones and others).
* Supports filling glyphs with specified color (use `--fill-color` argument). 
* Supports filling glyphs which have embedded colors (e.g. emojis). To do this use `--no-embed-color` argument, but note that fewer glyphs may be exported.
* Automatically determines valid font sizes (no `invalid pixel size` errors). 
* Exported glyphs are named by character hex value, including additional info for emoji variations.
* Can export a glyph for a specified character using `--glyph` parameter.

## Examples

Glyph Extractor was tested (and works!) on this emoji fonts:
* Apple Color Emoji (you can found it in `/System/Library/Fonts/Apple Color Emoji.ttc` if you are using MacOS)
* [Noto Emoji](https://github.com/googlefonts/noto-emoji)
* [FxEmoji](https://github.com/mozilla/fxemoji)
* [EmojiOne Color](https://github.com/adobe-fonts/emojione-color)

If you plan to use the extracted glyphs in your work, please make sure to respect the font's original license.