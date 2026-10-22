import QtQuick

// Blok „Ostatnio znane” na górze Sesji gry (spec 2026-10-22-retronic-przeglad.md, makieta 1-karty-offline): pokazywany tylko, gdy gry nie ma.
// Dane z `ostatnie` (okno_api stan) przez PrzegladModel.lastKnown: statystyki (LEVEL, MAGIC LEVEL, HP/MANA max, EXP, GOLD z sesji), trzy kolumny
// (gdzie stoi · ostatnia sesja · alarm i nadzór) i stopka ze źródłem. Brak pliku `ostatnie` (null) = pusty blok z objaśnieniem, bez wyjątku.
Rectangle {
  id: block

  property var info: ({ empty: true, title: "", sub: "", online: "", ago: "", stats: [], cols: [], source: "" })

  implicitHeight: content.implicitHeight
  radius: 10
  color: Theme.sur
  border.width: 1
  border.color: Theme.line

  Column {
    id: content
    width: block.width

    // nagłówek: tytuł + opis po lewej, „ostatnio online …” po prawej
    Item {
      width: block.width
      height: 29
      Row {
        anchors.left: parent.left
        anchors.leftMargin: 14
        anchors.verticalCenter: parent.verticalCenter
        spacing: 8
        Text { text: block.info.title; color: Theme.dim; font.family: Theme.font; font.pixelSize: Theme.tiny; font.letterSpacing: 1 }
        Text { text: block.info.sub; color: Theme.dim; font.family: Theme.font; font.pixelSize: Theme.small }
      }
      Row {
        visible: block.info.online !== ""
        anchors.right: parent.right
        anchors.rightMargin: 14
        anchors.verticalCenter: parent.verticalCenter
        spacing: 6
        Text { text: "ostatnio online"; color: Theme.dim; font.family: Theme.font; font.pixelSize: Theme.small }
        Text { objectName: "ostatnio-online"; text: block.info.online; color: Theme.fg; font.family: Theme.font; font.pixelSize: Theme.small; font.bold: true }
        Text { text: block.info.ago; color: Theme.dim; font.family: Theme.font; font.pixelSize: Theme.small }
      }
      Rectangle { anchors.left: parent.left; anchors.right: parent.right; anchors.bottom: parent.bottom; height: 1; color: Theme.line }
    }

    // statystyki
    Item {
      visible: !block.info.empty
      width: block.width
      height: block.info.empty ? 0 : statRow.implicitHeight + 28
      Flow {
        id: statRow
        anchors.left: parent.left
        anchors.leftMargin: 14
        anchors.right: parent.right
        anchors.rightMargin: 14
        anchors.verticalCenter: parent.verticalCenter
        spacing: 34
        Repeater {
          model: block.info.stats
          delegate: StatBlock {
            required property var modelData
            objectName: "ostatnio-" + modelData.key
            label: modelData.label
            value: modelData.value
            suffix: modelData.small
            valueColor: modelData.dim ? Theme.dim2 : Theme.fg
          }
        }
      }
      Rectangle { anchors.left: parent.left; anchors.right: parent.right; anchors.bottom: parent.bottom; height: 1; color: Theme.line }
    }

    // trzy kolumny
    Row {
      visible: !block.info.empty
      width: block.width
      Repeater {
        model: block.info.cols
        delegate: Item {
          id: colItem
          required property var modelData
          required property int index
          width: block.width / 3
          height: colColumn.implicitHeight + 28
          Rectangle { visible: colItem.index > 0; anchors.left: parent.left; anchors.top: parent.top; anchors.bottom: parent.bottom; width: 1; color: Theme.line }
          Column {
            id: colColumn
            x: 14
            y: 14
            width: colItem.width - 28
            spacing: 5
            Text { text: colItem.modelData.title; color: Theme.dim; font.family: Theme.font; font.pixelSize: Theme.tiny; font.letterSpacing: 1; bottomPadding: 4 }
            Repeater {
              model: colItem.modelData.rows
              delegate: Item {
                id: kvItem
                required property var modelData
                width: colColumn.width
                implicitHeight: Math.max(kvKey.implicitHeight, kvVal.implicitHeight)
                height: implicitHeight
                Text { id: kvKey; width: 104; text: kvItem.modelData.k; color: Theme.dim; font.family: Theme.font; font.pixelSize: Theme.small + 1 }
                Text {
                  id: kvVal
                  anchors.left: kvKey.right
                  anchors.right: parent.right
                  text: kvItem.modelData.v
                  color: Theme.tone(kvItem.modelData.tone)
                  font.family: Theme.font
                  font.pixelSize: Theme.small + 1
                  wrapMode: Text.Wrap
                }
              }
            }
          }
        }
      }
    }

    // stopka: źródło danych
    Item {
      visible: !block.info.empty
      width: block.width
      height: block.info.empty ? 0 : srcText.implicitHeight + 16
      Rectangle { anchors.left: parent.left; anchors.right: parent.right; anchors.top: parent.top; height: 1; color: Theme.line }
      Text {
        id: srcText
        objectName: "ostatnio-zrodlo"
        anchors.left: parent.left
        anchors.leftMargin: 14
        anchors.right: parent.right
        anchors.rightMargin: 14
        anchors.verticalCenter: parent.verticalCenter
        text: block.info.source
        color: Theme.dim2
        font.family: Theme.font
        font.pixelSize: Theme.tiny
        elide: Text.ElideRight
      }
    }
  }
}
