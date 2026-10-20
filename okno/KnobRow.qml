pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Layouts
import "UstawieniaModel.js" as Ust

// Wiersz pokrętła (makieta wariant A): nazwa techniczna (Q2) + opis z komentarza pokretla.py po lewej, kontrolka po prawej:
// suwak + pole liczby (liczby), przełącznik (0/1), przyciski wyboru (pokrętła tekstowe z dozwolonych wartości) albo sam odczyt
// (klucz spoza listy pokręteł). Każda zmiana zapisuje się od razu (ctl.setKnob -> okno_api ustaw). Wartość różna od domyślnej jest
// wyróżniona, a gdy tryb z ostatniego startu nadpisze to pokrętło, pod opisem stoi ostrzeżenie.
Rectangle {
  id: row

  required property var p
  required property var ctl
  property var conflict: null            // wynik Ust.conflictFor: {tryb, wartosc} albo null
  property bool flash: false             // mignięcie po przejściu z Ctrl+K
  property bool showGroup: false         // przy wyszukiwaniu po wszystkich grupach: podpis grupy

  readonly property string kind: Ust.controlKind(p)
  readonly property bool changed: Ust.isChanged(p)
  readonly property bool hasDefault: !p.readonly && p.domyslna !== null && p.domyslna !== undefined

  implicitHeight: Math.max(textCol.implicitHeight, controlCol.implicitHeight) + 24
  color: flash ? Theme.alpha(Theme.blue, 0.14) : "transparent"
  Behavior on color { ColorAnimation { duration: 250 } }

  Rectangle {
    anchors.left: parent.left
    anchors.right: parent.right
    anchors.bottom: parent.bottom
    height: 1
    color: Theme.line
  }

  RowLayout {
    anchors.left: parent.left
    anchors.right: parent.right
    anchors.top: parent.top
    anchors.leftMargin: 22
    anchors.rightMargin: 22
    anchors.topMargin: 12
    spacing: 18

    Column {
      id: textCol
      Layout.fillWidth: true
      Layout.alignment: Qt.AlignTop
      spacing: 4

      Row {
        spacing: 8
        Text {
          objectName: "nazwa-" + row.p.klucz
          text: row.p.klucz
          color: row.changed ? Theme.warn : Theme.fg
          font.family: Theme.font
          font.pixelSize: Theme.body
          font.bold: true
        }
        Chip {
          visible: row.showGroup
          small: true
          label: row.p.grupaUI
        }
        Chip {
          visible: row.changed
          small: true
          label: "domyślna " + Ust.valueLabel(row.p, row.p.domyslna)
          textColor: Theme.dim
        }
      }
      Text {
        width: parent.width
        text: row.p.opis
        visible: text !== ""
        color: Theme.dim
        font.family: Theme.font
        font.pixelSize: Theme.small
        wrapMode: Text.Wrap
      }
      Text {
        objectName: "ostrzezenie-" + row.p.klucz
        width: parent.width
        visible: row.conflict !== null
        text: row.conflict !== null ? "⚠ " + Ust.conflictText(row.conflict, row.p) : ""
        color: Theme.warn
        font.family: Theme.font
        font.pixelSize: Theme.small
        wrapMode: Text.Wrap
      }
    }

    Column {
      id: controlCol
      Layout.preferredWidth: 300
      Layout.maximumWidth: 300
      Layout.alignment: Qt.AlignTop
      spacing: 6

      // ---- przełącznik 0/1
      Item {
        visible: row.kind === "przelacznik"
        width: 300
        height: 24
        Row {
          anchors.right: parent.right
          anchors.verticalCenter: parent.verticalCenter
          spacing: 10
          Text {
            anchors.verticalCenter: parent.verticalCenter
            text: Ust.valueLabel(row.p)
            color: Number(row.p.biezaca) === 1 ? Theme.ok : Theme.dim
            font.family: Theme.font
            font.pixelSize: Theme.small
          }
          Przelacznik {
            objectName: "przelacznik-" + row.p.klucz
            anchors.verticalCenter: parent.verticalCenter
            on: Number(row.p.biezaca) === 1
            onToggled: function(value) { row.ctl.setKnob(row.p.klucz, value ? 1 : 0) }
          }
        }
      }

      // ---- suwak + pole liczby
      Row {
        visible: row.kind === "suwak"
        spacing: 12
        height: 26
        Suwak {
          id: slider
          objectName: "suwak-" + row.p.klucz
          anchors.verticalCenter: parent.verticalCenter
          width: 212
          knob: row.p
          value: Number(row.p.biezaca)
          onCommitted: function(v) { row.ctl.setKnob(row.p.klucz, v) }
        }
        Rectangle {
          id: field
          objectName: "pole-" + row.p.klucz
          width: 76
          height: 26
          radius: 6
          color: Theme.bg2
          property bool error: false
          readonly property string shownText: Ust.valueLabel(row.p, slider.shown)
          border.width: 1
          border.color: error ? Theme.bad : (input.activeFocus ? Theme.blue : (row.changed ? Theme.warn : Theme.line2))

          function rebind() { input.text = Qt.binding(function() { return field.shownText }) }

          // Enter albo utrata fokusu: liczba w zakresie -> zapis; błędna wartość wraca do bieżącej z komunikatem.
          function commit(t) {
            var r = Ust.parseInput(row.p, t)
            if (!r.ok) {
              error = true
              row.ctl.setKnobNote(row.p.klucz + ": " + r.blad, "bad")
            } else {
              error = false
              if (!Ust.sameValue(r.value, row.p.biezaca)) row.ctl.setKnob(row.p.klucz, r.value)
            }
            rebind()
          }

          TextInput {
            id: input
            anchors.fill: parent
            anchors.leftMargin: 8
            anchors.rightMargin: 8
            verticalAlignment: TextInput.AlignVCenter
            horizontalAlignment: TextInput.AlignRight
            text: field.shownText
            color: row.changed ? Theme.warn : Theme.fg
            font.family: Theme.font
            font.pixelSize: Theme.body
            font.bold: true
            selectByMouse: true
            clip: true
            onEditingFinished: field.commit(text)
            onTextEdited: field.error = false
          }
        }
      }

      // ---- wybór z dozwolonych wartości (pokrętła tekstowe)
      Flow {
        visible: row.kind === "wybor"
        width: 300
        spacing: 6
        Repeater {
          model: row.p.opcje ? row.p.opcje : []
          delegate: Rectangle {
            id: pill
            required property var modelData
            readonly property bool on: modelData === row.p.biezaca
            readonly property string tag: Ust.optionLabel(row.p.klucz, modelData)
            objectName: "opcja-" + row.p.klucz + "-" + modelData
            height: 26
            width: pillText.implicitWidth + 22
            radius: 6
            color: on ? Theme.alpha(Theme.blue, 0.18) : (pillMouse.containsMouse ? Theme.sur2 : "transparent")
            border.width: 1
            border.color: on ? Theme.blue : (pillMouse.containsMouse ? Theme.dim : Theme.line2)
            function tryClick() { if (!on) row.ctl.setKnob(row.p.klucz, modelData) }
            Text {
              id: pillText
              anchors.centerIn: parent
              text: pill.modelData + (pill.tag !== "" ? " · " + pill.tag : "")
              color: pill.on ? Theme.fg : Theme.fg2
              font.family: Theme.font
              font.pixelSize: Theme.small
              font.bold: pill.on
            }
            MouseArea {
              id: pillMouse
              anchors.fill: parent
              hoverEnabled: true
              cursorShape: Qt.PointingHandCursor
              onClicked: pill.tryClick()
            }
          }
        }
      }

      // ---- tylko odczyt (klucz spoza listy)
      Item {
        visible: row.kind === "odczyt"
        width: 300
        height: 24
        Row {
          anchors.right: parent.right
          anchors.verticalCenter: parent.verticalCenter
          spacing: 8
          Text {
            text: Ust.valueLabel(row.p)
            color: Theme.fg2
            font.family: Theme.font
            font.pixelSize: Theme.body
            font.bold: true
          }
          Chip { small: true; label: "tylko odczyt" }
        }
      }

      // ---- powrót do domyślnej
      Item {
        id: resetLink
        objectName: "domyslna-" + row.p.klucz
        visible: row.changed && row.hasDefault && row.kind !== "odczyt"
        width: 300
        height: 16
        function tryClick() { if (row.hasDefault) row.ctl.setKnob(row.p.klucz, row.p.domyslna) }
        Text {
          anchors.right: parent.right
          text: "wróć do domyślnej " + Ust.valueLabel(row.p, row.p.domyslna)
          color: resetMouse.containsMouse ? Theme.blue : Theme.dim
          font.family: Theme.font
          font.pixelSize: Theme.tiny
          font.underline: resetMouse.containsMouse
        }
        MouseArea {
          id: resetMouse
          anchors.fill: parent
          hoverEnabled: true
          cursorShape: Qt.PointingHandCursor
          onClicked: resetLink.tryClick()
        }
      }
    }
  }
}
