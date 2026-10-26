"use strict"

// Uruchom: node --test okno/test/*.test.js   (z katalogu repo bota)
// Testy poleceń (Start z tym, ratunek-oznacz) chodzą na ATRAPIE katalogu (atrapa.py, stuby tylko logują), nigdy na prawdziwych skryptach.

const { describe, it, before, after } = require("node:test")
const assert = require("node:assert/strict")
const fs = require("node:fs")
const os = require("node:os")
const path = require("node:path")
const { spawnSync } = require("node:child_process")
const M = require("../OknoModel.js")
const Rules = require("../../wtyczka-paska/RetronicModel.js")

const REPO = path.resolve(__dirname, "..", "..")

const panelJson = (over) => JSON.stringify(Object.assign({
  text: "RT", tooltip: "Retronic: działa\nTryb: mozg.py skrypt, działa 1h 08m\nHP 250/250  mana 25/425", class: "dziala", alt: "dziala",
  pozycja: [1, 2, 8], w_miescie: null, w_depo: false, plan_depo_dostepny: true, wroc_oczekuje: false, wroc_w_marszu: false,
  serwis_dziala: false, serwis_krok: null, serwis_ukonczone: [], serwis_tryb: null, serwis_wynik: null, serwis_komunikat: "", serwis_wiek_s: null
}, over || {}))

const inst = (over) => Object.assign({
  id: "", nazwa: "główna", blad: null, panel: JSON.parse(panelJson()), klasa: "dziala", gracz: { hp: 250, max_hp: 250, mana: 25, max_mana: 425 },
  gra: true, sesja: true, bot: true, nick: "Mastafian", mapa: "gobliny_edron", tryb: ["ostrozny", "wyprawa"], ratunek_dzis: 3
}, over || {})

describe("polecenia okno_api (bez powłoki)", () => {
  it("stan: wszystkie albo jedna instancja", () => {
    assert.deepEqual(M.stanCommand("/r", null), ["python3", "-I", "/r/okno_api.py", "stan"])
    assert.deepEqual(M.stanCommand("/r", ""), ["python3", "-I", "/r/okno_api.py", "stan", "--instancja", ""])
    assert.deepEqual(M.stanCommand("/r", "test"), ["python3", "-I", "/r/okno_api.py", "stan", "--instancja", "test"])
  })
  it("odrzuca ID spoza wzoru bota", () => {
    assert.equal(M.stanCommand("/r", "Te st"), null)
    assert.equal(M.ratunekCommand("/r", "../x"), null)
    assert.equal(M.mapyCommand("/r", "a;rm"), null)
    assert.equal(M.apiCommand("", ["stan"]), null)
  })
  it("ratunek-oznacz tylko z poprawnym id sygnału", () => {
    assert.deepEqual(M.oznaczCommand("/r", "test", "51ea7f38e032"),
      ["python3", "-I", "/r/okno_api.py", "ratunek-oznacz", "--instancja", "test", "--id", "51ea7f38e032", "--falszywy"])
    assert.deepEqual(M.oznaczCommand("/r", "", "51ea7f38e032-2"),
      ["python3", "-I", "/r/okno_api.py", "ratunek-oznacz", "--instancja", "", "--id", "51ea7f38e032-2", "--falszywy"])
    assert.equal(M.oznaczCommand("/r", "test", "x; rm -rf"), null)
    assert.equal(M.oznaczCommand("/r", "test", "../../etc"), null)
  })
  it("Start z tym: argumenty pozycyjne, nigdy sklejone w skrypt; walidacja nazw", () => {
    const c = M.startCommand("/h", "test", "raty", ["ml", "ostrozny"], "Johny Dang")
    assert.deepEqual(c.slice(0, 2), ["bash", "-c"])
    assert.equal(c[2], M.START_SCRIPT)
    assert.deepEqual(c.slice(4), ["test", "/h", "raty", "ml,ostrozny", "Johny Dang"])
    assert.ok(!M.START_SCRIPT.includes("raty") && !M.START_SCRIPT.includes("Johny"))
    assert.equal(M.startCommand("/h", "test", "", [], ""), null)
    assert.equal(M.startCommand("/h", "test", "r a;ty", [], ""), null)
    assert.equal(M.startCommand("/h", "test", "raty", ["ml;x"], ""), null)
    assert.equal(M.startCommand("/h", "Bad Id", "raty", [], ""), null)
  })
  it("nick spoza wzoru nie trafia do RETRONIC_POSTAC", () => {
    assert.equal(M.startCommand("/h", "", "raty", [], "x; rm")[8], "")
    assert.equal(M.startCommand("/h", "", "raty", [], null)[8], "")
  })
})

describe("odpowiedzi API", () => {
  it("parseApi: sukces, błąd zaplecza, śmieci", () => {
    assert.equal(M.parseApi('{"ok": true, "x": 1}\n').data.x, 1)
    assert.deepEqual(M.parseApi('{"ok": false, "blad": "nie ma"}'), { ok: false, blad: "nie ma" })
    assert.equal(M.parseApi("").ok, false)
    assert.equal(M.parseApi("Traceback…").blad, "brak odczytu")
    assert.equal(M.parseApi("{nie json").blad, "błędny JSON")
  })
  it("mergeInstances: pełna lista podmienia wszystko, jedna instancja tylko swój wpis (kolejność zostaje)", () => {
    const cur = [inst({ id: "" }), inst({ id: "test", nick: "A" })]
    assert.deepEqual(M.mergeInstances(cur, [inst({ id: "x" })], null).map((i) => i.id), ["x"])
    const out = M.mergeInstances(cur, [inst({ id: "test", nick: "B" })], "test")
    assert.deepEqual(out.map((i) => i.id), ["", "test"])
    assert.equal(out[1].nick, "B")
    assert.equal(M.mergeInstances([], [inst({ id: "a" })], "a").length, 1)
  })
})

describe("status instancji = ten sam kształt i reguły co na pasku", () => {
  const st = (i) => Rules.parseStatus(M.panelOutput(i))
  it("działający bot: Stop, Miasto aktywne, Refill i Spot szare", () => {
    const s = st(inst())
    assert.equal(s.ok, true)
    assert.equal(s.running, true)
    assert.equal(s.czas, "1h 08m")
    assert.equal(s.lastMap, "gobliny_edron")
    assert.equal(s.lastMode, "ostrozny,wyprawa")
    assert.equal(Rules.buttonKind(s), "stop")
    assert.equal(Rules.returnButton(s).action, "wroc")
    assert.equal(Rules.refillButton(s).enabled, false)
    assert.equal(Rules.spotButton(s).enabled, false)
  })
  it("stojący bot w mieście: Start, Refill i Spot aktywne, Miasto szare", () => {
    const s = st(inst({ panel: JSON.parse(panelJson({ class: "stop", tooltip: "Retronic: stop", w_miescie: "edron" })), klasa: "stop", bot: false }))
    assert.equal(s.running, false)
    assert.equal(Rules.buttonKind(s), "start")
    assert.equal(Rules.buttonEnabled(s), true)
    assert.equal(Rules.refillButton(s).action, "refill")
    assert.equal(Rules.spotButton(s).action, "spot")
    assert.equal(Rules.returnButton(s).enabled, false)
  })
  it("brak panelu = brak odczytu, wszystko szare", () => {
    const s = st(inst({ panel: null }))
    assert.equal(s.ok, false)
    assert.equal(Rules.buttonEnabled(s), false)
    assert.equal(Rules.refillButton(s).enabled, false)
  })
  it("Start z tym: aktywny tylko gdy bot stoi, jest gra, brak serwisu i wybrana mapa", () => {
    const stoi = st(inst({ panel: JSON.parse(panelJson({ class: "stop", tooltip: "x", w_miescie: "edron" })) }))
    assert.deepEqual(M.startState(stoi, "raty"), { enabled: true, reason: "" })
    assert.equal(M.startState(stoi, "").reason, "wybierz mapę")
    assert.match(M.startState(st(inst()), "raty").reason, /działa/)
    assert.equal(M.startState(st(inst({ panel: JSON.parse(panelJson({ class: "brak", tooltip: "x" })) })), "raty").reason, "gra nie działa")
    const serwis = st(inst({ panel: JSON.parse(panelJson({ class: "stop", tooltip: "x", serwis_dziala: true })) }))
    assert.equal(M.startState(serwis, "raty").enabled, false)
    assert.equal(M.startState(null, "raty").enabled, false)
  })
})

describe("pasek boczny", () => {
  it("etykieta instancji, nick i podtytuł karty", () => {
    assert.equal(M.instanceLabel(inst()), "główna")
    assert.equal(M.instanceLabel(inst({ id: "test" })), "test")
    assert.equal(M.instanceLabel(inst({ id: "test", proxy: true })), "test · proxy")
    assert.equal(M.nickOf(inst({ nick: null, id: "test" })), "test")
    assert.equal(M.cardSubtitle(inst()), "gobliny_edron · ostrozny, wyprawa")
    assert.equal(M.cardSubtitle(inst({ mapa: null, tryb: [] })), "brak ostatniego startu")
  })
  it("ułamki HP/MP w granicach", () => {
    assert.equal(M.hpFraction(inst()), 1)
    assert.ok(Math.abs(M.mpFraction(inst()) - 25 / 425) < 1e-9)
    assert.equal(M.hpFraction(inst({ gracz: null })), 0)
    assert.equal(M.fraction(300, 250), 1)
    assert.equal(M.fraction(-5, 250), 0)
    assert.equal(M.fraction(5, 0), 0)
  })
  it("stopka: liczba działających i zdanie dla 10 postaci", () => {
    const list = []
    const statuses = {}
    for (let i = 0; i < 10; i++) {
      const id = i === 0 ? "" : "p" + i
      list.push(inst({ id, nick: "N" + i }))
      statuses[id] = Rules.parseStatus(M.panelOutput(inst({ id })))
    }
    assert.equal(M.runningCount(list, statuses), 10)
    assert.equal(M.pluralBots(1), "bot działa")
    assert.equal(M.pluralBots(2), "boty działają")
    assert.equal(M.pluralBots(5), "botów działa")
    assert.equal(M.pluralBots(12), "botów działa")
    assert.equal(M.footerSummary(list.slice(0, 2), statuses, Rules.stateLabel), "N0 działa 1h 08m · N1 działa 1h 08m")
  })
})

describe("Ratunek", () => {
  const sig = (over) => Object.assign({
    id: "aaaaaaaaaaaa", czas: "2026-10-19 21:04:41", kod: "S4", opis: "kręci się", poz: [33107, 31874, 8], stan: "IDZ", tryb: "cien",
    plik: "ratunek-20261019.jsonl", linia: 7, etykieta: null,
    dane: { wizyt: 3, oscylacje: 3, okno_s: 60, kod: "S4", opis: "kręci się", t: 1, poz: [1, 2, 8], wolan_h: 5, ponad_limit: false, tryb: "cien", stan: "IDZ", czas: "x" }
  }, over || {})
  const now = new Date(2026, 9, 19, 22, 0, 0)

  it("czas: dzisiejsze godziną, starsze z datą", () => {
    assert.equal(M.signalTime("2026-10-19 21:04:41", now), "21:04:41")
    assert.equal(M.signalTime("2026-10-18 22:06:07", now), "10-18 22:06")
    assert.equal(M.signalTime(null, now), "?")
  })
  it("miejsce i kod", () => {
    assert.equal(M.pozLabel([33107, 31874, 8]), "33107, 31874, z8")
    assert.equal(M.pozLabel(null), "?")
    assert.equal(M.pozLabel({ length: 3, 0: 1, 1: 2, 2: 7 }), "1, 2, z7")       // tablica z QML-a
    assert.equal(M.codeTone("S4"), "warn")
    assert.equal(M.codeTone("S6"), "mag")
    assert.equal(M.codeTone("S9"), "dim")
  })
  it("liczby detektora: czytelna kolejność, tylko pola ponad podstawowe", () => {
    const s = sig({ dane: { okno_s: 60, oscylacje: 3, wizyt: 4, kod: "S4", t: 1 } })
    assert.equal(M.signalSummary(s), "kręci się · wizyty 4, powroty 3")
    assert.equal(M.numbersLine(s), "wizyty pola 4, powroty 3, okno (s) 60")
    assert.equal(M.numbersLine(sig({ dane: { kod: "S4" } })), "brak")
    assert.equal(M.signalSummary(sig({ opis: "klik bez skutku", dane: { n: 5, cel: "Troll" } })), "klik bez skutku · cel Troll, razy 5")
  })
  it("Haiku: brak pola = 'Haiku: brak'; tekst i obiekt", () => {
    assert.equal(M.haikuLabel(sig()), "Haiku: brak")
    assert.equal(M.haikuText(sig()), null)
    assert.equal(M.haikuLabel(sig({ dane: { haiku_cien: "zatrzymać" } })), "zatrzymać")
    assert.equal(M.haikuText(sig({ dane: { haiku_cien: { odpowiedz: "wróć", model: "haiku" } } })), "wróć")
    assert.equal(M.haikuText(sig({ dane: { haiku_cien: { x: 1 } } })), '{"x":1}')
    assert.equal(M.haikuText(sig({ dane: { haiku_cien: "" } })), null)
    assert.equal(M.haikuText(sig({ dane: { haiku_cien: { ruch: "krok N", powod: null, dlaczego: "drabina na północ", czas_wywolania_s: 2.1, blad: null } } })),
      "krok N — drabina na północ · 2.1 s")
    assert.equal(M.haikuText(sig({ dane: { haiku_cien: { ruch: "czlowiek", powod: "timeout", dlaczego: "", blad: "timeout" } } })),
      "czlowiek (timeout) · błąd: timeout")
    assert.equal(M.haikuText(sig({ dane: { haiku_cien: { ruch: null, pominiety: "limit_h" } } })), "pominięty: limit_h")
  })
  it("filtry: dziś i kod; cykl kodów", () => {
    const list = [sig(), sig({ id: "b", czas: "2026-10-18 10:00:00", kod: "S6" }), sig({ id: "c", kod: "S3" })]
    assert.deepEqual(M.filterSignals(list, "dzis", "", now).map((s) => s.id), ["aaaaaaaaaaaa", "c"])
    assert.deepEqual(M.filterSignals(list, "7dni", "S6", now).map((s) => s.id), ["b"])
    assert.deepEqual(M.signalCodes(list), ["S3", "S4", "S6"])
    assert.equal(M.nextCode(["S3", "S4"], ""), "S3")
    assert.equal(M.nextCode(["S3", "S4"], "S3"), "S4")
    assert.equal(M.nextCode(["S3", "S4"], "S4"), "")
    assert.equal(M.nextCode([], ""), "")
  })
  it("liczniki z odpowiedzi ratunek, także gdy dane jeszcze nie przyszły", () => {
    const c = M.counters({ sygnaly: [sig(), sig({ dane: { haiku_cien: "x" } })], liczniki: { dzis: 7, ostatnia_godzina: 5, limit_h: 20, haiku: 1,
      najczestszy_kod: { kod: "S4", ile: 7, opis: "kręci się" }, falszywe: 1 } })
    assert.deepEqual([c.dzis, c.godzina, c.limit, c.kod, c.kodOpis, c.haikuOn, c.haiku, c.falszywe], [7, 5, 20, "S4", "S4 kręci się", true, "włączony · odpowiedzi 1", 1])
    const e = M.counters(null)
    assert.deepEqual([e.dzis, e.limit, e.kodOpis, e.haiku], [0, null, "brak", "wyłączony"])
  })
  it("ścieżka logu i etykieta", () => {
    assert.equal(M.logPath({ katalog_logow: "/k/logi" }, sig()), "/k/logi/ratunek-20261019.jsonl")
    assert.equal(M.logPath(null, sig()), "")
    assert.equal(M.labelText(sig({ etykieta: "falszywy" })), "oznaczony: fałszywy alarm")
    assert.equal(M.labelText(sig()), "")
  })
})

describe("Mapa i tryb", () => {
  it("przełączanie trybów zachowuje kolejność kliknięć i nie mutuje", () => {
    const a = ["ml"]
    assert.deepEqual(M.toggleMode(a, "ostrozny"), ["ml", "ostrozny"])
    assert.deepEqual(M.toggleMode(["ml", "ostrozny"], "ml"), ["ostrozny"])
    assert.deepEqual(a, ["ml"])
  })
  it("wybór równy ostatniemu niezależnie od kolejności trybów", () => {
    const last = { mapa: "raty", tryb: ["ml", "ostrozny"] }
    assert.equal(M.isLastChoice(last, "raty", ["ostrozny", "ml"]), true)
    assert.equal(M.isLastChoice(last, "raty", ["ml"]), false)
    assert.equal(M.isLastChoice(last, "inna", ["ml", "ostrozny"]), false)
    assert.equal(M.isLastChoice(null, "raty", []), false)
    assert.equal(M.chosenText("raty", ["ml", "ostrozny"]), "mapa raty, tryb ml, ostrozny")
    assert.equal(M.chosenText("raty", []), "mapa raty, tryb bez trybu")
  })
})

describe("polecenia na atrapie (stuby tylko logują)", () => {
  let dir, atrapa
  const run = (cmd, extraEnv) => !atrapa || !atrapa.RETRONIC_OKNO_KATALOG ? assert.fail("brak atrapy: nie wolno uruchamiać na prawdziwym katalogu") : spawnSync(cmd[0], cmd.slice(1), { encoding: "utf8", timeout: 15000, env: Object.assign({}, process.env, atrapa, extraEnv) })
  before(() => {
    dir = fs.mkdtempSync(path.join(os.tmpdir(), "okno-test-"))
    const r = spawnSync("python3", ["-I", path.join(REPO, "okno", "test", "atrapa.py"), dir], { encoding: "utf8" })
    assert.equal(r.status, 0, r.stderr)
    atrapa = {}
    for (const l of r.stdout.split("\n")) {
      const m = /^export (\w+)="(.*)"$/.exec(l)
      if (m) atrapa[m[1]] = m[2]
    }
  })
  after(() => fs.rmSync(dir, { recursive: true, force: true }))
  const log = () => fs.readFileSync(path.join(dir, "wywolania.log"), "utf8")

  it("Start z tym woła uruchom.sh z RETRONIC_ID, MAPA, TRYB i nickiem; wynik RC=0", () => {
    const r = run(M.startCommand(atrapa.RETRONIC_OKNO_KATALOG, "test", "raty", ["ml", "ostrozny"], "Johny Dang"))
    assert.equal(Rules.parseActionResult(r.stdout).ok, true)
    assert.match(log(), /^uruchom\.sh RETRONIC_ID=test MAPA=raty TRYB=ml,ostrozny POSTAC=Johny Dang ARGS=\[\]$/m)
  })
  it("Start z tym dla głównej: bez RETRONIC_ID", () => {
    run(M.startCommand(atrapa.RETRONIC_OKNO_KATALOG, "", "raty", [], ""), { RETRONIC_ID: "zly" })
    assert.match(log(), /^uruchom\.sh RETRONIC_ID=<brak> MAPA=raty TRYB= POSTAC=<brak> ARGS=\[\]$/m)
  })
  it("akcje paska (Rules.actionCommand) dostają ID instancji", () => {
    run(Rules.actionCommand(atrapa.RETRONIC_OKNO_KATALOG, "test", "refill"))
    run(Rules.actionCommand(atrapa.RETRONIC_OKNO_KATALOG, "test", "spot"))
    assert.match(log(), /^refill\.sh RETRONIC_ID=test .*ARGS=\[--tlo\]$/m)
    assert.match(log(), /^refill\.sh RETRONIC_ID=test .*ARGS=\[--spot\]$/m)
  })
  it("okno_api stan / ratunek / mapy-tryby na atrapie: kontrakt, którego używa model", () => {
    const stan = M.parseApi(run(M.stanCommand(REPO, null)).stdout)
    assert.equal(stan.ok, true, JSON.stringify(stan))
    assert.deepEqual(stan.data.instancje.map((i) => i.id), ["", "test"])
    assert.equal(Rules.parseStatus(M.panelOutput(stan.data.instancje[0])).running, true)
    assert.equal(Rules.parseStatus(M.panelOutput(stan.data.instancje[1])).running, false)
    const rat = M.parseApi(run(M.ratunekCommand(REPO, "")).stdout)
    assert.equal(rat.ok, true)
    assert.ok(rat.data.sygnaly.length >= 4)
    assert.equal(M.haikuText(rat.data.sygnaly[0]) !== null, true)
    const mt = M.parseApi(run(M.mapyCommand(REPO, "test")).stdout)
    assert.deepEqual(mt.data.ostatni.tryb, ["ml", "ostrozny"])
  })
  it("ratunek-oznacz dopisuje etykietę i API ją zwraca", () => {
    const rat = M.parseApi(run(M.ratunekCommand(REPO, "test")).stdout).data
    const id = rat.sygnaly[0].id
    const ozn = M.parseApi(run(M.oznaczCommand(REPO, "test", id)).stdout)
    assert.equal(ozn.ok, true)
    assert.equal(M.parseApi(run(M.ratunekCommand(REPO, "test")).stdout).data.sygnaly[0].etykieta, "falszywy")
    assert.equal(M.parseApi(run(M.oznaczCommand(REPO, "test", "000000000000")).stdout).ok, false)
  })
})

// ---------------------------------------------------------------- „Zaloguj postać” (24.10): stany guzika, wynik skryptu, limit czasu, polecenie
describe("zaloguj postać: stan guzika (loginState)", () => {
  const ekran = (over) => Object.assign({ id: "ekran", panel: { pozycja: null }, gracz: null, bot: false, sesja: true, gra: true, klient_pids: [1], przeglad: { stracony: false, w_grze: true } }, over)
  const nic = { loginId: "", busy: false }

  it("ekran logowania (sesja stoi, pozycja null, bez gracza i bota): aktywny, podpowiedź bez bota", () => {
    const s = M.loginState(ekran(), nic)
    assert.equal(s.enabled, true)
    assert.equal(s.busy, false)
    assert.equal(s.reason, "")
    assert.match(s.hint, /BEZ uruchamiania bota/)
    assert.doesNotMatch(s.hint, /uruchomi sesję/)
  })
  it("brak sesji: aktywny, podpowiedź mówi, że sesja wystartuje", () => {
    const s = M.loginState(ekran({ sesja: false, gra: false, klient_pids: [], przeglad: { w_grze: false } }), nic)
    assert.equal(s.enabled, true)
    assert.match(s.hint, /uruchomi sesję gry, potwierdzi IP proxy/)
  })
  it("w grze: pozycja z panelu, gracz z telemetrii albo działający bot = szary „już w grze”", () => {
    for (const over of [{ panel: { pozycja: [1, 2, 8] } }, { gracz: { hp: 1 } }, { bot: true }]) {
      const s = M.loginState(ekran(over), nic)
      assert.equal(s.enabled, false)
      assert.equal(s.reason, "in-game")
      assert.equal(s.hint, "już w grze")
    }
  })
  it("w_grze z Przeglądu (klient stoi) NIE znaczy „zalogowana”: ekran logowania zostaje aktywny", () => {
    assert.equal(M.loggedIn(ekran({ przeglad: { w_grze: true } })), false)
  })
  it("stracona (profil): szara, nawet na ekranie logowania i nawet gdy w grze", () => {
    for (const over of [{}, { bot: true }]) {
      const s = M.loginState(ekran(Object.assign({ przeglad: { stracony: true, w_grze: true } }, over)), nic)
      assert.equal(s.enabled, false)
      assert.equal(s.reason, "lost")
      assert.match(s.hint, /stracona/)
    }
  })
  it("główna instancja (id pusty): szara z powodem, okno jej nie dotyka", () => {
    const s = M.loginState(ekran({ id: "" }), nic)
    assert.equal(s.enabled, false)
    assert.equal(s.reason, "main")
    assert.match(s.hint, /główna instancja loguje się ręcznie/)
  })
  it("jedno logowanie naraz: własne = busy „Loguję…”, cudze = szare z nazwą postaci", () => {
    const own = M.loginState(ekran(), { loginId: "ekran", busy: true })
    assert.deepEqual([own.enabled, own.busy, own.label, own.reason], [false, true, "Loguję…", "login"])
    const other = M.loginState(ekran({ id: "bezsesji" }), { loginId: "ekran", busy: false })
    assert.deepEqual([other.enabled, other.busy, other.reason], [false, false, "other"])
    assert.match(other.hint, /trwa logowanie innej postaci \(ekran\): jedno naraz/)
  })
  it("inna akcja tej instancji w toku (Start, Zamknij grę): szare; brak odczytu: szare", () => {
    assert.equal(M.loginState(ekran(), { loginId: "", busy: true }).reason, "busy")
    assert.equal(M.loginState(null, nic).enabled, false)
    assert.equal(M.loginState(ekran(), undefined).enabled, true)
  })
  it("pierwszeństwo: stracona > własne logowanie > cudze > w grze > zajęta", () => {
    assert.equal(M.loginState(ekran({ bot: true }), { loginId: "x", busy: true }).reason, "other")
    assert.equal(M.loginState(ekran({ bot: true }), { loginId: "ekran", busy: true }).reason, "login")
    assert.equal(M.loginState(ekran({ bot: true }), { loginId: "", busy: true }).reason, "in-game")
  })
})

describe("zaloguj postać: wynik skryptu i limit czasu", () => {
  it("RC=0: ok i zdanie skryptu; bez zdania: domyślne", () => {
    assert.deepEqual(M.parseLoginResult("Postać zalogowana (albo już była w grze); bot nie został uruchomiony\nRC=0"),
                     { ok: true, message: "Postać zalogowana (albo już była w grze); bot nie został uruchomiony" })
    assert.match(M.parseLoginResult("RC=0").message, /bot nie został uruchomiony/)
  })
  it("kody błędów: ostatnia linia skryptu po polsku, bez obcinania do 48 znaków", () => {
    const r = M.parseLoginResult("jakieś wyjście\nIP wyjściowe SPOZA profilu: nie loguję. Zamknij grę (Sesja gry) i sprawdź proxy w profilu\nRC=24")
    assert.equal(r.ok, false)
    assert.equal(r.message, "IP wyjściowe SPOZA profilu: nie loguję. Zamknij grę (Sesja gry) i sprawdź proxy w profilu")
    assert.equal(M.parseLoginResult("Postać dawajkesh jest stracona (profil `stracony`): nie loguję\nRC=21").ok, false)
  })
  it("timeout (RC=124) i brak RC mają osobne komunikaty; bardzo długa linia jest przycięta", () => {
    assert.match(M.parseLoginResult("Przekroczono czas\nRC=124").message, /przerwane po 4 min/)
    assert.match(M.parseLoginResult("cokolwiek").message, /Brak wyniku/)
    assert.match(M.parseLoginResult("").message, /Brak wyniku/)
    const dl = M.parseLoginResult("x".repeat(400) + "\nRC=1").message
    assert.equal(dl.length, 160)
    assert.match(M.parseLoginResult("RC=7").message, /kod 7/)
  })
  it("limit czasu 240 s tylko dla zaloguj; reszta bez zmian (25 s akcje, 120 s sesja)", () => {
    assert.equal(M.actionTimeoutMs("zaloguj"), 240000)
    assert.equal(M.actionTimeoutMs("stop"), 25000)
    assert.equal(M.actionTimeoutMs("gra-zamknij"), 120000)
    assert.equal(M.isSessionAction("zaloguj"), false)          // nie przechodzi przez onSessionAction
  })
  it("polecenie: zaloguj_postac.sh z ID instancji, bez argumentów; główna (pusty id) bez polecenia", () => {
    const cmd = Rules.actionCommand("/x/pomocnik", "ekran", "zaloguj")
    assert.deepEqual(cmd.slice(0, 2), ["bash", "-c"])
    assert.equal(cmd[cmd.length - 1], "zaloguj_postac.sh")
    assert.equal(cmd[3], "retronic-zaloguj")
    assert.equal(cmd[4], "ekran")
    assert.equal(Rules.actionCommand("/x/pomocnik", "", "zaloguj"), null)
  })
})
