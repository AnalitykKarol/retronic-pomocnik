import QtQuick
import QtQuick.Controls
import Quickshell
import Quickshell.Io
import qs.Commons
import qs.Ui
import "RetronicModel.js" as Model

// Ikona "RT" na pasku (kolor = najgorszy stan botów) i panel po kliknięciu: wiersz na instancję
// z osobnym Stop/Start. Wtyczka jest cienka: czyta JSON panel.py i woła skrypty bota, własnej logiki bota nie ma.
Panel {
  id: root
  moduleName: "charlie.retronic"
  ipcTarget: "charlie.retronic"

  readonly property color foreground: bar ? bar.foreground : Color.foreground
  readonly property color urgent: bar ? bar.urgent : Color.urgent
  readonly property color dim: Qt.darker(foreground, 1.55)
  readonly property string fontFamily: bar ? bar.fontFamily : Style.font.family

  // Motyw Omarchy nie ma kolorów "ok"/"ostrzeżenie", więc stany mają własne; alarm i Stop biorą urgent z motywu.
  readonly property color okColor: "#6fbf73"
  readonly property color warnColor: "#d9a441"

  readonly property string helperDir: Model.expandPath(setting("helperDir", Model.DEFAULT_HELPER_DIR), Quickshell.env("HOME"))
  readonly property int refreshMs: Math.max(2, Math.min(60, Number(setting("refreshIntervalSec", 5)) || 5)) * 1000

  property var instanceIds: [""]
  property var rows: []
  property int statusRevision: 0

  // "Otwórz okno": jeden proces na cały panel (nie na instancję). Błąd gaśnie sam jak komunikaty akcji instancji.
  property bool windowBusy: false
  property string windowMessage: ""
  property bool windowPending: false

  readonly property var statuses: {
    root.statusRevision
    var out = []
    for (var i = 0; i < root.rows.length; i++) out.push(root.rows[i].status)
    return out
  }
  readonly property string worstClass: Model.worstClass(root.statuses)
  readonly property string summary: Model.hoverSentence(root.statuses)
  readonly property color iconColor: stateColor(root.worstClass)

  function stateColor(klasa) {
    if (klasa === "alarm") return root.urgent
    if (klasa === "dziala") return root.okColor
    if (klasa === "stop") return root.warnColor
    return root.dim
  }

  function alpha(c, a) { return Qt.rgba(c.r, c.g, c.b, a) }

  function refresh() {
    if (!listProcess.running) listProcess.running = true
    for (var i = 0; i < root.rows.length; i++) root.rows[i].poll()
  }

  function applyListing(text) {
    var ids = Model.instanceIds(text)
    // Ta sama lista = te same obiekty; przypisanie modelu zburzyłoby i odbudowało wszystkie instancje.
    if (JSON.stringify(ids) !== JSON.stringify(root.instanceIds)) root.instanceIds = ids
  }

  function openWindow() {
    if (windowBusy || windowProcess.running) return
    var command = Model.windowCommand(root.helperDir)
    if (!command) return
    windowBusy = true
    windowPending = true
    windowMessage = ""
    windowProcess.command = command
    windowProcess.running = true
    windowFallback.stop()
    windowTimeout.restart()
  }

  // Wynik: RC=0 = okno wystartowało albo dostało fokus, popup można zamknąć; inaczej krótki błąd w nagłówku.
  function finishWindow(text) {
    if (!windowPending) return
    windowPending = false
    windowTimeout.stop()
    windowFallback.stop()
    var result = Model.parseActionResult(text)
    windowMessage = result.ok ? "" : result.message
    if (windowMessage !== "") windowMessageFade.restart()
    windowCooldown.restart()
    if (result.ok) root.close()
  }

  function rebuildRows() {
    var result = []
    for (var i = 0; i < instances.count; i++) {
      var item = instances.objectAt(i)
      if (item) result.push(item)
    }
    root.rows = result
    root.statusRevision++
    for (var j = 0; j < result.length; j++) result[j].poll()
  }

  implicitWidth: button.implicitWidth
  implicitHeight: button.implicitHeight
  visible: true

  onOpenedChanged: if (opened) {
    root.refresh()
    Qt.callLater(function() { keyCatcher.forceActiveFocus() })
  }

  Process {
    id: listProcess
    command: Model.listCommand(root.helperDir)
    stdout: StdioCollector {
      waitForEnd: true
      onStreamFinished: root.applyListing(text)
    }
  }

  Process {
    id: windowProcess
    stdout: StdioCollector {
      id: windowOutput
      waitForEnd: true
      onStreamFinished: root.finishWindow(text)
    }
    onExited: windowFallback.restart()
  }

  Timer {
    id: windowFallback
    interval: 400
    onTriggered: root.finishWindow(windowOutput.text)
  }

  Timer {
    id: windowTimeout
    interval: 10000
    onTriggered: {
      windowProcess.running = false
      root.finishWindow("Przekroczono czas\nRC=124")
    }
  }

  Timer {
    id: windowCooldown
    interval: 1500
    onTriggered: root.windowBusy = false
  }

  Timer {
    id: windowMessageFade
    interval: 8000
    onTriggered: root.windowMessage = ""
  }

  Instantiator {
    id: instances
    model: root.instanceIds

    delegate: Instance {
      required property var modelData
      instanceId: modelData
      helperDir: root.helperDir
      onUpdated: root.statusRevision++
    }

    onObjectAdded: (index, object) => root.rebuildRows()
    onObjectRemoved: (index, object) => root.rebuildRows()
  }

  // Odczyt co refreshMs, bez demona. Działa też przy zamkniętym panelu: ikona ma pokazywać aktualny kolor.
  Timer {
    interval: root.refreshMs
    running: true
    repeat: true
    triggeredOnStart: true
    onTriggered: root.refresh()
  }

  BarIconButton {
    id: button
    anchors.fill: parent
    bar: root.bar
    text: "RT"
    slotSize: Style.bar.statusSlot
    foreground: root.iconColor
    tooltipText: root.summary
    onPressed: function(buttonCode) {
      if (buttonCode === Qt.RightButton) root.refresh()
      else root.toggle()
    }
  }

  KeyboardPanel {
    id: panel
    anchorItem: button
    owner: root
    bar: root.bar
    open: root.opened
    focusTarget: keyCatcher
    contentWidth: panel.fittedContentWidth(Style.space(380))
    contentHeight: panel.fittedContentHeight(column.implicitHeight, Style.space(560))

    // Celowo bez activateRequested (Enter/Spacja): Stop i Start tylko myszą, żeby nie trafić w nie klawiszem.
    PanelKeyCatcher {
      id: keyCatcher
      anchors.fill: parent
      onCloseRequested: root.close()
      onTabRequested: function(direction) { root.switchPanel(direction) }
      onTextKey: function(t) { if (t === "r" || t === "R") root.refresh() }

      Flickable {
        id: panelFlick
        anchors.fill: parent
        contentWidth: width
        contentHeight: column.implicitHeight
        clip: true
        boundsBehavior: Flickable.StopAtBounds
        flickableDirection: Flickable.VerticalFlick
        interactive: contentHeight > height
        ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }

        PanelContent {
          id: column
          width: panelFlick.width
          rows: root.rows
          summary: root.summary
          foreground: root.foreground
          urgent: root.urgent
          okColor: root.okColor
          warnColor: root.warnColor
          fontFamily: root.fontFamily
          windowBusy: root.windowBusy
          windowMessage: root.windowMessage
          onOpenWindowRequested: root.openWindow()
        }
      }
    }
  }
}
