// ---- public pages (spec §2, §9b) -------------------------------------------------------------------
const SVG = (d, w = 1.6) => `<svg class="ic" viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="${w}" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${d}</svg>`;
const ICON = {
  mystery: SVG('<circle cx="10.5" cy="10.5" r="6"/><path d="m15 15 5.5 5.5"/>'),
  escape: SVG('<rect x="5" y="10.5" width="14" height="10" rx="2"/><path d="M8 10.5V7.5a4 4 0 0 1 8 0v3"/>'),
  adventure: SVG('<circle cx="12" cy="12" r="8.5"/><path d="m15.5 8.5-2 5-5 2 2-5z"/>'),
  hidden: SVG('<path d="M12 3.5v3M12 17.5v3M3.5 12h3M17.5 12h3M6 6l2 2M16 16l2 2M18 6l-2 2M8 16l-2 2"/><circle cx="12" cy="12" r="2"/>'),
  gift: SVG('<rect x="4" y="9" width="16" height="11" rx="1.5"/><path d="M12 9v11M3.5 9h17M12 9c-2.5 0-4-1-4-2.5S9.5 4 12 9zM12 9c2.5 0 4-1 4-2.5S14.5 4 12 9z"/>'),
  arrow: SVG('<path d="M5 12h14M13 6l6 6-6 6"/>', 1.8),
};
const LINES = {
  mystery: { name: "Mystery", color: "#9C4A3F", icon: ICON.mystery },
  escape: { name: "Escape", color: "#3F8586", icon: ICON.escape },
  adventure: { name: "Adventure", color: "#6E8450", icon: ICON.adventure },
  hidden: { name: "Hidden Object", color: "#8C7A52", icon: ICON.hidden },
};
const diffText = (d) => (d ? `Level ${d} of 5` : "");
// Logo: a vault dial whose centre is a keyhole, with a detective's magnifier handle breaking the ring.
const LOGO = `<svg class="logo" viewBox="0 0 64 64" width="46" height="46" role="img" aria-label="Case Vault"><circle cx="32" cy="32" r="28.5" fill="#1A1710" stroke="#C3A15A" stroke-width="6"/><circle cx="32" cy="32" r="28.5" fill="none" stroke="#12141A" stroke-width="3.4" stroke-dasharray="1.5 5.9"/><circle cx="32" cy="32" r="24.6" fill="none" stroke="#E4C77E" stroke-width="1"/><circle cx="32" cy="32" r="21.4" fill="none" stroke="#C3A15A" stroke-width="1.6"/><g fill="#C3A15A" fill-opacity=".22" stroke="#C3A15A" stroke-width="1.3" stroke-linejoin="round"><path d="M32 32 C27 27 27 19 32 15 C37 19 37 27 32 32Z" transform="rotate(0 32 32)"/><path d="M32 32 C27 27 27 19 32 15 C37 19 37 27 32 32Z" transform="rotate(45 32 32)"/><path d="M32 32 C27 27 27 19 32 15 C37 19 37 27 32 32Z" transform="rotate(90 32 32)"/><path d="M32 32 C27 27 27 19 32 15 C37 19 37 27 32 32Z" transform="rotate(135 32 32)"/><path d="M32 32 C27 27 27 19 32 15 C37 19 37 27 32 32Z" transform="rotate(180 32 32)"/><path d="M32 32 C27 27 27 19 32 15 C37 19 37 27 32 32Z" transform="rotate(225 32 32)"/><path d="M32 32 C27 27 27 19 32 15 C37 19 37 27 32 32Z" transform="rotate(270 32 32)"/><path d="M32 32 C27 27 27 19 32 15 C37 19 37 27 32 32Z" transform="rotate(315 32 32)"/></g><g fill="#E4C77E"><path d="M32 2.2l2.4 3.3-2.4 3.1-2.4-3.1z"/><path d="M32 61.8l-2.4-3.3 2.4-3.1 2.4 3.1z"/><path d="M2.2 32l3.3-2.4 3.1 2.4-3.1 2.4z"/><path d="M61.8 32l-3.3 2.4-3.1-2.4 3.1-2.4z"/></g><circle cx="32" cy="32" r="8.4" fill="#12141A" stroke="#C3A15A" stroke-width="2"/><circle cx="32" cy="30" r="2.9" fill="#E4C77E"/><path d="M30.2 31.6h3.6l1.2 6.6h-6z" fill="#E4C77E"/><path d="m47.5 47.5 11 11" stroke="#12141A" stroke-width="8.4" stroke-linecap="round"/><path d="m47.5 47.5 11 11" stroke="#C3A15A" stroke-width="5.2" stroke-linecap="round"/><path d="m50.4 50.4 5.2 5.2" stroke="#12141A" stroke-width="1.2" stroke-linecap="round" stroke-dasharray="1 2.2"/></svg>`;

// ---- infographic icons (hand-drawn SVG, duotone brass) ---------------------------------------------
const GI = (d) => `<svg viewBox="0 0 48 48" width="46" height="46" fill="none" stroke="#C3A15A" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${d}</svg>`;
const STEP_ICON = [
  GI('<path d="M5 11c7-2.6 14-2 19 3v25c-5-4.6-12-5.4-19-3z" fill="#C3A15A" fill-opacity=".14"/><path d="M43 11c-7-2.6-14-2-19 3v25c5-4.6 12-5.4 19-3z"/><path d="M9.5 18c3-.8 6-.6 9 .6M9.5 24c3-.8 6-.6 9 .6M9.5 30c3-.8 6-.6 9 .6"/><circle cx="33" cy="22" r="5.6" fill="#12141A"/><path d="m37.2 26.2 4.6 4.6"/>'),
  GI('<rect x="9" y="5" width="30" height="38" rx="4.5" fill="#C3A15A" fill-opacity=".14"/><rect x="14" y="10" width="20" height="8.5" rx="1.8" fill="#12141A"/><path d="M17.5 14.2h3.2M23.4 14.2h3.2M29.3 14.2h1.6"/><g fill="#C3A15A" stroke="none"><circle cx="17" cy="26" r="1.8"/><circle cx="24" cy="26" r="1.8"/><circle cx="31" cy="26" r="1.8"/><circle cx="17" cy="32" r="1.8"/><circle cx="24" cy="32" r="1.8"/><circle cx="31" cy="32" r="1.8"/><circle cx="24" cy="38" r="1.8"/></g>'),
  GI('<path d="M10 6h23a2 2 0 0 1 2 2v28a5 5 0 0 1-5 5H15a5 5 0 0 1-5-5z" fill="#C3A15A" fill-opacity=".14"/><path d="M16 14h13M16 20h13M16 26h7"/><circle cx="34" cy="35" r="8" fill="#12141A"/><path d="m34 29.6 1.7 3.4 3.8.5-2.8 2.6.7 3.8-3.4-1.8-3.4 1.8.7-3.8-2.8-2.6 3.8-.5z" fill="#C3A15A" stroke-width="1.2"/>'),
];
const SHIELD = '<path d="M24 3.5l16.5 6v12.4c0 11.4-7.2 18.4-16.5 22.6C14.700 40.300 7.500 33.300 7.500 21.900V9.500z"';
const RANK_ICON = [
  GI(SHIELD + ' fill="#C3A15A" fill-opacity=".1"/><path d="M16.500 22l7.500 7.500 7.500-7.500"/>'),
  GI(SHIELD + ' fill="#C3A15A" fill-opacity=".16"/><circle cx="22.500" cy="20" r="6.200"/><path d="m27 24.500 5.500 5.500"/>'),
  GI(SHIELD + ' fill="#C3A15A" fill-opacity=".22"/><path d="M15.500 19l8.500 8 8.500-8M15.500 26l8.500 8 8.500-8"/>'),
  GI(SHIELD + ' fill="#C3A15A" fill-opacity=".32"/><path d="M14.500 30l1.800-11 5 5.200L24 15l2.700 9.200 5-5.200 1.800 11z" fill="#12141A"/><path d="M3 27c-2.500-6.500-1.500-13 2-17.500M45 27c2.500-6.500 1.500-13-2-17.500"/>'),
];

// ---- seasonal scene: an old castle drawn in SVG, re-coloured by date (northern hemisphere) --------
function seasonFor(d = new Date()) {
  const v = (d.getUTCMonth() + 1) * 100 + d.getUTCDate();
  if (v >= 1201 || v <= 106) return "christmas";
  if (v <= 319) return "winter";
  if (v <= 620) return "spring";
  if (v <= 922) return "summer";
  return "autumn";
}
const SEASONS = {
  winter: { sky: ["#0D1828", "#2B3F58"], moon: "#E8EEF5", far: "#142031", castle: "#18212D", win: "#F0C67A", ground: ["#E3ECF4", "#9DB1C7"], pine: "#0A121C", snow: 1, stars: 1 },
  christmas: { sky: ["#0A1714", "#1D3B33"], moon: "#F1E8D2", far: "#16302A", castle: "#15211C", win: "#F6C46A", ground: ["#E9F0F2", "#A5B8BE"], pine: "#08130F", snow: 1, stars: 1, tree: 1 },
  spring: { sky: ["#1B2B2C", "#6F917F"], moon: "#F2EEDC", far: "#2A423B", castle: "#1D2B27", win: "#F2CF84", ground: ["#4B6B4A", "#27402B"], pine: "#142A1D", petals: 1, stars: 1 },
  summer: { sky: ["#141E2E", "#B07A4E"], moon: "#F3D9A0", far: "#3A3430", castle: "#231F1A", win: "#F6C46A", ground: ["#3B4A2C", "#1F2A19"], pine: "#18240F", flies: 1, stars: 1 },
  autumn: { sky: ["#1A1713", "#82502D"], moon: "#F2C27C", far: "#3A2A1F", castle: "#2B2018", win: "#F4B860", ground: ["#4A3320", "#241810"], pine: "#1A120B", leaves: 1, stars: 1 },
};
function sceneSvg(name) {
  const t = SEASONS[name] || SEASONS.autumn;
  let seed = 11;
  const r = () => (seed = (seed * 16807) % 2147483647) / 2147483647;
  const stars = t.stars ? Array.from({ length: 70 }, () => `<circle cx="${(r() * 1600).toFixed(0)}" cy="${(r() * 420).toFixed(0)}" r="${(0.6 + r() * 1.3).toFixed(1)}" fill="#fff" opacity="${(0.25 + r() * 0.6).toFixed(2)}"/>`).join("") : "";
  const pine = (x, y, k, fill) => `<g transform="translate(${x} ${y}) scale(${k})" fill="${fill}"><path d="M0-120l26 44h-14l24 40h-18l26 36H-44l26-36h-18l24-40h-14z"/><rect x="-5" y="0" width="10" height="16"/></g>`;
  const wins = [[1140, 520], [1180, 520], [1250, 600], [1060, 600], [1355, 470], [1380, 470], [1355, 540], [1478, 620], [1160, 660], [1215, 660], [1300, 660]]
    .map(([x, y]) => `<path d="M${x} ${y + 26}v-18a7 7 0 0 1 14 0v18z" fill="${t.win}" opacity=".9"/>`).join("");
  const crenel = (x0, y, n) => Array.from({ length: n }, (_, i) => `<rect x="${x0 + i * 36}" y="${y}" width="22" height="18"/>`).join("");
  const roofStroke = t.snow ? ' stroke="#DDE8F1" stroke-width="3" stroke-linejoin="round"' : "";
  const castle = `<g fill="${t.castle}">
<rect x="960" y="640" width="620" height="130"/>${crenel(962, 624, 17)}
<rect x="1120" y="470" width="200" height="300"/>${crenel(1122, 452, 6)}
<rect x="1020" y="540" width="90" height="230"/><path d="M1008 540l57-104 57 104z"${roofStroke}/>
<rect x="1330" y="400" width="100" height="370"/><path d="M1318 400l62-118 62 118z"${roofStroke}/>
<rect x="1450" y="560" width="72" height="210"/><path d="M1440 560l46-76 46 76z"${roofStroke}/>
<path d="M1190 770v-70a30 30 0 0 1 60 0v70z" fill="#000" opacity=".55"/></g>${wins}`;
  const tree = t.tree ? (() => {
    const lights = Array.from({ length: 34 }, (_, i) => { const row = Math.floor(i / 6); const w = 20 + (5 - row) * 18; const x = 320 + (r() * 2 - 1) * w; const y = 560 + row * 44 + r() * 20;
      return `<circle cx="${x.toFixed(0)}" cy="${y.toFixed(0)}" r="3.4" fill="${["#F6C46A", "#E36A5A", "#F2E6C8"][i % 3]}" class="tw" style="animation-delay:-${(r() * 3).toFixed(1)}s"/>`; }).join("");
    return `${pine(320, 800, 2.6, t.pine)}<path d="m320 454 5 11 12 1.600-9 8 2.800 12-10.800-6.400-10.800 6.400 2.800-12-9-8 12-1.600z" fill="#F6C46A"/>${lights}`;
  })() : "";
  const fall = (n, mk) => Array.from({ length: n }, () => mk((r() * 1600).toFixed(0), (6 + r() * 9).toFixed(1), (-r() * 14).toFixed(1), (r() * 120 - 40).toFixed(0), (1.2 + r() * 2).toFixed(1))).join("");
  const snow = t.snow ? fall(46, (x, d, dl, dx, rad) => `<circle class="fall" cx="${x}" cy="0" r="${rad}" fill="#fff" opacity=".85" style="animation-duration:${d + 6}s;animation-delay:${dl}s;--dx:${dx}px"/>`) : "";
  const leaves = t.leaves ? fall(26, (x, d, dl, dx) => `<ellipse class="fall" cx="${x}" cy="0" rx="6" ry="3.2" fill="${["#C8742E", "#A8452B", "#D9A441"][Math.abs(+dx) % 3]}" style="animation-duration:${d + 4}s;animation-delay:${dl}s;--dx:${dx}px"/>`) : "";
  const petals = t.petals ? fall(30, (x, d, dl, dx) => `<ellipse class="fall" cx="${x}" cy="0" rx="4.600" ry="2.600" fill="#F0B9B1" opacity=".9" style="animation-duration:${d + 5}s;animation-delay:${dl}s;--dx:${dx}px"/>`) : "";
  const flies = t.flies ? Array.from({ length: 22 }, () => `<circle class="tw" cx="${(r() * 1600).toFixed(0)}" cy="${(560 + r() * 280).toFixed(0)}" r="2.600" fill="#F3E08A" style="animation-delay:-${(r() * 3).toFixed(1)}s"/>`).join("") : "";
  const far = `<path d="M0 640l120-130 90 70 150-170 130 150 110-90 160 170 140-130 150 150 170-190 130 160 120-110 150 170V900H0z" fill="${t.far}"/>`;
  const pines = [[80, 800, 1.5], [180, 830, 1.1], [640, 810, 1.7], [760, 840, 1.2], [880, 800, 1.4], [1560, 840, 1.3]].map(([x, y, k]) => pine(x, y, k, t.pine)).join("");
  return `<svg viewBox="0 0 1600 900" preserveAspectRatio="xMaxYMax slice" aria-hidden="true" focusable="false"><defs>
<linearGradient id="sk" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="${t.sky[0]}"/><stop offset="1" stop-color="${t.sky[1]}"/></linearGradient>
<linearGradient id="gr" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="${t.ground[0]}"/><stop offset="1" stop-color="${t.ground[1]}"/></linearGradient>
<radialGradient id="mg"><stop offset="0" stop-color="${t.moon}" stop-opacity=".35"/><stop offset="1" stop-color="${t.moon}" stop-opacity="0"/></radialGradient></defs>
<rect width="1600" height="900" fill="url(#sk)"/>${stars}<circle cx="560" cy="150" r="150" fill="url(#mg)"/><circle cx="560" cy="150" r="48" fill="${t.moon}"/>
${far}${castle}${pines}<path d="M0 790c200-40 360-34 560-10s420 46 640 6 280-20 400-6V900H0z" fill="url(#gr)"/>${tree}${flies}${snow}${leaves}${petals}</svg>`;
}

const CSS = `
:root{--ink:#12141A;--ink2:#191C24;--ink3:#222632;--line:#2D3240;--paper:#ECE4D0;--ivory:#F3EFE4;--brass:#C3A15A;--stamp:#A8473B;--muted:#A9A597;--ease:cubic-bezier(.16,1,.3,1)}
*{box-sizing:border-box}html{scroll-behavior:smooth}
body{margin:0;background:var(--ink);color:var(--ivory);font:16px/1.6 Outfit,system-ui,sans-serif;-webkit-font-smoothing:antialiased}
body::before{content:"";position:fixed;inset:0;pointer-events:none;opacity:.05;background-image:url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='160' height='160'><filter id='n'><feTurbulence type='fractalNoise' baseFrequency='.9' numOctaves='2'/></filter><rect width='160' height='160' filter='url(%23n)'/></svg>")}
a{color:var(--brass)}h1,h2,h3{font-family:Fraunces,Georgia,serif;font-weight:600;line-height:1.1;letter-spacing:-.015em;margin:.2em 0 .5em}
h1{font-size:clamp(30px,4.4vw,52px)}h2{font-size:clamp(24px,2.8vw,34px)}h3{font-size:19px}
.mono{font-family:"JetBrains Mono",ui-monospace,monospace;letter-spacing:.02em;font-size:.85em}
.wrap{max-width:1180px;margin:0 auto;padding:0 20px;position:relative}
.ic{vertical-align:-3px;flex:none}
header.top{display:flex;justify-content:space-between;align-items:center;padding:18px 20px;max-width:1180px;margin:0 auto;position:relative}
header.top .brand{color:var(--ivory);text-decoration:none;display:flex;align-items:center;gap:12px;font:600 21px Fraunces,serif}
header.top .brand small{display:block;font:500 10px "JetBrains Mono",monospace;letter-spacing:.34em;color:var(--brass);line-height:1;margin-bottom:3px}
header.top .brand b{color:var(--brass);font-weight:600}
header.top nav{display:flex;gap:6px;align-items:center}header.top nav a{padding:8px 14px;border-radius:999px;text-decoration:none;font-size:15px;color:var(--ivory);transition:background .25s var(--ease)}
header.top nav a:hover{background:var(--ink3)}header.top nav a.cta{border:1px solid var(--brass);color:var(--brass)}
.hero{display:grid;grid-template-columns:1.05fr .95fr;gap:56px;align-items:center;padding:40px 0 30px;min-height:min(78dvh,680px)}
.hero .lede{max-width:46ch;color:#CFCABB;font-size:18px}
.eyebrow{display:inline-flex;gap:8px;align-items:center;font:500 12px "JetBrains Mono",monospace;letter-spacing:.2em;text-transform:uppercase;color:var(--brass);margin-bottom:14px}
.eyebrow::before{content:"";width:28px;height:1px;background:var(--brass)}
.dossier{position:relative}.dossier .tag{position:absolute;top:-14px;right:18px;background:var(--stamp);color:#fff;padding:4px 14px;transform:rotate(4deg);font:500 12px "JetBrains Mono",monospace;letter-spacing:.18em}
.card{background:var(--paper);color:#23211C;border-radius:20px;padding:28px;box-shadow:0 30px 60px -28px rgba(0,0,0,.65),inset 0 1px 0 rgba(255,255,255,.5)}
.card h2,.card h3,.card h1{color:#1B1A16}label{display:block;font-weight:500;margin:14px 0 6px;font-size:14.5px}
select,input[type=text],input[type=email],input[type=password],input[type=number],textarea{width:100%;padding:13px 14px;border:1px solid #A89E86;border-radius:10px;font:inherit;background:#FBF8EF;color:#1B1A16}
input.code{font-size:24px;letter-spacing:.16em;text-transform:uppercase;font-family:"JetBrains Mono",monospace;text-align:center}
.btn{display:inline-flex;gap:8px;align-items:center;justify-content:center;background:var(--brass);color:#14161C;border:0;border-radius:10px;padding:13px 22px;font:600 16px Outfit,sans-serif;cursor:pointer;text-decoration:none;transition:transform .25s var(--ease),filter .25s}
.btn:hover{filter:brightness(1.07)}.btn:active{transform:translateY(1px) scale(.985)}
.btn.ghost{background:transparent;color:var(--brass);border:1px solid var(--brass)}.card .btn.ghost{color:#6B5522;border-color:#6B5522}.btn.small{padding:9px 15px;font-size:14px}
.btn:focus-visible,a:focus-visible,input:focus-visible,select:focus-visible,button:focus-visible{outline:3px solid #E8CB84;outline-offset:2px}
.row{display:flex;gap:10px;flex-wrap:wrap;align-items:center}.muted{color:var(--muted)}.card .muted{color:#6B6457}
section{padding:34px 0}.sec-head{display:flex;justify-content:space-between;align-items:end;gap:16px;margin-bottom:18px}.sec-head h2{margin:0}.sec-head a{font-size:15px;text-decoration:none;display:inline-flex;gap:6px;align-items:center}
.tabs{display:flex;gap:8px;flex-wrap:wrap;margin:6px 0 20px}.tabs button{display:inline-flex;gap:7px;align-items:center;border:1px solid var(--line);background:transparent;color:var(--ivory);border-radius:999px;padding:8px 16px;font:500 14px Outfit;cursor:pointer;transition:all .25s var(--ease)}
.tabs button:hover{border-color:var(--c)}.tabs button.on{background:var(--c);border-color:var(--c);color:#fff}
.shelf{margin:8px 0 30px}.shelf h3{color:#D9D3C0}.shelf .books{display:grid;grid-template-columns:repeat(auto-fill,minmax(168px,1fr));gap:18px}
.book{background:var(--ink2);border-radius:14px;overflow:hidden;text-decoration:none;color:var(--ivory);display:block;border:1px solid var(--line);transition:transform .45s var(--ease),border-color .3s}
.book:hover{transform:translateY(-5px);border-color:var(--c)}
.book img,.book .ph{width:100%;aspect-ratio:3/4;object-fit:cover;display:block;background:var(--ink3)}
.book .ph{display:flex;align-items:center;justify-content:center;color:var(--c)}.book .ph .ic{width:42px;height:42px}
.book .meta{padding:11px 13px 14px;font-size:13px}.book .meta b{display:block;font:600 15.5px Fraunces,serif;margin-bottom:5px;line-height:1.25}
.label{display:inline-flex;gap:6px;align-items:center;font-size:12px;padding:3px 10px;border-radius:999px;background:var(--c);color:#fff}
.free{display:grid;grid-template-columns:.8fr 1.2fr;gap:36px;align-items:center;background:var(--ink2);border:1px solid var(--line);border-radius:24px;padding:34px}
.free ul{list-style:none;margin:0;padding:0}.free li{display:flex;justify-content:space-between;gap:14px;align-items:center;padding:13px 0;border-bottom:1px solid var(--line)}.free li:last-child{border:0}
.free .no{color:var(--brass)}
.old-how{counter-reset:s;list-style:none;margin:0;padding:0;max-width:760px}.how li{display:grid;grid-template-columns:64px 1fr;gap:14px;padding:18px 0;border-top:1px solid var(--line)}
.how li::before{counter-increment:s;content:"0" counter(s);font:500 22px "JetBrains Mono",monospace;color:var(--brass)}.how b{font:600 19px Fraunces,serif;display:block}
.ranks{display:grid;grid-template-columns:repeat(4,1fr);border-top:1px solid var(--line)}.ranks div{padding:18px 18px 8px 0}.ranks div+div{padding-left:18px;border-left:1px solid var(--line)}
.ai-note{display:inline-block;margin:6px 0 8px;padding:4px 12px;border:1px solid var(--line);border-radius:999px;font-size:12.5px;color:#D3CBB6}
footer{border-top:1px solid var(--line);margin-top:40px;padding:26px 20px;text-align:center;font-size:14px;color:var(--muted)}
details{border-top:1px solid var(--line);padding:14px 0}details summary{cursor:pointer;font-weight:500}
.result{max-width:680px;margin:34px auto}.stamp{display:inline-block;border:4px solid var(--stamp);color:var(--stamp);padding:6px 18px;font:700 30px "JetBrains Mono",monospace;transform:rotate(-6deg);animation:stamp .5s var(--ease)}
@keyframes stamp{from{transform:scale(2.2) rotate(-6deg);opacity:0}to{transform:scale(1) rotate(-6deg);opacity:1}}
@keyframes rise{from{opacity:0;transform:translateY(14px)}to{opacity:1;transform:none}}.hero>*,.book{animation:rise .7s var(--ease) both}.book:nth-child(2){animation-delay:.06s}.book:nth-child(3){animation-delay:.12s}.book:nth-child(4){animation-delay:.18s}

.scene{position:fixed;inset:0;z-index:-1;overflow:hidden}.scene svg{width:100%;height:100%;display:block}
.scrim{position:fixed;inset:0;z-index:-1;pointer-events:none;background:linear-gradient(180deg,rgba(18,20,26,.1) 0%,rgba(18,20,26,.35) 50%,rgba(18,20,26,.8) 100%)}
.fall{animation:fall linear infinite}@keyframes fall{from{transform:translate(0,-30px)}to{transform:translate(var(--dx,30px),960px)}}
.tw{animation:tw 3s ease-in-out infinite}@keyframes tw{0%,100%{opacity:.35}50%{opacity:1}}
.info{display:grid;grid-template-columns:1.1fr .9fr;gap:30px;padding:26px 0 10px}
.panel{background:rgba(18,20,26,.74);backdrop-filter:blur(8px);border:1px solid var(--line);border-radius:22px;padding:26px 26px 22px;box-shadow:inset 0 1px 0 rgba(255,255,255,.06)}
.panel h2{font-size:24px;margin-bottom:18px}
.path{display:grid;grid-template-columns:repeat(3,1fr);gap:8px;align-items:start}
.step{position:relative;padding-top:2px}.step:nth-child(2){margin-top:30px}.step:nth-child(3){margin-top:60px}
.step::after{content:"";position:absolute;top:36px;left:84px;right:-26px;border-top:2px dashed #7A6535}.step:last-child::after{display:none}
.medal{position:relative;width:76px;height:76px;border-radius:50%;display:grid;place-items:center;background:#1A1710;border:2px solid var(--brass);box-shadow:0 0 0 5px #1A1710,0 0 0 6.5px #6D5A2D}
.medal i{position:absolute;top:-6px;left:-6px;width:26px;height:26px;border-radius:50%;background:var(--brass);color:#14161C;font:600 13px "JetBrains Mono",monospace;display:grid;place-items:center;font-style:normal}
.step b{display:block;margin:16px 0 4px;font:600 17px Fraunces,serif}.step p{margin:0;color:#C9C4B6;font-size:14px;line-height:1.5}
.ladder{display:grid;grid-template-columns:repeat(4,1fr);align-items:end;gap:6px}
.rank{display:flex;flex-direction:column;align-items:center;text-align:center}.rank .em{margin-bottom:8px}
.rank b{font:600 15px Fraunces,serif;line-height:1.15}.rank .mono{color:var(--brass);font-size:12px;margin:2px 0 6px}
.rank .ped{width:100%;border-radius:10px 10px 0 0;background:linear-gradient(180deg,rgba(195,161,90,.5),rgba(195,161,90,.06));border:1px solid #5E4E26;border-bottom:0;padding:8px 6px 0;font-size:11.5px;line-height:1.35;color:#D5D0C2}
.rank:nth-child(1) .ped{height:112px}.rank:nth-child(2) .ped{height:128px}.rank:nth-child(3) .ped{height:148px}.rank:nth-child(4) .ped{height:170px}
.newgrid{display:grid;grid-template-columns:repeat(5,1fr);gap:18px}
@media (max-width:1000px){.info{grid-template-columns:1fr}.newgrid{grid-template-columns:repeat(3,1fr)}}
@media (max-width:640px){.path{grid-template-columns:1fr}.step:nth-child(n){margin-top:0}.step{display:grid;grid-template-columns:90px 1fr;column-gap:14px}.step::after{display:none}.step b{margin-top:6px}.newgrid{grid-template-columns:repeat(2,1fr)}.ladder{gap:4px}.rank .ped{font-size:10.5px}}
@media (prefers-reduced-motion:reduce){*{animation:none!important;transition:none!important}}
.ending{white-space:pre-wrap;font-family:Fraunces,Georgia,serif;font-size:17.5px;line-height:1.75}
.reward{border:1.5px dashed #8B6F2E;border-radius:14px;padding:16px;margin:18px 0;background:#F6EBCB}
.err{background:#F4DDD7;color:#7A1F16;border-radius:10px;padding:10px 12px;margin:10px 0}.ok{background:#DDEBD8;color:#1E4D17;border-radius:10px;padding:10px 12px;margin:10px 0}
table.t{width:100%;border-collapse:collapse;font-size:14.5px}table.t td,table.t th{border-bottom:1px solid #D2C8B0;padding:8px 6px;text-align:left}
.bar{height:10px;background:#D2C8B0;border-radius:6px;overflow:hidden}.bar i{display:block;height:100%;background:#8B6F2E}
.files{display:grid;grid-template-columns:repeat(auto-fill,minmax(120px,1fr));gap:10px}.file{border-radius:10px;padding:10px 10px 28px;background:#E1D7BE;font-size:13px;position:relative;min-height:70px}
.file.solved::after{content:"SOLVED";position:absolute;right:6px;bottom:6px;color:var(--stamp);border:2px solid var(--stamp);font:700 11px "JetBrains Mono";padding:1px 5px;transform:rotate(-8deg)}.file.open{opacity:.55}
@media (max-width:860px){.hero{grid-template-columns:1fr;gap:28px;min-height:0;padding-top:20px}.free{grid-template-columns:1fr}.ranks{grid-template-columns:1fr 1fr}.ranks div:nth-child(3){border-left:0;padding-left:0}header.top nav a{padding:8px 10px}}
`;

function layout(title, body, o = {}) {
  const ts = o.turnstile ? `<script src="https://challenges.cloudflare.com/turnstile/v0/api.js" async defer></script>` : "";
  return `<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>${esc(title)} · Colorilax Case Vault</title><meta name="description" content="Solved your Colorilax case? Enter the final code, read the extended ending and claim your reward.">
<link rel="icon" href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 64 64'%3E%3Ccircle cx='32' cy='32' r='28' fill='%231A1710' stroke='%23C3A15A' stroke-width='7'/%3E%3Ccircle cx='32' cy='30' r='5' fill='%23E4C77E'/%3E%3Cpath d='m47 47 12 12' stroke='%23C3A15A' stroke-width='7' stroke-linecap='round'/%3E%3C/svg%3E"><link rel="preconnect" href="https://fonts.googleapis.com"><link href="https://fonts.googleapis.com/css2?family=Outfit:wght@400;500;600&family=Fraunces:opsz,wght@9..144,500;9..144,600&family=JetBrains+Mono:wght@500&display=swap" rel="stylesheet">
<style>${CSS}</style>${ts}</head><body>
<div class="scene" aria-hidden="true">${sceneSvg(o.season || seasonFor())}</div><div class="scrim"></div>
<header class="top"><a class="brand" href="/">${LOGO}<span><small>COLORILAX</small>Case <b>Vault</b></span></a><nav><a href="/cases">Case files</a><a class="cta" href="${o.user ? "/account" : "/login"}">${o.user ? "Detective File" : "Sign in"}</a></nav></header>
<main>${body}</main>
<footer><a href="/rules">Reward rules</a> · <a href="/privacy">Privacy</a> · <a href="mailto:${esc(o.support || DEFAULT_RULES.support_email)}">Contact</a>
<p style="margin:10px 0 4px">© ${new Date().getUTCFullYear()} Colorilax · HaloSpark e-Commerce Inc. All rights reserved.</p>
<p class="ai-note">All Colorilax books are created with the help of AI tools, then checked and finished by our team.</p><span class="mono" style="font-size:11px;opacity:.6">Case Vault v${VERSION}</span></footer>
</body></html>`;
}
const lineOf = (b) => LINES[b.line] || LINES.mystery;
function coverImg(b) {
  return b.cover_key ? `<img src="/cover/${encodeURIComponent(b.book_id)}" alt="Cover of ${esc(b.title)}" loading="lazy">`
    : `<div class="ph" aria-hidden="true">${lineOf(b).icon}</div>`;
}
function bookCard(b) {
  const l = lineOf(b);
  const pos = b.series_order && b.series_total ? `Book ${b.series_order} of ${b.series_total}` : "";
  return `<a class="book" style="--c:${l.color}" href="/case/${encodeURIComponent(b.book_id)}" data-line="${esc(b.line)}">${coverImg(b)}
<div class="meta"><b>${esc(b.title)}</b>${pos ? `<span class="mono">${pos}</span><br>` : ""}${b.status === "upcoming" || !released(b) ? `<span class="label" style="--c:#555">Opens ${esc(b.release_date || "soon")}</span>` : `<span class="label">${l.name}</span>`}</div></a>`;
}
function bookSelect(books, selected) {
  const groups = {};
  for (const b of books.filter(released)) (groups[b.series_title || "Single cases"] ||= []).push(b);
  return `<select name="book" id="book" required><option value="">Choose your book…</option>${Object.entries(groups).map(([g, bs]) =>
    `<optgroup label="${esc(g)}">${bs.map((b) => `<option value="${esc(b.book_id)}"${b.book_id === selected ? " selected" : ""}>${esc(b.title)}${b.series_order ? ` (Book ${b.series_order})` : ""}</option>`).join("")}</optgroup>`).join("")}</select>`;
}
function answerFields(book) {
  const a = jparse(book && book.answers, {});
  const kinds = Object.keys(a).length ? Object.keys(a) : ["culprit_name"];
  return kinds.map((k) => `<label for="a_${k}">${k === "unlock_code" ? "Final unlock code" : esc((book && book.answer_label) || "Final code")}</label>
<input class="code" type="text" id="a_${k}" name="a_${k}" autocomplete="off" autocapitalize="characters" spellcheck="false" required maxlength="60">`).join("");
}

async function homePage(env, ctx, url) {
  const books = await publicBooks(env);
  const selected = url.searchParams.get("book") || "";
  const sel = books.find((b) => b.book_id === selected);
  const site = await getSetting(env, "turnstile_site", "");
  const R = await rules(env);
  const series = {};
  for (const b of books) (series[b.series_id || `single-${b.line}`] ||= { title: b.series_title || "Single cases", line: b.line, books: [] }).books.push(b);
  const upcoming = books.filter((b) => !released(b)).slice(0, 6);
  const fresh = await all(env, "SELECT b.*, s.title AS series_title, s.total AS series_total FROM books b LEFT JOIN series s ON s.series_id=b.series_id WHERE b.status='active' ORDER BY COALESCE(b.release_date,'') DESC, b.rowid DESC LIMIT 5");
  let freeBooks = [];
  try { freeBooks = await all(env, "SELECT * FROM free_books WHERE active=1 ORDER BY updated DESC LIMIT 6"); } catch (e) { freeBooks = []; }
  const shop = R.shop_url || "https://colorilax.com";
  const tierInfo = { Rookie: `${R.coupon_pct}% off the next book after every case, plus extended endings`, Detective: "New-case e-mails 48 hours early",
    Inspector: "A free short case every quarter, and points that can be spent on books", "Chief Inspector": "Your name on a minor character in a new book (with your OK)" };
  const body = `<div class="wrap"><div class="hero"><div>
<span class="eyebrow">Colorilax mystery and escape books</span>
<h1>Finished the last puzzle? Open the vault.</h1>
<p class="lede">Every case ends with one final code. Enter it to read the extended ending, a few pages that are not in the book, then collect points and ${R.coupon_pct}% off your next case.</p>
<div class="row" style="margin-top:18px"><a class="btn" href="#new">New case files ${ICON.arrow}</a><a class="btn ghost" href="#free">Free books</a></div></div>
<div class="dossier"><span class="tag">CONFIDENTIAL</span><div class="card">
<h2 style="font-size:24px">Enter the final code</h2>
<form method="post" action="/check">${bookSelect(books, selected)}
<div id="answers">${answerFields(sel)}</div>
${site ? `<div class="cf-turnstile" data-sitekey="${esc(site)}" data-appearance="interaction-only"></div>` : ""}
<div class="row" style="margin-top:16px"><button class="btn" type="submit">Open the vault</button><a class="btn ghost" href="/cases">Browse case files</a></div>
<p class="muted" style="font-size:14px;margin-bottom:0">Stuck? The full logical solution is printed at the back of your book. No account is needed to check an answer.</p></form></div></div></div>

<section class="info"><div class="panel"><h2>How it works</h2><div class="path">
<div class="step"><div class="medal"><i>1</i>${STEP_ICON[0]}</div><b>Solve in the book</b><p>Every puzzle gives you a clue. The last one gives you the final code.</p></div>
<div class="step"><div class="medal"><i>2</i>${STEP_ICON[1]}</div><b>Enter the code</b><p>Pick your book, type the code, open the vault.</p></div>
<div class="step"><div class="medal"><i>3</i>${STEP_ICON[2]}</div><b>Read the ending, get rewarded</b><p>Points and ${R.coupon_pct}% off the next book go to detectives with an account.</p></div></div></div>
<div class="panel"><h2>Detective ranks</h2><div class="ladder">${R.tiers.slice(0, 4).map(([n, pt], i) => `<div class="rank"><div class="em">${RANK_ICON[i]}</div><b>${esc(n)}</b><span class="mono">${pt} pts</span><div class="ped">${esc(tierInfo[n] || "")}</div></div>`).join("")}</div></div></section>

${fresh.length ? `<section id="new"><div class="sec-head"><h2>New case files</h2><a href="/cases">All cases ${ICON.arrow}</a></div><div class="newgrid">${fresh.map(bookCard).join("")}</div></section>` : ""}

<section id="free"><div class="free"><div><span class="eyebrow">${ICON.gift} On the house</span><h2>Free coloring books</h2>
<p class="muted">Join Colorilax and pick one printable book on us. One per e-mail address.</p>
<a class="btn" href="${esc(shop)}/pages/free-book">Claim your free book ${ICON.arrow}</a></div>
<ul>${freeBooks.length ? freeBooks.map((f) => `<li><span><b>${esc(f.title)}</b>${f.interest ? `<br><span class="muted" style="font-size:13px">${esc(f.interest)}</span>` : ""}</span><span class="mono no">${esc(f.catalog_no || "FREE")}</span></li>`).join("")
    : `<li><span class="muted">New free books are added regularly. Join to be the first to know.</span></li>`}</ul></div></section>

<section><h2>All the case files</h2><div class="tabs" role="tablist"><button class="on" style="--c:#C3A15A" data-f="">All</button>${Object.entries(LINES).map(([k, l]) => `<button style="--c:${l.color}" data-f="${k}">${l.icon} ${l.name}</button>`).join("")}</div>
${Object.values(series).map((s) => `<div class="shelf" data-line="${esc(s.line)}"><h3>${esc(s.title)}</h3><div class="books">${s.books.map(bookCard).join("")}</div></div>`).join("") || `<p class="muted">The first case files open soon.</p>`}</section>
${upcoming.length ? `<section><h2>Opening soon</h2><div class="shelf"><div class="books">${upcoming.map(bookCard).join("")}</div></div></section>` : ""}

<section><h2>Questions</h2><details><summary>Do I need an account?</summary><p>No, to check an answer and read the extended ending. Yes, to collect rewards: it takes under a minute and needs only your e-mail.</p></details>
<details><summary>Where is my Book Code?</summary><p>On the last page of your personal PDF (colorilax.com) or printed inside your paperback. Bought on Etsy? Use your Etsy order number instead.</p></details>
<details><summary>I typed the right answer but it says no.</summary><p>Check the spelling on the solution page at the back of the book. Upper/lower case, accents and spaces do not matter.</p></details>
<details><summary>Do you reward reviews?</summary><p>No. Reviews are never rewarded.</p></details></section></div>
<script>document.querySelectorAll('.tabs button').forEach(b=>b.onclick=()=>{document.querySelectorAll('.tabs button').forEach(x=>x.classList.toggle('on',x===b));const f=b.dataset.f;document.querySelectorAll('.shelf[data-line]').forEach(s=>s.style.display=!f||s.dataset.line===f?'':'none')});
document.getElementById('book').onchange=e=>{location.search='?book='+encodeURIComponent(e.target.value)}</script>`;
  return html(layout("Enter the final code", body, { user: ctx.user, turnstile: !!site, support: R.support_email }));
}

async function casesPage(env, ctx, url) {
  const books = await publicBooks(env);
  const f = { line: url.searchParams.get("line") || "", series: url.searchParams.get("series") || "", diff: url.searchParams.get("difficulty") || "", aud: url.searchParams.get("audience") || "" };
  const list = books.filter((b) => (!f.line || b.line === f.line) && (!f.series || b.series_id === f.series) && (!f.diff || String(b.difficulty) === f.diff) && (!f.aud || b.audience === f.aud));
  const seriesOpts = [...new Map(books.filter((b) => b.series_id).map((b) => [b.series_id, b.series_title])).entries()];
  const opt = (v, l, cur) => `<option value="${esc(v)}"${v === cur ? " selected" : ""}>${esc(l)}</option>`;
  const body = `<div class="wrap"><h1>Case files</h1><form class="row" method="get">
<select name="line" style="max-width:200px">${opt("", "All lines", f.line)}${Object.entries(LINES).map(([k, l]) => opt(k, l.name, f.line)).join("")}</select>
<select name="series" style="max-width:240px">${opt("", "All series", f.series)}${seriesOpts.map(([k, t]) => opt(k, t, f.series)).join("")}</select>
<select name="difficulty" style="max-width:160px">${opt("", "Any difficulty", f.diff)}${[1, 2, 3, 4, 5].map((d) => opt(String(d), diffText(d), f.diff)).join("")}</select>
<select name="audience" style="max-width:160px">${opt("", "Adults & family", f.aud)}${opt("adult", "Adults", f.aud)}${opt("family", "Family", f.aud)}</select>
<button class="btn small" type="submit">Filter</button></form>
<div class="shelf" style="margin-top:18px"><div class="books">${list.map(bookCard).join("") || `<p class="muted">No case files match.</p>`}</div></div></div>`;
  return html(layout("Case files", body, { user: ctx.user }));
}

function buyButtons(b, user, R) {
  const etsy = b.etsy_url ? `<a class="btn small" href="${esc(b.etsy_url)}" rel="noopener">Buy on Etsy</a>` : "";
  const shop = b.shop_url ? `<a class="btn small ghost" href="${esc(b.shop_url)}" rel="noopener">Buy on colorilax.com</a>` : "";
  return user && user.lastChannel === "etsy" ? etsy + shop : shop + etsy;
}

async function bookPage(env, ctx, id) {
  const b = await getBook(env, id);
  if (!b || b.status === "hidden") return notFound(ctx);
  const R = await rules(env);
  const l = lineOf(b);
  const prev = b.series_id ? await one(env, "SELECT book_id,title FROM books WHERE series_id=? AND series_order=? AND status<>'hidden'", b.series_id, (b.series_order || 0) - 1) : null;
  const next = b.series_id ? await one(env, "SELECT book_id,title FROM books WHERE series_id=? AND series_order=? AND status<>'hidden'", b.series_id, (b.series_order || 0) + 1) : null;
  const n = await one(env, "SELECT COUNT(DISTINCT account_id) AS n FROM solves WHERE book_id=? AND status='verified'", b.book_id);
  const body = `<div class="wrap" style="--c:${l.color}"><div class="hero"><div><span class="label">${l.icon} ${l.name}</span>
<h1>${esc(b.title)}</h1>${b.series_order ? `<p class="mono">Book ${b.series_order}${b.series_id ? "" : ""}</p>` : ""}
<p>${esc(b.blurb || "")}</p><p class="muted">${b.difficulty ? `${diffText(b.difficulty)} · ` : ""}${b.pages ? `${b.pages} pages · ` : ""}${b.solve_minutes ? `about ${Math.round(b.solve_minutes / 60)} h to solve` : ""}</p>
${n && n.n >= R.solved_count_min ? `<p class="mono">${n.n.toLocaleString("en-US")} detectives have solved this case</p>` : ""}
${released(b) ? `<div class="row">${buyButtons(b, ctx.user, R)}<a class="btn small ghost" href="/?book=${encodeURIComponent(b.book_id)}">I solved it</a></div>`
    : `<form class="row" method="post" action="/notify"><input type="hidden" name="book" value="${esc(b.book_id)}"><input type="email" name="email" required placeholder="you@example.com" style="max-width:260px"><button class="btn small">Notify me</button></form><p class="muted">Opens ${esc(b.release_date || "soon")}.</p>`}
<p>${prev ? `← <a href="/case/${encodeURIComponent(prev.book_id)}">${esc(prev.title)}</a>` : ""} ${next ? ` · <a href="/case/${encodeURIComponent(next.book_id)}">${esc(next.title)}</a> →` : ""}</p></div>
<div class="book" style="max-width:300px">${coverImg(b)}</div></div></div>`;
  return html(layout(b.title, body, { user: ctx.user }));
}

function notFound(ctx) {
  return html(layout("Not found", `<div class="wrap result"><h1>Case not found</h1><p><a href="/">Back to the vault</a></p></div>`, { user: ctx && ctx.user }), 404);
}
function infoPage(ctx, title, inner) {
  return html(layout(title, `<div class="wrap result"><div class="card">${inner}</div></div>`, { user: ctx.user }));
}

// POST /check — the answer check. Never reveals the right answer; never says "close".
async function checkAnswer(env, ctx, req) {
  const f = await readBody(req);
  const R = await rules(env);
  const ip = clientIp(req);
  const book = await getBook(env, f.book);
  if (!book || !released(book)) return infoPage(ctx, "Choose a book", `<h2>Please choose your book</h2><p><a href="/">Back</a></p>`);
  if (!(await turnstileOk(env, f["cf-turnstile-response"], ip))) return infoPage(ctx, "Check", `<div class="err">We could not confirm you are human. Please try again.</div><p><a href="/?book=${encodeURIComponent(book.book_id)}">Back</a></p>`);
  const ipCount = await countAttempts(env, "scope='answer' AND ip=?", [ip]);
  if (ipCount >= R.ip_per_hour) return infoPage(ctx, "Slow down", `<h2>Lots of tries from your network</h2><p>Please wait a little and try again.</p>`);
  // Owner rule 2026-11-21: wrong answers may be retried until right. After 5 misses in 10 minutes a
  // short pause (anti-bot) applies; no hourly lock-out.
  const recentWrong = await countAttempts(env, "scope='answer' AND ok=0 AND book_id=? AND (ip=? OR vid=?)", [book.book_id, ip, ctx.vid], 10);
  const last = await one(env, "SELECT ts FROM attempts WHERE scope='answer' AND ok=0 AND book_id=? AND (ip=? OR vid=?) ORDER BY id DESC LIMIT 1", book.book_id, ip, ctx.vid);
  if (recentWrong >= R.wrong_before_pause && last && Date.parse(last.ts) > Date.now() - R.pause_seconds * 1000) {
    return infoPage(ctx, "Take a breath", `<h2>Take a breath, detective</h2><p>Please wait ${R.pause_seconds} seconds before the next try. Re-read your clues: the full logical solution is printed at the back of your book.</p><p><a class="btn" href="/?book=${encodeURIComponent(book.book_id)}">Try again</a></p>`);
  }
  const stored = jparse(book.answers, {});
  let correct = Object.keys(stored).length > 0;
  for (const kind of Object.keys(stored)) {
    if (!ANSWER_KINDS.includes(kind)) { correct = false; break; }
    const h = await answerHash(env.VAULT_ANSWER_KEY || "", book.book_id, kind, f[`a_${kind}`] || "");
    if (!stored[kind].some((x) => timingSafeEq(x, h))) correct = false;
  }
  const everWrong = await one(env, "SELECT COUNT(*) AS n FROM attempts WHERE scope='answer' AND ok=0 AND book_id=? AND (vid=? OR (account_id IS NOT NULL AND account_id=?))", book.book_id, ctx.vid, ctx.user ? ctx.user.id : -1);
  await logAttempt(env, { book_id: book.book_id, ip, vid: ctx.vid, account_id: ctx.user && ctx.user.id, scope: "answer", ok: correct });
  if (!correct) {
    return infoPage(ctx, "Not quite", `<h2>Not quite, detective. Check your clues.</h2><p>You can try again as often as you like. Spelling tip: upper/lower case, accents and spaces do not matter. The full logical solution is printed at the back of your book.</p>
<p><a class="btn" href="/?book=${encodeURIComponent(book.book_id)}">Try again</a></p>`);
  }
  const claim = randomToken(24);
  await run(env, "INSERT INTO solves(book_id,account_id,claim_hash,first_try,status,ip,created) VALUES(?,?,?,?,?,?,?)",
    book.book_id, ctx.user ? ctx.user.id : null, await sha256(claim), everWrong.n === 0 ? 1 : 0, "open", truncIp(ip), nowIso());
  const next = book.next_book_id ? await getBook(env, book.next_book_id) : null;
  const pts = R.points.solve + (everWrong.n === 0 ? R.points.first_try : 0);
  const body = `<div class="wrap result"><div class="card" style="text-align:center"><span class="stamp">CASE SOLVED</span>
<h1 style="margin-top:18px">${esc(book.title)}</h1></div>
<div class="card" style="margin-top:14px"><h2>The extended ending</h2><div class="ending">${esc(book.extended_ending || book.ending_text || "")}</div>
<div class="reward"><b>Your reward:</b> +${pts} Case Points${next ? `, ${R.coupon_pct}% off ${esc(next.title)}` : ""}${!next && book.series_id ? ", and you are one step closer to a free book for finishing the series" : ""}.
<br><span class="muted" style="font-size:14px">Claim it within ${R.claim_hold_hours} hours with your order number or Book Code.</span></div>
<div class="row"><a class="btn" href="/claim?s=${encodeURIComponent(claim)}">Claim your reward</a>${next ? `<a class="btn ghost" href="/case/${encodeURIComponent(next.book_id)}">See ${esc(next.title)}</a>` : ""}</div></div></div>`;
  return html(layout("Case solved", body, { user: ctx.user }), 200, { "set-cookie": setCookie("cv_claim", claim, R.claim_hold_hours * 3600) });
}

async function solveByClaim(env, claim, R) {
  if (!claim) return null;
  const s = await one(env, "SELECT * FROM solves WHERE claim_hash=?", await sha256(claim));
  if (!s || s.status !== "open" || s.created < isoAt(Date.now() - R.claim_hold_hours * 3600000)) return null;
  return s;
}

const MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"];
// Sign in / create account: e-mail + password, or Google (when the owner has set the Google client in /admin).
function signupForm(next, msg, google, mode = "signin") {
  const g = google ? `<p><a class="btn ghost" style="width:100%;text-align:center" href="/auth/google?next=${encodeURIComponent(next)}">Continue with Google</a></p>
<p class="muted" style="font-size:13px;text-align:center">By continuing with Google you agree to the <a href="/rules">reward rules</a> and <a href="/privacy">privacy policy</a>.</p><p style="text-align:center" class="muted">or</p>` : "";
  const signin = `<form method="post" action="/login"><input type="hidden" name="next" value="${esc(next)}"><input type="hidden" name="mode" value="signin">
<label for="em">E-mail</label><input type="email" id="em" name="email" required autocomplete="email">
<label for="pw">Password</label><input type="password" id="pw" name="password" required autocomplete="current-password">
<p class="row"><button class="btn" type="submit">Sign in</button><a href="/forgot?next=${encodeURIComponent(next)}">Forgot password?</a></p></form>
<p>New here? <a href="?mode=signup&next=${encodeURIComponent(next)}" onclick="document.getElementById('su').hidden=false;document.getElementById('si').hidden=true;return false">Create your detective account</a> (under a minute).</p>`;
  const signup = `<form method="post" action="/login"><input type="hidden" name="next" value="${esc(next)}"><input type="hidden" name="mode" value="signup">
<label for="em2">E-mail</label><input type="email" id="em2" name="email" required autocomplete="email">
<label for="pw2">Password (8+ characters)</label><input type="password" id="pw2" name="password" required minlength="8" autocomplete="new-password">
<label for="dn">Display name <span class="muted">(optional)</span></label><input type="text" id="dn" name="display_name" maxlength="60">
<label for="bm">Birth month <span class="muted">(optional, month only: birthday points)</span></label><select id="bm" name="birth_month"><option value="">—</option>${MONTHS.map((m, i) => `<option value="${i + 1}">${m}</option>`).join("")}</select>
<label for="rf">Referral code <span class="muted">(optional)</span></label><input type="text" id="rf" name="referral" maxlength="12">
<label style="font-weight:400"><input type="checkbox" name="newsletter" value="1"> ${esc(CONSENT_TEXT)}</label>
<label style="font-weight:400"><input type="checkbox" name="terms" value="1" required> I agree to the <a href="/rules" target="_blank">reward rules</a> and <a href="/privacy" target="_blank">privacy policy</a>.</label>
<p><button class="btn" type="submit">Create account</button></p></form>
<p>Already a detective? <a href="?next=${encodeURIComponent(next)}" onclick="document.getElementById('su').hidden=true;document.getElementById('si').hidden=false;return false">Sign in</a></p>`;
  return `<h2>${next.startsWith("/claim") ? "Claim your reward" : "Your Detective File"}</h2>${msg || ""}${g}
<div id="si"${mode === "signup" ? " hidden" : ""}>${signin}</div><div id="su"${mode === "signup" ? "" : " hidden"}>${signup}</div>`;
}

async function claimPage(env, ctx, req, url) {
  const R = await rules(env);
  const claim = url.searchParams.get("s") || cookies(req).cv_claim || "";
  const s = await solveByClaim(env, claim, R);
  if (!s) return infoPage(ctx, "Claim", `<h2>Nothing to claim here</h2><p>This claim link has expired or was already used. Enter your final code again on the <a href="/">home page</a>.</p>`);
  const book = await getBook(env, s.book_id);
  if (!ctx.user) return infoPage(ctx, "Claim", signupForm(`/claim?s=${claim}`, `<p>Sign in or create a free account to collect your reward. Your solved case is saved for ${R.claim_hold_hours} hours.</p>`, await googleOn(env)));
  return infoPage(ctx, "Claim", claimForm(book, claim, ""));
}
function claimForm(book, claim, msg) {
  return `<h2>Claim your reward</h2><p><b>${esc(book.title)}</b></p>${msg}
<form method="post" action="/claim"><input type="hidden" name="s" value="${esc(claim)}">
<label>Where did you buy it?</label>
<label style="font-weight:400"><input type="radio" name="channel" value="etsy" required> Etsy (digital)</label>
<label style="font-weight:400"><input type="radio" name="channel" value="shop"> colorilax.com (digital)</label>
<label style="font-weight:400"><input type="radio" name="channel" value="print"> Printed book</label>
<div id="w_order"><label for="order">Etsy order number <span class="muted">(in your Etsy receipt e-mail)</span></label><input type="text" id="order" name="order" inputmode="numeric" maxlength="14"></div>
<div id="w_code"><label for="code">Book Code <span class="muted">(last page of your PDF or inside your printed book)</span></label><input type="text" id="code" name="code" maxlength="24" placeholder="${esc(book.prefix)}-XXXXXXXX" style="text-transform:uppercase"></div>
<p><button class="btn" type="submit">Verify and claim</button></p></form>
<script>(()=>{const o=document.getElementById('w_order'),c=document.getElementById('w_code');o.hidden=c.hidden=true;document.querySelectorAll('input[name=channel]').forEach(r=>r.onchange=()=>{o.hidden=r.value!=='etsy';c.hidden=r.value==='etsy'})})()</script>`;
}

async function claimSubmit(env, ctx, req) {
  const R = await rules(env);
  const f = await readBody(req);
  if (!ctx.user) return redirect(`/claim?s=${encodeURIComponent(f.s || "")}`);
  if (ctx.user.locked) return infoPage(ctx, "Claim", `<div class="err">This account is on hold. Please contact support.</div>`);
  const s = await solveByClaim(env, f.s, R);
  if (!s) return infoPage(ctx, "Claim", `<h2>Nothing to claim here</h2><p>This claim has expired or was already used.</p>`);
  const book = await getBook(env, s.book_id);
  const ip = clientIp(req);
  if ((await countAttempts(env, "scope='proof' AND (ip=? OR account_id=?)", [ip, ctx.user.id])) >= R.wrong_per_hour)
    return infoPage(ctx, "Claim", `<div class="err">Too many tries for now. Please wait an hour.</div>`);
  const res = await verifyProof(env, ctx.user, s, book, f);
  await logAttempt(env, { book_id: book.book_id, ip, account_id: ctx.user.id, scope: "proof", ok: res.status !== "rejected" });
  if (res.status === "rejected") return infoPage(ctx, "Claim", claimForm(book, f.s, `<div class="err">${esc(res.msg)}</div>`));
  return redirect(`/account?m=${encodeURIComponent(res.msg)}`, { "set-cookie": setCookie("cv_claim", "", 0) });
}

// ---- accounts: password sign-in, Google sign-in, reset by e-mail link (15 min, single use) -----------
async function startSession(env, accId, next) {
  const sid = randomToken(32);
  await run(env, "INSERT INTO sessions(sid_hash,account_id,expires) VALUES(?,?,?)", await sha256(sid), accId, plusDays(30));
  await run(env, "UPDATE accounts SET last_active=? WHERE id=?", nowIso(), accId);
  const to = String(next || "/account");
  return redirect(to.startsWith("/") && !to.startsWith("//") ? to : "/account", { "set-cookie": setCookie("cv_sid", sid, 30 * 86400) });
}
const googleOn = async (env) => !!(await getSetting(env, "google_client_id", "")) && !!(await getSetting(env, "google_client_secret", ""));

async function loginPage(env, ctx, url) {
  if (ctx.user) return redirect(url.searchParams.get("next") || "/account");
  const next = url.searchParams.get("next") || "/account";
  return infoPage(ctx, "Sign in", signupForm(next, "", await googleOn(env), url.searchParams.get("mode") || "signin"));
}

async function loginSubmit(env, ctx, req) {
  const f = await readBody(req);
  const ip = clientIp(req);
  const next = String(f.next || "/account").startsWith("/") ? String(f.next || "/account") : "/account";
  const g = await googleOn(env);
  const again = (m, mode) => infoPage(ctx, "Sign in", signupForm(next, `<div class="err">${m}</div>`, g, mode));
  if (!emailOk(f.email)) return again("Please enter a valid e-mail.", f.mode);
  if ((await countAttempts(env, "scope='login' AND ok=0 AND ip=?", [ip])) >= 10) return again("Too many failed sign-ins. Please wait an hour or reset your password.", f.mode);
  const email = String(f.email).trim().toLowerCase();
  const acc = await one(env, "SELECT * FROM accounts WHERE email=?", email);
  if (f.mode === "signup") {
    if (acc) return again("An account with this e-mail already exists. Sign in, or reset your password.", "signin");
    if (String(f.password || "").length < 8) return again("Please choose a password with at least 8 characters.", "signup");
    if (!f.terms) return again("Please accept the reward rules to create your account.", "signup");
    const { acc: created } = await findOrCreateAccount(env, { ...f, email }, ip);
    await run(env, "UPDATE accounts SET password_hash=? WHERE id=?", await pwHash(String(f.password)), created.id);
    await logAttempt(env, { ip, scope: "login", ok: 1 });
    return startSession(env, created.id, next);
  }
  if (!acc || !acc.password_hash || !(await pwCheck(String(f.password || ""), acc.password_hash))) {
    await logAttempt(env, { ip, scope: "login", ok: 0 });
    return again(acc && !acc.password_hash ? "This account signs in with Google, or set a password with “Forgot password?”." : "E-mail or password is not right.", "signin");
  }
  if (acc.locked) return again("This account is on hold. Please contact support.", "signin");
  await logAttempt(env, { ip, scope: "login", ok: 1 });
  return startSession(env, acc.id, next);
}

async function forgotPage(env, ctx, req, url) {
  if (req.method === "GET") return infoPage(ctx, "Reset password", `<h2>Reset your password</h2><form method="post" action="/forgot"><input type="hidden" name="next" value="${esc(url.searchParams.get("next") || "/account")}">
<label for="em">E-mail</label><input type="email" id="em" name="email" required><p><button class="btn">Send reset link</button></p></form>`);
  const f = await readBody(req);
  const ip = clientIp(req);
  const email = String(f.email || "").trim().toLowerCase();
  const acc = emailOk(email) ? await one(env, "SELECT id FROM accounts WHERE email=?", email) : null;
  let devLink = "";
  if (acc && (await countAttempts(env, "scope='reset' AND ip=?", [ip])) < 5) {
    await logAttempt(env, { ip, scope: "reset", ok: 1 });
    const token = randomToken(32);
    await run(env, "INSERT INTO login_tokens(token_hash,email,data,expires) VALUES(?,?,?,?)", await sha256(token), email, JSON.stringify({ next: f.next || "/account", reset: 1 }), isoAt(Date.now() + 15 * 60000));
    const link = `${ctx.origin}/auth?t=${encodeURIComponent(token)}`;
    const body = mailFrame(`<p>Click to choose a new password. The link works once, for 15 minutes.</p><p><a href="${link}" style="background:#C9A24A;color:#14171F;padding:12px 20px;border-radius:8px;text-decoration:none;font-weight:600">Choose a new password</a></p><p style="color:#777;font-size:13px">Did not ask for this? Just ignore this e-mail.</p>`);
    try { await sendMail(env, email, "Reset your Case Vault password", body); } catch { await enqueue(env, "mail", { to: email, subject: "Reset your Case Vault password", html: body }); }
    if (env.ENV_NAME !== "production" && !(await getSetting(env, "mail_token", ""))) devLink = `<p class="muted">Staging (no mail set up): <a href="${link}">open the reset link</a></p>`;
  }
  return infoPage(ctx, "Check your e-mail", `<h2>Check your e-mail</h2><p>If <b>${esc(email)}</b> has an account, a reset link is on its way. It works once, for 15 minutes.</p>${devLink}`);
}

async function authLink(env, ctx, url, req) {
  const t = url.searchParams.get("t") || "";
  const row = await one(env, "SELECT * FROM login_tokens WHERE token_hash=?", await sha256(t));
  if (!row || row.used || row.expires < nowIso()) return infoPage(ctx, "Link expired", `<h2>This link has expired</h2><p>Links work once, for 15 minutes. <a href="/forgot">Get a new one</a>.</p>`);
  const upd = await run(env, "UPDATE login_tokens SET used=1 WHERE token_hash=? AND used=0", row.token_hash);
  if (!(upd.meta && upd.meta.changes)) return infoPage(ctx, "Link used", `<h2>This link was already used</h2>`);
  const data = jparse(row.data, {});
  const acc = await one(env, "SELECT * FROM accounts WHERE email=?", row.email);
  if (!acc) return redirect("/login");
  const res = await startSession(env, acc.id, data.reset ? `/account/password?next=${encodeURIComponent(data.next || "/account")}` : data.next);
  return res;
}

async function passwordPage(env, ctx, req, url) {
  if (!ctx.user) return redirect("/login");
  if (req.method === "POST") {
    const f = await readBody(req);
    if (String(f.password || "").length < 8) return infoPage(ctx, "Password", `<div class="err">At least 8 characters, please.</div><p><a href="/account/password">Back</a></p>`);
    await run(env, "UPDATE accounts SET password_hash=? WHERE id=?", await pwHash(String(f.password)), ctx.user.id);
    const n = String(f.next || "/account");
    return redirect(n.startsWith("/") ? `${n}${n.includes("?") ? "&" : "?"}m=Password%20saved` : "/account");
  }
  return infoPage(ctx, "New password", `<h2>Choose a new password</h2><form method="post" action="/account/password"><input type="hidden" name="next" value="${esc(url.searchParams.get("next") || "/account")}">
<label for="pw">New password (8+ characters)</label><input type="password" id="pw" name="password" minlength="8" required autocomplete="new-password"><p><button class="btn">Save password</button></p></form>`);
}

// Google sign-in (OpenID Connect, authorization-code flow). The token comes straight from Google over TLS
// with our client secret, so the ID token payload can be read without a separate signature check.
async function googleStart(env, ctx, url) {
  if (!(await googleOn(env))) return redirect("/login");
  const state = randomToken(18);
  const next = url.searchParams.get("next") || "/account";
  const q = new URLSearchParams({ client_id: await getSetting(env, "google_client_id", ""), redirect_uri: `${ctx.origin}/auth/google/callback`,
    response_type: "code", scope: "openid email profile", state, prompt: "select_account" });
  return redirect(`https://accounts.google.com/o/oauth2/v2/auth?${q}`, { "set-cookie": setCookie("cv_gstate", `${state}|${next}`, 600) });
}
async function googleCallback(env, ctx, url, req) {
  const [state, next] = String(cookies(req).cv_gstate || "").split("|");
  if (!state || state !== url.searchParams.get("state")) return infoPage(ctx, "Google", `<div class="err">Google sign-in expired. Please try again.</div><p><a href="/login">Back</a></p>`);
  const r = await net(env)("https://oauth2.googleapis.com/token", { method: "POST", headers: { "content-type": "application/x-www-form-urlencoded" },
    body: new URLSearchParams({ code: url.searchParams.get("code") || "", client_id: await getSetting(env, "google_client_id", ""),
      client_secret: await getSetting(env, "google_client_secret", ""), redirect_uri: `${ctx.origin}/auth/google/callback`, grant_type: "authorization_code" }).toString() });
  const j = await r.json().catch(() => ({}));
  const part = String(j.id_token || "").split(".")[1] || "";
  const claims = jparse(part ? atob(part.replace(/-/g, "+").replace(/_/g, "/")) : "", {});
  if (!r.ok || !claims.email || !claims.email_verified) return infoPage(ctx, "Google", `<div class="err">Google did not confirm an e-mail address.</div><p><a href="/login">Back</a></p>`);
  const { acc } = await findOrCreateAccount(env, { email: claims.email, display_name: claims.given_name || claims.name, terms: 1 }, clientIp(req));
  if (acc.locked) return infoPage(ctx, "Google", `<div class="err">This account is on hold. Please contact support.</div>`);
  if (!acc.google_sub) await run(env, "UPDATE accounts SET google_sub=? WHERE id=?", String(claims.sub || ""), acc.id);
  const res = await startSession(env, acc.id, next || "/account");
  res.headers.append("set-cookie", setCookie("cv_gstate", "", 0));
  return res;
}

function mailFrame(inner) {
  return `<div style="font-family:Arial,sans-serif;max-width:520px;margin:auto;padding:20px;background:#EFE6D2;color:#22211d;border-radius:10px"><h2 style="font-family:Georgia,serif;margin-top:0">Case Vault</h2>${inner}<p style="color:#777;font-size:12px">Colorilax · HaloSpark Inc.</p></div>`;
}

// ---- Detective File -----------------------------------------------------------------------------
async function accountPage(env, ctx, url) {
  if (!ctx.user) return infoPage(ctx, "Sign in", signupForm("/account", "", await googleOn(env)));
  const R = await rules(env);
  const a = ctx.user;
  const msg = url.searchParams.get("m");
  const rank = tierRank(a.tier, R);
  const nextTier = R.tiers[rank + 1];
  const pct = nextTier ? Math.min(100, Math.round((a.points_total / nextTier[1]) * 100)) : 100;
  const solves = await all(env, "SELECT s.*, b.title FROM solves s JOIN books b ON b.book_id=s.book_id WHERE s.account_id=? ORDER BY s.id DESC", a.id);
  const solvedIds = new Set(solves.filter((s) => s.status === "verified").map((s) => s.book_id));
  const seriesIds = [...new Set((await all(env, "SELECT b.series_id FROM solves s JOIN books b ON b.book_id=s.book_id WHERE s.account_id=? AND b.series_id IS NOT NULL", a.id)).map((r) => r.series_id))];
  let seriesHtml = "";
  for (const sid of seriesIds) {
    const s = await one(env, "SELECT * FROM series WHERE series_id=?", sid);
    const bs = await all(env, "SELECT * FROM books WHERE series_id=? AND status<>'hidden' ORDER BY series_order", sid);
    const done = bs.filter((b) => solvedIds.has(b.book_id)).length;
    seriesHtml += `<h3>${esc(s ? s.title : sid)} <span class="mono muted">${done}/${s ? s.total : bs.length}</span></h3><div class="files">${bs.map((b) => solvedIds.has(b.book_id)
      ? `<div class="file solved"><b>${b.series_order}.</b> ${esc(b.title)}</div>`
      : `<div class="file open"><b>${b.series_order}.</b> ${esc(b.title)}<br><a href="/case/${encodeURIComponent(b.book_id)}">Get it</a></div>`).join("")}</div>
${s && s.total - done > 0 && s.total - done <= 3 && s.next_series_id ? `<p class="mono">${s.total - done} ${s.total - done === 1 ? "case" : "cases"} left to unlock a free book</p>` : ""}`;
  }
  const rewards = await all(env, "SELECT r.*, b.title, b.etsy_url, b.shop_url FROM rewards r LEFT JOIN books b ON b.book_id=r.book_id WHERE r.account_id=? ORDER BY r.id DESC", a.id);
  const daysLeft = (e) => Math.max(0, Math.ceil((Date.parse(e) - Date.now()) / DAY));
  const coupons = rewards.filter((r) => r.kind === "coupon" && ["issued", "waiting_release", "retry"].includes(r.status)).map((r) => r.status === "issued"
    ? `<tr><td>${r.pct}% off <b>${esc(r.title)}</b><br><span class="muted">${r.channel === "etsy" ? "Use on Etsy" : "Use on colorilax.com"} · ${daysLeft(r.expires)} days left</span></td><td><code class="mono">${esc(r.code)}</code> <button class="btn small ghost" onclick="navigator.clipboard.writeText('${esc(r.code)}')">Copy</button></td><td><a href="${esc(r.channel === "etsy" ? r.etsy_url || R.etsy_shop_url : r.shop_url || R.shop_url)}">Shop</a></td></tr>`
    : `<tr><td>${r.pct}% off <b>${esc(r.title)}</b></td><td colspan="2" class="muted">${r.status === "waiting_release" ? "Your code arrives on release day" : "Being prepared…"}</td></tr>`).join("");
  const gifts = rewards.filter((r) => r.kind !== "coupon").map((r) => `<tr><td><b>${esc(r.title)}</b><br><span class="muted">${esc(r.note || r.kind)}</span></td><td>${r.status === "issued" ? `<a class="btn small" href="/dl/${encodeURIComponent(r.code)}">Download</a>` : `<span class="muted">${r.status === "waiting_release" ? "Reserved: sent on release day" : "Being prepared…"}</span>`}</td></tr>`).join("");
  const pending = solves.filter((s) => s.status === "pending").map((s) => `<li>${esc(s.title)}: waiting for your Etsy order to appear</li>`).join("");
  const ledger = await all(env, "SELECT * FROM points_ledger WHERE account_id=? ORDER BY id DESC LIMIT 30", a.id);
  const canRedeem = rank >= tierRank(R.redeem_min_tier, R);
  const redeemables = canRedeem ? (await all(env, "SELECT * FROM books WHERE redeemable=1 AND status='active' ORDER BY title")).filter(released) : [];
  const body = `<div class="wrap" style="max-width:860px">${msg ? `<div class="ok">${esc(msg)}</div>` : ""}
<div class="card"><div class="row" style="justify-content:space-between"><div><span class="mono muted">DETECTIVE FILE</span><h1 style="margin:0">${esc(a.display_name || a.email.split("@")[0])}</h1>
<span class="stamp" style="font-size:18px;animation:none;border-width:3px">${esc(a.tier.toUpperCase())}</span></div>
<div style="text-align:right"><span class="mono">${a.points_avail} pts available</span><br><span class="muted">${a.points_total} pts earned in total</span></div></div>
<div class="bar" style="margin-top:14px" role="progressbar" aria-valuenow="${pct}" aria-valuemin="0" aria-valuemax="100"><i style="width:${pct}%"></i></div>
<p class="muted">${nextTier ? `${nextTier[1] - a.points_total} points to ${esc(nextTier[0])}` : "Highest rank reached"}</p></div>
${pending ? `<div class="card" style="margin-top:14px"><h3>Waiting for verification</h3><ul>${pending}</ul></div>` : ""}
<div class="card" style="margin-top:14px"><h2>Coupon wallet</h2>${coupons ? `<table class="t">${coupons}</table>` : `<p class="muted">No coupons yet. Solve a case and claim it to get ${R.coupon_pct}% off the next book.</p>`}</div>
<div class="card" style="margin-top:14px"><h2>Cases by series</h2>${seriesHtml || `<p class="muted">No cases yet.</p>`}</div>
<div class="card" style="margin-top:14px"><h2>Gifts &amp; free books</h2>${gifts ? `<table class="t">${gifts}</table>` : `<p class="muted">Finish a whole series to get Book 1 of the next series free.</p>`}
${canRedeem ? `<form method="post" action="/account/redeem" class="row" style="margin-top:10px"><select name="book" style="max-width:320px">${redeemables.map((b) => `<option value="${esc(b.book_id)}">${esc(b.title)}</option>`).join("")}</select><button class="btn small"${a.points_avail < R.redeem_cost ? " disabled" : ""}>Redeem ${R.redeem_cost} pts</button></form>` : `<p class="muted">Redeeming points for books opens at ${esc(R.redeem_min_tier)}.</p>`}</div>
<div class="card" style="margin-top:14px"><h2>Invite a friend</h2><p>Your code: <code class="mono" style="font-size:20px">${esc(a.ref_code)}</code>. You get ${R.points.referral} points when a friend buys and solves their first case.</p></div>
<div class="card" style="margin-top:14px"><h2>Points history</h2><table class="t">${ledger.map((l) => `<tr><td>${l.ts.slice(0, 10)}</td><td>${esc(l.reason.replace("_", " "))}</td><td>${l.d_avail > 0 ? "+" : ""}${l.d_avail}</td></tr>`).join("")}</table></div>
<div class="card" style="margin-top:14px"><h2>Settings</h2><form method="post" action="/account/settings">
<label style="font-weight:400"><input type="checkbox" name="newsletter" value="1"${a.newsletter ? " checked" : ""}> ${esc(CONSENT_TEXT)}</label>
${a.tier === "Chief Inspector" ? `<label style="font-weight:400"><input type="checkbox" name="name_consent" value="1"${a.name_consent ? " checked" : ""}> You may use my display name for a minor character in a future book.</label>` : ""}
<p><button class="btn small">Save</button> <a class="btn small ghost" href="/account/password">Change password</a> <a class="btn small ghost" href="/logout">Sign out</a></p></form>
<details><summary>Delete my account</summary><form method="post" action="/account/delete"><p>This removes your e-mail, points and coupons from Case Vault. It cannot be undone.</p><label style="font-weight:400"><input type="checkbox" name="confirm" value="1" required> Yes, delete everything</label><p><button class="btn small" style="background:var(--stamp);color:#fff">Delete account</button></p></form></details></div></div>`;
  return html(layout("Detective File", body, { user: ctx.user }));
}

async function accountAction(env, ctx, req, action) {
  if (!ctx.user) return redirect("/account");
  const f = await readBody(req);
  const a = ctx.user;
  if (action === "settings") {
    const nl = f.newsletter ? 1 : 0;
    if (nl !== a.newsletter) {
      await recordConsent(env, a, !!nl, clientIp(req), "account settings");
      await enqueue(env, "klaviyo_sub", { email: a.email, subscribe: !!nl });
    }
    await run(env, "UPDATE accounts SET newsletter=?, name_consent=? WHERE id=?", nl, f.name_consent ? 1 : 0, a.id);
    return redirect("/account?m=Saved");
  }
  if (action === "redeem") {
    const r = await redeemPoints(env, a, f.book);
    return redirect(`/account?m=${encodeURIComponent(r.msg)}`);
  }
  if (action === "delete" && f.confirm) {
    await deleteAccount(env, a.id, "customer");
    return redirect("/", { "set-cookie": setCookie("cv_sid", "", 0) });
  }
  return redirect("/account");
}

async function deleteAccount(env, id, actor) {
  const a = await one(env, "SELECT email FROM accounts WHERE id=?", id);
  if (!a) return;
  if (a.email) await enqueue(env, "klaviyo_sub", { email: a.email, subscribe: false });
  for (const sql of ["DELETE FROM sessions WHERE account_id=?", "DELETE FROM points_ledger WHERE account_id=?", "DELETE FROM rewards WHERE account_id=?",
    "DELETE FROM referrals WHERE referrer_id=? OR referee_id=?", "UPDATE solves SET account_id=NULL, ip=NULL WHERE account_id=?",
    "UPDATE consents SET email=NULL WHERE account_id=?", "DELETE FROM accounts WHERE id=?"]) {
    const n = (sql.match(/\?/g) || []).length;
    await run(env, sql, ...Array(n).fill(id));
  }
  await audit(env, actor, "delete_account", { id });
}

async function download(env, ctx, token) {
  const rw = await one(env, "SELECT r.*, b.download_key, b.download_url, b.title FROM rewards r JOIN books b ON b.book_id=r.book_id WHERE r.code=? AND r.kind IN ('gift','redeem') AND r.status='issued'", token);
  if (!rw) return notFound(ctx);
  if (rw.download_key && env.BOOKS) {
    const obj = await env.BOOKS.get(rw.download_key);
    if (obj) return new Response(obj.body, { headers: { "content-type": obj.httpMetadata?.contentType || "application/octet-stream",
      "content-disposition": `attachment; filename="${rw.download_key.split("/").pop()}"`, "cache-control": "private, no-store" } });
  }
  if (rw.download_url) return redirect(rw.download_url);
  return infoPage(ctx, "Download", `<h2>Your download is being prepared</h2><p>We will e-mail you the link. Questions? Write to support.</p>`);
}

async function notifyMe(env, ctx, req) {
  const f = await readBody(req);
  const b = await getBook(env, f.book);
  if (b && emailOk(f.email)) await run(env, "INSERT OR IGNORE INTO notify(email,book_id,ts) VALUES(?,?,?)", String(f.email).trim().toLowerCase(), b.book_id, nowIso());
  return infoPage(ctx, "Noted", `<h2>Noted</h2><p>We will e-mail you once when this case opens. Nothing else.</p>`);
}

const RULES_DEFAULT = (R) => `<h1>Case Vault reward rules</h1>
<p>Rewards need a verified purchase: an Etsy order number (Etsy) or a Book Code (colorilax.com and printed books). Each order and book, and each Book Code, can be rewarded once. Solving the same book again does not count twice.</p>
<h3>After every case</h3><p>A single-use ${R.coupon_pct}% code for the next book in the same series, valid ${R.coupon_days} days from the day you receive it, not combinable with other codes. Etsy buyers receive an Etsy coupon. If the next book is not out yet, your code arrives on its release day. The last book of a series has no next book; finishing the whole series instead gives you Book 1 of the next series as a free digital book, plus ${R.points.series} points.</p>
<h3>Case Points</h3><table class="t"><tr><td>Create an account</td><td>${R.points.signup}</td></tr><tr><td>Solve a case (verified)</td><td>${R.points.solve}</td></tr><tr><td>Right on your first try</td><td>+${R.points.first_try}</td></tr><tr><td>Finish a series</td><td>+${R.points.series}</td></tr><tr><td>A friend you invited buys and solves their first case</td><td>${R.points.referral}</td></tr><tr><td>Birthday month</td><td>${R.points.birthday}</td></tr></table>
<p>Ranks use your total points and never go down: ${R.tiers.map((t) => `${t[0]} ${t[1]}`).join(" · ")}. From ${R.redeem_min_tier}, ${R.redeem_cost} available points can be exchanged for one digital book from the list we offer. Points have no cash value, cannot be transferred, and available points expire after 24 months without activity. We never give points or rewards for reviews.</p>
<p>We may cancel points or rewards obtained by abuse (shared answers without a purchase, several accounts, re-used codes). Questions: <a href="mailto:${esc(R.support_email)}">${esc(R.support_email)}</a>.</p>`;
const PRIVACY_DEFAULT = (R) => `<h1>Privacy</h1><p>Case Vault is run by HaloSpark Inc. (Colorilax). We keep only what the reward program needs: your e-mail, optional display name and birth month (month only), where you bought, your Etsy order number or Book Code, the books you solved, your points and codes, and your newsletter choice with the time it was given. From Etsy order files we keep only the order number, product and date: never names, addresses or payment details.</p>
<p>We send transactional e-mails (sign-in links, reward codes) to everyone who claims a reward. Marketing e-mails go only to people who ticked the newsletter box, and you can unsubscribe at any time. Our e-mail provider is Klaviyo. Answers you type are checked on our server and are not stored in readable form.</p>
<p>You can see your data in your Detective File and delete your account there, or ask us to send or erase your data at <a href="mailto:${esc(R.support_email)}">${esc(R.support_email)}</a>.</p>`;
