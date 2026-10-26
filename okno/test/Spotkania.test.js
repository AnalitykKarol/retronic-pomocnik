"use strict"

// Uruchom: node --test okno/test/*.test.js   (z katalogu repo bota)
// Statystyki spotkań z graczami (26.10): czysta logika SpotkaniaModel.js (linie karty, tabela, tempo, zmiany spotu, unikane) oraz kontrakt na ATRAPIE:
// `atrapa.py --spotkania` buduje pięć postaci z telemetrią, a prawdziwy okno_api (stan + spotkania) karmi model. Nic z prawdziwego katalogu, żadnych skryptów akcji.

const { describe, it, before, after } = require("node:test")
const assert = require("node:assert/strict")
const fs = require("node:fs")
const os = require("node:os")
const path = require("node:path")
const { spawnSync } = require("node:child_process")
const S = require("../SpotkaniaModel.js")
const M = require("../OknoModel.js")

const REPO = path.resolve(__dirname, "..", "..")
const NOW = new Date(1792691600 * 1000)
const hm = (s) => { const d = new Date(s * 1000); return (d.getHours() < 10 ? "0" : "") + d.getHours() + ":" + (d.getMinutes() < 10 ? "0" : "") + d.getMinutes() }

const sp = (over) => Object.assign({
  dostepne: true, powod: null, prog: 3, zrodlo: "telemetria", n: 1, bywalec: { nick: "Statutum", n: 1 }, bywalec_prog15: { nick: "Statutum", n: 1 }, graczy: 2, spotkan: 2, spotkan_prog15: 2, czas_na_spocie_s: 5040,
  spotkan_na_h: 0.7, ostatni: { nick: "Mleczko", t: 1792691000 }, uwaga: null, wiek_s: 12
}, over || {})
const inst = (id, spot, over) => Object.assign({ id: id, nick: id.toUpperCase(), przeglad: { stan: "bot_dziala", exp_h: 18400, zab_h: 95.8 }, spotkania: spot }, over || {})
const brak = (powod) => ({ dostepne: false, powod: powod, prog: 3 })

describe("formaty", () => {
  it("czas: 1h 24m, 24m, <1m, brak; liczby po polsku z przecinkiem", () => {
    assert.equal(S.span(5040), "1h 24m")
    assert.equal(S.span(3600), "1h")
    assert.equal(S.span(1440), "24m")
    assert.equal(S.span(30), "<1m")
    assert.equal(S.span(null), "-")
    assert.equal(S.span(-5), "-")
    assert.equal(S.decimal(0.7), "0,7")
    assert.equal(S.decimal(12), "12")
    assert.equal(S.decimal(2.86), "2,9")
    assert.equal(S.decimal(0), "0")
    assert.equal(S.decimal(null), "-")
  })
})

describe("linie karty postaci", () => {
  it("linie jak w makiecie: spotkań (bez progu 15 s) + najczęstszy gracz + próg bota n/próg, czas na spocie + spotkań na godzinę", () => {
    const l = S.cardLines(inst("a", sp()))
    assert.equal(l.shown, true)
    assert.equal(l.meet, "👥 spotkań 2 · próg 1/3 · Statutum ×1")
    assert.equal(l.time, "na spocie 1h 24m · 0,7/h")
    assert.equal(l.hot, false)
    assert.equal(l.ok, true)
  })
  it("krótkie mijania: spotkań (bez progu) większe niż licznik bota; „próg” nie jest podpisany jako spotkania", () => {
    const l = S.cardLines(inst("a", sp({ spotkan: 6, n: 0, spotkan_prog15: 0, bywalec: { nick: "Vados", n: 5 }, bywalec_prog15: null })))
    assert.equal(l.meet, "👥 spotkań 6 · próg 0/3 · Vados ×5")
    assert.equal(l.hot, false)
    assert.match(l.tip, /^Spotkań: 6 \(gracz w zasięgu wzroku choćby na chwilę/)
    assert.match(l.tip, /Próg 0\/3: licznik bota, spotkanie liczy się po 15 s w widoku; po 3\. spotkaniu tego samego gracza nadzorca zmienia spot/)
  })
  it("podpowiedź niesie najczęstszego gracza wg bota (do porównania) i widzianych", () => {
    const l = S.cardLines(inst("a", sp({ spotkan: 6, n: 2, bywalec: { nick: "Vados", n: 5 }, bywalec_prog15: { nick: "Usio", n: 2 }, widziani: 3, widziani_od: 1792650000, widziani_lista: [] })))
    assert.match(l.tip, /\(najczęściej: Usio ×2\)/)
    assert.match(l.tip, /Widziani na tym spocie od \d\d:\d\d: 3/)
  })
  it("licznik bota na progu (n >= próg) = hot; próg bierze z API, nie na sztywno", () => {
    assert.equal(S.cardLines(inst("a", sp({ n: 3, bywalec: { nick: "Statutum", n: 3 } }))).hot, true)
    assert.equal(S.cardLines(inst("a", sp({ n: 3 }))).meet.indexOf("próg 3/3") > 0, true)
    assert.equal(S.cardLines(inst("a", sp({ n: 2 }))).hot, false)
    assert.equal(S.cardLines(inst("a", sp({ n: 4, prog: 5 }))).hot, false)
    assert.equal(S.cardLines(inst("a", sp({ n: 5, prog: 5 }))).hot, true)
    assert.equal(S.cardLines(inst("a", sp({ n: 7, bywalec: { nick: "X", n: 7 } }))).hot, true)
  })
  it("zero spotkań na pomiarze: 0 bez bywalca, próg 0/3 i 0/h (to prawdziwe zero, nie brak)", () => {
    const l = S.cardLines(inst("a", sp({ n: 0, bywalec: null, spotkan: 0, spotkan_na_h: 0 })))
    assert.equal(l.meet, "👥 spotkań 0 · próg 0/3")
    assert.equal(l.time, "na spocie 1h 24m · 0/h")
  })
  it("krótki czas na spocie: spotkań/h = „-” (po 10 minutach), czas pokazany", () => {
    const l = S.cardLines(inst("a", sp({ czas_na_spocie_s: 240, spotkan_na_h: null })))
    assert.equal(l.time, "na spocie 4m · -/h")
  })
  it("brak danych (bot stoi, inna sesja, jeszcze nie policzone): „-”, nigdy zera, bez wyróżnienia, z powodem", () => {
    for (const powod of ["bot nie działa", "dane z poprzedniej sesji bota", "jeszcze nie policzone", "telemetria nieświeża (bot nie pisze)"]) {
      const l = S.cardLines(inst("a", brak(powod)))
      assert.equal(l.shown, true)
      assert.equal(l.meet, "👥 spotkań -")
      assert.equal(l.time, "na spocie - · -/h")
      assert.equal(l.hot, false)
      assert.equal(l.ok, false)
      assert.equal(l.why, powod)
    }
  })
  it("niedostępne z polami liczbowymi (np. stare dane): liczby nigdy nie przeciekają na kartę", () => {
    const l = S.cardLines(inst("a", Object.assign(brak("dane z poprzedniej sesji bota"), { n: 3, czas_na_spocie_s: 9999, spotkan_na_h: 5 })))
    assert.equal(l.meet, "👥 spotkań -")
    assert.equal(l.hot, false)
  })
  it("stary stan bez pola `spotkania` = karta bez linii (shown false)", () => {
    assert.equal(S.cardLines({ id: "a" }).shown, false)
    assert.equal(S.cardLines({ id: "a", spotkania: null }).shown, false)
    assert.equal(S.cardLines({ id: "a", spotkania: "zle" }).shown, false)
  })
  it("brak pola n/czasu mimo dostepne = bez zer udających pomiar na czasie", () => {
    const l = S.cardLines(inst("a", sp({ n: undefined, czas_na_spocie_s: undefined, spotkan_na_h: undefined, bywalec: null })))
    assert.equal(l.time, "na spocie - · -/h")
  })
})

describe("widziani na obecnym spocie (26.10)", () => {
  const T0 = 1792650000
  const wid = (over) => sp(Object.assign({ widziani: 7, widziani_od: T0, widziani_lista: [{ nick: "Vados", probek: 12, pierwszy_t: T0 + 60, ostatnio_t: T0 + 600 }, { nick: "Usio", probek: 8, pierwszy_t: T0 + 100, ostatnio_t: T0 + 300 }], widziani_powod: null, widziani_uwaga: null }, over || {}))
  it("trzecia linia karty: liczba + od której godziny; stare linie bez zmian", () => {
    const l = S.cardLines(inst("a", wid()))
    assert.equal(l.seen, "👁 widziani 7 · od " + hm(T0))
    assert.equal(l.seenOk, true)
    assert.equal(l.meet, "👥 spotkań 2 · próg 1/3 · Statutum ×1")
    assert.equal(l.time, "na spocie 1h 24m · 0,7/h")
    assert.match(l.seenTip, /^Widziani na tym spocie od \d\d:\d\d: 7 /)
    assert.match(l.seenTip, /Vados \(ostatnio \d\d:\d\d\), Usio \(ostatnio \d\d:\d\d\), …/)
  })
  it("zero widzianych to prawdziwe zero (nie brak); bez listy nicków nie ma „…”", () => {
    const l = S.cardLines(inst("a", wid({ widziani: 0, widziani_lista: [] })))
    assert.equal(l.seen, "👁 widziani 0 · od " + hm(T0))
    assert.equal(l.seenOk, true)
    assert.equal(l.seenTip.indexOf("…"), -1)
  })
  it("brak początku huntu: „-” z powodem z API, nigdy zero", () => {
    const s0 = inst("a", wid({ widziani: null, widziani_od: null, widziani_lista: [], widziani_powod: "brak początku huntu (ostatnie.json bez na_spocie_od)" }))
    const l = S.cardLines(s0)
    assert.equal(l.seen, "👁 widziani -")
    assert.equal(l.seenOk, false)
    assert.equal(l.seenTip, "widziani: brak początku huntu (ostatnie.json bez na_spocie_od)")
    assert.equal(S.seenOf(s0).why, "brak początku huntu (ostatnie.json bez na_spocie_od)")
    assert.equal(S.rowOf(s0).seen, "-")
  })
  it("stara pamięć podręczna bez pól widziani = „-”, reszta karty jak dotąd", () => {
    const l = S.cardLines(inst("a", sp()))
    assert.equal(l.seen, "👁 widziani -")
    assert.equal(l.seenOk, false)
    assert.equal(l.meet, "👥 spotkań 2 · próg 1/3 · Statutum ×1")
    assert.equal(S.seenOf(inst("a", sp())).why, "jeszcze nie policzone")
  })
  it("brak danych o spotkaniach (bot stoi): „-”, liczba z poprzedniej sesji nie przecieka", () => {
    const l = S.cardLines(inst("a", Object.assign(brak("bot nie działa"), { widziani: 9 })))
    assert.equal(l.seen, "👁 widziani -")
    assert.equal(l.seenOk, false)
  })
  it("stary stan bez pola `spotkania`: bez linii (seen puste)", () => {
    const l = S.cardLines({ id: "a" })
    assert.equal(l.shown, false)
    assert.equal(l.seen, "")
  })
  it("tabela i blok „czas i tempo”: liczba, od kiedy, nicki z godziną ostatniego widoku", () => {
    assert.equal(S.rowOf(inst("a", wid())).seen, "7")
    const t = S.tempoOf(inst("a", wid()))
    assert.equal(t.seen, "7")
    assert.equal(t.seenSince, "od " + hm(T0))
    assert.deepEqual(t.seenNames, ["Vados · " + hm(T0 + 600), "Usio · " + hm(T0 + 300)])
    assert.equal(S.tempoOf(inst("a", brak("bot nie działa"))).seen, "-")
  })
})

describe("tabela per postać", () => {
  const lista = [
    inst("a", sp({ n: 3, bywalec: { nick: "Statutum", n: 3 }, spotkan: 4, spotkan_na_h: 2.9, czas_na_spocie_s: 5000, graczy: 2 })),
    inst("b", brak("bot nie działa"), { przeglad: { stan: "zatrzymany" } }),
    inst("c", sp({ n: 0, bywalec: null, spotkan: 0, spotkan_na_h: 0, graczy: 0, czas_na_spocie_s: 2000 }))
  ]
  it("kolejność wejścia zachowana (sortowanie robi Backend jak w Przeglądzie), komórki sformatowane", () => {
    const r = S.rowsOf(lista)
    assert.deepEqual(r.map((x) => x.id), ["a", "b", "c"])
    assert.equal(r[0].meet, "3/3")
    assert.equal(r[0].hot, true)
    assert.equal(r[0].onSpot, "1h 23m")
    assert.equal(r[0].players, "2")
    assert.equal(r[0].perHour, "2,9")
    assert.equal(r[0].regular, "Statutum ×3")
    assert.equal(r[2].meet, "0/3")
    assert.equal(r[2].regular, "-")
    assert.equal(r[2].perHour, "0")
  })
  it("brak danych = „-” w każdej komórce, powód i stan postaci w wierszu", () => {
    const b = S.rowsOf(lista)[1]
    assert.deepEqual([b.onSpot, b.players, b.meet, b.perHour, b.regular], ["-", "-", "-", "-", "-"])
    assert.equal(b.ok, false)
    assert.equal(b.why, "bot nie działa")
    assert.equal(b.state, "bot stoi")
    assert.equal(b.whyShort, "bot stoi")
    assert.equal(S.rowOf(inst("x", brak("dane z poprzedniej sesji bota"))).whyShort, "inna sesja bota")
    assert.equal(S.rowOf(inst("x", brak("coś nowego"))).whyShort, "coś nowego")
    assert.equal(S.rowOf(inst("x", sp())).whyShort, "")
  })
  it("podsumowanie: ile postaci z danymi i ile na progu", () => {
    assert.deepEqual(S.summaryOf(lista), { total: 3, withData: 2, hot: 1 })
    assert.deepEqual(S.summaryOf([]), { total: 0, withData: 0, hot: 0 })
    assert.deepEqual(S.summaryOf(null), { total: 0, withData: 0, hot: 0 })
  })
})

describe("czas i tempo wybranej postaci", () => {
  it("czas na spocie, spotkań/h z raportu; exp/h i zabicia/h z przeglądu (spacja tysięcy, przecinek)", () => {
    const t = S.tempoOf(inst("a", sp()))
    assert.equal(t.onSpot, "1h 24m")
    assert.equal(t.perHour, "0,7")
    assert.equal(t.expH, "18 400")
    assert.equal(t.zabH, "95,8")
    assert.equal(t.ok, true)
  })
  it("bot stoi: wszystko „-”, exp/h i zab/h też (nie pokazujemy tempa martwej sesji)", () => {
    const t = S.tempoOf(inst("a", brak("bot nie działa"), { przeglad: { stan: "zatrzymany", exp_h: 18400, zab_h: 90 } }))
    assert.deepEqual([t.onSpot, t.perHour, t.expH, t.zabH], ["-", "-", "-", "-"])
    assert.equal(t.why, "bot nie działa")
  })
  it("krótki czas: notka przy spotkań/h", () => {
    assert.equal(S.tempoOf(inst("a", sp({ spotkan_na_h: null, czas_na_spocie_s: 200 }))).perHourNote, "po 10 minutach na spocie")
  })
})

describe("ostatnio widziany gracz", () => {
  it("najświeższy z postaci z danymi: nick, godzina, postać", () => {
    const l = [
      inst("a", sp({ ostatni: { nick: "Stary", t: 1792690000 } })),
      inst("b", sp({ ostatni: { nick: "Mleczko", t: 1792691300 } })),
      inst("c", Object.assign(brak("bot nie działa"), { ostatni: { nick: "Duch", t: 1792691590 } }))       // niedostępne nie liczy się nigdy
    ]
    const r = S.lastSeen(l, NOW)
    assert.equal(r.nick, "Mleczko")
    assert.equal(r.postac, "B")
    assert.equal(r.time, hm(1792691300))
    assert.equal(r.text, "Mleczko · " + hm(1792691300) + " · B")
  })
  it("brak graczy = null", () => {
    assert.equal(S.lastSeen([inst("a", sp({ ostatni: null }))], NOW), null)
    assert.equal(S.lastSeen([], NOW), null)
  })
})

describe("zmiany spotu dziś i unikane spoty", () => {
  const dane = {
    prog: 3,
    zmiany: [
      { t: 1792690000, id: "a", postac: "Aaa", typ: "zmiana", nick: "Statutum", n: 3, z: "trolle_edron", na: "rook_raty", powod: "gracz Statutum 3. raz", status: "wykonano", powt: 1 },
      { t: 1792689000, id: "b", postac: "Bbb", typ: "powrot", nick: "Mleczko", n: 3, z: "edron_trolle", na: null, powod: "brak wolnego spotu → powrót do miasta", status: "cien", powt: 1 },
      { t: 1792688000, id: "c", postac: "Ccc", typ: "brak", nick: "X", n: 3, z: "m", na: null, powod: "brak sensownego spotu, zostaje", status: "info", powt: 3 },
      { t: 1792687000, id: "lost", postac: "Stracona", typ: "zmiana", nick: "Y", n: 3, z: "a", na: "b", powod: "p", status: "blad", powt: 1 }
    ],
    unikane: [
      { id: "a", postac: "Aaa", mapa: "trolle_edron", jaskinia: "Edron, trolle z8", nick: "Statutum", zostalo_s: 5400 },
      { id: "lost", postac: "Stracona", mapa: "x", jaskinia: "X", nick: "Y", zostalo_s: 100 },
      { id: "b", postac: "Bbb", mapa: "edron_trolle", jaskinia: "Edron, troll cave", nick: "Mleczko", zostalo_s: 0 }
    ]
  }
  const widoczne = [inst("a", sp()), inst("b", sp()), inst("c", sp())]
  it("zmiana: godzina, postać, z którego na który spot, powód i status; powrót do miasta bez spotu docelowego", () => {
    const r = S.changeRows(dane, widoczne)
    assert.equal(r.length, 3)
    assert.deepEqual([r[0].time, r[0].nick, r[0].route, r[0].reason, r[0].status, r[0].tone], [hm(1792690000), "Aaa", "trolle_edron → rook_raty", "gracz Statutum 3. raz", "wykonano", "ok"])
    assert.equal(r[1].route, "edron_trolle → miasto")
    assert.equal(r[1].status, "tylko zapis")
    assert.equal(r[2].route, "m (zostaje)")
    assert.equal(r[2].repeat, 3)
  })
  it("postacie niewidoczne w oknie (stracone) nie pojawiają się w zmianach ani unikanych", () => {
    assert.equal(S.changeRows(dane, widoczne).some((x) => x.nick === "Stracona"), false)
    assert.equal(S.avoidRows(dane, widoczne).some((x) => x.nick === "Stracona"), false)
  })
  it("unikane: spot, gracz i czas do końca; wygasłe (0 s) pomijane", () => {
    const u = S.avoidRows(dane, widoczne)
    assert.equal(u.length, 1)
    assert.deepEqual([u[0].nick, u[0].spot, u[0].map, u[0].player, u[0].left], ["Aaa", "Edron, trolle z8", "trolle_edron", "Statutum", "1h 30m"])
  })
  it("brak danych polecenia = puste listy, bez wyjątku", () => {
    assert.deepEqual(S.changeRows(null, widoczne), [])
    assert.deepEqual(S.avoidRows(undefined, widoczne), [])
    assert.deepEqual(S.changeRows({ zmiany: "zle" }, widoczne), [])
  })
  it("podtytuł z progiem z API, ograniczenia z API albo stały zapis", () => {
    assert.match(S.subtitleOf({ prog: 5 }), /po 5\. spotkaniu/)
    assert.match(S.subtitleOf(null), /po 3\. spotkaniu/)
    assert.deepEqual(S.limitsOf({ granice: ["a", "b"] }), ["a", "b"])
    assert.equal(S.limitsOf(null).length >= 2, true)
  })
})

describe("polecenie", () => {
  it("spotkania: jedno wywołanie okno_api bez argumentów, bez powłoki", () => {
    assert.deepEqual(M.spotkaniaCommand("/r"), ["python3", "-I", "/r/okno_api.py", "spotkania"])
    assert.equal(M.spotkaniaCommand(""), null)
  })
})

// ---------------------------------------------------------------- kontrakt na atrapie: prawdziwy okno_api -> model
describe("okno_api na atrapie (`atrapa.py --spotkania`): to, co dostaje karta i zakładka", () => {
  let dir
  let env
  const run = (cmd) => spawnSync(cmd[0], cmd.slice(1), { encoding: "utf8", env: Object.assign({}, process.env, env), timeout: 60000 })
  before(() => {
    dir = fs.mkdtempSync(path.join(os.tmpdir(), "spotkania-test-"))
    const out = spawnSync("python3", [path.join(__dirname, "atrapa.py"), dir, "2", "--spotkania"], { encoding: "utf8" })
    assert.equal(out.status, 0, out.stderr)
    env = {}
    for (const l of out.stdout.split("\n")) { const m = /^export (\w+)="(.*)"$/.exec(l); if (m) env[m[1]] = m[2] }
  })
  after(() => fs.rmSync(dir, { recursive: true, force: true }))

  const stan = () => M.parseApi(run(M.stanCommand(REPO, null)).stdout).data.instancje
  const by = (list, id) => list.find((i) => i.id === id)

  it("przed pierwszym liczeniem karta pokazuje „-” (nie zera): jeszcze nie policzone", () => {
    const l = S.cardLines(by(stan(), "spohot"))
    assert.equal(l.meet, "👥 spotkań -")
    assert.equal(l.why, "jeszcze nie policzone")
  })
  it("polecenie spotkania liczy raz (cache 60 s), potem stan niesie liczniki per postać", () => {
    const r = M.parseApi(run(M.spotkaniaCommand(REPO)).stdout)
    assert.equal(r.ok, true, JSON.stringify(r))
    assert.equal(r.data.status_cache, "przeliczony")
    const r2 = M.parseApi(run(M.spotkaniaCommand(REPO)).stdout)
    assert.equal(r2.data.status_cache, "swiezy")
    const lista = stan()
    const hot = S.cardLines(by(lista, "spohot"))
    assert.equal(hot.meet, "👥 spotkań 4 · próg 3/3 · Statutum ×3")
    assert.equal(hot.hot, true)
    assert.match(hot.time, /^na spocie 1h 2\dm · 2,9\/h$/)
    assert.equal(S.cardLines(by(lista, "spolow")).meet, "👥 spotkań 1 · próg 1/3 · Statutum ×1")
    assert.equal(S.cardLines(by(lista, "spolow")).hot, false)
    // Przechodzień widziany 5 s: dla bota (>= 15 s) to 0/3, ale jako krótkie mijanie to 1 spotkanie
    assert.equal(S.cardLines(by(lista, "spozero")).meet, "👥 spotkań 1 · próg 0/3 · Przechodzień ×1")
    // spobot: „spotkań” zawsze z telemetrii (Mleczko 40 s), licznik bota z pliku bieżącej sesji (Statutum ×2) pod nazwami *_prog15
    assert.equal(S.cardLines(by(lista, "spobot")).meet, "👥 spotkań 1 · próg 2/3 · Mleczko ×1")
    assert.deepEqual(by(lista, "spobot").spotkania.bywalec_prog15, { nick: "Statutum", n: 2 })
    assert.equal(by(lista, "spobot").spotkania.spotkan_prog15, 3)
    assert.equal(by(lista, "spohot").spotkania.spotkan_prog15, 4)
    assert.equal(by(lista, "spozero").spotkania.spotkan_prog15, 0)
    assert.equal(by(lista, "spobot").spotkania.zrodlo, "bot")
    assert.equal(by(lista, "spohot").spotkania.zrodlo, "telemetria")
  })
  it("postać z zatrzymanym botem i główna: „-” zamiast liczb", () => {
    const lista = stan()
    for (const id of ["spostoi", "", "test"]) {
      const l = S.cardLines(by(lista, id))
      assert.equal(l.meet, "👥 spotkań -", id)
      assert.equal(l.time, "na spocie - · -/h", id)
    }
  })
  it("zakładka: tabela, ostatni gracz, zmiany spotu i unikane z prawdziwego API", () => {
    const lista = stan()
    const dane = M.parseApi(run(M.spotkaniaCommand(REPO)).stdout).data
    const rows = S.rowsOf(lista)
    assert.equal(rows.find((x) => x.id === "spohot").meet, "3/3")
    assert.equal(rows.find((x) => x.id === "spohot").spots, "4")
    assert.equal(rows.find((x) => x.id === "spozero").spots, "1")
    assert.equal(rows.find((x) => x.id === "spobot").botRegular, "Statutum ×2")
    assert.equal(rows.find((x) => x.id === "spobot").regular, "Mleczko ×1")
    assert.equal(rows.find((x) => x.id === "spostoi").onSpot, "-")
    assert.equal(S.lastSeen(lista, new Date()).nick, "Mleczko")
    // „widziani”: różni obcy w zasięgu wzroku od wejścia na spot (>= 1 próbka, bez progu 15 s)
    assert.equal(rows.find((x) => x.id === "spohot").seen, "2")        // Statutum + Mleczko
    assert.equal(rows.find((x) => x.id === "spolow").seen, "1")
    assert.equal(rows.find((x) => x.id === "spozero").seen, "1")       // Przechodzień 5 s: widziany, ale 0 spotkań
    assert.equal(rows.find((x) => x.id === "spozero").meet, "0/3")
    assert.equal(rows.find((x) => x.id === "spostoi").seen, "-")
    const z = S.changeRows(dane, lista)
    assert.deepEqual(z.map((x) => x.type).sort(), ["brak", "powrot", "zmiana"])
    assert.equal(z.find((x) => x.type === "zmiana").route, "trolle_edron → rook_raty_z8")
    assert.equal(z.find((x) => x.type === "zmiana").status, "wykonano")
    assert.equal(z.find((x) => x.type === "powrot").status, "tylko zapis")
    const u = S.avoidRows(dane, lista)
    assert.equal(u.length, 2)
    assert.equal(u.every((x) => x.leftSec > 0), true)
  })
})
