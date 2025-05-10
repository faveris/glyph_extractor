from fontTools.ttLib import TTFont
from PIL import Image, ImageFont, ImageDraw
import cairosvg.surface
import cairosvg.bounding_box
import argparse
import io
import math
from multiprocessing import Process, freeze_support, cpu_count
import numpy as np
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
parser.add_argument('--glyph', type=str, help='Which glyph to extract', default=None)
parser.add_argument('--max-process', type=int, help='Max processes to use', default=None)
args = parser.parse_args()

fontPath = args.font
colored = not args.no_embed_color
fillColor = struct.unpack('BBBB', bytes.fromhex(args.fill_color))
outputDir = args.output
whichGlyph = ord(args.glyph) if args.glyph else None
maxProcessCount = args.max_process if args.max_process else cpu_count()

if not os.path.exists(outputDir):
    os.makedirs(outputDir)

def bleed(pixels):
    alpha = pixels[:, :, 3]
    height, width = alpha.shape

    maskFull = alpha == 255
    maskPartial = (alpha > 0) & (alpha < 255)

    padded = np.pad(maskFull, pad_width=1, mode='constant', constant_values=0)
    edgeMask = np.zeros_like(maskPartial, dtype=bool)

    for dy in (-1, 0, 1):
        for dx in (-1, 0, 1):
            if dx == 0 and dy == 0:
                continue
            neighbor = padded[1+dy:1+dy+height, 1+dx:1+dx+width]
            edgeMask |= maskPartial & neighbor

    coords = np.argwhere(edgeMask)
    if coords.size == 0:
        return False

    for y, x in coords:
        sumRgb = np.zeros(3, dtype=np.int32)
        count = 0
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                ny, nx = y + dy, x + dx
                if 0 <= ny < height and 0 <= nx < width:
                    if alpha[ny, nx] == 255:
                        sumRgb += pixels[ny, nx, :3]
                        count += 1
        if count > 0:
            avg_rgb = (sumRgb // count).astype(np.uint8)
            pixels[y, x, :3] = avg_rgb
            pixels[y, x, 3] = 255

    return True

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
def splitName(name):
    match = namePattern.search(name)
    if match != None:
        groups = match.groupdict()
        if 'name' in groups:
            integer = int(groups['name'], 16)
            subname = groups['subname'] or ''
            return (integer, subname)

def parseName(name):
    key = None
    try:
        (key, subname) = splitName(name)
        text = "" + chr(key) + subname
        filename = f"{hex(key) + subname}.png"
    except:
        text = name
        filename = f"{text}.png"    
    return (key, text, filename)

def extractCbdt(ttfont, glyphs):
    cbdt = ttfont.get("CBDT")
    if cbdt != None:
        png_signature = b"\x89PNG\r\n\x1a\n"
        for strikeData in cbdt.strikeData:
            for k, v in strikeData.items():
                (key, text, filename) = parseName(k)

                if whichGlyph and whichGlyph != key:
                    continue

                offset = v.data.find(png_signature)
                if offset == -1:
                    print(f"{text} -> unsupported format", file=sys.stderr)
                    continue

                try:
                    png_data = v.data[offset:]
                    with open(os.path.join(outputDir, filename), "wb") as f:
                        f.write(png_data)
                    print(f"{text} -> {filename}")
                    glyphs.discard(key)
                except Exception as err:
                    print(f"{text} -> {err}", file=sys.stderr)

def extractSbix(ttfont, glyphs, size):
    sbix = ttfont.get("sbix")
    if sbix != None:
        for glyph in sbix.strikes[size].glyphs.values():
            (key, text, filename) = parseName(glyph.glyphName)

            if whichGlyph and whichGlyph != key:
                continue

            if glyph.graphicType != 'png ':
                print(f"{text} -> unsupported format ({glyph.graphicType})", file=sys.stderr)
                continue

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
        cmap = ttfont.getBestCmap()
        for doc in svgs.docList:
            id = doc.startGlyphID
            name = ttfont.getGlyphName(id)
            key = None
            try:
                key = list(cmap.keys())[list(cmap.values()).index(name)]
                text = "" + chr(key)
                filename = f"{hex(key)}.png"
            except:
                (key, text, filename) = parseName(name)

            if whichGlyph and whichGlyph != key:
                continue

            try:
                extractSvgGlyph(doc.data, filename)
                print(f"{text} -> {filename}")
                glyphs.discard(key)
            except Exception as err:
                print(f"{text} -> {err}", file=sys.stderr)

def detectFontSize(ttfont):
    size = args.size
    sizes = None

    cblc = ttfont.get("CBLC")
    if cblc != None:
        sizes = list()
        for strikeData in cblc.strikes:
            sizes.append(strikeData.bitmapSizeTable.ppemY)

    sbix = ttfont.get("sbix")
    if sbix != None:
        sizes = list(sbix.strikes.keys())
    
    if sizes != None:
        sizes = list(set(sizes))
        sizes.sort()
        size = next((x for x in sizes if x >= size), None)
        if size == None:
            print(f"Can't open the font with size {args.size}. Possible sizes: {', '.join([str(value) for value in sizes])}. Please try to specify the size using --size parameter.", file=sys.stderr)
            sys.exit(1)

    return size

def chunkify(lst, numChunks, minChunkSize):
    total = len(lst)
    if total < minChunkSize:
        return [lst]

    numChunks = min(numChunks, total // minChunkSize)
    chunkSize = math.ceil(total / numChunks)

    chunks = []
    for i in range(0, total, chunkSize):
        chunks.append(lst[i:i + chunkSize])

    if len(chunks) > 1 and len(chunks[-1]) < minChunkSize:
        chunks[-2].extend(chunks[-1])
        chunks.pop()

    return chunks

def process_chunk(glyphs, fontPath, fontSize, colored, fillColor, outputDir):
    imagefont = ImageFont.truetype(fontPath, fontSize)
    for key in glyphs:
        text = chr(key)
        filename = f"{hex(key)}.png"
        try:
            (left, top, right, bottom) = imagefont.getbbox(text)
            width = right
            height = bottom

            if width <= 0 or height <= 0:
                print(f"{text} -> empty")
                continue

            img = Image.new('RGBA', size=(width, height))
            d = ImageDraw.Draw(img)

            d.text((0, 0), text, font=imagefont, embedded_color=colored, fill=fillColor)

            if img.getbbox() is None:
                print(f"{text} -> empty")
                continue

            if colored:
                pixels = np.array(img)
                while bleed(pixels):
                    pass
                img.paste(Image.fromarray(pixels))
                clear(img)
                d.text((0, 0), text, font=imagefont, embedded_color=colored, fill=fillColor)

            img.save(os.path.join(outputDir, filename))
            print(f"{text} -> {filename}")
        except Exception as err:
            print(f"{text} -> {err}", file=sys.stderr)

def main():
    with TTFont(fontPath, fontNumber=0) as ttfont:
        glyphs = set()
        if whichGlyph:
            glyphs.add(whichGlyph)
        else:
            cmap = ttfont.getBestCmap()
            for key in cmap:
                glyphs.add(key)

        size = detectFontSize(ttfont)
        if size != args.size:
            print(f"Using font size {size}")

        if colored:
            extractSvg(ttfont, glyphs)
            extractCbdt(ttfont, glyphs)
            extractSbix(ttfont, glyphs, size)

        if len(glyphs) == 0:
            sys.exit(0)

        chunks = chunkify(list(glyphs), maxProcessCount, 50)
        if len(chunks) > 1:
            processes = []
            for chunk in chunks:
                p = Process(target=process_chunk, args=(chunk, fontPath, size, colored, fillColor, outputDir))
                p.start()
                processes.append(p)

            for p in processes:
                p.join()
        else:
            process_chunk(chunks[0], fontPath, size, colored, fillColor, outputDir)

if __name__ == "__main__":
    freeze_support()
    main()