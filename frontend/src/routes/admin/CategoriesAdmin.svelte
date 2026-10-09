<script>
  import { onMount } from 'svelte';
  import { slide } from 'svelte/transition';
  import Icon from '../../components/Icon.svelte';
  import { api } from '../../lib/api.js';
  import { timeAgo } from '../../lib/format.js';
  import { fly, reduced } from '../../lib/motion.js';
  import { toast } from '../../lib/toast.js';
  import CategoryForm from './CategoryForm.svelte';

  const STATUS = {
    ok: { label: 'Al día', cls: 'ok' },
    manual: { label: 'Subida manual', cls: 'ok' },
    blocked: { label: 'Bloqueado por la FVCL', cls: 'warn' },
    error: { label: 'Error', cls: 'err' },
    pending: { label: 'Sin datos', cls: '' },
  };

  let cats = $state([]);
  let loading = $state(true);
  let creating = $state(false);
  let editing = $state(null);
  let confirmDelete = $state(null);
  let syncing = $state(null); // id o 'all'
  let uploading = $state(null);

  async function load() {
    try {
      cats = await api('/api/admin/categories');
    } catch (err) {
      toast(err.message, 'error');
    } finally {
      loading = false;
    }
  }
  onMount(load);

  async function create(data) {
    try {
      await api('/api/admin/categories', { method: 'POST', json: data });
      creating = false;
      toast('Categoría creada', 'ok');
      await load();
    } catch (err) {
      toast(err.message, 'error');
    }
  }

  async function update(id, data) {
    try {
      await api(`/api/admin/categories/${id}`, { method: 'PUT', json: data });
      editing = null;
      toast('Guardado', 'ok');
      await load();
    } catch (err) {
      toast(err.message, 'error');
    }
  }

  async function remove(id) {
    if (confirmDelete !== id) {
      confirmDelete = id;
      setTimeout(() => confirmDelete === id && (confirmDelete = null), 4000);
      return;
    }
    try {
      await api(`/api/admin/categories/${id}`, { method: 'DELETE' });
      toast('Categoría eliminada', 'ok');
      confirmDelete = null;
      await load();
    } catch (err) {
      toast(err.message, 'error');
    }
  }

  async function sync(id = null) {
    syncing = id ?? 'all';
    try {
      const { report } = await api('/api/admin/sync', { method: 'POST', json: { category_id: id } });
      const bad = report.filter((r) => r.status === 'blocked' || r.status === 'error');
      if (!report.length) toast('No hay enlaces que sincronizar', 'error');
      else if (bad.length) toast(`${bad.length} fichero(s) sin descargar: súbelos a mano`, 'error', 5000);
      else toast('Sincronizado', 'ok');
      await load();
    } catch (err) {
      toast(err.message, 'error');
    } finally {
      syncing = null;
    }
  }

  async function upload(cat, event) {
    const files = [...event.currentTarget.files];
    event.currentTarget.value = '';
    if (!files.length) return;
    uploading = cat.id;
    const form = new FormData();
    files.forEach((f) => form.append('files', f));
    form.append('category_id', cat.id);
    try {
      const { results } = await api('/api/admin/upload', { method: 'POST', form });
      const msgs = results.map((r) => `${r.kind === 'ranking' ? 'Clasificación' : 'Calendario'}: ${r.message}`);
      toast(msgs.join(' · '), results.some((r) => r.status === 'error') ? 'error' : 'ok', 5000);
      await load();
    } catch (err) {
      toast(err.message, 'error', 5000);
    } finally {
      uploading = null;
    }
  }
</script>

<div class="toolbar">
  <button class="btn primary small" onclick={() => (creating = !creating)}>
    <Icon name={creating ? 'x' : 'plus'} size={16} />
    {creating ? 'Cancelar' : 'Nueva categoría'}
  </button>
  <button class="btn small" onclick={() => sync()} disabled={syncing !== null || !cats.length}>
    <Icon name="refresh" size={16} />
    {syncing === 'all' ? 'Sincronizando…' : 'Sincronizar todo'}
  </button>
</div>

{#if creating}
  <div class="card pad" transition:slide={{ duration: reduced ? 0 : 250 }}>
    <h3>Nueva categoría</h3>
    <CategoryForm onSave={create} onCancel={() => (creating = false)} />
  </div>
{/if}

{#if loading}
  <div class="skeleton" style="height:160px"></div>
{:else if !cats.length && !creating}
  <div class="card pad empty">
    <p>Aún no hay categorías. Crea la primera con los enlaces de los Excel de la FVCL.</p>
  </div>
{/if}

<div class="list">
  {#each cats as cat, i (cat.id)}
    <article class="card pad cat" in:fly={{ y: 12, delay: i * 50 }}>
      {#if editing === cat.id}
        <h3>Editar «{cat.name}»</h3>
        <CategoryForm initial={cat} onSave={(d) => update(cat.id, d)} onCancel={() => (editing = null)} />
      {:else}
        <header>
          <div class="t">
            <h3 class="ellipsis">{cat.name}</h3>
            <span class="muted small ellipsis">{cat.fvcl_name || 'Sin nombre FVCL'} · {cat.active ? 'visible' : 'oculta'}</span>
          </div>
          <span class="status {STATUS[cat.sync_status]?.cls}">{STATUS[cat.sync_status]?.label || cat.sync_status}</span>
        </header>

        <div class="stats muted small">
          <span>{cat.teams} equipos</span>
          <span>{cat.matches} partidos</span>
          <span>Datos {timeAgo(cat.updated_at)}</span>
        </div>
        {#if cat.last_error}
          <p class="error small">{cat.last_error}</p>
        {/if}

        <div class="links">
          {#if cat.ranking_url}
            <a class="btn small ghost" href={cat.ranking_url} target="_blank" rel="noopener"><Icon name="download" size={16} /> Clasificación</a>
          {/if}
          {#if cat.calendar_url}
            <a class="btn small ghost" href={cat.calendar_url} target="_blank" rel="noopener"><Icon name="download" size={16} /> Calendario</a>
          {/if}
        </div>

        <div class="actions">
          <label class="btn small primary" class:disabled={uploading === cat.id}>
            <Icon name="upload" size={16} />
            {uploading === cat.id ? 'Subiendo…' : 'Subir Excel'}
            <input type="file" accept=".xls,application/vnd.ms-excel" multiple onchange={(e) => upload(cat, e)} hidden />
          </label>
          <button class="btn small" onclick={() => sync(cat.id)} disabled={syncing !== null}>
            <Icon name="refresh" size={16} />
            {syncing === cat.id ? '…' : 'Sincronizar'}
          </button>
          <button class="btn small" onclick={() => (editing = cat.id)} aria-label="Editar"><Icon name="edit" size={16} /></button>
          <button class="btn small danger" onclick={() => remove(cat.id)} aria-label="Eliminar">
            <Icon name="trash" size={16} />
            {#if confirmDelete === cat.id}¿Seguro?{/if}
          </button>
        </div>
      {/if}
    </article>
  {/each}
</div>

<div class="card pad help">
  <h3>¿Cómo actualizar si la federación bloquea la descarga?</h3>
  <ol class="small">
    <li>Pulsa <b>Clasificación</b> o <b>Calendario</b>: se abre la web de la FVCL y se descarga el Excel.</li>
    <li>En Android: desde la descarga, <b>Compartir → Ancares</b>. Se sube solo.</li>
    <li>En iPhone u ordenador: vuelve aquí y pulsa <b>Subir Excel</b> (puedes elegir los dos a la vez).</li>
  </ol>
</div>

<style>
  .toolbar {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
    margin-bottom: 14px;
  }
  .pad {
    padding: 16px;
  }
  h3 {
    font-size: 16.5px;
    font-weight: 800;
    margin-bottom: 12px;
  }
  .list {
    display: grid;
    gap: 12px;
    margin: 14px 0;
  }
  .cat header {
    display: flex;
    align-items: flex-start;
    gap: 10px;
  }
  .cat header h3 {
    margin-bottom: 2px;
  }
  .t {
    flex: 1;
    min-width: 0;
    display: grid;
  }
  .small {
    font-size: 13px;
  }
  .status {
    flex: none;
    font-size: 12px;
    font-weight: 700;
    padding: 4px 10px;
    border-radius: 999px;
    background: var(--surface-2);
    color: var(--muted);
  }
  .status.ok {
    background: var(--brand-soft);
    color: var(--brand-strong);
  }
  .status.warn {
    background: rgba(242, 165, 22, 0.15);
    color: #b07400;
  }
  .status.err {
    background: rgba(229, 72, 77, 0.12);
    color: var(--danger);
  }
  .stats {
    display: flex;
    flex-wrap: wrap;
    gap: 4px 14px;
    margin: 10px 0 4px;
  }
  .error {
    color: var(--danger);
    margin: 6px 0 0;
    word-break: break-word;
  }
  .links,
  .actions {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
    margin-top: 12px;
  }
  .disabled {
    opacity: 0.6;
    pointer-events: none;
  }
  .empty p {
    margin: 0;
    color: var(--muted);
  }
  .help ol {
    margin: 0;
    padding-left: 20px;
    display: grid;
    gap: 6px;
    line-height: 1.45;
  }
</style>
