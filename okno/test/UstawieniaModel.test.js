"use strict"

// Uruchom: node --test okno/test/*.test.js   (z katalogu repo bota)
// Logika sekcji Ustawienia i Ctrl+K (UstawieniaModel.js). Testy zapisu chodzą na ATRAPIE katalogu (atrapa.py), nigdy na prawdziwych plikach.

const { describe, it, before, after } = require("node:test")
const assert = require("node:assert/strict")
const fs = require("node:fs")
const os = require("node:os")
const path = require("node:path")
const { spawnSync } = require("node:child_process")
const U = require("../UstawieniaModel.js")
const M = require("../OknoModel.js")

const REPO = path.resolve(__dirname, "..", "..")

const knob = (over) => Object.assign({
  klucz: "POGON_ZASIEG", grupa: "Walka i pościg", typ: "calkowita", min: 10, max: 14, domyslna: 10, biezaca: 10, zmieniona: false,
  opis: "max odległość pościgu za celem poza ekranem"
}, over || {})

const DATA = {
  ok: true,
  grupy: [{ nazwa: "Walka i pościg" }, { nazwa: "Leczenie i runy" }, { nazwa: "Zaawansowane" }],
  pokretla: [
    knob(),
    knob({ klucz: "POGON_LIMIT", typ: "ulamkowa", min: 12.0, max: 30.0, domyslna: 14.0, biezaca: 25.0, zmieniona: true, opis: "s bez zbliżania, potem odpuszczamy" }),
    knob({ klucz: "ZDROWIE_CZAR_HP", grupa: "Leczenie i runy", min: 10, max: 95, domyslna: 80, biezaca: 80, opis: "HP% poniżej którego leczymy exura" }),
    knob({ klucz: "UH_KOSZT", grupa: "Leczenie i runy", min: 1, max: 500, domyslna: 70, biezaca: 100, zmieniona: true, opis: "koszt many czaru runowego" }),
    knob({ klucz: "UH_AKTYWNY", grupa: "Leczenie i runy", typ: "przelacznik", min: 0, max: 1, domyslna: 0, biezaca: 0, opis: "1 = robienie run czarem runowym w spokoju" }),
    knob({ klucz: "UH_CZAR", grupa: "Leczenie i runy", typ: "tekst", min: null, max: null, domyslna: "adori gran", biezaca: "adura vita",
           zmieniona: true, opis: "słowa czaru (log); koszt osobno", opcje: ["adori gran", "adura gran", "adura vita", "adura"] }),
    knob({ klucz: "UH_KLAWISZ", grupa: "Leczenie i runy", typ: "tekst", min: null, max: null, domyslna: "F6", biezaca: "F7", zmieniona: true,
           opis: "hotkey czaru runowego w kliencie", opcje: ["F1", "F6", "F7"] }),
    knob({ klucz: "RUNA_AKTYWNA", grupa: "Leczenie i runy", typ: "przelacznik", min: 0, max: 1, domyslna: 0, biezaca: 1, zmieniona: true, opis: "1 = strzał runą w walce" }),
    knob({ klucz: "PET_NAZWA", grupa: "Zaawansowane", typ: "tekst", min: null, max: null, domyslna: "Elf Scout", biezaca: "Elf Scout", opis: "nazwa stworzenia", opcje: ["Elf Scout", "Scarab"] })
  ],
  inne_w_pliku: { STARY_KLUCZ: 5 },
  ostatnia_zmiana: null
}

describe("grupy", () => {
  const knobs = U.allKnobs(DATA)
  it("UH_* trafia do przypiętej grupy Runy (UH) na górze; reszta wg zaplecza; Poza listą na końcu", () => {
    const g = U.buildGroups(DATA, knobs)
    assert.deepEqual(g.map((x) => x.nazwa), ["Runy (UH)", "Walka i pościg", "Leczenie i runy", "Zaawansowane", "Poza listą"])
    assert.deepEqual(g.map((x) => x.ile), [4, 2, 2, 1, 1])
    assert.equal(g.find((x) => x.nazwa === "Runy (UH)").zmienione, 3)
    assert.equal(g.reduce((s, x) => s + x.ile, 0), knobs.length)
  })
  it("pusta grupa nie pojawia się na liście", () => {
    const g = U.buildGroups({ grupy: DATA.grupy, pokretla: [knob()], inne_w_pliku: {} }, U.allKnobs({ grupy: DATA.grupy, pokretla: [knob()] }))
    assert.deepEqual(g.map((x) => x.nazwa), ["Walka i pościg"])
  })
  it("w grupie Runy najpierw aktywność, czar, klawisz, koszt (kolejność zestawu run)", () => {
    assert.deepEqual(U.knobsOfGroup(knobs, "Runy (UH)").map((p) => p.klucz), ["UH_AKTYWNY", "UH_CZAR", "UH_KLAWISZ", "UH_KOSZT"])
  })
  it("klucz spoza listy pokręteł: tylko odczyt, bez kontrolki", () => {
    const x = knobs.find((p) => p.klucz === "STARY_KLUCZ")
    assert.equal(x.readonly, true)
    assert.equal(x.grupaUI, "Poza listą")
    assert.equal(U.controlKind(x), "odczyt")
    assert.equal(U.formatArg(x, 6), null)
  })
})

describe("typ pokrętła -> kontrolka", () => {
  const by = U.byKeyMap(U.allKnobs(DATA))
  it("0/1 = przełącznik, tekst = wybór z listy, liczby = suwak", () => {
    assert.equal(U.controlKind(by.UH_AKTYWNY), "przelacznik")
    assert.equal(U.controlKind(by.UH_CZAR), "wybor")
    assert.equal(U.controlKind(by.POGON_ZASIEG), "suwak")
    assert.equal(U.controlKind(by.POGON_LIMIT), "suwak")
  })
  it("krok suwaka: całkowite 1; ułamkowe wg rozpiętości; snap trzyma krok i granice", () => {
    assert.equal(U.stepFor(by.POGON_ZASIEG), 1)
    assert.equal(U.stepFor(by.POGON_LIMIT), 0.1)
    assert.equal(U.stepFor({ typ: "ulamkowa", min: 0.07, max: 0.2 }), 0.01)
    assert.equal(U.stepFor({ typ: "ulamkowa", min: 60.0, max: 3600.0 }), 1)
    assert.equal(U.snap(by.POGON_ZASIEG, 12.4), 12)
    assert.equal(U.snap(by.POGON_ZASIEG, 99), 14)
    assert.equal(U.snap(by.POGON_LIMIT, 20.04), 20)
    assert.equal(U.snap(by.POGON_LIMIT, 13.37), 13.4)
  })
  it("pole liczby: przecinek, zakres, całkowitość, śmieci", () => {
    assert.deepEqual(U.parseInput(by.POGON_LIMIT, "20,5"), { ok: true, value: 20.5 })
    assert.deepEqual(U.parseInput(by.POGON_ZASIEG, " 12 "), { ok: true, value: 12 })
    assert.equal(U.parseInput(by.POGON_ZASIEG, "12.5").ok, false)
    assert.match(U.parseInput(by.POGON_ZASIEG, "99").blad, /poza zakresem 10 do 14/)
    assert.equal(U.parseInput(by.POGON_ZASIEG, "abc").ok, false)
    assert.equal(U.parseInput(by.POGON_ZASIEG, "").ok, false)
    assert.equal(U.parseInput(by.POGON_ZASIEG, "1e3").ok, false)
  })
  it("podpisy wartości: HMM i UH przy czarze, włączone/wyłączone przy przełączniku", () => {
    assert.equal(U.optionLabel("UH_CZAR", "adori gran"), "HMM")
    assert.equal(U.optionLabel("UH_CZAR", "adura vita"), "UH")
    assert.equal(U.optionLabel("UH_CZAR", "adura"), "")
    assert.equal(U.valueLabel(by.UH_AKTYWNY), "wyłączone")
    assert.equal(U.valueLabel(by.UH_AKTYWNY, 1), "włączone")
    assert.equal(U.valueLabel(by.POGON_LIMIT), "25")
  })
})

describe("polecenie zapisu i cofania (bez powłoki)", () => {
  const by = U.byKeyMap(U.allKnobs(DATA))
  it("tekst jako JSON, liczba całkowita bez kropki, ułamkowa zawsze z kropką", () => {
    assert.deepEqual(U.ustawCommand("/r", "test", { UH_CZAR: "adori gran" }, by),
      ["python3", "-I", "/r/okno_api.py", "ustaw", "--instancja", "test", 'UH_CZAR="adori gran"'])
    assert.equal(U.formatArg(by.POGON_ZASIEG, 12), "POGON_ZASIEG=12")
    assert.equal(U.formatArg(by.POGON_LIMIT, 20), "POGON_LIMIT=20.0")
    assert.equal(U.formatArg(by.POGON_LIMIT, 20.5), "POGON_LIMIT=20.5")
    assert.equal(U.formatArg(by.UH_AKTYWNY, 1), "UH_AKTYWNY=1")
    assert.equal(U.formatArg(by.UH_AKTYWNY, true), "UH_AKTYWNY=1")
  })
  it("zestaw = jedno wywołanie z wieloma parami (jeden wpis w dzienniku cofania)", () => {
    const c = U.ustawCommand("/r", "", { UH_CZAR: "adori gran", UH_KLAWISZ: "F6", UH_KOSZT: 70 }, by)
    assert.deepEqual(c.slice(3), ["ustaw", "--instancja", "", 'UH_CZAR="adori gran"', 'UH_KLAWISZ="F6"', "UH_KOSZT=70"])
  })
  it("odrzuca wartość spoza zakresu, spoza opcji, nieznany klucz i zły identyfikator instancji", () => {
    assert.equal(U.ustawCommand("/r", "test", { POGON_ZASIEG: 99 }, by), null)
    assert.equal(U.ustawCommand("/r", "test", { POGON_ZASIEG: 12.5 }, by), null)
    assert.equal(U.ustawCommand("/r", "test", { UH_CZAR: "exura" }, by), null)
    assert.equal(U.ustawCommand("/r", "test", { NIE_MA: 1 }, by), null)
    assert.equal(U.ustawCommand("/r", "te st", { POGON_ZASIEG: 12 }, by), null)
    assert.equal(U.ustawCommand("/r", "test", {}, by), null)
    assert.equal(U.ustawCommand("", "test", { POGON_ZASIEG: 12 }, by), null)
    assert.equal(U.ustawCommand("/r", "test", { POGON_ZASIEG: "12; rm" }, by), null)
  })
  it("pokretla i cofnij: tylko z poprawnym id", () => {
    assert.deepEqual(U.pokretlaCommand("/r", ""), ["python3", "-I", "/r/okno_api.py", "pokretla", "--instancja", ""])
    assert.deepEqual(U.cofnijCommand("/r", "test"), ["python3", "-I", "/r/okno_api.py", "cofnij", "--instancja", "test"])
    assert.equal(U.cofnijCommand("/r", "../x"), null)
    assert.equal(U.pokretlaCommand("/r", "A;b"), null)
  })
})

describe("filtr listy i Ctrl+K", () => {
  const knobs = U.allKnobs(DATA)
  it("grupa bez tekstu; tylko zmienione zawęża", () => {
    assert.deepEqual(U.filterKnobs(knobs, { grupa: "Walka i pościg" }).map((p) => p.klucz), ["POGON_ZASIEG", "POGON_LIMIT"])
    assert.deepEqual(U.filterKnobs(knobs, { grupa: "Walka i pościg", tylkoZmienione: true }).map((p) => p.klucz), ["POGON_LIMIT"])
    assert.deepEqual(U.filterKnobs(knobs, { grupa: "Runy (UH)", tylkoZmienione: true }).map((p) => p.klucz), ["UH_CZAR", "UH_KLAWISZ", "UH_KOSZT"])
  })
  it("tekst szuka po wszystkich grupach: nazwa, opis, grupa; bez polskich znaków; słowa w dowolnej kolejności", () => {
    assert.equal(U.filterKnobs(knobs, { grupa: "Patrol", tekst: "uh koszt" })[0].klucz, "UH_KOSZT")       // UH_CZAR też ("koszt osobno" w opisie), ale niżej
    assert.equal(U.filterKnobs(knobs, { grupa: "x", tekst: "koszt uh" })[0].klucz, "UH_KOSZT")
    assert.equal(U.filterKnobs(knobs, { grupa: "x", tekst: "uh koszt" }).length, 2)
    assert.ok(U.filterKnobs(knobs, { grupa: "x", tekst: "lecz" }).some((p) => p.klucz === "ZDROWIE_CZAR_HP"))
    assert.ok(U.filterKnobs(knobs, { grupa: "x", tekst: "pościg" }).some((p) => p.klucz === "POGON_ZASIEG"))
    assert.ok(U.filterKnobs(knobs, { grupa: "x", tekst: "poscig" }).some((p) => p.klucz === "POGON_ZASIEG"))
    assert.deepEqual(U.filterKnobs(knobs, { grupa: "x", tekst: "nie ma takiego" }), [])
  })
  it("trafienie w nazwę przed trafieniem w opis", () => {
    const r = U.filterKnobs(knobs, { grupa: "x", tekst: "runy" }).map((p) => p.klucz)
    assert.equal(r.includes("UH_AKTYWNY"), true)
    const r2 = U.filterKnobs(knobs, { grupa: "x", tekst: "uh" }).map((p) => p.klucz)
    assert.equal(r2[0].indexOf("UH"), 0)
  })

  const items = U.paletteItems(knobs, {
    mapy: [{ nazwa: "raty", opis: "Thais, kanały: szczury" }],
    tryby: [{ nazwa: "uh", opis: "Robienie run UH (adura vita)", pokretla: {} }]
  })
  it("paleta: pokrętła, mapy i tryby; wynik z rodzajem", () => {
    const r = U.searchPalette(items, "uh")
    assert.equal(r[0].rodzaj, "pokretlo")
    assert.ok(r.some((x) => x.rodzaj === "tryb" && x.klucz === "uh"))
    assert.deepEqual(U.searchPalette(items, "szczury").map((x) => [x.rodzaj, x.klucz]), [["mapa", "raty"]])
  })
  it("paleta: UH_KOSZT po 'uh koszt', po opisie 'koszt many', po grupie 'leczenie'", () => {
    assert.equal(U.searchPalette(items, "uh koszt")[0].klucz, "UH_KOSZT")
    assert.equal(U.searchPalette(items, "koszt many")[0].klucz, "UH_KOSZT")
    assert.ok(U.searchPalette(items, "leczenie").some((x) => x.klucz === "ZDROWIE_CZAR_HP"))
    assert.deepEqual(U.searchPalette(items, "zzzz"), [])
  })
  it("paleta: puste zapytanie podpowiada pokrętła run (UH) w kolejności zestawu", () => {
    assert.deepEqual(U.searchPalette(items, "").map((x) => x.klucz), ["UH_AKTYWNY", "UH_CZAR", "UH_KLAWISZ", "UH_KOSZT"])
  })
  it("paleta: limit wyników", () => {
    assert.equal(U.searchPalette(items, "a", 3).length, 3)
  })
  it("paleta bez danych o mapach i trybach działa na samych pokrętłach", () => {
    assert.equal(U.paletteItems(knobs, null).length, knobs.length)
  })
  it("wyróżnienie trafienia: tokeny w tekście, ucieczka znaków HTML", () => {
    assert.equal(U.highlight("UH_KOSZT", ["uh"], "#fff"), '<font color="#fff">UH</font>_KOSZT')
    assert.equal(U.highlight("a < b", ["b"], "#fff"), 'a &lt; <font color="#fff">b</font>')
    assert.equal(U.highlight("Pościg", ["poscig"], "#fff"), '<font color="#fff">Pościg</font>')
    assert.equal(U.highlight("x & y", [], "#fff"), "x &amp; y")
  })
})

describe("ostrzeżenie: tryb nadpisze pokrętło przy następnym starcie", () => {
  const knobs = U.allKnobs(DATA)
  const by = U.byKeyMap(knobs)
  const tryby = [
    { nazwa: "ml", pokretla: { ML_CZAR_AKTYWNY: 1, UH_AKTYWNY: 0 } },
    { nazwa: "runy", pokretla: { UH_AKTYWNY: 1, UH_CZAR: "adori gran", UH_KOSZT: 70, UH_KLAWISZ: "F7" } },
    { nazwa: "ostrozny", pokretla: { RUNA_AKTYWNA: 0 } }
  ]
  it("tryby scalane od lewej do prawej: późniejszy wygrywa", () => {
    const s = U.modeSettings(tryby, ["ml", "runy"])
    assert.deepEqual(s.UH_AKTYWNY, { tryb: "runy", wartosc: 1 })
    assert.deepEqual(U.modeSettings(tryby, ["runy", "ml"]).UH_AKTYWNY, { tryb: "ml", wartosc: 0 })
    assert.deepEqual(U.modeSettings(tryby, ["nie_ma"]), {})
    assert.deepEqual(U.modeSettings(tryby, []), {})
  })
  it("konflikt tylko gdy wartość trybu różni się od bieżącej; klucz spoza listy pomijany (ML_CZAR_AKTYWNY nie ma w danych)", () => {
    const c = U.modeConflicts(U.modeSettings(tryby, ["ml", "ostrozny"]), by)
    assert.deepEqual(c.map((x) => [x.klucz, x.tryb, x.wartosc, x.biezaca]), [["RUNA_AKTYWNA", "ostrozny", 0, 1]])
    const c2 = U.modeConflicts(U.modeSettings(tryby, ["runy"]), by)
    assert.deepEqual(c2.map((x) => x.klucz), ["UH_AKTYWNY", "UH_CZAR", "UH_KOSZT"])    // UH_KLAWISZ F7 = F7: bez konfliktu
  })
  it("UH_KOSZT 70 vs bieżące 100 jest konfliktem; równa wartość nie", () => {
    const c = U.modeConflicts(U.modeSettings(tryby, ["runy"]), by)
    assert.equal(U.conflictFor(c, "UH_KOSZT").wartosc, 70)
    const by2 = U.byKeyMap(U.allKnobs(U.applyChanges(DATA, { UH_KOSZT: 70 })))
    assert.equal(U.conflictFor(U.modeConflicts(U.modeSettings(tryby, ["runy"]), by2), "UH_KOSZT"), null)
  })
  it("teksty ostrzeżeń: wiersz i podsumowanie", () => {
    const c = U.modeConflicts(U.modeSettings(tryby, ["ostrozny"]), by)
    assert.match(U.conflictText(c[0], by.RUNA_AKTYWNA), /tryb „ostrozny” przy następnym starcie ustawi RUNA_AKTYWNA = wyłączone \(teraz włączone\)/)
    assert.match(U.conflictSummary(c, ["ostrozny"]), /trybu ostrozny\. Przy następnym starcie \(uruchom\.sh\) ustawi on: RUNA_AKTYWNA\./)
    assert.equal(U.conflictSummary([], ["ostrozny"]), "")
  })
})

describe("zestawy run z trybów", () => {
  const by = U.byKeyMap(U.allKnobs(DATA))
  const tryby = [
    { nazwa: "ml", pokretla: { UH_AKTYWNY: 0 } },
    { nazwa: "runy", pokretla: { UH_AKTYWNY: 1, UH_CZAR: "adori gran", UH_KLAWISZ: "F6", UH_KOSZT: 70, UH_MANA_MIN: 70, JEDZENIE_CZAR_AKTYWNY: 0 } },
    { nazwa: "uh", pokretla: { UH_CZAR: "adura vita", UH_KLAWISZ: "F7", UH_KOSZT: 100 } },
    { nazwa: "zly", pokretla: { UH_CZAR: "nieznany czar" } }
  ]
  it("zestaw = tylko UH_CZAR, klawisz, koszt, mana z trybu, który ustawia UH_CZAR; UH_AKTYWNY i reszta nie wchodzą", () => {
    const p = U.runePresets(tryby, by)
    assert.deepEqual(p.map((x) => x.tryb), ["runy", "uh"])
    assert.deepEqual(Object.keys(p[0].pary), ["UH_CZAR", "UH_KLAWISZ", "UH_KOSZT"])    // UH_MANA_MIN poza `by` w DATA
    assert.equal(p[0].tytul, "HMM (adori gran)")
    assert.equal(p[1].tytul, "UH (adura vita)")
    assert.match(p[0].opis, /adori gran · F6 · koszt 70/)
  })
  it("zestaw aktywny, gdy bieżące wartości się zgadzają", () => {
    const p = U.runePresets(tryby, by)
    assert.equal(U.presetActive(p[0], by), false)
    const after = U.byKeyMap(U.allKnobs(U.applyChanges(DATA, p[0].pary)))
    assert.equal(U.presetActive(p[0], after), true)
    assert.equal(U.presetActive(p[1], after), false)
  })
  it("zapis zestawu to jedno polecenie ustaw z walidowanymi parami", () => {
    const p = U.runePresets(tryby, by)
    const c = U.ustawCommand("/r", "", p[0].pary, by)
    assert.deepEqual(c.slice(5), ['', 'UH_CZAR="adori gran"', 'UH_KLAWISZ="F6"', "UH_KOSZT=70"])
  })
})

describe("wyniki zapisu i podpisy", () => {
  const by = U.byKeyMap(U.allKnobs(DATA))
  it("applyChanges poprawia bieżącą i flagę zmieniona; nie rusza oryginału", () => {
    const d = U.applyChanges(DATA, { UH_CZAR: "adori gran", POGON_ZASIEG: 12 })
    const m = U.byKeyMap(U.allKnobs(d))
    assert.equal(m.UH_CZAR.biezaca, "adori gran")
    assert.equal(m.UH_CZAR.zmieniona, false)
    assert.equal(m.POGON_ZASIEG.zmieniona, true)
    assert.equal(DATA.pokretla.find((p) => p.klucz === "UH_CZAR").biezaca, "adura vita")
  })
  it("opis zmiany i cofnięcia", () => {
    assert.equal(U.describeChange({ UH_CZAR: "adori gran" }, { UH_CZAR: "adura vita" }, by), "UH_CZAR: adura vita → adori gran")
    assert.equal(U.describeChange({ POGON_ZASIEG: 12 }, { POGON_ZASIEG: null }, by), "POGON_ZASIEG: domyślna → 12")
    assert.equal(U.describeChange({ A: 1, B: 2, C: 3, D: 4 }, {}, {}), "A: domyślna → 1 · B: domyślna → 2 · C: domyślna → 3 · +1")
    assert.equal(U.describeUndo({ przywrocone: { UH_CZAR: "adura vita" }, usuniete: ["POGON_ZASIEG"] }, by), "UH_CZAR → adura vita · POGON_ZASIEG → domyślna")
  })
  it("podpis Cofnij ostatnią: klucze, wartość przed, godzina; null gdy brak dziennika", () => {
    assert.equal(U.undoLabel(null, by), null)
    const dzis = new Date(2026, 9, 20, 12, 0, 0)
    assert.equal(U.undoLabel({ czas: "2026-10-20 10:12:05", po: { UH_CZAR: "adori gran" }, przed: { UH_CZAR: "adura vita" }, brak: [] }, by, dzis),
      "UH_CZAR adura vita ← adori gran · 10:12")
    assert.equal(U.undoLabel({ czas: "2026-10-20 10:12:05", po: { POGON_ZASIEG: 12 }, przed: {}, brak: ["POGON_ZASIEG"] }, by, dzis), "POGON_ZASIEG domyślna ← 12 · 10:12")
    assert.equal(U.undoLabel({ czas: "2026-10-19 21:14:00", po: { POGON_ZASIEG: 12 }, przed: {}, brak: [] }, by, dzis), "POGON_ZASIEG domyślna ← 12 · 19.10 21:14")
  })
})

describe("zapis i cofnięcie na atrapie (okno_api z prawdziwą walidacją pokretla.py)", () => {
  let dir, atrapa
  const run = (cmd) => !atrapa || !atrapa.RETRONIC_OKNO_KATALOG ? assert.fail("brak atrapy: nie wolno uruchamiać na prawdziwym katalogu") : spawnSync(cmd[0], cmd.slice(1), { encoding: "utf8", timeout: 15000, env: Object.assign({}, process.env, atrapa) })
  before(() => {
    dir = fs.mkdtempSync(path.join(os.tmpdir(), "okno-test-ust-"))
    const r = spawnSync("python3", ["-I", path.join(REPO, "okno", "test", "atrapa.py"), dir], { encoding: "utf8" })
    assert.equal(r.status, 0, r.stderr)
    atrapa = {}
    for (const l of r.stdout.split("\n")) {
      const m = /^export (\w+)="(.*)"$/.exec(l)
      if (m) atrapa[m[1]] = m[2]
    }
  })
  after(() => fs.rmSync(dir, { recursive: true, force: true }))
  const plik = () => path.join(atrapa.RETRONIC_OKNO_KATALOG, "na_zywo.json")
  const read = (id) => M.parseApi(run(U.pokretlaCommand(REPO, id)).stdout)

  it("kontrakt `pokretla`: grupy, typy, opcje, inne_w_pliku, ostatnia_zmiana", () => {
    const r = read("")
    assert.equal(r.ok, true, JSON.stringify(r))
    const knobs = U.allKnobs(r.data)
    const by = U.byKeyMap(knobs)
    assert.equal(by.UH_CZAR.typ, "tekst")
    assert.ok(by.UH_CZAR.opcje.includes("adori gran"))
    assert.equal(by.UH_CZAR.biezaca, "adura vita")
    assert.equal(by.UH_AKTYWNY.typ, "przelacznik")
    assert.equal(by.STARY_KLUCZ.readonly, true)
    assert.equal(r.data.ostatnia_zmiana, null)
    const g = U.buildGroups(r.data, knobs)
    assert.equal(g[0].nazwa, "Runy (UH)")
    assert.equal(g.reduce((s, x) => s + x.ile, 0), knobs.length)
  })
  it("UH_CZAR=adori gran: plik się zmienia, zestaw przechodzi w jednym wywołaniu, cofnij przywraca", () => {
    const before = fs.readFileSync(plik(), "utf8")
    const by = U.byKeyMap(U.allKnobs(read("").data))
    const w = M.parseApi(run(U.ustawCommand(REPO, "", { UH_CZAR: "adori gran" }, by)).stdout)
    assert.equal(w.ok, true, JSON.stringify(w))
    assert.deepEqual(w.data.zmienione, { UH_CZAR: "adori gran" })
    assert.deepEqual(w.data.poprzednie, { UH_CZAR: "adura vita" })
    assert.equal(JSON.parse(fs.readFileSync(plik(), "utf8")).UH_CZAR, "adori gran")
    const r = read("")
    assert.equal(U.byKeyMap(U.allKnobs(r.data)).UH_CZAR.biezaca, "adori gran")
    assert.match(U.undoLabel(r.data.ostatnia_zmiana, by, new Date()), /^UH_CZAR adura vita ← adori gran · \d\d:\d\d$/)
    const c = M.parseApi(run(U.cofnijCommand(REPO, "")).stdout)
    assert.equal(c.ok, true, JSON.stringify(c))
    assert.deepEqual(c.data.przywrocone, { UH_CZAR: "adura vita" })
    assert.equal(JSON.parse(fs.readFileSync(plik(), "utf8")).UH_CZAR, "adura vita")
    assert.deepEqual(JSON.parse(fs.readFileSync(plik(), "utf8")), JSON.parse(before))
  })
  it("ułamek zapisany jako float, tekst z walidacją opcji, zestaw w jednym wpisie dziennika", () => {
    const by = U.byKeyMap(U.allKnobs(read("").data))
    const w = M.parseApi(run(U.ustawCommand(REPO, "", { POGON_LIMIT: 20, UH_KLAWISZ: "F6", UH_KOSZT: 70 }, by)).stdout)
    assert.equal(w.ok, true, JSON.stringify(w))
    assert.equal(fs.readFileSync(plik(), "utf8").includes('"POGON_LIMIT": 20.0'), true)
    assert.equal(M.parseApi(run(U.cofnijCommand(REPO, "")).stdout).data.przywrocone.UH_KOSZT, 100)
    assert.equal(JSON.parse(fs.readFileSync(plik(), "utf8")).UH_KLAWISZ, "F7")
  })
  it("zaplecze odrzuca wartość, którą model by przepuścił (np. spoza opcji) bez zapisu", () => {
    const before = fs.readFileSync(plik(), "utf8")
    const w = M.parseApi(run(["python3", "-I", path.join(REPO, "okno_api.py"), "ustaw", "--instancja", "", 'UH_CZAR="exura"']).stdout)
    assert.equal(w.ok, false)
    assert.equal(fs.readFileSync(plik(), "utf8"), before)
  })
  it("konflikt z trybem na atrapie: test (ml, ostrozny) vs UH_AKTYWNY=1", () => {
    const d = read("test").data
    const by = U.byKeyMap(U.allKnobs(d))
    const mt = M.parseApi(run(M.mapyCommand(REPO, "test")).stdout).data
    const c = U.modeConflicts(U.modeSettings(mt.tryby, mt.ostatni.tryb), by)
    assert.deepEqual(c.map((x) => [x.klucz, x.tryb, x.wartosc]), [["ML_CZAR_AKTYWNY", "ml", 1], ["UH_AKTYWNY", "ml", 0]])
    const presets = U.runePresets(mt.tryby, by)
    assert.deepEqual(presets.map((x) => x.tryb), ["runy", "uh"])
    assert.equal(U.presetActive(presets[0], by), true)      // instancja test ma już HMM: adori gran, F6, 70, 70
  })
})
