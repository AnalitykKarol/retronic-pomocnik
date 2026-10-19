import QtQuick
import Quickshell
import "OknoModel.js" as Model
import "RetronicModel.js" as Rules

// Stan i procesy okna: odczyty z okno_api.py (stan wybranej postaci co 2 s, pełny stan co 5 s, ratunek i mapy-tryby dla
// otwartej sekcji) i akcje na botach. Akcje woła tymi samymi poleceniami co pasek (Rules.actionCommand z RetronicModel.js),
// "Start z tym" to uruchom.sh z MAPA/TRYB. Każdy rodzaj wywołania to osobny Job: jedno naraz, nic nie blokuje UI.
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

  property var instances: []
  property var statuses: ({})          // id -> Rules.parseStatus (ten sam kształt co na pasku)
  property bool loaded: false
  property string stanError: ""
  property var refreshedAt: null
  property string selectedId: ""
  property string section: "ratunek"   // mapa | ratunek (sesja gry i ustawienia: F4 i F3)

  property var ratunekData: null
  property string ratunekError: ""
  property var mapyData: null
  property string mapyError: ""

  // wybór mapy/trybów per instancja: id -> {mapa, tryby, touched}
  property var choices: ({})

  property bool actionBusy: false
  property var messages: ({})          // id -> krótki błąd ostatniej akcji (gaśnie sam)
  property string markNote: ""         // wynik "To fałszywy alarm"
  property string startNote: ""        // wynik "Start z tym"

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
    var known = false
    for (var j = 0; j < merged.length; j++) if (merged[j].id === selectedId) known = true
    instances = merged
    statuses = map
    refreshedAt = new Date()
    if (!known && merged.length) { selectedId = merged[0].id; refreshSection() }
    loaded = true
  }

  function select(id) {
    if (id === selectedId) return
    selectedId = id
    ratunekData = null
    ratunekError = ""
    mapyData = null
    mapyError = ""
    markNote = ""
    startNote = ""
    pollSelected()
    refreshSection()
  }

  function setSection(name) {
    if (name !== "mapa" && name !== "ratunek") return      // sesja gry (F4) i ustawienia (F3) jeszcze nie działają
    section = name
    refreshSection()
  }

  function refreshSection() {
    if (section === "ratunek") loadRatunek()
    else if (section === "mapa") loadMapy()
  }

  function loadRatunek() { ratunekJob.start(Model.ratunekCommand(repoDir, selectedId), selectedId) }
  function loadMapy() { mapyJob.start(Model.mapyCommand(repoDir, selectedId), selectedId) }

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

  function beginAction(command, id, kind) {
    if (!command || actionBusy || actionJob.pending) return false
    actionBusy = true
    setMessage(id, "")
    if (kind === "start-z-tym") startNote = ""
    actionKind = kind
    actionJob.start(command, id)
    return true
  }

  property string actionKind: ""

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

  function onActionFinished(text, id) {
    var result = Rules.parseActionResult(text)
    setMessage(id, result.ok ? "" : result.message)
    if (actionKind === "start-z-tym") startNote = result.ok ? "Start wysłany: " + Model.chosenText(choiceOf(id).mapa, choiceOf(id).tryby) : ""
    cooldown.restart()
    pollSelected()
    loadMapy()
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
  property Job ratunekJob: Job {
    timeoutMs: 8000
    onFinished: function(text, tag) { ctl.onRatunek(text, tag) }
  }
  property Job mapyJob: Job {
    timeoutMs: 8000
    onFinished: function(text, tag) { ctl.onMapy(text, tag) }
  }
  property Job markJob: Job {
    timeoutMs: 8000
    onFinished: function(text, tag) { ctl.onMarked(text, tag) }
  }
  property Job openJob: Job { timeoutMs: 8000 }
  // Skrypt, który wisi dłużej niż 25 s, jest przerywany i zgłasza błąd (jak na pasku).
  property Job actionJob: Job {
    timeoutMs: 25000
    timeoutText: "Przekroczono czas\nRC=124"
    onFinished: function(text, tag) { ctl.onActionFinished(text, tag) }
  }

  // Blokada ok. 1,5 s po akcji (jak na pasku): drugi klik nie trafi w przycisk, który zdążył zmienić się w przeciwny.
  property Timer cooldown: Timer {
    interval: 1500
    onTriggered: ctl.actionBusy = false
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
  property Timer allTimer: Timer {
    interval: 5000
    running: true
    repeat: true
    triggeredOnStart: true
    onTriggered: ctl.pollAll()
  }
  property Timer sectionTimer: Timer {
    interval: 5000
    running: true
    repeat: true
    onTriggered: ctl.refreshSection()
  }
}
