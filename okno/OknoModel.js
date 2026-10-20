// Model okna zarządzania Retronic: czysta logika bez Quickshella (testy: node --test okno/test/*.test.js).
// Okno jest cienkie: czyta JSON z okno_api.py (zaplecze F1) i woła skrypty bota. Reguły szarości akcji (Stop/Start,
// Miasto, Refill, Spot) NIE są tu powielane: komponenty QML biorą je z ../wtyczka-paska/RetronicModel.js (ten sam plik co pasek),
// a ten model tylko składa z odpowiedzi `okno_api stan` obiekt statusu w kształcie, który tamte reguły rozumieją (panelOutput).
//
// Kontrakt (okno_api.py):
//   stan [--instancja ID]            {"instancje":[{id,nazwa,panel,klasa,gracz,gra,sesja,bot,nick,mapa,tryb,ratunek_dzis,blad,...}]}
//   ratunek --instancja ID           {"sygnaly":[{id,czas,kod,opis,poz,stan,tryb,plik,linia,dane,etykieta}],"liczniki":{...},"katalog_logow"}
//   ratunek-oznacz --instancja ID --id X --falszywy
//   mapy-tryby --instancja ID        {"mapy":[{nazwa,opis}],"tryby":[{nazwa,opis,ile_pokretel}],"ostatni":{mapa,tryb[],...}}
//   sesja --instancja ID             (F4) {sesja,gra,bot,proxy,od,podglad{port,otwarty,pid},profil{...}|null,tozsamosc,ip{adres,zgodne}|null,
//                                    log_startu[],log_akcji[],mozna_uruchomic,mozna_zamknac,...}; akcje: gra-start | gra-zamknij | podglad

var NAME_PATTERN = /^[A-Za-z0-9][A-Za-z0-9_.-]{0,63}$/
var SIGNAL_ID_PATTERN = /^[0-9a-f]{12}(-[0-9]+)?$/
var NICK_PATTERN = /^[A-Za-z][A-Za-z' -]{1,29}$/
var ID_PATTERN = /^[a-z0-9][a-z0-9_-]{0,23}$/          // jak w modelu paska i instancja.py

function validId(id) {
  return id === "" || ID_PATTERN.test(String(id))
}

// ---------------------------------------------------------------- polecenia (bez powłoki, argumenty pozycyjne)

function apiCommand(repoDir, args) {
  if (!repoDir) return null
  return ["python3", "-I", repoDir + "/okno_api.py"].concat(args)
}

// id === null: wszystkie instancje (odświeżanie co 5 s); inaczej tylko ta jedna (co 2 s).
function stanCommand(repoDir, id) {
  if (id === null) return apiCommand(repoDir, ["stan"])
  if (!validId(id)) return null
  return apiCommand(repoDir, ["stan", "--instancja", String(id)])
}

function ratunekCommand(repoDir, id) {
  if (!validId(id)) return null
  return apiCommand(repoDir, ["ratunek", "--instancja", String(id)])
}

function mapyCommand(repoDir, id) {
  if (!validId(id)) return null
  return apiCommand(repoDir, ["mapy-tryby", "--instancja", String(id)])
}

function oznaczCommand(repoDir, id, signalId) {
  if (!validId(id) || !SIGNAL_ID_PATTERN.test(String(signalId))) return null
  return apiCommand(repoDir, ["ratunek-oznacz", "--instancja", String(id), "--id", String(signalId), "--falszywy"])
}

function sesjaCommand(repoDir, id) {
  if (!validId(id)) return null
  return apiCommand(repoDir, ["sesja", "--instancja", String(id)])
}

// "Start z tym": uruchom.sh z MAPA/TRYB i RETRONIC_ID (+ RETRONIC_POSTAC, gdy znany nick). Skrypt jak ACTION_SCRIPT paska:
// wynik do pliku tymczasowego, na końcu RC=<kod>, zawsze exit 0. Wartości idą jako $1..$5, nigdy sklejone w tekst skryptu.
var START_SCRIPT = [
  'ID="$1"; DIR="$2"; MAPA="$3"; TRYB="$4"; POSTAC="$5"',
  'if [ -n "$ID" ]; then export RETRONIC_ID="$ID"; else unset RETRONIC_ID; fi',
  'if [ -n "$POSTAC" ]; then export RETRONIC_POSTAC="$POSTAC"; fi',
  'export MAPA TRYB',
  'f=$(mktemp) || { echo "RC=1"; exit 0; }',
  'cd "$DIR" 2>/dev/null || { echo "brak katalogu pomocnika"; echo "RC=1"; rm -f "$f"; exit 0; }',
  '"$DIR/uruchom.sh" > "$f" 2>&1 < /dev/null',
  'rc=$?',
  'tail -c 600 "$f"; echo',
  'rm -f "$f"',
  'echo "RC=$rc"',
  'exit 0'
].join("\n")

function startCommand(helperDir, id, mapa, tryby, nick) {
  if (!helperDir || !validId(id) || !NAME_PATTERN.test(String(mapa || ""))) return null
  var list = tryby || []
  for (var i = 0; i < list.length; i++) if (!NAME_PATTERN.test(String(list[i]))) return null
  var postac = nick && NICK_PATTERN.test(String(nick)) ? String(nick) : ""
  return ["bash", "-c", START_SCRIPT, "retronic-okno-start", String(id), helperDir, String(mapa), list.join(","), postac]
}

// ---------------------------------------------------------------- odpowiedzi API

// Wyjście okno_api.py -> {ok, data} | {ok:false, blad}. Czyta pierwszą linię JSON (API drukuje jedną).
function parseApi(output) {
  var lines = String(output || "").split("\n")
  var json = null
  for (var i = 0; i < lines.length; i++) {
    if (lines[i].charAt(0) === "{") { json = lines[i]; break }
  }
  if (json === null) return { ok: false, blad: "brak odczytu" }
  var data
  try { data = JSON.parse(json) } catch (e) { return { ok: false, blad: "błędny JSON" } }
  if (!data || typeof data !== "object") return { ok: false, blad: "błędny JSON" }
  if (data.ok !== true) return { ok: false, blad: String(data.blad || "błąd zaplecza") }
  return { ok: true, data: data }
}

// Odpowiedź `stan` jednej instancji -> tekst w formacie, który zna Rules.parseStatus (linia JSON panel.py, PROXY, --ENV--).
// Proxy: okno_api stan go nie podaje (zaplecze F1), więc linii PROXY brak = proxy nieznane. Brak panelu = brak odczytu.
function panelOutput(inst) {
  if (!inst || !inst.panel || typeof inst.panel !== "object") return ""
  var panel = inst.panel
  // level i podgląd z `stan` (zaplecze kopiuje je z panel.py --json): tylko gdy panel sam ich nie niesie
  if (panel.level === undefined && typeof inst.level === "number") {
    panel = Object.assign({}, panel, { level: inst.level, level_procent: inst.level_procent })
  }
  if (panel.podglad === undefined && inst.podglad && typeof inst.podglad === "object" && inst.podglad.port !== null && inst.podglad.port !== undefined) {
    panel = Object.assign({}, panel, { podglad: inst.podglad })
  }
  var env = []
  if (inst.mapa) env.push("MAPA=" + inst.mapa)
  if (inst.tryb && inst.tryb.length) env.push("TRYB=" + inst.tryb.join(","))
  return JSON.stringify(panel) + "\n--ENV--\n" + env.join("\n")
}

// Lista instancji po odpowiedzi `stan`: onlyId === null = pełna lista; inaczej podmienia/dodaje jeden wpis (kolejność zostaje).
function mergeInstances(current, incoming, onlyId) {
  if (onlyId === null || onlyId === undefined) return incoming
  var out = []
  var replaced = false
  for (var i = 0; i < current.length; i++) {
    var match = null
    for (var j = 0; j < incoming.length; j++) if (incoming[j].id === current[i].id) match = incoming[j]
    if (current[i].id === onlyId && match) { out.push(match); replaced = true } else out.push(current[i])
  }
  if (!replaced && incoming.length) out.push(incoming[0])
  return out
}

// ---------------------------------------------------------------- pasek boczny

function instanceLabel(inst) {
  var base = inst.id === "" ? "główna" : String(inst.id)
  return inst.proxy === true ? base + " · proxy" : base
}

function nickOf(inst) {
  return inst.nick ? String(inst.nick) : (inst.id === "" ? "główna" : String(inst.id))
}

function cardSubtitle(inst) {
  var mapa = inst.mapa || ""
  var tryb = inst.tryb && inst.tryb.length ? inst.tryb.join(", ") : ""
  if (mapa && tryb) return mapa + " · " + tryb
  return mapa || tryb || "brak ostatniego startu"
}

function fraction(cur, max) {
  if (typeof cur !== "number" || typeof max !== "number" || max <= 0) return 0
  return Math.max(0, Math.min(1, cur / max))
}

function hpFraction(inst) { return inst.gracz ? fraction(inst.gracz.hp, inst.gracz.max_hp) : 0 }
function mpFraction(inst) { return inst.gracz ? fraction(inst.gracz.mana, inst.gracz.max_mana) : 0 }

// Level na karcie: z `gracz` (stan wybrany do karty) albo z pola instancji; brak = "" (karta nic nie pokazuje).
function levelOf(inst) {
  if (!inst) return null
  var v = inst.gracz && typeof inst.gracz.level === "number" ? inst.gracz.level : inst.level
  return typeof v === "number" && isFinite(v) && v >= 1 ? Math.floor(v) : null
}

function levelText(inst) {
  var v = levelOf(inst)
  return v === null ? "" : "lvl " + v
}

// Znacznik podglądu przy nicku z wyniku Rules.previewState (te same stany co na pasku):
// open = akcent, closed = przygaszony, none/main/unknown = bez znacznika (nick nieklikalny albo klikalny bez wskaźnika).
function previewMarker(ps) {
  var state = ps ? ps.state : "none"
  if (state === "open") return { visible: true, filled: true, tone: "blue", label: "podgląd otwarty" }
  if (state === "closed") return { visible: true, filled: false, tone: "dim", label: "podgląd zamknięty" }
  return { visible: false, filled: false, tone: "dim", label: ps ? ps.label : "" }
}

function pad2(n) { return (n < 10 ? "0" : "") + n }

function clock(date) {
  return pad2(date.getHours()) + ":" + pad2(date.getMinutes()) + ":" + pad2(date.getSeconds())
}

// Stopka: "2 boty działają" i krótki stan każdej postaci. statuses: id -> wynik Rules.parseStatus.
function runningCount(instances, statuses) {
  var n = 0
  for (var i = 0; i < instances.length; i++) {
    var s = statuses[instances[i].id]
    if (s && s.ok && s.running) n++
  }
  return n
}

function pluralBots(n) {
  if (n === 1) return "bot działa"
  var last = n % 10
  var lastTwo = n % 100
  if (last >= 2 && last <= 4 && !(lastTwo >= 12 && lastTwo <= 14)) return "boty działają"
  return "botów działa"
}

function footerSummary(instances, statuses, stateLabel) {
  var parts = []
  for (var i = 0; i < instances.length; i++) {
    var inst = instances[i]
    parts.push(nickOf(inst) + " " + stateLabel(statuses[inst.id]))
  }
  return parts.join(" · ")
}

// ---------------------------------------------------------------- Ratunek

var BASE_KEYS = { kod: 1, opis: 1, t: 1, poz: 1, wolan_h: 1, ponad_limit: 1, tryb: 1, stan: 1, czas: 1, haiku_cien: 1 }
var DETAIL_LABELS = { wizyt: "wizyty pola", oscylacje: "powroty", okno_s: "okno (s)", stoi_s: "stoi (s)", kotwica: "kotwica",
                      cel: "cel", n: "razy", kroki: "kroki", okrazen: "okrążeń", pietro: "piętro", trasa: "trasa" }
var DETAIL_ORDER = ["wizyt", "oscylacje", "stoi_s", "kotwica", "cel", "n", "kroki", "okrazen", "pietro", "trasa", "okno_s"]
var DETAIL_SHORT = { wizyt: "wizyty", oscylacje: "powroty", stoi_s: "stoi s", okno_s: "w oknie s" }


// Tablice z obiektów trzymanych przez QML (ListView, property var) nie zawsze przechodzą Array.isArray: liczy się kształt.
function isList(v) {
  return v !== null && v !== undefined && typeof v === "object" && typeof v.length === "number"
}

function listItems(v) {
  var out = []
  for (var i = 0; i < v.length; i++) out.push(v[i])
  return out
}

function pozLabel(poz) {
  if (!isList(poz) || poz.length < 2) return "?"
  return poz.length >= 3 ? poz[0] + ", " + poz[1] + ", z" + poz[2] : poz[0] + ", " + poz[1]
}

function todayString(now) {
  return now.getFullYear() + "-" + pad2(now.getMonth() + 1) + "-" + pad2(now.getDate())
}

// "21:04:41" dla dzisiejszych, "10-18 21:04" dla starszych.
function signalTime(czas, now) {
  var c = String(czas || "")
  if (c.length < 19) return c || "?"
  if (c.substring(0, 10) === todayString(now)) return c.substring(11, 19)
  return c.substring(5, 10) + " " + c.substring(11, 16)
}

function codeTone(kod) {
  if (kod === "S1") return "blue"
  if (kod === "S2") return "bad"
  if (kod === "S4") return "warn"
  if (kod === "S6") return "mag"
  return "dim"
}

function formatValue(v) {
  if (isList(v)) return listItems(v).join(", ")
  if (v !== null && typeof v === "object") return JSON.stringify(v)
  return String(v)
}

// Pola sygnału poza podstawowymi -> [{klucz, etykieta, wartosc}] (to, co detektor policzył).
function extraFields(sig) {
  var out = []
  var d = sig && sig.dane ? sig.dane : {}
  var keys = Object.keys(d).filter(function (k) { return !BASE_KEYS[k] })
  // QML oddaje obiekty z kluczami alfabetycznie; kolejność ma być czytelna (najważniejsze liczby detektora pierwsze).
  keys.sort(function (a, b) {
    var ia = DETAIL_ORDER.indexOf(a)
    var ib = DETAIL_ORDER.indexOf(b)
    if (ia < 0) ia = 99
    if (ib < 0) ib = 99
    return ia !== ib ? ia - ib : (a < b ? -1 : 1)
  })
  for (var i = 0; i < keys.length; i++) {
    out.push({ klucz: keys[i], etykieta: DETAIL_LABELS[keys[i]] || keys[i], wartosc: formatValue(d[keys[i]]) })
  }
  return out
}

// Kolumna "co": opis + krótko liczby ("kręci się · wizyty 3, powroty 3").
function signalSummary(sig) {
  var base = String(sig.opis || sig.kod || "?")
  var extra = extraFields(sig)
  var parts = []
  for (var i = 0; i < extra.length && parts.length < 2; i++) {
    parts.push((DETAIL_SHORT[extra[i].klucz] || extra[i].etykieta) + " " + extra[i].wartosc)
  }
  return parts.length ? base + " · " + parts.join(", ") : base
}

function numbersLine(sig) {
  var extra = extraFields(sig)
  var parts = []
  for (var i = 0; i < extra.length; i++) parts.push(extra[i].etykieta + " " + extra[i].wartosc)
  return parts.length ? parts.join(", ") : "brak"
}

function modeLabel(tryb) {
  if (tryb === "cien") return "cień: tylko zapis, bez ruchu"
  if (!tryb) return "nieznany"
  return String(tryb)
}

// Odpowiedź Haiku w cieniu (pole `haiku_cien`, F2a): tekst albo obiekt. Brak pola = null.
function haikuText(sig) {
  var h = sig && sig.dane ? sig.dane.haiku_cien : undefined
  if (h === undefined || h === null || h === "") return null
  if (typeof h === "string") return h
  if (typeof h === "object" && Object.prototype.hasOwnProperty.call(h, "ruch")) {   // rekord F2a (ratunek_cien.py)
    if (h.pominiety) return "pominięty: " + h.pominiety
    var r = h.ruch === null || h.ruch === undefined ? "brak ruchu" : String(h.ruch)
    if (h.ruch === "czlowiek" && h.powod) r += " (" + h.powod + ")"
    if (h.dlaczego) r += " — " + h.dlaczego
    if (typeof h.czas_wywolania_s === "number") r += " · " + h.czas_wywolania_s + " s"
    if (h.blad) r += " · błąd: " + h.blad
    return r
  }
  if (typeof h === "object") {
    var keys = ["odpowiedz", "tekst", "decyzja", "co_by_zrobil", "akcja", "wniosek", "uzasadnienie"]
    var parts = []
    for (var i = 0; i < keys.length; i++) {
      if (h[keys[i]] !== undefined && h[keys[i]] !== null && h[keys[i]] !== "") parts.push(String(h[keys[i]]))
    }
    if (parts.length) return parts.join(" — ")
    return JSON.stringify(h)
  }
  return String(h)
}

function haikuLabel(sig) {
  var t = haikuText(sig)
  return t === null ? "Haiku: brak" : t
}

// Filtr listy: period "dzis" | "7dni", code "" = wszystkie kody.
function filterSignals(signals, period, code, now) {
  var today = todayString(now)
  var out = []
  for (var i = 0; i < signals.length; i++) {
    var s = signals[i]
    if (period === "dzis" && String(s.czas || "").substring(0, 10) !== today) continue
    if (code && s.kod !== code) continue
    out.push(s)
  }
  return out
}

// Kody obecne na liście, posortowane (do przełączania chipa "wszystkie kody").
function signalCodes(signals) {
  var seen = {}
  var out = []
  for (var i = 0; i < signals.length; i++) {
    var k = signals[i].kod
    if (k && !seen[k]) { seen[k] = true; out.push(k) }
  }
  out.sort()
  return out
}

// Następny kod w cyklu: "" -> pierwszy -> ... -> ostatni -> "".
function nextCode(codes, current) {
  if (!codes.length) return ""
  if (current === "") return codes[0]
  var i = codes.indexOf(current)
  return i < 0 || i === codes.length - 1 ? "" : codes[i + 1]
}

// Liczniki do czterech bloków u góry. data = odpowiedź `ratunek`.
function counters(data) {
  var l = data && data.liczniki ? data.liczniki : {}
  var top = l.najczestszy_kod
  var haikuOn = l.haiku === 1 || l.haiku === true
  var withHaiku = 0
  var all = data && data.sygnaly ? data.sygnaly : []
  for (var i = 0; i < all.length; i++) if (haikuText(all[i]) !== null) withHaiku++
  return {
    dzis: typeof l.dzis === "number" ? l.dzis : 0,
    godzina: typeof l.ostatnia_godzina === "number" ? l.ostatnia_godzina : 0,
    limit: typeof l.limit_h === "number" ? l.limit_h : null,
    kod: top ? top.kod : "",
    kodOpis: top ? (top.kod + " " + (top.opis || "")).trim() : "brak",
    haikuOn: haikuOn,
    haiku: haikuOn ? (withHaiku > 0 ? "włączony · odpowiedzi " + withHaiku : "włączony · brak odpowiedzi") : "wyłączony",
    falszywe: typeof l.falszywe === "number" ? l.falszywe : 0
  }
}

function logPath(data, sig) {
  if (!data || !data.katalog_logow || !sig || !sig.plik) return ""
  return String(data.katalog_logow) + "/" + String(sig.plik)
}

function labelText(sig) {
  if (!sig || !sig.etykieta) return ""
  return sig.etykieta === "falszywy" ? "oznaczony: fałszywy alarm" : "oznaczony: prawdziwy"
}

// ---------------------------------------------------------------- Mapa i tryb

function toggleMode(list, name) {
  var i = list.indexOf(name)
  var out = list.slice()
  if (i >= 0) out.splice(i, 1)
  else out.push(name)
  return out
}

function sameSet(a, b) {
  if (a.length !== b.length) return false
  for (var i = 0; i < a.length; i++) if (b.indexOf(a[i]) < 0) return false
  return true
}

// Wybór równy ostatnio użytemu (do podpowiedzi "to samo co ostatnio").
function isLastChoice(last, mapa, tryby) {
  return !!last && last.mapa === mapa && sameSet(last.tryb || [], tryby)
}

// Czy "Start z tym" jest aktywny. status = wynik Rules.parseStatus; reguła jak ▶ Start paska (bot stoi, jest gra, serwis nie trwa)
// plus wybrana mapa. -> {enabled, reason}.
function startState(status, mapa) {
  if (!status || !status.ok) return { enabled: false, reason: "brak odczytu" }
  if (status.running) return { enabled: false, reason: "bot tej postaci działa: najpierw Stop" }
  if (status.serwis && status.serwis.dziala) return { enabled: false, reason: "serwis w toku" }
  if (status.klasa === "brak") return { enabled: false, reason: "gra nie działa" }
  if (!mapa) return { enabled: false, reason: "wybierz mapę" }
  return { enabled: true, reason: "" }
}

function chosenText(mapa, tryby) {
  return "mapa " + (mapa || "?") + ", tryb " + (tryby && tryby.length ? tryby.join(", ") : "bez trybu")
}

// ---------------------------------------------------------------- Sesja gry (F4b)
//
// Czyste funkcje nad odpowiedzią `okno_api sesja` (s). Profil i proxy są tylko do odczytu (D-F4-1): okno ich nie zmienia.
// Akcje (Rules.ACTION_SCRIPTS): gra-start, gra-zamknij, podglad = sesja_gry.py start|zamknij|podglad z RETRONIC_ID.

var SESSION_ACTIONS = { "gra-start": 1, "gra-zamknij": 1, "podglad": 1 }
var MAIN_SESSION_HINT = "główna instancja startuje i kończy się ręcznie (retronic.sh / sesja.sh); okno jej nie dotyka"

var CLOSE_SLOW_MESSAGE = "zamykanie trwa dłużej, stan odświeży się sam"
var SESSION_TIMEOUT_MS = 120000     // sesja_gry.py zamknij: najgorszy przypadek ok. 90 s
var ACTION_TIMEOUT_MS = 25000

function isSessionAction(kind) {
  return Object.prototype.hasOwnProperty.call(SESSION_ACTIONS, kind)
}

function sessionAlive(s) {
  if (!s) return false
  return !!(s.sesja || isList(s.klient_pids) && s.klient_pids.length || isList(s.proxy_pids) && s.proxy_pids.length
            || isList(s.sesja_sh_pids) && s.sesja_sh_pids.length)
}

// Dlaczego "Uruchom grę" jest szare ("" gdy aktywne).
function startBlockReason(s) {
  if (!s) return "brak odczytu sesji"
  if (s.glowna) return MAIN_SESSION_HINT
  if (s.mozna_uruchomic) return ""
  if (sessionAlive(s)) return "sesja już działa: najpierw Zamknij grę"
  var p = s.profil
  if (!p) return "brak profilu instancji"
  if (!p.jest) return p.blad || "brak profilu instancji (proxy, IP, konto)"
  if (p.blad) return "profil: " + p.blad
  return "start niemożliwy"
}

function stopBlockReason(s) {
  if (!s) return "brak odczytu sesji"
  if (s.glowna) return MAIN_SESSION_HINT
  if (s.mozna_zamknac) return ""
  return "sesja nie działa: nie ma czego zamykać"
}

// Podgląd (sesja_gry.py podglad). Spójnie z Rules.previewState (znacznik przy nicku i klik w nick): sesja "stoi" dla podglądu, gdy jest
// port VNC (podglad.port); otwarty = ten sam guzik tylko przenosi fokus. Bez portu: szary (z powodem zależnym od tego, czy sesja żyje).
function previewButton(s) {
  if (!s) return { enabled: false, label: "Otwórz podgląd", hint: "brak odczytu sesji" }
  if (s.glowna) return { enabled: false, label: "Otwórz podgląd", hint: MAIN_SESSION_HINT }
  var p = s.podglad || {}
  if (p.otwarty) return { enabled: true, label: "Pokaż podgląd", hint: "podgląd jest już otwarty: przenosi na niego fokus" }
  if (p.port === null || p.port === undefined) {
    return { enabled: false, label: "Otwórz podgląd",
             hint: s.sesja ? "brak portu VNC sesji (sesja jeszcze wstaje?)" : "sesja nie działa" }
  }
  return { enabled: true, label: "Otwórz podgląd", hint: "otwiera podgląd VNC tej sesji; w nim zalogujesz postać" }
}

// Trzy guziki wg nazw akcji. -> { "gra-start": {enabled, hint}, "gra-zamknij": {...}, "podglad": {enabled, label, hint} }
function sessionButtons(s) {
  var start = startBlockReason(s)
  var stop = stopBlockReason(s)
  return {
    "gra-start": { enabled: start === "", hint: start === "" ? "uruchamia sesję gry z profilu instancji (proxy, IP, postać)" : start },
    "gra-zamknij": { enabled: stop === "", hint: stop === "" ? "zamyka grę tylko tej instancji" : stop },
    "podglad": previewButton(s)
  }
}

// Okno potwierdzenia "Zamknij grę". Bot działa: dodatkowe ostrzeżenie (sesja_gry.py zamknij zatrzymuje go przed zamknięciem gry).
function closeConfirm(s, nick) {
  var lines = ["Zamyka tylko sesję tej instancji (sway, gra, proxy); inne postacie zostają."]
  var botRuns = !!(s && s.bot)
  if (botRuns) {
    lines.push("Bot tej postaci działa: zostanie zatrzymany. Jeśli postać jest w walce, może zostać w grze " +
               "(potwory dalej ją atakują): lepiej najpierw Stop i ⌂ Miasto.")
  }
  return { title: "Zamknąć grę " + (nick || (s && s.nazwa) || "") + "?", lines: lines, botRuns: botRuns }
}

function durationLabel(sec) {
  if (typeof sec !== "number" || !isFinite(sec) || sec < 0) return ""
  var m = Math.floor(sec / 60)
  if (m < 1) return Math.floor(sec) + " s"
  if (m < 60) return m + " min"
  var h = Math.floor(m / 60)
  if (h < 24) return h + " h " + pad2(m % 60) + " min"
  return Math.floor(h / 24) + " d " + (h % 24) + " h"
}

// "od 11:42 (3 h 12 min)"; brak epoch = "—". now: Date.
function sinceLabel(od, now) {
  if (typeof od !== "number" || !isFinite(od) || !now) return "—"
  var d = new Date(od * 1000)
  var age = durationLabel(now.getTime() / 1000 - od)
  var at = pad2(d.getHours()) + ":" + pad2(d.getMinutes())
  if (age === "") return "od " + at
  return "od " + at + " (" + age + ")"
}

// Jedno zdanie o sesji: tone ok | warn | dim.
function sessionSummary(s) {
  if (!s) return { tone: "dim", text: "odczyt…" }
  if (s.sesja && s.gra) return { tone: "ok", text: "działa" }
  if (s.sesja) return { tone: "warn", text: "sesja wstała, gra jeszcze nie" }
  if (sessionAlive(s)) return { tone: "warn", text: "niepełna: zostały procesy sesji" }
  return { tone: "dim", text: "zatrzymana" }
}

// Karta stanu: [{klucz, etykieta, wartosc, ton}] — sesja (sway), gra, bot, proxy, podgląd, od kiedy.
function stateRows(s, now) {
  if (!s) return []
  var p = s.podglad || {}
  var preview = p.otwarty ? { v: "otwarty", t: "blue" } : (s.sesja && p.port ? { v: "zamknięty (port " + p.port + ")", t: "dim" } : { v: "brak", t: "dim" })
  return [
    { klucz: "sesja", etykieta: "sesja (sway)", wartosc: s.sesja ? "działa" : "nie działa", ton: s.sesja ? "ok" : "dim" },
    { klucz: "gra", etykieta: "gra (klient)", wartosc: s.gra ? "działa" : "nie działa", ton: s.gra ? "ok" : "dim" },
    { klucz: "bot", etykieta: "bot", wartosc: s.bot ? "działa" : "stoi", ton: s.bot ? "ok" : "dim" },
    { klucz: "proxy", etykieta: "proxy (siec_proxy)", wartosc: s.proxy ? "działa" : "nie działa", ton: s.proxy ? "ok" : "dim" },
    { klucz: "podglad", etykieta: "podgląd", wartosc: preview.v, ton: preview.t },
    { klucz: "od", etykieta: "sesja od", wartosc: s.sesja ? sinceLabel(s.od, now) : "—", ton: "fg" }
  ]
}

// Odznaka IP z ostatniego startu (też nieudanego). ok | bad | dim.
function ipBadge(s) {
  var ip = s ? s.ip : null
  if (!ip) return { tone: "dim", text: "IP: brak sprawdzenia (jeszcze nie było startu)" }
  var addr = ip.adres || "?"
  return ip.zgodne ? { tone: "ok", text: "IP " + addr + " zgodne z profilem" } : { tone: "bad", text: "IP " + addr + " SPOZA profilu" }
}

// Profil tylko do odczytu: [{klucz, etykieta, wartosc, ton}]. Bez profilu (główna/brak pliku) pusto.
function profileRows(s) {
  var p = s ? s.profil : null
  if (!p || !p.jest) return []
  var ips = isList(p.ip_oczekiwane) ? listItems(p.ip_oczekiwane).join(", ") : ""
  var rows = [
    { klucz: "proxy", etykieta: "proxy", wartosc: p.proxy || "—", ton: "fg" },
    { klucz: "user", etykieta: "użytkownik proxy", wartosc: p.user || "—", ton: "fg" },
    { klucz: "ip", etykieta: "oczekiwane IP", wartosc: ips || "—", ton: "fg" },
    { klucz: "postac", etykieta: "postać", wartosc: p.postac || "nie wpisana", ton: p.postac ? "fg" : "dim" },
    { klucz: "konto", etykieta: "konto", wartosc: p.konto_przypisane ? "przypisane" : "nieprzypisane (po zalogowaniu: profil.py przypisz)",
      ton: p.konto_przypisane ? "ok" : "warn" },
    { klucz: "tozsamosc", etykieta: "tożsamość sprzętu", wartosc: s.tozsamosc ? "jest" : "brak", ton: s.tozsamosc ? "ok" : "warn" }
  ]
  if (p.uwagi) rows.push({ klucz: "uwagi", etykieta: "uwagi", wartosc: p.uwagi, ton: "dim" })
  return rows
}

// Błąd/ostrzeżenie profilu nad blokiem. -> {tone: bad|warn, text} | null
function profileNotice(s) {
  var p = s ? s.profil : null
  if (!p) return null
  if (p.blad) return { tone: "bad", text: p.blad }
  if (p.ostrzezenie) return { tone: "warn", text: p.ostrzezenie }
  return null
}

// Rada przy IP z ostatniego startu spoza profilu, gdy sesja jeszcze żyje (nie wolno logować postaci przez inne IP).
function ipAdvice(s) {
  if (!s || !s.ip || s.ip.zgodne !== false || !sessionAlive(s)) return ""
  return "IP spoza profilu: nie loguj postaci. Zamknij grę i sprawdź proxy w profilu (zmiana poza oknem)."
}

// Podpowiedź po udanym starcie: gra stoi bez zalogowanej postaci (bot jeszcze nie działa).
function startHint(s, justStarted) {
  if (!justStarted || !s || !s.sesja || s.bot) return ""
  return "Gra wystartowała. Zaloguj postać w podglądzie (Otwórz podgląd), potem uruchom bota w Mapa i tryb."
}

// Wyjście ACTION_SCRIPT dla gra-start | gra-zamknij | podglad -> {ok, message}. Jedna linia skryptu + RC; nie kasujemy
// treści przy sukcesie (Rules.parseActionResult zostawia wtedy pusty komunikat, a tu ta linia jest wynikiem akcji).
function parseSessionAction(output, kind) {
  var lines = String(output || "").split("\n").map(function (l) { return l.trim() })
  var rc = null
  var body = []
  for (var i = 0; i < lines.length; i++) {
    var m = /^RC=(\d+)$/.exec(lines[i])
    if (m) { rc = Number(m[1]); continue }
    if (lines[i] !== "") body.push(lines[i])
  }
  // Zamknięcie gry trwa do ok. 90 s (zatrzymaj 30 + swaymsg 10 + wait 25 + TERM 8 + wineserver 15): brak wyniku albo przekroczenie czasu
  // to nie błąd, tylko sesja domykana dalej (stan odświeża się sam).
  if (kind === "gra-zamknij" && (rc === null || rc === 124)) return { ok: false, message: CLOSE_SLOW_MESSAGE }
  if (rc === null) return { ok: false, message: "Brak wyniku skryptu" }
  var text = body.length ? body[body.length - 1] : ""
  if (rc === 124) return { ok: false, message: "Przekroczono czas: sprawdź stan sesji, akcja mogła się jeszcze dokończyć" }
  if (rc !== 0) return { ok: false, message: text !== "" ? text : "Błąd (kod " + rc + ")" }
  return { ok: true, message: text !== "" ? text : "Zrobione" }
}

function sessionActionLabel(kind) {
  if (kind === "gra-start") return "Uruchom grę"
  if (kind === "gra-zamknij") return "Zamknij grę"
  if (kind === "podglad") return "Podgląd"
  return String(kind)
}

// ---- zajętość akcji per instancja: akcja instancji A nie blokuje instancji B; na jedną instancję jedna akcja naraz.
// Mapa id -> true (niezmienna: każda zmiana zwraca kopię, więc binding QML się odświeża).
function actionTimeoutMs(kind) { return isSessionAction(kind) ? SESSION_TIMEOUT_MS : ACTION_TIMEOUT_MS }

function isBusy(map, id) { return !!map && map[id] === true }

function busyBegin(map, id) {
  var copy = {}
  for (var k in map) copy[k] = map[k]
  copy[id] = true
  return copy
}

function busyEnd(map, id) {
  var copy = {}
  for (var k in map) if (k !== id) copy[k] = map[k]
  return copy
}

// Linie logu do pokazania w bloku: ostatnie n niepustych, każda przycięta.
function logTail(lines, n, width) {
  var out = []
  var src = isList(lines) ? listItems(lines) : []
  var max = width || 160
  for (var i = Math.max(0, src.length - (n || 6)); i < src.length; i++) {
    var l = String(src[i]).replace(/\s+$/, "")
    if (l !== "") out.push(l.length > max ? l.substring(0, max - 1) + "…" : l)
  }
  return out
}

if (typeof module !== "undefined" && module.exports) {
  module.exports = {
    validId: validId, apiCommand: apiCommand, stanCommand: stanCommand, ratunekCommand: ratunekCommand,
    mapyCommand: mapyCommand, oznaczCommand: oznaczCommand, startCommand: startCommand, START_SCRIPT: START_SCRIPT,
    parseApi: parseApi, panelOutput: panelOutput, mergeInstances: mergeInstances,
    instanceLabel: instanceLabel, nickOf: nickOf, cardSubtitle: cardSubtitle, fraction: fraction,
    hpFraction: hpFraction, mpFraction: mpFraction, clock: clock, runningCount: runningCount, pluralBots: pluralBots,
    footerSummary: footerSummary, pozLabel: pozLabel, todayString: todayString, signalTime: signalTime,
    codeTone: codeTone, extraFields: extraFields, signalSummary: signalSummary, numbersLine: numbersLine,
    modeLabel: modeLabel, haikuText: haikuText, haikuLabel: haikuLabel, filterSignals: filterSignals,
    signalCodes: signalCodes, nextCode: nextCode, counters: counters, logPath: logPath, labelText: labelText,
    sesjaCommand: sesjaCommand, levelOf: levelOf, levelText: levelText, previewMarker: previewMarker,
    isSessionAction: isSessionAction, sessionAlive: sessionAlive, startBlockReason: startBlockReason, stopBlockReason: stopBlockReason,
    previewButton: previewButton, sessionButtons: sessionButtons, closeConfirm: closeConfirm, durationLabel: durationLabel,
    sinceLabel: sinceLabel, sessionSummary: sessionSummary, stateRows: stateRows, ipBadge: ipBadge, profileRows: profileRows,
    profileNotice: profileNotice, ipAdvice: ipAdvice, startHint: startHint, parseSessionAction: parseSessionAction, sessionActionLabel: sessionActionLabel,
    logTail: logTail, MAIN_SESSION_HINT: MAIN_SESSION_HINT, CLOSE_SLOW_MESSAGE: CLOSE_SLOW_MESSAGE,
    SESSION_TIMEOUT_MS: SESSION_TIMEOUT_MS, ACTION_TIMEOUT_MS: ACTION_TIMEOUT_MS, actionTimeoutMs: actionTimeoutMs,
    isBusy: isBusy, busyBegin: busyBegin, busyEnd: busyEnd,
    toggleMode: toggleMode, sameSet: sameSet, isLastChoice: isLastChoice, startState: startState, chosenText: chosenText
  }
}
