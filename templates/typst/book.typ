// Puzzle Forge — book interior template.
// Python writes `layout.json` next to this file (see forge/layout/document.py).
#let L = json(sys.inputs.at("layout", default: "layout.json"))
#let inch = 1in
#let base = L.base_size_pt * 1pt

#set document(title: L.title, author: if L.author == "" { () } else { L.author }, date: none)
#set text(font: L.fonts.body, size: base, lang: "en")
#set par(leading: 0.6em)

#let running-header = context {
  set text(font: L.fonts.sans, size: 0.75 * base, fill: luma(90))
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
  let n = rows.at(0).len()
  let cell = b.at("cell_in", default: 0.35) * inch
  let fpt = b.at("font_pt", default: 14) * 1pt
  align(center, table(
    columns: (cell,) * n,
    rows: (cell,) * rows.len(),
    align: center + horizon,
    stroke: 0.5pt + luma(120),
    inset: 0pt,
    ..rows.flatten().map(c => text(font: L.fonts.sans, size: fpt, c)),
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
    par(justify: true, b.text)
    v(0.4em)
  } else if k == "list" {
    list(..b.items)
  } else if k == "spacer" {
    v(b.height_in * inch)
  } else if k == "image" {
    align(center, image(b.path, width: b.width_in * inch))
  } else if k == "letter_grid" {
    letter-grid(b)
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
