/**
 * Imagen para compartir (resultado o previa) dibujada en el móvil con Canvas 2D.
 * Se carga bajo demanda desde ShareSheet: no pesa en la carga inicial.
 */
import { initials, isOursName, shortTeam, teamHue } from './format.js';

export const FORMATS = {
  story: { w: 1080, h: 1920, label: 'Historia' },
  square: { w: 1080, h: 1080, label: 'Cuadrado' },
};

const FONT = 'system-ui, -apple-system, "Segoe UI", Roboto, Helvetica, Arial, sans-serif';
const GREEN = '#31a943';
const MINT = '#8ee39c';

// Posiciones (en px del lienzo) de cada bloque según formato y tipo de imagen
const LAYOUT = {
  story: {
    logo: [210, 170], brand: 360, head: 560, headSize: 150, title: 645, titleSize: 46,
    crest: 300, crestY: 880, crestX: [0.25, 0.75], name: 1095, nameSize: 54,
    bandH: 90, bandSize: 36, foot: 1868, footSize: 34,
    result: { score: 1330, scoreSize: 240, pills: 1390, pillH: 72, pillSize: 40, when: 1555, whenSize: 46, venue: 1620, venueSize: 40, venueLines: 2, band: 1700 },
    preview: { vsSize: 110, date: 1330, dateSize: 62, time: 1480, timeSize: 150, venue: 1580, venueSize: 42, venueLines: 2, band: 1700 },
  },
  square: {
    logo: [95, 110], brand: 0, head: 268, headSize: 104, title: 330, titleSize: 36,
    crest: 200, crestY: 505, crestX: [0.22, 0.78], name: 655, nameSize: 40,
    bandH: 70, bandSize: 28, foot: 1035, footSize: 26,
    result: { score: 572, scoreSize: 150, pills: 690, pillH: 56, pillSize: 30, when: 815, whenSize: 36, venue: 862, venueSize: 30, venueLines: 1, band: 905 },
    preview: { vsSize: 80, date: 735, dateSize: 40, time: 828, timeSize: 88, venue: 878, venueSize: 28, venueLines: 1, band: 910 },
  },
};

/** Titular desde el punto de vista de Ancares. */
export function headline(data) {
  if (data.kind === 'preview') return 'PRÓXIMO PARTIDO';
  return { win: '¡VICTORIA!', loss: 'DERROTA', draw: 'EMPATE' }[data.outcome] || 'RESULTADO';
}

/** Mayor tamaño de fuente (≤ size) con el que `text` cabe en `maxWidth`. */
export function fitFont(ctx, text, maxWidth, size, weight = 700, min = 18) {
  let s = size;
  for (; s > min; s -= 2) {
    ctx.font = `${weight} ${s}px ${FONT}`;
    if (ctx.measureText(text).width <= maxWidth) break;
  }
  ctx.font = `${weight} ${s}px ${FONT}`;
  return s;
}

// --- dibujo ---------------------------------------------------------------------

function loadImage(src) {
  return new Promise((resolve) => {
    if (!src) return resolve(null);
    const img = new Image();
    img.onload = () => resolve(img);
    img.onerror = () => resolve(null);
    img.src = src;
  });
}

function text(ctx, str, x, y, { size, weight = 700, color = '#fff', align = 'center', maxWidth = 980, min } = {}) {
  fitFont(ctx, str, maxWidth, size, weight, min);
  ctx.fillStyle = color;
  ctx.textAlign = align;
  ctx.textBaseline = 'alphabetic';
  ctx.fillText(str, x, y);
}

/** Texto partido en hasta `maxLines` líneas centradas; la última se corta con «…». */
export function wrapLines(ctx, str, maxWidth, maxLines) {
  const words = str.split(/\s+/);
  const lines = [];
  let line = '';
  for (const word of words) {
    const test = line ? `${line} ${word}` : word;
    if (ctx.measureText(test).width <= maxWidth || !line) line = test;
    else {
      lines.push(line);
      line = word;
    }
  }
  if (line) lines.push(line);
  if (lines.length > maxLines) {
    const kept = lines.slice(0, maxLines);
    let last = `${kept[maxLines - 1]} ${lines.slice(maxLines).join(' ')}`;
    while (ctx.measureText(last + '…').width > maxWidth && last.length > 1) last = last.slice(0, -1);
    kept[maxLines - 1] = last.trimEnd() + '…';
    return kept;
  }
  return lines;
}

function paragraph(ctx, str, x, y, { size, weight = 500, color, maxWidth, maxLines }) {
  ctx.font = `${weight} ${size}px ${FONT}`;
  ctx.fillStyle = color;
  ctx.textAlign = 'center';
  wrapLines(ctx, str, maxWidth, maxLines).forEach((l, i) => ctx.fillText(l, x, y + i * size * 1.3));
}

function roundRect(ctx, x, y, w, h, r) {
  ctx.beginPath();
  ctx.moveTo(x + r, y);
  ctx.arcTo(x + w, y, x + w, y + h, r);
  ctx.arcTo(x + w, y + h, x, y + h, r);
  ctx.arcTo(x, y + h, x, y, r);
  ctx.arcTo(x, y, x + w, y, r);
  ctx.closePath();
}

function background(ctx, w, h) {
  const g = ctx.createLinearGradient(0, 0, w * 0.3, h);
  g.addColorStop(0, '#1d4a2a');
  g.addColorStop(0.55, '#0f2416');
  g.addColorStop(1, '#08130b');
  ctx.fillStyle = g;
  ctx.fillRect(0, 0, w, h);
  // Brillo verde arriba a la derecha
  const r = ctx.createRadialGradient(w * 0.95, h * 0.05, 0, w * 0.95, h * 0.05, w * 0.9);
  r.addColorStop(0, 'rgba(49,169,67,0.55)');
  r.addColorStop(1, 'rgba(49,169,67,0)');
  ctx.fillStyle = r;
  ctx.fillRect(0, 0, w, h);
  // Balón decorativo abajo a la izquierda
  ctx.save();
  ctx.strokeStyle = 'rgba(255,255,255,0.05)';
  ctx.lineWidth = w * 0.035;
  ctx.beginPath();
  ctx.arc(w * 0.05, h * 0.92, w * 0.42, 0, Math.PI * 2);
  ctx.stroke();
  ctx.lineWidth = w * 0.02;
  ctx.beginPath();
  ctx.arc(w * 0.05, h * 0.92, w * 0.26, 0, Math.PI * 2);
  ctx.stroke();
  ctx.restore();
}

function crest(ctx, img, team, cx, cy, size, ours) {
  const r = size / 2;
  ctx.save();
  ctx.shadowColor = 'rgba(0,0,0,0.35)';
  ctx.shadowBlur = size * 0.12;
  ctx.shadowOffsetY = size * 0.04;
  ctx.beginPath();
  ctx.arc(cx, cy, r, 0, Math.PI * 2);
  if (img) {
    ctx.fillStyle = '#fff';
    ctx.fill();
    ctx.restore();
    ctx.save();
    ctx.beginPath();
    ctx.arc(cx, cy, r, 0, Math.PI * 2);
    ctx.clip();
    const pad = ours ? 0 : size * 0.1; // el escudo de Ancares ya es redondo
    const box = size - pad * 2;
    const scale = Math.min(box / img.width, box / img.height);
    const w = img.width * scale;
    const h = img.height * scale;
    ctx.drawImage(img, cx - w / 2, cy - h / 2, w, h);
    ctx.restore();
  } else {
    const hue = teamHue(team.name);
    ctx.fillStyle = `hsl(${hue} 45% 28%)`;
    ctx.fill();
    ctx.restore();
    text(ctx, initials(team.name), cx, cy + size * 0.13, { size: size * 0.36, weight: 800, color: `hsl(${hue} 70% 85%)` });
  }
  if (ours) {
    ctx.save();
    ctx.strokeStyle = GREEN;
    ctx.lineWidth = size * 0.035;
    ctx.beginPath();
    ctx.arc(cx, cy, r + size * 0.02, 0, Math.PI * 2);
    ctx.stroke();
    ctx.restore();
  }
}

function pills(ctx, labels, cy, height, size, w) {
  ctx.font = `700 ${size}px ${FONT}`;
  const padX = height * 0.45;
  const gap = height * 0.25;
  const widths = labels.map((l) => ctx.measureText(l).width + padX * 2);
  const total = widths.reduce((a, b) => a + b, 0) + gap * (labels.length - 1);
  let x = (w - total) / 2;
  labels.forEach((label, i) => {
    roundRect(ctx, x, cy, widths[i], height, height / 2);
    ctx.fillStyle = 'rgba(255,255,255,0.12)';
    ctx.fill();
    ctx.fillStyle = '#fff';
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    ctx.fillText(label, x + widths[i] / 2, cy + height / 2 + 1);
    x += widths[i] + gap;
  });
}

export async function renderMatchImage(data, formatKey = 'story') {
  const { w, h } = FORMATS[formatKey];
  const L = LAYOUT[formatKey];
  const canvas = document.createElement('canvas');
  canvas.width = w;
  canvas.height = h;
  const ctx = canvas.getContext('2d');

  const homeOurs = isOursName(data.home.name);
  const awayOurs = isOursName(data.away.name);
  const [club, homeImg, awayImg] = await Promise.all([
    loadImage('/logo.png'),
    loadImage(homeOurs ? '/logo.png' : data.home.logo),
    loadImage(awayOurs ? '/logo.png' : data.away.logo),
  ]);

  background(ctx, w, h);

  // Cabecera: escudo del club y marca
  if (club) {
    const [cy, size] = L.logo;
    ctx.drawImage(club, w / 2 - size / 2, cy - size / 2, size, size);
  }
  if (L.brand) text(ctx, 'VOLEIBOL ANCARES', w / 2, L.brand, { size: 34, weight: 800, color: MINT });

  // Titular y competición
  const head = headline(data);
  const headColor = data.kind === 'preview' ? MINT : '#fff';
  ctx.save();
  if (data.outcome === 'win') {
    ctx.shadowColor = 'rgba(49,169,67,0.9)';
    ctx.shadowBlur = 40;
  }
  text(ctx, head, w / 2, L.head, { size: data.kind === 'preview' ? L.headSize * 0.62 : L.headSize, weight: 900, color: headColor });
  ctx.restore();
  text(ctx, data.title, w / 2, L.title, { size: L.titleSize, weight: 600, color: 'rgba(255,255,255,0.75)' });

  // Escudos y nombres
  const [lx, rx] = L.crestX.map((f) => w * f);
  crest(ctx, homeImg, data.home, lx, L.crestY, L.crest, homeOurs);
  crest(ctx, awayImg, data.away, rx, L.crestY, L.crest, awayOurs);
  const nameWidth = w * (L.crestX[0] * 2 - 0.04);
  text(ctx, shortTeam(data.home.name), lx, L.name, { size: L.nameSize, weight: homeOurs ? 800 : 600, maxWidth: nameWidth });
  text(ctx, shortTeam(data.away.name), rx, L.name, { size: L.nameSize, weight: awayOurs ? 800 : 600, maxWidth: nameWidth });

  const K = data.kind === 'result' ? L.result : L.preview;
  const dim = 'rgba(255,255,255,0.72)';
  if (data.kind === 'result') {
    text(ctx, `${data.homeSets}–${data.awaySets}`, w / 2, K.score, { size: K.scoreSize, weight: 900, maxWidth: w * 0.34 });
    const labels = data.partials.map(([a, b, done = true]) => `${a}-${b}${done ? '' : '*'}`);
    if (labels.length) pills(ctx, labels, K.pills, K.pillH, K.pillSize, w);
    text(ctx, data.when, w / 2, K.when, { size: K.whenSize, weight: 700, color: 'rgba(255,255,255,0.85)' });
  } else {
    text(ctx, 'VS', w / 2, L.crestY + K.vsSize * 0.35, { size: K.vsSize, weight: 900, color: 'rgba(255,255,255,0.8)' });
    text(ctx, data.whenDate, w / 2, K.date, { size: K.dateSize, weight: 700, color: '#fff' });
    if (data.whenTime) text(ctx, data.whenTime, w / 2, K.time, { size: K.timeSize, weight: 900, color: '#fff' });
  }
  if (data.venue) paragraph(ctx, data.venue, w / 2, K.venue, { size: K.venueSize, color: dim, maxWidth: w * 0.86, maxLines: K.venueLines });

  // Banda: provisional o previsión del tiempo
  const band = data.provisional
    ? {
        label: `RESULTADO PROVISIONAL · pendiente de ${data.tournament ? 'confirmar' : 'la federación'}`,
        fill: 'rgba(242,165,22,0.18)',
        color: '#ffc861',
      }
    : data.weather
      ? { label: data.weather, fill: 'rgba(255,255,255,0.1)', color: '#fff' }
      : null;
  if (band) {
    const bw = w * 0.84;
    roundRect(ctx, (w - bw) / 2, K.band, bw, L.bandH, L.bandH / 2);
    ctx.fillStyle = band.fill;
    ctx.fill();
    ctx.textBaseline = 'middle';
    fitFont(ctx, band.label, bw - L.bandH, L.bandSize, 700);
    ctx.fillStyle = band.color;
    ctx.textAlign = 'center';
    ctx.fillText(band.label, w / 2, K.band + L.bandH / 2 + 2);
    ctx.textBaseline = 'alphabetic';
  }

  // Pie
  text(ctx, `Ancares Seguidores · app no oficial · ${location.host}`, w / 2, L.foot, {
    size: L.footSize, weight: 600, color: 'rgba(255,255,255,0.55)',
  });

  return new Promise((resolve) => canvas.toBlob(resolve, 'image/png'));
}

export function fileName(data) {
  const kind = data.kind === 'preview' ? 'previa' : 'resultado';
  const slug = (s) => shortTeam(s).toLowerCase().normalize('NFKD').replace(/[^\w]+/g, '-').replace(/^-|-$/g, '');
  return `ancares-${kind}-${slug(data.home.name)}-${slug(data.away.name)}.png`;
}
