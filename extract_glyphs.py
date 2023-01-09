from fontTools.ttLib import TTFont
from PIL import Image, ImageFont, ImageDraw
import operator

fontPath = "FirefoxEmoji.ttf"
size = 100

def bleed(img):
    pixels = img.load()
    edge = set()
    width = img.size[0]
    height = img.size[1]
    for x in range(width):
        for y in range(height):
            if pixels[x, y][3] == 255:
                for i in range(max(0, x - 1), min(x + 2, width)):
                    for j in range(max(0, y - 1), min(y + 2, height)):
                        alpha = pixels[i, j][3]
                        if alpha > 0 and alpha < 255:
                            edge.add((i, j))

    for (x, y) in edge:
        color = (0, 0, 0, 0)
        count = 0
        for i in range(max(0, x - 1), min(x + 2, width)):
            for j in range(max(0, y - 1), min(y + 2, height)):
                if (pixels[i, j][3] == 255):
                    color = tuple(map(operator.add, color, pixels[i, j]))
                    count += 1

        if count > 0:
            color = tuple(map(operator.floordiv, color[:3], (count, count, count)))
            color = color + (255,)
            pixels[x, y] = color

    return len(edge) > 0

def clear(img):
    pixels = img.load()
    width = img.size[0]
    height = img.size[1]
    for x in range(width):
        for y in range(height):
            pixels[x, y] = pixels[x, y][:3] + (0,)

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

        while bleed(img): pass
        clear(img)
        d.text((0, 0), text, font=imagefont, embedded_color=True)

        print(f"{text} -> {filename}")
        img.save(filename)