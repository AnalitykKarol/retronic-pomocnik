import QtQuick
import QtQuick.Layouts
import Quickshell
import "OknoModel.js" as Model
import "RetronicModel.js" as Rules

// Okno zarządzania Retronic (spec wtyczka-paska/specs/2026-10-19-retronic-okno.md, faza F2, F3): osobny proces Quickshella
// (`quickshell -p <repo>/okno/`, patrz ../okno.sh), niezależny od paska i powłoki Omarchy. Okno tylko czyta JSON z ../okno_api.py
// i woła skrypty bota; własnej logiki bota nie ma. Układ: pasek boczny 260 px + sekcja (Przegląd, Sesja gry, Ratunek, Mapa i tryb, Ustawienia) + stopka;
// Ctrl+K otwiera wyszukiwarkę pokręteł, map i trybów (F3).
ShellRoot {
  id: shell

  Backend { id: ctl }

  FloatingWindow {
    id: win
    title: "Retronic · okno zarządzania"
    // rozmiar: domyślnie jak makieta (1280x820); RETRONIC_OKNO_ROZMIAR=WxH tylko do testów układu
    readonly property var size: (Quickshell.env("RETRONIC_OKNO_ROZMIAR") || "1280x820").split("x")
    implicitWidth: Number(size[0])
    implicitHeight: Number(size[1])
    minimumSize: Qt.size(1000, 600)
    color: Theme.bg
    visible: true

    // zamknięcie okna kończy proces (jedno okno = jeden proces; okno.sh startuje go od nowa)
    onClosed: Qt.quit()
    onVisibleChanged: if (!visible) Qt.quit()

    Rectangle {
      id: root
      objectName: "okno-korzen"
      anchors.fill: parent
      color: Theme.bg

      ColumnLayout {
        anchors.fill: parent
        spacing: 0

        // ---------- pasek tytułu (makieta: .titlebar)
        Rectangle {
          Layout.fillWidth: true
          Layout.preferredHeight: 34
          color: Theme.bg2
          Rectangle { anchors.bottom: parent.bottom; width: parent.width; height: 1; color: Theme.line }
          Row {
            anchors.left: parent.left
            anchors.leftMargin: 14
            anchors.verticalCenter: parent.verticalCenter
            spacing: 10
            Text { text: "Retronic"; color: Theme.fg; font.family: Theme.font; font.pixelSize: Theme.small + 1; font.bold: true }
            Text { text: "okno zarządzania"; color: Theme.dim; font.family: Theme.font; font.pixelSize: Theme.small + 1 }
          }
          Rectangle {
            id: searchBtn
            objectName: "szukaj-przycisk"
            anchors.right: rightTitle.left
            anchors.rightMargin: rightTitle.visible ? 18 : 0
            anchors.verticalCenter: parent.verticalCenter
            width: searchRow.implicitWidth + 18
            height: 22
            radius: 5
            color: searchMouse.containsMouse ? Theme.sur2 : "transparent"
            border.width: 1
            border.color: searchMouse.containsMouse ? Theme.dim : Theme.line2
            function tryClick() { ctl.openPalette() }
            Row {
              id: searchRow
              anchors.centerIn: parent
              spacing: 8
              Text { text: "⌕ szukaj"; color: Theme.fg2; font.family: Theme.font; font.pixelSize: Theme.small }
              Text { text: "Ctrl K"; color: Theme.dim; font.family: Theme.font; font.pixelSize: Theme.tiny; anchors.verticalCenter: parent.verticalCenter }
            }
            MouseArea {
              id: searchMouse
              anchors.fill: parent
              hoverEnabled: true
              cursorShape: Qt.PointingHandCursor
              onClicked: searchBtn.tryClick()
            }
          }
          Text {
            id: rightTitle
            objectName: "tytul-prawy"
            anchors.right: parent.right
            anchors.rightMargin: 14
            anchors.verticalCenter: parent.verticalCenter
            visible: text !== ""
            text: ctl.ratunekData ? "ratunek: cień (Haiku " + Model.counters(ctl.ratunekData).haiku + ")" : ""
            color: Theme.dim
            font.family: Theme.font
            font.pixelSize: Theme.small + 1
          }
        }

        RowLayout {
          Layout.fillWidth: true
          Layout.fillHeight: true
          spacing: 0

          Sidebar {
            Layout.preferredWidth: 260
            Layout.fillHeight: true
            ctl: ctl
          }

          Item {
            Layout.fillWidth: true
            Layout.fillHeight: true

            Text {
              anchors.centerIn: parent
              visible: !ctl.loaded
              text: ctl.stanError !== "" ? "błąd odczytu stanu: " + ctl.stanError : "odczyt stanu botów…"
              color: ctl.stanError !== "" ? Theme.bad : Theme.dim
              font.family: Theme.font
              font.pixelSize: Theme.body
            }

            PrzegladView {
              objectName: "widok-przeglad"
              anchors.fill: parent
              visible: ctl.loaded && ctl.section === "przeglad"
              ctl: ctl
            }
            SesjaView {
              objectName: "widok-sesja"
              anchors.fill: parent
              visible: ctl.loaded && ctl.section === "sesja"
              ctl: ctl
            }
            RatunekView {
              objectName: "widok-ratunek"
              anchors.fill: parent
              visible: ctl.loaded && ctl.section === "ratunek"
              ctl: ctl
            }
            MapaView {
              objectName: "widok-mapa"
              anchors.fill: parent
              visible: ctl.loaded && ctl.section === "mapa"
              ctl: ctl
            }
            UstawieniaView {
              objectName: "widok-ustawienia"
              anchors.fill: parent
              visible: ctl.loaded && ctl.section === "ustawienia"
              ctl: ctl
            }
          }
        }

        // ---------- stopka: stan botów i czas odświeżenia
        Rectangle {
          Layout.fillWidth: true
          Layout.preferredHeight: 30
          color: Theme.bg2
          Rectangle { anchors.top: parent.top; width: parent.width; height: 1; color: Theme.line }

          Row {
            id: footLeft
            anchors.left: parent.left
            anchors.leftMargin: 14
            anchors.verticalCenter: parent.verticalCenter
            spacing: 16
            Row {
              spacing: 6
              Rectangle {
                width: 9; height: 9; radius: 4.5
                anchors.verticalCenter: parent.verticalCenter
                color: Model.runningCount(ctl.instances, ctl.statuses) > 0 ? Theme.ok : Theme.dim2
              }
              Text {
                objectName: "stopka-liczba"
                text: {
                  var n = Model.runningCount(ctl.instances, ctl.statuses)
                  return n === 0 ? "żaden bot nie działa" : n + " " + Model.pluralBots(n)
                }
                color: Theme.dim
                font.family: Theme.font
                font.pixelSize: Theme.small
              }
            }
            Text {
              objectName: "stopka-boty"
              width: Math.max(0, root.width - 260 - 14 - 190)
              text: Model.footerSummary(ctl.instances, ctl.statuses, Rules.stateLabel)
              color: Theme.dim
              font.family: Theme.font
              font.pixelSize: Theme.small
              elide: Text.ElideRight
            }
          }
          Text {
            objectName: "stopka-czas"
            anchors.right: parent.right
            anchors.rightMargin: 14
            anchors.verticalCenter: parent.verticalCenter
            text: ctl.stanError !== "" ? "błąd odczytu: " + ctl.stanError
                  : (ctl.refreshedAt ? "odświeżono " + Model.clock(ctl.refreshedAt) + " · co 2 s" : "odczyt…")
            color: ctl.stanError !== "" ? Theme.bad : Theme.dim
            font.family: Theme.font
            font.pixelSize: Theme.small
          }
        }
      }

      // Ctrl+K: wyszukiwarka (otwarta: ten sam skrót ją zamyka)
      Shortcut {
        sequences: ["Ctrl+K"]
        onActivated: if (ctl.paletteOpen) ctl.closePalette(); else ctl.openPalette()
      }

      Paleta {
        objectName: "paleta-nakladka"
        anchors.fill: parent
        ctl: ctl
      }
    }

    // Scenariusz testowy (tylko gdy ustawiony RETRONIC_OKNO_SCENARIUSZ): kroki, zrzuty, kliknięcia przez tryClick().
    Scenariusz {
      ctl: ctl
      target: root
    }
  }
}
