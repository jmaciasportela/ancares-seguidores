<script>
  import { untrack } from 'svelte';
  import FormatPicker from '../../components/FormatPicker.svelte';
  import { DEFAULT_FORMAT } from '../../lib/scoring.js';

  let { initial = null, kind: initialKind = 'league', onSave, onCancel } = $props();

  // El formulario parte de una copia de `initial` y no debe seguir sus cambios
  const init = untrack(() => initial) || {};
  let f = $state({
    name: init.name ?? '',
    fvcl_name: init.fvcl_name ?? '',
    ranking_url: init.ranking_url ?? '',
    calendar_url: init.calendar_url ?? '',
    sort_order: init.sort_order ?? 0,
    active: init.active ?? true,
    score_format: init.score_format ?? { ...DEFAULT_FORMAT },
    kind: init.kind ?? untrack(() => initialKind),
    points_system: init.points_system ?? 'auto',
  });
  // Normativa FVCL 2026-27: Cadete, Infantil, Alevín y Benjamín puntúan 2-1-0; Juvenil, Júnior y Sénior, 3-2-1-0
  const POINTS = [
    { id: 'auto', label: 'Automática (recomendada)', hint: 'Según la normativa de la FVCL para la categoría, comprobada con la clasificación oficial.' },
    { id: '2-1-0', label: '2-1-0: Cadete, Infantil, Alevín, Benjamín', hint: '2 puntos por partido ganado y 1 por perdido, sea cual sea el resultado.' },
    { id: '3-2-1-0', label: '3-2-1-0: Juvenil, Júnior, Sénior', hint: '3 por ganar 3-0 o 3-1, 2 por ganar 3-2 y 1 por perder 2-3.' },
  ];
  const isTournament = $derived(f.kind === 'tournament');
  let busy = $state(false);

  async function submit(e) {
    e.preventDefault();
    busy = true;
    try {
      const data = { ...f, sort_order: Number(f.sort_order) || 0 };
      if (data.kind === 'tournament') Object.assign(data, { fvcl_name: '', ranking_url: '', calendar_url: '' });
      await onSave(data);
    } finally {
      busy = false;
    }
  }
</script>

<form class="form" onsubmit={submit}>
  <div class="kinds" role="radiogroup" aria-label="Tipo">
    <button type="button" role="radio" aria-checked={!isTournament} class:on={!isTournament} onclick={() => (f.kind = 'league')}>
      <b>Liga FVCL</b><span>Datos de los Excel de la federación</span>
    </button>
    <button type="button" role="radio" aria-checked={isTournament} class:on={isTournament} onclick={() => (f.kind = 'tournament')}>
      <b>Torneo</b><span>Partidos y fechas a mano</span>
    </button>
  </div>
  <div class="field">
    <label for="c-name">Nombre visible</label>
    <input id="c-name" class="input" bind:value={f.name} placeholder={isTournament ? 'Torneo de Navidad' : 'Infantil Femenino'} required maxlength="120" />
  </div>
  {#if !isTournament}
  <div class="field">
    <label for="c-fvcl">Nombre de la competición en la FVCL</label>
    <input id="c-fvcl" class="input" bind:value={f.fvcl_name} placeholder="CRE Infantil Femenino Liga Oro" maxlength="200" />
    <span class="hint">Tal y como aparece en el nombre del Excel («Calendario <b>CRE Infantil Femenino Liga Oro</b>.xls»). Sirve para reconocer los ficheros que compartas.</span>
  </div>
  <div class="field">
    <label for="c-rank">Enlace Excel de clasificación</label>
    <input id="c-rank" class="input" type="url" inputmode="url" bind:value={f.ranking_url} placeholder="https://fvcl.es/es/tournament/…/ranking/…/export-xls" />
  </div>
  <div class="field">
    <label for="c-cal">Enlace Excel de calendario</label>
    <input id="c-cal" class="input" type="url" inputmode="url" bind:value={f.calendar_url} placeholder="https://fvcl.es/es/tournament/…/calendar/…/all/export-xls" />
  </div>
  {/if}
  <div class="field">
    <span class="label">Formato del marcador</span>
    <FormatPicker bind:value={f.score_format} />
    <span class="hint">El Marcador lo propone al anotar partidos de esta categoría (se puede cambiar antes de empezar).</span>
  </div>
  <div class="field">
    <label for="c-points">Puntuación de la clasificación</label>
    <select id="c-points" class="input" bind:value={f.points_system}>
      {#each POINTS as p (p.id)}<option value={p.id}>{p.label}</option>{/each}
    </select>
    <span class="hint">
      {POINTS.find((p) => p.id === f.points_system)?.hint}
      {#if initial?.points_applied} Ahora se aplica: <b>{initial.points_applied.id}</b> ({initial.points_applied.source_label}).{/if}
      Se usa en la clasificación provisional, la evolución y los grupos de torneo; la tabla oficial viene tal cual de la federación.
    </span>
  </div>
  <div class="row">
    <div class="field">
      <label for="c-order">Orden</label>
      <input id="c-order" class="input" type="number" bind:value={f.sort_order} />
    </div>
    <label class="check">
      <input type="checkbox" bind:checked={f.active} />
      Visible en la app
    </label>
  </div>
  <div class="actions">
    {#if onCancel}<button type="button" class="btn ghost" onclick={onCancel}>Cancelar</button>{/if}
    <button class="btn primary" disabled={busy}>{busy ? 'Guardando…' : 'Guardar'}</button>
  </div>
</form>

<style>
  .form {
    padding: 4px 0;
  }
  .kinds {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 8px;
    margin-bottom: 14px;
  }
  .kinds button {
    display: grid;
    gap: 2px;
    text-align: left;
    padding: 10px 12px;
    border-radius: 14px;
    border: 1.5px solid var(--line);
    background: var(--surface);
  }
  .kinds b {
    font-size: 14.5px;
  }
  .kinds span {
    font-size: 12.5px;
    color: var(--muted);
  }
  .kinds button.on {
    border-color: var(--brand);
    background: var(--brand-soft);
  }
  .label {
    font-size: 13.5px;
    font-weight: 650;
    color: var(--muted);
  }
  .row {
    display: grid;
    grid-template-columns: 110px 1fr;
    gap: 16px;
    align-items: center;
  }
  .check {
    display: flex;
    align-items: center;
    gap: 8px;
    font-weight: 600;
    margin-top: 10px;
  }
  .check input {
    width: 20px;
    height: 20px;
    accent-color: var(--brand);
  }
  .actions {
    display: flex;
    justify-content: flex-end;
    gap: 8px;
  }
</style>
