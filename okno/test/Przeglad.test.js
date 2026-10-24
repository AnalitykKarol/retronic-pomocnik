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
  it("wszystkie: W GRZE (2) potem OFFLINE (5), sort stan->nick", () => {
    const g = P.groupsOf(rows, "wszystkie")
    assert.deepEqual(g.map((x) => x.key + ":" + x.count), ["gra:2", "offline:5"])
    assert.deepEqual(g[0].rows.map((r) => r.nick), ["Geblish", "Odchyd"])
    assert.deepEqual(g[1].rows.map((r) => r.stan), ["zawieszony", "zawieszony", "offline", "offline", "offline"])
  })
  it("w grze: tylko pierwsza grupa; z alarmem: wg alarm_24h/stan alarm", () => {
    assert.deepEqual(P.groupsOf(rows, "w grze").map((x) => x.key), ["gra"])
    const al = P.groupsOf(rows, "z alarmem")
    assert.deepEqual(al.map((x) => x.key), ["offline"])
    assert.deepEqual(al[0].rows.map((r) => r.nick).sort(), ["Dawajkesh", "Kolanosh"])
  })
  it("liczniki filtrów", () => {
    assert.deepEqual(P.filterCounts(rows), { "wszystkie": 7, "w grze": 2, "z alarmem": 2 })
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
    assert.equal(c.offline, 1)
    assert.equal(c.total, 3)
    assert.equal(P.navBadge([i, by("gebelish"), by("odchyd")]), "2/3 w grze")
    const grupy = P.groupsOf(P.rowsOf([i, by("gebelish")], NOW), "wszystkie")
    assert.deepEqual(grupy.map((g) => g.key + ":" + g.rows.map((x) => x.id).join(",")), ["gra:gebelish", "offline:invincible"])
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
