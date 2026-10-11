<script>
  import BottomSheet from './BottomSheet.svelte';
  import Icon from './Icon.svelte';
  import { closeShare, shareRequest } from '../lib/shareSheet.js';
  import { route } from '../lib/router.js';
  import { shareText } from '../lib/share.js';
  import { describeWeather, weatherFor } from '../lib/weather.js';
  import { toast } from '../lib/toast.js';

  let format = $state('story');
  let url = $state(null);
  let blob = $state(null);
  let busy = $state(false);
  let mod = null; // shareImage.js, cargado la primera vez
  const isIOS = /iphone|ipad|ipod/i.test(navigator.userAgent);

  const req = $derived($shareRequest);

  // Cambiar de pantalla cierra el panel
  let lastPath = $route.path;
  $effect(() => {
    if ($route.path !== lastPath) {
      lastPath = $route.path;
      if (req) close();
    }
  });

  $effect(() => {
    const r = req;
    const f = format;
    if (!r) return;
    let alive = true;
    render(r, f).then((res) => {
      if (!alive) return URL.revokeObjectURL(res.url);
      if (url) URL.revokeObjectURL(url);
      ({ url, blob } = res);
    });
    return () => (alive = false);
  });

  async function render(r, f) {
    busy = true;
    try {
      mod ??= await import('../lib/shareImage.js');
      const data = { ...r.data };
      if (data.weatherMatch) {
        try {
          const wx = await weatherFor(data.weatherMatch);
          if (wx.available) {
            const d = describeWeather(wx.weather_code, wx.is_day);
            data.weather = `${d.icon}  ${Math.round(wx.temperature)}° · ${d.label} · ${wx.place}`;
          }
        } catch {
          /* sin tiempo: la imagen sale igual */
        }
      }
      const b = await mod.renderMatchImage(data, f);
      return { url: URL.createObjectURL(b), blob: b };
    } finally {
      busy = false;
    }
  }

  async function shareImage() {
    if (!blob || !mod) return;
    const file = new File([blob], mod.fileName(req.data), { type: 'image/png' });
    if (navigator.canShare?.({ files: [file] })) {
      try {
        await navigator.share({ files: [file], title: 'Ancares Seguidores' });
        close();
      } catch (err) {
        if (err?.name !== 'AbortError') toast('No se pudo compartir la imagen', 'error');
      }
    } else {
      const a = document.createElement('a');
      a.href = url;
      a.download = file.name;
      a.click();
      toast(isIOS ? 'Mantén pulsada la imagen para guardarla' : 'Imagen descargada', 'ok');
    }
  }

  function close() {
    closeShare();
    if (url) URL.revokeObjectURL(url);
    url = blob = null;
  }
</script>

<BottomSheet open={!!req} onClose={close}>
  <h3 class="title">Compartir</h3>
  <div class="formats" role="radiogroup" aria-label="Formato de la imagen">
    <button role="radio" aria-checked={format === 'story'} class:on={format === 'story'} onclick={() => (format = 'story')}>Historia</button>
    <button role="radio" aria-checked={format === 'square'} class:on={format === 'square'} onclick={() => (format = 'square')}>Cuadrado</button>
  </div>
  <div class="preview" class:square={format === 'square'} class:busy>
    {#if url}<img src={url} alt="Vista previa de la imagen para compartir" />{/if}
  </div>
  <button class="btn primary" onclick={shareImage} disabled={!blob || busy}><Icon name="share" size={18} /> Compartir imagen</button>
  <button class="btn" onclick={() => { shareText(req.text); close(); }}>Solo texto</button>
</BottomSheet>

<style>
  .title {
    text-align: center;
    font-size: 18px;
    font-weight: 800;
  }
  .formats {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 4px;
    padding: 4px;
    border-radius: 12px;
    background: var(--surface-2);
  }
  .formats button {
    min-height: 36px;
    border-radius: 9px;
    font-weight: 650;
    font-size: 14px;
    color: var(--muted);
  }
  .formats button.on {
    background: var(--surface);
    color: var(--text);
    box-shadow: 0 1px 3px rgba(0, 0, 0, 0.12);
  }
  .preview {
    justify-self: center;
    height: min(46dvh, 420px);
    aspect-ratio: 9 / 16;
    max-width: 100%;
    border-radius: 16px;
    overflow: hidden;
    background: #0b1a10;
    box-shadow: 0 10px 30px rgba(0, 0, 0, 0.3);
    transition: aspect-ratio 0.25s, opacity 0.2s;
  }
  .preview.square {
    aspect-ratio: 1;
    height: auto;
    width: min(100%, 360px);
  }
  .preview.busy {
    opacity: 0.6;
  }
  .preview img {
    width: 100%;
    height: 100%;
    object-fit: contain;
    display: block;
  }
</style>
