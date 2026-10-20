pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Controls
import "OknoModel.js" as Model
import "UstawieniaModel.js" as Ust

// Wyszukiwarka Ctrl+K (makieta wariant C): nakładka nad oknem, szuka po nazwie, opisie i grupie pokręteł wybranej postaci oraz po mapach
// i trybach. Strzałki zmieniają wybór, Enter otwiera pokrętło w Ustawieniach (mapę/tryb: sekcję Mapa i tryb), Esc zamyka.
// Wartości w wynikach są tylko do podglądu; zmiana dzieje się w sekcji Ustawienia.
Item {
  id: pal

  required property var ctl

  property string query: ""
  property int current: 0

  readonly property var toks: Ust.tokens(query)
  readonly property var items: Ust.paletteItems(ctl.knobs, ctl.mapyData)
  readonly property var results: Ust.searchPalette(items, query)
  readonly property string nick: ctl.selected ? Model.nickOf(ctl.selected) : ""

  visible: ctl.paletteOpen
  z: 100

  onVisibleChanged: {
    if (visible) { query = ""; current = 0; input.text = ""; input.forceActiveFocus() }
  }
  onResultsChanged: current = Math.min(current, Math.max(0, results.length - 1))

  function accept() {
    if (current < 0 || current >= results.length) return
    var it = results[current]
    ctl.closePalette()
    if (it.rodzaj === "pokretlo") ctl.openKnob(it.klucz)
    else ctl.setSection("mapa")
  }

  function move(delta) {
    if (!results.length) return
    current = (current + delta + results.length) % results.length
    list.positionViewAtIndex(current, ListView.Contain)
  }

  // tło: kliknięcie poza oknem wyszukiwarki zamyka
  Rectangle {
    anchors.fill: parent
    color: Qt.rgba(0, 0, 0, 0.5)
    MouseArea { anchors.fill: parent; onClicked: pal.ctl.closePalette() }
  }

  Rectangle {
    id: box
    objectName: "paleta"
    anchors.horizontalCenter: parent.horizontalCenter
    anchors.top: parent.top
    anchors.topMargin: 72
    width: Math.min(680, parent.width - 60)
    height: head.height + sep.height + body.height + foot.height
    radius: 10
    color: Theme.sur
    border.width: 1
    border.color: Theme.blue

    MouseArea { anchors.fill: parent }       // klik w okno nie zamyka

    Column {
      anchors.left: parent.left
      anchors.right: parent.right
      anchors.top: parent.top

      Item {
        id: head
        width: parent.width
        height: 48
        Text {
          id: lens
          anchors.left: parent.left
          anchors.leftMargin: 16
          anchors.verticalCenter: parent.verticalCenter
          text: "⌕"
          color: Theme.blue
          font.family: Theme.font
          font.pixelSize: Theme.title
        }
        TextInput {
          id: input
          objectName: "paleta-pole"
          anchors.left: lens.right
          anchors.leftMargin: 10
          anchors.right: hint.left
          anchors.rightMargin: 10
          anchors.verticalCenter: parent.verticalCenter
          color: Theme.fg
          font.family: Theme.font
          font.pixelSize: Theme.body + 1
          selectByMouse: true
          clip: true
          onTextChanged: { pal.query = text; pal.current = 0 }
          Keys.onPressed: function(event) {
            if (event.key === Qt.Key_Down) { pal.move(1); event.accepted = true }
            else if (event.key === Qt.Key_Up) { pal.move(-1); event.accepted = true }
            else if (event.key === Qt.Key_Return || event.key === Qt.Key_Enter) { pal.accept(); event.accepted = true }
            else if (event.key === Qt.Key_Escape) { pal.ctl.closePalette(); event.accepted = true }
          }
          Text {
            anchors.fill: parent
            visible: input.text === ""
            text: "szukaj pokrętła, mapy albo trybu dla " + pal.nick + "…"
            color: Theme.dim2
            font: input.font
            verticalAlignment: Text.AlignVCenter
            elide: Text.ElideRight
          }
        }
        Rectangle {
          id: hint
          anchors.right: parent.right
          anchors.rightMargin: 14
          anchors.verticalCenter: parent.verticalCenter
          width: hintText.implicitWidth + 14
          height: 20
          radius: 4
          color: Theme.bg2
          border.width: 1
          border.color: Theme.line2
          Text {
            id: hintText
            anchors.centerIn: parent
            text: "Esc"
            color: Theme.dim
            font.family: Theme.font
            font.pixelSize: Theme.tiny
          }
        }
      }

      Rectangle { id: sep; width: parent.width; height: 1; color: Theme.line }

      Item {
        id: body
        width: parent.width
        height: Math.min(8, Math.max(1, pal.results.length)) * 54 + 8

        ListView {
          id: list
          objectName: "paleta-wyniki"
          anchors.fill: parent
          anchors.topMargin: 4
          anchors.bottomMargin: 4
          clip: true
          model: pal.results
          boundsBehavior: Flickable.StopAtBounds
          ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }

          delegate: Rectangle {
            id: res
            required property var modelData
            required property int index
            readonly property bool on: index === pal.current
            readonly property var p: modelData.p
            width: list.width
            height: 54
            color: on ? Theme.sur2 : "transparent"

            Rectangle {
              visible: res.on
              anchors.left: parent.left
              anchors.top: parent.top
              anchors.bottom: parent.bottom
              width: 2
              color: Theme.blue
            }

            Column {
              anchors.left: parent.left
              anchors.leftMargin: 16
              anchors.right: valueBox.left
              anchors.rightMargin: 12
              anchors.verticalCenter: parent.verticalCenter
              spacing: 4
              Text {
                width: parent.width
                textFormat: Text.StyledText
                text: Ust.highlight(res.modelData.tytul, pal.toks, Theme.warn.toString())
                color: Theme.fg
                font.family: Theme.font
                font.pixelSize: Theme.body
                font.bold: true
                elide: Text.ElideRight
              }
              Text {
                width: parent.width
                textFormat: Text.StyledText
                text: res.modelData.grupa + (res.modelData.rodzaj === "pokretlo" ? " · " + pal.nick : "") + (res.modelData.opis !== "" ? " · " : "")
                      + Ust.highlight(res.modelData.opis, pal.toks, Theme.warn.toString())
                color: Theme.dim
                font.family: Theme.font
                font.pixelSize: Theme.small
                elide: Text.ElideRight
              }
            }

            Rectangle {
              id: valueBox
              anchors.right: parent.right
              anchors.rightMargin: 16
              anchors.verticalCenter: parent.verticalCenter
              width: Math.min(210, valueText.implicitWidth + 20)
              height: 26
              radius: 6
              color: Theme.bg2
              border.width: 1
              border.color: res.p && Ust.isChanged(res.p) ? Theme.warn : Theme.line2
              Text {
                id: valueText
                anchors.centerIn: parent
                width: parent.width - 12
                horizontalAlignment: Text.AlignHCenter
                text: res.p ? Ust.valueLabel(res.p) + (Ust.optionLabel(res.p.klucz, res.p.biezaca) !== "" ? " · " + Ust.optionLabel(res.p.klucz, res.p.biezaca) : "")
                            : (res.modelData.rodzaj === "mapa" ? "mapa" : "tryb")
                color: res.p && Ust.isChanged(res.p) ? Theme.warn : Theme.fg2
                font.family: Theme.font
                font.pixelSize: Theme.small
                font.bold: true
                elide: Text.ElideRight
              }
            }

            MouseArea {
              anchors.fill: parent
              hoverEnabled: true
              onEntered: pal.current = res.index
              onClicked: { pal.current = res.index; pal.accept() }
            }
          }

          Text {
            anchors.centerIn: parent
            visible: pal.results.length === 0
            text: pal.ctl.knobs.length === 0 ? "ładowanie pokręteł…" : "nic nie pasuje do „" + pal.query + "”"
            color: Theme.dim
            font.family: Theme.font
            font.pixelSize: Theme.body
          }
        }
      }

      Rectangle {
        id: foot
        width: parent.width
        height: 30
        color: Theme.bg2
        radius: 10
        Rectangle { anchors.top: parent.top; width: parent.width; height: 10; color: parent.color }
        Rectangle { anchors.top: parent.top; width: parent.width; height: 1; color: Theme.line }
        Text {
          anchors.left: parent.left
          anchors.leftMargin: 16
          anchors.verticalCenter: parent.verticalCenter
          text: pal.query === "" ? "podpowiedź: pokrętła run (UH) · ↑↓ wybór · Enter otwiera w Ustawieniach · Esc zamyka"
                                 : pal.results.length + " wyników · ↑↓ wybór · Enter otwiera w Ustawieniach · Esc zamyka"
          color: Theme.dim
          font.family: Theme.font
          font.pixelSize: Theme.tiny
        }
      }
    }
  }
}
