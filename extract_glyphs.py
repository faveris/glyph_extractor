from fontTools.ttLib import TTFont
from PIL import Image, ImageFont, ImageDraw

fontPath = "FirefoxEmoji.ttf"
size = 100

with TTFont(fontPath, fontNumber=0) as ttfont:
    imagefont = ImageFont.truetype(fontPath, size)
    print(f"Opened {fontPath} with size {size}")

    for key in ttfont.getBestCmap().keys():
        text = "" + chr(key)
        filename = f"{hex(key)}.png"

        (left, top, right, bottom) = imagefont.getbbox(text)
        width = right
        height = bottom

        if width <= 0 or height <= 0:
            print(f"{text} -> empty")
            continue

        img = Image.new('RGBA', size=(width, height))
        d = ImageDraw.Draw(img)
        try:
            d.text((0, 0), text, font=imagefont, embedded_color=True)
        except OSError:
            print(f"{text} -> error")
            continue

        print(f"{text} -> {filename}")
        img.save(filename)