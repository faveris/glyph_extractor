from fontTools.ttLib import TTFont
from PIL import Image, ImageFont, ImageDraw
import cairosvg.surface
import cairosvg.bounding_box
import argparse
import io
import operator
import os
import re
import struct
import sys

parser = argparse.ArgumentParser()
parser.add_argument('font', type=str, help='Path to the font file')
parser.add_argument('--output', type=str, help='Path to the output folder', default='output')
parser.add_argument('--size', type=int, help='Preferable font size', default=100)
parser.add_argument('--no-embed-color', action='store_true', help="Don't use embedded colors of a glyph")
parser.add_argument('--fill-color', type=str, help='Fill color in hex format', default='000000FF')
args = parser.parse_args()

fontPath = args.font
size = args.size
colored = not args.no_embed_color
fillColor = struct.unpack('BBBB', bytes.fromhex(args.fill_color))
outputDir = args.output

if not os.path.exists(outputDir):
    os.makedirs(outputDir)

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

def convertBoundingBox(bbox):
    x = bbox[0]
    y = bbox[1]
    x_max = x + bbox[2]
    y_max = y + bbox[3]
    return (x, y, x_max, y_max)

namePattern = re.compile(r'(u|uni)(?P<name>[0-9a-fA-F]+)(?P<subname>.*)')
def parseName(name):
    match = namePattern.search(name)
    if match != None:
        groups = match.groupdict()
        if 'name' in groups:
            integer = int(groups['name'], 16)
            subname = groups['subname'] or ''
            return (integer, subname)

def readSbix(ttfont, glyphs):
    sbix = ttfont.get("sbix")
    if sbix != None:
        sizes = list(sbix.strikes.keys())
        sizes.sort()
        
        global size
        size = next((x for x in sizes if x >= size), None)
        if size == None:
            print(f"Can't open the font with size {args.size}. Possible sizes: {', '.join([str(value) for value in sizes])}", file=sys.stderr)
            sys.exit(1)

        if size != args.size:
            print(f"Using font size {size}")

        if not colored:
            return

        for glyph in sbix.strikes[size].glyphs.values():
            if glyph.graphicType == 'png ':
                key = None
                try:
                    (key, subname) = parseName(glyph.glyphName)
                    text = "" + chr(key) + subname
                    filename = f"{hex(key) + subname}.png"
                except:
                    text = glyph.glyphName
                    filename = f"{text}.png"

                try:
                    with open(os.path.join(outputDir, filename), "wb") as f: 
                        f.write(glyph.imageData)
                    print(f"{text} -> {filename}")
                    glyphs.discard(key)
                except Exception as err:
                    print(f"{text} -> {err}", file=sys.stderr)

def extractSvgGlyph(data, filename):
    tree = cairosvg.surface.Tree(bytestring=data)

    out = io.BytesIO()
    surface = cairosvg.surface.PNGSurface(tree, out, 96)

    bbox = None
    for node in tree.children:
        b = cairosvg.bounding_box.calculate_bounding_box(surface, node)
        if b != None:
            if bbox == None:
                bbox = b
                continue
            cur = convertBoundingBox(bbox)
            new = convertBoundingBox(b)
            x = min(cur[0], new[0])
            y = min(cur[1], new[1])
            max_x = max(cur[2], new[2])
            max_y = max(cur[3], new[3])
            bbox = (x, y, max_x - x, max_y - y)

    if (bbox != None):
        tree.update({"viewBox": ' '.join([str(value) for value in bbox])})
        out = io.BytesIO()
        surface = cairosvg.surface.PNGSurface(tree, out, 96)

    surface.finish()

    with open(os.path.join(outputDir, filename), "wb") as outfile:
        outfile.write(out.getbuffer())

def extractSvg(ttfont, glyphs):
    svgs = ttfont.get("SVG ")
    if svgs != None:
        for doc in svgs.docList:
            id = doc.startGlyphID
            name = ttfont.getGlyphName(id)
            key = None
            try:
                key = list(cmap.keys())[list(cmap.values()).index(name)]
                text = "" + chr(key)
                filename = f"{hex(key)}.png"
            except:
                try:
                    (key, subname) = parseName(name)
                    text = "" + chr(key) + subname
                    filename = f"{hex(key) + subname}.png"
                except:
                    text = name
                    filename = f"{name}.png"
            
            try:
                extractSvgGlyph(doc.data, filename)
                print(f"{text} -> {filename}")
                glyphs.discard(key)
            except Exception as err:
                print(f"{text} -> {err}", file=sys.stderr)

with TTFont(fontPath, fontNumber=0) as ttfont:
    glyphs = set()
    cmap = ttfont.getBestCmap()
    for key in cmap:
        glyphs.add(key)

    if colored:
        extractSvg(ttfont, glyphs)
    
    readSbix(ttfont, glyphs)

    if len(glyphs) == 0:
        sys.exit(0);

    imagefont = ImageFont.truetype(fontPath, size)

    for key in glyphs:
        text = "" + chr(key)
        filename = f"{hex(key)}.png"

        (left, top, right, bottom) = imagefont.getbbox(text)
        width = right
        height = bottom

        if width <= 0 or height <= 0:
            print(f"{text} -> empty")
            continue

        try:
            img = Image.new('RGBA', size=(width, height))
            d = ImageDraw.Draw(img)

            d.text((0, 0), text, font=imagefont, embedded_color=colored, fill=fillColor)
            while bleed(img): pass
            clear(img)
            d.text((0, 0), text, font=imagefont, embedded_color=colored, fill=fillColor)

            img.save(os.path.join(outputDir, filename))
            print(f"{text} -> {filename}")
        except Exception as err:
            print(f"{text} -> {err}", file=sys.stderr)