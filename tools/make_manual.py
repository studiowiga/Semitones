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
    pim = Image.open(os.path.join(M, 'cover_pedal.jpg'))
    ph = 172 * mm; pw = ph * pim.width / pim.height
    c.drawImage(os.path.join(M, 'cover_pedal.jpg'), (W - pw) / 2, H - 22 * mm - ph, pw, ph)
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
    ('Eb Standard / Half step down (-1)', '-1', 'off', 'Hendrix / SRV / Van Halen tuning from a guitar in E.', 'Accordage Hendrix / SRV / Van Halen depuis une guitare en Mi.'),
    ('D Standard / Whole step down (-2)', '-2', 'off', 'Heavier rhythm, singer-friendly keys.', 'Rythmiques plus lourdes, tonalités plus faciles à chanter.'),
    ('C# Standard (-3)', '-3', 'off', 'Classic 90s / nu-metal territory.', 'Territoire années 90 / néo-métal.'),
    ('C Standard (-4)', '-4', 'off', 'Modern metal, drop C riffs on a guitar in drop D.', 'Métal moderne, riffs en drop C depuis une guitare en drop D.'),
    ('B Standard (-5)', '-5', 'off', 'Baritone feel on a regular six-string.', 'Sensation baryton sur une six-cordes.'),
    ('Bb Standard (-6)', '-6', 'off', 'Very low six-string tuning.', 'Accordage très grave pour six-cordes.'),
    ('Baritone A (-7)', '-7', 'off', 'Down a fifth: E becomes A.', 'Une quinte plus bas : Mi devient La.'),
    ('Octave down (-12)', '-12', 'off', 'Bass-like line from the guitar.', 'Ligne de basse jouée à la guitare.'),
    ('Octave doubler down (-12 + dry)', '-12', '50 %', 'Fast octaver: guitar + octave below.', 'Octaver rapide : guitare + octave inférieure.'),
    ('Sub octave blend (-12 + dry 30 %)', '-12', '30 %', 'Discreet sub weight under the riff.', 'Léger poids sub sous le riff.'),
    ('Power fifth below (-7 + dry)', '-7', '45 %', 'Adds the fifth below: instant power chord.', 'Ajoute la quinte inférieure : power chord instantané.'),
    ('Capo 1 / 2 / 3 / 5 / 7', '+1 ... +7', 'off', 'Electric capo without touching the guitar.', 'Capodastre électrique sans toucher la guitare.'),
    ('Fourth up harmony (+5 + dry)', '+5', '40 %', 'Parallel fourth harmony.', 'Harmonie parallèle à la quarte.'),
    ('Fifth up harmony (+7 + dry)', '+7', '40 %', 'Parallel fifth harmony.', 'Harmonie parallèle à la quinte.'),
    ('Octave up (+12)', '+12', 'off', 'One octave higher, solo lines.', 'Une octave plus haut, lignes de solo.'),
    ('12-string (+12 + dry 30 %)', '+12', '30 %', 'Octave sparkle like a 12-string.', 'Brillance d\'octave façon 12 cordes.'),
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
    s.append(img('overview.jpg', CW * 0.56))
    s.append(P(T('The front panel is the CHUG Capo, control for control. Numbers refer to the next pages.',
                 'La face avant est celle de la CHUG Capo, commande par commande. Les numéros renvoient aux pages suivantes.'), 'cap'))

    rows = [[T('No.', 'N°'), T('Control', 'Commande'), T('Function', 'Fonction')]]
    rows += [
        ['1', T('Display', 'Afficheur'), T('Pitch change in semitones (-12 ... +12). In mix adjust mode it shows the mix in % (0 ... 100). '
             'Bottom-left dot = MIX mode, bottom-right dot = FAV. Drag up/down or scroll over it to change the value.',
             'Transposition en demi-tons (-12 ... +12). En réglage du mix, il affiche le mix en % (0 ... 100). Point en bas à gauche = '
             'mode MIX, point en bas à droite = FAV. Glisser vers le haut / bas ou molette dessus pour changer la valeur.')],
        ['2', T('Left arrow', 'Flèche gauche'), T('-1 semitone (hold to repeat). In mix adjust mode: lowers the mix.',
             '-1 demi-ton (maintenir pour répéter). En réglage du mix : baisse le mix.')],
        ['3', T('Right arrow', 'Flèche droite'), T('+1 semitone (hold to repeat). In mix adjust mode: raises the mix.',
             '+1 demi-ton (maintenir pour répéter). En réglage du mix : monte le mix.')],
        ['4', 'MIX', T('Click: MIX mode on / off. Hold (0.6 s): mix adjust mode, the LED and the MIX dot flash, the arrows set the '
             'mix 0 ... 100 %; click MIX again or wait 4 s to leave.',
             'Clic : mode MIX marche / arrêt. Maintien (0,6 s) : réglage du mix, la LED et le point MIX clignotent, les flèches '
             'règlent le mix de 0 à 100 % ; recliquez sur MIX ou attendez 4 s pour sortir.')],
        ['5', 'FAV', T('Click: recall / leave the FAV setting. Hold (0.9 s): saves the current sound (pitch, MIX mode, mix) as FAV '
             '(the display blinks) and engages it.',
             'Clic : rappelle / quitte le réglage FAV. Maintien (0,9 s) : mémorise le son actuel (transposition, mode MIX, mix) '
             'comme FAV (l\'afficheur clignote) et l\'active.')],
        ['6', 'LED', T('Off = bypass. Red = effect on, 100 % shifted. Blue = MIX mode. Green = FAV. Flashing blue = mix adjust.',
             'Éteinte = bypass. Rouge = effet actif, 100 % transposé. Bleue = mode MIX. Verte = FAV. Bleue clignotante = réglage du mix.')],
        ['7', T('Footswitch', 'Footswitch'), T('Effect on / bypass (buffered bypass, click-free). Toggles as soon as it is pressed.',
             'Effet actif / bypass (bypass bufférisé, sans clic). Bascule dès l\'appui.')],
        ['8', T('Preset menu', 'Menu des presets'), T('Factory presets (section 6). Shows "Custom" when the sound matches none of them.',
             'Presets d\'usine (section 6). Affiche « Custom » quand le son ne correspond à aucun.')],
        ['9', T('Status line', "Ligne d'état"), T('Live values (pitch, mix %, MIX and FAV state, bypass), control hints on mouse-over, '
             'MIDI learn prompts.', 'Valeurs en direct (transposition, mix en %, état MIX et FAV, bypass), aide au survol, invite de MIDI learn.')],
        ['10 / 11', 'IN / OUT', T('Input on the right side, output on the left, as on the pedal.',
             'Entrée sur le côté droit, sortie à gauche, comme sur la pédale.')],
    ]
    s.append(table(rows, [14 * mm, 30 * mm, CW - 44 * mm]))

    s.append(PageBreak())
    s.append(P(T('4. Modes, footswitch and LED', '4. Modes, footswitch et LED'), 'h1'))
    s.append(P(T('Pitch (100 %)', 'Transposition (100 %)'), 'h2'))
    s.append(P(T("With MIX mode off you only hear the transposed guitar, like a capo or a retuned instrument. At 0 the signal goes "
                 "straight through (no delay at all).",
                 "Mode MIX éteint, seule la guitare transposée est entendue, comme avec un capodastre ou un instrument réaccordé. "
                 "À 0, le signal passe directement (aucun retard).")))
    s.append(P(T('MIX mode', 'Mode MIX'), 'h2'))
    s.append(P(T("MIX mode blends the shifted and the dry signal from 0 to 100 % (equal-power law: at 50 % both are at -3 dB). "
                 "Low settings add an octave or a fifth under or over the riff; 100 % is the shifted signal alone. The dry part is "
                 "never delayed, so the blend stays tight.",
                 "Le mode MIX mélange signal transposé et signal direct de 0 à 100 % (loi à puissance constante : à 50 % les deux sont "
                 "à -3 dB). Les réglages bas ajoutent une octave ou une quinte sous ou sur le riff ; 100 % = le signal transposé seul. "
                 "La partie directe n'est jamais retardée : le mélange reste serré.")))
    s.append(P(T('FAV', 'FAV'), 'h2'))
    s.append(P(T("One favourite memory, as on the pedal. Engaging FAV switches to the stored pitch, MIX mode and mix (green LED, FAV dot). "
                 "Clicking FAV again returns to your previous setting. Moving an arrow while FAV is on starts from the FAV sound and "
                 "leaves FAV. The FAV memory is saved with the project.",
                 "Une mémoire favorite, comme sur la pédale. Activer FAV passe à la transposition, au mode MIX et au mix mémorisés "
                 "(LED verte, point FAV). Recliquer sur FAV revient au réglage précédent. Toucher une flèche en FAV repart du son FAV et "
                 "quitte FAV. La mémoire FAV est enregistrée avec le projet.")))

    s.append(P(T('5. MIDI and expression pedals', '5. MIDI et pédales d\'expression'), 'h1'))
    s.append(P(T("Every function is a host parameter (Effect On, Pitch, Mix Mode, Mix, FAV) and can be automated. For MIDI "
                 "controllers such as the M-Vave Chocolate Plus, right-click a control and choose <b>MIDI Learn</b>, then move the "
                 "controller: the status line confirms what is waiting for a CC.",
                 "Toutes les fonctions sont des paramètres de l'hôte (Effect On, Pitch, Mix Mode, Mix, FAV) automatisables. Pour un "
                 "contrôleur MIDI comme la M-Vave Chocolate Plus, clic droit sur une commande puis <b>MIDI Learn</b>, et bougez le "
                 "contrôleur : la ligne d'état indique ce qui attend un CC.")))
    rows = [[T('Right-click on', 'Clic droit sur'), T('Learnable targets', 'Cibles assignables'), T('Notes', 'Remarques')],
            [T('Footswitch', 'Footswitch'), T('Footswitch (on / bypass)', 'Footswitch (marche / bypass)'),
             T('Latching (CC >= 64 = on) or momentary (each press toggles).', 'À accrochage (CC >= 64 = marche) ou momentané (chaque appui bascule).')],
            ['FAV', 'FAV', T('Momentary by default, like a non-latching switch on the FAV jack.', 'Momentané par défaut, comme un switch non verrouillable sur le jack FAV.')],
            ['MIX', T('MIX mode; Mix (expression)', 'Mode MIX ; Mix (expression)'),
             T('Moving the expression pedal also turns MIX mode on.', 'Bouger la pédale d\'expression active aussi le mode MIX.')],
            [T('Arrows', 'Flèches'), T('-1 / +1 semitone', '-1 / +1 demi-ton'), T('Triggered when the CC goes over 64.', 'Déclenché quand le CC passe au-dessus de 64.')],
            [T('Display', 'Afficheur'), T('Pitch (expression), arrows', 'Pitch (expression), flèches'),
             T('Heel = -12, toe = +12.', 'Talon = -12, pointe = +12.')]]
    s.append(table(rows, [30 * mm, 50 * mm, CW - 80 * mm]))
    s.append(Spacer(1, 6))
    s.append(P(T("Expression pedals are smooth: each new value is reached with a ramp lasting the time between two CC messages, "
                 "then a 2-pole filter; 14-bit controllers (CC n + CC n+32) are supported. The pedal's travel is learned "
                 "automatically, so 0 and 100 % are reached even if it only sends 2 to 116 (menu: <i>Reset expression pedal travel</i>).",
                 "Les pédales d'expression sont sans saccades : chaque nouvelle valeur est atteinte par une rampe de la durée séparant "
                 "deux messages CC, puis un filtre à 2 pôles ; les contrôleurs 14 bits (CC n + CC n+32) sont acceptés. La course de "
                 "la pédale est apprise automatiquement : 0 et 100 % sont atteints même si elle n'envoie que 2 à 116 (menu : "
                 "<i>Reset expression pedal travel</i>).")))

    s.append(P(T('Window', 'Fenêtre'), 'h2'))
    s.append(P(T("The window opens at the default size of the Studio Wiga single pedals (760 x 958) and cannot be made smaller. "
                 "Drag the bottom-right corner to enlarge it (aspect ratio kept), or right-click the background: Default / 125 % / 150 %.",
                 "La fenêtre s'ouvre à la taille par défaut des pédales simples Studio Wiga (760 x 958) et ne peut pas être réduite. "
                 "Tirez le coin inférieur droit pour l'agrandir (proportions conservées) ou clic droit sur le fond : Default / 125 % / 150 %.")))

    s.append(PageBreak())
    s.append(P(T('6. Presets', '6. Presets'), 'h1'))
    rows = [[T('Preset', 'Preset'), T('Pitch', 'Transp.'), 'MIX', T('Use', 'Usage')]]
    rows += [[n, p, m, T(en, fr)] for n, p, m, en, fr in PRESETS]
    s.append(table(rows, [58 * mm, 18 * mm, 14 * mm, CW - 90 * mm]))

    s.append(P(T('7. Tips', '7. Conseils'), 'h1'))
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

    s.append(KeepTogether([P(T('8. Specifications', '8. Caractéristiques techniques'), 'h1'), table([
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
        ['MIDI', T('MIDI learn on every control, latching / momentary switches, 14-bit CC, learned pedal travel',
                    'MIDI learn sur chaque commande, switchs à accrochage / momentanés, CC 14 bits, course de pédale apprise')],
        [T('Window', 'Fenêtre'), T('760 x 958 default (minimum), resizable up to 200 %', '760 x 958 par défaut (minimum), redimensionnable jusqu\'à 200 %')],
    ], [42 * mm, CW - 42 * mm])]))
    return s

story = [NextPageTemplate('cover_en'), Spacer(1, 1)]
story += part('en')
story += [NextPageTemplate('cover_fr'), PageBreak(), Spacer(1, 1)]
story += part('fr')
doc.build(story)
print(OUT)
