"use strict"

// Uruchom: node --test okno/test/*.test.js   (z katalogu repo bota)
// Sekcja Sesja gry (F4b) i karty postaci (level, podgląd): czyste funkcje OknoModel.js + prawdziwy okno_api `sesja` na ATRAPIE katalogu
// (atrapa.py --sesja; sesja_gry.py w atrapie tylko loguje). Nigdy prawdziwe skrypty akcji ani prawdziwy katalog.

const { describe, it, before, after } = require("node:test")
const assert = require("node:assert/strict")
const fs = require("node:fs")
const os = require("node:os")
const path = require("node:path")
const { spawnSync } = require("node:child_process")
const M = require("../OknoModel.js")
const Rules = require("../../wtyczka-paska/RetronicModel.js")

const REPO = path.resolve(__dirname, "..", "..")

const sesja = (over) => Object.assign({
  ok: true, instancja: "x1", nazwa: "x1", glowna: false, sesja: false, sway_pids: [], gra: false, klient_pids: [], bot: false, proxy: false,
  proxy_pids: [], sesja_sh_pids: [], od: null, podglad: { port: null, otwarty: false, pid: null },
  profil: { jest: true, blad: null, ostrzezenie: null, proxy: "p.example.test:80", user: "fx", ip_oczekiwane: ["10.0.0.1"], postac: "Nick",
            konto_przypisane: true, uwagi: null, start_mozliwy: true },
  tozsamosc: true, ip: null, log_startu: [], log_startu_czas: null, log_akcji: [], log_akcji_plik: null,
  mozna_uruchomic: true, mozna_zamknac: false
}, over || {})

const running = (over) => sesja(Object.assign({
  sesja: true, sway_pids: [1], gra: true, klient_pids: [2], proxy: true, proxy_pids: [3], sesja_sh_pids: [4], od: 1000,
  podglad: { port: 5901, otwarty: false, pid: null }, mozna_uruchomic: false, mozna_zamknac: true,
  ip: { adres: "10.0.0.1", zgodne: true }
}, over || {}))

const main = () => sesja({ instancja: "", nazwa: "główna", glowna: true, profil: null, tozsamosc: false, mozna_uruchomic: false })

describe("sesjaCommand", () => {
  it("polecenie okno_api bez powłoki; zły id = null", () => {
    assert.deepEqual(M.sesjaCommand("/r", "dzial"), ["python3", "-I", "/r/okno_api.py", "sesja", "--instancja", "dzial"])
    assert.deepEqual(M.sesjaCommand("/r", ""), ["python3", "-I", "/r/okno_api.py", "sesja", "--instancja", ""])
    assert.equal(M.sesjaCommand("/r", "Zly Id; rm"), null)
    assert.equal(M.sesjaCommand("", "dzial"), null)
  })
  it("akcje sesji to dokładnie trzy rodzaje z RetronicModel.js", () => {
    for (const k of ["gra-start", "gra-zamknij", "podglad"]) {
      assert.equal(M.isSessionAction(k), true)
      assert.ok(Rules.actionCommand("/h", "dzial", k), k)
    }
    for (const k of ["stop", "start", "refill", "toString", "hasOwnProperty"]) assert.equal(M.isSessionAction(k), false, k)
  })
})

describe("guziki sesji: dostępność i powody", () => {
  it("zatrzymana, profil ok: tylko Uruchom grę", () => {
    const b = M.sessionButtons(sesja())
    assert.equal(b["gra-start"].enabled, true)
    assert.equal(b["gra-zamknij"].enabled, false)
    assert.match(b["gra-zamknij"].hint, /nie ma czego zamykać/)
    assert.equal(b["podglad"].enabled, false)
    assert.equal(b["podglad"].label, "Otwórz podgląd")
  })
  it("działa, podgląd zamknięty: Zamknij i Otwórz podgląd; Uruchom szare z powodem", () => {
    const b = M.sessionButtons(running())
    assert.equal(b["gra-start"].enabled, false)
    assert.match(b["gra-start"].hint, /najpierw Zamknij grę/)
    assert.equal(b["gra-zamknij"].enabled, true)
    assert.equal(b["podglad"].enabled, true)
    assert.equal(b["podglad"].label, "Otwórz podgląd")
  })
  it("podgląd otwarty: ten sam guzik nazywa się Pokaż podgląd (fokus)", () => {
    const b = M.sessionButtons(running({ podglad: { port: 5901, otwarty: true, pid: 77 } }))
    assert.equal(b["podglad"].enabled, true)
    assert.equal(b["podglad"].label, "Pokaż podgląd")
    assert.match(b["podglad"].hint, /fokus/)
  })
  it("sesja wstaje bez portu VNC: podgląd szary z powodem", () => {
    const b = M.sessionButtons(running({ podglad: { port: null, otwarty: false, pid: null } }))
    assert.equal(b["podglad"].enabled, false)
    assert.match(b["podglad"].hint, /portu VNC/)
  })
  it("zostały procesy po sesji (sway nie żyje), ale port VNC jest: Zamknij aktywne, Uruchom szare, podgląd jak Rules.previewState (port = sesja stoi)", () => {
    const s = running({ sesja: false, sway_pids: [], gra: false, podglad: { port: 5901, otwarty: false, pid: null } })
    const b = M.sessionButtons(s)
    assert.equal(b["gra-zamknij"].enabled, true)
    assert.equal(b["gra-start"].enabled, false)
    assert.equal(b["podglad"].enabled, true)
  })
  it("sesja nie działa i nie ma portu: podgląd szary z powodem 'sesja nie działa'", () => {
    const b = M.sessionButtons(sesja())
    assert.equal(b["podglad"].enabled, false)
    assert.match(b["podglad"].hint, /sesja nie działa/)
  })
  it("guzik podglądu w sekcji Sesja = Rules.previewState dla tego samego podglądu (sesja stoi <=> jest port, otwarty zawsze klikalny)", () => {
    for (const pg of [{ port: null, otwarty: false, pid: null }, { port: 5901, otwarty: false, pid: null }, { port: 5901, otwarty: true, pid: 9 }]) {
      for (const live of [true, false]) {
        const s = running({ sesja: live, podglad: pg })
        const status = { ok: true, klasa: "stop", running: false, podglad: pg }
        assert.equal(M.sessionButtons(s)["podglad"].enabled, Rules.previewState(status, "dzial").enabled, JSON.stringify([pg, live]))
      }
    }
  })
  it("brak profilu albo błąd profilu: Uruchom szare z powodem z profilu", () => {
    const brak = sesja({ mozna_uruchomic: false, profil: { jest: false, blad: "brak profil.json: instancja bez stałego profilu", start_mozliwy: false } })
    assert.equal(M.sessionButtons(brak)["gra-start"].enabled, false)
    assert.match(M.sessionButtons(brak)["gra-start"].hint, /brak profil\.json/)
    const kolizja = sesja({ mozna_uruchomic: false, profil: Object.assign({}, sesja().profil, { blad: "IP 10.0.0.1 ma już instancja 'a'", start_mozliwy: false }) })
    assert.match(M.sessionButtons(kolizja)["gra-start"].hint, /^profil: IP 10\.0\.0\.1/)
  })
  it("główna: żaden guzik, powód to ręczne prowadzenie", () => {
    const b = M.sessionButtons(main())
    for (const k of ["gra-start", "gra-zamknij", "podglad"]) {
      assert.equal(b[k].enabled, false, k)
      assert.match(b[k].hint, /ręcznie/, k)
    }
  })
  it("brak odczytu (null): wszystko szare, nic nie wybucha", () => {
    const b = M.sessionButtons(null)
    for (const k of ["gra-start", "gra-zamknij", "podglad"]) assert.equal(b[k].enabled, false, k)
  })
  it("bramka to wyłącznie odpowiedź zaplecza (mozna_*), nie własne zgadywanie okna", () => {
    assert.equal(M.sessionButtons(sesja({ mozna_uruchomic: false }))["gra-start"].enabled, false)
    assert.equal(M.sessionButtons(running({ mozna_zamknac: false }))["gra-zamknij"].enabled, false)
  })
})

describe("potwierdzenie zamknięcia", () => {
  it("bot stoi: jedna linia, bez ostrzeżenia", () => {
    const c = M.closeConfirm(running(), "Nick")
    assert.equal(c.title, "Zamknąć grę Nick?")
    assert.equal(c.botRuns, false)
    assert.equal(c.lines.length, 1)
  })
  it("bot działa: dodatkowe ostrzeżenie o zatrzymaniu bota i postaci w walce", () => {
    const c = M.closeConfirm(running({ bot: true }), "Nick")
    assert.equal(c.botRuns, true)
    assert.equal(c.lines.length, 2)
    assert.match(c.lines[1], /zostanie zatrzymany/)
    assert.match(c.lines[1], /w walce/)
    assert.match(c.lines[1], /zostać w grze/)
  })
})

describe("karta stanu, profil, IP", () => {
  it("czas trwania i 'od kiedy'", () => {
    assert.equal(M.durationLabel(45), "45 s")
    assert.equal(M.durationLabel(12 * 60 + 5), "12 min")
    assert.equal(M.durationLabel(3 * 3600 + 12 * 60), "3 h 12 min")
    assert.equal(M.durationLabel(26 * 3600), "1 d 2 h")
    assert.equal(M.durationLabel(-1), "")
    assert.equal(M.durationLabel(null), "")
    const od = new Date(2026, 9, 20, 11, 42, 0).getTime() / 1000
    assert.equal(M.sinceLabel(od, new Date(2026, 9, 20, 14, 54, 30)), "od 11:42 (3 h 12 min)")
    assert.equal(M.sinceLabel(null, new Date()), "—")
  })
  it("podsumowanie sesji", () => {
    assert.deepEqual(M.sessionSummary(running()), { tone: "ok", text: "działa" })
    assert.equal(M.sessionSummary(running({ gra: false })).tone, "warn")
    assert.equal(M.sessionSummary(running({ sesja: false })).text, "niepełna: zostały procesy sesji")
    assert.deepEqual(M.sessionSummary(sesja()), { tone: "dim", text: "zatrzymana" })
    assert.equal(M.sessionSummary(null).text, "odczyt…")
  })
  it("wiersze stanu: sesja, gra, bot, proxy, podgląd, od", () => {
    const rows = M.stateRows(running({ bot: true, podglad: { port: 5901, otwarty: true, pid: 5 } }), new Date(1010 * 1000))
    assert.deepEqual(rows.map((r) => r.klucz), ["sesja", "gra", "bot", "proxy", "podglad", "od"])
    const by = (k) => rows.find((r) => r.klucz === k)
    assert.equal(by("bot").wartosc, "działa")
    assert.equal(by("podglad").wartosc, "otwarty")
    assert.equal(by("podglad").ton, "blue")
    assert.match(by("od").wartosc, /^od \d\d:\d\d \(10 s\)$/)
    const stopped = M.stateRows(sesja(), new Date())
    assert.equal(stopped.find((r) => r.klucz === "sesja").wartosc, "nie działa")
    assert.equal(stopped.find((r) => r.klucz === "od").wartosc, "—")
    assert.equal(M.stateRows(running(), new Date()).find((r) => r.klucz === "podglad").wartosc, "zamknięty (port 5901)")
    assert.deepEqual(M.stateRows(null, new Date()), [])
  })
  it("odznaka IP: zgodne / spoza profilu / brak", () => {
    assert.deepEqual(M.ipBadge(running()), { tone: "ok", text: "IP 10.0.0.1 zgodne z profilem" })
    assert.deepEqual(M.ipBadge(running({ ip: { adres: "1.2.3.4", zgodne: false } })), { tone: "bad", text: "IP 1.2.3.4 SPOZA profilu" })
    assert.equal(M.ipBadge(sesja()).tone, "dim")
    assert.equal(M.ipBadge(null).tone, "dim")
  })
  it("profil tylko do odczytu: wiersze i brak hasła", () => {
    const rows = M.profileRows(sesja({ profil: Object.assign({}, sesja().profil, { uwagi: "proxy nr 5" }) }))
    assert.deepEqual(rows.map((r) => r.klucz), ["proxy", "user", "ip", "postac", "konto", "tozsamosc", "uwagi"])
    assert.equal(rows[0].wartosc, "p.example.test:80")
    assert.equal(rows[2].wartosc, "10.0.0.1")
    assert.equal(rows[4].wartosc, "przypisane")
    assert.equal(rows[5].wartosc, "jest")
    assert.equal(JSON.stringify(rows).toLowerCase().includes("haslo"), false)
    const brak = M.profileRows(sesja({ tozsamosc: false, profil: Object.assign({}, sesja().profil, { konto_przypisane: false, postac: null }) }))
    assert.equal(brak.find((r) => r.klucz === "konto").ton, "warn")
    assert.equal(brak.find((r) => r.klucz === "tozsamosc").ton, "warn")
    assert.equal(brak.find((r) => r.klucz === "postac").wartosc, "nie wpisana")
    assert.deepEqual(M.profileRows(main()), [])
    assert.deepEqual(M.profileRows(sesja({ profil: { jest: false, blad: "x" } })), [])
  })
  it("błąd ma pierwszeństwo przed ostrzeżeniem profilu", () => {
    const p = (o) => sesja({ profil: Object.assign({}, sesja().profil, o) })
    assert.deepEqual(M.profileNotice(p({ blad: "zle", ostrzezenie: "uwaga" })), { tone: "bad", text: "zle" })
    assert.deepEqual(M.profileNotice(p({ ostrzezenie: "uwaga" })), { tone: "warn", text: "uwaga" })
    assert.equal(M.profileNotice(p({})), null)
    assert.equal(M.profileNotice(main()), null)
  })
})

describe("wynik akcji, podpowiedź, logi", () => {
  it("jedna linia skryptu + RC=0 = sukces z tą linią", () => {
    assert.deepEqual(M.parseSessionAction("sesja a wystartowała\nRC=0\n"), { ok: true, message: "sesja a wystartowała" })
    assert.deepEqual(M.parseSessionAction("RC=0"), { ok: true, message: "Zrobione" })
  })
  it("RC != 0 = błąd z ostatnią linią, 124 = przekroczony czas, brak RC = brak wyniku", () => {
    assert.deepEqual(M.parseSessionAction("odmowa: sesja już działa\nRC=1"), { ok: false, message: "odmowa: sesja już działa" })
    assert.deepEqual(M.parseSessionAction("RC=1"), { ok: false, message: "Błąd (kod 1)" })
    assert.equal(M.parseSessionAction("Przekroczono czas\nRC=124").ok, false)
    assert.match(M.parseSessionAction("Przekroczono czas\nRC=124").message, /Przekroczono czas/)
    assert.deepEqual(M.parseSessionAction(""), { ok: false, message: "Brak wyniku skryptu" })
  })
  it("zamknięcie gry: przekroczony czas albo brak RC to 'trwa dłużej', nie 'Brak wyniku skryptu' (inne akcje bez zmian)", () => {
    const slow = { ok: false, message: "zamykanie trwa dłużej, stan odświeży się sam" }
    assert.deepEqual(M.parseSessionAction("Przekroczono czas\nRC=124", "gra-zamknij"), slow)
    assert.deepEqual(M.parseSessionAction("", "gra-zamknij"), slow)
    assert.deepEqual(M.parseSessionAction("RC=1\n", "gra-zamknij"), { ok: false, message: "Błąd (kod 1)" })
    assert.deepEqual(M.parseSessionAction("gra a zamknięta\nRC=0", "gra-zamknij"), { ok: true, message: "gra a zamknięta" })
    assert.deepEqual(M.parseSessionAction("", "gra-start"), { ok: false, message: "Brak wyniku skryptu" })
    assert.match(M.parseSessionAction("RC=124", "podglad").message, /Przekroczono czas/)
  })
  it("limity czasu: akcje sesji 120 s (zamknij ok. 90 s w najgorszym razie), reszta 25 s", () => {
    assert.equal(M.SESSION_TIMEOUT_MS, 120000)
    for (const k of ["gra-start", "gra-zamknij", "podglad"]) assert.equal(M.actionTimeoutMs(k), 120000, k)
    for (const k of ["stop", "start", "wroc", "refill", "spot", "start-z-tym"]) assert.equal(M.actionTimeoutMs(k), 25000, k)
  })
  it("podpowiedź 'zaloguj postać w podglądzie' tylko po starcie, gdy sesja stoi bez bota", () => {
    assert.match(M.startHint(running(), true), /Zaloguj postać w podglądzie/)
    assert.equal(M.startHint(running(), false), "")
    assert.equal(M.startHint(running({ bot: true }), true), "")
    assert.equal(M.startHint(sesja(), true), "")
    assert.equal(M.startHint(null, true), "")
  })
  it("rada przy IP spoza profilu tylko dla żywej sesji", () => {
    assert.match(M.ipAdvice(running({ ip: { adres: "1.2.3.4", zgodne: false } })), /nie loguj postaci/)
    assert.equal(M.ipAdvice(running()), "")
    assert.equal(M.ipAdvice(sesja({ ip: { adres: "1.2.3.4", zgodne: false } })), "")
    assert.equal(M.ipAdvice(null), "")
  })
  it("ogon logu: ostatnie n niepustych linii, przycięte", () => {
    assert.deepEqual(M.logTail(["a", "", "b", "c"], 2), ["b", "c"])
    assert.deepEqual(M.logTail(null, 3), [])
    assert.equal(M.logTail(["x".repeat(300)], 1, 20)[0].length, 20)
  })
})

describe("karta postaci: level i znacznik podglądu", () => {
  it("level z gracza albo z pola instancji; brak = pusty tekst", () => {
    assert.equal(M.levelText({ gracz: { level: 31 } }), "lvl 31")
    assert.equal(M.levelText({ level: 18 }), "lvl 18")
    assert.equal(M.levelText({ gracz: { hp: 1 }, level: 7 }), "lvl 7")
    assert.equal(M.levelText({ gracz: null, level: null }), "")
    assert.equal(M.levelText({}), "")
    assert.equal(M.levelText({ level: 0 }), "")
    assert.equal(M.levelText({ level: 12.9 }), "lvl 12")
    assert.equal(M.levelText(null), "")
  })
  it("znacznik: otwarty = akcent, zamknięty = przygaszony, brak sesji / główna / nieznany = bez znacznika", () => {
    const id = "x"
    const st = (podglad, klasa) => Rules.parseStatus(M.panelOutput({ panel: { class: klasa || "stop", tooltip: "Retronic: stop", podglad: podglad }, mapa: "", tryb: [] }))
    assert.deepEqual(M.previewMarker(Rules.previewState(st({ port: 5901, otwarty: true, pid: 9 }), id)), { visible: true, filled: true, tone: "blue", label: "podgląd otwarty" })
    assert.deepEqual(M.previewMarker(Rules.previewState(st({ port: 5901, otwarty: false, pid: null }), id)), { visible: true, filled: false, tone: "dim", label: "podgląd zamknięty" })
    assert.equal(M.previewMarker(Rules.previewState(st({ port: null, otwarty: false, pid: null }), id)).visible, false)
    assert.equal(M.previewMarker(Rules.previewState(st({ port: 5901, otwarty: true }), "")).visible, false)
    assert.equal(M.previewMarker(Rules.previewState(null, id)).visible, false)
    assert.equal(M.previewMarker(Rules.previewState(st(undefined), id)).visible, false)       // stary panel.py bez pola: klikalny, bez znacznika
    assert.equal(Rules.previewState(st(undefined), id).enabled, true)
  })
  it("panelOutput dokłada level i podgląd ze `stan`, gdy panel ich nie niesie", () => {
    const i = { panel: { class: "stop", tooltip: "Retronic: stop\nHP 10/10  mana 5/5" }, level: 22, level_procent: 40, podglad: { port: 5900, otwarty: true, pid: 3 }, mapa: "", tryb: [] }
    const s = Rules.parseStatus(M.panelOutput(i))
    assert.equal(s.level, 22)
    assert.equal(s.levelProcent, 40)
    assert.deepEqual(s.podglad, { port: 5900, otwarty: true, pid: 3 })
    // pole z panelu wygrywa; pusty podgląd ze stanu (port null) niczego nie dokłada
    const j = { panel: { class: "stop", tooltip: "Retronic: stop", level: 5, podglad: { port: 1, otwarty: false } }, level: 22, podglad: { port: 5900, otwarty: true }, mapa: "", tryb: [] }
    assert.equal(Rules.parseStatus(M.panelOutput(j)).level, 5)
    assert.equal(Rules.parseStatus(M.panelOutput(j)).podglad.port, 1)
    const k = { panel: { class: "stop", tooltip: "Retronic: stop" }, podglad: { port: null, otwarty: false, pid: null }, mapa: "", tryb: [] }
    assert.equal(Rules.parseStatus(M.panelOutput(k)).podglad, null)
  })
})

describe("okno_api sesja + sesja_gry.py na atrapie (stub tylko loguje)", () => {
  let dir, atrapa
  const run = (cmd) => !atrapa || !atrapa.RETRONIC_OKNO_KATALOG ? assert.fail("brak atrapy: nie wolno uruchamiać na prawdziwym katalogu")
    : spawnSync(cmd[0], cmd.slice(1), { encoding: "utf8", timeout: 15000, env: Object.assign({}, process.env, atrapa) })
  const api = (id) => M.parseApi(run(M.sesjaCommand(REPO, id)).stdout)
  before(() => {
    dir = fs.mkdtempSync(path.join(os.tmpdir(), "okno-sesja-"))
    const r = spawnSync("python3", ["-I", path.join(REPO, "okno", "test", "atrapa.py"), dir, "2", "--sesja"], { encoding: "utf8" })
    assert.equal(r.status, 0, r.stderr)
    atrapa = {}
    for (const l of r.stdout.split("\n")) {
      const m = /^export (\w+)="(.*)"$/.exec(l)
      if (m) atrapa[m[1]] = m[2]
    }
    assert.ok(atrapa.XDG_RUNTIME_DIR && atrapa.XDG_RUNTIME_DIR.startsWith(dir), "atrapa musi izolować XDG_RUNTIME_DIR")
  })
  after(() => fs.rmSync(dir, { recursive: true, force: true }))
  const log = () => fs.readFileSync(path.join(dir, "wywolania.log"), "utf8")

  it("dzial: sesja, bot, proxy, podgląd otwarty, IP zgodne; Zamknij z ostrzeżeniem o bocie", () => {
    const r = api("dzial")
    assert.equal(r.ok, true, JSON.stringify(r))
    const b = M.sessionButtons(r.data)
    assert.equal(b["gra-start"].enabled, false)
    assert.equal(b["gra-zamknij"].enabled, true)
    assert.equal(b["podglad"].label, "Pokaż podgląd")
    assert.equal(M.ipBadge(r.data).tone, "ok")
    assert.equal(M.closeConfirm(r.data, "X").botRuns, true)
    assert.equal(M.sessionSummary(r.data).text, "działa")
    assert.match(M.sinceLabel(r.data.od, new Date()), /^od \d\d:\d\d \(3 h 1\d min\)$/)
  })
  it("ipzle: podgląd zamknięty, IP spoza profilu, ostrzeżenie profilu, bot stoi", () => {
    const r = api("ipzle")
    assert.equal(r.data.bot, false)
    assert.equal(M.sessionButtons(r.data)["podglad"].label, "Otwórz podgląd")
    assert.equal(M.sessionButtons(r.data)["podglad"].enabled, true)
    assert.equal(M.ipBadge(r.data).tone, "bad")
    assert.equal(M.profileNotice(r.data).tone, "warn")
    assert.equal(M.closeConfirm(r.data, "X").botRuns, false)
  })
  it("test: profil ok, sesja zatrzymana: Uruchom aktywne, reszta szara", () => {
    const b = M.sessionButtons(api("test").data)
    assert.equal(b["gra-start"].enabled, true)
    assert.equal(b["gra-zamknij"].enabled, false)
    assert.equal(b["podglad"].enabled, false)
  })
  it("bezprofilu: błąd profilu, Uruchom szare", () => {
    const r = api("bezprofilu")
    assert.equal(M.profileNotice(r.data).tone, "bad")
    assert.equal(M.sessionButtons(r.data)["gra-start"].enabled, false)
    assert.match(M.sessionButtons(r.data)["gra-start"].hint, /brak profil\.json/)
  })
  it("główna: bez profilu i bez guzików", () => {
    const r = api("")
    assert.equal(r.data.glowna, true)
    assert.equal(M.sessionButtons(r.data)["gra-start"].enabled, false)
    assert.deepEqual(M.profileRows(r.data), [])
  })
  it("stan: level i podgląd instancji docierają do reguł karty (Rules.previewState)", () => {
    const stan = M.parseApi(run(M.stanCommand(REPO, null)).stdout)
    assert.equal(stan.ok, true, JSON.stringify(stan))
    const by = (id) => stan.data.instancje.find((i) => i.id === id)
    const state = (id) => Rules.previewState(Rules.parseStatus(M.panelOutput(by(id))), id).state
    assert.equal(state("dzial"), "open")
    assert.equal(state("ipzle"), "closed")
    assert.equal(state("test"), "none")
    assert.equal(state(""), "main")
    assert.equal(M.levelText(by("dzial")), "lvl 58")
    assert.equal(M.levelText(by("")), "lvl 31")
  })
  it("akcje: sesja_gry.py start|zamknij|podglad z RETRONIC_ID i wynikiem w jednej linii", () => {
    for (const [kind, arg, id] of [["gra-start", "start", "test"], ["gra-zamknij", "zamknij", "dzial"], ["podglad", "podglad", "ipzle"]]) {
      const r = run(Rules.actionCommand(atrapa.RETRONIC_OKNO_KATALOG, id, kind))
      const res = M.parseSessionAction(r.stdout)
      assert.equal(res.ok, true, r.stdout)
      assert.match(res.message, new RegExp(id))
      assert.match(log(), new RegExp("^sesja_gry\\.py RETRONIC_ID=" + id + " .*ARGS=\\[" + arg + "\\]$", "m"))
    }
    assert.equal(log().split("\n").filter((l) => l.startsWith("sesja_gry.py")).length, 3)
  })
})

describe("zajętość akcji per instancja (busyIds)", () => {
  it("akcja instancji A nie zajmuje B ani głównej; ta sama instancja jest zajęta", () => {
    let m = {}
    m = M.busyBegin(m, "a")
    assert.equal(M.isBusy(m, "a"), true)
    assert.equal(M.isBusy(m, "b"), false)
    assert.equal(M.isBusy(m, ""), false)
    m = M.busyBegin(m, "")
    assert.equal(M.isBusy(m, ""), true)
    assert.equal(M.isBusy(m, "b"), false)
  })
  it("koniec akcji A zwalnia tylko A; operacje są niezmienne (kopia: binding QML się odświeża)", () => {
    const m0 = M.busyBegin(M.busyBegin({}, "a"), "b")
    const m1 = M.busyEnd(m0, "a")
    assert.notEqual(m1, m0)
    assert.equal(M.isBusy(m0, "a"), true)
    assert.equal(M.isBusy(m1, "a"), false)
    assert.equal(M.isBusy(m1, "b"), true)
    assert.deepEqual(M.busyEnd({}, "x"), {})
  })
  it("brak mapy albo klucz z prototypu nie jest zajęty", () => {
    assert.equal(M.isBusy(undefined, "a"), false)
    assert.equal(M.isBusy({}, "toString"), false)
    assert.equal(M.isBusy({}, "constructor"), false)
  })
})
