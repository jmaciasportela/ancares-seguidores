<script>
  import { describeWeather, weatherFor } from '../lib/weather.js';
  import { formatDay } from '../lib/format.js';
  import { fade } from '../lib/motion.js';

  /** tone: 'dark' (sobre la tarjeta verde) o 'light'; compact: una sola línea */
  let { match, tone = 'light', compact = false } = $props();
  let data = $state(null);

  $effect(() => {
    data = null;
    if (!match?.starts_at || match.is_bye) return;
    let alive = true;
    weatherFor(match)
      .then((d) => alive && (data = d))
      .catch(() => {});
    return () => (alive = false);
  });

  const w = $derived(data?.available ? describeWeather(data.weather_code, data.is_day) : null);
  const temp = $derived(data?.available ? Math.round(data.temperature) : null);
</script>

{#if w}
  <div class="weather {tone}" class:compact in:fade title="Previsión para {data.place} a la hora del partido">
    <span class="icon" aria-hidden="true">{w.icon}</span>
    <span class="main"><b>{temp}°</b> {#if !compact}{w.label}{/if}</span>
    {#if data.precipitation_probability != null}
      <span class="extra">💧 {data.precipitation_probability}%</span>
    {/if}
    {#if !compact}
      <span class="extra">💨 {Math.round(data.wind_speed)} km/h</span>
      <span class="place">En {data.place}, a la hora del partido</span>
    {/if}
  </div>
{:else if data?.reason === 'too_far' && !compact}
  <div class="weather {tone} muted-line" in:fade>
    <span class="icon" aria-hidden="true">🌤️</span>
    <span class="place">Previsión del tiempo disponible a partir del {formatDay(data.available_from + 'T12:00:00Z').toLowerCase()}</span>
  </div>
{/if}

<style>
  .weather {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 4px 10px;
    padding: 8px 12px;
    border-radius: 14px;
    font-size: 14px;
  }
  .weather.dark {
    background: rgba(255, 255, 255, 0.1);
    color: #fff;
  }
  .weather.light {
    background: var(--surface-2);
    color: var(--text);
  }
  .weather.compact {
    flex: none;
    flex-wrap: nowrap;
    white-space: nowrap;
    padding: 4px 10px;
    border-radius: 999px;
    font-size: 13px;
    gap: 6px;
  }
  .icon {
    font-size: 22px;
    line-height: 1;
  }
  .compact .icon {
    font-size: 16px;
  }
  .main b {
    font-size: 17px;
    font-weight: 800;
  }
  .compact .main b {
    font-size: 14px;
  }
  .extra {
    opacity: 0.9;
    font-variant-numeric: tabular-nums;
  }
  .place {
    flex-basis: 100%;
    font-size: 12px;
    opacity: 0.75;
  }
  .muted-line .place {
    flex-basis: auto;
    flex: 1;
  }
</style>
