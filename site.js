// Shared data for the homepage (/) and the gig browser (/tool/).

// The 7 database categories, with the friendlier names shown to visitors.
// slug matches the /category/<slug>/ pages and the tool's ?cat= links.
const CATS = [
  { cat: 'Local & professional services', slug: 'local-professional-services', name: 'Services from home', sub: 'Bookkeeping, dispatching, assistants' },
  { cat: 'Digital & subscription products', slug: 'digital-subscription-products', name: 'Digital products', sub: 'Printables, templates, e-books' },
  { cat: 'Marketing & content', slug: 'marketing-content', name: 'Marketing for businesses', sub: 'Social media, ads, websites' },
  { cat: 'Physical & print products', slug: 'physical-print-products', name: 'Things you make', sub: 'Print-on-demand, crafts, books' },
  { cat: 'Content & personal brand', slug: 'content-personal-brand', name: 'YouTube & blogging', sub: 'Faceless channels, niche blogs' },
  { cat: 'AI & automation', slug: 'ai-automation', name: 'AI & automation', sub: 'AI tools, chatbots, agencies' },
  { cat: 'E-commerce', slug: 'e-commerce', name: 'Online stores', sub: 'Etsy, Amazon, Shopify' }
];
const CAT_BY_SLUG = Object.fromEntries(CATS.map(c => [c.slug, c]));
const CAT_BY_NAME = Object.fromEntries(CATS.map(c => [c.cat, c]));

// Groups for ?kind= links (products / services / audience). AI & automation sits in
// all three until those gigs are sorted into product, service or audience.
const KINDS = {
  products: { name: 'Product', cats: ['digital-subscription-products', 'physical-print-products', 'e-commerce', 'ai-automation'] },
  services: { name: 'Service', cats: ['local-professional-services', 'marketing-content', 'ai-automation'] },
  audience: { name: 'Audience-building', cats: ['content-personal-brand', 'ai-automation'] }
};

const SAVED_KEY = 'shi_saved_gigs'; // same key as the live tool, so saved gigs carry over

function esc(s) { return String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c])); }
function slugify(name) { return (name || '').toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-+|-+$/g, '').slice(0, 60); }
function initials(name) { return (name || '?').split(/[^A-Za-z0-9]+/).filter(Boolean).map(w => w[0]).join('').slice(0, 2).toUpperCase(); }
function shortCost(c) { return String(c || '').split(' (')[0]; }
function shortCreator(f) { return String(f || '').split(' on ')[0]; }
function toTitleCase(str) {
  const minor = new Set(['a','an','the','and','but','or','nor','for','so','yet','at','by','in','of','on','to','up','as','is','it','vs']);
  const words = String(str || '').split(' ');
  return words.map((w, i) => {
    if (!w) return w;
    if (/^[A-Z0-9$]/.test(w) && w === w.toUpperCase() && /[A-Z]/.test(w)) return w;
    if (/[A-Z]/.test(w.slice(1))) return w.charAt(0).toUpperCase() + w.slice(1); // keep AI-built, YouTube, TikTok
    const lower = w.toLowerCase();
    if (i !== 0 && i !== words.length - 1 && minor.has(lower)) return lower;
    return lower.charAt(0).toUpperCase() + lower.slice(1);
  }).join(' ');
}
// Short headline (2-6 words) shown on cards; older entries fall back to the full name.
function shortTitle(i) { return i.title || toTitleCase(i.name); }
function hasTag(i, t) { return (i.filters || []).includes(t); }
function avatarHtml(name, cls) {
  // Creators without a saved photo get a neutral head-and-shoulders silhouette (Oct 30, 2026; was initials).
  return `<img class="${cls}" src="/assets/avatars/avatar-${esc(slugify(name))}.jpg" alt="" loading="lazy" onerror="this.onerror=null;this.src='/assets/avatars/silhouette.svg'">`;
}
function loadIdeas() { return fetch('/ideas.json').then(r => r.json()); }
