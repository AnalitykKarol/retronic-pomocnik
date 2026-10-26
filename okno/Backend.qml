import QtQuick
import Quickshell
import "OknoModel.js" as Model
import "UstawieniaModel.js" as Ust
import "RetronicModel.js" as Rules
import "PrzegladModel.js" as Prz

// Stan i procesy okna: odczyty z okno_api.py (stan wybranej postaci co 2 s, pełny stan co 5 s, ratunek i mapy-tryby dla
// otwartej sekcji) i akcje na botach. Akcje woła tymi samymi poleceniami co pasek (Rules.actionCommand z RetronicModel.js),
// "Start z tym" to uruchom.sh z MAPA/TRYB. Ustawienia (F3): odczyt `pokretla`, zapis `ustaw` (od razu po puszczeniu suwaka / kliknięciu,
// kolejka po jednym wywołaniu naraz) i `cofnij` — walidacja, kopia .bak i dziennik są w okno_api.py. Każdy rodzaj wywołania to osobny Job.
QtObject {
  id: ctl

  function envOr(name, fallback) {
    var v = Quickshell.env(name)
    return v ? String(v) : fallback
  }

  // Repo bota = katalog nad okno/ (tam okno_api.py); dane i skrypty akcji = RETRONIC_OKNO_KATALOG (atrapa w testach) albo to samo repo.
  readonly property string repoDir: envOr("RETRONIC_OKNO_REPO", String(Quickshell.shellDir) + "/..")
  readonly property string helperDir: envOr("RETRONIC_OKNO_KATALOG", repoDir)
  readonly property string opener: envOr("RETRONIC_OKNO_OTWIERACZ", "xdg-open")
  readonly property string sortFile: envOr("RETRONIC_OKNO_SORT_PLIK", envOr("XDG_STATE_HOME", envOr("HOME", "") + "/.local/state") + "/retronic-okno/sortowanie")

  property var instances: []
  property var statuses: ({})          // id -> Rules.parseStatus (ten sam kształt co na pasku)
  property bool loaded: false
  property string stanError: ""
  property var refreshedAt: null
  property string selectedId: ""
  // Stracone postacie (profil `stracony`) są domyślnie ukryte w pasku bocznym i stopce (25.10); przełącznik „pokaż stracone” w pasku,
  // chip „stracone” w Przeglądzie działa niezależnie. Klik w straconą w Przeglądzie (openChar) włącza showLost, żeby wybór nie spadł.
  property bool showLost: false
  property string section: "przeglad"   // przeglad | sesja | mapa | ustawienia | spotkania (26.10: „Spotkania” zajęło miejsce „Ratunek” w menu; RATUNEK_HAIKU=0 u wszystkich)
  // Sortowanie postaci (25.10; domyślnie poziom ↓): jedno ustawienie dla tabeli Przeglądu i listy w pasku bocznym (prosto i spójnie). Zmiana nie resetuje się
  // przy odświeżeniu stanu i przeżywa restart okna: zapis w pliku stanu okna (jedna linia z kluczem; RETRONIC_OKNO_SORT_PLIK albo ~/.local/state/retronic-okno/sortowanie).
  property string sortKey: Prz.DEFAULT_SORT
  property bool sortTouched: false      // wybór zrobiony przed odczytem pliku wygrywa z plikiem
  property bool sortDirty: false        // zapis czeka, bo poprzedni jeszcze trwa

  property var ratunekData: null           // Ratunek wyłączony z menu (26.10): nic go już nie odczytuje, pola zostają dla RatunekView.qml
  property string ratunekError: ""
  // Spotkania z graczami (26.10): `okno_api spotkania` = zmiany spotu dziś i unikane spoty (+ pełne wpisy); liczniki kart i tabeli idą ze `stan` (inst.spotkania).
  // Zaplecze liczy z telemetrii i trzyma wynik w cache (60 s), więc odpytujemy co 30 s zawsze (karty potrzebują cache) i co 5 s przy otwartej zakładce.
  property var spotkaniaData: null
  property string spotkaniaError: ""
  property var mapyData: null
  property string mapyError: ""

  // ---- Sesja gry (F4b): odczyt `okno_api sesja` wybranej instancji (co 2 s przy otwartej sekcji) i wynik ostatniej akcji
  property var sesjaData: null
  property string sesjaRaw: ""             // surowa odpowiedź: identyczna nie przebudowuje widoku
  property string sesjaError: ""
  property var sesjaNote: ({ id: "", text: "", tone: "" })     // wynik ostatniej akcji: tone ok | bad
  property string sesjaStarted: ""         // id instancji, której start właśnie się udał (podpowiedź "zaloguj postać w podglądzie")

  // ---- Ustawienia (F3): pokrętła wybranej instancji
  property var pokretlaData: null
  property string pokretlaRaw: ""          // surowa odpowiedź: identyczna nie przebudowuje widoku (nie gubi fokusu pola ani suwaka)
  property string pokretlaError: ""
  property bool pokretlaStale: false       // odczyt w toku jest już nieaktualny (zapis w międzyczasie): po nim czytamy jeszcze raz
  property var writeQueue: []
  property var knobNote: ({ text: "", tone: "" })      // wynik ostatniego zapisu/cofnięcia: tone ok | bad
  property string settingsGroup: ""
  property string settingsText: ""
  property bool settingsOnlyChanged: false
  property string focusKey: ""             // pokrętło do pokazania w widoku (Ctrl+K Enter)
  property int focusSerial: 0
  property bool paletteOpen: false
  readonly property var knobs: Ust.allKnobs(pokretlaData)
  readonly property var knobsByKey: Ust.byKeyMap(knobs)
  readonly property bool knobBusy: ustawJob.pending || cofnijJob.pending || writeQueue.length > 0

  // wybór mapy/trybów per instancja: id -> {mapa, tryby, touched}
  property var choices: ({})

  // Akcje na botach i sesjach: zajętość jest PER INSTANCJA (busyIds: id -> true; Model.busyBegin/busyEnd). Jedna akcja naraz na instancję,
  // ale długie `Zamknij grę` jednej postaci nie szarzy Stop/⌂ Miasto innych. Każda instancja ma własny przebieg (Job + cooldown), patrz runFor.
  property var busyIds: ({})
  property var runs: ({})              // id -> przebieg akcji (obiekt z runFactory)
  property var messages: ({})          // id -> krótki błąd ostatniej akcji (gaśnie sam)
  property string markNote: ""         // wynik "To fałszywy alarm"
  property string startNote: ""        // wynik "Start z tym"
  // „Zaloguj postać” (24.10): jedno logowanie naraz z okna. loginId = instancja, której logowanie trwa ("" brak; główna ma id "", ale się nie loguje).
  // loginNotes: id -> {ok, text}, wynik ostatniego logowania (gaśnie po 40 s, patrz loginFade).
  property string loginId: ""
  property var loginNotes: ({})

  readonly property var visibleInstances: Prz.sortInstances(Prz.visibleInstances(instances, showLost), sortKey, refreshedAt || new Date())
  readonly property int lostCount: Prz.lostCount(instances)
  readonly property var selected: {
    for (var i = 0; i < instances.length; i++) if (instances[i].id === selectedId) return instances[i]
    return null
  }
  readonly property var selectedStatus: selected ? statuses[selected.id] || null : null

  // ------------------------------------------------------------ odczyt stanu

  function pollAll() { allJob.start(Model.stanCommand(repoDir, null), "") }
  function pollSelected() { if (loaded) selJob.start(Model.stanCommand(repoDir, selectedId), selectedId) }

  function onStan(text, only) {
    var r = Model.parseApi(text)
    if (!r.ok) { stanError = r.blad; return }
    stanError = ""
    var merged = Model.mergeInstances(instances, r.data.instancje || [], only)
    var map = {}
    for (var i = 0; i < merged.length; i++) map[merged[i].id] = Rules.parseStatus(Model.panelOutput(merged[i]))
    var pick = Prz.selectionAfter(merged, selectedId, showLost)       // wybrana postać stała się stracona/ukryta lub zniknęła: pierwsza widoczna
    var changed = pick !== selectedId
    instances = merged
    statuses = map
    refreshedAt = new Date()
    if (changed && merged.length) { selectedId = pick; refreshSection() }
    loaded = true
  }

  // Przełącznik „pokaż stracone” (pasek boczny). Ukrycie, gdy wybrana jest stracona: wybór spada na pierwszą widoczną.
  function setShowLost(on) {
    showLost = on
    var pick = Prz.selectionAfter(instances, selectedId, showLost)
    if (pick !== selectedId) select(pick)
  }

  // Wybór sortowania (chipy w Przeglądzie): zapamiętany w pliku, żeby przeżył restart okna. Nieznany klucz = bez zmian.
  function setSort(key) {
    var k = Prz.validSort(key)
    if (!k) return
    sortTouched = true
    if (k === sortKey) return
    sortKey = k
    saveSort()
  }

  function saveSort() {
    var cmd = ["sh", "-c", "mkdir -p \"$(dirname \"$1\")\" && printf '%s\\n' \"$2\" > \"$1\"", "sh", sortFile, sortKey]
    if (!sortWriteJob.start(cmd, sortKey)) sortDirty = true
  }

  function onSortSaved() {
    if (sortDirty) { sortDirty = false; saveSort() }
  }

  function onSortLoaded(text) {
    var k = Prz.validSort(text)
    if (k && !sortTouched) sortKey = k
  }

  Component.onCompleted: sortReadJob.start(["sh", "-c", "cat \"$1\" 2>/dev/null", "sh", sortFile], "")

  function select(id) {
    if (id === selectedId) return
    selectedId = id
    ratunekData = null
    ratunekError = ""
    mapyData = null
    mapyError = ""
    sesjaData = null
    sesjaRaw = ""
    sesjaError = ""
    // sesjaNote i sesjaStarted niosą id instancji i widok pokazuje je tylko jej: akcja zakończona po przełączeniu postaci nie ginie
    pokretlaData = null
    pokretlaRaw = ""
    pokretlaError = ""
    setKnobNote("", "")           // kolejka zapisów zostaje: elementy niosą własne id instancji (onUstaw)
    markNote = ""
    startNote = ""
    pollSelected()
    refreshSection()
  }

  function setSection(name) {
    if (name !== "przeglad" && name !== "sesja" && name !== "mapa" && name !== "spotkania" && name !== "ustawienia") return
    section = name
    refreshSection()
  }

  // Klik w wiersz Przeglądu / kartę postaci w Przeglądzie: wybiera postać i otwiera jej Sesję gry (spec przeglądu: „klik w wiersz otwiera postać”).
  function openChar(id) {
    for (var i = 0; i < instances.length; i++) if (instances[i].id === id && Prz.isLost(instances[i])) showLost = true
    select(id)
    setSection("sesja")
  }

  function refreshSection() {
    if (section === "przeglad") return           // Przegląd czyta tylko stan z pollAll (instances), własnego odczytu nie ma
    if (section === "sesja") loadSesja()
    else if (section === "spotkania") loadSpotkania()
    else if (section === "mapa") loadMapy()
    else if (section === "ustawienia") { loadPokretla(); loadMapy() }       // mapy-tryby: ostrzeżenie o trybie z ostatniego startu
  }

  function loadRatunek() { ratunekJob.start(Model.ratunekCommand(repoDir, selectedId), selectedId) }       // nieużywane od 26.10 (sekcja wyłączona z menu)
  function loadSpotkania() { spotkaniaJob.start(Model.spotkaniaCommand(repoDir), "") }

  function onSpotkania(text) {
    var r = Model.parseApi(text)
    if (!r.ok) { spotkaniaError = r.blad; return }       // dane z poprzedniego odczytu zostają widoczne; błąd pokazuje widok
    spotkaniaError = ""
    spotkaniaData = r.data
  }
  function loadMapy() { mapyJob.start(Model.mapyCommand(repoDir, selectedId), selectedId) }

  function loadSesja() { sesjaJob.start(Model.sesjaCommand(repoDir, selectedId), selectedId) }

  function onSesja(text, id) {
    if (id !== selectedId) { loadSesja(); return }          // odpowiedź dla poprzednio wybranej postaci
    var r = Model.parseApi(text)
    if (!r.ok) { sesjaError = r.blad; return }
    sesjaError = ""
    if (text === sesjaRaw) return
    sesjaRaw = text
    sesjaData = r.data
    if (!r.data.sesja && sesjaStarted === id && !r.data.mozna_zamknac) sesjaStarted = ""     // sesja już nie żyje: podpowiedź nieaktualna
  }

  function setSesjaNote(id, text, tone) {
    sesjaNote = { id: id, text: text, tone: tone }
    if (text !== "") sesjaNoteFade.restart()
  }

  // gra-start | gra-zamknij | podglad dla wybranej instancji; bramka jak guzik: szary nie wystartuje (Model.sessionButtons).
  function sessionAction(kind) {
    if (!Model.isSessionAction(kind) || !sesjaData) return false
    if (!Model.sessionButtons(sesjaData)[kind].enabled) return false
    setSesjaNote(selectedId, "", "")
    return beginAction(Rules.actionCommand(helperDir, selectedId, kind), selectedId, kind)
  }

  // Klik w nick na karcie postaci: podgląd tej instancji (te same stany co znacznik: Rules.previewState).
  function previewFor(id) {
    var ps = Rules.previewState(statuses[id] || null, id)
    if (!ps.enabled) return false
    return beginAction(Rules.actionCommand(helperDir, id, "podglad"), id, "podglad")        // null (np. pusty id) -> beginAction odmawia
  }

  function onSessionAction(text, id, kind) {
    var r = Model.parseSessionAction(text, kind)
    setSesjaNote(id, Model.sessionActionLabel(kind) + ": " + r.message, r.ok ? "ok" : "bad")
    if (kind === "gra-start") sesjaStarted = r.ok ? id : (sesjaStarted === id ? "" : sesjaStarted)
    else if (kind === "gra-zamknij" && r.ok && sesjaStarted === id) sesjaStarted = ""
    if (!r.ok && kind === "podglad") setMessage(id, r.message)       // także w pasku bocznym (klik w nick nie otwiera sekcji)
    pollSelected()
    pollAll()
    if (id === selectedId) loadSesja()
  }

  function onRatunek(text, id) {
    var r = Model.parseApi(text)
    if (id !== selectedId) { loadRatunek(); return }       // odpowiedź dla poprzednio wybranej postaci
    if (!r.ok) { ratunekError = r.blad; return }
    ratunekError = ""
    ratunekData = r.data
  }

  function onMapy(text, id) {
    var r = Model.parseApi(text)
    if (id !== selectedId) { loadMapy(); return }
    if (!r.ok) { mapyError = r.blad; return }
    mapyError = ""
    mapyData = r.data
    // Wybór, którego użytkownik nie ruszył, podąża za "ostatnio użytym" (pierwszy odczyt i po starcie bota); ruszony zostaje.
    // Przypisujemy tylko przy realnej zmianie: każda zmiana `choices` zamyka otwarte potwierdzenie startu.
    var c = choices[id]
    var o = r.data.ostatni || {}
    var lastTryb = o.tryb || []
    if (!c || (!c.touched && !Model.isLastChoice({ mapa: o.mapa || "", tryb: lastTryb }, c.mapa, c.tryby))) {
      setChoice(id, o.mapa || "", lastTryb.slice(), false)
    }
  }

  // ------------------------------------------------------------ ustawienia: odczyt, zapis, cofnięcie

  function loadPokretla() {
    if (pokretlaJob.pending) { pokretlaStale = true; return }
    pokretlaJob.start(Ust.pokretlaCommand(repoDir, selectedId), selectedId)
  }

  function onPokretla(text, id) {
    if (id !== selectedId) { loadPokretla(); return }      // odpowiedź dla poprzednio wybranej postaci
    if (pokretlaStale || writeBusyNow()) { pokretlaStale = false; loadPokretla(); return }    // odczyt sprzed zapisu: nie nadpisuj, czytaj od nowa
    var r = Model.parseApi(text)
    if (!r.ok) { pokretlaError = r.blad; return }
    pokretlaError = ""
    if (text === pokretlaRaw) return
    pokretlaRaw = text
    pokretlaData = r.data
    var groups = Ust.buildGroups(r.data, Ust.allKnobs(r.data))
    var known = false
    for (var i = 0; i < groups.length; i++) if (groups[i].nazwa === settingsGroup) known = true
    if (!known && groups.length) settingsGroup = groups[0].nazwa      // pierwsza = Runy (UH)
  }

  function writeBusyNow() { return ustawJob.pending || writeQueue.length > 0 }

  function setKnobNote(text, tone) {
    knobNote = { text: text, tone: tone }
    if (text !== "") noteFade.restart()
  }

  // Jedno pokrętło (suwak, przełącznik, wybór, pole). Zapis idzie od razu (Q3); wartość spoza zakresu odrzuca już okno.
  function setKnob(klucz, wartosc) {
    var changes = {}
    changes[klucz] = wartosc
    queueWrite(changes)
  }

  // Zestaw (kilka pokręteł) = jedno wywołanie `ustaw` = jeden wpis dziennika = jedno "Cofnij ostatnią".
  function queueWrite(changes) {
    var cmd = Ust.ustawCommand(repoDir, selectedId, changes, knobsByKey)
    if (!cmd) { setKnobNote("nie zapisano: wartość poza zakresem lub spoza listy", "bad"); return false }
    var copy = writeQueue.slice()
    copy.push({ cmd: cmd, changes: changes, id: selectedId })
    writeQueue = copy
    pumpWrites()
    return true
  }

  function pumpWrites() {
    if (ustawJob.pending || cofnijJob.pending || writeQueue.length === 0) return
    var item = writeQueue[0]
    writeQueue = writeQueue.slice(1)
    ustawJob.start(item.cmd, item.id)
  }

  function onUstaw(text, id) {
    var r = Model.parseApi(text)
    if (id !== selectedId) {
      // zapis z kolejki dla postaci, którą użytkownik już przełączył: błąd nie może zginąć po cichu
      if (!r.ok) setKnobNote("nie zapisano (" + nickOfId(id) + "): " + r.blad, "bad")
    } else {
      if (!r.ok) setKnobNote("nie zapisano: " + r.blad, "bad")
      else if (Object.keys(r.data.zmienione || {}).length === 0) setKnobNote("bez zmian: wartość już jest ustawiona", "ok")
      else {
        pokretlaData = Ust.applyChanges(pokretlaData, r.data.zmienione)      // od razu widać; prawdę dociąga odczyt poniżej
        pokretlaRaw = ""
        setKnobNote("zapisano " + Ust.describeChange(r.data.zmienione, r.data.poprzednie, knobsByKey) + " · bot czyta na_zywo.json w locie", "ok")
      }
    }
    loadPokretla()
    pumpWrites()
  }

  function nickOfId(id) {
    for (var i = 0; i < instances.length; i++) if (instances[i].id === id) return Model.nickOf(instances[i])
    return id === "" ? "główna" : id
  }

  function undo() {
    if (knobBusy) return
    var last = pokretlaData ? pokretlaData.ostatnia_zmiana : null
    var cmd = Ust.cofnijCommand(repoDir, selectedId, last && typeof last.epoch === "number" ? last.epoch : undefined)
    if (cmd) cofnijJob.start(cmd, selectedId)
  }

  function onCofnij(text, id) {
    var r = Model.parseApi(text)
    if (id === selectedId) {
      if (!r.ok) setKnobNote("nie cofnięto: " + r.blad, "bad")
      else setKnobNote("cofnięto " + Ust.describeUndo(r.data, knobsByKey) + (r.data.pominiete && r.data.pominiete.length ? " (pominięto: " + r.data.pominiete.length + ")" : ""), "ok")
    }
    pokretlaRaw = ""
    loadPokretla()
  }

  function applyPreset(preset) {
    return queueWrite(preset.pary)
  }

  // Ctrl+K Enter: pokrętło w widoku Ustawień (filtr wyczyszczony, grupa pokrętła, przewinięcie i mignięcie wiersza).
  function openKnob(klucz) {
    var p = knobsByKey[klucz]
    settingsText = ""
    settingsOnlyChanged = false
    if (p) settingsGroup = p.grupaUI
    focusKey = klucz
    focusSerial++
    setSection("ustawienia")
  }

  function openPalette() {
    if (!loaded) return
    paletteOpen = true
    loadPokretla()
    loadMapy()
  }

  function closePalette() { paletteOpen = false }

  // ------------------------------------------------------------ wybór mapy i trybów

  function choiceOf(id) { return choices[id] || { mapa: "", tryby: [], touched: false } }

  function setChoice(id, mapa, tryby, touched) {
    var copy = {}
    for (var k in choices) copy[k] = choices[k]
    copy[id] = { mapa: mapa, tryby: tryby, touched: touched }
    choices = copy
  }

  function chooseMap(name) {
    var c = choiceOf(selectedId)
    setChoice(selectedId, name, c.tryby, true)
    startNote = ""
  }

  function toggleMode(name) {
    var c = choiceOf(selectedId)
    setChoice(selectedId, c.mapa, Model.toggleMode(c.tryby, name), true)
    startNote = ""
  }

  function useLast() {
    var o = mapyData && mapyData.ostatni ? mapyData.ostatni : {}
    setChoice(selectedId, o.mapa || "", (o.tryb || []).slice(), false)
    startNote = ""
  }

  // ------------------------------------------------------------ akcje na botach

  function setMessage(id, text) {
    var copy = {}
    for (var k in messages) copy[k] = messages[k]
    copy[id] = text
    messages = copy
    if (text !== "") messageFade.restart()
  }

  function isBusy(id) { return Model.isBusy(busyIds, id) }

  // Przebieg akcji instancji `id` (Job + cooldown), tworzony przy pierwszej akcji i używany ponownie.
  function runFor(id) {
    if (!runs[id]) {
      var copy = {}
      for (var k in runs) copy[k] = runs[k]
      copy[id] = runFactory.createObject(ctl, { runId: id, owner: ctl })
      runs = copy
    }
    return runs[id]
  }

  function endBusy(id) { busyIds = Model.busyEnd(busyIds, id) }

  // Jedna akcja naraz NA INSTANCJĘ (id); akcje innych instancji idą równolegle. Zamknięcie gry ma limit 120 s (Model.actionTimeoutMs).
  function beginAction(command, id, kind) {
    if (!command || isBusy(id)) return false
    var run = runFor(id)
    if (run.job.pending) return false
    busyIds = Model.busyBegin(busyIds, id)
    setMessage(id, "")
    if (kind === "start-z-tym" && id === selectedId) startNote = ""
    run.kind = kind
    run.job.timeoutMs = Model.actionTimeoutMs(kind)
    if (!run.job.start(command, id)) { endBusy(id); return false }
    if (kind === Model.LOGIN_KIND) { loginId = id; setLoginNote(id, null) }
    return true
  }

  function setLoginNote(id, note) {
    var copy = {}
    for (var k in loginNotes) copy[k] = loginNotes[k]
    if (note === null) delete copy[id]
    else copy[id] = note
    loginNotes = copy
    if (note !== null) loginFade.restart()
  }

  // „Zaloguj postać”: loguje postać instancji `id` do gry BEZ bota (zaloguj_postac.sh). Stan guzika liczy Model.loginState;
  // to samo sprawdzenie stoi tu, żeby klik z innej ścieżki (scenariusz) nie ominął szarości.
  function loginState(id) {
    var inst = null
    for (var i = 0; i < instances.length; i++) if (instances[i].id === id) inst = instances[i]
    return Model.loginState(inst, { loginId: loginId, busy: isBusy(id) })
  }

  function runLogin(id) {
    if (!loginState(id).enabled) return false
    return beginAction(Rules.actionCommand(helperDir, id, Model.LOGIN_KIND), id, Model.LOGIN_KIND)
  }

  // kind: stop | start | wroc | wroc-anuluj | refill | spot | refill-stop (Rules.ACTION_SCRIPTS: dokładnie to, co robi pasek)
  function runAction(kind) {
    beginAction(Rules.actionCommand(helperDir, selectedId, kind), selectedId, kind)
  }

  function startWithChoice() {
    var c = choiceOf(selectedId)
    var state = Model.startState(selectedStatus, c.mapa)
    if (!state.enabled) return
    beginAction(Model.startCommand(helperDir, selectedId, c.mapa, c.tryby, selected ? selected.nick : ""), selectedId, "start-z-tym")
  }

  // Wynik akcji instancji `id` (rodzaj niesie jej własny przebieg: równoległe akcje innych instancji go nie nadpisują).
  function onActionFinished(text, id, kind) {
    runFor(id).cooldown.restart()                                  // blokada tej instancji ok. 1,5 s po akcji
    if (kind === Model.LOGIN_KIND) {
      var login = Model.parseLoginResult(text)
      if (loginId === id) loginId = ""
      setLoginNote(id, { ok: login.ok, text: login.message })
      pollSelected()
      pollAll()
      return
    }
    if (Model.isSessionAction(kind)) { onSessionAction(text, id, kind); return }
    var result = Rules.parseActionResult(text)
    setMessage(id, result.ok ? "" : result.message)
    if (kind === "start-z-tym" && id === selectedId) startNote = result.ok ? "Start wysłany: " + Model.chosenText(choiceOf(id).mapa, choiceOf(id).tryby) : ""
    pollSelected()
    pollAll()
    if (id === selectedId) loadMapy()
  }

  function markFalse(signalId) {
    if (markJob.pending) return
    markNote = ""
    markJob.start(Model.oznaczCommand(repoDir, selectedId, signalId), selectedId)
  }

  function onMarked(text, id) {
    var r = Model.parseApi(text)
    markNote = r.ok ? "oznaczono jako fałszywy alarm" : "nie zapisano: " + r.blad
    if (id === selectedId) loadRatunek()
  }

  function openLog(path) {
    if (!path || openJob.pending) return
    openJob.start([opener, path], "")
  }

  // ------------------------------------------------------------ procesy i zegary

  property Job allJob: Job {
    timeoutMs: 6000
    onFinished: function(text, tag) { ctl.onStan(text, null) }
  }
  property Job selJob: Job {
    timeoutMs: 5000
    onFinished: function(text, tag) { ctl.onStan(text, tag) }
  }
  property Job sesjaJob: Job {
    timeoutMs: 8000
    onFinished: function(text, tag) { ctl.onSesja(text, tag) }
  }
  property Job ratunekJob: Job {
    timeoutMs: 8000
    onFinished: function(text, tag) { ctl.onRatunek(text, tag) }
  }
  property Job spotkaniaJob: Job {
    timeoutMs: 30000                       // pierwsze obliczenie z telemetrii trwa kilka sekund; potem cache 60 s
    onFinished: function(text, tag) { ctl.onSpotkania(text) }
  }
  property Job mapyJob: Job {
    timeoutMs: 8000
    onFinished: function(text, tag) { ctl.onMapy(text, tag) }
  }
  property Job pokretlaJob: Job {
    timeoutMs: 8000
    onFinished: function(text, tag) { ctl.onPokretla(text, tag) }
  }
  property Job ustawJob: Job {
    timeoutMs: 8000
    onFinished: function(text, tag) { ctl.onUstaw(text, tag) }
  }
  property Job cofnijJob: Job {
    timeoutMs: 8000
    onFinished: function(text, tag) { ctl.onCofnij(text, tag) }
  }
  property Job markJob: Job {
    timeoutMs: 8000
    onFinished: function(text, tag) { ctl.onMarked(text, tag) }
  }
  property Job openJob: Job { timeoutMs: 8000 }
  property Job sortReadJob: Job {
    timeoutMs: 3000
    onFinished: function(text, tag) { ctl.onSortLoaded(text) }
  }
  property Job sortWriteJob: Job {
    timeoutMs: 3000
    onFinished: function(text, tag) { ctl.onSortSaved() }
  }
  // Przebieg akcji jednej instancji: ActionRun.qml (Job + cooldown), patrz runFor.
  property Component runFactory: Component { ActionRun {} }

  property Timer sesjaNoteFade: Timer {
    interval: 20000
    onTriggered: ctl.sesjaNote = ({ id: "", text: "", tone: "" })
  }
  property Timer noteFade: Timer {
    interval: 12000
    onTriggered: ctl.knobNote = ({ text: "", tone: "" })
  }
  property Timer loginFade: Timer {
    interval: 40000
    onTriggered: ctl.loginNotes = ({})
  }
  property Timer messageFade: Timer {
    interval: 8000
    onTriggered: ctl.messages = ({})
  }

  property Timer selTimer: Timer {
    interval: 2000
    running: true
    repeat: true
    onTriggered: ctl.pollSelected()
  }
  // Sesja gry odświeża się co 2 s tylko przy otwartej sekcji (jedno wywołanie naraz: Job odrzuca następne, gdy poprzednie trwa)
  property Timer sesjaTimer: Timer {
    interval: 2000
    running: ctl.section === "sesja" && ctl.loaded
    repeat: true
    onTriggered: ctl.loadSesja()
  }
  property Timer allTimer: Timer {
    interval: 5000
    running: true
    repeat: true
    triggeredOnStart: true
    onTriggered: ctl.pollAll()
  }
  // Odświeżanie danych spotkań: zawsze co 30 s po pierwszym odczycie stanu (karty postaci pokazują licznik z cache zaplecza), zakładka dodatkowo co 5 s (sectionTimer)
  property Timer spotkaniaTimer: Timer {
    interval: 30000
    running: ctl.loaded
    repeat: true
    triggeredOnStart: true
    onTriggered: ctl.loadSpotkania()
  }
  property Timer sectionTimer: Timer {
    interval: 5000
    running: true
    repeat: true
    onTriggered: ctl.refreshSection()
  }
}
