#!/usr/bin/env python3
"""Builds docs/Semitones_Manual_EN-FR_v<version>.pdf (English then French)."""
import os, re, sys
import numpy as np, cv2
from PIL import Image, ImageDraw, ImageFont
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (BaseDocTemplate, PageTemplate, Frame, Paragraph, Spacer, Image as RLImage,
                                Table, TableStyle, PageBreak, NextPageTemplate, KeepTogether)
from reportlab.lib.styles import ParagraphStyle

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
M = os.path.join(ROOT, 'design', 'manual')
VERSION = re.search(r'project\(Semitones VERSION ([0-9.]+)', open(os.path.join(ROOT, 'CMakeLists.txt')).read()).group(1)
OUT = os.path.join(ROOT, 'docs', 'Semitones_Manual_EN-FR_v%s.pdf' % VERSION)

pdfmetrics.registerFont(TTFont('Pop', os.path.join(ROOT, 'assets', 'Poppins-Medium.ttf')))
pdfmetrics.registerFont(TTFont('PopB', os.path.join(ROOT, 'assets', 'Poppins-Bold.ttf')))
pdfmetrics.registerFont(TTFont('PopL', '/usr/share/fonts/truetype/google-fonts/Poppins-Light.ttf'))
pdfmetrics.registerFont(TTFont('Sym', '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'))
pdfmetrics.registerFontFamily('PopL', normal='PopL', bold='PopB', italic='PopL', boldItalic='PopB')

ACC = colors.HexColor('#39a0ff')
INK = colors.HexColor('#1d1e21')
GREY = colors.HexColor('#6b6e75')
W, H = A4

# ------------------------------------------------------------ white logo
def logo_png(path):
    ss = 4; Hh = 120 * ss
    r_out = Hh * 0.47; th = Hh * 0.15
    font = ImageFont.truetype(os.path.join(ROOT, 'assets', 'Poppins-Bold.ttf'), int(Hh * 0.78))
    text = 'STUDIO WIGA'
    tb = ImageDraw.Draw(Image.new('L', (8, 8))).textbbox((0, 0), text, font=font)
    rings_w = r_out * 2 * 1.62; gap = Hh * 0.42
    Ww = int(rings_w + gap + (tb[2] - tb[0]) + Hh * 0.2)
    def ring(c):
        a = Image.new('L', (Ww, Hh), 0); d = ImageDraw.Draw(a)
        d.ellipse([c[0] - r_out, c[1] - r_out, c[0] + r_out, c[1] + r_out], fill=255)
        ri = r_out - th; d.ellipse([c[0] - ri, c[1] - ri, c[0] + ri, c[1] + ri], fill=0)
        return np.asarray(a).astype(np.float32) / 255
    A1 = ring((r_out + 2, Hh / 2)); A2 = ring((r_out + 2 + r_out * 1.24, Hh / 2))
    k = np.ones((int(th * 0.55), int(th * 0.55)), np.uint8)
    yy = np.mgrid[0:Hh, 0:Ww][0]
    top = yy < Hh / 2
    R = np.maximum(A1 * np.where(top, 1 - cv2.dilate(A2, k), 1), A2 * np.where(top, 1, 1 - cv2.dilate(A1, k)))
    t = Image.new('L', (Ww, Hh), 0)
    ImageDraw.Draw(t).text((rings_w + gap - tb[0], (Hh - (tb[3] - tb[1])) / 2 - tb[1]), text, font=font, fill=255)
    A = np.maximum(R, np.asarray(t).astype(np.float32) / 255)
    al = Image.fromarray((A * 255).astype(np.uint8)).resize((Ww // ss, Hh // ss), Image.LANCZOS)
    im = Image.new('RGBA', al.size, (255, 255, 255, 0)); im.putalpha(al)
    im.save(path)
    return al.size

LOGO = os.path.join(M, 'logo_white.png')

# ------------------------------------------------------------ detoured cover (house style: pedal on black, reflection, soft halo)
def cover_detoured(out, accent=(57, 160, 255)):
    im = Image.open(os.path.join(ROOT, 'docs', 'screenshot.png')).convert('RGB')   # real render, effect on, +4
    m = Image.new('L', im.size, 0); dr = ImageDraw.Draw(m)
    dr.rounded_rectangle([117, 12, 663, 945], radius=12, fill=255)                 # pedal body
    dr.rectangle([89, 422, 118, 504], fill=255); dr.rectangle([662, 422, 699, 504], fill=255)   # jacks
    im.putalpha(m)
    p = im.crop((86, 10, 702, 947))
    up = 2
    p = p.resize((p.width * up, p.height * up), Image.LANCZOS)
    pw, ph = p.size
    cw, ch = int(pw * 1.55), int(ph * 1.42)
    x0, y0 = (cw - pw) // 2, int(ph * 0.10)
    a = np.asarray(p.split()[3]).astype(np.float32) / 255
    canvas = np.zeros((ch, cw, 3), np.float32)
    A = np.zeros((ch, cw), np.float32); A[y0:y0 + ph, x0:x0 + pw] = a
    g = cv2.GaussianBlur(A, (0, 0), pw * 0.16)
    yy, xx = np.mgrid[0:ch, 0:cw].astype(np.float32)
    win = np.clip(np.minimum.reduce([xx, cw - 1 - xx, yy, ch - 1 - yy]) / (0.12 * cw), 0, 1) ** 2
    g = g / max(g.max(), 1e-6) * win * 0.26
    canvas += g[..., None] * (np.array(accent, np.float32)[None, None, :] / 255)
    rgb = np.asarray(p.convert('RGB')).astype(np.float32) / 255
    rh = int(ph * 0.30); ry = y0 + ph + 2; rh = min(rh, ch - ry)
    ra = a[::-1][:rh] * np.linspace(0.30, 0.0, rh)[:, None]
    canvas[ry:ry + rh, x0:x0 + pw] = canvas[ry:ry + rh, x0:x0 + pw] * (1 - ra[..., None]) + rgb[::-1][:rh] * ra[..., None]
    canvas[y0:y0 + ph, x0:x0 + pw] = canvas[y0:y0 + ph, x0:x0 + pw] * (1 - a[..., None]) + rgb * a[..., None]
    Image.fromarray((np.clip(canvas, 0, 1) * 255).astype(np.uint8)).save(out, quality=92)

COVER = os.path.join(M, 'cover_detoured.jpg')
cover_detoured(COVER)
lw, lh = logo_png(LOGO)

# ------------------------------------------------------------ styles
st = {
    'h1': ParagraphStyle('h1', fontName='PopB', fontSize=17, leading=22, textColor=INK, spaceBefore=4, spaceAfter=8),
    'h2': ParagraphStyle('h2', fontName='PopB', fontSize=11.5, leading=15, textColor=ACC, spaceBefore=9, spaceAfter=3),
    'p': ParagraphStyle('p', fontName='PopL', fontSize=9.6, leading=14.2, textColor=INK, spaceAfter=5),
    'li': ParagraphStyle('li', fontName='PopL', fontSize=9.6, leading=14, textColor=INK, leftIndent=12, bulletIndent=2, spaceAfter=2.5),
    'cap': ParagraphStyle('cap', fontName='Pop', fontSize=8, leading=11, textColor=GREY, alignment=1, spaceAfter=8),
    'tc': ParagraphStyle('tc', fontName='PopL', fontSize=8.8, leading=12, textColor=INK),
    'th': ParagraphStyle('th', fontName='PopB', fontSize=8.8, leading=12, textColor=colors.white),
}

def P(t, s='p'): return Paragraph(t, st[s])
def B(t): return Paragraph(t, st['li'], bulletText='•')

def table(rows, widths, head=True):
    data = [[Paragraph(c, st['th'] if (head and i == 0) else st['tc']) for c in r] for i, r in enumerate(rows)]
    t = Table(data, colWidths=widths, repeatRows=1 if head else 0)
    sty = [('VALIGN', (0, 0), (-1, -1), 'TOP'), ('TOPPADDING', (0, 0), (-1, -1), 4), ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
           ('LINEBELOW', (0, 0), (-1, -1), 0.4, colors.HexColor('#d9dbe0'))]
    if head: sty += [('BACKGROUND', (0, 0), (-1, 0), INK)]
    for i in range(1 if head else 0, len(rows)):
        if i % 2 == 0: sty.append(('BACKGROUND', (0, i), (-1, i), colors.HexColor('#f3f4f6')))
    t.setStyle(TableStyle(sty))
    return t

def img(name, width):
    im = Image.open(os.path.join(M, name))
    return RLImage(os.path.join(M, name), width=width, height=width * im.height / im.width)

# ------------------------------------------------------------ page decorations
def cover_page(c, doc, lang):
    c.saveState()
    c.setFillColor(colors.black); c.rect(0, 0, W, H, fill=1, stroke=0)
    c.setFillColor(ACC); c.rect(0, H - 4 * mm, W, 4 * mm, fill=1, stroke=0)
    c.setFont('PopB', 9); c.setFillColor(ACC)
    c.drawString(18 * mm, H - 14 * mm, 'ENGLISH' if lang == 'en' else 'FRANÇAIS')
    pim = Image.open(COVER)
    ph = 172 * mm; pw = ph * pim.width / pim.height
    c.drawImage(COVER, (W - pw) / 2, H - 20 * mm - ph, pw, ph)
    title = 'S E M I T O N E S'
    c.setFillColor(colors.white); c.setFont('PopB', 30)
    c.drawCentredString(W / 2, 62 * mm, title)
    c.setFillColor(colors.HexColor('#c9cbd0')); c.setFont('PopL', 11)
    c.drawCentredString(W / 2, 53 * mm, 'Low latency pitch pedal  -  digital capo  -  VST3' if lang == 'en'
                        else 'Pédale de transposition faible latence  -  capodastre numérique  -  VST3')
    c.setFont('Pop', 9.5)
    c.drawCentredString(W / 2, 46 * mm, ('User manual  ·  version %s' if lang == 'en' else "Notice d'utilisation  ·  version %s") % VERSION)
    lwid = 52 * mm
    c.drawImage(LOGO, (W - lwid) / 2, 22 * mm, lwid, lwid * lh / lw, mask='auto')
    c.restoreState()

def normal_page(c, doc):
    c.saveState()
    c.setFillColor(ACC); c.rect(0, H - 2.2 * mm, W, 2.2 * mm, fill=1, stroke=0)
    c.setFont('Pop', 7.5); c.setFillColor(GREY)
    c.drawString(18 * mm, 10 * mm, 'Semitones %s  ·  Studio Wiga' % VERSION)
    c.drawRightString(W - 18 * mm, 10 * mm, str(doc.page))
    c.restoreState()

doc = BaseDocTemplate(OUT, pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm, topMargin=16 * mm, bottomMargin=18 * mm,
                      title='Semitones %s - User manual / Notice' % VERSION, author='Studio Wiga')
fr = Frame(18 * mm, 18 * mm, W - 36 * mm, H - 34 * mm, id='f')
doc.addPageTemplates([
    PageTemplate(id='cover_en', frames=[fr], onPage=lambda c, d: cover_page(c, d, 'en')),
    PageTemplate(id='cover_fr', frames=[fr], onPage=lambda c, d: cover_page(c, d, 'fr')),
    PageTemplate(id='body', frames=[fr], onPage=normal_page),
])
CW = W - 36 * mm

# ------------------------------------------------------------ content
PRESETS = [
    ('Standard (0)', '0', 'off', 'Plain pass-through, the pedal ready to be moved.', 'Signal direct, pédale prête à être déplacée.'),
    ('Eb Standard (-1)', '-1', 'off', 'Hendrix / SRV / Van Halen tuning from a guitar in E.', 'Accordage Hendrix / SRV / Van Halen depuis une guitare en Mi.'),
    ('D Standard (-2)', '-2', 'off', 'Heavier rhythm, singer-friendly keys.', 'Rythmiques plus lourdes, tonalités plus faciles à chanter.'),
    ('C# Standard (-3)', '-3', 'off', 'Classic 90s / nu-metal territory.', 'Territoire années 90 / néo-métal.'),
    ('C Standard (-4)', '-4', 'off', 'Modern metal, drop C riffs on a guitar in drop D.', 'Métal moderne, riffs en drop C depuis une guitare en drop D.'),
    ('B Standard (-5)', '-5', 'off', 'Baritone feel on a regular six-string.', 'Sensation baryton sur une six-cordes.'),
    ('Bb Standard (-6)', '-6', 'off', 'Very low six-string tuning.', 'Accordage très grave pour six-cordes.'),
    ('Baritone A (-7)', '-7', 'off', 'Down a fifth: E becomes A.', 'Une quinte plus bas : Mi devient La.'),
    ('Octave down (-12)', '-12', 'off', 'Bass-like line from the guitar.', 'Ligne de basse jouée à la guitare.'),
    ('Octave doubler (-12)', '-12', '50 %', 'Fast octaver: guitar + octave below.', 'Octaver rapide : guitare + octave inférieure.'),
    ('Sub octave (-12)', '-12', '30 %', 'Discreet sub weight under the riff.', 'Léger poids sub sous le riff.'),
    ('Power fifth (-7)', '-7', '45 %', 'Adds the fifth below: instant power chord.', 'Ajoute la quinte inférieure : power chord instantané.'),
    ('Capo 1 / 2 / 3 / 5 / 7', '+1 ... +7', 'off', 'Electric capo without touching the guitar.', 'Capodastre électrique sans toucher la guitare.'),
    ('Fourth harmony (+5)', '+5', '40 %', 'Parallel fourth harmony.', 'Harmonie parallèle à la quarte.'),
    ('Fifth harmony (+7)', '+7', '40 %', 'Parallel fifth harmony.', 'Harmonie parallèle à la quinte.'),
    ('Octave up (+12)', '+12', 'off', 'One octave higher, solo lines.', 'Une octave plus haut, lignes de solo.'),
    ('12-string (+12)', '+12', '30 %', 'Octave sparkle like a 12-string.', 'Brillance d\'octave façon 12 cordes.'),
]

def part(lang):
    E = lang == 'en'
    T = lambda en, fr: en if E else fr
    s = []
    s.append(NextPageTemplate('body'))
    s.append(PageBreak())
    s.append(P(T('1. Introduction', '1. Présentation'), 'h1'))
    s.append(P(T(
        "Semitones is a VST3 replica of the <b>Solar Guitars CHUG Capo</b>, the low latency pitch pedal designed by Ola Englund's "
        "Solar team as a \"digital bi-directional capo\". It transposes your guitar or bass from one octave down to one octave up, "
        "in semitone steps, with the arrow buttons either side of the display, exactly like moving a capo along the fretboard.",
        "Semitones est une réplique VST3 de la <b>Solar Guitars CHUG Capo</b>, la pédale de transposition à faible latence conçue par "
        "l'équipe Solar d'Ola Englund comme un « capodastre numérique bidirectionnel ». Elle transpose guitare ou basse d'une octave "
        "vers le bas à une octave vers le haut, par demi-tons, avec les flèches de part et d'autre de l'afficheur, comme un capodastre "
        "qu'on déplace sur le manche.")))
    s.append(P(T(
        "Like the pedal, the engine is built for <b>latency first</b> (fast palm-muted chugs must not drag) and for a <b>transparent "
        "tone</b> that stays the same whatever the transposition. A MIX mode blends the shifted signal with your dry guitar (fast "
        "octaver, harmonies) and one FAV memory recalls your favourite setting in one click or from a MIDI footswitch.",
        "Comme la pédale, le moteur privilégie <b>la latence</b> (les chugs en palm-mute rapides ne doivent pas traîner) et un <b>son "
        "transparent</b>, identique quelle que soit la transposition. Le mode MIX mélange le signal transposé à la guitare directe "
        "(octaver rapide, harmonies) et une mémoire FAV rappelle votre réglage favori en un clic ou depuis un footswitch MIDI.")))
    s.append(P(T('How it sounds', 'Le son'), 'h2'))
    s.append(P(T(
        "The shifter works in the time domain and follows the period of the note you play (down to about 31 Hz, so 7 and 8-string "
        "drop tunings and basses are tracked). Splices are placed where both read heads see the same phase of the waveform, so "
        "single notes and power chords stay clean and solid; every new pick snaps the shifter back to the most recent audio to keep "
        "attacks tight. Measured head delay is about 2 ms on high notes and 6 to 10 ms on the low strings. As on the real pedal, "
        "dense chords and wide intervals bring some digital artefacts, more noticeable at the extremes (+/-12).",
        "Le transpositeur travaille dans le domaine temporel et suit la période de la note jouée (jusqu'à environ 31 Hz : les "
        "accordages graves de 7 et 8 cordes et la basse sont suivis). Les raccords sont placés là où les deux têtes de lecture voient "
        "la même phase de l'onde : notes seules et power chords restent nets et pleins ; chaque nouvelle attaque ramène le "
        "transpositeur sur l'audio le plus récent pour garder des attaques serrées. Retard mesuré : environ 2 ms sur les notes "
        "aiguës, 6 à 10 ms sur les cordes graves. Comme sur la vraie pédale, les accords très riches et les grands intervalles "
        "laissent entendre quelques artefacts numériques, surtout aux extrêmes (+/-12).")))

    s.append(P(T('2. Installation', '2. Installation'), 'h1'))
    s.append(B(T("<b>Windows</b>: copy the <b>Semitones.vst3</b> folder to <b>C:\\Program Files\\Common Files\\VST3</b>.",
                 "<b>Windows</b> : copiez le dossier <b>Semitones.vst3</b> dans <b>C:\\Program Files\\Common Files\\VST3</b>.")))
    s.append(B(T("<b>macOS</b>: copy <b>Semitones.vst3</b> to <b>/Library/Audio/Plug-Ins/VST3</b> (or ~/Library/Audio/Plug-Ins/VST3). "
                 "If macOS blocks it, run <i>xattr -dr com.apple.quarantine</i> on the bundle.",
                 "<b>macOS</b> : copiez <b>Semitones.vst3</b> dans <b>/Library/Audio/Plug-Ins/VST3</b> (ou ~/Library/Audio/Plug-Ins/VST3). "
                 "Si macOS le bloque, lancez <i>xattr -dr com.apple.quarantine</i> sur le paquet.")))
    s.append(B(T("<b>Reaper</b>: Options &gt; Preferences &gt; Plug-ins &gt; VST &gt; <i>Re-scan</i>. The plug-in appears as "
                 "<b>Semitones (Studio Wiga)</b>.",
                 "<b>Reaper</b> : Options &gt; Préférences &gt; Plug-ins &gt; VST &gt; <i>Re-scan</i>. Le plugin apparaît sous le nom "
                 "<b>Semitones (Studio Wiga)</b>.")))

    s.append(PageBreak())
    s.append(P(T('3. The interface', "3. L'interface"), 'h1'))
    s.append(img('overview.jpg', CW * 0.50))
    s.append(P(T('Studio Wiga dark brushed steel design with the engraved Semitones name, same controls as the CHUG Capo. Numbers refer to the next pages.',
                 'Design Studio Wiga en acier brossé sombre avec le nom Semitones gravé, mêmes commandes que la CHUG Capo. Les numéros renvoient aux pages suivantes.'), 'cap'))

    rows = [[T('No.', 'N°'), T('Control', 'Commande'), T('Function', 'Fonction')]]
    rows += [
        ['1', T('Display', 'Afficheur'), T('Pitch change in semitones (-12 ... +12). In mix adjust mode it shows the mix in % (0 ... 100). '
             'Blue dot-matrix display; a blue dot above MIX lights up when MIX mode is on. Drag up/down or scroll over it to change the value.',
             'Transposition en demi-tons (-12 ... +12). En réglage du mix, il affiche le mix en % (0 ... 100). Afficheur bleu '
             'à matrice de points ; un point bleu s\'allume au-dessus de MIX quand le mode MIX est actif. Glisser vers le haut / bas ou molette dessus pour changer la valeur.')],
        ['2', T('Left arrow', 'Flèche gauche'), T('-1 semitone (hold to repeat). In mix adjust mode: lowers the mix.',
             '-1 demi-ton (maintenir pour répéter). En réglage du mix : baisse le mix.')],
        ['3', T('Right arrow', 'Flèche droite'), T('+1 semitone (hold to repeat). In mix adjust mode: raises the mix.',
             '+1 demi-ton (maintenir pour répéter). En réglage du mix : monte le mix.')],
        ['4', 'MIX', T('Click: MIX mode on / off. Hold (0.6 s): mix adjust mode, the light ring and the MIX dot flash, the arrows set the '
             'mix 0 ... 100 %; click MIX again or wait 4 s to leave.',
             'Clic : mode MIX marche / arrêt. Maintien (0,6 s) : réglage du mix, l\'anneau lumineux et le point MIX clignotent, les flèches '
             'règlent le mix de 0 à 100 % ; recliquez sur MIX ou attendez 4 s pour sortir.')],
        ['5', 'FAV', T('Click: recall / leave the FAV setting. Hold (0.9 s): saves the current sound (pitch, MIX mode, mix) as FAV '
             '(the display blinks) and engages it.',
             'Clic : rappelle / quitte le réglage FAV. Maintien (0,9 s) : mémorise le son actuel (transposition, mode MIX, mix) '
             'comme FAV (l\'afficheur clignote) et l\'active.')],
        ['6', T('Light ring', 'Anneau lumineux'), T('Blue ring around the footswitch (colour of the display) with a bright light and a long glowing trail turning around it: lit = effect on, off = bypass, '
             'flashing = mix adjust. MIX: blue dot in the display; MIX and FAV states also on the status line.',
             'Anneau bleu autour du footswitch (couleur de l\'afficheur) avec une lumière à longue traînée lumineuse qui tourne : allumé = effet actif, éteint = bypass, clignotant = réglage '
             'du mix. MIX : point bleu dans l\'afficheur ; états MIX et FAV aussi sur la ligne d\'état.')],
        ['7', T('Footswitch', 'Footswitch'), T('Effect on / bypass (buffered bypass, click-free). Toggles as soon as it is pressed.',
             'Effet actif / bypass (bypass bufférisé, sans clic). Bascule dès l\'appui.')],
        ['8', T('Preset menu', 'Menu des presets'), T('On the pedal, above the display: factory presets (section 8) grouped by use. Shows "Custom" when the sound matches none of them.',
             'Sur la pédale, au-dessus de l\'afficheur : presets d\'usine (section 8) groupés par usage. Affiche « Custom » quand le son ne correspond à aucun.')],
        ['9', T('Status line', "Ligne d'état"), T('Live values (pitch, mix %, MIX and FAV state, bypass), control hints on mouse-over, '
             'MIDI learn prompts.', 'Valeurs en direct (transposition, mix en %, état MIX et FAV, bypass), aide au survol, invite de MIDI learn.')],
        ['10 / 11', 'IN / OUT', T('Input on the right side, output on the left, as on the pedal.',
             'Entrée sur le côté droit, sortie à gauche, comme sur la pédale.')],
    ]
    s.append(table(rows, [14 * mm, 30 * mm, CW - 44 * mm]))

    s.append(PageBreak())
    s.append(P(T('4. Controls: pitch, MIX and FAV', '4. Les commandes : transposition, MIX et FAV'), 'h1'))
    s.append(P(T('Pitch (arrows and display)', 'Transposition (flèches et afficheur)'), 'h2'))
    s.append(P(T("The arrows change the pitch by one semitone from -12 to +12 (hold to repeat); you can also drag up / down or scroll over the "
                 "display. With MIX mode off you only hear the transposed guitar, like a capo or a retuned instrument. At 0 the signal goes "
                 "straight through (no delay at all).",
                 "Les flèches changent la transposition d'un demi-ton, de -12 à +12 (maintenir pour répéter) ; on peut aussi glisser vers le haut / bas "
                 "ou utiliser la molette sur l'afficheur. Mode MIX éteint, seule la guitare transposée est entendue, comme avec un capodastre ou un "
                 "instrument réaccordé. À 0, le signal passe directement (aucun retard).")))
    s.append(P(T('MIX mode', 'Mode MIX'), 'h2'))
    s.append(P(T("Click MIX to switch MIX mode on / off (blue dot above MIX in the display). MIX mode blends the shifted and the dry signal from "
                 "0 to 100 % (equal-power law: at 50 % both are at -3 dB). Hold MIX for 0.6 s to adjust the mix with the arrows: the light ring and "
                 "the MIX dot flash and the display shows the mix in %; click MIX again or wait 4 s to leave. Low settings add an octave or a fifth "
                 "under or over the riff; 100 % is the shifted signal alone. The dry part is never delayed, so the blend stays tight.",
                 "Un clic sur MIX active / coupe le mode MIX (point bleu au-dessus de MIX dans l'afficheur). Le mode MIX mélange signal transposé et "
                 "signal direct de 0 à 100 % (loi à puissance constante : à 50 % les deux sont à -3 dB). Maintenez MIX 0,6 s pour régler le mix aux "
                 "flèches : l'anneau lumineux et le point MIX clignotent et l'afficheur indique le mix en % ; recliquez sur MIX ou attendez 4 s pour "
                 "sortir. Les réglages bas ajoutent une octave ou une quinte sous ou sur le riff ; 100 % = le signal transposé seul. La partie directe "
                 "n'est jamais retardée : le mélange reste serré.")))
    s.append(P(T('FAV', 'FAV'), 'h2'))
    s.append(P(T("One favourite memory, as on the pedal. Click FAV to switch to the stored pitch, MIX mode and mix (FAV ON on the status line); "
                 "click again to return to your previous setting. Hold FAV for 0.9 s to store the current sound as FAV (the display blinks). "
                 "Moving an arrow while FAV is on starts from the FAV sound and leaves FAV. The FAV memory is saved with the project.",
                 "Une mémoire favorite, comme sur la pédale. Un clic sur FAV passe à la transposition, au mode MIX et au mix mémorisés (FAV ON sur "
                 "la ligne d'état) ; un nouveau clic revient au réglage précédent. Maintenez FAV 0,9 s pour mémoriser le son actuel (l'afficheur "
                 "clignote). Toucher une flèche en FAV repart du son FAV et quitte FAV. La mémoire FAV est enregistrée avec le projet.")))
    s.append(P(T('Preset menu', 'Menu des presets'), 'h2'))
    s.append(P(T("The menu above the display recalls the factory presets (section 8), grouped by use. It shows \"Custom\" when the sound matches none of them.",
                 "Le menu au-dessus de l'afficheur rappelle les presets d'usine (section 8), groupés par usage. Il affiche « Custom » quand le son ne correspond à aucun.")))

    s.append(P(T('5. Footswitch, light ring and status line', "5. Footswitch, anneau lumineux et ligne d'état"), 'h1'))
    for en, fr in [
        ("<b>Footswitch</b>: effect on / bypass, toggles as soon as it is pressed. Buffered bypass with a 6 ms crossfade, click-free.",
         "<b>Footswitch</b> : effet actif / bypass, bascule dès l'appui. Bypass bufférisé avec fondu de 6 ms, sans clic."),
        ("<b>Light ring</b>: blue ring around the footswitch (colour of the display) with a bright light and a long glowing trail turning around it "
         "(one turn in 1.6 s). Lit = effect on, off = bypass, flashing = mix adjust.",
         "<b>Anneau lumineux</b> : anneau bleu autour du footswitch (couleur de l'afficheur) avec une lumière à longue traînée qui tourne (un tour "
         "en 1,6 s). Allumé = effet actif, éteint = bypass, clignotant = réglage du mix."),
        ("<b>Status line</b> (under the pedal): live values (pitch, mix %, MIX and FAV state, bypass), control hints on mouse-over and the MIDI Learn prompts.",
         "<b>Ligne d'état</b> (sous la pédale) : valeurs en direct (transposition, mix en %, états MIX et FAV, bypass), aide au survol et invites du MIDI Learn."),
    ]:
        s.append(B(T(en, fr)))

    s.append(PageBreak())
    s.append(P(T('6. MIDI', '6. MIDI'), 'h1'))
    s.append(P(T("Every function is a host parameter (Effect On, Pitch, Mix Mode, Mix, FAV) and can be automated. For MIDI controllers such as the "
                 "M-Vave Chocolate Plus, every control has its own <b>MIDI Learn</b>. Semitones listens on every MIDI channel; nothing is assigned "
                 "by default, so you choose your own CCs.",
                 "Toutes les fonctions sont des paramètres de l'hôte (Effect On, Pitch, Mix Mode, Mix, FAV) automatisables. Pour un contrôleur MIDI "
                 "comme la M-Vave Chocolate Plus, chaque commande a son propre <b>MIDI Learn</b>. Semitones écoute tous les canaux MIDI ; rien n'est "
                 "assigné par défaut : vous choisissez vos CC.")))
    for en, fr in [
        ("<b>Right-click a control</b> and choose <b>MIDI Learn: &lt;control&gt; (CC n / none)</b>. MIX offers MIX mode and Mix (expression); the "
         "display offers Pitch (expression) and the two arrows.",
         "<b>Clic droit sur une commande</b> puis <b>MIDI Learn: &lt;commande&gt; (CC n / none)</b>. MIX propose le mode MIX et le Mix (expression) ; "
         "l'afficheur propose Pitch (expression) et les deux flèches."),
        ("The status line shows <b>MIDI LEARN: move a control for X</b>. Move a pedal or press a footswitch: the first CC received is assigned and "
         "the status line confirms <b>X = CC n</b> for 2 seconds. CC 32-63 (14-bit LSB) and 120-127 (channel mode) are never learned.",
         "La ligne d'état affiche <b>MIDI LEARN: move a control for X</b>. Bougez une pédale ou appuyez sur un footswitch : le premier CC reçu est "
         "assigné et la ligne d'état confirme <b>X = CC n</b> pendant 2 secondes. Les CC 32-63 (LSB 14 bits) et 120-127 (mode de canal) ne sont jamais pris."),
        ("<b>Clear MIDI: &lt;control&gt;</b> removes the assignment; <b>Cancel MIDI learn</b> (or choosing the same Learn again) stops waiting.",
         "<b>Clear MIDI: &lt;commande&gt;</b> retire l'assignation ; <b>Cancel MIDI learn</b> (ou rechoisir le même Learn) arrête l'attente."),
        ("Switches: <i>Latching switch (CC &gt;= 64 = on)</i> or <i>Momentary switch (each press toggles)</i>, chosen in the same menu. "
         "Expression pedals: <i>Reset expression pedal travel</i>.",
         "Switchs : <i>Latching switch (CC &gt;= 64 = on)</i> ou <i>Momentary switch (each press toggles)</i>, au choix dans le même menu. "
         "Pédales d'expression : <i>Reset expression pedal travel</i>."),
        ("Right-click the background &gt; <b>MIDI</b>: <i>Learn</i> for every control with its current CC and <b>Reset MIDI to defaults (nothing assigned)</b>.",
         "Clic droit sur le fond &gt; <b>MIDI</b> : <i>Learn</i> de chaque commande avec son CC actuel et <b>Reset MIDI to defaults (nothing assigned)</b>."),
        ("Assignments, switch types and learned pedal travel are saved with the project.",
         "Assignations, types de switch et course de pédale apprise sont enregistrés avec le projet."),
    ]:
        s.append(B(T(en, fr)))
    s.append(Spacer(1, 5))
    rows = [[T('Control (MIDI Learn name)', 'Commande (nom du MIDI Learn)'), T('Default CC', 'CC par défaut'), 'Type'],
            [T('Footswitch (on / bypass)', 'Footswitch (on / bypass)'), T('none', 'aucun'), T('Footswitch, latching by default (CC &gt;= 64 = on) or momentary (each press toggles).', 'Footswitch, à accrochage par défaut (CC &gt;= 64 = marche) ou momentané (chaque appui bascule).')],
            ['FAV', T('none', 'aucun'), T('Footswitch, momentary by default (like a non-latching switch on the FAV jack) or latching.', 'Footswitch, momentané par défaut (comme un switch non verrouillable sur le jack FAV) ou à accrochage.')],
            ['MIX mode', T('none', 'aucun'), T('Switch, latching by default or momentary.', 'Bascule, à accrochage par défaut ou momentanée.')],
            ['Right arrow (+1 st)', T('none', 'aucun'), T('Trigger: +1 semitone each time the CC goes over 64.', 'Déclencheur : +1 demi-ton à chaque passage du CC au-dessus de 64.')],
            ['Left arrow (-1 st)', T('none', 'aucun'), T('Trigger: -1 semitone each time the CC goes over 64.', 'Déclencheur : -1 demi-ton à chaque passage du CC au-dessus de 64.')],
            ['Pitch (expression)', T('none', 'aucun'), T('Continuous, 25 steps: heel = -12, toe = +12 (14-bit accepted).', 'Continu, 25 pas : talon = -12, pointe = +12 (14 bits accepté).')],
            ['Mix (expression)', T('none', 'aucun'), T('Continuous 0-100 %; moving it also turns MIX mode on (14-bit accepted).', 'Continu 0-100 % ; le bouger active aussi le mode MIX (14 bits accepté).')]]
    s.append(table(rows, [46 * mm, 22 * mm, CW - 68 * mm]))
    s.append(Spacer(1, 6))
    s.append(P(T("Expression pedals are smooth: each new value is reached with a ramp lasting the time between two CC messages, then a 2-pole filter; "
                 "14-bit controllers (CC n + CC n+32) are supported. The pedal's travel is learned automatically, so 0 and 100 % are reached even if "
                 "it only sends 2 to 116.",
                 "Les pédales d'expression sont sans saccades : chaque nouvelle valeur est atteinte par une rampe de la durée séparant deux messages "
                 "CC, puis un filtre à 2 pôles ; les contrôleurs 14 bits (CC n + CC n+32) sont acceptés. La course de la pédale est apprise "
                 "automatiquement : 0 et 100 % sont atteints même si elle n'envoie que 2 à 116.")))

    s.append(P(T('7. Window', '7. Fenêtre'), 'h1'))
    s.append(P(T("Right-click anywhere &gt; <b>Window size</b>: <b>60 % (default)</b>, <b>75 %</b>, <b>100 %</b>, like the other Studio Wiga pedals. "
                 "The window opens at the default size and can never be made smaller; you can also drag the bottom-right corner to enlarge it "
                 "(aspect ratio kept).",
                 "Clic droit n'importe où &gt; <b>Window size</b> : <b>60 % (default)</b>, <b>75 %</b>, <b>100 %</b>, comme les autres pédales Studio "
                 "Wiga. La fenêtre s'ouvre à la taille par défaut et ne peut jamais être plus petite ; on peut aussi tirer le coin inférieur droit "
                 "pour l'agrandir (proportions conservées).")))
    s.append(PageBreak())
    s.append(P(T('8. Presets', '8. Presets'), 'h1'))
    rows = [[T('Preset', 'Preset'), T('Pitch', 'Transp.'), 'MIX', T('Use', 'Usage')]]
    rows += [[n, p, m, T(en, fr)] for n, p, m, en, fr in PRESETS]
    s.append(table(rows, [58 * mm, 18 * mm, 14 * mm, CW - 90 * mm]))

    s.append(P(T('9. Tips', '9. Conseils'), 'h1'))
    s.append(B(T("Place Semitones <b>first</b> in the Reaper chain, before drives and before Two Notes Genome: the shifter tracks a "
                 "clean guitar best, and the amp then reacts naturally to the transposed signal.",
                 "Placez Semitones <b>en premier</b> dans la chaîne Reaper, avant les saturations et avant Two Notes Genome : le "
                 "transpositeur suit mieux une guitare claire, et l'ampli réagit naturellement au signal transposé.")))
    s.append(B(T("Down-tuning a 7-string in G: -1 to -5 stays very solid on riffs; octave down is huge on single-note lines and "
                 "power chords, keep big open chords for the moderate settings.",
                 "Pour descendre une 7 cordes en Sol : -1 à -5 restent très solides sur les riffs ; l'octave basse est énorme sur les "
                 "lignes en notes seules et les power chords, gardez les grands accords ouverts pour les réglages modérés.")))
    s.append(B(T("Monitor live through the plug-in: no latency is reported to the host, the shifted signal is heard immediately, "
                 "exactly as through the pedal.",
                 "Jouez en direct à travers le plugin : aucune latence n'est déclarée à l'hôte, le signal transposé est entendu "
                 "immédiatement, exactement comme à travers la pédale.")))
    s.append(B(T("Mix around 30 % with -12 gives the fast octaver sound of the pedal's MIX mode; +12 at 30 % adds a 12-string shimmer.",
                 "Un mix vers 30 % à -12 donne l'octaver rapide du mode MIX de la pédale ; +12 à 30 % ajoute une brillance de 12 cordes.")))

    s.append(KeepTogether([P(T('10. Specifications', '10. Caractéristiques techniques'), 'h1'), table([
        [T('Item', 'Élément'), T('Value', 'Valeur')],
        [T('Format', 'Format'), 'VST3 - Windows 10 / 11 (x64), macOS 10.13+ (Apple Silicon + Intel)'],
        [T('Original pedal', "Pédale d'origine"), 'Solar Guitars CHUG Capo (low latency professional pitch pedal)'],
        [T('Pitch range', 'Plage'), T('-12 ... +12 semitones, 1 semitone steps', '-12 ... +12 demi-tons, pas d\'un demi-ton')],
        ['Mix', T('0 ... 100 % (1 % steps, equal-power), MIX mode on / off', '0 ... 100 % (pas de 1 %, puissance constante), mode MIX marche / arrêt')],
        [T('Memory', 'Mémoire'), T('1 FAV slot (pitch, MIX mode, mix), saved with the project', '1 mémoire FAV (transposition, mode MIX, mix), enregistrée avec le projet')],
        [T('Latency', 'Latence'), T('~2 ms (high notes) to ~6-10 ms (low strings), 0 reported to the host', '~2 ms (aigus) à ~6-10 ms (cordes graves), 0 déclarée à l\'hôte')],
        [T('Pitch tracking', 'Suivi de hauteur'), T('about 31 Hz to 1.1 kHz (7/8-string and bass drop tunings)', 'environ 31 Hz à 1,1 kHz (accordages graves 7/8 cordes et basse)')],
        [T('Channels', 'Canaux'), T('mono or stereo in, mono or stereo out', 'entrée mono ou stéréo, sortie mono ou stéréo')],
        [T('Sample rates', "Fréquences d'échantillonnage"), '44.1 ... 192 kHz'],
        ['Bypass', T('buffered, 6 ms crossfade', 'bufférisé, fondu de 6 ms')],
        ['MIDI', T('MIDI Learn on every control (nothing assigned by default), omni, latching / momentary switches, 14-bit CC, learned pedal travel; saved with the project',
                    'MIDI Learn sur chaque commande (rien d\'assigné par défaut), omni, switchs à accrochage / momentanés, CC 14 bits, course de pédale apprise ; enregistré avec le projet')],
        [T('Window', 'Fenêtre'), T('60 % (default, minimum), 75 %, 100 %; corner resize', '60 % (défaut, minimum), 75 %, 100 % ; redimensionnement par le coin')],
        [T('Windows stability', 'Stabilité Windows'), T('anti-freeze v2: the audio thread never calls the host, window refresh driven by a timer with a watchdog',
                    "anti-gel v2 : le thread audio n'appelle jamais l'hôte, rafraîchissement de la fenêtre piloté par un timer avec chien de garde")],
    ], [42 * mm, CW - 42 * mm])]))
    return s

story = [NextPageTemplate('cover_en'), Spacer(1, 1)]
story += part('en')
story += [NextPageTemplate('cover_fr'), PageBreak(), Spacer(1, 1)]
story += part('fr')
doc.build(story)
print(OUT)
