<script>
  import { onMount } from 'svelte';
  import { api } from '../../lib/api.js';
  import { timeAgo } from '../../lib/format.js';
  import { toast } from '../../lib/toast.js';

  const KIND = { ranking: 'Clasificación', calendar: 'Calendario' };
  const SOURCE = { auto: 'automática', manual: 'subida', share: 'compartido' };
  let logs = $state([]);
  let loading = $state(true);

  onMount(async () => {
    try {
      logs = await api('/api/admin/logs?limit=100');
    } catch (err) {
      toast(err.message, 'error');
    } finally {
      loading = false;
    }
  });
</script>

{#if loading}
  <div class="skeleton" style="height:200px"></div>
{:else if !logs.length}
  <div class="card empty muted">Sin actividad todavía.</div>
{:else}
  <div class="card list">
    {#each logs as l (l.id)}
      <div class="log">
        <span class="dot {l.status}"></span>
        <div class="body">
          <div class="line">
            <b class="ellipsis">{l.category || '—'} · {KIND[l.kind] || l.kind}</b>
            <span class="muted small">{timeAgo(l.created_at)}</span>
          </div>
          <span class="muted small">{l.status} ({SOURCE[l.source] || l.source}){l.message ? ` — ${l.message}` : ''}</span>
        </div>
      </div>
    {/each}
  </div>
{/if}

<style>
  .list {
    padding: 4px 14px;
  }
  .log {
    display: flex;
    gap: 10px;
    padding: 10px 0;
  }
  .log + .log {
    border-top: 1px solid var(--line);
  }
  .dot {
    flex: none;
    width: 10px;
    height: 10px;
    border-radius: 50%;
    margin-top: 6px;
    background: var(--muted);
  }
  .dot.ok,
  .dot.unchanged {
    background: var(--brand);
  }
  .dot.blocked {
    background: var(--warn);
  }
  .dot.error {
    background: var(--danger);
  }
  .body {
    flex: 1;
    min-width: 0;
    display: grid;
    gap: 2px;
  }
  .line {
    display: flex;
    justify-content: space-between;
    gap: 8px;
  }
  .small {
    font-size: 12.5px;
    word-break: break-word;
  }
  .empty {
    padding: 24px;
    text-align: center;
  }
</style>
