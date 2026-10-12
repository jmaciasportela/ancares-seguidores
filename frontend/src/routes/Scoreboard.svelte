<script>
  import { onMount } from 'svelte';
  import BottomSheet from '../components/BottomSheet.svelte';
  import FormatPicker from '../components/FormatPicker.svelte';
  import Icon from '../components/Icon.svelte';
  import ScorePad from '../components/ScorePad.svelte';
  import TeamBadge from '../components/TeamBadge.svelte';
  import { api, resource } from '../lib/api.js';
  import { formatWhen, isOursName, partialsText, shortTeam } from '../lib/format.js';
  import { fly } from '../lib/motion.js';
  import { go, route } from '../lib/router.js';
  import { refreshScorer, scorer } from '../lib/scorer.js';
  import * as S from '../lib/scoring.js';
  import { scoreText } from '../lib/share.js';
  import { dataFromGame } from '../lib/shareData.js';
  import { openShare } from '../lib/shareSheet.js';
  import { toast } from '../lib/toast.js';

  const KEY = 'ancares:marcador';
  const FORMAT_KEY = 'ancares:marcador-formato';

  function read(key) {
    try {
      return JSON.parse(localStorage.getItem(key));
    } catch {
      return null;
    }
  }
  function write(key, value) {
    try {
      if (value) localStorage.setItem(key, JSON.stringify(value));
      else localStorage.removeItem(key);
    } catch {
      /* sin almacenamiento: el partido no sobrevive a una recarga */
    }
  }

  // $state.raw: el estado se sustituye entero en cada jugada (funciones puras)
  let game = $state.raw(read(KEY));
  $effect(() => write(KEY, game));
  const step = $derived(!game ? 'setup' : game.status === 'finished' ? 'summary' : 'play');

  // --- preparar -----------------------------------------------------------------
  let candidates = $state([]);
  let loadingCandidates = $state(true);
  let selected = $state(null); // id de partido o 'free'
  let freeHome = $state('Ancares');
  let freeAway = $state('');
  let format = $state(read(FORMAT_KEY) || { ...S.DEFAULT_FORMAT });

  const whenLabel = (m) => (Math.abs(m.minutes_from_now) <= 90 ? 'Ahora' : formatWhen(m.starts_at));
  const rivalOf = (m) => (isOursName(m.home) ? m.away : m.home);
  const rivalLogo = (m) => (isOursName(m.home) ? m.away_logo : m.home_logo);

  function choose(item) {
    selected = item === 'free' ? 'free' : item.id;
    if (item !== 'free' && item.score_format) format = { ...item.score_format };
  }

  onMount(async () => {
    refreshScorer();
    try {
      candidates = await api('/api/scoring/matches');
    } catch {
      candidates = [];
    } finally {
      loadingCandidates = false;
    }
    const pick = Number($route.query.get('pick'));
    const preferred = candidates.find((c) => c.id === pick) || candidates.find((c) => Math.abs(c.minutes_from_now) <= 240);
    choose(preferred || 'free');
  });

  function start() {
    write(FORMAT_KEY, format);
    const m = candidates.find((c) => c.id === selected);
    if (m) {
      game = S.newMatch({
        format,
        home: { name: m.home, logo: m.home_logo },
        away: { name: m.away, logo: m.away_logo },
        oursSide: isOursName(m.home) ? 'home' : 'away',
        match: pickMatch(m),
      });
    } else {
      const home = freeHome.trim() || 'Ancares';
      const away = freeAway.trim() || 'Rival';
      const oursSide = isOursName(home) ? 'home' : isOursName(away) ? 'away' : null;
      game = S.newMatch({ format, home: { name: home }, away: { name: away }, oursSide });
    }
  }

  const pickMatch = (m) => ({
    id: m.id,
    category_id: m.category_id,
    category: m.category,
    category_slug: m.category_slug,
    round_no: m.round_no,
    round_name: m.round_name,
    home: m.home,
    away: m.away,
    starts_at: m.starts_at,
  });

  // --- jugar ------------------------------------------------------------------
  // Ancares abajo por defecto (más a mano); "Cambiar lados" lo invierte
  const order = $derived.by(() => {
    if (!game) return [];
    const homeOnTop = game.oursSide !== 'home';
    return (game.swapped ? !homeOnTop : homeOnTop) ? ['home', 'away'] : ['away', 'home'];
  });
  const won = $derived(game ? S.setsWon(game) : { home: 0, away: 0 });
  const setNo = $derived(game ? game.sets.length : 0);
  const needed = $derived(game ? S.setsToWin(game.format) : null);
  const tone = (side) => ((game.oursSide || 'home') === side ? 'green' : 'dark');
  const hint = (side) => (S.isMatchPoint(game, side) ? 'Punto de partido' : S.isSetPoint(game, side) ? 'Punto de set' : '');
  const teamName = (side) => shortTeam(game[side].name);

  function tap(side) {
    const prev = game;
    const next = S.point(prev, side);
    if (next === prev) return;
    game = next;
    navigator.vibrate?.(12);
    if (S.isCourtChange(prev, next)) toast('Cambio de campo: un equipo ha llegado a 8', 'ok', 4000);
  }

  let menuOpen = $state(false);
  let confirmFinish = $state(false);
  let confirmDiscard = $state(false);

  function closeMenu() {
    menuOpen = false;
    confirmFinish = confirmDiscard = false;
  }

  // La pantalla no se apaga mientras se lleva el marcador
  $effect(() => {
    if (step !== 'play' || !('wakeLock' in navigator)) return;
    let lock = null;
    const acquire = async () => {
      try {
        if (document.visibilityState === 'visible') lock = await navigator.wakeLock.request('screen');
      } catch {
        /* el navegador puede denegarlo: no es grave */
      }
    };
    acquire();
    document.addEventListener('visibilitychange', acquire);
    return () => {
      document.removeEventListener('visibilitychange', acquire);
      lock?.release?.();
    };
  });

  // --- resumen ------------------------------------------------------------------
  const result = $derived(game && game.status === 'finished' ? S.toResult(game) : null);
  const winner = $derived(game ? S.matchWinner(game) : null);
  let assign = $state(null); // id de partido o 'none'
  let publishing = $state(false);
  let published = $state(null); // slug de la categoría publicada
  let confirmPublish = $state(false);
  // Partido de liga elegido para asignar el resultado
  const target = $derived(candidates.find((c) => c.id === assign) || null);
  let confirmNew = $state(false);

  // Partidos para asignar: primero los más cercanos a cuando empezó el marcador
  const assignable = $derived.by(() => {
    if (!game) return [];
    const t = game.startedAt;
    return [...candidates].sort(
      (a, b) => Math.abs(new Date(a.starts_at) - t) - Math.abs(new Date(b.starts_at) - t),
    );
  });

  $effect(() => {
    if (step !== 'summary' || assign !== null || loadingCandidates) return;
    const g = game.match;
    // Partido libre: se respeta la elección (se puede asignar a mano desde la lista)
    if (!g) {
      assign = 'none';
      return;
    }
    const same = assignable.find((c) => c.category_id === g.category_id && c.round_no === g.round_no && c.home === g.home && c.away === g.away);
    const near = assignable.find((c) => Math.abs(new Date(c.starts_at) - game.startedAt) <= 6 * 3600e3);
    assign = (same || near)?.id ?? 'none';
  });

  /** Ajusta local/visitante del marcador al del partido de liga (si Ancares cambió de lado). */
  function resultFor(m) {
    const leagueOurs = isOursName(m.home) ? 'home' : 'away';
    if (!game.oursSide || game.oursSide === leagueOurs) return result;
    return {
      home_sets: result.away_sets,
      away_sets: result.home_sets,
      partials: result.partials.map(([h, a, d]) => [a, h, d]),
      finished_early: result.finished_early,
    };
  }

  async function publish() {
    const m = candidates.find((c) => c.id === assign);
    if (!m) return;
    publishing = true;
    try {
      const r = await api('/api/scoring/results', {
        method: 'POST',
        json: { category_id: m.category_id, round_no: m.round_no, home: m.home, away: m.away, ...resultFor(m) },
      });
      published = r.category_slug;
      confirmPublish = false;
      // Que la portada y la categoría muestren ya el resultado
      resource('/api/home').refresh();
      resource(`/api/categories/${r.category_slug}`).refresh();
      toast('Resultado provisional publicado', 'ok');
    } catch (err) {
      toast(err.message, 'error', 6000);
      if (err.status === 401) refreshScorer();
      if (err.status === 409) candidates = await api('/api/scoring/matches').catch(() => candidates);
    } finally {
      publishing = false;
    }
  }

  function share() {
    const m = candidates.find((c) => c.id === assign);
    const title = m ? `${m.category} · ${m.round_name}` : 'Partido amistoso';
    const text = scoreText({
      title,
      home: game.home.name,
      away: game.away.name,
      homeSets: result.home_sets,
      awaySets: result.away_sets,
      partials: partialsText(result),
      provisional: !!m,
    });
    openShare(dataFromGame(game, result, title, !!m), text);
  }

  function newGame() {
    if (!published && !confirmNew) {
      confirmNew = true;
      return;
    }
    game = null;
    assign = null;
    published = null;
    confirmNew = confirmPublish = false;
  }
</script>

{#if step === 'setup'}
  <div class="page">
    <header class="title" in:fly={{ y: -10 }}>
      <h1>Marcador</h1>
      {#if $scorer.can_publish}<span class="chip brand"><Icon name="key" size={14} /> {$scorer.name}</span>{/if}
    </header>
    <p class="muted intro">Lleva el tanteo con un toque por punto. Al terminar puedes compartirlo y, con código de anotador, publicarlo como resultado provisional.</p>

    <h2 class="section-title">¿Qué partido?</h2>
    {#if loadingCandidates}
      <div class="skeleton" style="height:76px"></div>
    {/if}
    <div class="options">
      {#each candidates as m (m.id)}
        <button class="option card" class:on={selected === m.id} onclick={() => choose(m)}>
          <TeamBadge name={rivalOf(m)} logo={rivalLogo(m)} size={40} />
          <span class="info">
            <b class="ellipsis">vs {shortTeam(rivalOf(m))}</b>
            <span class="muted ellipsis">{m.category} · {m.round_name}{m.provisional ? ' · ya tiene resultado provisional' : ''}</span>
          </span>
          <span class="when" class:now={whenLabel(m) === 'Ahora'}>{whenLabel(m)}</span>
        </button>
      {/each}
      <button class="option card" class:on={selected === 'free'} onclick={() => choose('free')}>
        <span class="free-icon"><Icon name="ball" size={22} /></span>
        <span class="info"><b>Partido libre</b><span class="muted">Amistoso o entrenamiento</span></span>
      </button>
    </div>
    {#if !loadingCandidates && !candidates.length}
      <p class="muted small">No hay partidos de Ancares en estos días. Puedes llevar un partido libre.</p>
    {/if}

    {#if selected === 'free'}
      <div class="free card" in:fly={{ y: 8 }}>
        <label class="field"><span>Local</span><input class="input" bind:value={freeHome} maxlength="60" /></label>
        <label class="field"><span>Visitante</span><input class="input" bind:value={freeAway} placeholder="Rival" maxlength="60" /></label>
      </div>
    {/if}

    <h2 class="section-title">Formato</h2>
    <FormatPicker bind:value={format} />

    <button class="btn primary start" onclick={start} disabled={!selected}>
      <Icon name="score" size={20} /> Empezar
    </button>
  </div>
{:else if step === 'play'}
  <div class="play">
    <header class="bar">
      <button class="icon-btn" onclick={() => go('/')} aria-label="Salir (el partido se guarda)"><Icon name="back" size={22} /></button>
      <div class="status">
        <b>Set {setNo}</b>
        <span>{teamName('home')} {won.home} – {won.away} {teamName('away')}</span>
      </div>
      <button class="icon-btn" onclick={() => (menuOpen = true)} aria-label="Opciones"><Icon name="more" size={22} /></button>
    </header>

    <div class="pads">
      {#each order as side (side)}
        <ScorePad
          team={game[side]}
          points={S.currentSet(game)[side]}
          sets={won[side]}
          setsToWin={needed}
          serving={game.serve === side}
          tone={tone(side)}
          hint={hint(side)}
          onTap={() => tap(side)}
        />
      {/each}
    </div>

    <footer class="actions">
      <button class="btn undo" onclick={() => (game = S.undo(game))} disabled={!game.history.length}>
        <Icon name="undo" size={20} /> Deshacer
      </button>
      {#if game.sets.length > 1}
        <span class="prev">{game.sets.slice(0, -1).map((s) => `${s.home}-${s.away}`).join(' · ')}</span>
      {/if}
    </footer>
  </div>

  <!-- Fin de set / fin de partido: no se puede cerrar sin decidir -->
  <BottomSheet open={game.status === 'set_over' || game.status === 'match_over'}>
    {@const last = S.currentSet(game)}
    {@const setWin = last.home > last.away ? 'home' : 'away'}
    {#if game.status === 'set_over'}
      <h3 class="sheet-title">Set {setNo} para {teamName(setWin)}</h3>
      <p class="big-score">{last.home} – {last.away}</p>
      <p class="muted center">Sets: {teamName('home')} {won.home} – {won.away} {teamName('away')}</p>
      <button class="btn primary" onclick={() => (game = S.nextSet(game))}>Empezar set {setNo + 1}</button>
      <button class="btn" onclick={() => (game = S.undo(game))}><Icon name="undo" size={18} /> Deshacer último punto</button>
      <button class="btn ghost" onclick={() => (game = S.finish(game))}><Icon name="flag" size={18} /> Terminar el partido aquí</button>
    {:else}
      <h3 class="sheet-title">
        {winner === 'draw' ? '¡Empate!' : `¡${teamName(winner)} gana el partido!`}
      </h3>
      <p class="big-score">{won.home} – {won.away}</p>
      <p class="muted center">{game.sets.map((s) => `${s.home}-${s.away}`).join(' · ')}</p>
      <button class="btn primary" onclick={() => (game = S.finish(game))}><Icon name="flag" size={18} /> Terminar partido</button>
      <button class="btn" onclick={() => (game = S.undo(game))}><Icon name="undo" size={18} /> Deshacer último punto</button>
    {/if}
  </BottomSheet>

  <BottomSheet open={menuOpen} onClose={closeMenu}>
    <h3 class="sheet-title">Opciones</h3>
    <div class="adjust">
      <span class="muted small">Corregir el set en curso</span>
      {#each ['home', 'away'] as side}
        <div class="adj-row">
          <span class="ellipsis">{teamName(side)}</span>
          <button class="round" onclick={() => (game = S.adjust(game, side, -1))} aria-label="Quitar punto a {teamName(side)}"><Icon name="minus" size={18} /></button>
          <b>{S.currentSet(game)[side]}</b>
          <button class="round" onclick={() => (game = S.adjust(game, side, +1))} aria-label="Sumar punto a {teamName(side)}"><Icon name="plus" size={18} /></button>
        </div>
      {/each}
    </div>
    <button class="btn" onclick={() => { game = { ...game, swapped: !game.swapped }; closeMenu(); }}>
      <Icon name="swap" size={18} /> Cambiar lados
    </button>
    {#if confirmFinish}
      <button class="btn primary" onclick={() => { game = S.finish(game); closeMenu(); }}>Sí, terminar ahora</button>
    {:else}
      <button class="btn" onclick={() => (confirmFinish = true)}><Icon name="flag" size={18} /> Terminar partido ahora</button>
    {/if}
    {#if confirmDiscard}
      <button class="btn danger" onclick={() => { game = null; closeMenu(); }}>Sí, descartar el partido</button>
    {:else}
      <button class="btn ghost danger-text" onclick={() => (confirmDiscard = true)}><Icon name="trash" size={18} /> Descartar partido</button>
    {/if}
    <p class="muted small center">{S.describeFormat(game.format)}</p>
  </BottomSheet>
{:else}
  <div class="page summary">
    <header class="title" in:fly={{ y: -10 }}>
      <h1>{winner === 'draw' ? 'Empate' : winner ? `Gana ${teamName(winner)}` : 'Partido terminado'}</h1>
    </header>

    <div class="result card" in:fly={{ y: 16 }}>
      {#each ['home', 'away'] as side}
        <div class="res-row" class:win={winner === side}>
          <TeamBadge name={game[side].name} logo={game[side].logo} size={36} />
          <span class="ellipsis">{shortTeam(game[side].name)}</span>
          <b>{result[side === 'home' ? 'home_sets' : 'away_sets']}</b>
        </div>
      {/each}
      <div class="partials">
        {#each result.partials as [h, a, done], i}
          <span class:open={!done}>Set {i + 1}: {h}-{a}{done ? '' : ' (sin terminar)'}</span>
        {/each}
      </div>
      {#if game.finishedEarly}<p class="muted small">Terminado antes de tiempo.</p>{/if}
    </div>

    <h2 class="section-title">Partido de liga</h2>
    {#if loadingCandidates}
      <div class="skeleton" style="height:60px"></div>
    {:else}
      <div class="options">
        {#each assignable as m (m.id)}
          <button class="option card" class:on={assign === m.id} onclick={() => { assign = m.id; published = null; }}>
            <TeamBadge name={rivalOf(m)} logo={rivalLogo(m)} size={36} />
            <span class="info">
              <b class="ellipsis">vs {shortTeam(rivalOf(m))}</b>
              <span class="muted ellipsis">{m.category} · {formatWhen(m.starts_at)}{m.provisional ? ` · ya publicado por ${m.provisional.by}` : ''}</span>
            </span>
          </button>
        {/each}
        <button class="option card" class:on={assign === 'none'} onclick={() => (assign = 'none')}>
          <span class="free-icon"><Icon name="ball" size={20} /></span>
          <span class="info"><b>No es de liga</b><span class="muted">Solo compartir</span></span>
        </button>
      </div>
    {/if}

    {#if assign !== 'none' && assign !== null}
      <div class="notice card">
        <Icon name="info" size={20} />
        {#if target?.tournament}
          <p><b>Resultado provisional.</b> Contará en el torneo cuando lo confirme el admin.</p>
        {:else}
          <p><b>Resultado provisional.</b> El que vale es el que publique la federación en unos días; cuando llegue, sustituirá a este.</p>
        {/if}
      </div>
      {#if published}
        <button class="btn primary wide" onclick={() => go(`/c/${published}?t=resultados`)}><Icon name="check" size={18} /> Publicado · ver resultados</button>
      {:else if $scorer.can_publish && target?.provisional && !target.can_publish}
        <!-- Manda el primer resultado publicado: solo su autor o el admin pueden cambiarlo -->
        <p class="taken">
          Ya hay un resultado provisional publicado por <b>{target.provisional.by}</b>
          ({target.provisional.home_sets}-{target.provisional.away_sets}). Si no es correcto, pide al admin que lo borre.
        </p>
      {:else if $scorer.can_publish}
        {@const fixing = !!target?.provisional}
        {#if confirmPublish}
          <button class="btn primary wide" onclick={publish} disabled={publishing}>
            {publishing ? 'Publicando…' : fixing ? 'Sí, sustituir el resultado' : 'Sí, publicar como provisional'}
          </button>
        {:else}
          <button class="btn primary wide" onclick={() => (confirmPublish = true)}>
            <Icon name="upload" size={18} /> {fixing ? 'Corregir el resultado provisional' : 'Publicar resultado provisional'}
          </button>
        {/if}
      {:else}
        <p class="muted small">Para publicarlo en la app necesitas un <b>código de anotador</b>: pídeselo al administrador e introdúcelo en <a href="#/club">Club → Funciones extra</a>.</p>
      {/if}
    {/if}

    <button class="btn wide" onclick={share}><Icon name="share" size={18} /> Compartir</button>
    <div class="row-btns">
      <button class="btn ghost" onclick={() => { game = S.undo(game); assign = null; published = null; }}><Icon name="undo" size={18} /> Volver al marcador</button>
      <button class="btn ghost" class:danger-text={confirmNew} onclick={newGame}>{confirmNew ? 'Sin publicar: ¿seguro?' : 'Nuevo partido'}</button>
    </div>
  </div>
{/if}

<style>
  .title {
    display: flex;
    align-items: center;
    gap: 10px;
    padding-top: calc(var(--safe-top) + 8px);
  }
  .title h1 {
    flex: 1;
    font-size: 28px;
    font-weight: 850;
  }
  .intro {
    font-size: 14px;
    margin: 6px 2px 0;
  }
  .small {
    font-size: 13px;
  }
  .center {
    text-align: center;
  }
  .options {
    display: grid;
    grid-template-columns: minmax(0, 1fr);
    gap: 8px;
  }
  .option {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 12px 14px;
    text-align: left;
    border: 1.5px solid var(--line);
    transition: border-color 0.2s, background 0.2s, transform 0.15s;
  }
  .option:active {
    transform: scale(0.99);
  }
  .option.on {
    border-color: var(--brand);
    background: var(--brand-soft);
  }
  .info {
    flex: 1;
    min-width: 0;
    display: grid;
    font-size: 13.5px;
  }
  .info b {
    font-size: 15.5px;
  }
  .when {
    flex: none;
    font-size: 13px;
    font-weight: 700;
    color: var(--muted);
  }
  .when.now {
    color: #fff;
    background: var(--danger);
    padding: 3px 9px;
    border-radius: 999px;
  }
  .free-icon {
    width: 40px;
    height: 40px;
    border-radius: 50%;
    display: grid;
    place-items: center;
    background: var(--surface-2);
    color: var(--muted);
    flex: none;
  }
  .free {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 10px;
    padding: 12px;
    margin-top: 8px;
  }
  .free .field {
    margin: 0;
  }
  .free .field span {
    font-size: 13px;
    font-weight: 650;
    color: var(--muted);
  }
  .start {
    width: 100%;
    min-height: 56px;
    font-size: 18px;
    margin-top: 22px;
  }

  /* --- jugar --- */
  .play {
    position: fixed;
    inset: 0;
    z-index: 50;
    display: grid;
    grid-template-rows: auto 1fr auto;
    background: #0b1a10;
    color: #fff;
  }
  .bar {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: calc(var(--safe-top) + 6px) 8px 6px;
  }
  .icon-btn {
    width: 44px;
    height: 44px;
    display: grid;
    place-items: center;
    border-radius: 50%;
    color: #fff;
  }
  .icon-btn:active {
    background: rgba(255, 255, 255, 0.12);
  }
  .status {
    flex: 1;
    min-width: 0;
    display: grid;
    text-align: center;
    line-height: 1.2;
  }
  .status b {
    font-size: 13px;
    letter-spacing: 0.12em;
    text-transform: uppercase;
    color: #8ee39c;
  }
  .status span {
    font-size: 15px;
    font-weight: 700;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  .pads {
    display: grid;
    grid-template-rows: 1fr 1fr;
    gap: 3px;
    min-height: 0;
  }
  .actions {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 10px 12px calc(var(--safe-bottom) + 10px);
  }
  .undo {
    min-height: 52px;
    padding: 0 22px;
    background: rgba(255, 255, 255, 0.12);
    color: #fff;
    font-size: 16px;
  }
  .prev {
    flex: 1;
    text-align: right;
    font-size: 13px;
    opacity: 0.75;
    font-variant-numeric: tabular-nums;
  }
  .sheet-title {
    text-align: center;
    font-size: 20px;
    font-weight: 850;
  }
  .big-score {
    margin: 0;
    text-align: center;
    font-size: 54px;
    font-weight: 850;
    font-variant-numeric: tabular-nums;
    color: var(--brand);
  }
  .adjust {
    display: grid;
    gap: 8px;
  }
  .adj-row {
    display: grid;
    grid-template-columns: 1fr auto 48px auto;
    align-items: center;
    gap: 10px;
    font-weight: 650;
  }
  .adj-row b {
    text-align: center;
    font-size: 22px;
    font-variant-numeric: tabular-nums;
  }
  .round {
    width: 44px;
    height: 44px;
    border-radius: 50%;
    display: grid;
    place-items: center;
    background: var(--surface-2);
  }
  .danger-text {
    color: var(--danger);
  }

  /* --- resumen --- */
  .result {
    padding: 14px 16px;
    margin-top: 14px;
    display: grid;
    gap: 10px;
  }
  .res-row {
    display: flex;
    align-items: center;
    gap: 12px;
    font-size: 17px;
  }
  .res-row span {
    flex: 1;
    min-width: 0;
  }
  .res-row b {
    font-size: 30px;
    font-weight: 850;
    font-variant-numeric: tabular-nums;
    color: var(--muted);
  }
  .res-row.win b {
    color: var(--brand);
  }
  .res-row.win span {
    font-weight: 750;
  }
  .partials {
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
  }
  .partials span {
    font-size: 13px;
    padding: 4px 10px;
    border-radius: 999px;
    background: var(--surface-2);
    font-variant-numeric: tabular-nums;
  }
  .partials span.open {
    font-style: italic;
  }
  .notice {
    display: flex;
    gap: 10px;
    padding: 12px 14px;
    margin: 14px 0 10px;
    font-size: 14px;
    border-color: rgba(242, 165, 22, 0.5);
  }
  .notice :global(svg) {
    flex: none;
    color: var(--warn);
    margin-top: 2px;
  }
  .notice p {
    margin: 0;
  }
  .wide {
    width: 100%;
    margin-top: 8px;
  }
  .taken {
    margin: 0 0 4px;
    padding: 10px 12px;
    border-radius: 12px;
    background: var(--surface-2);
    font-size: 14px;
  }
  .row-btns {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 8px;
    margin-top: 8px;
  }
</style>
