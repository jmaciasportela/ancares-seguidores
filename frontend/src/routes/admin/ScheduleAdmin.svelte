<script>
  import { onMount } from 'svelte';
  import { slide } from 'svelte/transition';
  import Icon from '../../components/Icon.svelte';
  import TeamBadge from '../../components/TeamBadge.svelte';
  import { api } from '../../lib/api.js';
  import { formatDay, shortTeam } from '../../lib/format.js';
  import { reduced } from '../../lib/motion.js';
  import { toast } from '../../lib/toast.js';

  /** Horarios de una liga: el admin puede cambiar fecha, hora o pabellón y eso manda sobre el Excel. */
  let { category, onBack } = $props();

  let matches = $state([]);
  let loading = $state(true);
  let onlyOurs = $state(true);
  let showPlayed = $state(false);
  let editing = $state(null); // id del partido en edición
  let form = $state({ date: '', time: '', venue: '' });
  let saving = $state(false);

  const visible = $derived(matches.filter((m) => (!onlyOurs || m.is_ours) && (showPlayed || !m.played)));
  const rounds = $derived.by(() => {
    const out = [];
    for (const m of visible) {
      const last = out.at(-1);
      if (last?.round_no === m.round_no) last.matches.push(m);
      else out.push({ round_no: m.round_no, name: m.round_name, matches: [m] });
    }
    return out;
  });
  const changed = $derived(matches.filter((m) => m.override).length);
  const venues = $derived([...new Set(matches.flatMap((m) => [m.venue, m.excel.venue]).filter(Boolean))].sort());

  async function load() {
    try {
      matches = await api(`/api/admin/categories/${category.id}/schedule`);
    } catch (err) {
      toast(err.message, 'error');
    } finally {
      loading = false;
    }
  }
  onMount(load);

  const when = (s) => (s.date ? `${formatDay(`${s.date}T12:00:00`)} · ${s.time}` : 'Sin fecha');

  function edit(m) {
    editing = m.id;
    form = { date: m.date || '', time: m.time || '', venue: m.override && m.venue !== m.excel.venue ? m.venue : '' };
  }

  function replace(updated) {
    matches = matches.map((m) => (m.id === updated.id ? updated : m));
  }

  async function save(e) {
    e.preventDefault();
    saving = true;
    try {
      replace(await api(`/api/admin/matches/${editing}/schedule`, { method: 'PUT', json: form }));
      toast('Horario cambiado. Se mantendrá aunque se vuelva a importar el Excel.', 'ok', 4000);
      editing = null;
    } catch (err) {
      toast(err.message, 'error', 5000);
    } finally {
      saving = false;
    }
  }

  async function restore(m) {
    try {
      replace(await api(`/api/admin/matches/${m.id}/schedule`, { method: 'DELETE' }));
      toast('Vuelve a usarse el horario del Excel', 'ok');
      editing = null;
    } catch (err) {
      toast(err.message, 'error');
    }
  }
</script>

<header class="head">
  <button class="btn small ghost" onclick={onBack}><Icon name="back" size={16} /> Categorías</button>
  <h3 class="ellipsis">Horarios · {category.name}</h3>
</header>

<p class="muted small intro">
  Si un partido se juega otro día, a otra hora o en otro pabellón que los del Excel, cámbialo aquí: lo que pongas
  <b>manda siempre</b>, aunque se vuelva a importar el calendario. Puedes volver al del Excel cuando quieras.
</p>

<div class="filters">
  <label class="check"><input type="checkbox" bind:checked={onlyOurs} /> Solo Ancares</label>
  <label class="check"><input type="checkbox" bind:checked={showPlayed} /> Ver jugados</label>
  {#if changed}<span class="count">{changed} {changed === 1 ? 'cambiado' : 'cambiados'} a mano</span>{/if}
</div>

{#if loading}
  <div class="skeleton" style="height:160px"></div>
{:else if !rounds.length}
  <div class="card pad empty muted">No hay partidos pendientes{onlyOurs ? ' de Ancares' : ''}.</div>
{:else}
  <datalist id="venues">{#each venues as v (v)}<option value={v}></option>{/each}</datalist>
  {#each rounds as r (r.round_no)}
    <h4 class="round">{r.name}</h4>
    <div class="card list">
      {#each r.matches as m (m.id)}
        <div class="match" class:changed={m.override}>
          <div class="teams">
            <span class="team"><TeamBadge name={m.home} size={22} /> <span class="ellipsis" class:ours={m.is_ours && /ancares/i.test(m.home)}>{shortTeam(m.home)}</span></span>
            <span class="team"><TeamBadge name={m.away} size={22} /> <span class="ellipsis" class:ours={m.is_ours && /ancares/i.test(m.away)}>{shortTeam(m.away)}</span></span>
          </div>
          <div class="when">
            <b>{when(m)}</b>
            <span class="muted small ellipsis">{m.venue || 'Pabellón por confirmar'}</span>
            {#if m.override}
              <span class="tag">Cambiado a mano</span>
              <span class="muted small excel">Excel: {when(m.excel)}{m.excel.venue && m.excel.venue !== m.venue ? ` · ${m.excel.venue}` : ''}</span>
            {/if}
          </div>
          {#if editing !== m.id}
            <button class="btn small ghost edit" onclick={() => edit(m)} aria-label="Cambiar horario"><Icon name="edit" size={16} /></button>
          {/if}
        </div>
        {#if editing === m.id}
          <form class="editor" onsubmit={save} transition:slide={{ duration: reduced ? 0 : 200 }}>
            <div class="grid">
              <label class="field"><span>Fecha</span><input class="input" type="date" bind:value={form.date} /></label>
              <label class="field"><span>Hora</span><input class="input" type="time" bind:value={form.time} /></label>
            </div>
            <label class="field">
              <span>Pabellón <span class="muted">(vacío: el del Excel{m.excel.venue ? `, ${m.excel.venue}` : ''})</span></span>
              <input class="input" list="venues" bind:value={form.venue} maxlength="200" placeholder={m.excel.venue || 'Pabellón'} />
            </label>
            <div class="row">
              <button class="btn small primary" disabled={saving}>{saving ? 'Guardando…' : 'Guardar'}</button>
              <button type="button" class="btn small" onclick={() => (editing = null)}>Cancelar</button>
              {#if m.override}
                <button type="button" class="btn small ghost" onclick={() => restore(m)}><Icon name="undo" size={16} /> Volver al del Excel</button>
              {/if}
            </div>
          </form>
        {/if}
      {/each}
    </div>
  {/each}
{/if}

<style>
  .head {
    display: flex;
    align-items: center;
    gap: 10px;
    margin-bottom: 8px;
  }
  .head h3 {
    font-size: 17px;
    font-weight: 800;
    min-width: 0;
  }
  .intro {
    margin: 0 0 10px;
  }
  .filters {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 8px 16px;
    margin-bottom: 8px;
  }
  .check {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    font-size: 14px;
  }
  .count {
    margin-left: auto;
    font-size: 13px;
    font-weight: 700;
    color: var(--brand-strong);
  }
  .round {
    margin: 14px 2px 6px;
    font-size: 13px;
    font-weight: 800;
    letter-spacing: 0.06em;
    text-transform: uppercase;
    color: var(--muted);
  }
  .list {
    padding: 2px 12px;
  }
  .match {
    display: grid;
    grid-template-columns: minmax(0, 1fr) minmax(0, 1.1fr) auto;
    align-items: center;
    gap: 10px;
    padding: 10px 0;
  }
  .match + .match,
  .editor + .match {
    border-top: 1px solid var(--line);
  }
  .teams,
  .when {
    display: grid;
    gap: 4px;
    min-width: 0;
  }
  .team {
    display: flex;
    align-items: center;
    gap: 6px;
    font-size: 14px;
    min-width: 0;
  }
  .ours {
    font-weight: 800;
  }
  .when b {
    font-size: 14px;
  }
  .changed .when b {
    color: var(--brand-strong);
  }
  .tag {
    justify-self: start;
    padding: 1px 8px;
    border-radius: 999px;
    font-size: 11.5px;
    font-weight: 800;
    background: var(--brand-soft);
    color: var(--brand-strong);
  }
  .excel {
    text-decoration: line-through;
  }
  .edit {
    width: 36px;
    height: 36px;
    padding: 0;
  }
  .editor {
    display: grid;
    gap: 10px;
    padding: 10px 0 14px;
  }
  .grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 8px;
  }
  .field {
    display: grid;
    gap: 4px;
    font-size: 13px;
    font-weight: 650;
  }
  .row {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
  }
  .small {
    font-size: 12.5px;
  }
  .empty {
    padding: 24px;
    text-align: center;
  }
</style>
