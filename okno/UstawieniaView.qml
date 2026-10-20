pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "OknoModel.js" as Model
import "UstawieniaModel.js" as Ust

// Sekcja Ustawienia (faza F3): grupy pokręteł wybranej postaci (lista z licznikiem + wyszukiwarka), w grupie wiersz = nazwa techniczna,
// opis z komentarza pokretla.py i kontrolka. Zapis do na_zywo.json instancji idzie OD RAZU (Q3) przez okno_api ustaw (walidacja pokretla.py,
// kopia .bak, dziennik), bot czyta plik na żywo. Pod listą: wynik ostatniej zmiany i "Cofnij ostatnią". Grupa "Runy (UH)" jest pierwsza
// i ma zestawy run z trybów (np. HMM = adori gran). Gdy tryb z ostatniego startu nadpisze pokrętło przy następnym starcie, widać ostrzeżenie.
Item {
  id: view

  required property var ctl

  property bool flashOn: false

  readonly property var knobs: ctl.knobs
  readonly property var byKey: ctl.knobsByKey
  readonly property var payload: ctl.pokretlaData
  readonly property var groups: Ust.buildGroups(payload, knobs)
  readonly property var shown: Ust.filterKnobs(knobs, { grupa: ctl.settingsGroup, tekst: ctl.settingsText, tylkoZmienione: ctl.settingsOnlyChanged })
  readonly property string nick: ctl.selected ? Model.nickOf(ctl.selected) : ""
  readonly property bool botRuns: ctl.selectedStatus && ctl.selectedStatus.ok ? ctl.selectedStatus.running : false

  // tryb z ostatniego startu (ostatni_start*.env) i jego pokrętła: co nadpisze przy następnym starcie
  readonly property var mapy: ctl.mapyData
  readonly property var lastModes: mapy && mapy.ostatni && mapy.ostatni.tryb ? mapy.ostatni.tryb : []
  readonly property var conflicts: Ust.modeConflicts(Ust.modeSettings(mapy && mapy.tryby ? mapy.tryby : [], lastModes), byKey)
  readonly property string conflictLine: Ust.conflictSummary(conflicts, lastModes)
  readonly property var presets: Ust.runePresets(mapy && mapy.tryby ? mapy.tryby : [], byKey)
  readonly property bool showPresets: presets.length > 0 && ctl.settingsText === "" && ctl.settingsGroup === Ust.PINNED_GROUP && !ctl.settingsOnlyChanged
  readonly property string fileError: payload && payload.blad_pliku ? String(payload.blad_pliku) : ""
  readonly property var undoText: Ust.undoLabel(payload ? payload.ostatnia_zmiana : null, byKey)

  function reveal() {
    var i = Ust.indexOfKey(shown, ctl.focusKey)
    if (i < 0) return
    list.positionViewAtIndex(i, ListView.Center)
    flashOn = true
    flashTimer.restart()
  }

  // Zmiana grupy, filtra albo pojawienie się zestawów run (nagłówek listy) zaczyna listę od góry; zwykły zapis jej nie rusza.
  function toTop() { topTimer.restart() }
  onShowPresetsChanged: if (showPresets) toTop()

  Connections {
    target: view.ctl
    function onFocusSerialChanged() { revealTimer.restart() }
    function onSettingsGroupChanged() { view.toTop() }
    function onSettingsTextChanged() { view.toTop() }
    function onSettingsOnlyChangedChanged() { view.toTop() }
  }
  Timer { id: topTimer; interval: 120; onTriggered: list.positionViewAtBeginning() }
  Timer { id: revealTimer; interval: 90; onTriggered: view.reveal() }
  Timer { id: flashTimer; interval: 2200; onTriggered: view.flashOn = false }

  ColumnLayout {
    anchors.fill: parent
    spacing: 0

    SectionHeader {
      Layout.fillWidth: true
      title: "Ustawienia · " + view.nick
      subtitle: view.botRuns ? "zmiana działa w locie: bot czyta na_zywo.json, bez restartu"
                             : "bot stoi: wartość zapisze się w na_zywo.json i zadziała po starcie bota"
      Chip {
        objectName: "chip-w-locie"
        label: view.botRuns ? "● w locie" : "○ bot stoi"
        textColor: view.botRuns ? Theme.ok : Theme.dim
      }
      Chip {
        objectName: "filtr-zmienione"
        clickable: true
        on: view.ctl.settingsOnlyChanged
        label: "tylko zmienione"
        textColor: view.ctl.settingsOnlyChanged ? Theme.blue : Theme.fg2
        onActivated: view.ctl.settingsOnlyChanged = !view.ctl.settingsOnlyChanged
      }
    }

    RowLayout {
      Layout.fillWidth: true
      Layout.fillHeight: true
      spacing: 0

      // ---------- grupy + wyszukiwarka
      ColumnLayout {
        Layout.preferredWidth: Math.max(196, Math.min(230, view.width * 0.26))
        Layout.maximumWidth: 230
        Layout.fillHeight: true
        spacing: 0

        Rectangle {
          Layout.fillWidth: true
          Layout.leftMargin: 14
          Layout.rightMargin: 14
          Layout.topMargin: 12
          Layout.bottomMargin: 8
          Layout.preferredHeight: 30
          radius: 6
          color: Theme.bg2
          border.width: 1
          border.color: search.activeFocus ? Theme.blue : Theme.line2
          Text {
            id: lens
            anchors.left: parent.left
            anchors.leftMargin: 9
            anchors.verticalCenter: parent.verticalCenter
            text: "⌕"
            color: Theme.dim
            font.family: Theme.font
            font.pixelSize: Theme.body
          }
          TextInput {
            id: search
            objectName: "ustawienia-szukaj"
            anchors.left: lens.right
            anchors.leftMargin: 6
            anchors.right: parent.right
            anchors.rightMargin: 8
            anchors.verticalCenter: parent.verticalCenter
            text: view.ctl.settingsText
            color: Theme.fg
            font.family: Theme.font
            font.pixelSize: Theme.small + 1
            selectByMouse: true
            clip: true
            onTextEdited: view.ctl.settingsText = text
            Text {
              anchors.fill: parent
              visible: search.text === ""
              text: "szukaj pokrętła…"
              color: Theme.dim2
              font: search.font
              verticalAlignment: Text.AlignVCenter
            }
          }
        }

        ListView {
          id: groupList
          objectName: "lista-grup"
          Layout.fillWidth: true
          Layout.fillHeight: true
          clip: true
          model: view.groups
          spacing: 2
          leftMargin: 10
          rightMargin: 10
          bottomMargin: 10
          boundsBehavior: Flickable.StopAtBounds
          ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }

          delegate: Rectangle {
            id: grow
            required property var modelData
            readonly property bool on: view.ctl.settingsText === "" && view.ctl.settingsGroup === modelData.nazwa
            objectName: "grupa-" + modelData.nazwa
            width: groupList.width - 20
            height: 34
            radius: 6
            color: on ? Theme.sur2 : (gmouse.containsMouse ? Theme.alpha(Theme.sur2, 0.5) : "transparent")
            function tryClick() { view.ctl.settingsText = ""; view.ctl.settingsGroup = modelData.nazwa }
            Text {
              anchors.left: parent.left
              anchors.leftMargin: 10
              anchors.right: counts.left
              anchors.rightMargin: 8
              anchors.verticalCenter: parent.verticalCenter
              text: grow.modelData.nazwa
              color: grow.on ? Theme.fg : Theme.fg2
              font.family: Theme.font
              font.pixelSize: Theme.body
              font.bold: grow.on
              elide: Text.ElideRight
            }
            Row {
              id: counts
              anchors.right: parent.right
              anchors.rightMargin: 10
              anchors.verticalCenter: parent.verticalCenter
              spacing: 6
              Rectangle {
                visible: grow.modelData.zmienione > 0
                width: chg.implicitWidth + 10
                height: 16
                radius: 8
                color: Theme.alpha(Theme.warn, 0.2)
                Text {
                  id: chg
                  anchors.centerIn: parent
                  text: grow.modelData.zmienione
                  color: Theme.warn
                  font.family: Theme.font
                  font.pixelSize: Theme.tiny
                }
              }
              Text {
                text: grow.modelData.ile
                color: Theme.dim
                font.family: Theme.font
                font.pixelSize: Theme.small
              }
            }
            MouseArea {
              id: gmouse
              anchors.fill: parent
              hoverEnabled: true
              cursorShape: Qt.PointingHandCursor
              onClicked: grow.tryClick()
            }
          }
        }
      }

      Rectangle { Layout.fillHeight: true; Layout.preferredWidth: 1; color: Theme.line }

      // ---------- zestawy run + lista pokręteł grupy
      ColumnLayout {
        Layout.fillWidth: true
        Layout.fillHeight: true
        spacing: 0

        Text {
          Layout.leftMargin: 22
          Layout.topMargin: 12
          Layout.bottomMargin: 8
          objectName: "tytul-listy"
          text: view.ctl.settingsText !== "" ? "WYNIKI „" + view.ctl.settingsText + "” (" + view.shown.length + ")"
                : (view.ctl.settingsGroup + " (" + view.shown.length + ")" + (view.ctl.settingsOnlyChanged ? " · tylko zmienione" : "")).toUpperCase()
          color: Theme.dim
          font.family: Theme.font
          font.pixelSize: Theme.tiny
          font.letterSpacing: 1
        }

        ListView {
          id: list
          objectName: "lista-pokretel"
          Layout.fillWidth: true
          Layout.fillHeight: true
          clip: true
          model: view.shown
          boundsBehavior: Flickable.StopAtBounds
          ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }

          // zestawy run z tryby.json: UH_CZAR + hotkey + koszt + mana jednym kliknięciem (jeden wpis dziennika = jedno Cofnij); przewijają się z listą
          header: Column {
            id: headCol
            width: list.width

            // ostrzeżenia: tryb z ostatniego startu nadpisze pokrętła; uszkodzony na_zywo.json (przewijają się z listą; przy wierszu stoi to samo)
            Item {
              objectName: "ostrzezenie-trybu"
              visible: view.conflictLine !== "" || view.fileError !== ""
              width: parent.width
              height: visible ? warnBox.height + 10 : 0
              Rectangle {
                id: warnBox
                x: 22
                y: 0
                width: parent.width - 44
                height: warnText.implicitHeight + 18
                radius: 8
                color: Theme.alpha(Theme.warn, 0.08)
                border.width: 1
                border.color: Theme.alpha(Theme.warn, 0.5)
                Text {
                  id: warnText
                  anchors.left: parent.left
                  anchors.right: parent.right
                  anchors.top: parent.top
                  anchors.margins: 9
                  text: (view.fileError !== "" ? "⚠ " + view.fileError + ": zapis zostanie odrzucony, dopóki plik jest uszkodzony. " : "")
                        + (view.conflictLine !== "" ? "⚠ " + view.conflictLine : "")
                  color: Theme.warn
                  font.family: Theme.font
                  font.pixelSize: Theme.small
                  wrapMode: Text.Wrap
                }
              }
            }

            Item {
              objectName: "zestawy-run"
              width: parent.width
              visible: view.showPresets
              height: visible ? presetCol.implicitHeight + 28 : 0
              Rectangle {
                anchors.fill: parent
                anchors.leftMargin: 22
                anchors.rightMargin: 22
                anchors.topMargin: 0
                anchors.bottomMargin: 8
                radius: 8
                color: Theme.sur
                border.width: 1
                border.color: Theme.line
              }
              Column {
                id: presetCol
                anchors.left: parent.left
                anchors.right: parent.right
                anchors.top: parent.top
                anchors.leftMargin: 34
                anchors.rightMargin: 34
                anchors.topMargin: 9
                spacing: 7
                Text {
                  text: "ZESTAWY RUN · jaką runę robi " + view.nick + " (czar, hotkey, koszt many, próg many)"
                  color: Theme.dim
                  font.family: Theme.font
                  font.pixelSize: Theme.tiny
                  font.letterSpacing: 1
                  width: parent.width
                  elide: Text.ElideRight
                }
                Flow {
                  width: parent.width
                  spacing: 8
                  Repeater {
                    model: view.presets
                    delegate: Rectangle {
                      id: preset
                      required property var modelData
                      readonly property bool on: Ust.presetActive(modelData, view.byKey)
                      objectName: "zestaw-" + modelData.tryb
                      width: Math.max(300, pcol.implicitWidth + 28)
                      height: pcol.implicitHeight + 14
                      radius: 8
                      color: on ? Theme.alpha(Theme.blue, 0.12) : (pmouse.containsMouse ? Theme.alpha(Theme.sur2, 0.6) : Theme.bg2)
                      border.width: 1
                      border.color: on ? Theme.blue : Theme.line2
                      function tryClick() { if (!on) view.ctl.applyPreset(modelData) }
                      Column {
                        id: pcol
                        anchors.left: parent.left
                        anchors.leftMargin: 12
                        anchors.verticalCenter: parent.verticalCenter
                        spacing: 3
                        Row {
                          spacing: 8
                          Text {
                            text: preset.modelData.tytul
                            color: Theme.fg
                            font.family: Theme.font
                            font.pixelSize: Theme.body
                            font.bold: true
                          }
                          Chip { small: true; label: "tryb " + preset.modelData.tryb }
                          Chip {
                            visible: preset.on
                            small: true
                            label: "ustawione"
                            textColor: Theme.ok
                          }
                        }
                        Text {
                          text: preset.modelData.opis
                          color: Theme.dim
                          font.family: Theme.font
                          font.pixelSize: Theme.small
                        }
                      }
                      MouseArea {
                        id: pmouse
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: preset.on ? Qt.ArrowCursor : Qt.PointingHandCursor
                        onClicked: preset.tryClick()
                      }
                    }
                  }
                }
              }
            }
          }

          delegate: KnobRow {
            required property var modelData
            width: list.width
            ctl: view.ctl
            p: modelData
            conflict: Ust.conflictFor(view.conflicts, modelData.klucz)
            flash: view.flashOn && view.ctl.focusKey === modelData.klucz
            showGroup: view.ctl.settingsText !== ""
          }

          Text {
            anchors.centerIn: parent
            visible: list.count === 0
            text: view.ctl.pokretlaError !== "" ? "błąd odczytu: " + view.ctl.pokretlaError
                  : (view.payload === null ? "ładowanie pokręteł…"
                     : (view.ctl.settingsOnlyChanged ? "nic nie różni się od domyślnych" : "brak pokręteł pasujących do wyszukiwania"))
            color: view.ctl.pokretlaError !== "" ? Theme.bad : Theme.dim
            font.family: Theme.font
            font.pixelSize: Theme.body
          }
        }
      }
    }

    // ---------- pasek zapisu: wynik ostatniej zmiany i Cofnij ostatnią (Q3: zapis od razu, bez "Zapisz")
    Rectangle {
      Layout.fillWidth: true
      Layout.preferredHeight: 62
      color: Theme.bg2
      Rectangle { anchors.top: parent.top; width: parent.width; height: 1; color: Theme.line }

      Column {
        anchors.left: parent.left
        anchors.leftMargin: 22
        anchors.right: undoBtn.left
        anchors.rightMargin: 16
        anchors.verticalCenter: parent.verticalCenter
        spacing: 4

        Text {
          objectName: "zapis-wynik"
          width: parent.width
          text: view.ctl.knobNote.text !== "" ? (view.ctl.knobNote.tone === "bad" ? "✗ " : "✓ ") + view.ctl.knobNote.text
                : (view.undoText !== null ? "Ostatnia zmiana z okna: " + view.undoText : "Zapis od razu po puszczeniu suwaka / kliknięciu · brak zmian z okna do cofnięcia")
          color: view.ctl.knobNote.tone === "bad" ? Theme.bad : (view.ctl.knobNote.tone === "ok" ? Theme.ok : Theme.fg)
          font.family: Theme.font
          font.pixelSize: Theme.body
          font.bold: view.ctl.knobNote.text !== ""
          elide: Text.ElideRight
        }
        Text {
          width: parent.width
          text: "zapis do " + (view.payload ? view.payload.plik : "…") + " przez walidację bota · kopia .bak-DATA-okno przy pierwszej zmianie dnia"
          color: Theme.dim
          font.family: Theme.font
          font.pixelSize: Theme.small
          elide: Text.ElideMiddle
        }
      }

      Btn {
        id: undoBtn
        objectName: "cofnij-ostatnia"
        anchors.right: parent.right
        anchors.rightMargin: 22
        anchors.verticalCenter: parent.verticalCenter
        label: "Cofnij ostatnią"
        active: view.undoText !== null
        busy: view.ctl.knobBusy
        onActivated: view.ctl.undo()
      }
    }
  }
}
