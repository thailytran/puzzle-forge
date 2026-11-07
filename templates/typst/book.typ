// Puzzle Forge — book interior template.
// Python writes `layout.json` next to this file (see forge/layout/document.py).
#let L = json(sys.inputs.at("layout", default: "layout.json"))
#let inch = 1in
#let base = L.base_size_pt * 1pt

#set document(title: L.title, author: if L.author == "" { () } else { L.author }, date: none)
#set text(font: L.fonts.body, size: base, lang: "en")
#set par(leading: 0.6em)

#let running-header = context {
  set text(font: L.fonts.sans, size: 8.5pt, fill: luma(90))
  align(center, L.title)
}
#let page-footer = context {
  set text(font: L.fonts.sans, size: 0.8 * base)
  align(center, counter(page).display())
}

#set page(
  width: L.width_in * inch,
  height: L.height_in * inch,
  margin: (
    inside: L.margins.inside * inch,
    outside: L.margins.outside * inch,
    top: L.margins.top * inch,
    bottom: L.margins.bottom * inch,
  ),
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
    columns: (1.15fr, 1fr) * pairs,
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

#let render-block(b) = {
  let k = b.kind
  if k == "heading" {
    let lvl = b.at("level", default: 1)
    let size = if lvl == 1 { 1.8 * base } else { 1.3 * base }
    block(below: 0.8em, text(font: L.fonts.sans, weight: "bold", size: size, b.text))
  } else if k == "paragraph" {
    let fp = b.at("font_pt", default: none)
    if fp != none { text(size: fp * 1pt, par(justify: true, b.text)) } else { par(justify: true, b.text) }
    v(0.4em)
  } else if k == "list" {
    list(..b.items)
  } else if k == "spacer" {
    v(b.height_in * inch)
  } else if k == "image" {
    align(center, image(b.path, width: b.width_in * inch))
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
  } else if k == "word_list" {
    word-list(b)
  } else if k == "toc" {
    toc(b)
  } else {
    panic("unknown block kind: " + k)
  }
}

// ---------------------------------------------------------------- pages
#let title-page(p) = {
  v(1fr)
  align(center)[
    #text(font: L.fonts.sans, weight: "bold", size: 2.6 * base, L.title)
    #if L.subtitle != "" { v(0.8em); text(font: L.fonts.sans, size: 1.4 * base, L.subtitle) }
  ]
  v(1fr)
  if L.author != "" { align(center, text(size: 1.2 * base, L.author)) }
  v(0.5fr)
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

#for p in L.pages {
  page(
    header: if p.header and p.kind != "title" { running-header } else { none },
    footer: if p.number and p.kind != "title" { page-footer } else { none },
  )[
    #if p.kind == "title" {
      title-page(p)
    } else if p.kind == "notes" {
      notes-page(p)
    } else if p.kind == "blank" {
      []
    } else {
      if p.at("title", default: none) != none {
        render-block((kind: "heading", text: p.title, level: 1))
      }
      for b in p.blocks { render-block(b) }
    }
  ]
}
