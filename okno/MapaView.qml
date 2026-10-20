pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "OknoModel.js" as Model

// Sekcja Mapa i tryb: mapy z opisem (jedna), tryby (wiele naraz), ostatnio użyte i "Start z tym" (uruchom.sh z MAPA/TRYB
// i RETRONIC_ID wybranej postaci). Zmiana działa przy następnym starcie: działającego bota okno nie rusza, a przycisk Start jest
// wtedy szary. Start wymaga potwierdzenia.
Item {
  id: view

  required property var ctl

  property bool confirming: false

  readonly property var payload: ctl.mapyData
  readonly property var maps: payload && payload.mapy ? payload.mapy : []
  readonly property var modes: payload && payload.tryby ? payload.tryby : []
  readonly property var last: payload && payload.ostatni ? payload.ostatni : null
  readonly property var choice: ctl.choiceOf(ctl.selectedId)
  readonly property var startState: Model.startState(ctl.selectedStatus, choice.mapa)
  readonly property string nick: ctl.selected ? Model.nickOf(ctl.selected) : ""
  readonly property string message: ctl.selected ? (ctl.messages[ctl.selected.id] || "") : ""
  readonly property bool sameAsLast: Model.isLastChoice(last, choice.mapa, choice.tryby)

  // Zmiana postaci, wyboru albo stanu bota unieważnia otwarte potwierdzenie.
  onChoiceChanged: confirming = false
  onStartStateChanged: if (!startState.enabled) confirming = false
  Connections {
    target: view.ctl
    function onSelectedIdChanged() { view.confirming = false }
  }

  ColumnLayout {
    anchors.fill: parent
    spacing: 0

    SectionHeader {
      Layout.fillWidth: true
      title: "Mapa i tryb · " + view.nick
      subtitle: "wybór na następny start; zmiana działa przy następnym starcie"
      Chip {
        visible: view.last !== null
        label: view.last && (view.last.mapa || (view.last.tryb && view.last.tryb.length))
               ? "ostatnio: " + (view.last.mapa || "?") + " · " + (view.last.tryb && view.last.tryb.length ? view.last.tryb.join(", ") : "bez trybu")
               : "ostatnio: brak"
      }
      Btn {
        objectName: "uzyj-ostatnich"
        label: "Użyj ostatnich"
        active: view.last !== null && !!view.last.mapa && !view.sameAsLast
        onActivated: view.ctl.useLast()
      }
    }

    RowLayout {
      Layout.fillWidth: true
      Layout.fillHeight: true
      spacing: 0

      // ---------- mapy
      ColumnLayout {
        Layout.fillWidth: true
        Layout.preferredWidth: 560
        Layout.minimumWidth: 0
        Layout.fillHeight: true
        spacing: 0

        Text {
          Layout.leftMargin: 22
          Layout.topMargin: 12
          Layout.bottomMargin: 8
          text: "MAPY (" + view.maps.length + ") · jedna"
          color: Theme.dim
          font.family: Theme.font
          font.pixelSize: Theme.tiny
          font.letterSpacing: 1
        }

        ListView {
          id: mapList
          objectName: "lista-map"
          Layout.fillWidth: true
          Layout.fillHeight: true
          clip: true
          model: view.maps
          spacing: 6
          leftMargin: 22
          rightMargin: 22
          bottomMargin: 10
          boundsBehavior: Flickable.StopAtBounds
          ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }

          delegate: Rectangle {
            id: mrow
            required property var modelData
            readonly property bool on: view.choice.mapa === modelData.nazwa
            width: mapList.width - 44
            height: mcol.implicitHeight + 20
            radius: 8
            color: on ? Theme.alpha(Theme.blue, 0.08) : (mmouse.containsMouse ? Theme.alpha(Theme.sur2, 0.5) : Theme.sur)
            border.width: 1
            border.color: on ? Theme.blue : Theme.line

            Rectangle {
              id: radio
              anchors.left: parent.left
              anchors.leftMargin: 12
              anchors.top: parent.top
              anchors.topMargin: 12
              width: 14
              height: 14
              radius: 7
              color: "transparent"
              border.width: 2
              border.color: mrow.on ? Theme.blue : Theme.line2
              Rectangle {
                visible: mrow.on
                anchors.centerIn: parent
                width: 6
                height: 6
                radius: 3
                color: Theme.blue
              }
            }
            Column {
              id: mcol
              anchors.left: radio.right
              anchors.leftMargin: 10
              anchors.right: parent.right
              anchors.rightMargin: 12
              anchors.top: parent.top
              anchors.topMargin: 10
              spacing: 3
              Row {
                spacing: 8
                Text {
                  text: mrow.modelData.nazwa
                  color: Theme.fg
                  font.family: Theme.font
                  font.pixelSize: Theme.body
                  font.bold: true
                }
                Chip {
                  visible: view.last !== null && view.last.mapa === mrow.modelData.nazwa
                  small: true
                  label: "ostatnio"
                  textColor: Theme.cyan
                }
              }
              Text {
                width: parent.width
                text: mrow.modelData.opis
                color: Theme.dim
                font.family: Theme.font
                font.pixelSize: Theme.small
                wrapMode: Text.Wrap
                maximumLineCount: 2
                elide: Text.ElideRight
              }
            }
            MouseArea {
              id: mmouse
              anchors.fill: parent
              hoverEnabled: true
              cursorShape: Qt.PointingHandCursor
              onClicked: view.ctl.chooseMap(mrow.modelData.nazwa)
            }
          }

          Text {
            anchors.centerIn: parent
            visible: mapList.count === 0
            text: view.ctl.mapyError !== "" ? "błąd odczytu: " + view.ctl.mapyError
                  : (view.payload === null ? "ładowanie…" : "brak map w mapy.json")
            color: view.ctl.mapyError !== "" ? Theme.bad : Theme.dim
            font.family: Theme.font
            font.pixelSize: Theme.body
          }
        }
      }

      Rectangle { Layout.fillHeight: true; Layout.preferredWidth: 1; color: Theme.line }

      // ---------- tryby
      ColumnLayout {
        Layout.preferredWidth: 420
        Layout.maximumWidth: 420
        Layout.minimumWidth: 0
        Layout.fillHeight: true
        spacing: 0

        Text {
          Layout.leftMargin: 18
          Layout.topMargin: 12
          Layout.bottomMargin: 8
          text: "TRYBY (" + view.modes.length + ") · wiele naraz"
          color: Theme.dim
          font.family: Theme.font
          font.pixelSize: Theme.tiny
          font.letterSpacing: 1
        }

        ListView {
          id: modeList
          objectName: "lista-trybow"
          Layout.fillWidth: true
          Layout.fillHeight: true
          clip: true
          model: view.modes
          spacing: 6
          leftMargin: 18
          rightMargin: 22
          bottomMargin: 10
          boundsBehavior: Flickable.StopAtBounds
          ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }

          delegate: Rectangle {
            id: trow
            required property var modelData
            readonly property bool on: view.choice.tryby.indexOf(modelData.nazwa) >= 0
            width: modeList.width - 40
            height: tcol.implicitHeight + 20
            radius: 8
            color: on ? Theme.alpha(Theme.blue, 0.08) : (tmouse.containsMouse ? Theme.alpha(Theme.sur2, 0.5) : Theme.sur)
            border.width: 1
            border.color: on ? Theme.blue : Theme.line

            Rectangle {
              id: box
              anchors.left: parent.left
              anchors.leftMargin: 12
              anchors.top: parent.top
              anchors.topMargin: 12
              width: 14
              height: 14
              radius: 3
              color: trow.on ? Theme.blue : "transparent"
              border.width: 2
              border.color: trow.on ? Theme.blue : Theme.line2
              Text {
                visible: trow.on
                anchors.centerIn: parent
                text: "✓"
                color: Theme.bg
                font.family: Theme.font
                font.pixelSize: 10
                font.bold: true
              }
            }
            Column {
              id: tcol
              anchors.left: box.right
              anchors.leftMargin: 10
              anchors.right: parent.right
              anchors.rightMargin: 12
              anchors.top: parent.top
              anchors.topMargin: 10
              spacing: 3
              Row {
                spacing: 8
                Text {
                  text: trow.modelData.nazwa
                  color: Theme.fg
                  font.family: Theme.font
                  font.pixelSize: Theme.body
                  font.bold: true
                }
                Chip {
                  small: true
                  label: trow.modelData.ile_pokretel + " pokręteł"
                }
                Chip {
                  visible: view.last !== null && view.last.tryb && view.last.tryb.indexOf(trow.modelData.nazwa) >= 0
                  small: true
                  label: "ostatnio"
                  textColor: Theme.cyan
                }
              }
              Text {
                width: parent.width
                text: trow.modelData.opis
                color: Theme.dim
                font.family: Theme.font
                font.pixelSize: Theme.small
                wrapMode: Text.Wrap
                maximumLineCount: 3
                elide: Text.ElideRight
              }
            }
            MouseArea {
              id: tmouse
              anchors.fill: parent
              hoverEnabled: true
              cursorShape: Qt.PointingHandCursor
              onClicked: view.ctl.toggleMode(trow.modelData.nazwa)
            }
          }
        }
      }
    }

    // ---------- pasek startu
    Rectangle {
      Layout.fillWidth: true
      Layout.preferredHeight: 72
      color: Theme.bg2

      Rectangle { anchors.top: parent.top; width: parent.width; height: 1; color: Theme.line }

      Column {
        anchors.left: parent.left
        anchors.leftMargin: 22
        anchors.right: actions.left
        anchors.rightMargin: 16
        anchors.verticalCenter: parent.verticalCenter
        spacing: 4

        Text {
          objectName: "wybor-tekst"
          width: parent.width
          text: view.confirming
                ? "Uruchomić " + view.nick + ": " + Model.chosenText(view.choice.mapa, view.choice.tryby) + "?"
                : "Wybrane: " + Model.chosenText(view.choice.mapa, view.choice.tryby)
          color: Theme.fg
          font.family: Theme.font
          font.pixelSize: Theme.body
          font.bold: true
          elide: Text.ElideRight
        }
        Text {
          objectName: "wybor-uwaga"
          width: parent.width
          text: view.message !== "" ? view.message
                : (view.ctl.startNote !== "" ? view.ctl.startNote
                   : (!view.startState.enabled ? view.startState.reason + " · zmiana działa przy następnym starcie"
                      : "zmiana działa przy następnym starcie; uruchom.sh zapisze ten wybór jako ostatni"))
          color: view.message !== "" ? Theme.bad : (view.ctl.startNote !== "" ? Theme.ok : Theme.dim)
          font.family: Theme.font
          font.pixelSize: Theme.small
          elide: Text.ElideRight
        }
      }

      Row {
        id: actions
        anchors.right: parent.right
        anchors.rightMargin: 22
        anchors.verticalCenter: parent.verticalCenter
        spacing: 8

        Btn {
          objectName: "start-z-tym"
          visible: !view.confirming
          label: "▶ Start z tym"
          tone: "ok"
          active: view.startState.enabled
          busy: view.ctl.isBusy(view.ctl.selectedId)
          onActivated: view.confirming = true
        }
        Btn {
          objectName: "start-potwierdz"
          visible: view.confirming
          label: "Tak, uruchom"
          tone: "ok"
          active: view.startState.enabled
          busy: view.ctl.isBusy(view.ctl.selectedId)
          onActivated: { view.confirming = false; view.ctl.startWithChoice() }
        }
        Btn {
          objectName: "start-anuluj"
          visible: view.confirming
          label: "Anuluj"
          onActivated: view.confirming = false
        }
      }
    }
  }
}
