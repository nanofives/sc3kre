#!/usr/bin/env python3
"""Build one fixed airframe plus three lightweight, independently drawn rotor cels."""
from pathlib import Path
import struct
import sys
import math
from PIL import Image, ImageEnhance, ImageDraw
import sprite_codec as codec

GROUP = 0x739A61A0
ATTR = 0xFFFA9000
IMAGE = 0xFFFAA000
KEY = codec.TRANSPARENT
WIDTHS = (34, 48, 70, 100, 142)
VARIANTS = 34  # Two fixed bodies; three rotor phases in two headings.

def record_file(path, records):
    offset = 4 + (len(records) + 1) * 20
    with path.open("wb") as file:
        file.write(struct.pack("<I", codec.IXF_SIGNATURE))
        for group, instance, kind, payload in records:
            file.write(struct.pack("<IIIII", group, instance, kind, offset, len(payload)))
            offset += len(payload)
        file.write(bytes(20))
        for _, _, _, payload in records:
            file.write(payload)

def attribute(variant):
    data = bytearray(b"BIN\r")
    data.extend(struct.pack("<II", 1, codec.BASIC_CITY_SPRITE_CLSID))
    data.extend(struct.pack("<6B", 5, 4, 20, 20, 1, 0))
    data.extend(struct.pack("<IH", 0, 20))
    for zoom in range(5):
        for facing in range(4):
            frame = zoom * 4 + facing
            data.extend(struct.pack("<HII BHH", frame, 0,
                IMAGE + zoom * 256 + variant * 4 + facing, 0, 0, 0))
    return bytes(data)

def keyed(image,rotor=False):
    pixels=[]
    for y in range(image.height):
        for x in range(image.width):
            r,g,b,a=image.getpixel((x,y))
            # Remove faint source-background noise before the Bayer edge fade.
            threshold=48 if rotor else max(88,(64,176,208,112)[(x&1)+2*(y&1)])
            if a<threshold:pixels.append(KEY)
            else:
                value=((r>>3)<<11)|((g>>2)<<5)|(b>>3)
                pixels.append(value if value!=KEY else 0xF81E)
    return pixels

def sprite(source,zoom,heading):
    width=WIDTHS[zoom];height=round(width*.70)
    art=source.transpose(Image.Transpose.FLIP_LEFT_RIGHT) if heading else source.copy()
    art.thumbnail((width,height),Image.Resampling.LANCZOS)
    canvas=Image.new("RGBA",(width,height))
    canvas.alpha_composite(art,((width-art.width)//2,(height-art.height)//2))
    return ImageEnhance.Contrast(canvas).enhance(1.12)

def rotor_sprite(zoom,heading,phase,bounds):
    # Pure geometry: rotating narrow streaks in an isometric plane. No aircraft
    # pixels are animated, moved, regenerated or cut away between rotor frames.
    width=WIDTHS[zoom];height=round(width*.70);ss=4
    im=Image.new('RGBA',(width*ss,height*ss));draw=ImageDraw.Draw(im)
    scale=min(width/(bounds[2]-bounds[0]),height/(bounds[3]-bounds[1]))
    pad_x=(width-(bounds[2]-bounds[0])*scale)/2
    pad_y=(height-(bounds[3]-bounds[1])*scale)/2
    def point(x,y):
        px=pad_x+(x-bounds[0])*scale
        if heading:px=width-px
        return (px*ss,(pad_y+(y-bounds[1])*scale)*ss)
    angle=phase*math.pi/6
    # The rotor footprint stays constant; three phase cels cover a 90-degree
    # cycle of four equal blades. Modest trails soften the apparent cadence.
    for cx,cy,rx,ry,tilt in [(683,479,555,254,24),(1418,186,55,108,0)]:
        for arm in range(4):
            a=angle+arm*math.pi/2
            for trail,alpha in [(0.18,110),(0.10,165),(0.,240)]:
                aa=a-trail
                poly=[]
                for r,theta in [(.10,aa-.018),(1.,aa-.027),(1.,aa+.027),(.10,aa+.018)]:
                    x=rx*r*math.cos(theta);y=ry*r*math.sin(theta)+tilt*r*math.cos(theta)
                    poly.append(point(cx+x,cy+y))
                draw.polygon(poly,fill=(132,135,122,alpha))
    return im.resize((width,height),Image.Resampling.LANCZOS)

def shadow_sprite(zoom,core):
    # Two faint code-native ground ellipses avoid stipple and animated noise.
    width=WIDTHS[zoom]; height=round(width*.70); ss=4
    im=Image.new('RGBA',(width*ss,height*ss)); draw=ImageDraw.Draw(im)
    rx=width*(.19 if core else .25); ry=width*(.060 if core else .085)
    cx=width/2; cy=height/2
    draw.ellipse(((cx-rx)*ss,(cy-ry)*ss,(cx+rx)*ss,(cy+ry)*ss),fill=(24,28,32,255))
    return im.resize((width,height),Image.Resampling.LANCZOS)

# Manually checked sheet bounds and mast positions. Source sheet order of the
# two rear diagonal views is reversed relative to requested order.
DIRECTIONS = [
 ((0,110,535,365),(196,170),(496,167)),
 ((1330,45,1774,425),(1474,104),(1699,277)),
 ((975,40,1280,425),(1120,80),(1097,304)),
 ((540,45,940,425),(800,105),(604,283)),
 ((0,545,535,810),(344,614),(47,613)),
 ((540,445,950,870),(800,610),(609,518)),
 ((975,440,1290,887),(1120,610),(1140,487)),
 ((1330,445,1774,887),(1480,610),(1700,511)),
]
def body_and_rotor(sheet,zoom,heading,phase=None):
    width=WIDTHS[zoom];height=round(width*.90)
    box,hub,tail=DIRECTIONS[heading]
    scale=width/710.
    cx=width/2.;cy=height*.35
    if phase is None:
        art=sheet.crop(box)
        art=art.resize((round(art.width*scale),round(art.height*scale)),Image.Resampling.LANCZOS)
        im=Image.new('RGBA',(width,height))
        im.alpha_composite(art,(round(cx+(box[0]-hub[0])*scale),round(cy+(box[1]-hub[1])*scale)))
        return im
    ss=4;im=Image.new('RGBA',(width*ss,height*ss));draw=ImageDraw.Draw(im)
    tx=cx+(tail[0]-hub[0])*scale;ty=cy+(tail[1]-hub[1])*scale
    for hx,hy,rx,ry in [(cx,cy,width*.43,width*.165),(tx,ty,width*.026,width*.058)]:
        for arm in range(4):
            for trail,alpha in [(.18,110),(.10,165),(0.,240)]:
                a=phase*math.pi/6+arm*math.pi/2-trail
                poly=[((hx+rx*r*math.cos(a+t))*ss,(hy+ry*r*math.sin(a+t))*ss)
                      for r,t in [(.10,-.018),(1.,-.027),(1.,.027),(.10,.018)]]
                draw.polygon(poly,fill=(132,135,122,alpha))
    return im.resize((width,height),Image.Resampling.LANCZOS)

def main(destination):
    destination.mkdir(parents=True,exist_ok=True)
    previews=Path(__file__).resolve().parents[2]/'Preview'
    previews.mkdir(parents=True,exist_ok=True)
    sheet=Image.open(Path(__file__).with_name('apache-directions.png')).convert('RGBA')
    records=[];spans={}
    for zoom in range(5):
        for variant in range(VARIANTS):
            if variant>=32:im=shadow_sprite(zoom,variant==33)
            else:im=body_and_rotor(sheet,zoom,variant%8,None if variant<8 else (variant-8)//8)
            if zoom==4:im.save(previews/f'preview-variant-{variant}.png')
            for facing in range(4):
                iid=IMAGE+zoom*256+variant*4+facing
                ay=im.height//2 if variant>=32 else round(im.height*.35)+round(im.width*.05)
                anchor=(im.width//2,ay,im.width-im.width//2,im.height-ay)
                raw=codec.pack_rgb565(im.width,im.height,keyed(im,variant>=8))
                records.extend(((0,iid,0,codec.sprite_resource(im.width,im.height,raw)),
                                (0,iid,1,struct.pack('<4H',*anchor))))
                spans[iid]=anchor
    name='SC3KU_ApacheFlyover'
    record_file(destination/f'{name}.DAT',records)
    record_file(destination/f'{name}.IXF',[(GROUP,ATTR+i,0x6300,attribute(i)) for i in range(VARIANTS)])
    lines=['; Eight directional airframes, 24 rotor cels, two ground shadows']
    for instance,span in spans.items():lines.append(f'{instance:08X}, '+', '.join(map(str,span)))
    (destination/f'{name}.SII').write_bytes(('\r\n'.join(lines)+'\r\n').encode('ascii'))
    assert len(codec.read_ixf(destination/f'{name}.DAT'))==1360
    assert len(codec.read_ixf(destination/f'{name}.IXF'))==VARIANTS
    print('PASS: 680 images across five zooms and four camera banks; 34 attributes')

if __name__=='__main__':main(Path(sys.argv[1]))
