pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "OknoModel.js" as Model

// Sekcja Ratunek (tylko odczyt + etykieta "fałszywy alarm"): liczniki, lista sygnałów z logi/ratunek-*.jsonl wybranej postaci
// i szczegóły wybranego. Dane z `okno_api ratunek`; zapis tylko `ratunek-oznacz` (dopisanie etykiety, pliki sygnałów nietknięte).
Item {
  id: view

  required property var ctl

  property string period: "dzis"        // dzis | 7dni (okno API to 7 dni)
  property string code: ""              // "" = wszystkie kody
  property string pickedId: ""

  readonly property var payload: ctl.ratunekData
  readonly property var all: payload && payload.sygnaly ? payload.sygnaly : []
  readonly property var now: ctl.refreshedAt || new Date()
  readonly property var shown: Model.filterSignals(all, period, code, now)
  readonly property var counts: Model.counters(payload)
  readonly property var current: {
    for (var i = 0; i < shown.length; i++) if (shown[i].id === pickedId) return shown[i]
    return shown.length ? shown[0] : null
  }
  readonly property string nick: ctl.selected ? Model.nickOf(ctl.selected) : ""
  readonly property bool shadow: all.length === 0 || all[0].tryb === "cien"

  // szerokość kolumny "co": reszta po stałych kolumnach (czas 92, kod 46, gdzie 150), trzech odstępach 12 i lewym marginesie 12
  function whatWidth(total) { return Math.max(60, total - 92 - 46 - 150 - 36 - 12 - 12) }

  // Chip kodów: gdy wybrany kod zniknął z listy, wróć do wszystkich.
  onShownChanged: if (code !== "" && Model.signalCodes(all).indexOf(code) < 0) code = ""

  ColumnLayout {
    anchors.fill: parent
    spacing: 0

    SectionHeader {
      Layout.fillWidth: true
      title: "Ratunek · " + view.nick
      subtitle: view.shadow ? "sygnały „to wygląda na bota” — w cieniu: tylko zapis, bez ruchu" : "sygnały „to wygląda na bota”"
      Chip {
        objectName: "filtr-okres"
        clickable: true
        label: view.period === "dzis" ? "dziś" : "7 dni"
        onActivated: view.period = view.period === "dzis" ? "7dni" : "dzis"
      }
      Chip {
        objectName: "filtr-kod"
        clickable: true
        label: view.code === "" ? "wszystkie kody" : view.code
        onActivated: view.code = Model.nextCode(Model.signalCodes(view.all), view.code)
      }
    }

    Row {
      Layout.fillWidth: true
      Layout.preferredHeight: 62
      leftPadding: 22
      topPadding: 14
      spacing: 28

      StatBlock { label: "dziś"; value: String(view.counts.dzis) }
      StatBlock {
        label: "ostatnia godzina"
        value: String(view.counts.godzina)
        suffix: view.counts.limit !== null ? "/ limit " + view.counts.limit : ""
      }
      StatBlock {
        label: "najczęściej (7 dni)"
        value: view.counts.kodOpis
        valueColor: view.counts.kod !== "" ? Theme.tone(Model.codeTone(view.counts.kod)) : Theme.dim
      }
      StatBlock {
        label: "Haiku"
        value: view.counts.haiku
        valueColor: view.counts.haikuOn ? Theme.ok : Theme.dim
      }
    }
    Rectangle { Layout.fillWidth: true; Layout.preferredHeight: 1; color: Theme.line }

    RowLayout {
      Layout.fillWidth: true
      Layout.fillHeight: true
      spacing: 0

      // ---------- lista sygnałów
      Item {
        Layout.fillWidth: true
        Layout.fillHeight: true

        Rectangle {
          id: listHead
          anchors.left: parent.left
          anchors.right: parent.right
          anchors.top: parent.top
          height: 31
          color: "transparent"
          Row {
            anchors.fill: parent
            anchors.leftMargin: 12
            spacing: 12
            Repeater {
              model: [["czas", 92], ["kod", 46], ["co", -1], ["gdzie", 150]]
              Text {
                required property var modelData
                width: modelData[1] < 0 ? view.whatWidth(parent.width) : modelData[1]
                anchors.verticalCenter: parent.verticalCenter
                text: modelData[0].toUpperCase()
                color: Theme.dim2
                font.family: Theme.font
                font.pixelSize: Theme.tiny
                font.letterSpacing: 1
              }
            }
          }
          Rectangle { anchors.bottom: parent.bottom; width: parent.width; height: 1; color: Theme.line }
        }

        ListView {
          id: list
          objectName: "lista-sygnalow"
          anchors.top: listHead.bottom
          anchors.left: parent.left
          anchors.right: parent.right
          anchors.bottom: parent.bottom
          clip: true
          model: view.shown
          boundsBehavior: Flickable.StopAtBounds
          ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }

          delegate: Rectangle {
            id: row
            required property var modelData
            readonly property bool on: view.current !== null && view.current.id === modelData.id
            width: ListView.view.width
            height: 38
            color: on ? Theme.alpha(Theme.blue, 0.07) : (rowMouse.containsMouse ? Theme.alpha(Theme.sur2, 0.5) : "transparent")
            opacity: modelData.etykieta === "falszywy" ? 0.55 : 1

            Rectangle { visible: row.on; width: 3; height: parent.height; color: Theme.blue }
            Rectangle { anchors.bottom: parent.bottom; width: parent.width; height: 1; color: Theme.line }

            Row {
              anchors.fill: parent
              anchors.leftMargin: 12
              spacing: 12
              Text {
                width: 92
                anchors.verticalCenter: parent.verticalCenter
                text: Model.signalTime(row.modelData.czas, view.now)
                color: Theme.fg
                font.family: Theme.font
                font.pixelSize: Theme.body
              }
              Rectangle {
                width: 46
                height: 20
                anchors.verticalCenter: parent.verticalCenter
                radius: 4
                color: Theme.alpha(Theme.tone(Model.codeTone(row.modelData.kod)), 0.16)
                Text {
                  anchors.centerIn: parent
                  text: row.modelData.kod || "?"
                  color: Theme.tone(Model.codeTone(row.modelData.kod))
                  font.family: Theme.font
                  font.pixelSize: Theme.small
                  font.bold: true
                }
              }
              Text {
                width: view.whatWidth(row.width)
                anchors.verticalCenter: parent.verticalCenter
                text: Model.signalSummary(row.modelData) + (row.modelData.etykieta === "falszywy" ? "  (fałszywy)" : "")
                color: Theme.fg
                font.family: Theme.font
                font.pixelSize: Theme.body
                elide: Text.ElideRight
              }
              Text {
                width: 150
                anchors.verticalCenter: parent.verticalCenter
                text: Model.pozLabel(row.modelData.poz)
                color: Theme.dim
                font.family: Theme.font
                font.pixelSize: Theme.small + 1
                elide: Text.ElideRight
              }
            }

            MouseArea {
              id: rowMouse
              anchors.fill: parent
              hoverEnabled: true
              onClicked: view.pickedId = row.modelData.id
            }
          }

          Text {
            anchors.centerIn: parent
            visible: list.count === 0
            text: view.ctl.ratunekError !== "" ? "błąd odczytu: " + view.ctl.ratunekError
                  : (view.payload === null ? "ładowanie…" : "brak sygnałów w tym oknie czasu")
            color: view.ctl.ratunekError !== "" ? Theme.bad : Theme.dim
            font.family: Theme.font
            font.pixelSize: Theme.body
          }
        }
      }

      Rectangle { Layout.fillHeight: true; Layout.preferredWidth: 1; color: Theme.line }

      // ---------- szczegóły wybranego
      Item {
        Layout.preferredWidth: 359
        Layout.fillHeight: true

        Column {
          visible: view.current !== null
          anchors.fill: parent
          anchors.margins: 18
          anchors.topMargin: 16
          spacing: 12

          Item {
            width: parent.width
            height: 22
            Rectangle {
              id: bigCode
              width: 40
              height: 22
              radius: 4
              color: Theme.alpha(Theme.tone(Model.codeTone(view.current ? view.current.kod : "")), 0.16)
              Text {
                anchors.centerIn: parent
                text: view.current ? (view.current.kod || "?") : ""
                color: Theme.tone(Model.codeTone(view.current ? view.current.kod : ""))
                font.family: Theme.font
                font.pixelSize: Theme.small
                font.bold: true
              }
            }
            Text {
              anchors.left: bigCode.right
              anchors.leftMargin: 12
              anchors.verticalCenter: parent.verticalCenter
              text: view.current ? (view.current.opis || "") : ""
              color: Theme.fg
              font.family: Theme.font
              font.pixelSize: Theme.body
              font.bold: true
            }
            Text {
              anchors.right: parent.right
              anchors.verticalCenter: parent.verticalCenter
              text: view.current ? Model.signalTime(view.current.czas, view.now) : ""
              color: Theme.dim
              font.family: Theme.font
              font.pixelSize: Theme.body
            }
          }

          GridLayout {
            width: parent.width
            columns: 2
            columnSpacing: 10
            rowSpacing: 6

            Repeater {
              model: view.current ? [
                ["stan bota", String(view.current.stan || "?")],
                ["miejsce", Model.pozLabel(view.current.poz)],
                ["liczby", Model.numbersLine(view.current)],
                ["tryb", Model.modeLabel(view.current.tryb)],
                ["w logu", String(view.current.plik || "?") + ":" + String(view.current.linia || "?")],
                ["etykieta", Model.labelText(view.current) || "brak"],
                ["Haiku", Model.haikuLabel(view.current)]
              ] : []
              delegate: Item {
                id: kvRow
                required property var modelData
                required property int index
                Layout.fillWidth: true
                Layout.columnSpan: 2
                implicitHeight: Math.max(k.implicitHeight, v.implicitHeight)
                Text {
                  id: k
                  width: 100
                  text: kvRow.modelData[0]
                  color: Theme.dim
                  font.family: Theme.font
                  font.pixelSize: Theme.small + 1
                }
                Text {
                  id: v
                  anchors.left: k.right
                  anchors.leftMargin: 10
                  anchors.right: parent.right
                  text: kvRow.modelData[1]
                  color: kvRow.modelData[0] === "Haiku" && kvRow.modelData[1] === "Haiku: brak" ? Theme.dim : Theme.fg
                  font.family: Theme.font
                  font.pixelSize: Theme.small + 1
                  wrapMode: Text.Wrap
                }
              }
            }
          }

          Row {
            spacing: 8
            Btn {
              objectName: "falszywy-alarm"
              label: "To fałszywy alarm"
              active: view.current !== null && view.current.etykieta !== "falszywy"
              busy: view.ctl.markJob.pending
              onActivated: view.ctl.markFalse(view.current.id)
            }
            Btn {
              objectName: "pokaz-w-logu"
              label: "Pokaż w logu"
              active: view.current !== null && Model.logPath(view.payload, view.current) !== ""
              onActivated: view.ctl.openLog(Model.logPath(view.payload, view.current))
            }
          }

          Text {
            visible: text !== ""
            width: parent.width
            text: view.ctl.markNote
            color: view.ctl.markNote.indexOf("nie zapisano") === 0 ? Theme.bad : Theme.dim
            font.family: Theme.font
            font.pixelSize: Theme.small
            wrapMode: Text.Wrap
          }
          Text {
            width: parent.width
            text: view.current ? Model.logPath(view.payload, view.current) + ":" + view.current.linia : ""
            color: Theme.dim2
            font.family: Theme.font
            font.pixelSize: Theme.tiny
            wrapMode: Text.WrapAnywhere
          }
        }
      }
    }
  }
}
