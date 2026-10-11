<script>
  import { onMount } from 'svelte';
  import Icon from '../../components/Icon.svelte';
  import { api } from '../../lib/api.js';
  import { partialsText, timeAgo } from '../../lib/format.js';
  import { fly, pop } from '../../lib/motion.js';
  import { shareText } from '../../lib/share.js';
  import { toast } from '../../lib/toast.js';

  let scorers = $state([]);
  let provisional = $state([]);
  let loading = $state(true);
  let name = $state('');
  let creating = $state(false);
  let fresh = $state(null); // {name, code}: el código solo se ve una vez
  let confirmDelete = $state(null);

  async function load() {
    try {
      [scorers, provisional] = await Promise.all([api('/api/admin/scorers'), api('/api/admin/provisional')]);
    } catch (err) {
      toast(err.message, 'error');
    } finally {
      loading = false;
    }
  }
  onMount(load);

  async function create(e) {
    e.preventDefault();
    creating = true;
    try {
      fresh = await api('/api/admin/scorers', { method: 'POST', json: { name } });
      name = '';
      await load();
    } catch (err) {
      toast(err.message, 'error');
    } finally {
      creating = false;
    }
  }

  async function action(s, what) {
    try {
      const r = await api(`/api/admin/scorers/${s.id}/${what}`, { method: 'POST' });
      if (r.code) fresh = r;
      await load();
    } catch (err) {
      toast(err.message, 'error');
    }
  }

  async function remove(s) {
    if (confirmDelete !== s.id) {
      confirmDelete = s.id;
      return;
    }
    await api(`/api/admin/scorers/${s.id}`, { method: 'DELETE' });
    confirmDelete = null;
    await load();
  }

  async function removeProvisional(p) {
    await api(`/api/admin/provisional/${p.id}`, { method: 'DELETE' });
    toast('Resultado provisional borrado', 'ok');
    await load();
  }

  function shareCode() {
    shareText(
      `Hola ${fresh.name}: este es tu código de anotador de Ancares Seguidores: ${fresh.code}\n` +
        'Ábrelo en la app → Club → Funciones extra, e introdúcelo para publicar resultados provisionales desde el Marcador.',
    );
  }

  async function copyCode() {
    try {
      await navigator.clipboard.writeText(fresh.code);
      toast('Código copiado', 'ok');
    } catch {
      toast('No se pudo copiar', 'error');
    }
  }
</script>

<p class="muted hint">
  Cada anotador recibe un código que introduce en la app (Club → Funciones extra). Con él puede publicar resultados
  provisionales desde el Marcador. Revocarlo lo desactiva al momento en todos sus móviles.
</p>

<form class="card create" onsubmit={create}>
  <input class="input" bind:value={name} placeholder="Nombre (p. ej. Ana, madre de Lucía)" maxlength="100" required />
  <button class="btn primary" disabled={creating || !name.trim()}><Icon name="plus" size={16} /> Crear</button>
</form>

{#if fresh}
  <div class="card code-box" in:pop>
    <span class="muted small">Código de <b>{fresh.name}</b>. Apúntalo o compártelo ahora: no se volverá a mostrar.</span>
    <b class="code">{fresh.code}</b>
    <div class="row">
      <button class="btn small" onclick={copyCode}>Copiar</button>
      <button class="btn small primary" onclick={shareCode}><Icon name="share" size={15} /> Compartir</button>
      <button class="btn small ghost" onclick={() => (fresh = null)}>Hecho</button>
    </div>
  </div>
{/if}

{#if loading}
  <div class="skeleton" style="height:120px"></div>
{/if}

<div class="list">
  {#each scorers as s, i (s.id)}
    <article class="card item" class:off={!s.active} in:fly={{ y: 10, delay: i * 40 }}>
      <div class="head">
        <span class="avatar"><Icon name="key" size={18} /></span>
        <div class="info">
          <b class="ellipsis">{s.name}</b>
          <span class="muted small">{s.active ? 'Activo' : 'Revocado'} · último uso {timeAgo(s.last_used_at)}</span>
        </div>
      </div>
      <div class="row">
        {#if s.active}
          <button class="btn small" onclick={() => action(s, 'revoke')}>Revocar</button>
        {:else}
          <button class="btn small" onclick={() => action(s, 'activate')}>Reactivar</button>
        {/if}
        <button class="btn small" onclick={() => action(s, 'regenerate')}>Nuevo código</button>
        <button class="btn small danger" onclick={() => remove(s)} aria-label="Borrar">
          <Icon name="trash" size={15} />{#if confirmDelete === s.id}¿Seguro?{/if}
        </button>
      </div>
    </article>
  {/each}
</div>

<h3 class="section-title">Resultados provisionales</h3>
{#if !provisional.length && !loading}
  <div class="card empty muted">No hay resultados provisionales pendientes.</div>
{/if}
<div class="list">
  {#each provisional as p (p.id)}
    <article class="card item">
      <div class="info">
        <b class="ellipsis">{p.home} {p.home_sets} - {p.away_sets} {p.away}</b>
        <span class="muted small">{p.category} · Jornada {p.round_no} · {partialsText(p)}</span>
        <span class="muted small">Por {p.by} · {timeAgo(p.updated_at)}{p.finished_early ? ' · terminado antes de tiempo' : ''}</span>
      </div>
      <div class="row">
        <button class="btn small danger" onclick={() => removeProvisional(p)}><Icon name="trash" size={15} /> Borrar</button>
      </div>
    </article>
  {/each}
</div>

<style>
  .hint {
    font-size: 13px;
    margin: 0 2px 12px;
  }
  .small {
    font-size: 12.5px;
  }
  .create {
    display: flex;
    gap: 8px;
    padding: 10px;
  }
  .create .input {
    flex: 1;
    min-width: 0;
  }
  .code-box {
    display: grid;
    gap: 10px;
    justify-items: center;
    text-align: center;
    padding: 18px;
    margin-top: 12px;
    border-color: var(--brand);
  }
  .code {
    font-family: ui-monospace, 'SF Mono', Menlo, monospace;
    font-size: 30px;
    letter-spacing: 0.14em;
    color: var(--brand);
  }
  .list {
    display: grid;
    grid-template-columns: minmax(0, 1fr);
    gap: 10px;
    margin-top: 12px;
  }
  .item {
    padding: 12px 14px;
    display: grid;
    gap: 10px;
  }
  .item.off {
    opacity: 0.6;
  }
  .head {
    display: flex;
    align-items: center;
    gap: 12px;
  }
  .avatar {
    width: 38px;
    height: 38px;
    border-radius: 12px;
    display: grid;
    place-items: center;
    background: var(--brand-soft);
    color: var(--brand-strong);
    flex: none;
  }
  .info {
    flex: 1;
    min-width: 0;
    display: grid;
  }
  .row {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
  }
  .empty {
    padding: 20px;
    text-align: center;
  }
</style>
