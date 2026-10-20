import QtQuick
import Quickshell.Io
import "RetronicModel.js" as Model

// Jedna instancja Retronic: odczyt statusu (panel.py --json) i jej własne akcje (Stop/Start, Wróć do miasta, Refill).
// Nie wie nic o innych instancjach; Panel.qml trzyma ich listę i rysuje wiersze.
QtObject {
  id: root

  property string instanceId: ""
  property string helperDir: ""

  // Wynik Model.parseStatus; null do pierwszego odczytu.
  property var status: null
  // Krótki błąd ostatniej akcji (np. "Gra nie działa"); gaśnie sam.
  property string message: ""
  // Akcja w toku albo tuż po niej: przycisk jest wtedy zablokowany, żeby ten sam klik
  // nie trafił w przycisk, który po zmianie stanu zamienił się Stop <-> Start.
  property bool busy: false
  readonly property bool pending: statusPending || actionPending

  property bool statusPending: false
  property bool actionPending: false

  signal updated()

  function poll() {
    if (statusProcess.running || !helperDir) return
    var command = Model.statusCommand(helperDir, instanceId)
    if (!command) return
    statusProcess.command = command
    statusPending = true
    statusProcess.running = true
  }

  // kind: "stop" | "start" | "wroc" | "wroc-anuluj" | "refill" | "spot" | "refill-stop" | "podglad" (patrz ACTION_SCRIPTS w modelu).
  // Skrypty bota dostają tylko RETRONIC_ID tej instancji. "refill" i "spot" odpalają serwis ODŁĄCZONY (refill.sh --tlo/--spot wraca od razu),
  // więc ten sam timeout 25 s co przy Start wystarcza; postęp widać w statusie (serwis_*), nie w wyniku akcji.
  function run(kind) {
    if (busy || actionProcess.running) return
    var command = Model.actionCommand(helperDir, instanceId, kind)
    if (!command) return
    busy = true
    message = ""
    actionProcess.command = command
    actionPending = true
    actionProcess.running = true
    actionTimeout.restart()
  }

  function finishStatus(text) {
    if (!statusPending) return
    statusPending = false
    status = Model.parseStatus(text)
    updated()
  }

  function finishAction(text) {
    if (!actionPending) return
    actionPending = false
    actionTimeout.stop()
    var result = Model.parseActionResult(text)
    message = result.ok ? "" : result.message
    if (message !== "") messageFade.restart()
    cooldown.restart()
    poll()
  }

  property Process statusProcess: Process {
    stdout: StdioCollector {
      id: statusOutput
      waitForEnd: true
      onStreamFinished: root.finishStatus(text)
    }
    // Proces, który nie wystartował, nie zamyka strumienia: po jego wyjściu domykamy odczyt sami.
    onExited: root.statusFallback.restart()
  }

  property Process actionProcess: Process {
    stdout: StdioCollector {
      id: actionOutput
      waitForEnd: true
      onStreamFinished: root.finishAction(text)
    }
    onExited: root.actionFallback.restart()
  }

  property Timer statusFallback: Timer {
    interval: 400
    onTriggered: root.finishStatus(statusOutput.text)
  }

  property Timer actionFallback: Timer {
    interval: 400
    onTriggered: root.finishAction(actionOutput.text)
  }

  // Skrypt, który wisi dłużej niż 25 s, jest przerywany (SIGTERM) i zgłasza błąd.
  property Timer actionTimeout: Timer {
    interval: 25000
    onTriggered: {
      root.actionProcess.running = false
      root.finishAction("Przekroczono czas\nRC=124")
    }
  }

  property Timer cooldown: Timer {
    interval: 1500
    onTriggered: {
      root.busy = false
      root.poll()
    }
  }

  property Timer messageFade: Timer {
    interval: 8000
    onTriggered: root.message = ""
  }
}
