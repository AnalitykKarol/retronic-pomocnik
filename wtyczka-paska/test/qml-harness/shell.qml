import QtQuick
import Quickshell
import qs.Commons
import "RetronicModel.js" as Model

// Harness QA (offscreen), uruchamiany przez ../qml-podglad.sh: PanelContent na atrapie statusów, nic nie uruchamia. Klik w nick = log "run <id> <kind>".
ShellRoot {
  id: shell
  readonly property string out: Quickshell.env("PASEK_WYNIK")

  function pj(klasa, tip, extra) {
    return JSON.stringify(Object.assign({ text: "RT", class: klasa, alt: klasa, tooltip: tip }, extra)) + "\nPROXY=1\n--ENV--\nMAPA=gobliny_edron\nTRYB=ostrozny\n"
  }
  component FakeInst: QtObject {
    property string instanceId: ""
    property var status: null
    property bool busy: false
    property string message: ""
    property var calls: []
    function run(kind) { calls.push(kind); console.log("scenariusz run " + instanceId + " " + kind) }
  }
  property var rows: [
    fake("", pj("dziala", "Retronic: działa\nTryb: mozg.py hybryda, działa 2h 05m\nHP 410/410  mana 120/120", { podglad: { port: null, otwarty: false, pid: null } })),
    fake("invincible", pj("dziala", "Retronic: działa\nTryb: mozg.py hybryda, działa 8m 26s\nHP 170/170  mana 20/20  lvl 8 (35%)", { level: 8, level_procent: 35.2, podglad: { port: 5901, otwarty: true, pid: 4242 } })),
    fake("test", pj("stop", "Retronic: zatrzymany", { podglad: { port: 5902, otwarty: false, pid: null } })),
    fake("startup", pj("brak", "Retronic: gra nie działa", { podglad: { port: 5903, otwarty: false, pid: null } })),
    fake("ghost", pj("brak", "Retronic: gra nie działa", { podglad: { port: null, otwarty: false, pid: null } }))
  ]
  function fake(id, text) { return fakeComp.createObject(shell, { instanceId: id, status: Model.parseStatus(text) }) }
  Component { id: fakeComp; FakeInst {} }

  FloatingWindow {
    id: win
    implicitWidth: 420
    implicitHeight: 700
    color: "#1a1b26"
    visible: true
    Rectangle {
      id: bg
      anchors.fill: parent
      color: "#1a1b26"
      PanelContent {
        id: pc
        x: 14; y: 14
        width: 392
        rows: shell.rows
        summary: "5 instancji: 2 działa, 1 stop, 2 brak gry"
        foreground: "#c0caf5"
        urgent: "#f7768e"
        previewColor: "#7aa2f7"
        fontFamily: "JetBrains Mono"
      }
    }
    Timer {
      interval: 1500; running: true
      onTriggered: {
        var res = []
        function find(item, name, acc) {
          if (!item) return
          if (item.objectName === name) acc.push(item)
          var kids = item.children || []
          for (var i = 0; i < kids.length; i++) find(kids[i], name, acc)
        }
        var areas = []; find(pc, "nick-podglad", areas)
        var marks = []; find(pc, "znacznik-podgladu", marks)
        console.log("scenariusz nick-areas " + areas.length + " widoczne-znaczniki " + marks.map(function (m) { return m.visible }).join(","))
        console.log("scenariusz enabled " + areas.map(function (a) { return a.enabled }).join(",") + " cursor " + areas.map(function (a) { return a.cursorShape }).join(","))
        // klik w kolejne nicki (sygnał clicked); główna (enabled=false) i brak gry nie mogą wywołać run
        for (var i = 0; i < areas.length; i++) if (areas[i].enabled) areas[i].clicked(null)
        bg.grabToImage(function (r) { console.log("scenariusz zrzut " + r.saveToFile(shell.out + "/pasek-popup.png")); Qt.quit() }, Qt.size(840, 1400))
      }
    }
  }
}
