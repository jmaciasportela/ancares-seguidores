<script>
  import { untrack } from 'svelte';

  let { initial = null, onSave, onCancel } = $props();

  // El formulario parte de una copia de `initial` y no debe seguir sus cambios
  const init = untrack(() => initial) || {};
  let f = $state({
    name: init.name ?? '',
    fvcl_name: init.fvcl_name ?? '',
    ranking_url: init.ranking_url ?? '',
    calendar_url: init.calendar_url ?? '',
    sort_order: init.sort_order ?? 0,
    active: init.active ?? true,
  });
  let busy = $state(false);

  async function submit(e) {
    e.preventDefault();
    busy = true;
    try {
      await onSave({ ...f, sort_order: Number(f.sort_order) || 0 });
    } finally {
      busy = false;
    }
  }
</script>

<form class="form" onsubmit={submit}>
  <div class="field">
    <label for="c-name">Nombre visible</label>
    <input id="c-name" class="input" bind:value={f.name} placeholder="Infantil Femenino" required maxlength="120" />
  </div>
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
