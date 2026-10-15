import type { Directive } from 'vue';

const animations = new WeakMap<HTMLElement, Animation>();

/** Animate existing content without remounting forms or delaying navigation. */
export const vContentMotion: Directive<HTMLElement, unknown> = {
  updated(element, binding) {
    if (binding.value === binding.oldValue) return;
    if (binding.arg === 'page') element.scrollTop = 0;
    animations.get(element)?.cancel();
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;
    animations.set(element, element.animate(
      [{ opacity: 0.35, transform: 'translateY(6px)' }, { opacity: 1, transform: 'translateY(0)' }],
      { duration: 200, easing: 'cubic-bezier(0.22, 1, 0.36, 1)' },
    ));
  },
  beforeUnmount(element) {
    animations.get(element)?.cancel();
    animations.delete(element);
  },
};
