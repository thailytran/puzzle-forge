// Puzzle Forge — book interior template.
// Python writes `layout.json` next to this file (see forge/layout/document.py).
#let L = json(sys.inputs.at("layout", default: "layout.json"))
#let inch = 1in
#let base = L.base_size_pt * 1pt
#let E = L.at("edition", default: none)            // forge/editions/settings.py
#let T = L.at("theme", default: none)              // page frame + heading plaque (CBN Mystery, forge/mystery/art.py)
#let bleed = if E == none { 0pt } else { E.bleed_in * inch }
#let wm-on = E != none and E.watermark
// outer side of the current page: recto (odd) = right; simplex spiral books bind on the left
#let outer-right() = E != none and E.simplex or calc.odd(here().page())

#set document(title: L.title, author: if L.author == "" { () } else { L.author }, date: none)
#set text(font: L.fonts.body, size: base, lang: "en")
#set par(leading: 0.6em)

#let running-header = context {
  set text(font: L.fonts.sans, size: 8.5pt, fill: luma(90))
  align(center, L.title)
}
#let page-footer = context {
  set text(font: L.fonts.sans, size: 0.8 * base)
  if E != none {  // layer 2: small logo in the outer footer corner
    place((if outer-right() { right } else { left }) + top, image("brand/logo.svg", width: 0.14in))
  }
  align(center, counter(page).display())
  if E != none and E.microtext != "" {
    v(-0.35em)
    align(center, text(size: E.microtext_pt * 1pt, fill: rgb(E.accent), E.microtext))
    v(9pt)  // reserved band for `forge edition stamp`
  }
}

#let crop-marks() = {
  let len = bleed - 0.025in
  let s = (paint: black, thickness: 0.25pt)
  for (x, y) in ((bleed, bleed), (bleed + L.width_in * inch, bleed),
                 (bleed, bleed + L.height_in * inch),
                 (bleed + L.width_in * inch, bleed + L.height_in * inch)) {
    let dx = if x == bleed { -1 } else { 1 }
    let dy = if y == bleed { -1 } else { 1 }
    place(top + left, line(start: (x + dx * 0.025in, y), end: (x + dx * bleed, y), stroke: s))
    place(top + left, line(start: (x, y + dy * 0.025in), end: (x, y + dy * bleed), stroke: s))
  }
}
#let page-background = context {
  if T != none and T.at("background", default: none) != none {
    place(top + left, dx: 0pt, dy: 0pt, image(T.background, width: 100%, height: 100%, fit: "stretch"))
  }
  if wm-on {
    let size = E.wm_size_in * inch
    let dx = bleed + L.margins.outside * inch
    let dy = -(bleed + L.margins.bottom * inch + 0.1in)
    if outer-right() {
      place(bottom + right, dx: -dx, dy: dy, image("brand/emblem.svg", width: size))
    } else {
      place(bottom + left, dx: dx, dy: dy, image("brand/emblem.svg", width: size))
    }
  }
  if E != none and E.crop_marks { crop-marks() }
}

#set page(
  width: L.width_in * inch + 2 * bleed,
  height: L.height_in * inch + 2 * bleed,
  margin: if E != none and E.simplex {
    (left: L.margins.inside * inch + bleed, right: L.margins.outside * inch + bleed,
     top: L.margins.top * inch + bleed, bottom: L.margins.bottom * inch + bleed)
  } else {
    (inside: L.margins.inside * inch + bleed, outside: L.margins.outside * inch + bleed,
     top: L.margins.top * inch + bleed, bottom: L.margins.bottom * inch + bleed)
  },
  footer-descent: if E != none { 15% } else { 30% },
  background: page-background,
)

// ---------------------------------------------------------------- blocks
#let letter-grid(b) = {
  let rows = b.rows
  let nr = rows.len()
  let nc = rows.at(0).len()
  let cell = b.at("cell_in", default: 0.35) * inch
  let fpt = b.at("font_pt", default: 14) * 1pt
  let borders = b.at("borders", default: false)
  let hl = b.at("highlights", default: ())
  align(center, box(width: nc * cell, height: nr * cell, {
    // solution highlights: thick round-capped grey strokes under the letters
    for h in hl {
      let (r1, c1, r2, c2) = h
      place(top + left, line(
        start: ((c1 + 0.5) * cell, (r1 + 0.5) * cell),
        end: ((c2 + 0.5) * cell, (r2 + 0.5) * cell),
        stroke: (paint: luma(200), thickness: 0.7 * cell, cap: "round"),
      ))
    }
    for (r, row) in rows.enumerate() {
      for (c, ch) in row.enumerate() {
        if ch != none {
          if borders {
            place(top + left, dx: c * cell, dy: r * cell,
              rect(width: cell, height: cell, stroke: 0.5pt + luma(120)))
          }
          place(top + left, dx: c * cell, dy: r * cell, box(width: cell, height: cell,
            align(center + horizon, text(font: L.fonts.sans, size: fpt, ch))))
        }
      }
    }
  }))
}

#let sudoku-grid(b) = {
  let n = b.size
  let cell = b.cell_in * inch
  let fpt = b.font_pt * 1pt
  let shaded = b.at("shaded", default: ())
  align(center, box(width: n * cell, height: n * cell, {
    for s in shaded {
      let (r, c) = s
      place(top + left, dx: c * cell, dy: r * cell, rect(width: cell, height: cell, fill: luma(215), stroke: none))
    }
    for i in range(n + 1) {
      let tv = if calc.rem(i, b.box_cols) == 0 { 2pt } else { 0.5pt }
      let th = if calc.rem(i, b.box_rows) == 0 { 2pt } else { 0.5pt }
      place(top + left, line(start: (i * cell, 0pt), end: (i * cell, n * cell), stroke: tv))
      place(top + left, line(start: (0pt, i * cell), end: (n * cell, i * cell), stroke: th))
    }
    for (r, row) in b.cells.enumerate() {
      for (c, v) in row.enumerate() {
        if v != none {
          let given = b.given_mask.at(r).at(c)
          place(top + left, dx: c * cell, dy: r * cell, box(width: cell, height: cell,
            align(center + horizon, text(font: L.fonts.sans, size: fpt,
              weight: if given { "bold" } else { "regular" },
              fill: if given { black } else { luma(90) }, str(v)))))
        }
      }
    }
  }))
}

#let maze(b) = {
  let w = b.width_in * inch
  let unit = w / (b.cols + 2 * b.pad)
  align(center, box(width: w, height: unit * (b.rows + 2 * b.pad), {
    place(top + left, image(b.path, width: w))
    place(top + left, dx: unit * 1.1, dy: 0pt,
      text(font: L.fonts.sans, size: base, weight: "bold", "START"))
    place(bottom + right, dx: -unit * 1.1, dy: 0pt,
      text(font: L.fonts.sans, size: base, weight: "bold", "FINISH"))
    for l in b.at("letters", default: ()) {
      place(top + left, dx: (l.c + b.pad) * unit, dy: (l.r + b.pad) * unit,
        box(width: unit, height: unit, align(center + horizon,
          text(font: L.fonts.sans, weight: "bold", size: b.font_pt * 1pt, l.ch))))
    }
  }))
}

#let answer-lines(b) = {
  set text(font: L.fonts.sans, size: b.at("font_pt", default: 12) * 1pt)
  let pairs = b.at("pairs", default: 1)
  grid(
    columns: if pairs == 1 { (auto, 1fr) } else { (1.15fr, 1fr) * pairs },
    row-gutter: b.at("gap_em", default: 1.1) * 1em,
    column-gutter: 1em,
    ..b.rows.map(r => (
      r.left,
      if r.right == "" { box(width: 100%, height: 1em, stroke: (bottom: 0.6pt)) } else if r.right.contains("_") { text(tracking: 0.08em, r.right) } else { strong(r.right) },
    )).flatten(),
  )
}

#let cryptogram(b) = {
  let fpt = b.at("font_pt", default: 12) * 1pt
  let small = if fpt >= 16pt { fpt } else { 0.8 * fpt }  // large print: no text below 16 pt
  set text(font: L.fonts.sans, size: fpt)
  let cell(x) = box(width: 1.1 * fpt, stack(dir: ttb, spacing: 0.2em,
    box(width: 100%, height: 1.3 * fpt, stroke: if x.c != "" { (bottom: 0.6pt) } else { none },
      align(center + bottom, strong(x.p))),
    box(width: 100%, height: 1em, align(center, text(size: small, fill: luma(60), x.c))),
  ))
  let body = par(leading: 0.7em, justify: false,
    b.words.map(w => box(w.map(cell).join())).join(h(0.9em)))
  block(breakable: false, below: 0.9em, {
    if b.at("number", default: none) != none {
      grid(columns: (auto, 1fr), column-gutter: 0.6em,
        text(weight: "bold", str(b.number) + "."), body)
    } else { body }
    if b.at("source", default: "") != "" {
      align(right, text(style: "italic", size: small, "— " + b.source))
    }
  })
}

#let crossword-grid(b) = {
  let rows = b.cells
  let cell = b.cell_in * inch
  let fpt = b.font_pt * 1pt
  align(center, box(width: rows.at(0).len() * cell, height: rows.len() * cell, {
    for (r, row) in rows.enumerate() {
      for (c, x) in row.enumerate() {
        if x != none {
          place(top + left, dx: c * cell, dy: r * cell, rect(width: cell, height: cell,
            stroke: 0.8pt, inset: 0pt, {
              if x.n > 0 { place(top + left, dx: 1.5pt, dy: 1pt, text(size: 0.38 * fpt, str(x.n))) }
              align(center + horizon, text(font: L.fonts.sans, size: fpt, x.ch))
            }))
        }
      }
    }
  }))
}

// colour legend sits ABOVE the picture grid: the lower corners of the frame hold ornaments
#let legend-row(b) = {
  if b.at("legend", default: true) {
    // one single row of small swatches (owner 2026-11-21): the mosaic gets the room
    set text(font: L.fonts.sans, size: 0.78 * base)
    align(center, box(b.palette.map(e => box(stack(dir: ltr, spacing: 3pt,
      rect(width: 0.17in, height: 0.17in, fill: rgb(e.hex), stroke: 0.5pt),
      align(horizon, (if b.mode == "B" { str(e.answer) } else { str(e.n) }) + " " + e.name)))).join(h(0.7em))))
    v(0.35em)
  }
}

#let cbn-grid(b) = {
  legend-row(b)
  let rows = b.cells
  let nr = rows.len()
  let nc = rows.at(0).len()
  let cell = b.cell_in * inch
  let fpt = b.font_pt * 1pt
  let colors = b.at("colors", default: none)
  align(center, box(width: nc * cell, height: nr * cell, {
    for (r, row) in rows.enumerate() {
      for (c, lab) in row.enumerate() {
        let fill = if colors != none { rgb(b.palette.at(colors.at(r).at(c) - 1).hex) } else { white }
        place(top + left, dx: c * cell, dy: r * cell,
          rect(width: cell, height: cell, fill: fill, stroke: 0.4pt + luma(140)))
        if colors == none {
          place(top + left, dx: c * cell, dy: r * cell, box(width: cell, height: cell,
            align(center + horizon, text(font: L.fonts.sans, size: fpt, lab))))
        }
      }
    }
  }))
}

// Polygon colour-by-number mosaic (hexagons, triangles, dots…): every cell arrives as an outline
// in inches plus its centre, label and (solution pages) colour index.
#let cbn-poly(b) = {
  legend-row(b)
  let fpt = b.font_pt * 1pt
  let lab = b.label_in * inch
  align(center, box(width: b.w_in * inch, height: b.h_in * inch, {
    for c in b.cells {
      let fill = if c.f > 0 { rgb(b.palette.at(c.f - 1).hex) } else { white }
      place(top + left, polygon(fill: fill, stroke: 0.4pt + luma(140),
        ..c.p.map(q => (q.at(0) * inch, q.at(1) * inch))))
      if c.f == 0 {
        place(top + left, dx: c.c.at(0) * inch - lab / 2, dy: c.c.at(1) * inch - lab / 2,
          box(width: lab, height: lab, align(center + horizon,
            text(font: L.fonts.sans, size: fpt, c.l))))
      }
    }
  }))
}

#let word-list(b) = {
  let cols = b.at("columns", default: 3)
  set text(font: L.fonts.sans, size: b.at("font_pt", default: 11) * 1pt)
  align(center, grid(
    columns: (auto,) * cols,
    column-gutter: 2.2em,
    row-gutter: 0.55em,
    ..b.words,
  ))
}

#let toc(b) = {
  set text(font: L.fonts.sans)
  for e in b.entries {
    block(spacing: 0.5em, [#e.title #box(width: 1fr, repeat[.]) #e.page])
  }
}

// knock-out: functional blocks sit on a white panel so the watermark never shows through them
// (same geometry with or without watermark, so the no-watermark QA reference lays out identically)
#let panel(body) = if E != none {
  block(width: 100%, fill: if wm-on { white } else { none }, outset: 6pt, body)
} else { body }

#let render-block(b) = panel({
  let k = b.kind
  if k == "heading" {
    let lvl = b.at("level", default: 1)
    let size = if lvl == 1 { 1.8 * base } else { 1.3 * base }
    if lvl == 1 and T != none and T.at("plaque", default: none) != none {
      // title on a carved sign (Studio design kit); long titles shrink to fit
      let w = T.at("plaque_w_in", default: 5.0) * inch
      let h = T.at("plaque_h_in", default: 0.9) * inch
      let fs = if b.text.len() > 34 { 1.25 * base } else if b.text.len() > 24 { 1.5 * base } else { 1.85 * base }
      block(below: 0.7em, width: 100%, align(center, box(width: w, height: h, {
        place(center + horizon, image(T.plaque, width: w, height: h, fit: "stretch"))
        place(center + horizon, dx: T.at("text_dx_in", default: 0.0) * inch, dy: -0.02 * h,
          text(font: T.at("heading_font", default: L.fonts.sans), size: fs, fill: rgb(T.at("heading_ink", default: "#3b2412")),
            stroke: (paint: rgb("#3a2210"), thickness: 0.5pt), b.text))
      })))
    } else {
      block(below: 0.8em, text(font: L.fonts.sans, weight: "bold", size: size, b.text))
    }
  } else if k == "paragraph" {
    let fp = b.at("font_pt", default: none)
    if fp != none { text(size: fp * 1pt, par(justify: true, b.text)) } else { par(justify: true, b.text) }
    v(0.4em)
  } else if k == "list" {
    let fp = b.at("font_pt", default: none)
    let body = if b.at("numbered", default: false) { enum(tight: true, spacing: 0.35em, ..b.items) } else { list(..b.items) }
    if fp != none { text(size: fp * 1pt, body) } else { body }
  } else if k == "writelog" {
    // Code Log: generous ruled lines to write on (owner 2026-11-21: lines were too close together)
    let rule = box(width: 100%, height: 0.27in, stroke: (bottom: 0.7pt + luma(130)))
    v(0.45in)
    pad(x: 0.35in, for it in b.items {
      block(breakable: false, below: 0.2in, grid(columns: (auto, auto, 1fr, auto, 1fr, auto, 1fr), column-gutter: 7pt, row-gutter: 0.08in, align: bottom,
        text(weight: "bold", it.label), [evidence], rule, [it is], rule, [and], rule,
        [], [fact], grid.cell(colspan: 5, rule)))
    })
  } else if k == "spacer" {
    v(b.height_in * inch)
  } else if k == "url" {
    align(center, text(font: L.fonts.mono, weight: "bold", size: 1.1 * base, b.text))
    v(0.3em)
  } else if k == "image" {
    if T != none {  // themed book: picture in a rounded gold frame
      align(center, box(radius: 8pt, clip: true, stroke: (paint: rgb(T.at("accent", default: "#b8862b")), thickness: 2pt),
        image(b.path, width: b.width_in * inch)))
      v(0.3em)
    } else {
      align(center, image(b.path, width: b.width_in * inch))
    }
  } else if k == "letter_grid" {
    letter-grid(b)
  } else if k == "sudoku_grid" {
    sudoku-grid(b)
  } else if k == "maze" {
    maze(b)
  } else if k == "answer_lines" {
    answer-lines(b)
  } else if k == "cryptogram" {
    cryptogram(b)
  } else if k == "crossword_grid" {
    crossword-grid(b)
  } else if k == "cells" {
    grid(
      columns: (1fr,) * b.columns,
      column-gutter: 0.25in,
      row-gutter: 0.2in,
      ..b.items.map(it => block(breakable: false, {
        text(font: L.fonts.sans, weight: "bold", size: 0.85 * base, it.title)
        v(0.2em)
        for x in it.blocks { render-block(x) }
      })),
    )
  } else if k == "cbn_grid" {
    cbn-grid(b)
  } else if k == "cbn_poly" {
    cbn-poly(b)
  } else if k == "word_list" {
    word-list(b)
  } else if k == "toc" {
    toc(b)
  } else {
    panic("unknown block kind: " + k)
  }
})

// themed pages: whatever does not fit the clear area of the frame shrinks to fit (never runs into
// the corner ornaments or onto the next page)
#let fit(body) = block(width: 100%, height: 100%, layout(size => {
  let m = measure(width: size.width, body)
  let k = if m.height > size.height { size.height / m.height } else { 1.0 }
  scale(x: k * 100%, y: k * 100%, origin: top + center, reflow: true, block(width: size.width, body))
}))

// Like fit(), but for the small panel of a designed page: the content is laid out wider and scaled
// down as one piece, so a long line (number-lock chain, alphabet strip) never wraps or runs out.
#let fit-wide(body, top: 1.0) = block(width: 100%, height: 100%, layout(size => {
  let pick = 0.5
  for k in (1.0, 0.92, 0.85, 0.78, 0.72, 0.66, 0.6, 0.55, 0.5).filter(k => k <= top) {
    let m = measure(width: size.width / k, body)
    if m.height * k <= size.height { pick = k; break }
  }
  align(center + horizon, scale(x: pick * 100%, y: pick * 100%, reflow: true, block(width: size.width / pick, body)))
}))

// ---------------------------------------------------------------- designed puzzle page (themed books)
#let styled-puzzle(p) = {
  let S = p.style
  let c = rgb(S.color)
  let soft = c.lighten(86%)
  // sign title (plaque from the design kit) + chapter line
  render-block((kind: "heading", text: S.title, level: 1))
  v(-0.45em)
  align(center, text(font: L.fonts.sans, size: 0.85 * base, weight: "bold", fill: c, upper(S.subtitle)))
  v(0.35em)
  let I = T.at("icons", default: (:))
  let icon(name, w) = if name in I { image(I.at(name), width: w) } else { none }
  // the puzzle itself on a white card with the type colour; a sticker icon sits on its corner
  block(width: 100%, breakable: false, fill: white, stroke: (paint: c, thickness: 2pt), radius: 10pt, inset: 8pt, {
    for b in p.blocks { render-block(b) }
    let ic = icon(S.at("icon", default: "key"), 0.62in)
    if ic != none { place(top + right, dx: 0.28in, dy: -0.42in, ic) }
  })
  v(0.4em)
  // how to play + tips
  grid(columns: (1.35fr, 1fr), column-gutter: 0.12in,
    block(width: 100%, fill: soft, stroke: (paint: c, thickness: 1.2pt), radius: 8pt, inset: 8pt, {
      box(icon("watch", 0.22in)) + h(0.3em) + text(font: L.fonts.sans, weight: "bold", size: 0.9 * base, fill: c, "HOW TO PLAY")
      v(0.25em)
      for (i, s) in S.steps.enumerate() {
        grid(columns: (0.22in, 1fr), column-gutter: 0.06in,
          box(width: 0.2in, height: 0.2in, radius: 50%, fill: c,
            align(center + horizon, text(font: L.fonts.sans, weight: "bold", size: 0.75 * base, fill: white, str(i + 1)))),
          text(size: 0.8 * base, s))
        v(0.05em)
      }
    }),
    block(width: 100%, fill: rgb("#fff6d8"), stroke: (paint: rgb("#e0a526"), thickness: 1.2pt), radius: 8pt, inset: 8pt, {
      box(icon("bulb", 0.22in)) + h(0.3em) + text(font: L.fonts.sans, weight: "bold", size: 0.9 * base, fill: rgb("#b7791f"), "TIPS")
      v(0.25em)
      for s in S.tips { text(size: 0.8 * base, [• #s]); v(0.1em) }
    }),
  )
  v(0.35em)
  // slogan ribbon
  align(center, box(fill: c, radius: 14pt, inset: (x: 16pt, y: 6pt),
    text(font: T.at("heading_font", default: L.fonts.sans), size: 1.05 * base, fill: white, S.slogan)))
}

// ---------------------------------------------------------------- pages
#let cover-of(p) = if p.kind != "title" { none } else {
  p.at("blocks", default: ()).find(b => b.kind == "image")
}

#let title-page(p) = {
  let img = cover-of(p)
  if img != none {
    // themed book: the cover picture fills the page (page background); title on a dark band,
    // the back-cover blurb on a parchment card at the foot (owner 2026-11-21)
    let hf = if T != none { T.at("heading_font", default: L.fonts.sans) } else { L.fonts.sans }
    let gold = rgb("#f3d58a")
    block(width: 100%, fill: rgb("#14203a").transparentize(12%), radius: 10pt, inset: (x: 16pt, y: 14pt),
      stroke: (paint: gold, thickness: 1.2pt), align(center, {
        text(font: hf, size: 3.0 * base, fill: gold, L.title)
        if L.subtitle != "" { v(0.35em); text(font: L.fonts.sans, size: 1.15 * base, fill: white, upper(L.subtitle)) }
      }))
    v(1fr)
    let paras = p.blocks.filter(b => b.kind == "paragraph")
    if paras.len() > 0 {
      block(width: 100%, fill: rgb("#fffaf0").transparentize(8%), radius: 10pt, inset: 14pt,
        stroke: (paint: rgb("#b8862b"), thickness: 1.2pt), {
          set par(justify: true)
          for (i, b) in paras.enumerate() {
            if i == 0 { text(size: 1.05 * base, b.text) } else { v(0.4em); align(center, text(font: L.fonts.sans, weight: "bold", size: 0.95 * base, fill: rgb("#8a1c1c"), b.text)) }
          }
        })
    }
  } else {
    v(1fr)
    align(center)[
      #text(font: L.fonts.sans, weight: "bold", size: 2.6 * base, L.title)
      #if L.subtitle != "" { v(0.8em); text(font: L.fonts.sans, size: 1.4 * base, L.subtitle) }
    ]
    for b in p.at("blocks", default: ()) { v(0.8em); render-block(b) }
    v(1fr)
    if L.author != "" { align(center, text(size: 1.2 * base, L.author)) }
    v(0.5fr)
  }
}

#let notes-page(p) = {
  text(font: L.fonts.sans, weight: "bold", size: 1.6 * base, p.at("title", default: "Notes"))
  v(1em)
  for _ in range(18) {
    v(1fr)
    line(length: 100%, stroke: 0.4pt + luma(150))
  }
  v(1fr)
}

// Gemini-designed page for this puzzle type (forge/mystery/art.py build_templates), or none
#let tpl-of(p) = if T == none or p.at("style", default: none) == none { none } else if p.style.type == "story" {
  (image: p.style.bg, pic: (w: p.style.w, h: p.style.h))
} else if p.style.type == "poster" {
  (image: p.style.bg)
} else {
  T.at("templates", default: (:)).at(p.style.type, default: none)
}
// one shared frame over every designed page (the frame with a transparent centre); a designed
// page is fitted into the opening of that frame, so the frame never hides its texts. A story
// picture sits complete at the top of the opening: nothing is laid over it.
#let designed-bg(tp) = {
  let win = T.at("window", default: (x: 0.0, y: 0.0, w: 1.0, h: 1.0))
  place(top + left, image(T.background, width: 100%, height: 100%, fit: "stretch"))
  let pic = tp.at("pic", default: none)
  if pic != none {
    place(top + left, dx: (win.x + (1 - pic.w) / 2 * win.w) * 100%, dy: win.y * 100%,
      image(tp.image, width: pic.w * win.w * 100%, height: pic.h * win.h * 100%, fit: "stretch"))
  } else {
    place(top + left, dx: win.x * 100%, dy: win.y * 100%,
      image(tp.image, width: win.w * 100%, height: win.h * 100%, fit: "stretch"))
  }
  if T.at("overlay", default: none) != none {
    place(top + left, image(T.overlay, width: 100%, height: 100%, fit: "stretch"))
  }
}
// storytelling page: the whole picture on top, the story on the plain paper under it
#let story-page(p) = {
  let side = L.margins.outside * inch
  let win = T.at("window", default: (x: 0.0, y: 0.0, w: 1.0, h: 1.0))
  // plain paper only: under the picture, above the corner ornaments
  let bx = (win.x + 0.075 * win.w) * L.width_in * inch
  let by = (win.y + (p.style.h + 0.02) * win.h) * L.height_in * inch
  let bw = 0.85 * win.w * L.width_in * inch
  let bh = calc.min(0.79 * L.height_in * inch - by, 0.40 * win.h * L.height_in * inch)
  let body(k) = {
    set text(size: k * base, fill: rgb("#24160c"))
    set par(leading: 0.5em, justify: true)
    for b in p.blocks { render-block(b) }
  }
  place(top + left, dx: bx - side, dy: by - L.margins.top * inch,
    context {
      // largest size that fits the calm lower part of the painting (never spills over the frame)
      let k = (1.12, 1.05, 1.0, 0.93, 0.86, 0.8, 0.74, 0.68).find(k => measure(block(width: bw, body(k))).height <= bh)
      block(width: bw, height: bh, body(if k == none { 0.62 } else { k }))
    })
}

// the whole designed page is the background; the exact puzzle sits in its empty panel
#let template-puzzle(p, tp) = {
  let c = rgb(p.style.color)
  let side = L.margins.outside * inch
  place(top + left, dx: tp.x_in * inch - side, dy: tp.y_in * inch - L.margins.top * inch,
    block(width: tp.w_in * inch, height: tp.h_in * inch, inset: (x: 0.26in, y: 0.2in), fit-wide(top: if p.style.type == "cbn" { 1.0 } else { 0.78 }, {
      // fit(): the puzzle shrinks until it is inside the panel, never over the frame art
      align(center, text(font: L.fonts.sans, size: 0.85 * base, weight: "bold", fill: c, upper(p.style.subtitle)))
      v(0.2em)
      align(center, { for b in p.blocks { render-block(b) } })
    })))
}

#for p in L.pages {
  let tp = tpl-of(p)
  page(
    header: if p.header and p.kind != "title" and T == none { running-header } else { none },
    footer: if p.number and p.kind != "title" { page-footer } else { none },
    background: if tp != none { designed-bg(tp) } else if cover-of(p) != none {
      place(top + left, image(cover-of(p).path, width: 100%, height: 100%, fit: "cover"))
    } else { page-background },
  )[
    #if p.kind == "title" {
      title-page(p)
    } else if p.kind == "notes" {
      panel(notes-page(p))  // writing area: knocks the watermark out
    } else if p.kind == "blank" {
      []
    } else {
      let styled = T != none and p.at("style", default: none) != none
      if p.at("title", default: none) != none and not styled and T == none {
        render-block((kind: "heading", text: p.title, level: 1))
      }
      if tp != none and p.style.type == "poster" {
        []  // the whole page is designed, text included
      } else if tp != none and p.style.type == "story" {
        story-page(p)
      } else if tp != none {
        template-puzzle(p, tp)
      } else if styled {
        // inset: the cards stay clear of the keys / lanterns the frame hangs on its sides
        block(width: 100%, height: 100% - 0.55in, pad(x: 0.38in, fit(styled-puzzle(p))))
      } else if T != none and p.blocks.len() > 0 and T.at("card", default: false) {  // owner: no white cards
        // themed book: the page content sits on a cream card with a gold rule (reads well on the parchment frame)
        block(width: 100%, breakable: true, fill: rgb(T.at("panel_fill", default: "#fffdf6")),
          stroke: (paint: rgb(T.at("accent", default: "#b8862b")), thickness: 1.2pt), radius: 10pt, inset: 12pt,
          { for b in p.blocks { render-block(b) } })
      } else if T != none {
        block(width: 100%, height: 100% - 0.55in, fit({
          if p.at("title", default: none) != none {
            render-block((kind: "heading", text: p.title, level: 1))
          }
          for b in p.blocks { render-block(b) }
        }))
      } else {
        for b in p.blocks { render-block(b) }
      }
    }
  ]
}
