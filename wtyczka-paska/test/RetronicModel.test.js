"use strict"

// Uruchom: node --test test/*.test.js   (z katalogu plugins/charlie.retronic)
// Testy poleceń chodzą na ATRAPIE katalogu pomocnika (mktemp), nigdy na prawdziwych zatrzymaj.sh / uruchom.sh.

const { describe, it, before, after } = require("node:test")
const assert = require("node:assert/strict")
const fs = require("node:fs")
const os = require("node:os")
const path = require("node:path")
const { spawnSync } = require("node:child_process")
const M = require("../RetronicModel.js")

const ok = (klasa, extra) => Object.assign({ ok: true, klasa, running: klasa === "dziala", czas: "", hp: null, mana: null, proxy: null, lastMap: "", lastMode: "", error: "" }, extra)

describe("lista instancji", () => {
  it("główna zawsze pierwsza, reszta posortowana, bez _wspolne i śmieci", () => {
    assert.deepEqual(M.instanceIds("test\n_wspolne\ndwa\n"), ["", "dwa", "test"])
    assert.deepEqual(M.instanceIds(""), [""])
    assert.deepEqual(M.instanceIds(undefined), [""])
    assert.deepEqual(M.instanceIds("invincible\n_wspolne\n_bez_glownej\n"), ["invincible"])
    assert.deepEqual(M.instanceIds("_bez_glownej\n"), [])
  })
  it("odrzuca nazwy niezgodne ze wzorem bota (spacje, wielkie litery, ścieżki, średniki)", () => {
    assert.deepEqual(M.parseInstanceListing("Test\na b\n../x\na;rm\n-x\n" + "a".repeat(25) + "\nok_1\n"), ["ok_1"])
  })
  it("dowolna liczba instancji, bez duplikatów", () => {
    assert.deepEqual(M.parseInstanceListing("c\nb\na\nb\nd\ne\n"), ["a", "b", "c", "d", "e"])
  })
  it("nazwa wyświetlana: pusty ID to główna", () => {
    assert.equal(M.displayName(""), "główna")
    assert.equal(M.displayName("test"), "test")
  })
})

describe("ścieżka pomocnika", () => {
  it("rozwija ~", () => {
    assert.equal(M.expandPath("~/Games/x", "/home/u"), "/home/u/Games/x")
    assert.equal(M.expandPath("~", "/home/u"), "/home/u")
    assert.equal(M.expandPath("/opt/x", "/home/u"), "/opt/x")
    assert.equal(M.expandPath("  ", "/home/u"), "")
  })
  it("polecenia odrzucają złe ID i pusty katalog", () => {
    assert.equal(M.statusCommand("/d", "a b"), null)
    assert.equal(M.statusCommand("", ""), null)
    assert.equal(M.actionCommand("/d", "x;y", "stop"), null)
    assert.equal(M.actionCommand("/d", "", "kill"), null)
  })
  it("ID i katalog idą jako osobne argumenty, nie w tekście skryptu", () => {
    const c = M.actionCommand("/d ir/z 'q'", "test", "stop")
    assert.equal(c[0], "bash")
    assert.equal(c[1], "-c")
    assert.ok(!c[2].includes("test") && !c[2].includes("/d ir"))
    assert.deepEqual(c.slice(4), ["test", "/d ir/z 'q'", "zatrzymaj.sh"])
    assert.equal(M.actionCommand("/d", "", "start")[6], "uruchom.sh")
  })
})

const JSON_DZIALA = JSON.stringify({
  text: "󰐊 RT",
  tooltip: "Retronic: działa\nTryb: mozg.py hybryda, działa 8m 26s\nHP 235/235  mana 33/335\n07:59:51 [ATAK] klik\nWniosek analityka: [uwaga] tajny wniosek\nLewy: start/stop, prawy: panel",
  class: "dziala", alt: "dziala"
})

describe("parseStatus", () => {
  it("działa: czas, HP, mana, proxy, ostatni start; bez treści logów i wniosku", () => {
    const s = M.parseStatus(JSON_DZIALA + "\nPROXY=1\n--ENV--\nMAPA=gobliny_edron\nTRYB=ostrozny\n")
    assert.equal(s.ok, true)
    assert.equal(s.klasa, "dziala")
    assert.equal(s.running, true)
    assert.equal(s.czas, "8m 26s")
    assert.deepEqual(s.hp, { cur: 235, max: 235 })
    assert.deepEqual(s.mana, { cur: 33, max: 335 })
    assert.equal(s.proxy, true)
    assert.equal(M.stateLabel(s), "działa 8m 26s")
    assert.equal(M.resourcesLabel(s), "HP 235/235  mana 33/335")
    assert.equal(M.lastStartLabel(s), "ostatni: gobliny_edron, ostrozny")
    assert.equal(M.proxyLabel(s), "proxy włączone")
    assert.ok(!JSON.stringify(s).includes("tajny"))
    assert.ok(!JSON.stringify(s).includes("klik"))
  })
  it("stop: nie działa, brak HP, proxy wyłączone, wartości env w cudzysłowach", () => {
    const j = JSON.stringify({ text: "󰓛 RT", tooltip: "Retronic: zatrzymany\nLewy: start/stop", class: "stop", alt: "stop" })
    const s = M.parseStatus(j + "\nPROXY=0\n--ENV--\nMAPA=rook\nTRYB='a b'\n")
    assert.equal(s.klasa, "stop")
    assert.equal(s.running, false)
    assert.equal(s.hp, null)
    assert.equal(M.stateLabel(s), "stop")
    assert.equal(M.resourcesLabel(s), "")
    assert.equal(M.proxyLabel(s), "proxy wyłączone")
    assert.equal(M.lastStartLabel(s), "ostatni: rook, a b")
  })
  it("alarm z martwym botem: running=false (jest Start), z żywym: running=true", () => {
    const martwy = M.parseStatus(JSON.stringify({ tooltip: "Retronic: ALARM\n! ALARM_GM", class: "alarm" }) + "\nPROXY=0\n")
    assert.equal(martwy.klasa, "alarm")
    assert.equal(martwy.running, false)
    assert.equal(M.stateLabel(martwy), "ALARM")
    const zywy = M.parseStatus(JSON.stringify({ tooltip: "Retronic: ALARM\nTryb: mozg.py hybryda, działa 1m 02s\n! ALARM_GM", class: "alarm" }) + "\nPROXY=0\n")
    assert.equal(zywy.running, true)
    assert.equal(M.buttonKind(zywy), "stop")
    assert.equal(M.buttonKind(martwy), "start")
  })
  it("brak gry: Start zablokowany", () => {
    const s = M.parseStatus(JSON.stringify({ tooltip: "Retronic: brak gry", class: "brak" }) + "\nPROXY=0\n")
    assert.equal(M.stateLabel(s), "brak gry")
    assert.equal(M.buttonKind(s), "start")
    assert.equal(M.buttonEnabled(s), false)
  })
  it("brak ostatni_start: 'ostatni: brak'", () => {
    const s = M.parseStatus(JSON.stringify({ tooltip: "x", class: "stop" }) + "\nPROXY=0\n--ENV--\n")
    assert.equal(M.lastStartLabel(s), "ostatni: brak")
  })
  it("pusty / błędny / nieznany wynik: odczyt nieudany, przyciski zablokowane", () => {
    for (const bad of ["", "\nPROXY=0\n--ENV--\n", "{nie json\nPROXY=0", JSON.stringify({ class: "dziwny" })]) {
      const s = M.parseStatus(bad)
      assert.equal(s.ok, false, bad)
      assert.equal(M.buttonEnabled(s), false)
      assert.equal(M.stateLabel(s), "brak odczytu")
    }
  })
  it("start dozwolony tylko dla stop/alarm, stop dla działającego", () => {
    assert.equal(M.buttonEnabled(ok("stop")), true)
    assert.equal(M.buttonKind(ok("stop")), "start")
    assert.equal(M.buttonEnabled(ok("dziala")), true)
    assert.equal(M.buttonKind(ok("dziala")), "stop")
  })
})

describe("najgorszy stan i hover", () => {
  it("alarm > stop > działa > brak", () => {
    assert.equal(M.worstClass([ok("dziala"), ok("stop")]), "stop")
    assert.equal(M.worstClass([ok("dziala"), ok("alarm"), ok("stop")]), "alarm")
    assert.equal(M.worstClass([ok("dziala"), ok("brak")]), "dziala")
    assert.equal(M.worstClass([ok("brak"), ok("stop")]), "stop")
    assert.equal(M.worstClass([ok("brak")]), "brak")
  })
  it("brak odczytu liczy się jak brak, null jest pomijany, pusta lista to brak", () => {
    assert.equal(M.worstClass([null, M.unknownStatus()]), "brak")
    assert.equal(M.worstClass([null, ok("dziala")]), "dziala")
    assert.equal(M.worstClass([]), "brak")
  })
  it("zdanie: 2 instancje: 1 działa, 1 stop", () => {
    assert.equal(M.hoverSentence([ok("dziala"), ok("stop")]), "2 instancje: 1 działa, 1 stop")
  })
  it("zdanie: odmiana i kolejność (alarm pierwszy)", () => {
    assert.equal(M.hoverSentence([ok("dziala")]), "1 instancja: działa")
    assert.equal(M.hoverSentence([ok("stop")]), "1 instancja: stop")
    assert.equal(M.hoverSentence([ok("stop"), ok("stop"), ok("alarm"), ok("dziala"), ok("brak")]), "5 instancji: 1 alarm, 1 działa, 2 stop, 1 brak gry")
    assert.equal(M.hoverSentence([ok("stop"), ok("stop"), ok("stop")]), "3 instancje: 3 stop")
    assert.equal(M.pluralInstances(12), "instancji")
    assert.equal(M.pluralInstances(22), "instancje")
  })
  it("zdanie przed pierwszym odczytem i z nieudanym odczytem", () => {
    assert.equal(M.hoverSentence([null, null]), "Retronic: odczyt…")
    assert.equal(M.hoverSentence([ok("dziala"), M.unknownStatus()]), "2 instancje: 1 działa, 1 brak gry")
  })
})

describe("wynik akcji", () => {
  it("rc=0 to sukces bez komunikatu (także 'nie było bota')", () => {
    assert.deepEqual(M.parseActionResult("zatrzymany\n\nRC=0\n"), { ok: true, message: "" })
    assert.deepEqual(M.parseActionResult("RC=0"), { ok: true, message: "" })
  })
  it("znane odmowy po polsku", () => {
    assert.deepEqual(M.parseActionResult("brak socketu gry\n\nRC=1\n"), { ok: false, message: "Gra nie działa" })
    assert.deepEqual(M.parseActionResult("bot już działa\n\nRC=1\n"), { ok: false, message: "Bot już działa" })
  })
  it("nieznany błąd: ostatnia linia, jedna linia, skrócona", () => {
    const r = M.parseActionResult("a\n" + "x".repeat(200) + "\n\nRC=2\n")
    assert.equal(r.ok, false)
    assert.ok(r.message.length <= M.MAX_ERROR_LENGTH)
    assert.ok(r.message.endsWith("…"))
    assert.ok(!r.message.includes("\n"))
    assert.deepEqual(M.parseActionResult("RC=3"), { ok: false, message: "Błąd (kod 3)" })
  })
  it("brak linii RC to błąd, nie sukces", () => {
    assert.equal(M.parseActionResult("").ok, false)
    assert.equal(M.parseActionResult("zatrzymany").ok, false)
  })
})

// ------------------------------------------------------------ guziki miasta ("Wróć do miasta", "Refill")

// Próbka prawdziwego wyjścia panel.py --json (testy bota: test_refill.py 4b) z polami guzików.
const cityFields = (extra) => Object.assign({
  pozycja: [33173, 31796, 8], w_miescie: "edron", w_depo: true, plan_depo_dostepny: true,
  wroc_oczekuje: false, wroc_w_marszu: false,
  serwis_dziala: false, serwis_krok: null, serwis_ukonczone: [], serwis_wynik: null, serwis_komunikat: "", serwis_wiek_s: null
}, extra)
const BEZ_TRYBU = "Retronic: zatrzymany\nLewy: start/stop, prawy: panel"
const DZIALA_TRYB = "Retronic: działa\nTryb: mozg.py hybryda, działa 8m 26s\nHP 235/235  mana 33/335"
const city = (klasa, extra) => M.parseStatus(JSON.stringify(Object.assign({
  text: "RT", tooltip: klasa === "dziala" ? DZIALA_TRYB : BEZ_TRYBU, class: klasa, alt: klasa }, cityFields(extra))) + "\nPROXY=0\n--ENV--\n")
// bot działa na spocie goblinów
const naSpocie = (extra) => city("dziala", Object.assign({ pozycja: [33053, 31844, 8], w_miescie: null, w_depo: false }, extra))

describe("guziki miasta: parsowanie pól panel.py", () => {
  it("nowe pola: miasto, wroc, serwis; dotychczasowe bez zmian", () => {
    const s = city("stop", { serwis_dziala: true, serwis_krok: "jedzenie", serwis_ukonczone: ["jedzenie", 5], serwis_wiek_s: 7 })
    assert.equal(s.ok, true)
    assert.equal(s.klasa, "stop")
    assert.equal(s.cityData, true)
    assert.deepEqual(s.miasto, { wMiescie: "edron", wDepo: true, planDepo: true })
    assert.deepEqual(s.wroc, { oczekuje: false, wMarszu: false })
    assert.deepEqual(s.serwis, { dziala: true, krok: "jedzenie", tryb: "", ukonczone: ["jedzenie"], wynik: "", komunikat: "", wiekS: 7 })
  })
  it("pozycja nieznana: planDepo null; w_miescie null = poza miastem", () => {
    const s = city("dziala", { pozycja: null, w_miescie: null, plan_depo_dostepny: null })
    assert.equal(s.miasto.planDepo, null)
    assert.equal(s.miasto.wMiescie, "")
  })
  it("starszy panel.py bez pól: cityData=false, Stop/Start działają jak dotąd", () => {
    const s = M.parseStatus(JSON_DZIALA + "\nPROXY=0\n")
    assert.equal(s.cityData, false)
    assert.equal(M.buttonEnabled(s), true)
    assert.equal(M.returnButton(s).enabled, false)
    assert.equal(M.returnButton(s).hint, "panel.py bez danych o mieście")
    assert.equal(M.refillButton(s).enabled, false)
    assert.deepEqual(M.cityInfo(s), { text: "", error: false })
  })
  it("odczyt nieudany: guziki miasta szare", () => {
    const s = M.unknownStatus()
    assert.equal(s.cityData, false)
    assert.equal(M.returnButton(s).enabled, false)
    assert.equal(M.refillButton(s).enabled, false)
    assert.equal(M.returnButton(null).hint, "brak odczytu")
  })
})

describe("guzik Wróć do miasta", () => {
  it("bot działa na spocie z planem depo: aktywny, akcja wroc", () => {
    const b = M.returnButton(naSpocie())
    assert.deepEqual([b.action, b.enabled, b.label], ["wroc", true, "⌂ Miasto"])
  })
  it("zlecenie czeka: Anuluj (wroc-anuluj), info o spokojnej chwili", () => {
    const s = naSpocie({ wroc_oczekuje: true })
    const b = M.returnButton(s)
    assert.deepEqual([b.action, b.enabled, b.label], ["wroc-anuluj", true, "✕ Anuluj"])
    assert.deepEqual(M.cityInfo(s), { text: "czeka na spokojną chwilę", error: false })
  })
  it("w marszu: szary, nie da się anulować (tylko Stop), info o marszu", () => {
    const s = naSpocie({ wroc_w_marszu: true })
    const b = M.returnButton(s)
    assert.deepEqual([b.action, b.enabled, b.label], ["", false, "w marszu…"])
    assert.ok(b.hint.includes("Stop"))
    assert.equal(M.cityInfo(s).text, "w marszu do depo")
  })
  it("plik WROC a w marszu naraz (plik jeszcze nie zdjęty): marsz wygrywa", () => {
    assert.equal(M.returnButton(naSpocie({ wroc_oczekuje: true, wroc_w_marszu: true })).label, "w marszu…")
  })
  it("szary z powodem: brak planu, pozycja nieznana, już w mieście, bot stoi, brak gry, serwis w toku", () => {
    const hint = (s) => { const b = M.returnButton(s); assert.equal(b.enabled, false); assert.equal(b.action, ""); return b.hint }
    assert.equal(hint(naSpocie({ plan_depo_dostepny: false })), "brak planu depo dla tej pozycji")
    assert.equal(hint(naSpocie({ plan_depo_dostepny: null })), "pozycja postaci nieznana")
    assert.equal(hint(city("dziala", {})), "postać już jest w mieście")
    assert.equal(hint(city("stop", {})), "bot nie działa")
    assert.equal(hint(city("brak", {})), "gra nie działa")
    assert.equal(hint(city("stop", { serwis_dziala: true })), "serwis w toku")
  })
  it("stary plik WROC przy martwym bocie nie daje Anuluj", () => {
    const b = M.returnButton(city("stop", { wroc_oczekuje: true }))
    assert.equal(b.enabled, false)
    assert.equal(M.cityInfo(city("stop", { wroc_oczekuje: true })).text, "w depo, bot stoi")
  })
})

describe("guzik Refill", () => {
  it("bot stoi w mieście, serwis nie trwa: aktywny, akcja refill", () => {
    const b = M.refillButton(city("stop", {}))
    assert.deepEqual([b.action, b.enabled, b.label], ["refill", true, "↻ Refill"])
  })
  it("serwis w toku: Przerwij (refill-stop) i krok w info", () => {
    const s = city("stop", { serwis_dziala: true, serwis_krok: "backpack" })
    const b = M.refillButton(s)
    assert.deepEqual([b.action, b.enabled, b.label], ["refill-stop", true, "■ Przerwij"])
    assert.deepEqual(M.cityInfo(s), { text: "serwis w toku (krok: plecak)", error: false })
    assert.equal(M.cityInfo(city("stop", { serwis_dziala: true })).text, "serwis w toku")
  })
  it("szary z powodem: bot działa, poza miastem, pozycja nieznana, brak gry, alarm", () => {
    const hint = (s) => { const b = M.refillButton(s); assert.equal(b.enabled, false); assert.equal(b.action, ""); return b.hint }
    assert.equal(hint(city("dziala", {})), "najpierw zatrzymaj bota")
    assert.equal(hint(city("stop", { w_miescie: null, w_depo: false })), "postać jest poza miastem (najpierw ⌂ Miasto)")
    assert.equal(hint(city("stop", { w_miescie: null, plan_depo_dostepny: null, pozycja: null })), "pozycja postaci nieznana")
    assert.equal(hint(city("brak", {})), "gra nie działa")
    assert.equal(hint(city("alarm", {})), "alarm: poczekaj, aż minie")
  })
  it("Start jest zablokowany w trakcie serwisu (drugi sterujący grą), poza tym bez zmian", () => {
    const w = city("stop", { serwis_dziala: true })
    assert.equal(M.buttonKind(w), "start")
    assert.equal(M.buttonEnabled(w), false)
    assert.equal(M.buttonEnabled(city("stop", {})), true)
    assert.equal(M.buttonEnabled(city("dziala", { serwis_dziala: true })), true)
  })
})

describe("guzik Spot", () => {
  it("bot stoi w mieście, serwis nie trwa: aktywny, akcja spot", () => {
    const b = M.spotButton(city("stop", {}))
    assert.deepEqual([b.action, b.enabled, b.label], ["spot", true, "↗ Spot"])
    assert.equal(M.spotButton(city("stop", { w_depo: false })).enabled, true)
  })
  it("szary z powodem: bot działa, poza miastem, pozycja nieznana, brak gry, alarm, brak odczytu, stary panel.py", () => {
    const hint = (s) => { const b = M.spotButton(s); assert.equal(b.enabled, false); assert.equal(b.action, ""); return b.hint }
    assert.equal(hint(city("dziala", {})), "najpierw zatrzymaj bota")
    assert.equal(hint(city("stop", { w_miescie: null, w_depo: false })), "już poza miastem: użyj ▶ Start")
    assert.equal(hint(city("stop", { w_miescie: null, plan_depo_dostepny: null, pozycja: null })), "pozycja postaci nieznana")
    assert.equal(hint(city("brak", {})), "gra nie działa")
    assert.equal(hint(city("alarm", {})), "alarm: poczekaj, aż minie")
    assert.equal(hint(M.unknownStatus()), "brak odczytu")
    assert.equal(hint(M.parseStatus(JSON_DZIALA + "\nPROXY=0\n")), "panel.py bez danych o mieście")
  })
  it("serwis w toku: Spot szary (jedno wspólne ■ Przerwij na miejscu Refill, bez dublowania)", () => {
    const refillRun = city("stop", { serwis_dziala: true, serwis_krok: "jedzenie", serwis_tryb: "refill" })
    assert.deepEqual([M.spotButton(refillRun).enabled, M.spotButton(refillRun).label, M.spotButton(refillRun).hint], [false, "↗ Spot", "serwis w toku"])
    assert.equal(M.refillButton(refillRun).action, "refill-stop")
    const spotRun = city("stop", { serwis_dziala: true, serwis_krok: "wyjscie", serwis_tryb: "spot" })
    const b = M.spotButton(spotRun)
    assert.deepEqual([b.enabled, b.action, b.label], [false, "", "idę na spot…"])
    assert.equal(M.refillButton(spotRun).action, "refill-stop")
    assert.equal(M.refillButton(spotRun).label, "■ Przerwij")
  })
  it("linia stanu w trakcie: idę na spot… z krokiem; zwykły refill bez zmian", () => {
    assert.equal(M.cityInfo(city("stop", { serwis_dziala: true, serwis_krok: "wyjscie", serwis_tryb: "spot" })).text, "idę na spot… (krok: wyjście)")
    assert.equal(M.cityInfo(city("stop", { serwis_dziala: true, serwis_tryb: "spot" })).text, "idę na spot…")
    assert.equal(M.cityInfo(city("stop", { serwis_dziala: true, serwis_krok: "blanki", serwis_tryb: "refill" })).text, "serwis w toku (krok: blanki)")
  })
  it("porażka: błąd jak przy Refillu, Spot znów aktywny (świadomy klik), po starcie bota szary i bez błędu", () => {
    const blad = city("stop", { serwis_wynik: "blad", serwis_komunikat: "wyjscie: nie doszedłem", serwis_wiek_s: 20 })
    assert.deepEqual(M.cityInfo(blad), { text: "błąd: wyjscie: nie doszedłem", error: true })
    assert.equal(M.spotButton(blad).action, "spot")
    const poSukcesie = naSpocie({ serwis_wynik: null })
    assert.equal(M.spotButton(poSukcesie).enabled, false)
    assert.equal(M.cityInfo(poSukcesie).text, "")
  })
  it("tryb serwisu: stary panel.py bez pola = pusty (zachowanie jak Refill)", () => {
    assert.equal(city("stop", {}).serwis.tryb, "")
    assert.equal(city("stop", { serwis_tryb: "spot" }).serwis.tryb, "spot")
  })
  it("polecenie: refill.sh --spot z RETRONIC_ID instancji", () => {
    assert.deepEqual(M.actionCommand("/d", "test", "spot").slice(4), ["test", "/d", "refill.sh", "--spot"])
  })
})

describe("info o cyklu (cityInfo)", () => {
  it("w depo i w mieście po powrocie: bot stoi", () => {
    assert.equal(M.cityInfo(city("stop", {})).text, "w depo, bot stoi")
    assert.equal(M.cityInfo(city("stop", { w_depo: false })).text, "w mieście, bot stoi")
  })
  it("porażka serwisu: błąd z powodem, widoczny; bez ponawiania", () => {
    const s = city("stop", { serwis_wynik: "blad", serwis_komunikat: "blanki: brak miejsca w plecaku", serwis_wiek_s: 120 })
    assert.deepEqual(M.cityInfo(s), { text: "błąd: blanki: brak miejsca w plecaku", error: true })
    assert.equal(M.refillButton(s).action, "refill")
  })
  it("błąd bez komunikatu i błąd sprzed godziny", () => {
    assert.equal(M.cityInfo(city("stop", { serwis_wynik: "blad" })).text, "błąd: serwis nie powiódł się")
    assert.equal(M.cityInfo(city("stop", { serwis_wynik: "blad", serwis_komunikat: "x", serwis_wiek_s: M.ERROR_VISIBLE_S + 1 })).text, "w depo, bot stoi")
  })
  it("po starcie bota błąd znika (bot działa)", () => {
    assert.equal(M.cityInfo(naSpocie({ serwis_wynik: "blad", serwis_komunikat: "x", serwis_wiek_s: 5 })).text, "")
  })
  it("błąd -> start bota -> stop bota: błąd nie wraca (panel.py po starcie bota oddaje wynik pusty)", () => {
    const blad = { serwis_wynik: "blad", serwis_komunikat: "blanki: brak miejsca", serwis_wiek_s: 30 }
    assert.equal(M.cityInfo(city("stop", blad)).error, true)
    assert.equal(M.cityInfo(naSpocie(blad)).text, "")                      // bot działa: błąd schowany
    const poStopie = city("stop", { serwis_wynik: null, serwis_komunikat: "", serwis_wiek_s: 400 })
    assert.deepEqual(M.cityInfo(poStopie), { text: "w depo, bot stoi", error: false })
    assert.equal(M.refillButton(poStopie).action, "refill")
  })
  it("serwis przerwany; po sukcesie nic poza lokalizacją", () => {
    assert.equal(M.cityInfo(city("stop", { serwis_wynik: "przerwano", serwis_wiek_s: 5 })).text, "serwis przerwany")
    assert.equal(M.cityInfo(city("stop", { serwis_wynik: "ok" })).text, "w depo, bot stoi")
  })
  it("nazwy kroków po polsku", () => {
    assert.equal(M.stepLabel("wyjscie"), "wyjście")
    assert.equal(M.stepLabel("backpack"), "plecak")
    assert.equal(M.stepLabel("nowy"), "nowy")
  })
})

describe("polecenia akcji miasta", () => {
  it("wroc / wroc-anuluj / refill / refill-stop: skrypt i argument jako osobne argumenty", () => {
    assert.deepEqual(M.actionCommand("/d", "test", "wroc").slice(4), ["test", "/d", "wroc.sh"])
    assert.deepEqual(M.actionCommand("/d", "test", "wroc-anuluj").slice(4), ["test", "/d", "wroc.sh", "--anuluj"])
    assert.deepEqual(M.actionCommand("/d", "", "refill").slice(4), ["", "/d", "refill.sh", "--tlo"])
    assert.deepEqual(M.actionCommand("/d", "", "refill-stop").slice(4), ["", "/d", "refill.sh", "--przerwij"])
  })
  it("nieznany rodzaj (także z prototypu) i złe ID: null", () => {
    for (const k of ["kill", "constructor", "__proto__", "toString", "hasOwnProperty"]) assert.equal(M.actionCommand("/d", "", k), null, k)
    assert.equal(M.actionCommand("/d", "a b", "refill"), null)
  })
  it("komunikaty odmów nowych skryptów", () => {
    assert.deepEqual(M.parseActionResult("bot nie działa, uruchom: ./uruchom.sh\n\nRC=1\n"), { ok: false, message: "Bot nie działa" })
    assert.deepEqual(M.parseActionResult("serwis już działa\n\nRC=1\n"), { ok: false, message: "Serwis już trwa" })
    assert.deepEqual(M.parseActionResult("bot działa (pid 12), zatrzymaj: ./zatrzymaj.sh\n\nRC=1\n"), { ok: false, message: "Bot działa: najpierw Stop" })
  })
})

describe("guzik Otwórz okno (polecenie)", () => {
  it("jeden guzik panelu: zawsze aktywny, bez zależności od stanu botów", () => {
    const b = M.windowButton()
    assert.equal(b.action, "okno")
    assert.equal(b.enabled, true)
    assert.equal(b.tone, "ok")
    assert.ok(b.label.includes("Otwórz okno"))
  })
  it("katalog idzie jako osobny argument, nie w tekście skryptu; pusty katalog: null", () => {
    const c = M.windowCommand("/d ir/z 'q'")
    assert.deepEqual([c[0], c[1]], ["bash", "-c"])
    assert.ok(!c[2].includes("/d ir"))
    assert.deepEqual(c.slice(4), ["/d ir/z 'q'"])
    assert.equal(M.windowCommand(""), null)
    assert.equal(M.windowCommand(undefined), null)
  })
  it("okno.sh jest odłączone (setsid -f, wyjście do /dev/null), żeby żyło po zamknięciu popupu i restarcie paska", () => {
    assert.match(M.WINDOW_SCRIPT, /setsid -f bash "\$DIR\/okno\.sh" > \/dev\/null 2>&1 < \/dev\/null/)
  })
})

// ------------------------------------------------------------ atrapa katalogu pomocnika

describe("polecenia na atrapie pomocnika", () => {
  let dir
  const run = (cmd) => spawnSync(cmd[0], cmd.slice(1), { encoding: "utf8", timeout: 10000 })
  const read = (f) => fs.readFileSync(path.join(dir, f), "utf8")
  const setState = (id, klasa) => fs.writeFileSync(path.join(dir, "stan." + (id || "glowna")), klasa)
  const sh = (name, body) => fs.writeFileSync(path.join(dir, name), "#!/bin/bash\n" + body, { mode: 0o755 })

  before(() => {
    dir = fs.mkdtempSync(path.join(os.tmpdir(), "retronic-atrapa-"))
    fs.mkdirSync(path.join(dir, "instancje", "test"), { recursive: true })
    fs.mkdirSync(path.join(dir, "instancje", "dwa"))
    fs.mkdirSync(path.join(dir, "instancje", "_wspolne"))
    fs.writeFileSync(path.join(dir, "instancje", "plik.txt"), "")
    fs.writeFileSync(path.join(dir, "ostatni_start.env"), "MAPA=gobliny_edron\nTRYB=ostrozny\n")
    fs.writeFileSync(path.join(dir, "ostatni_start.test.env"), "MAPA=rook\nTRYB=ostrozny\n")
    fs.writeFileSync(path.join(dir, "panel.py"), [
      "import json, os, sys",
      "i = os.environ.get('RETRONIC_ID', '')",
      "k = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'stan.' + (i or 'glowna'))).read().strip()",
      "t = 'Retronic: ' + k",
      "if k == 'dziala': t += '\\nTryb: mozg.py hybryda, działa 8m 26s\\nHP 100/200  mana 5/10\\nWniosek analityka: sekret'",
      "print(json.dumps({'text': 'RT', 'tooltip': t, 'class': k, 'alt': k}, ensure_ascii=False))"
    ].join("\n"))
    sh("zatrzymaj.sh", 'echo "$RETRONIC_ID" >> "$(dirname "$0")/wywolania.log"; echo stop >> "$(dirname "$0")/wywolania.log"\n' +
      'D="$(dirname "$0")"; echo stop > "$D/stan.${RETRONIC_ID:-glowna}"; echo zatrzymany')
    // jak prawdziwy uruchom.sh: odmawia, gdy działa albo brak gry; start zostawia dziecko trzymające stdout
    sh("uruchom.sh", 'D="$(dirname "$0")"; echo "start:$RETRONIC_ID" >> "$D/wywolania.log"\n' +
      '[ "$(cat "$D/stan.${RETRONIC_ID:-glowna}")" = dziala ] && { echo "bot już działa" >&2; exit 1; }\n' +
      '[ -e "$D/brak_gry.${RETRONIC_ID:-glowna}" ] && { echo "brak socketu gry" >&2; exit 1; }\n' +
      'echo dziala > "$D/stan.${RETRONIC_ID:-glowna}"; (sleep 4 &) ; echo "Start (atrapa)"')
    setState("", "dziala")
    setState("test", "stop")
    setState("dwa", "stop")
    // wroc.sh / refill.sh: zapisują wywołanie z argumentami; refill --tlo zostawia odłączone dziecko (jak prawdziwy setsid -f)
    sh("wroc.sh", 'D="$(dirname "$0")"; echo "wroc:$RETRONIC_ID:$*" >> "$D/miasto.log"; [ "$1" = --anuluj ] && echo "zlecenie anulowane" || echo "zlecenie przyjęte"')
    sh("refill.sh", 'D="$(dirname "$0")"; echo "refill:$RETRONIC_ID:$*" >> "$D/miasto.log"\n' +
      '[ -e "$D/bot_dziala" ] && { echo "bot działa (pid 12), zatrzymaj: ./zatrzymaj.sh" >&2; exit 1; }\n' +
      '[ "$1" = --tlo ] || [ "$1" = --spot ] && { setsid -f sleep 4 > /dev/null 2>&1 < /dev/null; echo "refill ruszył"; }\n' +
      '[ "$1" = --przerwij ] && echo "refill przerwany"; exit 0')
  })
  after(() => fs.rmSync(dir, { recursive: true, force: true }))

  it("lista instancji z katalogu: tylko katalogi, bez _wspolne", () => {
    const r = run(M.listCommand(dir))
    assert.equal(r.status, 0, r.stderr)
    assert.deepEqual(M.instanceIds(r.stdout), ["", "dwa", "test"])
  })
  it("lista instancji: brak katalogu instancje daje tylko główną", () => {
    const r = run(M.listCommand(path.join(dir, "nie-ma")))
    assert.deepEqual(M.instanceIds(r.stdout), [""])
  })
  it("status głównej i test z atrapy (ostatni start, proxy wyłączone, bez wniosku)", () => {
    const g = M.parseStatus(run(M.statusCommand(dir, "")).stdout)
    assert.equal(g.klasa, "dziala")
    assert.equal(g.czas, "8m 26s")
    assert.equal(g.lastMap, "gobliny_edron")
    assert.equal(g.proxy, false)
    assert.ok(!JSON.stringify(g).includes("sekret"))
    const t = M.parseStatus(run(M.statusCommand(dir, "test")).stdout)
    assert.equal(t.klasa, "stop")
    assert.equal(t.lastMap, "rook")
  })
  it("status gdy panel.py zawodzi albo katalog nie istnieje: odczyt nieudany", () => {
    assert.equal(M.parseStatus(run(M.statusCommand(dir, "dwa")).stdout).ok, true)
    fs.rmSync(path.join(dir, "stan.dwa"))
    assert.equal(M.parseStatus(run(M.statusCommand(dir, "dwa")).stdout).ok, false)
    setState("dwa", "stop")
    assert.equal(M.parseStatus(run(M.statusCommand(path.join(dir, "nie-ma"), "")).stdout).ok, false)
  })
  it("proxy: wykrywa siec_proxy.sh tej instancji po RETRONIC_ID", () => {
    fs.writeFileSync(path.join(dir, "siec_proxy.sh"), "#!/bin/bash\nsleep 6\n", { mode: 0o755 })
    const child = require("node:child_process").spawn(path.join(dir, "siec_proxy.sh"), [], { env: Object.assign({}, process.env, { RETRONIC_ID: "test" }), stdio: "ignore" })
    try {
      const wait = Date.now() + 300
      while (Date.now() < wait) { /* daj bashowi wystartować */ }
      assert.equal(M.parseStatus(run(M.statusCommand(dir, "test")).stdout).proxy, true)
      assert.equal(M.parseStatus(run(M.statusCommand(dir, "")).stdout).proxy, false)
      assert.equal(M.parseStatus(run(M.statusCommand(dir, "dwa")).stdout).proxy, false)
    } finally {
      child.kill()
    }
  })
  it("Stop dotyka tylko wskazanej instancji i nie wisi", () => {
    fs.writeFileSync(path.join(dir, "wywolania.log"), "")
    const t0 = Date.now()
    const r = M.parseActionResult(run(M.actionCommand(dir, "", "stop")).stdout)
    assert.equal(r.ok, true)
    assert.ok(Date.now() - t0 < 3000)
    assert.equal(read("stan.glowna").trim(), "stop")
    assert.equal(read("stan.test").trim(), "stop")
    assert.equal(read("wywolania.log"), "\nstop\n")
    setState("", "dziala")
  })
  it("Start instancji test: uruchom.sh dostaje RETRONIC_ID=test; dziecko nie blokuje wtyczki", () => {
    fs.writeFileSync(path.join(dir, "wywolania.log"), "")
    const t0 = Date.now()
    const out = run(M.actionCommand(dir, "test", "start")).stdout
    assert.deepEqual(M.parseActionResult(out), { ok: true, message: "" })
    assert.ok(Date.now() - t0 < 3000, "start czekał na dziecko: " + (Date.now() - t0))
    assert.equal(read("wywolania.log"), "start:test\n")
    assert.equal(read("stan.test").trim(), "dziala")
    assert.equal(read("stan.glowna").trim(), "dziala")
  })
  it("Start na działającym i bez gry: odmowa pokazana krótko", () => {
    assert.deepEqual(M.parseActionResult(run(M.actionCommand(dir, "test", "start")).stdout), { ok: false, message: "Bot już działa" })
    setState("dwa", "stop")
    fs.writeFileSync(path.join(dir, "brak_gry.dwa"), "")
    assert.deepEqual(M.parseActionResult(run(M.actionCommand(dir, "dwa", "start")).stdout), { ok: false, message: "Gra nie działa" })
  })
  it("Wróć do miasta i Anuluj: wroc.sh dostaje RETRONIC_ID instancji i argument", () => {
    fs.writeFileSync(path.join(dir, "miasto.log"), "")
    assert.deepEqual(M.parseActionResult(run(M.actionCommand(dir, "test", "wroc")).stdout), { ok: true, message: "" })
    assert.deepEqual(M.parseActionResult(run(M.actionCommand(dir, "", "wroc-anuluj")).stdout), { ok: true, message: "" })
    assert.equal(read("miasto.log"), "wroc:test:\nwroc::--anuluj\n")
  })
  it("Refill: refill.sh --tlo wraca od razu mimo odłączonego dziecka; Przerwij dostaje --przerwij", () => {
    fs.writeFileSync(path.join(dir, "miasto.log"), "")
    const t0 = Date.now()
    assert.deepEqual(M.parseActionResult(run(M.actionCommand(dir, "test", "refill")).stdout), { ok: true, message: "" })
    assert.ok(Date.now() - t0 < 3000, "refill czekał na odłączone dziecko: " + (Date.now() - t0))
    assert.deepEqual(M.parseActionResult(run(M.actionCommand(dir, "test", "refill-stop")).stdout), { ok: true, message: "" })
    assert.equal(read("miasto.log"), "refill:test:--tlo\nrefill:test:--przerwij\n")
  })
  it("Spot: refill.sh --spot wraca od razu mimo odłączonego dziecka", () => {
    fs.writeFileSync(path.join(dir, "miasto.log"), "")
    const t0 = Date.now()
    assert.deepEqual(M.parseActionResult(run(M.actionCommand(dir, "test", "spot")).stdout), { ok: true, message: "" })
    assert.ok(Date.now() - t0 < 3000, "spot czekał na odłączone dziecko: " + (Date.now() - t0))
    assert.equal(read("miasto.log"), "refill:test:--spot\n")
  })
  it("Refill z działającym botem: odmowa pokazana krótko", () => {
    fs.writeFileSync(path.join(dir, "bot_dziala"), "")
    try {
      assert.deepEqual(M.parseActionResult(run(M.actionCommand(dir, "", "refill")).stdout), { ok: false, message: "Bot działa: najpierw Stop" })
    } finally {
      fs.rmSync(path.join(dir, "bot_dziala"))
    }
  })
  it("Otwórz okno: okno.sh startuje odłączone, polecenie wraca od razu mimo długo żyjącego okna", () => {
    // atrapa okna: zapisuje wywołanie i żyje 4 s trzymając stdout (jak quickshell), w osobnej sesji
    sh("okno.sh", 'D="$(dirname "$0")"; echo "okno:$$:$(ps -o sid= -p $$ | tr -d " "):$*" >> "$D/okno.log"; sleep 4')
    fs.writeFileSync(path.join(dir, "okno.log"), "")
    const t0 = Date.now()
    const r = run(M.windowCommand(dir))
    assert.deepEqual(M.parseActionResult(r.stdout), { ok: true, message: "" })
    assert.ok(Date.now() - t0 < 3000, "polecenie czekało na okno: " + (Date.now() - t0))
    const wait = Date.now() + 1000
    while (read("okno.log") === "" && Date.now() < wait) { /* daj odłączonemu procesowi wystartować */ }
    const [, pid, sid] = read("okno.log").trim().split(":")
    assert.ok(pid, "okno.sh nie wystartowało")
    assert.equal(sid, pid, "okno.sh powinno być liderem własnej sesji (setsid)")
  })
  it("Otwórz okno: brak okno.sh w katalogu daje czytelny błąd, bez uruchamiania czegokolwiek", () => {
    const r = M.parseActionResult(run(M.windowCommand(path.join(dir, "nie-ma"))).stdout)
    assert.equal(r.ok, false)
    assert.ok(r.message.length > 0 && r.message.length <= M.MAX_ERROR_LENGTH)
  })
  it("brak katalogu pomocnika przy akcji: czytelny błąd", () => {
    const r = M.parseActionResult(run(M.actionCommand(path.join(dir, "nie-ma"), "", "stop")).stdout)
    assert.equal(r.ok, false)
    assert.ok(r.message.length > 0 && r.message.length <= M.MAX_ERROR_LENGTH)
  })
})
