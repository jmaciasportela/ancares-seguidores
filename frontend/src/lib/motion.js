import { cubicOut, backOut } from 'svelte/easing';
import { fly as svelteFly, fade as svelteFade, scale as svelteScale } from 'svelte/transition';

export const reduced =
  typeof matchMedia !== 'undefined' && matchMedia('(prefers-reduced-motion: reduce)').matches;

const d = (ms) => (reduced ? 0 : ms);

export const fly = (node, opts = {}) => svelteFly(node, { y: 16, duration: d(380), easing: cubicOut, ...opts, ...(reduced ? { duration: 0 } : {}) });
export const fade = (node, opts = {}) => svelteFade(node, { duration: d(220), ...opts, ...(reduced ? { duration: 0 } : {}) });
export const pop = (node, opts = {}) => svelteScale(node, { start: 0.85, duration: d(380), easing: backOut, ...opts, ...(reduced ? { duration: 0 } : {}) });
export const flipOpts = { duration: d(450), easing: cubicOut };
