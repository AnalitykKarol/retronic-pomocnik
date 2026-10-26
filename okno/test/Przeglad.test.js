"use strict"

// Uruchom: node --test okno/test/*.test.js   (z katalogu repo bota)
// Przegląd, karty offline i „Ostatnio znane” (F2): czysta logika PrzegladModel.js na prawdziwym zrzucie `okno_api.py stan` (test/stan-przeglad.json,
// 7 instancji: 2 w grze z ostatnie:null, 5 offline, w tym Kolanosh zawieszony do terminu i Kutangen = rezerwa, bo zrzut sprzed pola `rola`; stany stracona/bank testowane na klonach). Czas w testach stały.

const { describe, it } = require("node:test")
const assert = require("node:assert/strict")
const fs = require("node:fs")
const path = require("node:path")
const P = require("../PrzegladModel.js")

const STAN = JSON.parse(fs.readFileSync(path.join(__dirname, "stan-przeglad.json"), "utf8"))
const NOW = new Date(1792691600 * 1000)
const by = (id) => STAN.instancje.find((i) => i.id === id)
const clone = (o) => JSON.parse(JSON.stringify(o))
const pad = (n) => (n < 10 ? "0" : "") + n
const hm = (s) => { const d = new Date(s * 1000); return pad(d.getHours()) + ":" + pad(d.getMinutes()) }

describe("czas", () => {
  it("dziś / wczoraj / starsze / brak", () => {
    const today = NOW.getTime() / 1000 - 600
    assert.equal(P.whenLabel(today, NOW), hm(today))
    const yest = NOW.getTime() / 1000 - 86400
    assert.equal(P.whenLabel(yest, NOW), "wczoraj " + hm(yest))
    assert.match(P.whenLabel(NOW.getTime() / 1000 - 5 * 86400, NOW), /^\d\d\.\d\d \d\d:\d\d$/)
    assert.equal(P.whenLabel(null, NOW), "—")
    assert.equal(P.whenLabel(undefined, NOW), "—")
  })
  it("spanLabel i doLabel", () => {
    assert.equal(P.spanLabel(10), "<1 min")
    assert.equal(P.spanLabel(38 * 60), "38 min")
    assert.equal(P.spanLabel(3600), "1 h")
    assert.equal(P.spanLabel(72 * 60), "1 h 12 min")
    assert.equal(P.spanLabel(null), "—")
    assert.equal(P.doLabel("2026-10-24 08:30"), "24.10 08:30")
  })
  it("plural", () => {
    assert.equal(P.plural(1, "a", "b", "c"), "a")
    assert.equal(P.plural(3, "a", "b", "c"), "b")
    assert.equal(P.plural(12, "a", "b", "c"), "c")
    assert.equal(P.plural(5, "a", "b", "c"), "c")
  })
})

describe("liczniki", () => {
  it("prawdziwy zrzut: 2 z 7 w grze, 2 boty, 2 zawieszone (w tym 1 rezerwa)", () => {
    const c = P.countersOf(STAN.instancje)
    assert.equal(c.total, 7)
    assert.equal(c.inGame, 2)
    assert.equal(c.bot, 2)
    assert.equal(c.suspended, 2)
    assert.equal(c.reserve, 1)
    assert.equal(c.offline, 5)
    assert.equal(P.navBadge(STAN.instancje), "2/7 w grze")
    assert.equal(P.suspendedNote(c), "w tym 2 zawieszone")
  })
  it("instancje test:true są widoczne w wierszach, ale poza sumami", () => {
    const list = clone(STAN.instancje)
    const t = clone(by("wydra")); t.id = "t1"; t.przeglad.test = true; t.przeglad.w_grze = true; t.przeglad.stan = "bot_dziala"; t.przeglad.exp_h = 999
    list.push(t)
    const c = P.countersOf(list)
    assert.equal(c.total, 7)
    assert.equal(c.inGame, 2)
    assert.equal(c.expH, 0)
    assert.equal(P.navBadge(list), "2/7 w grze")
    const rows = P.rowsOf(list, NOW)
    assert.equal(rows.length, 8)
    assert.equal(rows[7].test, true)
  })
  it("exp/h tylko z botów z liczbą", () => {
    const list = clone(STAN.instancje)
    by("odchyd") // brak w klonie? użyj klonu
    list.find((i) => i.id === "odchyd").przeglad.exp_h = 4200
    list.find((i) => i.id === "gebelish").przeglad.exp_h = 1000
    const c = P.countersOf(list)
    assert.equal(c.expH, 5200)
    assert.equal(c.expBots, 2)
    assert.equal(P.expBotsNote(c), "2 boty")
  })
  it("pusta lista nie wywala", () => {
    const c = P.countersOf([])
    assert.equal(c.total, 0)
    assert.equal(P.navBadge([]), "0/0 w grze")
    assert.deepEqual(P.groupsOf([], "wszystkie"), [])
  })
})

describe("grupy i filtry", () => {
  const rows = P.rowsOf(STAN.instancje, NOW)
  it("wszystkie: W GRZE (2) potem OFFLINE (5); domyślnie poziom ↓ (sortowanie 25.10), sortowanie „stan” trzyma dawną kolejność stanów", () => {
    const g = P.groupsOf(rows, "wszystkie")
    assert.deepEqual(g.map((x) => x.key + ":" + x.count), ["gra:2", "offline:5"])
    assert.deepEqual(g[0].rows.map((r) => r.nick), ["Geblish", "Odchyd"])
    assert.deepEqual(g[1].rows.map((r) => r.nick), ["Invincible", "Dawajkesh", "Wydra", "Kutangen", "Kolanosh"])
    const s = P.groupsOf(rows, "wszystkie", "stan")
    assert.deepEqual(s[1].rows.map((r) => r.stan), ["zawieszony", "zawieszony", "offline", "offline", "offline"])
  })
  it("w grze: tylko pierwsza grupa; z alarmem: wg alarm_24h/stan alarm", () => {
    assert.deepEqual(P.groupsOf(rows, "w grze").map((x) => x.key), ["gra"])
    const al = P.groupsOf(rows, "z alarmem")
    assert.deepEqual(al.map((x) => x.key), ["offline"])
    assert.deepEqual(al[0].rows.map((r) => r.nick).sort(), ["Dawajkesh", "Kolanosh"])
  })
  it("liczniki filtrów", () => {
    assert.deepEqual(P.filterCounts(rows), { "wszystkie": 7, "w grze": 2, "z alarmem": 2, "stracone": 0 })
  })
  it("stracone: tylko postacie z `stracony`, także stracona z otwartym klientem; licznik chipa", () => {
    const inst = clone(STAN.instancje)
    const d = inst.find((i) => i.id === "dawajkesh")
    Object.assign(d.przeglad, { stan: "zawieszony", stracony: true })
    const g = inst.find((i) => i.id === "gebelish")
    Object.assign(g.przeglad, { stan: "karol_gra", w_grze: true, stracony: true })
    const r = P.rowsOf(inst, NOW)
    const st = P.groupsOf(r, "stracone")
    assert.deepEqual(st.map((x) => x.key + ":" + x.count), ["offline:2"])
    assert.deepEqual(st[0].rows.map((x) => x.nick).sort(), ["Dawajkesh", "Geblish"])
    assert.equal(P.filterCounts(r)["stracone"], 2)
    assert.equal(P.filterCounts(r)["w grze"], 1)
    assert.ok(P.FILTERS.includes("stracone"))
  })
  it("ukryj stracone (25.10): „wszystkie”, „w grze” i „z alarmem” ich nie pokazują, licznik „wszystkie” bez straconych, chip „stracone” je pokazuje", () => {
    const inst = clone(STAN.instancje)
    const d = inst.find((i) => i.id === "dawajkesh")                  // offline z alarmem 24 h w zrzucie: po utracie nie ma go także w „z alarmem”
    Object.assign(d.przeglad, { stan: "zawieszony", stracony: true })
    const g = inst.find((i) => i.id === "gebelish")                   // stracona z otwartym klientem: nie w „w grze”
    Object.assign(g.przeglad, { stan: "karol_gra", w_grze: true, stracony: true })
    const r = P.rowsOf(inst, NOW)
    const ids = (f) => P.groupsOf(r, f).flatMap((x) => x.rows.map((y) => y.id))
    assert.equal(ids("wszystkie").length, 5)
    assert.ok(!ids("wszystkie").includes("dawajkesh") && !ids("wszystkie").includes("gebelish"))
    assert.ok(!ids("w grze").includes("gebelish"))
    assert.ok(!ids("z alarmem").includes("dawajkesh"))
    assert.deepEqual(ids("stracone").sort(), ["dawajkesh", "gebelish"])
    const c = P.filterCounts(r)
    assert.equal(c["wszystkie"], 5)
    assert.equal(c["stracone"], 2)
    assert.equal(c["wszystkie"] + c["stracone"], r.length)
    assert.equal(c["w grze"], ids("w grze").length)
    assert.equal(c["z alarmem"], ids("z alarmem").length)
    // liczniki u góry spójne z tabelą: total = widoczne, stracone osobno
    const k = P.countersOf(inst)
    assert.equal(k.total, 5)
    assert.equal(k.lost, 2)
    assert.equal(P.navBadge(inst), k.inGame + "/5 w grze")
  })
  it("wszystkie stracone: „wszystkie” puste, chip „stracone” pokazuje komplet", () => {
    const inst = clone(STAN.instancje)
    inst.forEach((i) => { i.przeglad = Object.assign({}, i.przeglad, { stracony: true }) })
    const r = P.rowsOf(inst, NOW)
    assert.deepEqual(P.groupsOf(r, "wszystkie"), [])
    assert.deepEqual(P.filterCounts(r), { "wszystkie": 0, "w grze": 0, "z alarmem": 0, "stracone": inst.length })
  })
})

describe("lista postaci w pasku bocznym: stracone ukryte", () => {
  const withLost = (ids) => {
    const inst = clone(STAN.instancje)
    inst.forEach((i) => { if (ids.includes(i.id)) i.przeglad = Object.assign({}, i.przeglad, { stracony: true }) })
    return inst
  }
  it("visibleInstances: bez straconych, a z showLost wszystkie; lostCount", () => {
    const inst = withLost(["dawajkesh", "gebelish"])
    assert.equal(inst.length, 7)
    assert.deepEqual(P.visibleInstances(inst, false).map((i) => i.id), inst.map((i) => i.id).filter((id) => id !== "dawajkesh" && id !== "gebelish"))
    assert.equal(P.visibleInstances(inst, true).length, 7)
    assert.equal(P.lostCount(inst), 2)
    assert.equal(P.lostCount(clone(STAN.instancje)), 0)
    assert.equal(P.visibleInstances(clone(STAN.instancje), false).length, 7)
  })
  it("selectionAfter: wybór zostaje, gdy widoczny; stracona/ukryta spada na pierwszą widoczną; showLost trzyma straconą", () => {
    const inst = withLost(["dawajkesh"])
    const first = P.visibleInstances(inst, false)[0].id
    assert.equal(P.selectionAfter(inst, "gebelish", false), "gebelish")
    assert.equal(P.selectionAfter(inst, "dawajkesh", false), first)
    assert.equal(P.selectionAfter(inst, "dawajkesh", true), "dawajkesh")
    assert.equal(P.selectionAfter(inst, "nie-ma-takiej", false), first)
  })
  it("selectionAfter: same stracone, nic widocznego: zostaje stary wybór, a nieznany daje pierwszą instancję (bez wyjątku)", () => {
    const inst = withLost(STAN.instancje.map((i) => i.id))
    assert.equal(P.visibleInstances(inst, false).length, 0)
    assert.equal(P.selectionAfter(inst, "gebelish", false), "gebelish")
    assert.equal(P.selectionAfter(inst, "nie-ma-takiej", false), inst[0].id)
    assert.equal(P.selectionAfter([], "x", false), "x")
  })
})

describe("wiersz", () => {
  it("w grze z ostatnie:null: dane na żywo, braki jako —/?", () => {
    const r = P.rowOf(by("gebelish"), NOW)
    assert.equal(r.inGame, true)
    assert.equal(r.level, 8)
    assert.equal(r.levelPct, 26)
    assert.equal(r.ml, "?")
    assert.equal(r.hp.live, true)
    assert.equal(r.hp.max, 185)
    assert.equal(r.mana.frac, 11 / 35)
    assert.equal(r.where, "32339, 32259, z8")
    assert.equal(r.zabH, null)
    assert.equal(r.expH, null)
    assert.equal(r.alarm, null)
    assert.equal(r.spotTime.main, "—")
    assert.equal(r.supervision.text, "nie · profil")
  })
  it("offline Kolanosh: ostatnio znane, alarm świeży, zawieszony do terminu", () => {
    const r = P.rowOf(by("kolanoth"), NOW)
    assert.equal(r.inGame, false)
    assert.equal(r.level, 10)
    assert.equal(r.levelPct, 13)
    assert.equal(r.hp.text, "max ~188")
    assert.equal(r.mana.text, "max 95")
    assert.equal(r.ml, "?")
    assert.equal(r.zabH, null)
    assert.equal(r.pill.label, "zawieszony")
    assert.equal(r.since, "do 24.10 08:30")
    assert.equal(r.alarm.tone, "bad")
    assert.match(r.alarm.text, /^wyprawa: utkniecie/)
    assert.equal(r.spotTime.pre, "ostatnio")
    assert.equal(r.spotTime.main, P.whenLabel(1792665042.3, NOW))
    assert.equal(r.supervision.text, "do 24.10 08:30")
    assert.match(r.where, /^33121, 31756, z9$/)
  })
  it("Kutangen: rezerwa, nie „zawieszony do …”", () => {
    const i = by("kutangen")
    assert.equal(P.isReserve(i), true)
    assert.equal(P.isReserve(by("kolanoth")), false)
    const r = P.rowOf(i, NOW)
    assert.deepEqual(r.pill, { label: "rezerwa", tone: "dim" })
    assert.equal(r.reserve, true)
    assert.equal(r.since, "")
    assert.equal(P.cardOffline(i, NOW).right.text, "rezerwa")
    assert.equal(P.cardOffline(by("kolanoth"), NOW).right.text, "do 24.10")
    assert.equal(r.alarm.tone, "dim")
  })
  it("Dawajkesh stracony: „stracona”, nie rezerwa, nie bank i nie w licznikach zawieszonych", () => {
    const i = clone(by("dawajkesh"))
    i.przeglad.stan = "zawieszony"
    i.przeglad.nadzor = { aktywny: false, powod: "postać poza nadzorem (nadzor: false)", do: null, zrodlo: "profil" }
    i.przeglad.stracony = true
    i.przeglad.rola = null
    assert.equal(P.isLost(i), true)
    assert.equal(P.isReserve(i), false)
    assert.equal(P.isBank(i), false)
    assert.equal(P.isLost(by("kutangen")), false)
    const r = P.rowOf(i, NOW)
    assert.deepEqual(r.pill, { label: "stracona", tone: "bad" })
    assert.equal(r.lost, true)
    assert.equal(r.reserve, false)
    assert.deepEqual(r.supervision, { text: "stracona", tone: "bad" })
    assert.equal(P.cardOffline(i, NOW).right.text, "stracona")
    const nadzor = P.lastKnown(i, NOW).cols[2].rows.find((x) => x.k === "nadzór")
    assert.match(nadzor.v, /^stracona/)
    const c = P.countersOf([i, by("kutangen")])
    assert.equal(c.suspended, 1)
    assert.equal(c.reserve, 1)
    assert.equal(c.lost, 1)
  })
  it("Invincible stracona (klient wciąż otwarty, bot stoi, STOP ręczny = API „karol_gra”): „stracona”, nie „Karol gra”, nie rezerwa", () => {
    // kształt z prawdziwego `okno_api.py stan` 24.10 po 14:11: stan karol_gra, w_grze true, stracony true, nadzor false z profilu
    const i = clone(by("invincible"))
    i.gra = true; i.sesja = true; i.bot = false; i.klasa = "stop"
    Object.assign(i.przeglad, {
      stan: "karol_gra", w_grze: true, stracony: true, rola: null,
      nadzor: { aktywny: false, powod: "postać poza nadzorem (nadzor: false)", do: null, zrodlo: "profil" },
      stop: { auto: true, reczny: true }
    })
    assert.equal(P.isLost(i), true)
    assert.equal(P.isReserve(i), false)
    assert.equal(P.isOffline(i), true)
    assert.equal(P.cardMode(i), "offline")
    const r = P.rowOf(i, NOW)
    assert.deepEqual(r.pill, { label: "stracona", tone: "bad" })
    assert.equal(r.inGame, false)
    assert.equal(r.dot, "dim2")
    assert.equal(r.since, "")
    assert.equal(r.zabH, null)
    assert.deepEqual(r.supervision, { text: "stracona", tone: "bad" })
    assert.equal(P.cardOffline(i, NOW).right.text, "stracona")
    assert.equal(P.cardSubtitleText(i, "x"), "postać stracona")
    assert.equal(P.cardSubtitleTone(i), "bad")
    assert.equal(P.lastKnownVisible(i), true)
    const c = P.countersOf([i, by("gebelish"), by("odchyd")])
    assert.equal(c.lost, 1)
    assert.equal(c.karol, 0)
    assert.equal(c.inGame, 2)
    assert.equal(c.bot, 2)
    assert.equal(c.offline, 0)       // stracone są ukryte (25.10): poza total i offline, tylko c.lost
    assert.equal(c.total, 2)
    assert.equal(P.navBadge([i, by("gebelish"), by("odchyd")]), "2/2 w grze")
    const grupy = P.groupsOf(P.rowsOf([i, by("gebelish")], NOW), "wszystkie")
    assert.deepEqual(grupy.map((g) => g.key + ":" + g.rows.map((x) => x.id).join(",")), ["gra:gebelish"])
    const naZadanie = P.groupsOf(P.rowsOf([i, by("gebelish")], NOW), "stracone")
    assert.deepEqual(naZadanie.map((g) => g.key + ":" + g.rows.map((x) => x.id).join(",")), ["offline:invincible"])
  })
  it("stracona także z zamkniętym klientem (stan zawieszony/offline z API) i bez klucza `rola`", () => {
    for (const stan of ["zawieszony", "offline"]) {
      const i = clone(by("invincible"))
      Object.assign(i.przeglad, { stan, stracony: true })
      delete i.przeglad.rola
      assert.equal(P.pillOf(i).label, "stracona", stan)
      assert.equal(P.isReserve(i), false, stan)
    }
  })
  it("Kutangen bank (profil `rola: bank`): „bank”, nie rezerwa i nie zawieszony", () => {
    const i = clone(by("kutangen"))
    i.przeglad.rola = "bank"
    i.przeglad.stracony = false
    assert.equal(P.isBank(i), true)
    assert.equal(P.isReserve(i), false)
    assert.equal(P.isLost(i), false)
    const r = P.rowOf(i, NOW)
    assert.deepEqual(r.pill, { label: "bank", tone: "blue" })
    assert.equal(r.bank, true)
    assert.equal(r.reserve, false)
    assert.deepEqual(r.supervision, { text: "bank", tone: "blue" })
    assert.deepEqual(P.cardOffline(i, NOW).right, { text: "bank", tone: "blue" })
    const nadzor = P.lastKnown(i, NOW).cols[2].rows.find((x) => x.k === "nadzór")
    assert.match(nadzor.v, /^bank/)
    const c = P.countersOf([i, by("kolanoth")])
    assert.equal(c.bank, 1)
    assert.equal(c.reserve, 0)
    assert.equal(c.suspended, 1)        // tylko Kolanosh (zawieszony do terminu)
    assert.equal(c.offline, 2)
    assert.equal(P.suspendedNote(c), "w tym 1 zawieszona")
  })
  it("bank w grze zachowuje żywy stan (alarm/bot), stracona ma pierwszeństwo przed rolą bank", () => {
    const w = clone(by("gebelish"))
    w.przeglad.rola = "bank"
    assert.equal(P.pillOf(w).label, "bot działa")
    const l = clone(by("kutangen"))
    l.przeglad.rola = "bank"
    l.przeglad.stracony = true
    assert.equal(P.isBank(l), false)
    assert.equal(P.pillOf(l).label, "stracona")
  })
  it("zwykła rezerwa (zawieszony bez terminu, bez roli, bez `stracony`) dalej „rezerwa”; rola inna niż bank nie zmienia stanu", () => {
    const i = clone(by("kutangen"))
    i.przeglad.rola = null
    i.przeglad.stracony = false
    assert.equal(P.isReserve(i), true)
    assert.deepEqual(P.pillOf(i), { label: "rezerwa", tone: "dim" })
    assert.deepEqual(P.supervisionOf(i), { text: "nie · profil", tone: "dim" })
    assert.equal(P.cardOffline(i, NOW).right.text, "rezerwa")
    i.przeglad.rola = "sklep"
    assert.equal(P.isBank(i), false)
    assert.equal(P.pillOf(i).label, "rezerwa")
  })
  it("Wydra: miasto i depo", () => {
    const r = P.rowOf(by("wydra"), NOW)
    assert.equal(r.where, "Thais · depo z7")
    assert.equal(r.pill.label, "offline")
    assert.equal(r.supervision.text, "wstrzymany · STOP ręczny")
  })
  it("brak przeglądu/ostatnie nie wywala", () => {
    const r = P.rowOf({ id: "x", nick: "X" }, NOW)
    assert.equal(r.stan, "offline")
    assert.equal(r.level, null)
    assert.equal(r.where, "—")
    assert.equal(r.hp.text, "—")
    assert.equal(P.cardMode({ id: "x" }), "legacy")
  })
  it("karol_gra ma cyan, nigdy bad/warn", () => {
    const i = clone(by("wydra")); i.przeglad.stan = "karol_gra"; i.przeglad.w_grze = true
    assert.equal(P.rowOf(i, NOW).pill.tone, "cyan")
    assert.equal(P.rowOf(i, NOW).dot, "cyan")
    assert.equal(P.cardSubtitleText(i, "mapa"), "Karol gra · bot stoi")
    assert.equal(P.cardSubtitleTone(i), "cyan")
  })
})

describe("karta offline", () => {
  it("Kolanosh: gdzie, kiedy, HP/MP, ML, powód", () => {
    const c = P.cardOffline(by("kolanoth"), NOW)
    assert.equal(c.place, "⌖ z9 · 33121,31756")
    assert.equal(c.when, P.whenLabel(1792665042.3, NOW))
    assert.equal(c.hp, "188")
    assert.equal(c.mp, "95")
    assert.equal(c.ml, "?")
    assert.equal(c.mlKnown, false)
    assert.equal(c.right.tone, "mag")
  })
  it("Wydra: miasto i depo; STOP ręczny", () => {
    const c = P.cardOffline(by("wydra"), NOW)
    assert.equal(c.place, "⌂ Thais · depo z7")
    assert.equal(c.right.text, "STOP ręczny")
  })
  it("ostatnie:null nie wywala", () => {
    const i = clone(by("wydra")); i.ostatnie = null
    const c = P.cardOffline(i, NOW)
    assert.equal(c.place, "brak ostatnich danych")
    assert.equal(c.hp, "—")
    assert.equal(c.when, "")
  })
  it("ML z wartością", () => {
    const i = clone(by("wydra")); i.ostatnie.ml = 31
    assert.equal(P.cardOffline(i, NOW).ml, "31")
    assert.equal(P.cardOffline(i, NOW).mlKnown, true)
  })
})

describe("procent ML w tabeli i na karcie", () => {
  const withMl = (id, extra) => { const i = clone(by(id)); i.ostatnie = Object.assign({}, i.ostatnie || {}, { ml: 31, ml_zrodlo: "pamiec" }, extra); return i }
  it("postać w grze: wiersz tabeli ma mlPct z ostatnie.ml_proc", () => {
    const i = withMl("gebelish", { ml_proc: 42.4 })
    assert.equal(i.gra, true)
    const r = P.rowOf(i, NOW)
    assert.equal(r.ml, "31")
    assert.equal(r.mlPct, 42)
  })
  it("postać offline: wiersz i karta mają mlPct", () => {
    const i = withMl("wydra", { ml_proc: 7.6 })
    assert.equal(P.rowOf(i, NOW).mlPct, 8)
    assert.equal(P.cardOffline(i, NOW).mlPct, 8)
  })
  it("brak/nieprawidłowy ml_proc, wpis ręczny, brak ML: mlPct = null", () => {
    for (const bad of [null, undefined, "x", NaN, -1, 101]) assert.equal(P.rowOf(withMl("gebelish", { ml_proc: bad }), NOW).mlPct, null, String(bad))
    assert.equal(P.rowOf(withMl("gebelish", { ml_proc: 42, ml_zrodlo: "reczny" }), NOW).mlPct, null)
    assert.equal(P.rowOf(withMl("gebelish", { ml_proc: 42, ml: null }), NOW).mlPct, null)
    assert.equal(P.rowOf(clone(by("gebelish")), NOW).mlPct, null)   // ostatnie: null
    assert.equal(P.rowOf(clone(by("gebelish")), NOW).ml, "?")
  })
})

describe("Ostatnio znane", () => {
  it("widoczny tylko offline i nie dla głównej", () => {
    assert.equal(P.lastKnownVisible(by("kolanoth")), true)
    assert.equal(P.lastKnownVisible(by("gebelish")), false)
    assert.equal(P.lastKnownVisible({ id: "", przeglad: {} }), false)
    const g = clone(by("kolanoth")); g.gra = true
    assert.equal(P.lastKnownVisible(g), false)
  })
  it("Kolanosh: statystyki, kolumny, źródło", () => {
    const k = P.lastKnown(by("kolanoth"), NOW)
    assert.equal(k.empty, false)
    const st = Object.fromEntries(k.stats.map((s) => [s.key, s]))
    assert.equal(st.level.value, "10")
    assert.equal(st.level.small, "13%")
    assert.equal(st.ml.value, "?")
    assert.equal(st.ml.dim, true)
    assert.equal(st.hp.value, "~188")
    assert.equal(st.mana.value, "95")
    assert.equal(st.exp.value, "9\u00a0769")
    assert.match(st.exp.small, /^do 11: /)
    assert.equal(st.gold.value, "13")
    assert.equal(k.cols.length, 3)
    const sess = Object.fromEntries(k.cols[1].rows.map((r) => [r.k, r]))
    assert.equal(sess.zabicia.v, "9")
    assert.equal(sess.exp.v, "+180")
    assert.equal(sess.koniec.v, "bot zniknął bez zapisu końca")
    assert.equal(sess["stan bota"].v, "WYPAD")
    assert.match(k.source, /^źródło: instancje\/kolanoth\/ostatnie\.json · zapisane \d\d\.\d\d \d\d:\d\d:\d\d przez uzupełnienie z telemetrii \(backfill\) · przybliżone: max_hp$/)
    const nadzor = k.cols[2].rows.find((r) => r.k === "nadzór")
    assert.equal(nadzor.v, "zawieszony do 24.10 08:30")
  })
  it("ML z pamięci pokazuje procent do następnego ML jak procent levelu", () => {
    const mk = (extra) => { const i = clone(by("kolanoth")); Object.assign(i.ostatnie, { ml: 31, ml_zrodlo: "pamiec" }, extra); return Object.fromEntries(P.lastKnown(i, NOW).stats.map((s) => [s.key, s])).ml }
    const ok = mk({ ml_proc: 42.4 })
    assert.equal(ok.value, "31")
    assert.equal(ok.small, "42%")
    assert.equal(ok.bar, 0.42)
    assert.equal(mk({ ml_proc: 0 }).small, "0%")
    assert.equal(mk({ ml_proc: 100 }).small, "100%")
    // brak albo nieprawidłowy procent: jak dotąd (pusty podpis, bez paska)
    for (const bad of [null, undefined, "x", NaN, -1, 101]) {
      const m = mk({ ml_proc: bad })
      assert.equal(m.small, "", String(bad))
      assert.equal(m.bar, -1, String(bad))
    }
    // wpis ręczny zostaje bez zmian
    const r = mk({ ml_zrodlo: "reczny", ml_proc: 42.4 })
    assert.equal(r.small, "wpis ręczny")
    assert.equal(r.bar, -1)
  })
  it("Kutangen: nadzór = rezerwa", () => {
    const k = P.lastKnown(by("kutangen"), NOW)
    const nadzor = k.cols[2].rows.find((r) => r.k === "nadzór")
    assert.match(nadzor.v, /^rezerwa/)
  })
  it("ostatnie:null daje pusty blok z objaśnieniem, bez wyjątku", () => {
    const i = clone(by("kolanoth")); i.ostatnie = null
    const k = P.lastKnown(i, NOW)
    assert.equal(k.empty, true)
    assert.deepEqual(k.stats, [])
    assert.match(k.sub, /brak zapisanych danych/)
  })
  it("expToNext zgodne z rdzeniem (L10->11)", () => {
    assert.equal(Math.round(P.expToNext(10)), 50 * (11 ** 3 - 6 * 121 + 17 * 11 - 12) / 3)
  })
})

describe("tempo sesji postaci (widok Sesja gry)", () => {
  it("bot w grze: exp/h i zab/h z przeglad, tekst z grupowaniem cyfr", () => {
    const i = clone(by("gebelish")); i.przeglad.exp_h = 12345; i.przeglad.zab_h = 101.4
    const r = P.sessionRate(i)
    assert.equal(r.expH, 12345)
    assert.equal(r.expText, "12\u00a0345")
    assert.equal(r.zabText, "101")
  })
  it("zgodne z kolumnami Przeglądu (rowOf) dla każdej instancji zrzutu", () => {
    for (const i of STAN.instancje) {
      const row = P.rowOf(i, NOW)
      const r = P.sessionRate(i)
      assert.equal(r.expH, row.expH, i.id)
      assert.equal(r.zabH, row.zabH, i.id)
    }
  })
  it("null / offline / zawieszona / brak przeglad = „—”", () => {
    const i = clone(by("gebelish")); i.przeglad.exp_h = null; i.przeglad.zab_h = null
    assert.equal(P.sessionRate(i).expText, "—")
    assert.equal(P.sessionRate(i).zabText, "—")
    const off = clone(by("gebelish")); off.przeglad.w_grze = false; off.przeglad.stan = "offline"; off.przeglad.exp_h = 500
    assert.equal(P.sessionRate(off).expText, "—")
    assert.equal(P.sessionRate(by("kolanoth")).expText, "—")
    assert.equal(P.sessionRate({ id: "x" }).zabText, "—")
    assert.equal(P.sessionRate(null).expText, "—")
  })
})

describe("sortowanie (25.10): domyślnie poziom ↓, wybór sortowania", () => {
  const R = (id, nick, over) => Object.assign({ id, nick, level: null, levelPct: null, expH: null, order: 1, stan: "bot_dziala", hp: { live: false, frac: 0 }, lastT: null, lost: false, inGame: true, alarmFlag: false }, over || {})
  const ids = (rows) => rows.map((r) => r.id)

  it("domyślnie (bez klucza, nieznany klucz) i „level”: najwyższy poziom pierwszy", () => {
    const rows = [R("a", "A", { level: 8 }), R("b", "B", { level: 13 }), R("c", "C", { level: 10 })]
    assert.equal(P.DEFAULT_SORT, "level")
    assert.deepEqual(ids(P.sortRows(rows)), ["b", "c", "a"])
    assert.deepEqual(ids(P.sortRows(rows, "level")), ["b", "c", "a"])
    assert.deepEqual(ids(P.sortRows(rows, "nie-ma-takiego")), ["b", "c", "a"])
    assert.deepEqual(P.SORTS.map((s) => s.key), ["level", "nazwa", "exp_h", "stan", "hp", "ostatnio"])
  })
  it("remis poziomu: wyższy % do następnego poziomu, potem nazwa alfabetycznie (bez względu na wielkość liter), potem id", () => {
    const rows = [R("n1", "Zeta", { level: 10, levelPct: 40 }), R("n2", "alfa", { level: 10, levelPct: 40 }), R("n3", "Beta", { level: 10, levelPct: 84 }),
                  R("n4", "Gama", { level: 10, levelPct: null }), R("n5", "Alfa", { level: 10, levelPct: 40, id: "n0" })]
    assert.deepEqual(ids(P.sortRows(rows, "level")), ["n3", "n0", "n2", "n1", "n4"])      // 84% / 40% (Alfa id n0 < alfa id n2 przy równym tekście) / 40% Zeta / brak % na końcu remisu
  })
  it("brak poziomu (null, 0) zawsze na końcu, w sortowaniu po poziomie i po innych kluczach z tym samym remisem", () => {
    const rows = [R("x", "X"), R("l", "L", { level: 3 }), R("z", "Z", { level: 0 }), R("h", "H", { level: 20 })]
    assert.deepEqual(ids(P.sortRows(rows, "level")), ["h", "l", "x", "z"])                 // brak: dalej wg nazwy
    assert.deepEqual(ids(P.sortRows(rows, "stan")), ["h", "l", "x", "z"])                   // ten sam stan: remis rozstrzyga poziom, brak na końcu
  })
  it("nazwa A→Z (bez względu na wielkość liter), remis -> wyższy poziom", () => {
    const rows = [R("1", "kolanoth", { level: 10 }), R("2", "Gebelish", { level: 13 }), R("3", "adam", { level: 1 }), R("4", "Adam", { level: 5 })]
    assert.deepEqual(ids(P.sortRows(rows, "nazwa")), ["4", "3", "2", "1"])
  })
  it("nazwa: polskie litery jak podstawowe (Łukasz po Leonie i przed Marią, Żaba jak Zaba przed Zosią)", () => {
    const rows = [R("1", "Maria"), R("2", "Łukasz"), R("3", "Leon"), R("4", "Żaba"), R("5", "Zosia"), R("6", "Ćma"), R("7", "Cezar")]
    assert.deepEqual(ids(P.sortRows(rows, "nazwa")), ["7", "6", "3", "2", "1", "4", "5"])      // Cezar, Ćma, Leon, Łukasz, Maria, Żaba, Zosia
  })
  it("exp/h ↓: największe pierwsze, brak (null) na końcu, remis -> poziom", () => {
    const rows = [R("a", "A", { expH: 1200, level: 5 }), R("b", "B", { expH: null, level: 99 }), R("c", "C", { expH: 4500, level: 1 }), R("d", "D", { expH: 1200, level: 9 })]
    assert.deepEqual(ids(P.sortRows(rows, "exp_h")), ["c", "d", "a", "b"])
    assert.deepEqual(ids(P.sortRows([R("n", "N", { expH: null }), R("o", "O", { expH: 0 })], "exp_h")), ["o", "n"])      // 0 to liczba, null to brak
  })
  it("stan: alarm, bot działa, Karol gra, zatrzymany, zawieszony, offline; remis -> poziom", () => {
    const rows = [R("off", "Off", { order: 5, stan: "offline", level: 50 }), R("bot", "Bot", { order: 1, level: 5 }), R("al", "Al", { order: 0, stan: "alarm", level: 1 }),
                  R("zaw", "Zaw", { order: 4, stan: "zawieszony", level: 9 }), R("bot2", "Bot2", { order: 1, level: 7 })]
    assert.deepEqual(ids(P.sortRows(rows, "stan")), ["al", "bot2", "bot", "zaw", "off"])
  })
  it("HP% ↑: najniższe pierwsze, bez odczytu na żywo (offline) na końcu", () => {
    const hp = (f) => ({ live: true, frac: f })
    const rows = [R("a", "A", { hp: hp(0.9), level: 1 }), R("b", "B", { level: 99 }), R("c", "C", { hp: hp(0.25), level: 1 }), R("d", "D", { hp: hp(0.9), level: 7 })]
    assert.deepEqual(ids(P.sortRows(rows, "hp")), ["c", "d", "a", "b"])
  })
  it("ostatnio ↓: najświeższa aktywność pierwsza, brak czasu na końcu", () => {
    const rows = [R("a", "A", { lastT: 100 }), R("b", "B"), R("c", "C", { lastT: 900 }), R("d", "D", { lastT: 500 })]
    assert.deepEqual(ids(P.sortRows(rows, "ostatnio")), ["c", "d", "a", "b"])
  })
  it("stabilność i czystość: równe klucze zachowują kolejność wejściową, wejście nie jest zmieniane", () => {
    const a = { id: "s", nick: "Sam", level: 5 }
    const b = { id: "s", nick: "Sam", level: 5 }      // identyczne w każdym kluczu: rozstrzyga kolejność wejściowa
    const rows = [R("s", "Sam", a), R("s", "Sam", b), R("t", "Tom", { level: 5 })]
    const copy = rows.slice()
    for (const k of P.SORTS.map((s) => s.key)) {
      const out = P.sortRows(rows, k)
      assert.equal(out.length, 3)
      assert.ok(out.indexOf(rows[0]) < out.indexOf(rows[1]), "stabilnie przy kluczu " + k)
    }
    assert.deepEqual(rows, copy)
    assert.equal(P.sortRows(rows, "level") === rows, false)
    assert.deepEqual(P.sortRows([], "level"), [])
  })
  it("validSort: znane klucze (z białymi znakami z pliku), reszta null", () => {
    assert.equal(P.validSort("nazwa\n"), "nazwa")
    assert.equal(P.validSort(" exp_h "), "exp_h")
    assert.equal(P.validSort("zly"), null)
    assert.equal(P.validSort(""), null)
    assert.equal(P.validSort(undefined), null)
    assert.equal(P.validSort(null), null)
  })

  // ---- na prawdziwym zrzucie okno_api stan (7 instancji; poziomy: Invincible 15, Dawajkesh 13, Wydra 12, Kutangen 10/84%, Kolanosh 10/13%, Geblish 8, Odchyd 5)
  it("zrzut: domyślnie poziom ↓ w każdej grupie, remis 10 lvl rozstrzyga %; w grze 8 i 5", () => {
    const rows = P.rowsOf(STAN.instancje, NOW)
    const g = P.groupsOf(rows, "wszystkie")
    assert.deepEqual(g[0].rows.map((r) => r.id), ["gebelish", "odchyd"])
    assert.deepEqual(g[1].rows.map((r) => r.id), ["invincible", "dawajkesh", "wydra", "kutangen", "kolanoth"])
    assert.deepEqual(ids(P.sortRows(rows)).slice(0, 3), ["gebelish", "odchyd", "invincible"])     // 26.10: w grze pierwsze, potem poziom
  })
  it("zrzut: każda opcja sortuje grupy po swojemu (nazwa, exp/h, stan, HP%, ostatnio)", () => {
    const inst = clone(STAN.instancje)
    inst.find((i) => i.id === "gebelish").przeglad.exp_h = 800
    inst.find((i) => i.id === "odchyd").przeglad.exp_h = 2500
    const rows = P.rowsOf(inst, NOW)
    const first = (key) => P.groupsOf(rows, "wszystkie", key).map((g) => g.rows.map((r) => r.id))
    assert.deepEqual(first("nazwa")[1], ["dawajkesh", "invincible", "kolanoth", "kutangen", "wydra"])
    assert.deepEqual(first("exp_h")[0], ["odchyd", "gebelish"])
    assert.deepEqual(first("stan")[1], ["kutangen", "kolanoth", "invincible", "dawajkesh", "wydra"])      // zawieszeni przed offline, remis 10 lvl: wyższy %
    assert.deepEqual(first("ostatnio")[1], ["wydra", "invincible", "dawajkesh", "kolanoth", "kutangen"])
    assert.deepEqual(first("hp")[0], ["gebelish", "odchyd"])                                              // oboje 100% HP: remis rozstrzyga poziom
    assert.deepEqual(first("hp")[1], ["invincible", "dawajkesh", "wydra", "kutangen", "kolanoth"])     // offline bez HP na żywo: wg poziomu
  })
  it("zgodność z filtrami i straconymi: sortowanie działa na tym, co przepuszcza filtr; stracone ukryte też przy każdym sortowaniu", () => {
    const inst = clone(STAN.instancje)
    Object.assign(inst.find((i) => i.id === "invincible").przeglad, { stracony: true })     // najwyższy poziom, ale stracony
    const rows = P.rowsOf(inst, NOW)
    for (const k of P.SORTS.map((s) => s.key)) {
      const all = P.groupsOf(rows, "wszystkie", k).flatMap((g) => g.rows.map((r) => r.id))
      assert.equal(all.length, 6, k)
      assert.ok(!all.includes("invincible"), k)
      assert.deepEqual(P.groupsOf(rows, "stracone", k).flatMap((g) => g.rows.map((r) => r.id)), ["invincible"], k)
      assert.deepEqual(P.groupsOf(rows, "w grze", k).flatMap((g) => g.rows.map((r) => r.id)).sort(), ["gebelish", "odchyd"], k)
    }
    assert.deepEqual(P.groupsOf(rows, "wszystkie", "level")[1].rows.map((r) => r.id), ["dawajkesh", "wydra", "kutangen", "kolanoth"])
    assert.deepEqual(P.groupsOf(rows, "z alarmem", "level").flatMap((g) => g.rows.map((r) => r.id)), ["dawajkesh", "kolanoth"])
  })
  it("lista w pasku bocznym: sortInstances = ta sama kolejność co wiersze, widoczne bez straconych, wejście nietknięte", () => {
    const inst = clone(STAN.instancje)
    Object.assign(inst.find((i) => i.id === "invincible").przeglad, { stracony: true })
    const before = inst.map((i) => i.id)
    const vis = P.visibleInstances(inst, false)
    const side = P.sortInstances(vis, "level", NOW).map((i) => i.id)
    assert.deepEqual(side, ["gebelish", "odchyd", "dawajkesh", "wydra", "kutangen", "kolanoth"])     // 26.10: w grze pierwsze, potem poziom
    assert.deepEqual(inst.map((i) => i.id), before)
    assert.deepEqual(P.sortInstances(vis, "nazwa", NOW).map((i) => i.id), ["dawajkesh", "gebelish", "kolanoth", "kutangen", "odchyd", "wydra"])
    assert.deepEqual(P.sortInstances(P.visibleInstances(inst, true), "level", NOW).map((i) => i.id).slice(0, 3), ["gebelish", "odchyd", "invincible"])     // showLost: stracona wraca, wśród wylogowanych nadal wg poziomu
  })
  it("26.10: domyślne sortowanie stawia postacie w grze przed wylogowanymi, w obu grupach poziom ↓; inne klucze bez zmian", () => {
    const inst = clone(STAN.instancje)
    const rows = P.rowsOf(inst, NOW)
    const sorted = P.sortRows(rows, "level")
    const flags = sorted.map((r) => r.inGame)
    assert.ok(flags.indexOf(false) === -1 || flags.lastIndexOf(true) < flags.indexOf(false), "najpierw wszystkie w grze")
    for (const g of [true, false]) {
      const lv = sorted.filter((r) => r.inGame === g).map((r) => r.level).filter((x) => x != null)
      assert.deepEqual(lv, lv.slice().sort((x, y) => y - x))
    }
    assert.deepEqual(P.sortRows(rows, "nazwa").map((r) => r.id), ["dawajkesh", "gebelish", "invincible", "kolanoth", "kutangen", "odchyd", "wydra"])
  })
  it("selectionAfter nie zależy od sortowania: spadek wyboru nadal na pierwszą widoczną w kolejności instancji", () => {
    const inst = clone(STAN.instancje)
    Object.assign(inst.find((i) => i.id === "invincible").przeglad, { stracony: true })
    assert.equal(P.selectionAfter(inst, "invincible", false), P.visibleInstances(inst, false)[0].id)
    assert.equal(P.selectionAfter(inst, "wydra", false), "wydra")
    assert.equal(P.selectionAfter(inst, "invincible", true), "invincible")
  })
})
