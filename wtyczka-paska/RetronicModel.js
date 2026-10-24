// Model wtyczki Retronic: czysta logika bez Quickshella (testy: node --test test/*.test.js).
// Panel.qml tylko woła te funkcje. Kontrakt z botem (katalog pomocnika, tylko to, co tu czytamy):
//   status:  RETRONIC_ID=<id> python3 -I panel.py --json -> {"text","tooltip","class","alt"}, class: dziala|alarm|stop|brak
//   stop:    RETRONIC_ID=<id> ./zatrzymaj.sh
//   start:   RETRONIC_ID=<id> ./uruchom.sh (bez MAPA/TRYB bierze ostatni_start[.<id>].env)
//   lista:   pusty ID (główna, chyba że jest instancje/_bez_glownej) + podkatalogi instancje/ poza _wspolne
//   miasto:  RETRONIC_ID=<id> ./wroc.sh [--anuluj]            ("Wróć do miasta": plik WROC, bot rusza w spokojnej chwili)
//            RETRONIC_ID=<id> ./refill.sh --tlo | --spot | --przerwij  ("Refill": serwis w mieście odłączony, log refill.log;
//                                  "Spot": to samo bez zakupów, tylko wyjście z miasta i start bota)
//   kolejność: sortRows(): aktywne (w grze) u góry, potem nieaktywne; w grupie level malejąco, brak levelu na koniec, remis po ID
//   okno:    <katalog>/okno.sh odłączone (setsid -f): okno zarządzania Retronic, jeden egzemplarz (drugi start = fokus)
//            dodatkowe pola panel.py --json (opcjonalne): pozycja, w_miescie, w_depo, plan_depo_dostepny, wroc_*, serwis_*
//   level:   opcjonalne pola panel.py --json: level (int|null), level_procent (liczba|null); brak = wiersz HP/mana bez "lvl"
//   podglad: opcjonalne pole panel.py --json: podglad {port, otwarty, pid}; klik w nick = RETRONIC_ID=<id> sesja_gry.py podglad
//            (odłączony podgląd VNC albo fokus na otwarty; główna instancja nie ma podglądu)

var DEFAULT_HELPER_DIR = "~/Games/Retronic/pomocnik"

// Taki sam wzór jak _WZOR_ID w instancja.py bota. _wspolne odpada już na pierwszym znaku.
var ID_PATTERN = /^[a-z0-9][a-z0-9_-]{0,23}$/

// Ważność stanu do koloru ikony: alarm > stop > działa; "brak" (gra nie działa) najniżej.
var RANK = { alarm: 3, stop: 2, dziala: 1, brak: 0 }

var MAX_ERROR_LENGTH = 48

function validId(id) {
  return id === "" || ID_PATTERN.test(String(id))
}

function displayName(id) {
  return id === "" ? "główna" : String(id)
}

function expandPath(path, home) {
  var p = String(path || "").trim()
  if (p === "~") return String(home || "")
  if (p.indexOf("~/") === 0) return String(home || "") + p.substring(1)
  return p
}

// Wynik `find instancje -mindepth 1 -maxdepth 1 -xtype d -printf '%f\n'` -> lista ID bez duplikatów, posortowana.
function parseInstanceListing(text) {
  var seen = {}
  var ids = []
  var lines = String(text || "").split("\n")
  for (var i = 0; i < lines.length; i++) {
    var name = lines[i].trim()
    if (name === "" || !ID_PATTERN.test(name) || seen[name]) continue
    seen[name] = true
    ids.push(name)
  }
  ids.sort()
  return ids
}

// Katalog instancje/_bez_glownej (20.10) chowa główną instancję: po jej zakończeniu nie ma jej w panelu. Cofnięcie: rmdir.
var NO_MAIN_MARKER = "_bez_glownej"

// Główna instancja (pusty ID) pierwsza, chyba że jest znacznik NO_MAIN_MARKER.
function instanceIds(listingText) {
  var hidden = String(listingText || "").split("\n").some(function (l) { return l.trim() === NO_MAIN_MARKER })
  var ids = parseInstanceListing(listingText)
  return hidden ? ids : [""].concat(ids)
}

// Kolejność wierszy w panelu (22.10): na górze aktywne, pod nimi nieaktywne; w obu grupach level malejąco.
// Aktywna = postać jest w grze: status odczytany, a klasa inna niż "brak" (gra nie działa) albo żywy proces bota.
// To obejmuje bota (dziala), alarm, stop z otwartą grą i ręczną grę Karola (gra stoi, bot nie). Panel nie ma osobnego
// pola "zalogowana": grę widać po klasie (socket strażnika), więc "aktywna = w grze". Status null/nieodczytany = nieaktywna.
function isActive(status) {
  return !!(status && status.ok && (status.klasa !== "brak" || status.running))
}

// Level do sortowania: liczba całkowita >= 1 albo null (nieznany -> na koniec swojej grupy).
function sortLevel(status) {
  return status && typeof status.level === "number" && isFinite(status.level) && status.level >= 1 ? status.level : null
}

// rows: obiekty z polami instanceId i status (Instance.qml). Zwraca NOWĄ tablicę (wejście bez zmian).
// Remis levelu (też oba bez levelu): po ID alfabetycznie, główna (pusty ID) pierwsza.
function sortRows(rows) {
  var items = (rows || []).slice()
  items.sort(function (a, b) {
    var aa = isActive(a.status) ? 0 : 1
    var ab = isActive(b.status) ? 0 : 1
    if (aa !== ab) return aa - ab
    var la = sortLevel(a.status)
    var lb = sortLevel(b.status)
    if (la !== lb) {
      if (la === null) return 1
      if (lb === null) return -1
      return lb - la
    }
    var ia = String(a.instanceId)
    var ib = String(b.instanceId)
    return ia < ib ? -1 : (ia > ib ? 1 : 0)
  })
  return items
}

// ---------------------------------------------------------------- polecenia
//
// Bez powłoki po stronie QML: ID i katalog idą jako argumenty pozycyjne ($1, $2), nigdy sklejone w tekst skryptu.

var STATUS_SCRIPT = [
  'ID="$1"; DIR="$2"; cd "$DIR" 2>/dev/null || exit 0',
  'if [ -n "$ID" ]; then export RETRONIC_ID="$ID"; else unset RETRONIC_ID; fi',
  // 24.10: panel.py (wspólny cache, jeden przebieg na instancję na ~2 s) podaje po JSON-ie także linię PROXY=0|1 (RETRONIC_PANEL_PROXY=1).
  'out=$(RETRONIC_PANEL_PROXY=1 python3 -I "$DIR/panel.py" --json 2>/dev/null | head -n 2)',
  '[ -n "$out" ] && printf "%s\\n" "$out"',
  // proxy: czy proces siec_proxy.sh tej instancji żyje (gra instancji jest jego potomkiem). Bez pomiaru IP.
  // Zapas dla panel.py bez linii PROXY= (starszy, atrapa): dawny pgrep.
  'case "$out" in',
  '  *$\'\\n\'PROXY=*) ;;',
  '  *)',
  '    proxy=0',
  '    for p in $(pgrep -f "siec_proxy[.]sh" 2>/dev/null); do',
  '      mapfile -d "" a < "/proc/$p/cmdline" 2>/dev/null || continue',
  '      case "${a[1]}" in */siec_proxy.sh) ;; *) continue ;; esac',
  '      i=$(tr "\\0" "\\n" < "/proc/$p/environ" 2>/dev/null | sed -n "s/^RETRONIC_ID=//p")',
  '      if [ "$i" = "$ID" ]; then proxy=1; break; fi',
  '    done',
  '    echo "PROXY=$proxy" ;;',
  'esac',
  'echo "--ENV--"',
  'cat "$DIR/ostatni_start${ID:+.$ID}.env" 2>/dev/null',
  'exit 0'
].join("\n")

// Skrypt akcji: wynik skryptu bota do pliku tymczasowego (dzieci bota, np. mozg.py, nie trzymają wtedy rury do
// wtyczki), na końcu linia RC=<kod>. Zawsze exit 0: kod wyjścia niesie RC.
var ACTION_SCRIPT = [
  'ID="$1"; DIR="$2"; SCRIPT="$3"; ARG="$4"',
  'if [ -n "$ID" ]; then export RETRONIC_ID="$ID"; else unset RETRONIC_ID; fi',
  'f=$(mktemp) || { echo "RC=1"; exit 0; }',
  'cd "$DIR" 2>/dev/null || { echo "brak katalogu pomocnika"; echo "RC=1"; rm -f "$f"; exit 0; }',
  '"$DIR/$SCRIPT" ${ARG:+"$ARG"} > "$f" 2>&1 < /dev/null',
  'rc=$?',
  'tail -c 600 "$f"; echo',
  'rm -f "$f"',
  'echo "RC=$rc"',
  'exit 0'
].join("\n")

// rodzaj akcji -> [skrypt, argument]; argument pusty = bez argumentu (polecenia Stop/Start bez zmian)
var ACTION_SCRIPTS = {
  stop: ["zatrzymaj.sh", ""], start: ["uruchom.sh", ""],
  wroc: ["wroc.sh", ""], "wroc-anuluj": ["wroc.sh", "--anuluj"],
  refill: ["refill.sh", "--tlo"], spot: ["refill.sh", "--spot"], "refill-stop": ["refill.sh", "--przerwij"],
  // sesja gry jednej instancji (sesja_gry.py, spec okna F4a + spec 2026-10-20-retronic-lvl-i-podglad.md); główna = odmowa
  podglad: ["sesja_gry.py", "podglad"], "gra-start": ["sesja_gry.py", "start"], "gra-zamknij": ["sesja_gry.py", "zamknij"]
}

// "Otwórz okno": okno.sh to długo żyjący proces (quickshell), więc odpalamy go przez setsid -f, w osobnej sesji, z
// wyjściem w /dev/null: okno przeżywa zamknięcie popupu i restart paska. Drugi start okno.sh sam tylko przenosi fokus.
// Katalog idzie jako $1, nie w tekście skryptu. Zawsze exit 0: kod wyjścia niesie RC (jak ACTION_SCRIPT).
var WINDOW_SCRIPT = [
  'DIR="$1"',
  '[ -n "$DIR" ] && [ -f "$DIR/okno.sh" ] || { echo "brak okno.sh w katalogu pomocnika"; echo "RC=1"; exit 0; }',
  'command -v quickshell >/dev/null 2>&1 || { echo "brak quickshell w PATH"; echo "RC=1"; exit 0; }',
  'setsid -f bash "$DIR/okno.sh" > /dev/null 2>&1 < /dev/null',
  'echo "RC=$?"',
  'exit 0'
].join("\n")

function windowCommand(helperDir) {
  if (!helperDir) return null
  return ["bash", "-c", WINDOW_SCRIPT, "retronic-okno", String(helperDir)]
}

// Jeden guzik dla całego panelu (nie per instancja): niezależny od stanu botów, zawsze aktywny.
function windowButton() {
  return { action: "okno", label: "▣ Otwórz okno", enabled: true, hint: "Okno zarządzania Retronic (osobny proces)", tone: "ok" }
}

function listCommand(helperDir) {
  return ["find", helperDir + "/instancje", "-mindepth", "1", "-maxdepth", "1", "-xtype", "d", "-printf", "%f\\n"]
}

function statusCommand(helperDir, id) {
  if (!validId(id) || !helperDir) return null
  return ["bash", "-c", STATUS_SCRIPT, "retronic-status", String(id), helperDir]
}

var SESSION_KINDS = { podglad: true, "gra-start": true, "gra-zamknij": true }

function actionCommand(helperDir, id, kind) {
  if (!validId(id) || !helperDir || !Object.prototype.hasOwnProperty.call(ACTION_SCRIPTS, kind)) return null
  // Sesja gry (podgląd, start, zamknięcie) istnieje tylko dla instancji z ID: główna (ID pusty) jej nie ma, backend odmawia.
  if (id === "" && SESSION_KINDS[kind]) return null
  var spec = ACTION_SCRIPTS[kind]
  var command = ["bash", "-c", ACTION_SCRIPT, "retronic-" + kind, String(id), helperDir, spec[0]]
  if (spec[1] !== "") command.push(spec[1])
  return command
}

// ---------------------------------------------------------------- status

function unknownStatus(reason) {
  return { ok: false, klasa: "brak", running: false, czas: "", hp: null, mana: null, proxy: null,
           lastMap: "", lastMode: "", error: reason || "brak odczytu", cityData: false,
           level: null, levelProcent: null, podglad: null }
}

function cleanEnvValue(value) {
  // printf %q: wartości z mapy/trybu to zwykłe nazwy; zdejmujemy cudzysłowy i backslashe
  return String(value || "").replace(/^['"]|['"]$/g, "").replace(/\\/g, "").trim()
}

function parseEnv(lines) {
  var out = { map: "", mode: "" }
  for (var i = 0; i < lines.length; i++) {
    var m = /^(MAPA|TRYB)=(.*)$/.exec(lines[i])
    if (!m) continue
    if (m[1] === "MAPA") out.map = cleanEnvValue(m[2])
    else out.mode = cleanEnvValue(m[2])
  }
  return out
}

// Wyjście STATUS_SCRIPT: linia JSON, "PROXY=0|1", "--ENV--", zawartość ostatni_start*.env.
// Z tooltipu bierzemy WYŁĄCZNIE czas działania oraz HP/manę. Wniosku analityka i logów celowo nie czytamy.
function parseStatus(output) {
  var lines = String(output || "").split("\n")
  var json = null
  var proxy = null
  var envLines = []
  var inEnv = false
  for (var i = 0; i < lines.length; i++) {
    var line = lines[i]
    if (inEnv) { envLines.push(line.trim()); continue }
    if (line === "--ENV--") { inEnv = true; continue }
    if (line.indexOf("PROXY=") === 0) { proxy = line.substring(6).trim() === "1"; continue }
    if (json === null && line.charAt(0) === "{") json = line
  }
  if (json === null) return unknownStatus("brak odczytu")
  var data
  try { data = JSON.parse(json) } catch (e) { return unknownStatus("błędny JSON") }
  var klasa = data && typeof data["class"] === "string" ? data["class"] : ""
  if (RANK[klasa] === undefined) return unknownStatus("nieznany stan")

  var tooltip = String(data.tooltip || "")
  var run = /^Tryb: .*?, działa (.+)$/m.exec(tooltip)
  var hp = /^HP (\d+)\/(\d+)\s+mana (\d+)\/(\d+)/m.exec(tooltip)
  var env = parseEnv(envLines)
  var city = parseCity(data)
  var lvl = parseLevel(data, tooltip)
  return {
    ok: true,
    klasa: klasa,
    // panel.py podaje linię "Tryb:" tylko dla żywego procesu bota; alarm może trwać jeszcze po jego śmierci
    running: klasa === "dziala" || run !== null,
    czas: run ? run[1].trim() : "",
    hp: hp ? { cur: Number(hp[1]), max: Number(hp[2]) } : null,
    mana: hp ? { cur: Number(hp[3]), max: Number(hp[4]) } : null,
    proxy: proxy,
    lastMap: env.map,
    lastMode: env.mode,
    error: "",
    cityData: city.cityData,
    level: lvl.level,
    levelProcent: lvl.procent,
    podglad: parsePreview(data),
    miasto: city.miasto,
    wroc: city.wroc,
    serwis: city.serwis
  }
}

// Level z pól `level` / `level_procent`; zapasowo z linii tooltipu "lvl N (P%)" (starszy układ), gdy pól nie ma.
// -> {level: int|null, procent: liczba|null}. Procent bez levelu nie ma sensu: wtedy oba null.
function parseLevel(data, tooltip) {
  var level = null
  var procent = null
  if (typeof data.level === "number" && isFinite(data.level) && data.level >= 1) {
    level = Math.floor(data.level)
    if (typeof data.level_procent === "number" && isFinite(data.level_procent)) procent = data.level_procent
  } else if (data.level === undefined) {
    var m = /\blvl (\d+)(?: \((\d+(?:[.,]\d+)?)%\))?/.exec(tooltip)
    if (m) {
      level = Number(m[1])
      if (m[2] !== undefined) procent = Number(m[2].replace(",", "."))
    }
  }
  return { level: level, procent: procent }
}

// Pole `podglad` {port, otwarty, pid}; brak albo zły kształt = null ("nie wiadomo", stary panel.py).
function parsePreview(data) {
  var p = data && data.podglad
  if (!p || typeof p !== "object") return null
  return {
    port: typeof p.port === "number" && p.port > 0 ? p.port : null,
    otwarty: p.otwarty === true,
    pid: typeof p.pid === "number" && p.pid > 0 ? p.pid : null
  }
}

// Dodatkowe pola panel.py --json dla guzików miasta. Starszy panel.py ich nie ma: cityData=false, guziki szare.
function parseCity(data) {
  var has = data && typeof data.serwis_dziala === "boolean" && typeof data.wroc_oczekuje === "boolean"
  var list = Array.isArray(data.serwis_ukonczone) ? data.serwis_ukonczone.filter(function (k) { return typeof k === "string" }) : []
  return {
    cityData: !!has,
    miasto: {
      wMiescie: typeof data.w_miescie === "string" ? data.w_miescie : "",
      wDepo: data.w_depo === true,
      // true/false = jest/nie ma planu dojścia do depo z tej pozycji; null = pozycja nieznana
      planDepo: typeof data.plan_depo_dostepny === "boolean" ? data.plan_depo_dostepny : null
    },
    wroc: { oczekuje: data.wroc_oczekuje === true, wMarszu: data.wroc_w_marszu === true },
    serwis: {
      dziala: data.serwis_dziala === true,
      krok: typeof data.serwis_krok === "string" ? data.serwis_krok : "",
      tryb: typeof data.serwis_tryb === "string" ? data.serwis_tryb : "",     // refill | spot ("" = serwis z terminala / stary panel.py)
      ukonczone: list,
      wynik: typeof data.serwis_wynik === "string" ? data.serwis_wynik : "",
      komunikat: typeof data.serwis_komunikat === "string" ? data.serwis_komunikat : "",
      wiekS: typeof data.serwis_wiek_s === "number" ? data.serwis_wiek_s : null
    }
  }
}

function stateLabel(status) {
  if (!status || !status.ok) return "brak odczytu"
  if (status.klasa === "alarm") return "ALARM"
  if (status.klasa === "dziala") return status.czas ? "działa " + status.czas : "działa"
  if (status.klasa === "stop") return "stop"
  return "brak gry"
}

function resourcesLabel(status) {
  if (!status || !status.hp) return ""
  return "HP " + status.hp.cur + "/" + status.hp.max + "  mana " + status.mana.cur + "/" + status.mana.max
}

// Wiersz zasobów: "HP 170/170  mana 20/20  lvl 8 (35%)". Bez levelu dokładnie stary wiersz (resourcesLabel);
// bez HP, ale z levelem (zatrzymany bot, gdy panel.py czyta gracza) samo "lvl 8 (35%)".
function levelLabel(status) {
  if (!status || typeof status.level !== "number") return ""
  var p = status.levelProcent
  return "lvl " + status.level + (typeof p === "number" && isFinite(p) ? " (" + Math.round(p) + "%)" : "")
}

// Osobne kawałki do pogrubionego, kolorowego wiersza w popupie (Karol 20.10: „słabo widać”): HP, mana; level stoi przy nicku.
function hpLabel(status) {
  return status && status.hp ? "HP " + status.hp.cur + "/" + status.hp.max : ""
}

function manaLabel(status) {
  return status && status.mana ? "mana " + status.mana.cur + "/" + status.mana.max : ""
}

function statsLine(status) {
  var base = resourcesLabel(status)
  var lvl = levelLabel(status)
  if (lvl === "") return base
  return base === "" ? lvl : base + "  " + lvl
}

// ---------------------------------------------------------------- "Zobacz postać": klik w nick = podgląd VNC
//
// Stan znacznika przy nicku. state: main (bez podglądu, bez znacznika) | none (gra nie działa) | closed | open | unknown
// (panel.py bez pola `podglad`: znacznika nie ma, klik wolno, o ile gra działa). enabled = czy klik wywołuje akcję `podglad`.
// Sesja stoi, gdy działa podgląd-port (`podglad.port != null`, zapisuje go sesja.sh zaraz po starcie wayvnc), NIE gdy jest
// socket strażnika (klasa `brak` trwa jeszcze podczas startu gry: nick ma już być klikalny). Bez portu = stan none, także
// przy otwartym podglądzie (backend i tak odmawia podglądu bez sesji). Wyjątek: brak pola `podglad` (stary panel.py) =
// dawna reguła po klasie. id: opcjonalny; pusty = główna instancja.
var PREVIEW_HINT = "Zobacz postać (podgląd)"

function previewState(status, id) {
  if (id === "") return { state: "main", label: "", enabled: false, hint: "" }
  var none = { state: "none", label: "gra nie działa", enabled: false, hint: "gra nie działa" }
  if (!status || !status.ok) return none
  var p = status.podglad
  if (!p) return status.klasa === "brak" ? none : { state: "unknown", label: "", enabled: true, hint: PREVIEW_HINT }
  if (p.port === null || p.port === undefined) return none
  if (p.otwarty) return { state: "open", label: "podgląd otwarty", enabled: true,
                          hint: "Podgląd otwarty: klik przenosi na niego fokus" }
  return { state: "closed", label: "podgląd zamknięty", enabled: true, hint: PREVIEW_HINT }
}

function lastStartLabel(status) {
  if (!status || (!status.lastMap && !status.lastMode)) return "ostatni: brak"
  return "ostatni: " + (status.lastMap || "?") + ", " + (status.lastMode || "?")
}

function proxyLabel(status) {
  if (!status || status.proxy === null) return ""
  return status.proxy ? "proxy włączone" : "proxy wyłączone"
}

// Który przycisk w wierszu: stop (bot działa), start (można ruszyć), start z blokadą (brak gry / brak odczytu).
function buttonKind(status) {
  if (status && status.ok && status.running) return "stop"
  return "start"
}

function buttonEnabled(status) {
  if (!status || !status.ok) return false
  // Serwis w toku (Refill) steruje myszą i czatem gry: Start w tym czasie ruszyłby drugiego sterującego.
  if (!status.running && serviceRunning(status)) return false
  return status.running || status.klasa !== "brak"
}

// ---------------------------------------------------------------- guziki miasta: "Wróć do miasta" i "Refill"
//
// Czyste funkcje stanu; Instance.qml tylko woła akcję z pola `action`, a PanelContent.qml rysuje etykiety.
// Zasady: dwa osobne guziki na instancję, bez niejawnych akcji (każdy tylko po kliknięciu), brak danych = szary guzik
// z powodem w `hint` (pokazywanym pod myszą), porażka serwisu to widoczny stan "błąd: <powód>", bez ponawiania.

var ERROR_VISIBLE_S = 3600    // błąd ostatniego refillu widać godzinę (potem log jest „stary”), o ile bot dalej stoi

var STEP_NAMES = { bank: "bank", depo: "depo", jedzenie: "jedzenie", backpack: "plecak", blanki: "blanki", wyjscie: "wyjście" }

function stepLabel(step) {
  return STEP_NAMES[step] || String(step || "")
}

function serviceRunning(status) {
  return !!(status && status.serwis && status.serwis.dziala)
}

function cityDisabled(label, hint) {
  return { action: "", label: label, enabled: false, hint: hint, tone: "off" }
}

// "Wróć do miasta" / "Anuluj". action: wroc | wroc-anuluj | "" (szary).
function returnButton(status) {
  var label = "⌂ Miasto"
  if (!status || !status.ok) return cityDisabled(label, "brak odczytu")
  if (!status.cityData) return cityDisabled(label, "panel.py bez danych o mieście")
  if (serviceRunning(status)) return cityDisabled(label, "serwis w toku")
  if (!status.running) return cityDisabled(label, status.klasa === "brak" ? "gra nie działa" : "bot nie działa")
  if (status.wroc.wMarszu) return cityDisabled("w marszu…", "bot idzie do depo (zatrzymanie: ■ Stop)")
  if (status.wroc.oczekuje) return { action: "wroc-anuluj", label: "✕ Anuluj", enabled: true, tone: "warn",
                                     hint: "cofa zlecenie, dopóki bot nie ruszył" }
  if (status.miasto.wMiescie !== "") return cityDisabled(label, "postać już jest w mieście")
  if (status.miasto.planDepo === null) return cityDisabled(label, "pozycja postaci nieznana")
  if (status.miasto.planDepo === false) return cityDisabled(label, "brak planu depo dla tej pozycji")
  return { action: "wroc", label: label, enabled: true, tone: "ok",
           hint: "bot dojdzie do depo w najbliższej spokojnej chwili i stanie" }
}

// "Refill" / "Przerwij serwis". action: refill | refill-stop | "" (szary).
function refillButton(status) {
  var label = "↻ Refill"
  if (!status || !status.ok) return cityDisabled(label, "brak odczytu")
  if (!status.cityData) return cityDisabled(label, "panel.py bez danych o mieście")
  if (serviceRunning(status)) return { action: "refill-stop", label: "■ Przerwij", enabled: true, tone: "stop",
                                       hint: "przerywa serwis i zatrzymuje bota (STOP)" }
  if (status.klasa === "brak") return cityDisabled(label, "gra nie działa")
  if (status.klasa === "alarm") return cityDisabled(label, "alarm: poczekaj, aż minie")
  if (status.running) return cityDisabled(label, "najpierw zatrzymaj bota")
  if (status.miasto.wMiescie === "") {
    return cityDisabled(label, status.miasto.planDepo === null ? "pozycja postaci nieznana" : "postać jest poza miastem (najpierw ⌂ Miasto)")
  }
  return { action: "refill", label: label, enabled: true, tone: "ok",
           hint: "zakupy w mieście (bez banku i depo), potem bot rusza na spot" }
}

// "↗ Spot" (refill.sh --spot): z miasta na spot bez zakupów = tylko krok "wyjscie" i start bota ostatnią mapą i trybem.
// W trakcie serwisu Przerwij jest tylko jedno (na miejscu Refill), więc tu guzik jest szary: przy --spot z etykietą
// "idę na spot…", przy zwykłym Refillu z powodem.
function spotButton(status) {
  var label = "↗ Spot"
  if (!status || !status.ok) return cityDisabled(label, "brak odczytu")
  if (!status.cityData) return cityDisabled(label, "panel.py bez danych o mieście")
  if (serviceRunning(status)) {
    if (status.serwis.tryb === "spot") return cityDisabled("idę na spot…", "postać idzie do wyjścia z miasta (■ Przerwij po lewej)")
    return cityDisabled(label, "serwis w toku")
  }
  if (status.klasa === "brak") return cityDisabled(label, "gra nie działa")
  if (status.klasa === "alarm") return cityDisabled(label, "alarm: poczekaj, aż minie")
  if (status.running) return cityDisabled(label, "najpierw zatrzymaj bota")
  if (status.miasto.wMiescie === "") {
    return cityDisabled(label, status.miasto.planDepo === null ? "pozycja postaci nieznana" : "już poza miastem: użyj ▶ Start")
  }
  return { action: "spot", label: label, enabled: true, tone: "ok",
           hint: "bez zakupów: postać wychodzi z miasta, potem bot rusza na spot" }
}

// Jedna linia pod wierszem instancji: co się dzieje z cyklem spot -> miasto -> refill -> spot.
// -> {text, error}; text pusty = nic do pokazania.
function cityInfo(status) {
  if (!status || !status.ok || !status.cityData) return { text: "", error: false }
  var s = status.serwis
  if (s.dziala) {
    var what = s.tryb === "spot" ? "idę na spot…" : "serwis w toku"
    return { text: s.krok ? what + " (krok: " + stepLabel(s.krok) + ")" : what, error: false }
  }
  if (status.running && status.wroc.wMarszu) return { text: "w marszu do depo", error: false }
  if (status.running && status.wroc.oczekuje) return { text: "czeka na spokojną chwilę", error: false }
  if (!status.running) {
    var fresh = s.wiekS === null || s.wiekS < ERROR_VISIBLE_S
    if (s.wynik === "blad" && fresh) return { text: "błąd: " + (s.komunikat || "serwis nie powiódł się"), error: true }
    if (s.wynik === "przerwano" && fresh) return { text: "serwis przerwany", error: false }
    if (status.miasto.wDepo) return { text: "w depo, bot stoi", error: false }
    if (status.miasto.wMiescie !== "") return { text: "w mieście, bot stoi", error: false }
  }
  return { text: "", error: false }
}

// ---------------------------------------------------------------- zbiorczo (ikona, hover)

function rankOf(klasa) {
  return RANK[klasa] === undefined ? -1 : RANK[klasa]
}

// statuses: lista obiektów z parseStatus albo null (jeszcze bez odczytu). Nieudany odczyt liczy się jak "brak".
function worstClass(statuses) {
  var worst = null
  for (var i = 0; i < statuses.length; i++) {
    var s = statuses[i]
    if (!s) continue
    var k = s.ok ? s.klasa : "brak"
    if (worst === null || rankOf(k) > rankOf(worst)) worst = k
  }
  return worst === null ? "brak" : worst
}

function pluralInstances(n) {
  if (n === 1) return "instancja"
  var last = n % 10
  var lastTwo = n % 100
  if (last >= 2 && last <= 4 && !(lastTwo >= 12 && lastTwo <= 14)) return "instancje"
  return "instancji"
}

// Jedno zdanie do hovera: "2 instancje: 1 działa, 1 stop".
function hoverSentence(statuses) {
  var counts = { alarm: 0, dziala: 0, stop: 0, brak: 0 }
  var total = 0
  for (var i = 0; i < statuses.length; i++) {
    var s = statuses[i]
    if (!s) continue
    counts[s.ok ? s.klasa : "brak"]++
    total++
  }
  if (total === 0) return "Retronic: odczyt…"
  var names = [["alarm", "alarm"], ["dziala", "działa"], ["stop", "stop"], ["brak", "brak gry"]]
  var parts = []
  for (var j = 0; j < names.length; j++) {
    var n = counts[names[j][0]]
    if (n === 0) continue
    parts.push(total === 1 ? names[j][1] : n + " " + names[j][1])
  }
  return total + " " + pluralInstances(total) + ": " + parts.join(", ")
}

// ---------------------------------------------------------------- wynik akcji

function truncate(text, max) {
  var t = String(text)
  return t.length > max ? t.substring(0, max - 1).replace(/\s+$/, "") + "…" : t
}

function capitalize(text) {
  return text.length ? text.charAt(0).toUpperCase() + text.substring(1) : text
}

// Wyjście ACTION_SCRIPT -> {ok, message}. Komunikat krótki, jedna linia; znane odmowy skryptów mają polskie hasła.
function parseActionResult(output) {
  var lines = String(output || "").split("\n").map(function (l) { return l.trim() })
  var rc = null
  var body = []
  for (var i = 0; i < lines.length; i++) {
    var m = /^RC=(\d+)$/.exec(lines[i])
    if (m) { rc = Number(m[1]); continue }
    if (lines[i] !== "") body.push(lines[i])
  }
  if (rc === null) return { ok: false, message: "Brak wyniku skryptu" }
  if (rc === 0) return { ok: true, message: "" }
  var text = body.join(" ").toLowerCase()
  if (text.indexOf("brak socketu") >= 0) return { ok: false, message: "Gra nie działa" }
  if (text.indexOf("już działa") >= 0 && text.indexOf("serwis") >= 0) return { ok: false, message: "Serwis już trwa" }
  if (text.indexOf("już działa") >= 0) return { ok: false, message: "Bot już działa" }
  if (text.indexOf("bot działa") >= 0) return { ok: false, message: "Bot działa: najpierw Stop" }
  if (text.indexOf("bot nie działa") >= 0) return { ok: false, message: "Bot nie działa" }
  if (body.length === 0) return { ok: false, message: "Błąd (kod " + rc + ")" }
  return { ok: false, message: truncate(capitalize(body[body.length - 1]), MAX_ERROR_LENGTH) }
}

if (typeof module !== "undefined" && module.exports) {
  module.exports = {
    DEFAULT_HELPER_DIR: DEFAULT_HELPER_DIR,
    MAX_ERROR_LENGTH: MAX_ERROR_LENGTH,
    validId: validId,
    displayName: displayName,
    expandPath: expandPath,
    parseInstanceListing: parseInstanceListing,
    instanceIds: instanceIds,
    isActive: isActive,
    sortRows: sortRows,
    listCommand: listCommand,
    statusCommand: statusCommand,
    actionCommand: actionCommand,
    WINDOW_SCRIPT: WINDOW_SCRIPT,
    windowCommand: windowCommand,
    windowButton: windowButton,
    unknownStatus: unknownStatus,
    parseStatus: parseStatus,
    stateLabel: stateLabel,
    resourcesLabel: resourcesLabel,
    levelLabel: levelLabel,
    hpLabel: hpLabel,
    manaLabel: manaLabel,
    statsLine: statsLine,
    previewState: previewState,
    PREVIEW_HINT: PREVIEW_HINT,
    lastStartLabel: lastStartLabel,
    proxyLabel: proxyLabel,
    buttonKind: buttonKind,
    buttonEnabled: buttonEnabled,
    ERROR_VISIBLE_S: ERROR_VISIBLE_S,
    stepLabel: stepLabel,
    returnButton: returnButton,
    refillButton: refillButton,
    spotButton: spotButton,
    cityInfo: cityInfo,
    worstClass: worstClass,
    pluralInstances: pluralInstances,
    hoverSentence: hoverSentence,
    parseActionResult: parseActionResult
  }
}
