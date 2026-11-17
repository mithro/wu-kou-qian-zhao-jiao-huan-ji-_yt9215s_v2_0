"""Draw the debug-pin annotations on photo-u4-macro.jpg.

Writes lx-is601f-debug-pins-annotated.png next to this script. Needs Pillow and the DejaVu fonts.
Coordinates are pixels in photo-u4-macro.jpg, found by hand; see README.md.
"""
import sys
from PIL import Image, ImageDraw, ImageFont, ImageEnhance
import os
SP=os.path.dirname(os.path.abspath(__file__))+'/'
F='/usr/share/fonts/truetype/dejavu/'
def font(s,b=True): return ImageFont.truetype(F+('DejaVuSans-Bold.ttf' if b else 'DejaVuSans.ttf'),s)
UART=(255,170,40); SPI=(60,220,255); JTAG=(255,110,230); STRAP=(255,240,80); REF=(200,200,200); I2C=(140,255,140)
src=Image.open(SP+'photo-u4-macro.jpg').convert('RGB')
X0,Y0,X1,Y1=950,480,3072,2950
S=1.0
base=src.crop((X0,Y0,X1,Y1))
base=ImageEnhance.Brightness(base).enhance(1.08)
W,H=base.size
PANEL=1500; TOP=170
img=Image.new('RGB',(W+PANEL,H+TOP),(18,22,28))
img.paste(base,(0,TOP))
ov=Image.new('RGBA',img.size,(0,0,0,0)); od=ImageDraw.Draw(ov)
def P(x,y): return (x-X0, y-Y0+TOP)
# darken chip body
od.polygon([P(1200,1395),P(2470,1395),P(2500,1425),P(2500,2690),P(2470,2720),P(1200,2720),P(1170,2690),P(1170,1425)],fill=(0,0,0,150))
img=Image.alpha_composite(img.convert('RGBA'),ov).convert('RGB')
d=ImageDraw.Draw(img)
def topx(n): return 2430-38.4*(n-65)
def righty(n): return 2670-38.2*(n-33)
def otext(xy,t,f,fill,anchor='la',sw=3):
    d.text(xy,t,font=f,fill=fill,anchor=anchor,stroke_width=sw,stroke_fill=(0,0,0))
def vtext(x,y,t,f,fill):
    # text reading top-to-bottom starting at (x,y) centre-top
    bb=f.getbbox(t); w=bb[2]+8; h=bb[3]+10
    im=Image.new('RGBA',(w,h),(0,0,0,0)); dd=ImageDraw.Draw(im)
    dd.text((4,2),t,font=f,fill=fill+(255,),stroke_width=2,stroke_fill=(0,0,0,255))
    im=im.rotate(-90,expand=True)
    img.paste(im,(int(x-im.width/2),int(y)),im)
fp=font(23)
top=[ # pin, text, colour
 (67,'67  JTAG1_TDO* — no trace',JTAG),
 (70,'70  UART1_RX · DIS_SPIS',UART),
 (72,'72  JTAG0_TMS* (P4LED1)',JTAG),
 (73,'73  JTAG0_TCK*  (P3LED1)',JTAG),
 (74,'74  JTAG0_TDI* · EN_PWRLIGHT',JTAG),
 (75,'75  EN_SPIF strap  (P3LED0)',STRAP),
 (76,'76  UART1_TX · DIS_MCU strap',UART),
 (77,'77  DISAUTOLOAD strap (P2LED0)',STRAP),
 (78,'78  SPF1_SO  (P2LED1)',SPI),
 (79,'79  SPF1_SI — no trace',SPI),
 (81,'81  SPF1_CS · JTAG1_TMS*',SPI),
 (83,'83  SPF1_SCK · JTAG1_TCK* · EN_PHY',SPI),
 (84,'84  JTAG1_TDI*  (LED_DA)',JTAG),
 (87,'87  XTALO',REF),(88,'88  XTALI',REF),
 (89,'89  nRESET',REF),
 (90,'90  JTAG0_TDO* — no trace',JTAG),
 (91,'91  SCL / MDC',I2C),(92,'92  SDA / MDIO',I2C),
]
for n,t,c in top:
    x=topx(n); px,py=P(x,1296)
    d.ellipse((px-9,py-9,px+9,py+9),outline=c,width=4)
    d.line((px,py+9,px,py+118),fill=c,width=2)
    vtext(px,py+122,t,fp,c)
right=[
 (55,'SPF0_CS → R44   55',SPI),(54,'SPF0_SO → R89   54',SPI),
 (50,'SPF0_SI → R92   50',SPI),(49,'SPF0_SCK · SPF_MUX_SEL strap → R93   49',SPI),
 (47,'UART0_TX — no trace   47',UART),(46,'UART0_RX — no trace   46',UART),
]
for n,t,c in right:
    y=righty(n); px,py=P(2603,y)
    d.ellipse((px-9,py-9,px+9,py+9),outline=c,width=4)
    d.line((px-9,py,px-118,py),fill=c,width=2)
    otext((px-124,py),t,fp,c,'rm',2)
# pin 1
px,py=P(1247,2580); d.ellipse((px-48,py-48,px+48,py+48),outline=(255,255,255),width=4)
otext((px+60,py),'pin-1 dimple',font(26),(255,255,255),'lm')
px,py=P(1240,2772); otext((px,py+70),'pin 1',font(26),(255,255,255),'ma'); d.line((px,py+66,px,py+12),fill=(255,255,255),width=3)
# corner pin numbers
fs=font(22)
otext(P(2430,1235),'65',fs,(255,255,255),'mm'); otext(P(1240,1235),'96',fs,(255,255,255),'mm')
otext(P(2668,righty(64)),'64',fs,(255,255,255),'lm'); otext(P(2668,righty(33)),'33',fs,(255,255,255),'lm')
# destinations (vias / parts)
def ring(x,y,c,lab,dx=0,dy=-30,r=17,anchor='mm'):
    px,py=P(x,y); d.ellipse((px-r,py-r,px+r,py+r),outline=c,width=4)
    if lab: otext((px+dx,py+dy),lab,font(22),c,anchor)
VIAS=[ (80,1925,1030,(170,170,255),'80',-6,-32),(77,2022,1065,STRAP,'77',0,34),(76,2087,1005,UART,'76',0,-32),
 (75,2142,1047,STRAP,'75',0,34),(74,2197,1002,JTAG,'74',0,-32),(70,2380,1067,UART,'70',34,0),
 (78,2102,702,SPI,'78',36,0),(81,2025,630,SPI,'81',-36,0),
 (85,1644,1136,(170,170,255),'85',-34,6),(84,1718,1024,JTAG,'84',-32,-14),
 (92,1430,1057,I2C,'92',-6,-34),(91,1410,1112,I2C,'91',-36,4)]
if len(sys.argv)>1 and sys.argv[1]=='novias': VIAS=[]
for n,x,y,c,lab,dx,dy in VIAS: ring(x,y,c,lab,dx,dy)
# SPF0 resistors: left pads
for (lab,y) in [('R44',1825),('R89',1925),('R92',2025),('R93',2125)]:
    px,py=P(2925,y); d.rounded_rectangle((px-75,py-36,px+75,py+36),radius=8,outline=SPI,width=4)


# 83 via note
px,py=P(1752,1010); d.ellipse((px-22,py-22,px+22,py+22),outline=SPI,width=3)
d.line((px+16,py-16,px+70,py-150),fill=SPI,width=2)
otext((px+74,py-170),'83: via under this silkscreen (approx.)',font(22),SPI,'lm')
# ---------- title bar ----------
d.rectangle((0,0,img.width,TOP),fill=(18,22,28))
otext((30,22),'LX-IS601F V2.0 switch board: UART, SPI flash and JTAG pins on U4 (Motorcomm YT9215SCH)',font(46),(255,255,255),'la',0)
otext((30,92),'The chip is marked YT9215SCH, so the pin numbers below are the SC/SCH pinout (datasheet V1.03, 2025), not the YT9215S pinout.  Photo: top side, heatsink removed.',font(26,False),(200,210,220),'la',0)
# ---------- side panel ----------
x=W+40; y=TOP+20
def head(t,c=(255,255,255)):
    global y
    y+=14; d.text((x,y),t,font=font(32),fill=c); y+=46
    d.line((x,y,img.width-40,y),fill=(90,100,110),width=2); y+=12
def row(pin,fn,where,c):
    global y
    d.text((x,y),pin,font=font(26),fill=c)
    d.text((x+95,y),fn,font=font(26),fill=c)
    d.text((x+610,y),where,font=font(25,False),fill=(225,230,235)); y+=38
def note(t,c=(190,200,210)):
    global y
    d.text((x,y),t,font=font(24,False),fill=c); y+=33
head('UART','' or UART)
row('46','UART0_RX  (SWITCH_ID_1 strap)','no trace — solder to the chip lead',UART)
row('47','UART0_TX','no trace — solder to the chip lead',UART)
row('70','UART1_RX  (DIS_SPIS strap)','via ringed "70", beside the C97 label',UART)
row('76','UART1_TX  (DIS_MCU strap)','via ringed "76"',UART)
head('SPI flash, bank SPF1  (default: pin 49 low at reset)',SPI)
row('83','SCK  (EN_PHY strap)','via hidden under the C96/C25 silkscreen',SPI)
row('79','SI   (chip out → flash DI)','no trace — chip lead only',SPI)
row('78','SO   (flash DO → chip in)','via ringed "78"  (also P2LED1)',SPI)
row('81','CS#','via ringed "81"',SPI)
head('SPI flash, bank SPF0  (pin 49 high at reset)',SPI)
row('49','SCK  (SPF_MUX_SEL strap)','R93, pad nearest the chip',SPI)
row('50','SI   (chip out → flash DI)','R92, pad nearest the chip',SPI)
row('54','SO   (flash DO → chip in)','R89, pad nearest the chip',SPI)
row('55','CS#','R44, pad nearest the chip',SPI)
head('JTAG*  (unconfirmed, see note)',JTAG)
row('73','JTAG0_TCK*  (P3LED1)','LED trace running north, no via nearby',JTAG)
row('72','JTAG0_TMS*  (P4LED1)','LED trace running north, no via nearby',JTAG)
row('74','JTAG0_TDI*  (EN_PWRLIGHT)','via ringed "74"',JTAG)
row('90','JTAG0_TDO*  (GPIO47)','no trace — chip lead only',JTAG)
row('83','JTAG1_TCK*  (= SPF1_SCK)','same via as flash SCK',JTAG)
row('81','JTAG1_TMS*  (= SPF1_CS)','via ringed "81"',JTAG)
row('84','JTAG1_TDI*  (LED_DA)','via ringed "84"',JTAG)
row('67','JTAG1_TDO*  (GPIO31)','no trace — chip lead only',JTAG)
head('Boot straps and other useful pins',STRAP)
row('75','EN_SPIF  (1 = boot from flash)','via ringed "75"',STRAP)
row('76','DIS_MCU  (1 = RISC-V off)','via ringed "76"  (same pin as UART1_TX)',STRAP)
row('77','DISAUTOLOAD  (0 = autoload on)','via ringed "77"',STRAP)
row('89','nRESET','trace runs north past R23',REF)
row('91/92','SCL/MDC, SDA/MDIO','vias ringed "91", "92"  (EEPROM I²C or SMI)',I2C)
head('How sure is this')
for t in [
 '• Pin numbering: pin 1 is the lead next to the small dimple (bottom-left here), counting',
 '  anticlockwise, 32 leads per side. Checked against the board: 61/62 sit on the ground pour,',
 '  58/59 and 68/69 have wide power traces, 82 goes to C25, 87 goes to the crystal, and the four',
 '  resistors R44/R89/R92/R93 land exactly on the four SPF0 flash pins.',
 '• Routing was traced from top-side photos only. Where each via goes on the other layers,',
 '  and what the far pads of R44/R89/R92/R93 connect to, is not visible. Strap levels unknown.',
 '• * JTAG names come from the 2023 YT9215SC draft datasheet. The 2025 YT9215SCH datasheet',
 '  lists the same pins as GPIO/LED only, so JTAG may not work on this silicon until probed.',
 '• Pins 46, 47, 67, 79 and 90 have no copper leaving the lead: 0.4 mm pitch soldering needed.',
 '• Two bare chips appear in the photos (lots VKJC09324 and VKTP18287); both are YT9215SCH.']:
    note(t)

y+=20
d.text((x,y),'Wider view (second board, same layout) with the annotated areas boxed',font=font(26),fill=(255,255,255)); y+=42
o=Image.open(SP+'photo-u4-wide.jpg').convert('RGB')
bx=(480,700,3072,2900); o2=o.crop(bx)
hh=img.height-y-25; sc=hh/o2.height; o2=o2.resize((int(o2.width*sc),hh),Image.LANCZOS)
img.paste(o2,(x,y)); 
def B(x0,y0,x1,y1,c,t):
    a=(x+(x0-bx[0])*sc, y+(y0-bx[1])*sc, x+(x1-bx[0])*sc, y+(y1-bx[1])*sc)
    d.rectangle(a,outline=c,width=4); otext((a[0]+4,a[1]-28),t,font(21),c,'la',2)
B(1229,1300,1900,1570,UART,'strap / UART / flash vias')
B(1945,1880,2100,2190,SPI,'R44 R89 R92 R93')
B(760,1600,1840,2660,(255,255,255),'')
otext((x+(1300-bx[0])*sc,y+(2130-bx[1])*sc),'U4',font(30),(255,255,255),'mm',2)
px_,py_=x+(885-bx[0])*sc,y+(2433-bx[1])*sc
d.ellipse((px_-12,py_-12,px_+12,py_+12),outline=(255,255,255),width=3); otext((px_+18,py_),'pin 1',font(21),(255,255,255),'lm',2)

img.save(SP+'lx-is601f-debug-pins-annotated.png')
