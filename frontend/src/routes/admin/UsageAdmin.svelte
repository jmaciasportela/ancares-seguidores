<script>
  import { onMount } from 'svelte';
  import { api } from '../../lib/api.js';
  import { fly } from '../../lib/motion.js';
  import { toast } from '../../lib/toast.js';

  const PLATFORM = { android: 'Android', ios: 'iPhone / iPad', desktop: 'Ordenador', otro: 'Otros' };
  const dayFmt = new Intl.DateTimeFormat('es-ES', { weekday: 'short', day: 'numeric', month: 'short' });

  let data = $state(null);
  let active = $state(null); // índice del día tocado en la gráfica

  onMount(async () => {
    try {
      data = await api('/api/admin/usage');
    } catch (err) {
      toast(err.message, 'error');
    }
  });

  const pct = (n, total) => (total ? Math.round((100 * n) / total) : 0);
  const maxDaily = $derived(data ? Math.max(1, ...data.daily.map((d) => d.devices)) : 1);
  const maxFreq = $derived(data ? Math.max(1, ...data.frequency.map((f) => f.devices)) : 1);
  const label = (iso) => dayFmt.format(new Date(iso + 'T12:00:00')).replace('.', '');
  const sorted = (obj) => Object.entries(obj || {}).sort((a, b) => b[1] - a[1]);

  // Gráfica de barras: 30 días
  const W = 340;
  const H = 120;
  const PAD = { top: 8, bottom: 18, left: 4, right: 4 };
  const step = (W - PAD.left - PAD.right) / 30;
  const barW = step - 2; // 2 px de separación entre barras
  const barH = (n) => (n / maxDaily) * (H - PAD.top - PAD.bottom);
</script>

{#if !data}
  <div class="skeleton" style="height:260px"></div>
{:else}
  <section class="tiles" in:fly={{ y: 10 }}>
    <div class="tile card"><b>{data.active_today}</b><span>activos hoy</span></div>
    <div class="tile card"><b>{data.active_7d}</b><span>últimos 7 días</span></div>
    <div class="tile card"><b>{data.active_30d}</b><span>últimos 30 días</span></div>
    <div class="tile card hero">
      <b>{data.installed_30d}</b>
      <span>instalaciones activas</span>
      <small>{pct(data.installed_30d, data.active_30d)}% de los activos del mes</small>
    </div>
  </section>
  <p class="muted small line">
    <span>{data.new_7d} nuevos esta semana</span> ·
    <span>{data.days_per_week ?? '–'} días de uso por semana de media</span> ·
    <span>{data.total_devices} dispositivos en total</span>
  </p>

  <section class="card block" in:fly={{ y: 10, delay: 60 }}>
    <h3>Dispositivos por día</h3>
    <svg viewBox="0 0 {W} {H}" role="img" aria-label="Dispositivos activos cada día de los últimos 30 días">
      <line class="base" x1={PAD.left} x2={W - PAD.right} y1={H - PAD.bottom} y2={H - PAD.bottom} />
      {#each data.daily as d, i}
        {@const h = barH(d.devices)}
        <g
          role="button"
          tabindex="0"
          aria-label="{label(d.day)}: {d.devices} dispositivos"
          onpointerdown={() => (active = i)}
          onfocus={() => (active = i)}
        >
          <rect class="hit" x={PAD.left + i * step} y={PAD.top} width={step} height={H - PAD.top - PAD.bottom} />
          {#if d.devices}
            <path
              class="bar"
              class:on={active === i}
              d="M{PAD.left + i * step + 1},{H - PAD.bottom}
                 v{-(h - Math.min(4, h))}
                 q0,{-Math.min(4, h)} {Math.min(4, barW / 2)},{-Math.min(4, h)}
                 h{barW - 2 * Math.min(4, barW / 2)}
                 q{Math.min(4, barW / 2)},0 {Math.min(4, barW / 2)},{Math.min(4, h)}
                 v{h - Math.min(4, h)} z"
            />
          {/if}
        </g>
      {/each}
      <text class="tick" x={PAD.left} y={H - 4}>{label(data.daily[0].day)}</text>
      <text class="tick" x={W - PAD.right} y={H - 4} text-anchor="end">hoy</text>
    </svg>
    <p class="readout">
      {#if active !== null}
        <b>{label(data.daily[active].day)}:</b> {data.daily[active].devices} dispositivos
      {:else}
        <span class="muted">Toca una barra para ver el día · máximo {maxDaily}</span>
      {/if}
    </p>
  </section>

  <section class="card block" in:fly={{ y: 10, delay: 120 }}>
    <h3>Frecuencia</h3>
    <p class="muted small">Días distintos que ha entrado cada dispositivo en los últimos 30 días</p>
    <div class="hbars">
      {#each data.frequency as f}
        <div class="hrow">
          <span class="hlabel">{f.label}</span>
          <span class="htrack"><i style="width:{(f.devices / maxFreq) * 100}%"></i></span>
          <b>{f.devices}</b>
        </div>
      {/each}
    </div>
  </section>

  <section class="card block" in:fly={{ y: 10, delay: 180 }}>
    <h3>Plataformas y versiones</h3>
    <div class="hbars">
      {#each sorted(data.platforms) as [key, n]}
        <div class="hrow">
          <span class="hlabel">{PLATFORM[key] || key}</span>
          <span class="htrack"><i style="width:{pct(n, data.active_30d)}%"></i></span>
          <b>{pct(n, data.active_30d)}%</b>
        </div>
      {/each}
    </div>
    <div class="versions">
      {#each sorted(data.versions) as [v, n]}
        <span class="chip">v{v} · {n}</span>
      {/each}
    </div>
  </section>

  <p class="muted small privacy">
    Datos anónimos: cada móvil envía un número aleatorio propio, si tiene la app instalada, su plataforma y la versión.
    No se guardan IPs ni datos personales, y se borran a los 180 días. Ojo: en iPhone, la app instalada y Safari cuentan
    como dos dispositivos.
  </p>
{/if}

<style>
  section {
    --series: var(--brand-strong);
  }
  @media (prefers-color-scheme: dark) {
    section {
      --series: var(--brand);
    }
  }
  .tiles {
    display: grid;
    grid-template-columns: repeat(3, minmax(0, 1fr));
    gap: 8px;
  }
  .tile {
    display: grid;
    justify-items: center;
    text-align: center;
    padding: 12px 6px;
  }
  .tile b {
    font-size: 26px;
    font-weight: 850;
    font-variant-numeric: tabular-nums;
  }
  .tile span {
    font-size: 12px;
    color: var(--muted);
  }
  .tile.hero {
    grid-column: 1 / -1;
    background: var(--brand-soft);
    border-color: transparent;
  }
  .tile.hero b {
    font-size: 34px;
    color: var(--series);
  }
  .tile.hero span {
    font-size: 14px;
    font-weight: 700;
    color: var(--text);
  }
  .tile small {
    font-size: 12px;
    color: var(--muted);
  }
  .small {
    font-size: 12.5px;
  }
  .line {
    text-align: center;
    margin: 10px 0 14px;
  }
  .line span {
    white-space: nowrap;
  }
  .block {
    padding: 14px 16px;
    margin-bottom: 12px;
  }
  h3 {
    font-size: 15px;
    font-weight: 800;
    margin-bottom: 8px;
  }
  .block > p {
    margin: -4px 0 10px;
  }
  svg {
    display: block;
    width: 100%;
    height: auto;
    touch-action: pan-y;
  }
  .base {
    stroke: var(--line);
  }
  .hit {
    fill: transparent;
  }
  g:focus {
    outline: none;
  }
  g:focus-visible .hit {
    stroke: var(--series);
    stroke-width: 1.5;
  }
  .bar {
    fill: var(--series);
    opacity: 0.85;
    transition: opacity 0.15s;
  }
  .bar.on {
    opacity: 1;
  }
  .tick {
    font-size: 10px;
    fill: var(--muted);
  }
  .readout {
    margin: 6px 0 0;
    min-height: 18px;
    text-align: center;
    font-size: 13px;
  }
  .hbars {
    display: grid;
    gap: 8px;
  }
  .hrow {
    display: grid;
    grid-template-columns: 92px 1fr 40px;
    align-items: center;
    gap: 10px;
    font-size: 13px;
  }
  .hlabel {
    color: var(--muted);
  }
  .hrow b {
    text-align: right;
    font-variant-numeric: tabular-nums;
  }
  .htrack {
    height: 10px;
    border-radius: 5px;
    background: var(--surface-2);
    overflow: hidden;
  }
  .htrack i {
    display: block;
    height: 100%;
    border-radius: 5px;
    background: var(--series);
    transition: width 0.6s var(--ease-out);
  }
  .versions {
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
    margin-top: 12px;
  }
  .privacy {
    margin: 4px 2px 0;
    line-height: 1.5;
  }
</style>
