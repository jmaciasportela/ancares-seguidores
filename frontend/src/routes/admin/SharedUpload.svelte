<script>
  import { onMount } from 'svelte';
  import Icon from '../../components/Icon.svelte';
  import { api } from '../../lib/api.js';
  import { pop } from '../../lib/motion.js';

  let { count, onDone } = $props();

  const SHARE_CACHE = 'shared-files';
  let files = $state([]); // {name, blob}
  let results = $state([]);
  let cats = $state([]);
  let busy = $state(true);
  let error = $state('');

  async function readShared() {
    if (!('caches' in window)) return [];
    const cache = await caches.open(SHARE_CACHE);
    const out = [];
    for (const req of await cache.keys()) {
      const res = await cache.match(req);
      out.push({ name: decodeURIComponent(res.headers.get('X-Filename') || 'fichero.xls'), blob: await res.blob() });
    }
    return out;
  }

  async function send(list, categoryId = null) {
    const form = new FormData();
    list.forEach((f) => form.append('files', f.blob, f.name));
    form.append('source', 'share');
    if (categoryId) form.append('category_id', categoryId);
    return (await api('/api/admin/upload', { method: 'POST', form })).results;
  }

  onMount(async () => {
    try {
      files = await readShared();
      if (!files.length) {
        error = 'No se encontraron los ficheros compartidos. Vuelve a compartirlos.';
        return;
      }
      results = await send(files);
      if (results.some((r) => r.status === 'needs_category')) cats = await api('/api/admin/categories');
      else await clear();
    } catch (err) {
      error = err.message;
    } finally {
      busy = false;
    }
  });

  async function clear() {
    if ('caches' in window) await caches.delete(SHARE_CACHE);
  }

  async function assign(index, categoryId) {
    if (!categoryId) return;
    busy = true;
    try {
      const [r] = await send([files[index]], categoryId);
      results[index] = r;
      if (!results.some((x) => x.status === 'needs_category')) await clear();
    } catch (err) {
      error = err.message;
    } finally {
      busy = false;
    }
  }

  async function close() {
    await clear();
    onDone();
  }

  const LABEL = { ok: 'Importado', unchanged: 'Sin cambios', error: 'Error', needs_category: 'Elige categoría' };
</script>

<section class="card box" in:pop>
  <header>
    <h3><Icon name="upload" size={18} /> Ficheros compartidos ({count})</h3>
    {#if !busy}<button class="x" onclick={close} aria-label="Cerrar"><Icon name="x" size={18} /></button>{/if}
  </header>

  {#if busy && !results.length}
    <p class="muted">Subiendo…</p>
  {/if}
  {#if error}<p class="err">{error}</p>{/if}

  {#each results as r, i}
    <div class="res">
      <div class="top">
        <span class="name ellipsis">{r.filename}</span>
        <span class="st {r.status}">{LABEL[r.status] || r.status}</span>
      </div>
      <span class="muted small">{r.category ? `${r.category} · ` : ''}{r.message}</span>
      {#if r.status === 'needs_category'}
        <select class="input" onchange={(e) => assign(i, e.currentTarget.value)} disabled={busy}>
          <option value="">Elegir categoría…</option>
          {#each cats as c}<option value={c.id}>{c.name}</option>{/each}
        </select>
      {/if}
    </div>
  {/each}
</section>

<style>
  .box {
    padding: 16px;
    margin-bottom: 16px;
    border-color: var(--brand);
  }
  header {
    display: flex;
    align-items: center;
    justify-content: space-between;
  }
  h3 {
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: 16px;
  }
  .x {
    width: 32px;
    height: 32px;
    display: grid;
    place-items: center;
  }
  .res {
    display: grid;
    gap: 6px;
    padding: 10px 0;
    border-top: 1px solid var(--line);
    margin-top: 10px;
  }
  .top {
    display: flex;
    gap: 8px;
    align-items: center;
  }
  .name {
    flex: 1;
    font-weight: 650;
    font-size: 14px;
  }
  .st {
    font-size: 12px;
    font-weight: 700;
    padding: 3px 8px;
    border-radius: 999px;
    background: var(--surface-2);
  }
  .st.ok,
  .st.unchanged {
    background: var(--brand-soft);
    color: var(--brand-strong);
  }
  .st.error {
    color: var(--danger);
  }
  .st.needs_category {
    color: #b07400;
  }
  .small {
    font-size: 13px;
  }
  .err {
    color: var(--danger);
  }
</style>
