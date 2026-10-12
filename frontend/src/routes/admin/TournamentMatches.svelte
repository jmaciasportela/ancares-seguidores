<script>
  import { onMount } from 'svelte';
  import { slide } from 'svelte/transition';
  import Icon from '../../components/Icon.svelte';
  import TeamBadge from '../../components/TeamBadge.svelte';
  import { api } from '../../lib/api.js';
  import { formatDay, partialsText, shortTeam } from '../../lib/format.js';
  import { reduced } from '../../lib/motion.js';
  import { toast } from '../../lib/toast.js';

  let { category, onBack } = $props();

  const EMPTY = { phase: '', date: '', time: '', home: '', away: '', venue: '', result: '' };
  const EXAMPLE = '19/12 10:00 · Grupo A · Ancares UVa - CV Laguna · Pabellón Pisuerga';

  let matches = $state([]);
  let loading = $state(true);
  let form = $state({ ...EMPTY });
  let editing = $state(null); // id del partido en edición
  let showForm = $state(false);
  let saving = $state(false);
  let pasteOpen = $state(false);
  let pasteText = $state('');
  let preview = $state(null);
  let confirmDelete = $state(null);

  const phases = $derived([...new Set(matches.map((m) => m.phase))]);
  const teams = $derived([...new Set(matches.flatMap((m) => [m.home, m.away]))].sort());
  const venues = $derived([...new Set(matches.map((m) => m.venue).filter(Boolean))]);
  const byPhase = $derived(
    phases.map((p) => ({ name: p, matches: matches.filter((m) => m.phase === p) })).sort((a, b) => a.matches[0].round_no - b.matches[0].round_no),
  );
  const validRows = $derived(preview ? preview.filter((r) => !r.error) : []);

  async function load() {
    try {
      matches = await api(`/api/admin/categories/${category.id}/matches`);
    } catch (err) {
      toast(err.message, 'error');
    } finally {
      loading = false;
    }
  }
  onMount(load);

  function newMatch() {
    // Rellena fase, fecha y pabellón con los del último partido: suelen repetirse
    const last = matches.at(-1);
    form = { ...EMPTY, phase: last?.phase || '', date: last?.date || '', venue: last?.venue || '' };
    editing = null;
    showForm = true;
  }

  function edit(m) {
    form = { phase: m.phase, date: m.date || '', time: m.time || '', home: m.home, away: m.away, venue: m.venue || '', result: m.result || '' };
    editing = m.id;
    showForm = true;
  }

  async function save(e) {
    e.preventDefault();
    saving = true;
    try {
      if (editing) await api(`/api/admin/matches/${editing}`, { method: 'PUT', json: form });
      else await api(`/api/admin/categories/${category.id}/matches`, { method: 'POST', json: form });
      toast(editing ? 'Partido actualizado' : 'Partido añadido', 'ok');
      showForm = false;
      editing = null;
      await load();
    } catch (err) {
      toast(err.message, 'error', 5000);
    } finally {
      saving = false;
    }
  }

  async function remove(m) {
    if (confirmDelete !== m.id) {
      confirmDelete = m.id;
      return;
    }
    await api(`/api/admin/matches/${m.id}`, { method: 'DELETE' });
    confirmDelete = null;
    await load();
  }

  async function confirmProvisional(m) {
    try {
      await api(`/api/admin/provisional/${m.provisional.id}/confirm`, { method: 'POST' });
      toast('Resultado confirmado', 'ok');
      await load();
    } catch (err) {
      toast(err.message, 'error');
    }
  }

  async function review() {
    try {
      preview = (await api(`/api/admin/categories/${category.id}/matches/parse`, { method: 'POST', json: { text: pasteText } })).rows;
    } catch (err) {
      toast(err.message, 'error');
    }
  }

  async function addParsed() {
    const body = { matches: validRows.map(({ phase, date, time, home, away, venue }) => ({ phase, date, time, home, away, venue })) };
    try {
      const r = await api(`/api/admin/categories/${category.id}/matches/bulk`, { method: 'POST', json: body });
      toast(`${r.created} partidos añadidos`, 'ok');
      pasteText = '';
      preview = null;
      pasteOpen = false;
      await load();
    } catch (err) {
      toast(err.message, 'error', 5000);
    }
  }

  const when = (m) => (m.date ? `${formatDay(`${m.date}T12:00:00`)} · ${m.time}` : 'Sin fecha');
</script>

<header class="head">
  <button class="btn small ghost" onclick={onBack}><Icon name="back" size={16} /> Categorías</button>
  <h3 class="ellipsis">{category.name}</h3>
</header>

<div class="toolbar">
  <button class="btn primary small" onclick={newMatch}><Icon name="plus" size={16} /> Añadir partido</button>
  <button class="btn small" onclick={() => (pasteOpen = !pasteOpen)}><Icon name="list" size={16} /> Pegar lista</button>
</div>

{#if pasteOpen}
  <div class="card pad" transition:slide={{ duration: reduced ? 0 : 220 }}>
    <p class="muted small">
      Un partido por línea: fecha, hora, fase, equipos separados con « - » o « vs », y pabellón (opcionales salvo los equipos), separados con «·», «|» o «;». Por ejemplo:
      <code>{EXAMPLE}</code>
    </p>
    <textarea class="input" rows="6" bind:value={pasteText} placeholder={EXAMPLE}></textarea>
    <div class="row">
      <button class="btn small" onclick={review} disabled={!pasteText.trim()}>Revisar</button>
      {#if preview}
        <button class="btn small primary" onclick={addParsed} disabled={!validRows.length}>Añadir {validRows.length} partidos</button>
      {/if}
    </div>
    {#if preview}
      <div class="preview">
        {#each preview as r}
          <div class="prow" class:bad={r.error}>
            {#if r.error}
              <span class="err">✗ {r.error}</span><span class="muted line">{r.line}</span>
            {:else}
              <span>✓ <b>{r.home}</b> – <b>{r.away}</b></span>
              <span class="muted">{r.phase || 'Partidos'} · {r.date ? `${formatDay(`${r.date}T12:00:00`)} ${r.time}` : 'sin fecha'}{r.venue ? ` · ${r.venue}` : ''}</span>
            {/if}
          </div>
        {/each}
      </div>
    {/if}
  </div>
{/if}

{#if showForm}
  <form class="card pad mform" onsubmit={save} transition:slide={{ duration: reduced ? 0 : 220 }}>
    <h4>{editing ? 'Editar partido' : 'Nuevo partido'}</h4>
    <datalist id="phases">{#each phases as p}<option value={p}></option>{/each}</datalist>
    <datalist id="teams">{#each teams as t}<option value={t}></option>{/each}</datalist>
    <datalist id="venues">{#each venues as v}<option value={v}></option>{/each}</datalist>
    <label class="field"><span>Fase</span><input class="input" list="phases" bind:value={form.phase} placeholder="Grupo A, Semifinal, Final…" /></label>
    <div class="two">
      <label class="field"><span>Fecha</span><input class="input" type="date" bind:value={form.date} /></label>
      <label class="field"><span>Hora</span><input class="input" type="time" bind:value={form.time} required={!!form.date} /></label>
    </div>
    <div class="two">
      <label class="field"><span>Local</span><input class="input" list="teams" bind:value={form.home} required /></label>
      <label class="field"><span>Visitante</span><input class="input" list="teams" bind:value={form.away} required /></label>
    </div>
    <label class="field"><span>Pabellón</span><input class="input" list="venues" bind:value={form.venue} /></label>
    <label class="field">
      <span>Resultado <span class="opt">(opcional, vale como confirmado)</span></span>
      <input class="input" bind:value={form.result} placeholder="3-1 o 25-20 23-25 15-12" />
    </label>
    <div class="row end">
      <button type="button" class="btn ghost small" onclick={() => (showForm = false)}>Cancelar</button>
      <button class="btn primary small" disabled={saving}>{saving ? 'Guardando…' : 'Guardar'}</button>
    </div>
  </form>
{/if}

{#if loading}
  <div class="skeleton" style="height:160px"></div>
{:else if !matches.length}
  <div class="card pad empty muted">Aún no hay partidos. Añádelos uno a uno o pega la lista completa.</div>
{/if}

{#each byPhase as phase (phase.name)}
  <h4 class="phase">{phase.name}</h4>
  <div class="list">
    {#each phase.matches as m (m.id)}
      <article class="card match" class:ours={m.is_ours}>
        <div class="teams">
          <span class="team"><TeamBadge name={m.home} size={22} /> <span class="ellipsis">{shortTeam(m.home)}</span>{#if m.home_sets !== null}<b>{m.home_sets}</b>{/if}</span>
          <span class="team"><TeamBadge name={m.away} size={22} /> <span class="ellipsis">{shortTeam(m.away)}</span>{#if m.away_sets !== null}<b>{m.away_sets}</b>{/if}</span>
        </div>
        <span class="muted small">{when(m)}{m.venue ? ` · ${m.venue}` : ''}{m.partials.length ? ` · ${partialsText(m)}` : ''}</span>
        {#if m.provisional}
          <div class="prov">
            <span>⏳ Provisional de <b>{m.provisional.by}</b>: {m.provisional.home_sets}-{m.provisional.away_sets}</span>
            <button class="btn small primary" onclick={() => confirmProvisional(m)}><Icon name="check" size={15} /> Confirmar</button>
          </div>
        {/if}
        <div class="row">
          <button class="btn small" onclick={() => edit(m)}><Icon name="edit" size={15} /> Editar</button>
          <button class="btn small danger" onclick={() => remove(m)} aria-label="Borrar partido">
            <Icon name="trash" size={15} />{#if confirmDelete === m.id} ¿Seguro?{/if}
          </button>
        </div>
      </article>
    {/each}
  </div>
{/each}

<style>
  .head {
    display: flex;
    align-items: center;
    gap: 10px;
    margin-bottom: 12px;
  }
  .head h3 {
    font-size: 17px;
    font-weight: 800;
    min-width: 0;
  }
  .toolbar,
  .row {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
  }
  .row.end {
    justify-content: flex-end;
  }
  .toolbar {
    margin-bottom: 12px;
  }
  .pad {
    padding: 14px;
    margin-bottom: 12px;
    display: grid;
    gap: 10px;
  }
  .small {
    font-size: 12.5px;
  }
  code {
    display: block;
    margin-top: 6px;
    font-size: 12px;
    white-space: normal;
    word-break: break-word;
  }
  textarea {
    min-height: 120px;
    font-family: ui-monospace, Menlo, monospace;
    font-size: 13px;
  }
  .preview {
    display: grid;
    gap: 6px;
  }
  .prow {
    display: grid;
    gap: 2px;
    padding: 8px 10px;
    border-radius: 10px;
    background: var(--brand-soft);
    font-size: 13px;
  }
  .prow.bad {
    background: rgba(229, 72, 77, 0.1);
  }
  .err {
    color: var(--danger);
    font-weight: 650;
  }
  .line {
    font-family: ui-monospace, Menlo, monospace;
    font-size: 12px;
    word-break: break-word;
  }
  .mform h4 {
    font-size: 15px;
  }
  .mform .field {
    margin: 0;
  }
  .mform .field > span {
    font-size: 13px;
    font-weight: 650;
    color: var(--muted);
  }
  .opt {
    font-weight: 500;
  }
  .two {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 10px;
  }
  .phase {
    font-size: 13px;
    font-weight: 800;
    letter-spacing: 0.06em;
    text-transform: uppercase;
    color: var(--muted);
    margin: 18px 2px 8px;
  }
  .list {
    display: grid;
    grid-template-columns: minmax(0, 1fr);
    gap: 8px;
  }
  .match {
    padding: 10px 12px;
    display: grid;
    gap: 6px;
    min-width: 0;
  }
  .match.ours {
    box-shadow: inset 3px 0 0 var(--brand);
  }
  .teams {
    display: grid;
    gap: 4px;
  }
  .team {
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: 14.5px;
    min-width: 0;
  }
  .team .ellipsis {
    flex: 1;
    min-width: 0;
  }
  .prov {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    justify-content: space-between;
    gap: 8px;
    padding: 8px 10px;
    border-radius: 10px;
    background: rgba(242, 165, 22, 0.14);
    font-size: 13.5px;
  }
  .empty {
    text-align: center;
  }
</style>
